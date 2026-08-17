#!/usr/bin/env python3
"""Visual chrome for JARVIS-THEO: official purple mark + Grok-like dark shell."""
from __future__ import annotations

import base64
import os
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(os.environ.get("JARVIS_HOME") or Path(__file__).resolve().parents[1])
LOGO = ROOT / "web" / "jarvis-mark.png"

INK = (19, 8, 36)
TEXT = (247, 241, 255)
MUTED = (217, 199, 235)
FAINT = (170, 145, 194)
VIOLET = (168, 85, 247)
LAVENDER = (192, 132, 252)
HOT = (234, 220, 255)
LINE = (88, 42, 140)

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("JARVIS_THEO_PLAIN") == "1":
        return False
    return bool(sys.stdout.isatty())


def rgb(fg: tuple[int, int, int] | None = None, bg: tuple[int, int, int] | None = None) -> str:
    if not color_enabled():
        return ""
    parts = []
    if fg:
        parts.append(f"\033[38;2;{fg[0]};{fg[1]};{fg[2]}m")
    if bg:
        parts.append(f"\033[48;2;{bg[0]};{bg[1]};{bg[2]}m")
    return "".join(parts)


def paint(text: str, fg: tuple[int, int, int] | None = None, *, bold: bool = False) -> str:
    if not color_enabled():
        return text
    prefix = (BOLD if bold else "") + rgb(fg)
    return f"{prefix}{text}{RESET}"


def _osc(payload: str) -> None:
    sys.stdout.write(f"\033]{payload}\007")
    sys.stdout.flush()


def apply_room() -> None:
    """Paint the terminal like the JARVIS cockpit: deep purple, light ink."""
    if not color_enabled():
        return
    _osc(f"11;#{INK[0]:02x}{INK[1]:02x}{INK[2]:02x}")
    _osc(f"10;#{TEXT[0]:02x}{TEXT[1]:02x}{TEXT[2]:02x}")
    _osc(f"12;#{VIOLET[0]:02x}{VIOLET[1]:02x}{VIOLET[2]:02x}")


def restore_room() -> None:
    if not color_enabled():
        return
    _osc("111")
    _osc("110")
    _osc("112")


def _term_program() -> str:
    return (os.environ.get("TERM_PROGRAM") or os.environ.get("TERM") or "").lower()


def _try_inline_logo() -> bool:
    if not color_enabled() or not LOGO.is_file():
        return False
    raw = LOGO.read_bytes()
    if len(raw) < 80:
        return False
    encoded = base64.b64encode(raw).decode("ascii")
    program = _term_program()
    try:
        if "iterm" in program:
            sys.stdout.write(
                f"\033]1337;File=inline=1;width=36;height=12;preserveAspectRatio=1:{encoded}\007\n"
            )
            sys.stdout.flush()
            return True
        if shutil.which("kitty") and "kitty" in program:
            result = subprocess.run(
                ["kitty", "+kitten", "icat", "--align", "left", "--place", "36x12@0x0", str(LOGO)],
                check=False,
            )
            return result.returncode == 0
    except OSError:
        return False
    return False


def _paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    return min(
        ((abs(estimate - left), left), (abs(estimate - up), up), (abs(estimate - up_left), up_left))
    )[1]


def decode_png_rgba(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a png")
    offset = 8
    width = height = 0
    color_type = bit_depth = 0
    idat = bytearray()
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        chunk = data[offset + 8:offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, *_ = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            idat.extend(chunk)
        elif kind == b"IEND":
            break
    if bit_depth != 8 or color_type not in {2, 6} or width < 1 or height < 1:
        raise ValueError("unsupported png")
    raw = zlib.decompress(bytes(idat))
    bpp = 4 if color_type == 6 else 3
    stride = width * bpp
    rows: list[bytearray] = []
    cursor = 0
    prev = bytearray(stride)
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        row = bytearray(raw[cursor:cursor + stride])
        cursor += stride
        if filter_type == 1:
            for index in range(stride):
                left = row[index - bpp] if index >= bpp else 0
                row[index] = (row[index] + left) & 255
        elif filter_type == 2:
            for index in range(stride):
                row[index] = (row[index] + prev[index]) & 255
        elif filter_type == 3:
            for index in range(stride):
                left = row[index - bpp] if index >= bpp else 0
                row[index] = (row[index] + ((left + prev[index]) // 2)) & 255
        elif filter_type == 4:
            for index in range(stride):
                left = row[index - bpp] if index >= bpp else 0
                up_left = prev[index - bpp] if index >= bpp else 0
                row[index] = (row[index] + _paeth(left, prev[index], up_left)) & 255
        elif filter_type != 0:
            raise ValueError("bad png filter")
        if bpp == 3:
            rgba = bytearray()
            for index in range(0, stride, 3):
                rgba.extend(row[index:index + 3])
                rgba.append(255)
            row = rgba
        rows.append(row)
        prev = row
    return width, height, b"".join(rows)


def _sample(pixels: bytes, width: int, height: int, x: int, y: int, tw: int, th: int) -> tuple[int, int, int] | None:
    x0 = int(x * width / tw)
    x1 = max(x0 + 1, int((x + 1) * width / tw))
    y0 = int(y * height / th)
    y1 = max(y0 + 1, int((y + 1) * height / th))
    total = count = 0
    red = green = blue = 0
    for sy in range(y0, min(height, y1)):
        for sx in range(x0, min(width, x1)):
            offset = (sy * width + sx) * 4
            pr, pg, pb, pa = pixels[offset:offset + 4]
            if pa < 24:
                continue
            red += (pr * pa + INK[0] * (255 - pa)) // 255
            green += (pg * pa + INK[1] * (255 - pa)) // 255
            blue += (pb * pa + INK[2] * (255 - pa)) // 255
            count += 1
            total += 1
    if count == 0:
        return None
    return red // count, green // count, blue // count


_LOGO_CACHE: dict[tuple[int, bool], list[str]] = {}


def render_logo(columns: int = 22) -> list[str]:
    """Render the official web/jarvis-logo.png with real pixels (half-blocks)."""
    cache_key = (columns, color_enabled())
    cached = _LOGO_CACHE.get(cache_key)
    if cached is not None:
        return cached
    width, height, pixels = decode_png_rgba(LOGO)
    target_w = max(16, min(columns, 42))
    target_h = max(8, int(height * target_w / width))
    if target_h % 2:
        target_h += 1
    lines = []
    colored = color_enabled()
    for row in range(0, target_h, 2):
        cells = []
        for col in range(target_w):
            top = _sample(pixels, width, height, col, row, target_w, target_h)
            bottom = _sample(pixels, width, height, col, row + 1, target_w, target_h)
            if colored:
                if top is None and bottom is None:
                    cells.append(" ")
                elif bottom is None:
                    cells.append(f"\033[38;2;{top[0]};{top[1]};{top[2]}m▀{RESET}")
                elif top is None:
                    cells.append(f"\033[38;2;{bottom[0]};{bottom[1]};{bottom[2]}m▄{RESET}")
                else:
                    cells.append(
                        f"\033[38;2;{top[0]};{top[1]};{top[2]}m"
                        f"\033[48;2;{bottom[0]};{bottom[1]};{bottom[2]}m▀{RESET}"
                    )
            else:
                pixel = top or bottom
                if pixel is None:
                    cells.append(" ")
                else:
                    cells.append("█" if sum(pixel) > 140 else "░")
        lines.append("".join(cells).rstrip())
    rendered = [line for line in lines if line.strip()]
    _LOGO_CACHE[cache_key] = rendered
    return rendered


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def pixel_mark(glow: float = 0.72) -> list[str]:
    """J with top bar and hook, inside a double ring. Glow 0..1."""
    # , dust  . ring  * halo  o J body  @ J highlight
    grid = [
        "            , . . . . ,            ",
        "        . * * *   * * * .        ",
        "      . * ,   @ @ @ @   , * .      ",
        "    . *         o o o       * .    ",
        "   . *           o o         * .   ",
        "  . *            o o          * .  ",
        " . *             o o           * . ",
        ". *              o o            * .",
        ". *              o o            * .",
        " . *        @    o o           * . ",
        "  . *      @ o  o o           * .  ",
        "   . *      @ @ o o          * .   ",
        "    . *       @ o o         * .    ",
        "      . * ,     @ @     , * .      ",
        "        . * * *   * * * .        ",
        "            , . . . . ,            ",
    ]
    dust = _mix((70, 48, 110), FAINT, glow)
    ring = _mix((88, 50, 140), LAVENDER, glow)
    halo = _mix(LAVENDER, HOT, glow * 0.7)
    body = _mix(VIOLET, LAVENDER, glow * 0.55)
    hi = _mix(LAVENDER, (255, 248, 255), glow)
    ink = {
        ",": ("·", dust),
        ".": ("•", ring),
        "*": ("•", halo),
        "o": ("●", body),
        "@": ("●", hi),
    }
    out = []
    for raw in grid:
        cells = []
        for ch in raw:
            if ch in ink:
                glyph, tone = ink[ch]
                cells.append(paint(glyph, tone, bold=(ch in {"o", "@"} and glow > 0.8)))
            else:
                cells.append(" ")
        out.append("".join(cells).rstrip())
    return out


def banner(ready: bool, slots: int = 0, glow: float = 0.78) -> str:
    lines = []
    lines.extend(pixel_mark(glow))
    lines.append("")
    title = paint("J · A · R · V · I · S", _mix(LAVENDER, HOT, glow), bold=True)
    byline = paint("POR THEO LORENTZ PADILHA", _mix(FAINT, LAVENDER, glow))
    product = paint("JARVIS-THEO", TEXT, bold=True)
    rule = paint("─" * 42, LINE)
    status = "OpenRouter ligado" if ready else "OpenRouter sem chave"
    status_fg = LAVENDER if ready else (251, 113, 133)
    lines.append(title)
    lines.append(byline)
    lines.append(rule)
    lines.append(product)
    lines.append(paint("OpenRouter rápido · sem editar disco · /sair", FAINT))
    extra = f"{status}"
    if slots:
        extra += f" · {slots} rota(s)"
    lines.append(paint(extra, status_fg))
    lines.append(rule)
    return "\n".join(lines)


def play_intro(ready: bool, slots: int = 0) -> None:
    """Short Grok-like pulse, then leave the mark at rest."""
    if not color_enabled():
        print(banner(ready, slots))
        return
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    last_h = 0
    try:
        frames = (0.18, 0.38, 0.62, 0.88, 1.0, 0.7, 0.84, 1.0)
        for index, glow in enumerate(frames):
            text = banner(ready, slots, glow=glow)
            if index:
                sys.stdout.write(f"\033[{last_h}F\033[J")
            sys.stdout.write(text + "\n")
            sys.stdout.flush()
            last_h = text.count("\n") + 1
            time.sleep(0.065)
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


def user_prompt() -> str:
    diamond = paint("◆", VIOLET)
    name = paint("Theo", HOT, bold=True)
    arrow = paint("❯", LAVENDER)
    return f"{diamond} {name} {arrow} "


def jarvis_prefix() -> str:
    return paint("JARVIS", VIOLET, bold=True) + paint(" ▸ ", LAVENDER)


def muted(text: str) -> str:
    return paint(text, FAINT)


def status_line(text: str) -> str:
    return paint(text, MUTED)


def route_line(text: str) -> str:
    return paint("↻ ", LAVENDER) + paint(text, FAINT)
