#!/usr/bin/env python3
"""cover-art-demo 예시 이미지 생성 — 순수 파이썬 PNG 인코더(외부 의존 0).

밤 다리(사진·일러스트 계열 분류용: 사선·곡선 위주)와 기계 도면(도형 계열 분류용:
축정렬 위주) 두 장을 img/*.png 로 만들고, base64 data: URI 를 src/*.html 의
__BRIDGE_PNG__·__MACHINE_PNG__ 표식에 박아 넣는다. 외부 주소를 쓰지 않으므로
캔버스 오염 WARN 에 걸리지 않는다.
재생성: python3 make_images.py
"""
import base64
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMG = ROOT / "img"
SRC = ROOT / "src"
W1, H1 = 1280, 720   # 밤 다리 — 표지 전면(16:9)
W2, H2 = 560, 400    # 기계 도면 — 패널(7:5)


# ---------- PNG 인코더(외부 의존 0) ----------
def png(w, h, flat_rgba):
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    stride = w * 4
    raw = bytearray()
    for y in range(h):
        raw += b"\x00" + flat_rgba[y * stride:(y + 1) * stride]
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 4)
        bg = tuple(bg[:3])
        for i in range(0, len(self.px), 4):
            self.px[i:i + 3] = bytes(bg)
            self.px[i + 3] = 255

    def blend(self, x, y, color, a=1.0):
        x, y = round(x), round(y)
        if x < 0 or y < 0 or x >= self.w or y >= self.h or a <= 0:
            return
        i = (y * self.w + x) * 4
        r, g, b = color[0], color[1], color[2]
        self.px[i] = round(self.px[i] * (1 - a) + r * a)
        self.px[i + 1] = round(self.px[i + 1] * (1 - a) + g * a)
        self.px[i + 2] = round(self.px[i + 2] * (1 - a) + b * a)
        self.px[i + 3] = 255

    def line(self, x0, y0, x1, y1, color, width=2.0, alpha=1.0):
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0) * 2))
        for s in range(steps + 1):
            t = s / steps
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            self.dot(x, y, color, width, alpha)

    def dot(self, x, y, color, width, alpha):
        r = width / 2
        for dy in range(-int(r) - 1, int(r) + 2):
            for dx in range(-int(r) - 1, int(r) + 2):
                d = math.hypot(dx, dy)
                if d <= r:
                    self.blend(x + dx, y + dy, color, alpha * (1.0 if d <= r - 1 else r - d + 0.0))

    def circle(self, cx, cy, rad, color, width=2.0, alpha=1.0):
        steps = max(24, int(rad * 6))
        for s in range(steps):
            a = s / steps * 2 * math.pi
            self.dot(cx + math.cos(a) * rad, cy + math.sin(a) * rad, color, width, alpha)

    def fill_circle(self, cx, cy, rad, color, alpha=1.0):
        for dy in range(-int(rad) - 1, int(rad) + 2):
            for dx in range(-int(rad) - 1, int(rad) + 2):
                d = math.hypot(dx, dy)
                if d <= rad:
                    self.blend(cx + dx, cy + dy, color, alpha * (1.0 if d <= rad - 1.5 else max(0.0, (rad - d) / 1.5)))

    def rect(self, x, y, w, h, color, alpha=1.0):
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                self.blend(xx, yy, color, alpha)

    def quad(self, p0, p1, p2, color, width=2.0, alpha=1.0, segments=64):
        for s in range(segments):
            t0, t1 = s / segments, (s + 1) / segments
            a = lambda t: (  # 2차 베지어
                (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            x0, y0 = a(t0)
            x1, y1 = a(t1)
            self.line(x0, y0, x1, y1, color, width, alpha)

    def out(self):
        return png(self.w, self.h, self.px)

# ---------- 1) 밤 다리(일러스트 계열) — 표지 전면 ----------
def bridge():
    NIGHT = (13, 27, 51)
    LIGHT = (226, 235, 248)
    MOON = (247, 244, 224)
    WATER = (94, 118, 156)
    c = Canvas(W1, H1, NIGHT)
    # 달(리빌 끝의 시선 앵커)
    c.fill_circle(1040, 130, 46, MOON, 0.95)
    c.circle(1040, 130, 46, LIGHT, 2.0, 0.6)
    # 가느다란 구름
    for (cx, cy, cw) in ((300, 170, 190), (760, 92, 150), (1130, 210, 120)):
        for i in range(int(cw)):
            t = i / cw
            c.dot(cx + i, cy + 6 * math.sin(t * math.pi), LIGHT, 2.0, 0.28)
    # 주탑 2기(벌어지는 다리 + 가로 보)
    for tx in (330, 890):
        c.line(tx - 30, 160, tx - 10, 540, LIGHT, 4)
        c.line(tx + 10, 160, tx + 30, 540, LIGHT, 4)
        for y in (200, 300, 400, 500):
            off = 30 - (y - 160) * (20 / 380)
            c.line(tx - off, y, tx + off, y, LIGHT, 2, 0.75)
    # 주 케이블(2차 베지어)을 샘플링해 행거를 내리고, 케이블도 같은 점들로 그린다
    for (y0, sag) in ((178, 300), (196, 316)):
        pts = []
        for s in range(97):
            t = s / 96
            x = (1 - t) ** 2 * 60 + 2 * (1 - t) * t * 610 + t * t * 1160
            y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * (y0 + sag) + t * t * y0
            pts.append((x, y))
        for i in range(96):
            c.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], LIGHT, 3.2, 0.95)
        for i in range(3, 94, 6):
            c.line(pts[i][0], pts[i][1], pts[i][0], 536, LIGHT, 1.6, 0.8)
    # 상판 + 난간 + 밑 X 브레이싱(사선 — 그림 계열 판정을 잡는 재료)
    c.rect(0, 536, W1, 10, LIGHT, 0.95)
    c.line(0, 522, W1, 522, LIGHT, 1.6, 0.65)
    for x in range(20, W1, 46):
        c.line(x, 522, x, 536, LIGHT, 1.4, 0.6)
    for x in range(10, W1 - 70, 84):
        c.line(x, 546, x + 70, 588, LIGHT, 1.6, 0.55)
        c.line(x + 70, 546, x, 588, LIGHT, 1.6, 0.55)
    c.line(0, 546, W1, 546, LIGHT, 2, 0.8)
    c.line(0, 588, W1, 588, LIGHT, 2, 0.8)
    # 물결 — 짧은 획의 반복
    for row, y in enumerate((614, 636, 660, 686)):
        phase = row * 37
        for x in range((row * 23) % 60, W1, 64):
            for i in range(30):
                c.dot(x + i, y + 3 * math.sin(i / 30 * math.pi), WATER, 1.8, 0.5)
    # 불빛 몇 점(주탑 꼭대기·상판)
    for (x, y) in ((300, 152), (920, 152), (470, 530), (700, 530), (930, 530)):
        c.fill_circle(x, y, 4, (255, 214, 120), 0.95)
    return c.out()


# ---------- 2) 기계 도면(도형 계열) — 패널 ----------
def machine():
    PAPER = (250, 250, 247)
    INK = (24, 26, 30)
    BLUE = (43, 95, 179)
    c = Canvas(W2, H2, PAPER)
    # 도면 테두리·표제란(축정렬)
    c.rect(16, 16, W2 - 32, H2 - 32, (0, 0, 0, 0))
    c.line(16, 16, W2 - 16, 16, INK, 2)
    c.line(16, H2 - 16, W2 - 16, H2 - 16, INK, 2)
    c.line(16, 16, 16, H2 - 16, INK, 2)
    c.line(W2 - 16, 16, W2 - 16, H2 - 16, INK, 2)
    c.line(W2 - 176, H2 - 16, W2 - 16, H2 - 16, INK, 3)
    c.line(W2 - 176, H2 - 16, W2 - 176, H2 - 60, INK, 1.5)
    c.line(W2 - 176, H2 - 60, W2 - 16, H2 - 60, INK, 1.5)
    # 큰 톱니바퀴(중심 원 + 이 + 보스)
    cx, cy, R = 200, 190, 108
    c.circle(cx, cy, R, INK, 2.5)
    c.circle(cx, cy, R - 14, BLUE, 1.8)
    c.circle(cx, cy, 26, INK, 2.5)
    for i in range(16):
        a = i / 16 * 2 * math.pi
        x0, y0 = cx + math.cos(a) * (R - 2), cy + math.sin(a) * (R - 2)
        x1, y1 = cx + math.cos(a) * (R + 16), cy + math.sin(a) * (R + 16)
        c.line(x0, y0, x1, y1, INK, 3.2)
        a2 = a + math.pi / 16
        c.line(cx + math.cos(a) * (R + 16), cy + math.sin(a) * (R + 16),
               cx + math.cos(a2) * (R + 16), cy + math.sin(a2) * (R + 16), INK, 3.2)
    # 작은 맞물림 톱니(우상단)
    cx2, cy2, R2 = 366, 118, 56
    c.circle(cx2, cy2, R2, INK, 2.2)
    c.circle(cx2, cy2, 15, INK, 2)
    for i in range(10):
        a = i / 10 * 2 * math.pi + 0.31
        x0, y0 = cx2 + math.cos(a) * (R2 - 2), cy2 + math.sin(a) * (R2 - 2)
        x1, y1 = cx2 + math.cos(a) * (R2 + 12), cy2 + math.sin(a) * (R2 + 12)
        c.line(x0, y0, x1, y1, INK, 2.8)
    # 축선(중심선 — 점선)
    for (x0, y0, x1, y1) in ((cx - 140, cy, cx + 150, cy), (cx, cy - 140, cx, cy + 140),
                             (cx2 - 80, cy2, cx2 + 80, cy2), (cx2, cy2 - 80, cx2, cy2 + 80)):
        n = int(math.hypot(x1 - x0, y1 - y0) / 16)
        for i in range(0, n, 2):
            t0, t1 = i / n, min(1.0, (i + 1) / n)
            c.line(x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0,
                   x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1, BLUE, 1.4, 0.9)
    # 받침 블록(하단 좌측, 축정렬 사각)
    c.rect(64, 300, 200, 44, (233, 233, 228))
    c.line(64, 300, 264, 300, INK, 2.5)
    c.line(64, 344, 264, 344, INK, 2.5)
    c.line(64, 300, 64, 344, INK, 2.5)
    c.line(264, 300, 264, 344, INK, 2.5)
    for x in (84, 104, 224, 244):
        c.circle(x, 322, 5, INK, 1.8)
    # 치수선(도면 문법)
    c.line(80, 372, 248, 372, INK, 1.4)
    c.line(80, 364, 80, 380, INK, 1.4)
    c.line(248, 364, 248, 380, INK, 1.4)
    return c.out()


def main():
    IMG.mkdir(exist_ok=True)
    b, m = bridge(), machine()
    (IMG / "bridge.png").write_bytes(b)
    (IMG / "machine.png").write_bytes(m)
    bu = "data:image/png;base64," + base64.b64encode(b).decode()
    mu = "data:image/png;base64," + base64.b64encode(m).decode()
    for f in SRC.glob("*.html"):
        t = f.read_text(encoding="utf-8")
        if "__BRIDGE_PNG__" in t or "__MACHINE_PNG__" in t:
            f.write_text(t.replace("__BRIDGE_PNG__", bu).replace("__MACHINE_PNG__", mu), encoding="utf-8")
    print(f"bridge.png {len(b)//1024}KB / machine.png {len(m)//1024}KB — src 표식 치환 완료")


if __name__ == "__main__":
    main()
