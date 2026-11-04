"""Exercise compact controls/state with real Chromium, including motion and rotation.
Compact = 1920×1080 원본 배치를 축소한 세로 스택. 스크롤만으로 단계가 열리고,
장 본문 탭은 줌 뷰어를 연다. 재배치·도식 글자 목록(.ed-diagram-labels)은 없다.
Usage: python3 test_responsive_interactions.py /path/to/test_responsive/output
"""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
S=Path(__file__).resolve().parents[1];sys.path.insert(0,str(S/'scripts'))
from check_deck import launch

SLIDE_SEL={'series':'#stage>.deck.on>.slide','other':'#stage>.slide'}
# 장 본문 탭 지점: 슬라이드 안이지만 조작 요소(버튼·퀴즈·탭·코드·핀)가 아닌 곳
TAP_PT='''(s=>{const r=s.getBoundingClientRect();
 const NO='a[href],button,input,textarea,select,summary,details,.chk,.tabs,.faq,.code,.todo,.pin-shot,.pin-list,.pin,.go,.notes,.sr';
 for(const y of [r.top+30,r.top+r.height*0.5,r.top+r.height-24])for(const x of [r.left+8,r.left+r.width*0.5,r.right-8]){
  const el=document.elementFromPoint(x,y);
  if(el&&el.closest('.slide')===s&&!el.closest(NO))return {x,y};
 }return null})'''
# 장이 뷰포트를 넘지 않고, 폭이 꽉 차거나(폭 기준 축소) 사용 높이에 맞으면(높이 기준 축소) 된다.
# 사용 높이 = 탐색줄 위 ~ 위쪽 막대 아래 사이 띈 높이 − 위아래 간격(responsive.js 의 GAP×2).
FIT='''(sel)=>{const nav=document.querySelector(".ed-reader-nav"),tb=document.querySelector(".ed-topbar");
 const navT=(nav&&nav.getClientRects().length)?nav.getBoundingClientRect().top:innerHeight;
 const topB=(tb&&tb.getClientRects().length)?tb.getBoundingClientRect().bottom:0;
 const avail=navT-topB-16;
 return [...document.querySelectorAll(sel)].every(s=>{const r=s.getBoundingClientRect();
  return r.width<=innerWidth+2&&(Math.abs(r.width-innerWidth)<=2||Math.abs(r.height-avail)<=2);})}'''
# 다음 점프로 장 머리에 맞춘 뒤 그 장 상자가 위쪽 막대 아래·탐색줄 위 사이에 온전히 드는가
BETWEEN='''(sel)=>{const nav=document.querySelector(".ed-reader-nav"),tb=document.querySelector(".ed-topbar");
 const navT=(nav&&nav.getClientRects().length)?nav.getBoundingClientRect().top:innerHeight;
 const topB=(tb&&tb.getClientRects().length)?tb.getBoundingClientRect().bottom:0;
 const i=deckInfo().slide,r=document.querySelectorAll(sel)[i].getBoundingClientRect();
 return {i:i,top:r.top,bot:r.bottom,topB:topB,navT:navT,ok:r.top>=topB-1&&r.bottom<=navT+1}}'''

def run(out):
 results=[];failures=[]
 def check(name,ok,data=None):
  results.append({'name':name,'pass':bool(ok),'data':data})
  if not ok:failures.append(name)
 def settle(p):p.wait_for_timeout(70)  # rAF 대기는 프레임이 멎은 헤드리스에서 멈출 수 있어 고정 시간으로 둔다
 with sync_playwright() as pw:
  b=launch(pw)
  for kind,path in [('classic',out/'fill/filltest.html'),('pack',out/'workbook/deck.html'),('series',out/'series/map.html')]:
   c=b.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   p.goto(path.as_uri());p.evaluate('localStorage.clear()');p.reload();p.evaluate('document.fonts.ready');settle(p)
   sel=SLIDE_SEL['series' if kind=='series' else 'other']
   def go(i,st=0):p.evaluate('(a)=>'+('deckGo("3",a[0],a[1])' if kind=='series' else 'deckGo(a[0],a[1])'),[i,st]);settle(p)
   # 세로 폰 안내: 장이 보이는 세로 폰에서 첫 진입에만 보이고 닫으면 이 세션엔 다시 안 뜬다
   go(0)
   hint_on=p.evaluate("(e=>!!e&&e.classList.contains('on'))(document.querySelector('.ed-zoom-hint'))")
   check(kind+' portrait hint shown',hint_on,p.evaluate("document.querySelector('.ed-zoom-hint')&&document.querySelector('.ed-zoom-hint').textContent"))
   if hint_on:
    p.locator('.ed-zoom-hint .x').tap();settle(p)
    check(kind+' hint dismissed',not p.evaluate("(e=>!!e&&e.classList.contains('on'))(document.querySelector('.ed-zoom-hint'))"))
    p.reload();p.evaluate('document.fonts.ready');settle(p)
    go(0)
    check(kind+' hint once per session',not p.evaluate("(e=>!!e&&e.classList.contains('on'))(document.querySelector('.ed-zoom-hint'))"))
   p.get_by_role('button',name='다음',exact=True).tap();p.wait_for_timeout(900)
   check(kind+' touch next is slide jump',p.evaluate('deckInfo().slide')==1,p.evaluate('deckInfo()'))
   top=p.evaluate(f'document.querySelectorAll("{sel}")[1].getBoundingClientRect().top')
   check(kind+' next lands on slide top',top<200,top)
   sizes=p.locator('.ed-reader-nav button').evaluate_all('(es)=>es.map(e=>({w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}))')
   check(kind+' 44px targets',all(x['w']>=44 and x['h']>=44 for x in sizes),sizes)
   check(kind+' slides fit viewport',p.evaluate(f'({FIT})("{sel}")'),p.evaluate('innerWidth'))
   # 스크롤만으로 다단계 장의 모든 단계가 열리고, 위로 돌려도 닫히지 않는다
   tgt=p.evaluate(f'''(()=>{{var slides=[...document.querySelectorAll("{sel}")],bi=-1,bm=0;slides.forEach((s,i)=>{{var m=0;s.querySelectorAll("[data-step],[data-add],[data-only],[data-lit],[data-until]").forEach(e=>{{["step","add","only","lit","until"].forEach(a=>{{if(e.dataset[a]!==undefined)m=Math.max(m,+e.dataset[a]);}});}});if(m>bm){{bm=m;bi=i;}}}});return bi;}})()''')
   check(kind+' has multi-step slide',tgt>=0,tgt)
   if tgt>=0:
    p.evaluate(f'window.scrollTo(0,document.querySelectorAll("{sel}")[{tgt}].getBoundingClientRect().top+window.scrollY-72)');settle(p)
    for _ in range(60):
     p.evaluate('window.scrollBy(0,240)');p.wait_for_timeout(40)
     if p.evaluate(f'document.querySelectorAll("{sel}")[{tgt}].getBoundingClientRect().bottom<innerHeight*0.85'):break
    settle(p)
    left=p.evaluate(f'({{sh:document.querySelectorAll("{sel}")[{tgt}].querySelectorAll(".step-hide").length,ag:document.querySelectorAll("{sel}")[{tgt}].querySelectorAll("[data-add].gone").length}})')
    check(kind+' scroll reveals all steps',left['sh']==0 and left['ag']==0,left)
    p.evaluate('window.scrollBy(0,-700)');settle(p)
    back=p.evaluate(f'({{sh:document.querySelectorAll("{sel}")[{tgt}].querySelectorAll(".step-hide").length,ag:document.querySelectorAll("{sel}")[{tgt}].querySelectorAll("[data-add].gone").length}})')
    check(kind+' scroll back keeps steps',back['sh']==0 and back['ag']==0,back)
   check(kind+' no page overflow',p.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),p.evaluate('document.documentElement.scrollWidth'))
   check(kind+' no diagram labels',p.evaluate('document.querySelectorAll(".ed-diagram-labels,.ed-diagram-scroll,.ed-diagram-reader").length===0'))
   # ---- 줌 뷰어: 장 본문 탭 → 같은 장을 현재 단계 그대로 크게 본다 ----
   if tgt>=0:
    p.evaluate(f'window.scrollTo(0,document.querySelectorAll("{sel}")[{tgt}].getBoundingClientRect().top+window.scrollY-72)');settle(p)
    live=p.evaluate(f'(()=>{{const s=document.querySelectorAll("{sel}")[{tgt}];return {{hid:s.querySelectorAll(".step-hide").length,gone:s.querySelectorAll(".gone").length,title:(s.querySelector(".title")||s).textContent.slice(0,40)}}}})()')
    pt=p.evaluate(f'({TAP_PT})(document.querySelectorAll("{sel}")[{tgt}])')
    check(kind+' tap point found',pt is not None,pt)
    if pt:
     info=p.evaluate('deckInfo()')
     p.touchscreen.tap(pt['x'],pt['y']);settle(p)
     check(kind+' tap opens zoom',p.locator('.ed-zoom.on').count()==1 and p.evaluate('document.querySelector(".ed-zoom").getAttribute("role")==="dialog"&&document.querySelector(".ed-zoom").getAttribute("aria-modal")==="true"'))
     check(kind+' zoom same slide',p.evaluate(f'document.querySelector(".ed-zoom-num").textContent.startsWith("{tgt+1} /")'),p.evaluate('document.querySelector(".ed-zoom-num")&&document.querySelector(".ed-zoom-num").textContent'))
     clone=p.evaluate('(()=>{const c=document.querySelector(".ed-zoom .slide");return {hid:c.querySelectorAll(".step-hide").length,gone:c.querySelectorAll(".gone").length,title:(c.querySelector(".title")||c).textContent.slice(0,40)}})()')
     check(kind+' zoom same step state',clone['title']==live['title'] and clone['hid']==live['hid'] and clone['gone']==live['gone'],(live,clone))
     check(kind+' zoom engine untouched',p.evaluate('(a)=>deckInfo().slide===a.slide&&deckInfo().step===a.step',info),p.evaluate('deckInfo()'))
     p.touchscreen.tap(pt['x'],pt['y']);p.touchscreen.tap(pt['x'],pt['y']);settle(p)
     k=p.evaluate('(s=>parseFloat(s.match(/scale\\(([^)]+)\\)/)[1]))(document.querySelector(".ed-zoom-box").style.transform)')
     base=390/1920
     check(kind+' double-tap zooms 2.5x',abs(k-base*2.5)<base*0.15,(k,base))
     n0=p.evaluate('document.querySelector(".ed-zoom-num").textContent')
     p.locator('.ed-zoom-next').tap();settle(p)
     n1=p.evaluate('document.querySelector(".ed-zoom-num").textContent')
     check(kind+' zoom next',n0!=n1,(n0,n1))
     p.locator('.ed-zoom-prev').tap();settle(p)
     check(kind+' zoom prev',p.evaluate('document.querySelector(".ed-zoom-num").textContent')==n0)
     p.locator('.ed-zoom-x').tap();settle(p)
     check(kind+' zoom closes',p.locator('.ed-zoom.on').count()==0)
     p.touchscreen.tap(pt['x'],pt['y']);settle(p)
     check(kind+' zoom reopens',p.locator('.ed-zoom.on').count()==1)
     p.keyboard.press('Escape');settle(p)
     check(kind+' zoom escape closes',p.locator('.ed-zoom.on').count()==0)
   p.get_by_role('button',name='설명',exact=True).tap();settle(p)
   check(kind+' study readable',p.evaluate('document.body.classList.contains("st-self")&&parseFloat(getComputedStyle(document.querySelector(".st-pb")).fontSize)>=16'))
   check(kind+' study no animations',p.evaluate('document.getAnimations().filter(a=>a.playState==="running").length===0'))
   p.get_by_role('button',name='설명',exact=True).tap();p.get_by_role('button',name='노트',exact=True).tap()
   check(kind+' notes',p.locator('#notes').is_visible() and bool(p.locator('#notesText').inner_text()))
   p.get_by_role('button',name='노트',exact=True).tap();p.get_by_role('button',name='용어집',exact=True).tap()
   check(kind+' glossary',p.locator('#st-gloss').is_visible());p.keyboard.press('Escape')
   p.get_by_role('button',name='인쇄',exact=True).tap();check(kind+' print chooser',p.locator('#st-choose').is_visible());p.keyboard.press('Escape')
   go(1,1);before=p.evaluate('deckInfo()')
   for w,h in [(844,390),(768,1024),(1920,1080),(320,740),(390,844)]:
    p.set_viewport_size({'width':w,'height':h});settle(p)
    # 회전해도 장은 유지되고 열린 단계는 닫히지 않는다(더 큰 화면이 더 많이 여는 것은 허용)
    after=p.evaluate('deckInfo()');check(kind+f' rotate {w} state',after['slide']==before['slide'] and after['step']>=before['step'],(before,after));before=after
    check(kind+f' rotate {w} fit',p.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
   # 폰 가로(844×390)도 세로 읽기: 스크롤로 단계가 열린다
   p.set_viewport_size({'width':844,'height':390});settle(p)
   check(kind+' landscape is compact',p.evaluate('document.documentElement.classList.contains("ed-compact")'))
   check(kind+' landscape hint stays off',not p.evaluate("(e=>!!e&&e.classList.contains('on'))(document.querySelector('.ed-zoom-hint'))"))
   if tgt>=0:
    p.evaluate(f'window.scrollTo(0,document.querySelectorAll("{sel}")[{tgt}].getBoundingClientRect().top+window.scrollY-72)');settle(p)
    p.evaluate('(a)=>'+('deckGo("3",a[0],0)' if kind=='series' else 'deckGo(a[0],0)'),[tgt]);settle(p)
    for _ in range(60):
     p.evaluate('window.scrollBy(0,120)');p.wait_for_timeout(40)
     if p.evaluate(f'document.querySelectorAll("{sel}")[{tgt}].getBoundingClientRect().bottom<innerHeight*0.85'):break
    settle(p)
    left=p.evaluate(f'document.querySelectorAll("{sel}")[{tgt}].querySelectorAll(".step-hide").length')
    check(kind+' landscape scroll reveals',left==0,left)
    check(kind+' landscape no overflow',p.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
    check(kind+' landscape slides fit',p.evaluate(f'({FIT})("{sel}")'))
    navh=p.evaluate('(n=>n.getBoundingClientRect().height)(document.querySelector(".ed-reader-nav"))')
    check(kind+' landscape nav one row',navh<=80,navh)
   # 가로·세로 폰 모두: 다음으로 장 머리에 맞추면 장 상자가 위쪽 막대 아래와 탐색줄 위 사이에 온전히 든다
   for w,h in [(844,390),(390,844)]:
    p.set_viewport_size({'width':w,'height':h});settle(p)
    go(0)
    for _ in range(3):
     p.get_by_role('button',name='다음',exact=True).tap();p.wait_for_timeout(150)
     m=p.evaluate(f'({BETWEEN})("{sel}")')
     check(kind+f' slide fits chrome {w}x{h} #{m["i"]}',m['ok'],m)
    go(p.evaluate('deckInfo().count-1'));settle(p)
    m=p.evaluate(f'({BETWEEN})("{sel}")')
    check(kind+f' last slide fits chrome {w}x{h}',m['ok'],m)
   p.set_viewport_size({'width':390,'height':844});settle(p)
   if kind!='pack':
    go(27,0);p.wait_for_timeout(60)
    check(kind+' moving scene no overflow',p.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),p.evaluate('document.documentElement.scrollWidth'))
    p.emulate_media(reduced_motion='reduce');p.wait_for_timeout(600)  # 시작된 효과의 해제 프레임을 기다린다
    check(kind+' reduced stops',p.evaluate('document.getAnimations().filter(a=>a.playState==="running").length===0'))
    go(53,0)
    p.locator('.slide.active .chk-o:not([data-ok])').first.scroll_into_view_if_needed();settle(p)
    p.locator('.slide.active .chk-o:not([data-ok])').first.tap();settle(p)
    check(kind+' quiz wrong feedback',p.locator('.slide.active .chk-ng').count()>0)
    check(kind+' quiz tap no zoom',p.locator('.ed-zoom.on').count()==0)
    p.locator('.slide.active .chk-again').scroll_into_view_if_needed();p.locator('.slide.active .chk-again').tap();settle(p)
    p.locator('.slide.active .chk-o[data-ok]').first.tap();settle(p)
    check(kind+' quiz correct feedback',p.locator('.slide.active .chk-ok').count()>0)
    mark=p.locator('.slide.active .chk-right').first.evaluate('(e)=>{const b=e.getBoundingClientRect(),m=e.querySelector(".ed-mark").getBoundingClientRect();return {buttonHeight:b.height,markHeight:m.height};}')
    check(kind+' grading mark fits answer',mark['markHeight']<=mark['buttonHeight']+12,mark)
    saved=p.evaluate('deckInfo()');p.set_viewport_size({'width':844,'height':390});settle(p)
    check(kind+' quiz survives rotation',p.locator('.slide.active .chk-ok').count()>0 and saved==p.evaluate('deckInfo()'))
    p.set_viewport_size({'width':390,'height':844});settle(p)
   p.emulate_media(media='print');p.evaluate('dispatchEvent(new Event("beforeprint"))');settle(p)
   dims=p.locator('.deck.on .slide' if kind=='series' else '.slide').first.evaluate('(s)=>({width:s.getBoundingClientRect().width,height:s.getBoundingClientRect().height})')
   check(kind+' print 1920 canvas',dims['width']==1920 and dims['height']==1080,dims)
   check(kind+' print hides controls',not p.locator('.ed-reader-nav').is_visible() and not p.locator('.ed-zoom-hint').is_visible())
   p.emulate_media(media='screen');p.evaluate('dispatchEvent(new Event("afterprint"))');settle(p)
   check(kind+' no JS errors',not errors,errors);c.close()
  # 데스크톱·slide-fit 에서는 지금처럼 클릭 한 번에 한 단계씩 넘어간다
  c=b.new_context(viewport={'width':1920,'height':1080});p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
  p.goto((out/'fill/filltest.html').as_uri());p.wait_for_timeout(400)
  check('desktop not compact',not p.evaluate('document.documentElement.classList.contains("ed-compact")'))
  check('desktop no zoom on tap',p.evaluate('document.querySelectorAll(".ed-zoom.on").length===0'))
  i=p.evaluate('[...document.querySelectorAll("#stage>.slide")].findIndex(s=>s.querySelectorAll("[data-step]").length>0)')
  p.evaluate('i=>deckGo(i,0)',i);p.mouse.click(1600,500);p.wait_for_timeout(200)
  check('desktop click advances one step',p.evaluate('(a)=>deckInfo().slide===a&&deckInfo().step===1',i),p.evaluate('deckInfo()'))
  c.close()
  c=b.new_context(viewport={'width':1024,'height':768},has_touch=True);p=c.new_page()
  p.goto((out/'fill/filltest.html').as_uri());p.wait_for_timeout(400)
  check('slidefit not compact',p.evaluate('document.documentElement.classList.contains("ed-slidefit")') and not p.evaluate('document.documentElement.classList.contains("ed-compact")'))
  p.evaluate('i=>deckGo(i,0)',i);p.tap('#stage');p.wait_for_timeout(200)
  check('slidefit tap advances one step',p.evaluate('deckInfo().step')==1,p.evaluate('deckInfo()'))
  check('slidefit tap no zoom',p.locator('.ed-zoom.on').count()==0)
  c.close()
  b.close()
 (out/'interactions.json').write_text(json.dumps({'results':results,'failures':failures},ensure_ascii=False,indent=2))
 print(f'{len(results)} assertions; {len(failures)} failures');print('\n'.join(failures));return bool(failures)
if __name__=='__main__':sys.exit(run(Path(sys.argv[1])))
