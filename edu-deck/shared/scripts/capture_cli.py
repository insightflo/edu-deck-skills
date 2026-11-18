#!/usr/bin/env python3
"""capture_cli.py — 실제 CLI 명령을 실행해 stdout/stderr/exit code 를 캡처하고
edu-deck 에 바로 삽입할 수 있는 HTML 스니펫 + 메타 JSON 을 낸다 (실물 캐리어 수집기·경량판).

[왜] 교육 덱의 CLI 설명은 '실제로 돌아간 출력'을 싣는 신뢰가 있다. 손으로 옮겨 적으면
     낡고, 지어내면 실물이 아니다. 이 도구는 명령을 직접 실행해 그 출력을 .code / .win-frame /
     pre / screen-cite 계열에 붙여 넣을 수 있는 조각으로 수집한다. 출력 조각에는 실행 사실
     (exit code · 소요 시간 · 생성 시각)이 함께 남는다.
[입력] capture_cli.py --cmd "..." --out <출력.html> [--title "..."] [--max-lines 30]
                      [--timeout 30] [--mask-home] [--json <메타.json>] [--win-frame]
     --cmd       실행할 셸 명령(/bin/sh -c 로 실행 — 파이프·리다이렉션 가능).
     --out       HTML 스니펫 경로.
     --title     창 제목(없으면 명령어로 쓴다).
     --max-lines stdout/stderr 각각 남길 최대 줄(초과분은 '⋯ 외 N줄 생략' 표시).
     --timeout   초 단위 제한(초과 시 종료시키고 부분 출력 + 표시).
     --mask-home 홈 디렉터리(/Users/<사용자>·/home/<사용자>)를 ~ 로 가린다.
                 토큰 패턴(ghp_·sk-·AKIA·Bearer …)은 항상 가린다(설정 없음 — 실수 유출 방지).
     --json      메타 JSON 경로(명령·exit·줄 수·마스킹 수·원본 sha256 — 재현 대조용).
     --win-frame .win-frame(조각 55) 래퍼로 감싼다. 기본은 pre 안에 넣는 안쪽 조각만
                 (.code 패턴의 .p/.out/.c 규약 — ANSI 색은 인라인 스타일이므로 어디서든 유지).
[출력] HTML 스니펫 + (지정 시) 메타 JSON. ANSI SGR(색·굵게 등)은 안전한 span 인라인 스타일로
     변환하고 본문은 HTML 이스케이프된다. 밝은 배경 pre 에 넣을 때 ANSI 색상값은 어두운
     배경(.code 블록 등) 기준이므로 주의한다. 컬러가 안 나오는 명령은 도구 스스로
     '--color=always' 계열 플래그를 붙여 주면 색이 잡힌다(이 도구는 가짜 pty 를 안 쓴다).
[의존] 표준 라이브러리만 사용.
[출처] 개념 참조: awesomezun/awesome-showreels(MIT) — '실물 캡처를 덱 캐리어로 수집' 개념만
     참조한 클린룸 구현(원본 코드·식별자 미참조).
"""
import argparse
import hashlib
import html
import json
import pathlib
import re
import subprocess
import sys
import time

VERSION = "1.0.0"

# ── xterm 팔레트(어두운 배경 기준 조정) · 256색 큐브/회색은 규격값 ──────────────
PAL16 = [  # 30–37 표준
    "#5c6370", "#e06c75", "#98c379", "#e5c07b",
    "#61afef", "#c678dd", "#56b6c2", "#d7dae0",
]
PAL16_BRIGHT = [  # 90–97
    "#7f848e", "#ff7b86", "#a9e07f", "#ffd479",
    "#84c4ff", "#e2a2ff", "#7fe0e8", "#ffffff",
]


def _palette256():
    pal = list(PAL16) + list(PAL16_BRIGHT)
    levels = [0, 95, 135, 175, 215, 255]
    for r in levels:
        for g in levels:
            for b in levels:
                pal.append(f"#{r:02x}{g:02x}{b:02x}")
    for i in range(24):
        v = 8 + i * 10
        pal.append(f"#{v:02x}{v:02x}{v:02x}")
    return pal


PAL256 = _palette256()

# ── ANSI 이스케이프 인식(비-SGR 시퀀스는 제거) ────────────────────────────────
RE_ESC = re.compile(
    r"\x1b(?:"
    r"\[[0-9:;?]*[ -/]*[@-~]"      # CSI — 끝글자 m 이면 SGR, 아니면 버림
    r"|\][^\x07\x1b]*(?:\x07|\x1b\\)?"  # OSC(창 제목 등) — 버림
    r"|\([AB012]"                   # 문자셋 지정 — 버림
    r"|[=>78DEHMc]"                 # 기타 단일 이스케이프 — 버림
    r")"
)


RE_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+")  # \t·\n 제외 제어문자 — 미인식 ESC 잔여 포함 전부 제거


def _sanitize(chunk):
    # 인식된 이스케이프 외에 남은 ESC·제어문자는 브라우저로 흘러가지 못하게 여기서 끝낸다
    return RE_CTRL.sub("", chunk).replace("\x1b", "")


def _style_css(st):
    """SGR 상태 → CSS 문자열(없으면 None). reverse 는 렌더 시 fg/bg 교환으로 반영."""
    fg, bg = st["fg"], st["bg"]
    if st["rev"]:
        fg, bg = bg, fg
    parts = []
    if fg:
        parts.append(f"color:{fg}")
    if bg:
        parts.append(f"background:{bg}")
    if st["bold"]:
        parts.append("font-weight:700")
    deco = []
    if st["ul"]:
        deco.append("underline")
    if st["strike"]:
        deco.append("line-through")
    if deco:
        parts.append("text-decoration:" + " ".join(deco))
    if st["dim"]:
        parts.append("opacity:.6")
    if st["italic"]:
        parts.append("font-style:italic")
    if st["hidden"]:
        parts.append("opacity:0")
    return ";".join(parts) or None


def _new_state():
    return {"fg": None, "bg": None, "bold": False, "dim": False, "italic": False,
            "ul": False, "strike": False, "rev": False, "hidden": False}


def _apply_sgr(st, param_str):
    params = [int(p) if p else 0 for p in param_str.replace(":", ";").split(";")] or [0]
    i = 0
    while i < len(params):
        p = params[i]
        if p == 0:
            st.update(_new_state())
        elif p == 1:
            st["bold"] = True
        elif p == 2:
            st["dim"] = True
        elif p == 3:
            st["italic"] = True
        elif p == 4:
            st["ul"] = True
        elif p in (21, 22):
            st["bold"] = st["dim"] = False
        elif p == 23:
            st["italic"] = False
        elif p == 24:
            st["ul"] = False
        elif p == 7:
            st["rev"] = True
        elif p == 27:
            st["rev"] = False
        elif p == 8:
            st["hidden"] = True
        elif p == 28:
            st["hidden"] = False
        elif p == 9:
            st["strike"] = True
        elif p == 29:
            st["strike"] = False
        elif 30 <= p <= 37:
            st["fg"] = PAL16[p - 30]
        elif p == 39:
            st["fg"] = None
        elif 40 <= p <= 47:
            st["bg"] = PAL16[p - 40]
        elif p == 49:
            st["bg"] = None
        elif 90 <= p <= 97:
            st["fg"] = PAL16_BRIGHT[p - 90]
        elif 100 <= p <= 107:
            st["bg"] = PAL16_BRIGHT[p - 100]
        elif p in (38, 48):
            key = "fg" if p == 38 else "bg"
            if i + 1 < len(params) and params[i + 1] == 5 and i + 2 < len(params):
                n = params[i + 2]
                if 0 <= n < 256:
                    st[key] = PAL256[n]
                i += 2
            elif i + 4 < len(params) and params[i + 1] == 2:
                r, g, b = (max(0, min(255, v)) for v in params[i + 2:i + 5])
                st[key] = f"#{r:02x}{g:02x}{b:02x}"
                i += 4
        i += 1


def ansi_to_html(text):
    """ANSI 이스케이프가 섞인 텍스트를 HTML 이스케이프 + 인라인 스타일 span 으로 변환."""
    out = []
    st = _new_state()
    open_css = None

    def emit(chunk, css):
        nonlocal open_css
        chunk = _sanitize(chunk)
        if not chunk:
            return
        if open_css is not None and css != open_css:
            out.append("</span>")
            open_css = None
        if css is not None and open_css is None:
            out.append(f'<span style="{css}">')
            open_css = css
        out.append(chunk)

    pos = 0
    for m in RE_ESC.finditer(text):
        if m.start() > pos:
            emit(html.escape(text[pos:m.start()], quote=False), _style_css(st))
        seq = m.group(0)
        if re.fullmatch(r"\x1b\[[0-9:;]*m", seq):
            _apply_sgr(st, seq[2:-1])
        # 비-SGR 시퀀스는 조용히 버린다
        pos = m.end()
    if pos < len(text):
        emit(html.escape(text[pos:], quote=False), _style_css(st))
    if open_css is not None:
        out.append("</span>")
    return "".join(out)


# ── 터미널 프레임 정리: \r\n 정규화, \r=덮어쓰기(마지막 프레임), \b=지우기 ──────
def clean_frames(text):
    lines = [ln.split("\r")[-1] for ln in text.replace("\r\n", "\n").split("\n")]
    text = "\n".join(lines)
    while "\x08" in text:
        new = re.sub(r"[^\x08]\x08", "", text).replace("\x08", "")
        if new == text:
            break
        text = new
    return text


# ── 마스킹: 토큰은 항상, 홈 경로는 --mask-home 일 때 ──────────────────────────
TOKEN_PATTERNS = [
    ("github-token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}\b"),
     lambda m: m.group(1) + "_•••"),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b"),
     lambda m: "github_pat_•••"),
    ("openai", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
     lambda m: "sk-•••"),
    ("slack", re.compile(r"\b(xox[baprs])-([A-Za-z0-9-]{10,})\b"),
     lambda m: m.group(1) + "-•••"),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
     lambda m: "AKIA•••"),
    ("google-key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
     lambda m: "AIza•••"),
    ("google-oauth", re.compile(r"\bya29\.[A-Za-z0-9_-]{10,}\b"),
     lambda m: "ya29.•••"),
    ("bearer", re.compile(r"\b(Bearer)[ \t]+[A-Za-z0-9._~+/=-]{16,}\b"),
     lambda m: m.group(1) + " •••"),
]


def mask_text(text, mask_home):
    counts = {"home_paths": 0, "tokens": {}}
    if mask_home:
        home = str(pathlib.Path.home())
        counts["home_paths"] += text.count(home)
        text = text.replace(home, "~")
        def _other(m):
            counts["home_paths"] += 1
            return m.group(0).rsplit("/", 1)[0] + "/•"
        text = re.sub(r"/(?:Users|home)/[A-Za-z0-9._-]+", _other, text)
    for kind, rx, repl in TOKEN_PATTERNS:
        n = len(rx.findall(text))
        if n:
            counts["tokens"][kind] = n
            text = rx.sub(repl, text)
    return text, counts


def cap_lines(text, limit):
    """(남긴 텍스트, 총 줄, 잘린 줄 수) — 끝의 빈 줄(마지막 개행)은 세지 않는다."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    kept, dropped = lines[:limit], max(0, len(lines) - limit)
    return "\n".join(kept), len(lines), dropped


# ── 조각 조립(.code 패턴 규약: .p 프롬프트 · .out 출력 · .c 주석 — 명령만 복사됨) ──
def build_fragment(cmd, out_html, out_drop, err_html, err_drop, exit_code, timed_out,
                   dur_s, max_lines):
    parts = [f'<span class="p">$ </span>{html.escape(cmd, quote=False)}']
    if out_html:
        parts.append(f'<span class="out">{out_html}</span>')
    if out_drop:
        parts.append(f'<span class="c">⋯ 외 {out_drop}줄 생략 (stdout · max {max_lines})</span>')
    if err_html:
        parts.append('<span class="c">── stderr ──</span>')
        parts.append(f'<span class="out" style="color:var(--danger)">{err_html}</span>')
    if err_drop:
        parts.append(f'<span class="c">⋯ 외 {err_drop}줄 생략 (stderr · max {max_lines})</span>')
    tail = f"exit {exit_code}" if not timed_out else f"시간 초과 {dur_s:.0f}s (부분 출력)"
    if not out_html and not err_html:
        parts.append(f'<span class="c"># (출력 없음 — {tail})</span>')
    else:
        parts.append(f'<span class="c"># {tail} · {dur_s:.2f}s</span>')
    return "\n".join(parts)


def clip(s, n):
    return s if len(s) <= n else s[: n - 1] + "…"


def comment_safe(s):
    return re.sub(r"-{2,}", "–", s).replace(">", "›")


def build_win_frame(fragment, title, tag):
    return (
        f'<div class="win-frame">\n'
        f'  <div class="wf-bar"><span class="wf-dots"><i></i><i></i><i></i></span>'
        f'<span class="wf-title">{html.escape(title, quote=False)}</span>'
        f'<span class="wf-tag">{html.escape(tag, quote=False)}</span></div>\n'
        f'  <div class="wf-body">\n'
        f'    <div class="code">\n'
        f'      <div class="code-head"><span>터미널 — 실물 캡처</span>'
        f'<button type="button" class="code-copy">복사</button></div>\n'
        f'<pre>{fragment}</pre>\n'
        f'    </div>\n'
        f'  </div>\n'
        f'</div>\n'
    )


def main():
    ap = argparse.ArgumentParser(
        prog="capture_cli.py",
        description="CLI 명령 실물 캡처 → edu-deck HTML 스니펫 + 메타 JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--cmd", required=True, help='실행할 셸 명령 (예: "git log --oneline -5")')
    ap.add_argument("--out", required=True, help="출력 HTML 스니펫 경로")
    ap.add_argument("--title", help="창 제목(기본: 명령어)")
    ap.add_argument("--max-lines", type=int, default=30, help="스트림별 최대 줄(기본 30)")
    ap.add_argument("--timeout", type=float, default=30.0, help="제한 시간 초(기본 30)")
    ap.add_argument("--mask-home", action="store_true",
                    help="홈 디렉터리(/Users/·/home/)를 ~ 로 가림(토큰은 항상 가림)")
    ap.add_argument("--json", help="메타 JSON 출력 경로")
    ap.add_argument("--win-frame", action="store_true",
                    help=".win-frame(조각 55) 래퍼로 감싸기(기본: pre 안쪽 조각)")
    a = ap.parse_args()

    t0 = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(a.cmd, shell=True, capture_output=True, timeout=a.timeout)
        raw_out, raw_err, exit_code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        timed_out = True
        raw_out = e.stdout or b""
        raw_err = e.stderr or b""
        exit_code = None
    dur_s = time.monotonic() - t0

    # 명령문 자체에도 마스킹 — $ 에코·주석·제목·JSON 모두 가려진 명령으로 낸다(유출 경로 차단)
    cmd_shown, _ = mask_text(clean_frames(a.cmd), a.mask_home)

    def pipeline(raw):
        text = clean_frames(raw.decode("utf-8", errors="replace"))
        text, _ = mask_text(text, a.mask_home)
        kept, total, dropped = cap_lines(text, a.max_lines)
        return kept, ansi_to_html(kept), total, dropped, text

    out_kept, out_html, out_total, out_drop, out_full = pipeline(raw_out)
    err_kept, err_html, err_total, err_drop, err_full = pipeline(raw_err)
    joined = clean_frames((raw_out + b"\n" + raw_err).decode("utf-8", errors="replace"))
    _, mask_counts = mask_text(joined, a.mask_home)

    fragment = build_fragment(cmd_shown, out_html, out_drop, err_html, err_drop,
                              exit_code, timed_out, dur_s, a.max_lines)
    title = a.title or clip(cmd_shown, 28)
    tag = "시간초과" if timed_out else f"exit {exit_code}"
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    comment = (f"<!-- capture_cli.py 실물 캡처 · cmd: {comment_safe(cmd_shown)} · {tag} · "
               f"{stamp} -->\n")
    page = (build_win_frame(fragment, title, tag) if a.win_frame else fragment + "\n")

    out_path = pathlib.Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(comment + page, encoding="utf-8")

    if a.json:
        meta = {
            "tool": "capture_cli.py", "version": VERSION,
            "cmd": cmd_shown, "title": a.title,
            "exit_code": exit_code, "timed_out": timed_out,
            "duration_ms": round(dur_s * 1000),
            "timeout_sec": a.timeout, "max_lines": a.max_lines,
            "mask_home": a.mask_home, "masked": mask_counts,
            "stdout": {"bytes": len(raw_out), "lines_total": out_total,
                       "lines_kept": min(out_total, a.max_lines)},
            "stderr": {"bytes": len(raw_err), "lines_total": err_total,
                       "lines_kept": min(err_total, a.max_lines)},
            "raw_sha256": {"stdout": hashlib.sha256(raw_out).hexdigest(),
                           "stderr": hashlib.sha256(raw_err).hexdigest()},
            "excerpt": {"stdout": out_full[:8192], "stderr": err_full[:8192]},  # 가려진 본문
            "generated_at_utc": stamp, "platform": sys.platform,
        }
        jp = pathlib.Path(a.json)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    msum = f"마스킹 홈 {mask_counts['home_paths']}·토큰 {sum(mask_counts['tokens'].values())}"
    print(f"캡처 완료: {tag} · {dur_s:.2f}s · stdout {out_total}줄/stderr {err_total}줄 · {msum}")
    print(f"HTML: {out_path}" + (" (win-frame)" if a.win_frame else ""))
    if a.json:
        print(f"JSON: {pathlib.Path(a.json)}")


if __name__ == "__main__":
    main()
