"""Real browser regression for readable compact decks; never suppresses overflow.
Compact is the authored 1920×1080 slide scaled to the viewport — this test breaks
if a slide's rendered width stops matching the viewport, if the page overflows
horizontally, if the scaled layout drifts from the desktop layout, or if compact
re-creates reflow artifacts (e.g. .ed-diagram-labels).
Run: python3 shared/dev/test_responsive.py --out /path/to/evidence [--baseline]
"""
import argparse,json,sys,shutil,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
S=Path(__file__).resolve().parents[1]
ROOT=S.parent.parent
sys.path.insert(0,str(S/'scripts'))
from build_deck import build
from check_deck import launch
from resource_packs import DESIGNS

# 슬라이드 안 지점들을 장 폭 비율로 정규화해 모아 둔다 — 같은 장을 다른 화면 폭에서
# 잰 뒤 norm 을 비교하면 "재배치 없이 축소" 계약이 지켜지는지 확인할 수 있다.
MEASURE="""()=>{
 const s=document.querySelector('#stage>.deck.on>.slide.active')||document.querySelector('.slide.active'), rect=s.getBoundingClientRect();
 const ok=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&!e.closest('.gone,[hidden],.notes,.sr');};
 const seen=new Set(),picks=[];
 for(const e of [...s.children,...s.querySelectorAll('.title,.big,.card,.win,.chk,.eyebrow,.code,.tbl,.lane')])if(ok(e)&&!seen.has(e)){seen.add(e);picks.push(e);}
 const norm=picks.slice(0,24).map(e=>{const r=e.getBoundingClientRect();return [+((r.left-rect.left)/rect.width).toFixed(4),+((r.top-rect.top)/rect.width).toFixed(4),+(r.width/rect.width).toFixed(4),+(r.height/rect.width).toFixed(4)];});
 const nav=document.querySelector('.ed-reader-nav'),tb=document.querySelector('.ed-topbar');
 const navT=(nav&&nav.getClientRects().length)?nav.getBoundingClientRect().top:innerHeight;
 const topB=(tb&&tb.getClientRects().length)?tb.getBoundingClientRect().bottom:0;
 return {width:rect.width,height:rect.height,pageWidth:document.documentElement.scrollWidth,viewport:innerWidth,avail:navT-topB-16,slidefit:document.documentElement.classList.contains('ed-slidefit'),scale:getComputedStyle(document.getElementById('stage')).getPropertyValue('--ed-s').trim(),labels:document.querySelectorAll('.ed-diagram-labels').length,norm};
}"""
def norm_maxdiff(a,b):
 if len(a)!=len(b):return 999
 return max(abs(x-y) for p,q in zip(a,b) for x,y in zip(p,q)) if a else 0

def fixtures(out):
 fill=out/'fill'
 subprocess.run([sys.executable,str(S/'dev/fill_test.py'),str(fill)],check=True)
 subprocess.run([sys.executable,str(S/'scripts/build_deck.py'),str(fill)],check=True)
 for d in DESIGNS:
  dest=out/d
  subprocess.run([sys.executable,str(S/'scripts/resource_packs.py'),'init',str(dest),'--design',d,'--flow','problem','--title','근거를 확인하고 업무에 적용하기'],check=True)
  from bs4 import BeautifulSoup
  for source in (dest/'src').glob('*.html'):
   soup=BeautifulSoup(source.read_text(),'html.parser')
   soup.select_one('.notes').string=('자료의 작성자와 기준 날짜를 먼저 확인합니다. 업무 요청을 받으면 필요한 자료와 완료 조건을 따로 적어 봅니다. 사실과 아직 확인하지 못한 추측을 구분하고 짝과 답을 비교하세요. 근거가 부족한 부분은 다음 확인 항목으로 남깁니다. 선택한 이유를 한 문장으로 설명해 봅니다.')
   source.write_text(str(soup))
  subprocess.run([sys.executable,str(S/'scripts/build_deck.py'),str(dest)],check=True)
 series=out/'series';series.mkdir(exist_ok=True)
 for d in ['editorial','workbook','fill']:
  shutil.copytree(out/d,series/d,dirs_exist_ok=True)
 for hub in ['map','shelf','list']:
  (series/'series.json').write_text(json.dumps({'title':'반응형 교육 시리즈','output':hub+'.html','hub':{'type':hub},'episodes':[{'ep':str(i+1),'folder':d,'label':f'{i+1}편','title':d,'sub':'모바일에서도 내용과 진도를 보존합니다'} for i,d in enumerate(['editorial','workbook','fill'])]},ensure_ascii=False))
  subprocess.run([sys.executable,str(ROOT/'edu-deck-series/scripts/build_series.py'),str(series)],check=True)
 return fill/'filltest.html'

def run(out,baseline=False):
 out.mkdir(parents=True,exist_ok=True)
 deck=fixtures(out)
 rows=[];failures=[]
 with sync_playwright() as pw:
  browser=launch(pw)
  p=browser.new_page(viewport={'width':390,'height':844},reduced_motion='reduce')
  p.goto(deck.as_uri());p.evaluate('document.fonts.ready');p.evaluate('deckGo(1,9)')
  m=p.evaluate(MEASURE)
  p.screenshot(path=str(out/'phone-initial.png'),full_page=True)
  rows.append({'case':'initial-390','measure':m})
  if abs(m['width']-390)>2:failures.append(f"390px slide rendered width {m['width']:.2f} != viewport")
  if m['pageWidth']>391:failures.append(f'390px horizontal overflow: pageWidth={m["pageWidth"]}')
  if m['labels']:failures.append('compact produced .ed-diagram-labels')
  if baseline:
   (out/'results.json').write_text(json.dumps({'rows':rows,'failures':failures},indent=2));browser.close()
   print(json.dumps({'rows':rows,'failures':failures},indent=2));return bool(failures)
  for w,h in [(320,740),(390,844),(768,1024),(1024,768),(1920,1080),(844,390)]:
   p.set_viewport_size({'width':w,'height':h});p.wait_for_timeout(80)
   for i in range(57):
    p.evaluate('i=>deckGo(i,0)',i)
    maxstep=p.evaluate('deckInfo().maxStep')
    for step in range(maxstep+1):
     p.evaluate('(a)=>deckGo(a[0],a[1])',[i,step])
     m=p.evaluate(MEASURE)
     row={'case':'classic','width':w,'height':h,'slide':i,'step':step,'full':step==maxstep,**m};rows.append(row)
     if m['pageWidth']>w+1:failures.append(f'classic {w}/{i}/{step}: page overflow {m["pageWidth"]}')
     if w<1200 and not m['slidefit']:
      # 세로 읽기: 장은 폭 또는 사용 높이에 맞춰 축소되고(둘 중 작은 쪽) 재배치·도식 글자 목록은 없다
      if m['width']>w+2 or not(abs(m['width']-w)<=2 or abs(m['height']-m['avail'])<=2):
       failures.append(f'classic {w}/{i}/{step}: slide {m["width"]:.2f}x{m["height"]:.2f} fits neither viewport {w} nor avail {m["avail"]:.2f}')
      if m['labels']:failures.append(f'classic {w}/{i}/{step}: .ed-diagram-labels present')
     elif m['width']>w+1:failures.append(f'classic {w}/{i}/{step}: slide wider than viewport ({m["width"]:.2f}>{w})')
   if w==390:
    for i in [1,2,3,8,12,27,53,55]:
     p.evaluate('i=>deckGo(i,99)',i);p.screenshot(path=str(out/f'classic-390-{i}.png'),full_page=True)
  for design in DESIGNS:
   p.goto((out/design/'deck.html').as_uri());p.evaluate('document.fonts.ready')
   for w,h in [(320,740),(390,844),(768,1024),(1024,768),(1920,1080),(844,390)]:
    p.set_viewport_size({'width':w,'height':h});p.wait_for_timeout(80)
    for i in range(p.evaluate('deckInfo().count')):
     p.evaluate('i=>deckGo(i,99)',i);m=p.evaluate(MEASURE);rows.append({'case':design,'width':w,'slide':i,'full':True,**m})
     if m['pageWidth']>w+1:failures.append(f'{design} {w}/{i}: page overflow {m["pageWidth"]}')
     if w<1200 and not m['slidefit']:
      if m['width']>w+2 or not(abs(m['width']-w)<=2 or abs(m['height']-m['avail'])<=2):
       failures.append(f'{design} {w}/{i}: slide {m["width"]:.2f}x{m["height"]:.2f} fits neither viewport {w} nor avail {m["avail"]:.2f}')
      if m['labels']:failures.append(f'{design} {w}/{i}: .ed-diagram-labels present')
     elif m['width']>w+1:failures.append(f'{design} {w}/{i}: slide wider than viewport')
    if w==390:p.screenshot(path=str(out/f'{design}-390.png'),full_page=True)
  for hub in ['map','shelf','list']:
   p.goto((out/'series'/f'{hub}.html').as_uri());p.evaluate('localStorage.clear()');p.reload();p.evaluate('document.fonts.ready')
   for w,h in [(320,740),(390,844),(768,1024),(1024,768),(1920,1080),(844,390)]:
    p.set_viewport_size({'width':w,'height':h});p.wait_for_timeout(80)
    p.locator('#homebtn').evaluate('(b)=>b.click()')
    m=p.evaluate('()=>({width:document.documentElement.scrollWidth,title:parseFloat(getComputedStyle(document.querySelector(".hub-title")).fontSize)*document.querySelector(".hub-canvas").getBoundingClientRect().width/1920})')
    rows.append({'case':hub,'width':w,'measure':m})
    if m['width']>w+1:failures.append(f'hub {hub}/{w}: overflow')
    if w==390:p.screenshot(path=str(out/f'hub-{hub}-390.png'),full_page=True)
    for ep in ['1','2','3']:
     p.evaluate('ep=>deckGo(ep,1,99)',ep);m=p.evaluate(MEASURE);rows.append({'case':hub+'-episode','ep':ep,'width':w,'full':True,**m})
     if m['pageWidth']>w+1:failures.append(f'episode {hub}/{ep}/{w}: page overflow {m["pageWidth"]}')
     if w<1200 and not m['slidefit']:
      if m['width']>w+2 or not(abs(m['width']-w)<=2 or abs(m['height']-m['avail'])<=2):
       failures.append(f'episode {hub}/{ep}/{w}: slide {m["width"]:.2f}x{m["height"]:.2f} fits neither viewport {w} nor avail {m["avail"]:.2f}')
      if m['labels']:failures.append(f'episode {hub}/{ep}/{w}: .ed-diagram-labels present')
     elif m['width']>w+1:failures.append(f'episode {hub}/{ep}/{w}: slide wider than viewport')
  browser.close()
 # 모든 화면 폭에서 같은 장의 정규화 배치가 1920 기준과 1% 안으로 같은지 확인한다.
 # 대상은 "전 단계 공개" 장(row.full) — 단계 표시 집합이 같아야 배치 비교가 공평하다.
 bycase={}
 for r in rows:
  if r.get('full') and 'norm' in r:
   key=(r['case'],r.get('slide'),r.get('ep'))
   bycase.setdefault(key,{})[r['width']]=r['norm']
 for key,ws in bycase.items():
  base=ws.get(1920)
  if not base:continue
  # classic 은 공유 자산만 쓰므로 1% 엄밀 비교. 팩 디자인(series 편 포함)은 디자인
  # 자체의 @media(min-width) 규칙이 뷰포트에 반응해 약간 달라질 수 있어 3% 까지 허용.
  tol=0.01 if key[0]=='classic' else 0.03
  for w,norm in ws.items():
   if w==1920:continue
   d=norm_maxdiff(base,norm)
   if d>tol:failures.append(f'{key} @ {w}: layout drift vs 1920 = {d:.3f} (norm len {len(norm)} vs {len(base)})')
 (out/'results.json').write_text(json.dumps({'rows':rows,'failures':failures},ensure_ascii=False,indent=2))
 print(f'{len(rows)} measurements, {len(failures)} failures');print('\n'.join(failures[:30]))
 return bool(failures)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--baseline',action='store_true');args=ap.parse_args();sys.exit(run(args.out,args.baseline))
