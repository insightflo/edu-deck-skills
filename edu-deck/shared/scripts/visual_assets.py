"""Inline the shared design layer without network, installs or legacy fixtures."""
import base64
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]/'assets'
def common_css():
    font=(BASE/'fonts/PretendardVariable.woff2').read_bytes()
    if font[:4]!=b'wOF2':
        raise ValueError('PretendardVariable.woff2 is not a WOFF2 font')
    license=(BASE/'fonts/OFL.txt').read_text(encoding='utf-8')
    # OFL notice travels in every delivered standalone HTML, not only the sources.
    return ('/* Embedded unmodified Pretendard v1.3.9.\n'+license.replace('*/','* /')+'\n*/\n'
        +"@font-face{font-family:'Pretendard Variable';font-style:normal;font-weight:100 900;font-display:block;src:url(data:font/woff2;base64,"
        +base64.b64encode(font).decode('ascii')+") format('woff2')}\n"
        +(BASE/'css/tokens.css').read_text(encoding='utf-8')+'\n'
        +(BASE/'css/themes.css').read_text(encoding='utf-8')+'\n'
        +(BASE/'css/visual-motion.css').read_text(encoding='utf-8')+'\n'
        +(BASE/'css/responsive.css').read_text(encoding='utf-8')+'\n'
        +(BASE/'css/viewer.css').read_text(encoding='utf-8'))
def motion_js():
    text=((BASE/'js/responsive.js').read_text(encoding='utf-8')+'\n'
          +(BASE/'js/motion.js').read_text(encoding='utf-8')+'\n'
          +(BASE/'js/patterns.js').read_text(encoding='utf-8')+'\n'
          +(BASE/'js/viewer.js').read_text(encoding='utf-8')+'\n'
          +(BASE/'js/talk.js').read_text(encoding='utf-8'))
    if '</script' in text.lower():raise ValueError('motion.js cannot contain an HTML script closing tag')
    return text

# deck.json 'font' 선택 목록 — 모두 SIL OFL, 원문 라이선스는 assets/fonts/ 에 함께 저장된다.
#   pretendard      : 기본값 — 셸에 이미 임베드(추가 CSS 없음)
#   gowun-dodum     : 초등 친화 부드러운 고딕 (Gowun Dodum Regular, OFL-GowunDodum.txt)
#   gowun-batang    : 격식 있는 명조 계열 (Gowun Batang Regular, OFL-GowunBatang.txt)
# 외부 웹폰트 URL 금지 — 파일 안에 임베드한다. 새 폰트를 넣을 때는 OFL 원문도 같이 둔다.
FONTS={
    'pretendard':None,
    'gowun-dodum':{'family':'Gowun Dodum','file':'GowunDodum-Regular.woff2',
                   'license':'OFL-GowunDodum.txt','weight':'400'},
    'gowun-batang':{'family':'Gowun Batang','file':'GowunBatang-Regular.woff2',
                    'license':'OFL-GowunBatang.txt','weight':'400'},
}
def font_css(key):
    """[목적] deck.json font 키가 고른 글꼴을 임베드하는 CSS 조각을 만든다.
    [입력] key: FONTS 목록 키('pretendard' 이면 빈 문자열 — 셸 기본 내장 사용)
    [출력] @font-face(실명 등록)+본문·팩 변수 덮어쓰기 CSS. 실패 시 BuildError 아닌
      ValueError — 호출부(build_deck.build)에서 사용자 메시지로 바꾼다.
    [원칙] 글꼴은 실명으로 등록하고 라이선스 원문을 주석으로 운반한다.
      legacy 는 body 스택을, 팩 덱은 .slide.pack 의 --pack-sans/serif/mono 변수를 덮는다 —
      도움말·토스트 같은 발표 도구 요소는 셸 스택(Pretendard)을 유지한다.
    """
    if key in (None,'pretendard'):
        return ''
    spec=FONTS.get(key)
    if spec is None:
        raise ValueError(f"알 수 없는 font 키입니다: {key}")
    font=(BASE/'fonts'/spec['file']).read_bytes()
    if font[:4]!=b'wOF2':
        raise ValueError(f"{spec['file']} is not a WOFF2 font")
    license=(BASE/'fonts'/spec['license']).read_text(encoding='utf-8')
    fam=spec['family']
    fall="'Apple SD Gothic Neo','Malgun Gothic','맑은 고딕','Noto Sans KR','Noto Sans CJK KR',sans-serif"
    return ('/* deck.json font="'+key+'" — Embedded unmodified '+fam+'.\n'+license.replace('*/','* /')+'\n*/\n'
        +f"@font-face{{font-family:'{fam}';font-style:normal;font-weight:{spec['weight']};font-display:block;src:url(data:font/woff2;base64,"
        +base64.b64encode(font).decode('ascii')+f") format('woff2')}}\n"
        # visual-motion.css 의 'body,.slide,.pack' 스택과 같은 선택자로 덮어 쓴다 —
        # 셸 도움말·토스트 같은 발표 도구 요소는 자체 스택(Pretendard)을 유지한다.
        +f"body,.slide,.pack{{font-family:'{fam}',{fall}}}\n"
        +f".slide.pack{{--pack-sans:'{fam}',sans-serif;--pack-serif:'{fam}',sans-serif;--pack-mono:'{fam}',sans-serif}}\n")
