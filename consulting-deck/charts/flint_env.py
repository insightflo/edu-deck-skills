#!/usr/bin/env python3
"""flint-chart 환경 감지·설치·상태 기록 도구.

하위명령:
  check                 flint 설치 여부 3계층 감지 보고. exit 0=설치됨 · 1=없음 · 2=node 자체 없음
  install [--dir DIR]   flint-package.json(핀)을 FLINT_HOME에 복사해 npm install — 최초 1회 네트워크
  state get [키]        상태 파일(~/.edu-deck/flint-state.json) 읽기
  state set <키> <값>   상태 파일의 키를 JSON 값으로 쓰기

FLINT_HOME 해석: 환경변수 FLINT_HOME → 없으면 ~/.edu-deck/flint/.
저장소에는 node_modules를 반입하지 않는다(머신 로컬 설치).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CHARTS_DIR = Path(__file__).resolve().parent
PIN_PACKAGE = CHARTS_DIR / "flint-package.json"
STATE_PATH = Path.home() / ".edu-deck" / "flint-state.json"
PINNED = {"flint-chart": "1.0.1", "vega": "6.4.0", "vega-lite": "6.5.0"}


def flint_home() -> Path:
    return Path(os.environ.get("FLINT_HOME") or (Path.home() / ".edu-deck" / "flint")).expanduser()


def state_path() -> Path:
    return STATE_PATH


def load_state() -> dict:
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1}


def save_state(state: dict) -> None:
    state_path().parent.mkdir(parents=True, exist_ok=True)
    state.setdefault("version", 1)
    state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def node_ok() -> bool:
    return shutil.which("node") is not None


def _resolve_version(pkg_dir: Path) -> str | None:
    try:
        return json.loads((pkg_dir / "package.json").read_text(encoding="utf-8")).get("version")
    except Exception:
        return None


def _node_resolve(home: Path) -> tuple[bool, str | None]:
    """flint-chart/render 가 실제로 해석되는지 node로 확인. (성공, 버전)"""
    pkg = home / "node_modules" / "flint-chart" / "package.json"
    if not pkg.exists():
        return False, None
    code = (
        "const{createRequire}=require('module');"
        f"const r=createRequire({json.dumps(str(home / 'package.json'))});"
        "const p=r.resolve('flint-chart/render');"
        "console.log(p)"
    )
    try:
        out = subprocess.run(["node", "-e", code], capture_output=True, timeout=30, cwd=home)
    except Exception:
        return False, None
    if out.returncode != 0:
        return False, None
    return True, _resolve_version(pkg.parent)


def check() -> int:
    home = flint_home()
    print("# flint-chart 환경 감지")
    if not node_ok():
        print("node: 없음 — node >=18 필요. 설치 후 다시 확인")
        return 2
    print(f"node: 있음 ({subprocess.run(['node', '--version'], capture_output=True).stdout.decode().strip()})")
    ok, ver = _node_resolve(home)
    if ok:
        print(f"설치: FLINT_HOME={home} flint-chart {ver} — flint-chart/render 해석 OK")
    else:
        print(f"설치: FLINT_HOME={home} 없음 또는 해석 실패")

    # 2계층: npx 캐시 — 있어도 파이프라인 경로는 아님(보고만)
    try:
        cache = subprocess.run(["npm", "config", "get", "cache"], capture_output=True, timeout=15)
        npx_root = Path(cache.stdout.decode().strip()) / "_npx"
        hit = npx_root.exists() and any((p / "node_modules" / "flint-chart").exists() for p in npx_root.iterdir() if p.is_dir())
        print(f"npx 캐시: {'flint-chart 발견(보고만 — 파이프라인은 FLINT_HOME 사용)' if hit else '없음'}")
    except Exception:
        print("npx 캐시: 확인 불가")

    # 3계층: MCP 등록 — 저작 보조(선택)
    mcp_hit = []
    for cfg in (Path.home() / ".pi/agent/mcp.json", Path(".pi/mcp.json")):
        try:
            if cfg.exists() and "flint" in json.loads(cfg.read_text(encoding="utf-8")).get("mcpServers", {}):
                mcp_hit.append(str(cfg))
        except Exception:
            pass
    print(f"MCP flint 서버: {'등록됨 ' + ', '.join(mcp_hit) if mcp_hit else '미등록(선택 — 생성은 flint_gen.mjs)'}")
    st = load_state()
    st["installed"] = ok
    if ver:
        st.setdefault("versions", {})["flint-chart"] = ver
    save_state(st)
    return 0 if ok else 1


def install(target: Path | None) -> int:
    home = target or flint_home()
    if not node_ok() or shutil.which("npm") is None:
        print("FAIL node/npm 없음 — 설치 불가", file=sys.stderr)
        return 2
    home.mkdir(parents=True, exist_ok=True)
    shutil.copy(PIN_PACKAGE, home / "package.json")
    print(f"핀 패키지 복사 → {home/'package.json'} (flint-chart·vega·vega-lite 정확 버전)")
    r = subprocess.run(["npm", "install", "--no-audit", "--no-fund", "--loglevel=warn"], cwd=home)
    if r.returncode != 0:
        print("FAIL npm install — 네트워크 확인", file=sys.stderr)
        return 1
    # 소스맵·src 정리(기본 켬): 약 160MB → 약 55MB
    removed = 0
    for m in home.rglob("*.map"):
        try:
            removed += m.stat().st_size
            m.unlink()
        except OSError:
            pass
    src = home / "node_modules" / "flint-chart" / "src"
    if src.exists():
        for f in src.rglob("*"):
            if f.is_file():
                try:
                    removed += f.stat().st_size
                except OSError:
                    pass
        shutil.rmtree(src)
    print(f"정리: 소스맵·flint-chart/src 제거 — {removed/1e6:.0f}MB 절약")
    ok, ver = _node_resolve(home)
    if ok:
        st = load_state()
        st["installed"] = True
        st["versions"] = {k: _resolve_version(home / "node_modules" / k / "") or v for k, v in PINNED.items()}
        save_state(st)
        print(f"OK flint-chart {ver} → {home} (check exit 0)")
        return 0
    print("FAIL 설치 후 해석 실패", file=sys.stderr)
    return 1


def state_cmd(argv: list) -> int:
    if len(argv) < 1 or argv[0] not in ("get", "set"):
        print("사용법: state get [키] | state set <키> <json값>", file=sys.stderr)
        return 2
    if argv[0] == "get":
        st = load_state()
        if len(argv) == 1:
            print(json.dumps(st, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(st.get(argv[1]), ensure_ascii=False))
        return 0
    if len(argv) < 3:
        print("사용법: state set <키> <json값>", file=sys.stderr)
        return 2
    st = load_state()
    try:
        st[argv[1]] = json.loads(argv[2])
    except json.JSONDecodeError:
        st[argv[1]] = argv[2]
    save_state(st)
    print(f"{argv[1]} = {json.dumps(st[argv[1]], ensure_ascii=False)} → {state_path()}")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "check":
        return check()
    if cmd == "install":
        target = None
        if "--dir" in rest:
            i = rest.index("--dir")
            target = Path(rest[i + 1]).expanduser()
        return install(target)
    if cmd == "state":
        return state_cmd(rest)
    print(f"알 수 없는 명령: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
