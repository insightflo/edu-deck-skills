#!/usr/bin/env python3
"""Regenerate both shipped shells from packaged sources, offline.

Owner: dev/{shell_template,pack_shell_template}.html, assets/css/core.css,
assets/js/{study,motion,responsive}.js, css/{tokens,visual-motion,responsive}.css and fonts/.
No Downloads fixture, CSS extraction, icon rewrite or package installation.
The generated shells retain exactly the five public build markers.
"""
import sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'scripts'))
from visual_assets import common_css,motion_js

def main():
    study=(BASE/'assets/js/study.js').read_text(encoding='utf-8')
    if '</script' in study.lower():raise ValueError('study.js contains an HTML script closing tag')
    parts={'/*COMMON_CSS*/':common_css(),'/*CORE_CSS*/':(BASE/'assets/css/core.css').read_text(),
           '/*MOTION_JS*/':motion_js(),'/*STUDY_JS*/':study}
    for source,target in [('shell_template.html','shell.html'),('pack_shell_template.html','pack-shell.html')]:
        text=(BASE/'dev'/source).read_text(encoding='utf-8')
        for mark,value in parts.items():text=text.replace(mark,value)
        for mark in ('{{TITLE}}','/*EXTRA_CSS*/','<!--ICONS-->','<!--SLIDES-->','<!--STUDY_DATA-->'):
            if text.count(mark)!=1:raise ValueError(f'{source}: invalid public marker {mark}')
        (BASE/'assets'/target).write_text(text,encoding='utf-8')
        print(f'OK {target} {len(text.encode())} bytes')
if __name__=='__main__':main()
