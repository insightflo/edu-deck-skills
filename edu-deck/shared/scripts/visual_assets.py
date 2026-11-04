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
