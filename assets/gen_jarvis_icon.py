#!/usr/bin/env python3
"""Gera o icone do JARVIS: orbe (anel violeta -> azul gelo) sobre fundo escuro.

Somente stdlib (struct + zlib), deterministico, sem dependencias.
Renderiza cada tamanho por distancia analitica (SDF) com anti-aliasing,
dither sutil contra banding e geometria levemente mais grossa em tamanhos
pequenos para legibilidade no Dock.

Uso:
    python3 gen_jarvis_icon.py [DIR_SAIDA]
Gera jarvis-icon-<N>.png (N em 16..1024) e jarvis-icon-180.png (apple-touch).
"""
import math
import os
import struct
import sys
import zlib

VIOLET = (0x8A, 0x6C, 0xFF)
ICE = (0x7F, 0xB6, 0xFF)
BG_A = (0x0B, 0x09, 0x12)
BG_B = (0x1A, 0x14, 0x30)
GLASS_A = (0x17, 0x12, 0x26)
GLASS_B = (0x0D, 0x0A, 0x18)
DOT_CORE = (0xC7, 0xD6, 0xFF)

SIZES = (16, 32, 64, 128, 180, 256, 512, 1024)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def mixc(c1, c2, t):
    return (
        c1[0] + (c2[0] - c1[0]) * t,
        c1[1] + (c2[1] - c1[1]) * t,
        c1[2] + (c2[2] - c1[2]) * t,
    )


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def sd_rounded_rect(px, py, half, r):
    qx = abs(px) - (half - r)
    qy = abs(py) - (half - r)
    ax, ay = max(qx, 0.0), max(qy, 0.0)
    return math.hypot(ax, ay) + min(max(qx, qy), 0.0) - r


def dither(x, y, ch):
    h = (x * 374761393 + y * 668265263 + ch * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h >> 16) & 0xFF) / 255.0 - 0.5


def render(size):
    S = size
    c = S / 2.0
    half = 0.8047 * S / 2.0          # corpo 824/1024 do template Apple
    radius = 0.1811 * S              # raio do canto 185.4/1024
    R_mid = 0.2175 * S
    ring_w = 0.075 * S
    dot_r = 0.042 * S
    small = S <= 64
    if small:
        ring_w *= 1.3
        dot_r *= 1.25
    R_o = R_mid + ring_w / 2.0
    R_i = R_mid - ring_w / 2.0
    glow_sigma = 0.085 * S
    glow_peak = 0.16 if small else 0.34
    ss = 2 if small else 1
    inv_body = 1.0 / (0.8047 * S)

    px = bytearray(4 * S * S)
    for y in range(S):
        row = y * 4 * S
        for x in range(S):
            r_acc = g_acc = b_acc = a_acc = 0.0
            cnt = 0
            for sy in range(ss):
                for sx in range(ss):
                    if ss == 1:
                        X = x + 0.5
                        Y = y + 0.5
                    else:
                        X = x + (sx + 0.5) / ss
                        Y = y + (sy + 0.5) / ss
                    dx = X - c
                    dy = Y - c
                    d = math.hypot(dx, dy)

                    cov = smoothstep(0.5, -0.5, sd_rounded_rect(dx, dy, half, radius))
                    if cov <= 0.0:
                        continue

                    t = clamp((dx + dy) * inv_body + 0.5, 0.0, 1.0)
                    col = mixc(BG_A, BG_B, t)

                    if d < R_i:  # vidro do orbe (profundidade)
                        icov = smoothstep(0.5, -0.5, d - R_i)
                        glass = mixc(GLASS_A, GLASS_B, clamp(d / R_i, 0.0, 1.0))
                        col = mixc(col, glass, icov)

                    g = math.exp(-((d - R_mid) ** 2) / (2.0 * glow_sigma ** 2))
                    ga = glow_peak * g
                    if ga > 0.004:
                        gcol = mixc(VIOLET, ICE, clamp(dy * inv_body + 0.5, 0.0, 1.0))
                        col = mixc(col, gcol, ga)

                    rcov = smoothstep(0.5, -0.5, abs(d - R_mid) - ring_w / 2.0)
                    if rcov > 0.0:
                        ring = mixc(VIOLET, ICE, clamp(dy * inv_body + 0.5, 0.0, 1.0))
                        col = mixc(col, ring, rcov)

                    dcov = smoothstep(0.5, -0.5, d - dot_r)
                    if dcov > 0.0:
                        core = mixc(DOT_CORE, ICE, clamp(d / dot_r, 0.0, 1.0))
                        col = mixc(col, core, dcov)

                    r_acc += col[0]
                    g_acc += col[1]
                    b_acc += col[2]
                    a_acc += cov * 255.0
                    cnt += 1

            if cnt == 0:
                continue
            n = float(cnt)
            i = row + x * 4
            px[i] = int(round(clamp(r_acc / n + dither(x, y, 0), 0, 255)))
            px[i + 1] = int(round(clamp(g_acc / n + dither(x, y, 1), 0, 255)))
            px[i + 2] = int(round(clamp(b_acc / n + dither(x, y, 2), 0, 255)))
            px[i + 3] = int(round(clamp(a_acc / n, 0, 255)))
    return px


def write_png(path, size, raw):
    stride = 4 * size
    scan = bytearray()
    for y in range(size):
        scan.append(0)
        scan += raw[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(scan), 9))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    for size in SIZES:
        raw = render(size)
        name = "jarvis-icon-180.png" if size == 180 else "jarvis-icon-%d.png" % size
        write_png(os.path.join(out, name), size, raw)
        print("ok %s (%dx%d)" % (name, size, size))


if __name__ == "__main__":
    main()
