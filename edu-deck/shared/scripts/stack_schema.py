#!/usr/bin/env python3
"""data-c="stack" 도식 데이터(data-d JSON) 검사기 — stack.js 의 규칙과 같은 상수를 쓴다.

    from stack_schema import check, StackSchemaError
    warnings = check(payload_dict)          # 형태·배치 오류는 StackSchemaError 로 던진다
    warnings = check_data_d("data-d 속성 문자열")

- 형태 오류(형식·허용값·개수·중복 칸·그룹 덮음·중첩 초과) → StackSchemaError(빌드 실패).
- 칸 넘침(글자가 칸 폭을 넘어 …으로 줄어 그려질 것) → 경고 문자열 목록.
- data-d 규칙: HTML 속성에 작은따옴표로 감싸는 JSON — 안쪽에 ' 는 쓸 수 없다.
"""
import json
import re
import sys
from pathlib import Path

# 격자 상수 — assets/kit/stack.js 의 같은 이름 상수와 반드시 같게 둔다.
T, BW, BH, PX, PY = 64, 176, 110, 204, 166
OX, OY, GPX, GPT, GPB, NEST = 40, 44, 12, 40, 8, 12

ROWS, COLS = range(3), range(6)            # row 0~2 · col 0~5
NODES_MIN, NODES_MAX = 2, 14
EDGES_MAX, GROUPS_MAX = 20, 5
TONES = {"plain", "brand", "dark", "accent"}
GTONES = {"plain", "brand", "accent"}
KINDS = {"main", "sub", "dash"}
NAME_W, ROLE_W, EL_W, GL_W = 19, 14, 14, 16       # 각 글자 크기(px)
NAME_MAX, ROLE_MAX, EL_MAX = BW - 6, BW - 6, 104  # 각 칸 폭(px)

ICONS_FILE = Path(__file__).resolve().parents[1] / "assets" / "kit" / "vendor" / "lucide-subset.json"


class StackSchemaError(Exception):
    """형태·배치 오류 — 빌드를 멈춰야 하는 결함."""


def icon_names():
    try:
        return set(json.loads(ICONS_FILE.read_text(encoding="utf-8"))["icons"])
    except Exception:
        return set()


def est_width(s, size, weight):
    """캔버스 없이 가늠하는 글자 폭(px). 한글은 글자 크기 그대로, 라틴·숫자는 0.58배로 잡는다."""
    w = 0.0
    for ch in str(s):
        if ch.isspace():
            w += size * 0.3
        elif ord(ch) > 0x2E7F:      # 한글·CJK·전각 기호
            w += size
        elif ch in "iIlj.,'\"|!":
            w += size * 0.3
        else:
            w += size * 0.58
    return w * (1.04 if weight >= 700 else 1.0)


def _cells(o):
    seen = {}
    for n in o["nodes"]:
        key = (n["row"], n["col"])
        if key in seen:
            raise StackSchemaError(f"같은 칸 row{key[0]} col{key[1]} 에 노드 '{seen[key]}'·'{n['id']}' 가 겹친다")
        seen[key] = n["id"]
    return seen


def _geometry(o):
    """stack.js geometry 와 같은 좌표 — 노드·그룹 상자를 계산한다."""
    N = {n["id"]: dict(n, cx=OX + n["col"] * PX + BW / 2, top=OY + n["row"] * PY) for n in o["nodes"]}
    G = {g["id"]: dict(g, kids=[]) for g in o.get("groups", [])}
    for g in G.values():
        if g.get("parent") in G:
            G[g["parent"]]["kids"].append(g["id"])
    cache = {}

    def rect(g):
        if g["id"] in cache:
            return cache[g["id"]]
        c0, c1, r0, r1 = float("inf"), float("-inf"), float("inf"), float("-inf")
        for nid in g.get("nodes", []):
            n = N.get(nid)
            if not n:
                continue
            c0, c1 = min(c0, n["col"]), max(c1, n["col"])
            r0, r1 = min(r0, n["row"]), max(r1, n["row"])
        if g.get("cols"):
            c0, c1 = g["cols"]
        has = c0 != float("inf")
        x0 = OX + c0 * PX - GPX if has else float("inf")
        x1 = OX + c1 * PX + BW + GPX if has else float("-inf")
        y0 = OY + r0 * PY - GPT if has else float("inf")
        y1 = OY + r1 * PY + BH + GPB if has else float("-inf")
        for kid in g["kids"]:
            k = rect(G[kid])
            x0, x1 = min(x0, k[0] - NEST), max(x1, k[2] + NEST)
            y0, y1 = min(y0, k[1] - 30), max(y1, k[3] + NEST)
        cache[g["id"]] = (x0, y0, x1, y1)
        return cache[g["id"]]

    return N, G, rect


def check(o):
    """payload 객체 검사. 반환값 = 경고(칸 넘침) 문자열 목록."""
    if not isinstance(o, dict):
        raise StackSchemaError("data-d 는 객체여야 한다")
    for key in o:
        if key not in {"nodes", "edges", "groups"}:
            raise StackSchemaError(f"알 수 없는 키 '{key}' — nodes·edges·groups 만 쓴다")
    nodes, edges, groups = o.get("nodes"), o.get("edges", []), o.get("groups", [])
    if not isinstance(nodes, list) or not (NODES_MIN <= len(nodes) <= NODES_MAX):
        raise StackSchemaError(f"nodes 는 {NODES_MIN}~{NODES_MAX}개여야 한다(현재 {len(nodes) if isinstance(nodes, list) else '?'}개)")
    if not isinstance(edges, list) or len(edges) > EDGES_MAX:
        raise StackSchemaError(f"edges 는 {EDGES_MAX}개 이하여야 한다")
    if not isinstance(groups, list) or len(groups) > GROUPS_MAX:
        raise StackSchemaError(f"groups 는 {GROUPS_MAX}개 이하여야 한다")

    icons = icon_names()
    ids = set()
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not n["id"]:
            raise StackSchemaError("노드마다 문자열 id 가 필요하다")
        if n["id"] in ids:
            raise StackSchemaError(f"노드 id '{n['id']}' 중복")
        ids.add(n["id"])
        for k in ("row", "col"):
            v = n.get(k)
            if not isinstance(v, int) or isinstance(v, bool):
                raise StackSchemaError(f"노드 '{n['id']}': {k} 는 정수여야 한다")
        if n["row"] not in ROWS:
            raise StackSchemaError(f"노드 '{n['id']}': row 는 0~2 (현재 {n['row']})")
        if n["col"] not in COLS:
            raise StackSchemaError(f"노드 '{n['id']}': col 은 0~5 (현재 {n['col']})")
        if not isinstance(n.get("name"), str) or not n["name"]:
            raise StackSchemaError(f"노드 '{n['id']}': name 이 필요하다")
        if n.get("icon") is not None and n["icon"] not in icons:
            raise StackSchemaError(f"노드 '{n['id']}': 아이콘 '{n['icon']}' 이 사본에 없다")
        if n.get("tone") is not None and n["tone"] not in TONES:
            raise StackSchemaError(f"노드 '{n['id']}': tone '{n['tone']}' — 허용값 {sorted(TONES)}")
        if n.get("badge") is not None and not isinstance(n["badge"], (int, str)):
            raise StackSchemaError(f"노드 '{n['id']}': badge 는 숫자·문자여야 한다")
        for k in ("name", "role"):
            if n.get(k) is not None and "'" in str(n[k]):
                raise StackSchemaError(f"노드 '{n['id']}': {k} 안에 ' 는 쓸 수 없다(data-d 속성 규칙)")
    _cells(o)

    for e in edges:
        if not isinstance(e, dict):
            raise StackSchemaError("간선은 객체여야 한다")
        for k in ("from", "to"):
            if e.get(k) not in ids:
                raise StackSchemaError(f"간선 {k}='{e.get(k)}': 없는 노드 id")
        if e.get("kind") is not None and e["kind"] not in KINDS:
            raise StackSchemaError(f"간선 kind '{e['kind']}' — 허용값 {sorted(KINDS)}")
        if e.get("label") is not None and "'" in str(e["label"]):
            raise StackSchemaError("간선 label 안에 ' 는 쓸 수 없다(data-d 속성 규칙)")

    gids = set()
    for g in groups:
        if not isinstance(g, dict) or not isinstance(g.get("id"), str) or not g["id"]:
            raise StackSchemaError("그룹마다 문자열 id 가 필요하다")
        if g["id"] in gids:
            raise StackSchemaError(f"그룹 id '{g['id']}' 중복")
        gids.add(g["id"])
        if not isinstance(g.get("label"), str) or not g["label"]:
            raise StackSchemaError(f"그룹 '{g['id']}': label 이 필요하다")
        if g.get("tone") is not None and g["tone"] not in GTONES:
            raise StackSchemaError(f"그룹 '{g['id']}': tone '{g['tone']}' — 허용값 {sorted(GTONES)}")
        if g.get("icon") is not None and g["icon"] not in icons:
            raise StackSchemaError(f"그룹 '{g['id']}': 아이콘 '{g['icon']}' 이 사본에 없다")
        for nid in g.get("nodes", []):
            if nid not in ids:
                raise StackSchemaError(f"그룹 '{g['id']}': 멤버 '{nid}' 가 nodes 에 없다")
        cols = g.get("cols")
        if cols is not None:
            if not (isinstance(cols, list) and len(cols) == 2
                    and all(isinstance(c, int) and not isinstance(c, bool) for c in cols)
                    and cols[0] <= cols[1] and all(c in COLS for c in cols)):
                raise StackSchemaError(f"그룹 '{g['id']}': cols 는 [c0,c1] (0~5, c0≤c1) 여야 한다")
            for nid in g.get("nodes", []):
                nc = next(n["col"] for n in nodes if n["id"] == nid)
                if not (cols[0] <= nc <= cols[1]):
                    raise StackSchemaError(f"그룹 '{g['id']}': 멤버 '{nid}'(col{nc})가 선언 cols{cols} 밖 — 직사각 상자가 깨진다")
        if "'" in str(g["label"]):
            raise StackSchemaError(f"그룹 '{g['id']}': label 안에 ' 는 쓸 수 없다(data-d 속성 규칙)")
    for g in groups:
        p = g.get("parent")
        if p is not None:
            if p not in gids:
                raise StackSchemaError(f"그룹 '{g['id']}': parent '{p}' 없음")
            pp = next((x for x in groups if x["id"] == p), None)
            if pp and pp.get("parent") is not None:
                raise StackSchemaError(f"그룹 '{g['id']}': 중첩은 1단계까지")

    N, G, rect = _geometry(o)
    for g in G.values():
        x0, y0, x1, y1 = rect(g)
        member = set(g.get("nodes", []))
        for kid in g["kids"]:
            member |= set(G[kid].get("nodes", []))
        for nid, n in N.items():
            if nid in member:
                continue
            if x0 <= n["cx"] <= x1 and y0 <= n["top"] + BH / 2 <= y1:
                raise StackSchemaError(f"그룹 '{g['id']}' 상자가 멤버 아닌 노드 '{nid}' 를 덮는다 — cols/nodes 범위를 조정한다")

    warn = []
    for n in nodes:
        w = est_width(n["name"], NAME_W, 700)
        if w > NAME_MAX:
            warn.append(f"노드 '{n['id']}' 이름이 칸 폭을 넘어 …으로 줄어 그려짐(어림 {w:.0f}px > {NAME_MAX}px)")
        if n.get("role") and est_width(n["role"], ROLE_W, 500) > ROLE_MAX:
            warn.append(f"노드 '{n['id']}' 역할이 칸 폭을 넘어 …으로 줄어 그려짐")
    for e in edges:
        if e.get("label") and est_width(e["label"], EL_W, 600) > EL_MAX:
            warn.append(f"간선 label '{e['label']}' 이 넓어 …으로 줄어 그려짐")
    for g in groups:
        if est_width(g["label"], GL_W, 700) > 200:
            warn.append(f"그룹 '{g['id']}' 라벨이 길어 …으로 줄어 그려질 수 있음")
    return warn


def check_data_d(text):
    """data-d 속성 문자열 검사 — ' 들어가면 속성이 깨지므로 형태 오류."""
    if "'" in text:
        raise StackSchemaError("data-d 안에 작은따옴표(')가 있다 — 속성 구분이 깨진다")
    try:
        o = json.loads(text)
    except json.JSONDecodeError as e:
        raise StackSchemaError(f"data-d JSON 형태 오류: {e}") from e
    return check(o)


def main():
    ap = argparse.ArgumentParser(description="data-d JSON 파일 또는 조각 파일의 stack 도식을 검사한다")
    ap.add_argument("src", help=".json(data-d) 또는 .html(조각 — 안의 data-d 전부 검사)")
    a = ap.parse_args()
    text = Path(a.src).read_text(encoding="utf-8")
    if a.src.endswith(".json"):
        print(check_data_d(text) or "OK")
        return
    bad = 0
    for m in re.finditer(r"data-d='([^']*)'", text):
        try:
            for w in check_data_d(m.group(1)):
                print("WARN", w)
        except StackSchemaError as e:
            bad += 1
            print("ERROR", e)
    print("ERROR" if bad else "OK")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
