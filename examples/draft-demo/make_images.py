#!/usr/bin/env python3
"""draft-demo 예시 이미지 생성 — 순수 파이썬 PNG 인코더(외부 의존 0).

톱니바퀴·회로 느낌의 흑백 도면 그림을 img/*.png 로 만들고, base64 data: URI 를
src/NN-*.html 조각의 img src 에 박아 넣어 세 장 조각까지 함께 재생성한다.
외부 주소를 쓰지 않으므로 data-fx="draft" 캔버스 오염 WARN 에 걸리지 않는다.
재생성: python3 make_images.py
"""
import base64
import math
import struct
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMG_DIR = HERE / 'img'
SRC_DIR = HERE / 'src'

INK = (40, 46, 56)
PAPER = (247, 245, 238)
HATCH = (128, 138, 144)


def grain(px, w, h, density=26):
    """결정적 종이 그레인 — 선형 합동 잡색 스티플(재생성해도 같은 점).
    단일 색은 팔레트가 작아 지나치게 잘 압축되므로 명도를 흔든다(용량·질감)."""
    s = 20260223
    for i in range(0, w * h * 3, 3):
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        if (s >> 20) < density:
            g = 120 + ((s >> 8) & 0x7F)          # 120~247 잡색 명도
            px[i:i + 3] = bytes((g, g - 4 if g > 8 else g, g - 8 if g > 16 else g))


def png_encode(w, h, px):
    def chunk(t, d):
        return (struct.pack('>I', len(d)) + t + d
                + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF))
    raw = b''.join(b'\x00' + bytes(px[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))


def gear(w=480, h=480):
    """방사형 톱니바퀴 — 이빨·보어·볼트 구멍·해칭·중심 표시(가장자리 풍부)."""
    px = bytearray(bytes(PAPER) * w * h)
    cx, cy = w / 2, h / 2
    teeth, r_tip, r_root, bore = 14, 198, 156, 46
    bolt_r, bolt_d = 100, 18

    def put(x, y, c):
        if 0 <= x < w and 0 <= y < h:
            i = (y * w + x) * 3
            px[i:i + 3] = bytes(c)

    for y in range(h):
        for x in range(w):
            dx, dy = x - cx, y - cy
            r = math.hypot(dx, dy)
            th = math.atan2(dy, dx)
            p = (th * teeth / (2 * math.pi)) % 1
            if p < .12 or p > .88:
                prof = r_root
            elif p < .30:
                prof = r_root + (r_tip - r_root) * ((p - .12) / .18)
            elif p < .70:
                prof = r_tip
            else:
                prof = r_root + (r_tip - r_root) * (1 - (p - .70) / .18)
            body = r <= prof
            if body:
                if r < bore:
                    c = PAPER
                else:
                    c = INK
                    for k in range(6):
                        bx = cx + bolt_r * math.cos(k * math.pi / 3)
                        by = cy + bolt_r * math.sin(k * math.pi / 3)
                        if (x - bx) ** 2 + (y - by) ** 2 < bolt_d ** 2:
                            c = PAPER
                            break
                    if c == INK and bore + 10 < r < r_root - 12 and (x + 2 * y) % 11 < 2:
                        c = HATCH            # 도면 해칭 — 본체에만
            else:
                c = PAPER
            put(x, y, c)
    # 중심 십자 + 외곽 기준원(점선 느낌) — 도면 주석
    for t in range(-26, 27):
        put(round(cx) + t, round(cy), HATCH)
        put(round(cx), round(cy) + t, HATCH)
    for a in range(0, 360, 4):
        for rr in range(214, 216):
            put(round(cx + rr * math.cos(math.radians(a))),
                round(cy + rr * math.sin(math.radians(a))), HATCH)
    grain(px, w, h, 160)
    return png_encode(w, h, px)


def circuit(w=480, h=360):
    """칩·배선·패드 회로도 — 직교 배선과 비아 링으로 도면 느낌."""
    px = bytearray(bytes(PAPER) * w * h)

    def put(x, y, c=INK):
        if 0 <= x < w and 0 <= y < h:
            i = (y * w + x) * 3
            px[i:i + 3] = bytes(c)

    def disc(cx, cy, r, c=INK, fill=True):
        for yy in range(-r, r + 1):
            for xx in range(-r, r + 1):
                d = xx * xx + yy * yy
                if (fill and d <= r * r) or (not fill and (r - 2) ** 2 <= d <= r * r):
                    put(round(cx) + xx, round(cy) + yy, c)

    def line(x0, y0, x1, y1, t=4, c=INK):
        n = int(math.hypot(x1 - x0, y1 - y0)) + 1
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            y = y0 + (y1 - y0) * i / n
            disc(x, y, t // 2, c)

    def rect(x0, y0, x1, y1, t=4, c=INK):
        for x in range(x0, x1 + 1):
            for s in range(t):
                put(x, y0 + s, c)
                put(x, y1 - s, c)
        for y in range(y0, y1 + 1):
            for s in range(t):
                put(x0 + s, y, c)
                put(x1 - s, y, c)

    # 중앙 칩 본체 + 핀 스텁
    rect(170, 70, 310, 290, 4)
    rect(196, 96, 284, 264, 2, HATCH)
    for y in range(86, 281, 24):              # 양쪽 핀
        line(162, y, 170, y, 4)
        line(310, y, 318, y, 4)
    for a in range(0, 360, 6):                # 칩 위치 맞춤 표시
        put(round(240 + 34 * math.cos(math.radians(a))),
            round(180 + 34 * math.sin(math.radians(a))), HATCH)
    # 배선: 핀 → 모서리 패드(직교 2절)
    routes = [
        (162, 86, [(60, 86), (60, 40), (36, 40)]),
        (162, 158, [(40, 158), (40, 180), (24, 180)]),
        (162, 254, [(80, 254), (80, 330), (48, 330)]),
        (318, 110, [(400, 110), (400, 44), (438, 44)]),
        (318, 206, [(420, 206), (420, 300), (444, 300)]),
        (318, 278, [(370, 278), (370, 336), (336, 336)]),
    ]
    for x0, y0, pts in routes:
        xs, ys = x0, y0
        for nx, ny in pts:
            line(xs, ys, nx, ny, 4)
            xs, ys = nx, ny
        disc(xs, ys, 9)                        # 패드
        disc(xs, ys, 4, PAPER)
    for vx, vy in ((60, 60), (400, 80), (90, 300), (430, 240), (120, 330)):
        disc(vx, vy, 7, INK, fill=False)       # 비아 링
    for x in range(330, 470, 14):              # 접지면 해칭
        line(x, 315, x + 30, 345, 2, HATCH)
    grain(px, w, h, 200)
    return png_encode(w, h, px)


def uri(data):
    return 'data:image/png;base64,' + base64.b64encode(data).decode()


def notes(t):
    return t + (' — 발표자 노트: 화면을 한 번 보여 주고, → 를 눌러 다음 장면으로 넘어간다. '
                '도면처럼 그려지는 등장이 끝나면 실물 이미지만 남는다는 점을 짚어 준다. '
                '정적 인쇄본에서는 처음부터 최종 모습만 보인다.')


def main():
    IMG_DIR.mkdir(exist_ok=True)
    SRC_DIR.mkdir(exist_ok=True)
    gear_png = gear()
    circuit_png = circuit()
    (IMG_DIR / 'gear.png').write_bytes(gear_png)
    (IMG_DIR / 'circuit.png').write_bytes(circuit_png)
    g, c = uri(gear_png), uri(circuit_png)

    cover = f'''<section class="slide cx" data-archetype="cover" data-variant="split" id="cover-split" style="padding:0">
<div aria-hidden="true" style="position:absolute;left:1300px;top:0;width:620px;height:1080px;background:var(--accent)"></div>
<div aria-hidden="true" style="position:absolute;left:1300px;top:0;width:10px;height:1080px;background:var(--accent-light)"></div>
<div class="cover-art" style="position:absolute;left:1400px;top:170px;width:420px;height:560px;border:2px dashed var(--paper);border-radius:var(--r3);display:flex;align-items:center;justify-content:center">
<img src="{g}" alt="톱니바퀴 흑백 도면" data-fx="draft" style="width:400px;display:block">
</div>
<div aria-hidden="true" style="position:absolute;left:1400px;top:800px;width:420px;height:14px;background:var(--accent-light);opacity:.7"></div>
<div class="cx-text" style="top:300px;width:1020px">
<p class="cx-eyebrow">모션 시연</p>
<h1 class="cx-title"><span data-text="도면 드로잉" id="cx-typed" data-fx="scatter-gather"></span><span class="cx-caret"></span></h1>
<div class="cx-tokens">
<span style="--d:0">흡수</span><span style="--d:1">·</span><span style="--d:2">기법</span><span style="--d:3">·</span><span style="--d:4">도면</span><span style="--d:5">·</span><span style="--d:6">시연</span>
</div>
<p class="cx-sub">이미지가 도면처럼 다시 그려지는 등장</p>
</div>
<p class="cover-date" style="z-index:3">draft 기법 데모</p>
<aside class="notes">{notes('표지 — 톱니바퀴 도면이 격자 위에 플롯되며 나타난 뒤 실물로 전환된다')}</aside>
</section>
'''
    mech = f'''<section class="slide" data-archetype="mechanism" style="gap:36px">
<div class="head"><p class="eyebrow">작동 원리</p><h2 class="title">개념 이미지도 같은 기법으로 등장한다</h2></div>
<div class="row" style="gap:48px;align-items:center;flex:1;min-height:0">
<figure style="margin:0;width:520px;flex:none">
<img src="{c}" alt="회로도 흑백 도면" data-fx="draft" style="width:100%;display:block">
</figure>
<div class="col f1" data-step="1" style="gap:18px">
<p class="label">효과의 세 단계</p>
<div class="cand top" data-lit="2"><span class="w">격자·중심</span><span class="b" style="width:340px"></span><span class="p">0.4초</span></div>
<div class="cand"><span class="w">윤곽 플롯</span><span class="b" style="width:260px"></span><span class="p">1.4초</span></div>
<div class="cand"><span class="w">실물 공개</span><span class="b" style="width:150px"></span><span class="p">0.7초</span></div>
</div>
</div>
<div class="callout" data-step="4" style="font-size:30px"><b>핵심</b> 격자 → 가장자리 플롯 → 치수 수치 → 실물 크로스페이드, 모두 2400ms 안.</div>
<aside class="notes">{notes('회로도 개념 이미지에 draft 가 붙은 장 — 본문 도해에서도 같은 등장을 쓸 수 있다')}</aside>
</section>
'''
    plain = f'''<section class="slide" data-archetype="statement">
<div class="head"><p class="eyebrow">대조</p><h2 class="title">같은 이미지, 효과 없음 — 움직이지 않는 장</h2></div>
<div class="row" style="gap:48px;align-items:center;flex:1;min-height:0">
<figure style="margin:0;width:520px;flex:none">
<img src="{g}" alt="톱니바퀴 흑백 도면 — 정적" style="width:100%;display:block;filter:grayscale(1) opacity(.75)">
</figure>
<div class="col f1" style="gap:18px">
<p class="small" style="font-size:26px">효과가 없는 이미지는 처음부터 조용히 앉아 있습니다. 표지·개념 장의 등장 효과와 대비해 보세요.</p>
<p class="small" style="font-size:24px;color:var(--soft)">실물 화면 인용(screen-cite) 같은 증거 이미지는 이처럼 항상 움직이지 않는 것이 원칙입니다.</p>
</div>
</div>
<aside class="notes">{notes('회색 정적 이미지 — draft 없는 장과의 대조용')}</aside>
</section>
'''
    (SRC_DIR / '01-cover.html').write_text(cover, encoding='utf-8')
    (SRC_DIR / '02-mechanism.html').write_text(mech, encoding='utf-8')
    (SRC_DIR / '03-plain.html').write_text(plain, encoding='utf-8')
    print(f'gear.png {len(gear_png)//1024}KB / circuit.png {len(circuit_png)//1024}KB — src 3장 재생성')


if __name__ == '__main__':
    main()
