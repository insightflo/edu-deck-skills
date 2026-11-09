#!/usr/bin/env python3
"""capture_deck.py — 공통 도구로 위임하는 호환 경로

본체는 edu-deck/shared/scripts/capture_deck.py(전 스킬 공용 승격본)다.
이 파일은 기존 경로(컨설팅 스킬 문서·세션 기록) 호환을 위해 남겨뒀고,
인자 그대로 본체를 실행한다. 기능·출력 계약은 본체를 따른다.
"""
import pathlib
import runpy
import sys

SHARED = pathlib.Path(__file__).resolve().parents[2] / 'edu-deck/shared/scripts/capture_deck.py'
if not SHARED.exists():
    print(f'FAIL: 공통 본체가 없습니다 — {SHARED}', file=sys.stderr)
    sys.exit(2)
runpy.run_path(str(SHARED), run_name='__main__')
