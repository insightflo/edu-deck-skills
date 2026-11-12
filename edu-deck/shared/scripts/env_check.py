#!/usr/bin/env python3
"""[목적] edu-deck-solo 을 돌리기 전에 이 머신의 실행 환경(모듈·브라우저·PDF 도구·네트워크·검색 CLI)을 확인한다.
[사용법] python3 env_check.py [검색후보CLI이름 ...]
[입출력] 표준 출력으로 항목별 OK/없음 보고서. 종료 코드는 항상 0 — 이 보고서 자체가 결과다(실패 개수로 판정하지 않는다).
[연결] references/research.md 3절(조사 경로 고르기), references/runtimes.md(실행기별 도구·명령).
[주의] 실행기 자체에 웹 검색 도구가 있는지는 이 스크립트가 알 수 없다. 도구 목록은 각 실행기 화면/문서에서 확인하고 research.md 3절 경로표를 따른다.
[수정시 주의] 표준 라이브러리만 쓴다. 검색 CLI 이름을 여기에 하드코딩하지 않는다(인자로 받는다). 네트워크 확인은 실제 GET 1회뿐.
"""
import importlib.util
import shutil
import subprocess
import sys
import urllib.request

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
]
MODULES = [  # (모듈명, 없으면 영향)
    ("bs4", "check_deck·verify_sources 실행 불가"),
    ("lxml", "check_deck 실행 불가"),
    ("PIL", "check_deck 스크린샷 검사 불가"),
    ("playwright", "check_deck 화면 검사 불가(exit 3)"),
    ("pypdf", "PDF 대조는 pdftotext 에 의존"),
]


def module_ok(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def main() -> None:
    print("# edu-deck-solo 환경 확인")
    print(f"python: {sys.version.split()[0]}")

    missing = []
    for name, effect in MODULES:
        ok = module_ok(name)
        print(f"모듈 {name}: {'OK' if ok else '없음 → ' + effect}")
        if not ok:
            missing.append(name)

    chrome = next((p for p in CHROME_PATHS if __import__("os").path.exists(p)), None)
    if module_ok("playwright"):
        print("브라우저: playwright 설치됨 — 실제 실행은 check_deck 이 시험한다(없으면 Chrome 채널 시도)")
    if chrome:
        print(f"브라우저: Chrome 있음 → {chrome}")
    elif not module_ok("playwright"):
        print("브라우저: playwright·Chrome 모두 없음 → 화면 검사 불가(check_deck exit 3)")

    pdftotext = shutil.which("pdftotext")
    print(f"PDF 대조: {'pdftotext 있음' if pdftotext else 'pdftotext 없음'} + pypdf {'있음' if module_ok('pypdf') else '없음'}"
          + ("" if pdftotext or module_ok("pypdf") else " → PDF 원문대조 불가"))

    node = shutil.which("node")
    print(f"node: {'있음 (' + node + ')' if node else '없음 → chart_gen·flint 생성 불가'}")
    print("차트 flint: python3 consulting-deck/charts/flint_env.py check 로 확인(컨설팅 덱 차트 선택 엔진)")

    net_status = None
    try:
        req = urllib.request.Request(
            "https://www.law.go.kr/main.html",
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko,en;q=0.8"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            net_status = r.status
        print(f"네트워크: law.go.kr HTTP {net_status} → 셸 가져오기(--fetch·curl) 가능")
    except Exception as e:
        print(f"네트워크: law.go.kr 접속 실패({type(e).__name__}) → --fetch·curl 불가. 자체 검색 도구가 있어도 원문대조는 못 한다")

    clis = []
    for name in sys.argv[1:]:
        path = shutil.which(name)
        if not path:
            print(f"검색 CLI {name}: 없음")
            continue
        try:
            out = subprocess.run([name, "--version"], capture_output=True, timeout=15)
            ver = (out.stdout or out.stderr).decode(errors="replace").strip().splitlines()[0]
        except Exception:
            ver = "버전 확인 실패"
        print(f"검색 CLI {name}: 있음 ({ver})")
        clis.append(name)

    print("- 조사 경로 제안 (최종 판단은 research.md 3절 경로표 + 실행기 자체 도구 유무)")
    if net_status:
        if clis:
            print(f"  자체 검색 도구 없음 → B(외부 검색 CLI): {', '.join(clis)} 후보, runtimes.md 명령으로 1문항 시험 후 사용")
        else:
            print("  자체 검색 도구 없음 → C(공식 누리집 직접 가져오기). 검색 CLI 후보를 인자로 주면 확인한다")
    else:
        print("  셸 네트워크 불가 → 자체 검색 도구 없으면 D(멈추고 사용자에게 자료 요청). 확인 표시를 손으로 만들지 않는다")
    print("RESULT: env_check 완료 (이 보고서가 결과)")


if __name__ == "__main__":
    main()
