"""App icons, brand tiles and small interface glyphs.

Every icon is drawn on a 100x100 grid inside a <symbol>, so a scene can place it
at any size with <use>. Brand glyphs come from Simple Icons (CC0).
"""

from __future__ import annotations

import re
import subprocess

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

from svgkit import CACHE, Doc, num, superellipse

SQUIRCLE = superellipse(100)
SIMPLE_ICONS = "https://cdn.jsdelivr.net/npm/simple-icons@{version}/icons/{name}.svg"
SIMPLE_ICONS_VERSION = "16.32.0"
# Later Simple Icons releases dropped these, so they come from the last release that had them.
SIMPLE_ICONS_PINS = {"linkedin": "13.21.0", "openai": "15.22.0", "visualstudiocode": "12.4.0"}


def _brand_svg(name: str) -> str:
    path = CACHE / "icons" / f"{name}.svg"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        version = SIMPLE_ICONS_PINS.get(name, SIMPLE_ICONS_VERSION)
        url = SIMPLE_ICONS.format(version=version, name=name)
        subprocess.run(["curl", "-fsSL", "-o", str(path), url], check=True)
    return path.read_text()


def base(doc: Doc) -> None:
    doc.define(
        "icon-base",
        f'<path id="sq" d="{SQUIRCLE}"/>'
        '<clipPath id="sqc"><use href="#sq"/></clipPath>'
        '<linearGradient id="rim" x1="0" y1="0" x2="0" y2="100" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".6"/>'
        '<stop offset=".3" stop-color="#fff" stop-opacity=".1"/>'
        '<stop offset=".75" stop-color="#fff" stop-opacity=".04"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity=".22"/></linearGradient>'
        '<radialGradient id="sheen" cx="32" cy="-6" r="78" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".26"/>'
        '<stop offset=".6" stop-color="#fff" stop-opacity=".05"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>',
    )


def _linear(gid: str, stops: list[str], x1=50, y1=0, x2=50, y2=100) -> str:
    step = 1 / (len(stops) - 1)
    body = "".join(f'<stop offset="{num(i * step)}" stop-color="{c}"/>' for i, c in enumerate(stops))
    return (
        f'<linearGradient id="{gid}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'gradientUnits="userSpaceOnUse">{body}</linearGradient>'
    )


def _radial(gid: str, color: str, cx: float, cy: float, r: float, opacity: float) -> str:
    return (
        f'<radialGradient id="{gid}" cx="{cx}" cy="{cy}" r="{r}" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="{opacity}"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>'
    )


def _symbol(name: str, gradients: str, background: str, glyph: str) -> str:
    return (
        gradients
        + f'<symbol id="ic-{name}" viewBox="0 0 100 100">'
        + f'<use href="#sq" fill="{background}"/>'
        + f'<g clip-path="url(#sqc)">{glyph}<rect width="100" height="100" fill="url(#sheen)"/></g>'
        + '<use href="#sq" stroke="url(#rim)" stroke-width="2.2" clip-path="url(#sqc)"/>'
        + "</symbol>"
    )


S_PATH = "M73.6 25H34.4a12.7 12.7 0 0 0 0 25.4h30.7a12.7 12.7 0 0 1 0 25.4H26.4"


def _switchboard() -> str:
    glyph = (
        f'<path d="{S_PATH}" stroke="#04110f" stroke-opacity=".45" stroke-width="11" stroke-linecap="round" '
        'transform="translate(0 1.8)"/>'
        '<g fill="#04110f" fill-opacity=".45" transform="translate(0 1.8)">'
        '<circle cx="73.6" cy="25" r="7.4"/><circle cx="26.4" cy="75.8" r="7.4"/></g>'
        f'<path d="{S_PATH}" stroke="url(#sb-s)" stroke-width="11" stroke-linecap="round"/>'
        '<g fill="url(#sb-s)"><circle cx="73.6" cy="25" r="7.4"/><circle cx="26.4" cy="75.8" r="7.4"/></g>'
        f'<path d="{S_PATH}" stroke="#fff" stroke-opacity=".28" stroke-width="2.4" stroke-linecap="round" '
        'transform="translate(0 -2.6)"/>'
    )
    gradients = _linear("sb-bg", ["#474A52", "#2B2D32", "#1B1C20"]) + _linear(
        "sb-s", ["#93FBEA", "#5EE6D0", "#2FBBA6"], 50, 18, 50, 84
    )
    return _symbol("switchboard", gradients, "url(#sb-bg)", glyph)


def _kerbside() -> str:
    glyph = (
        '<rect x="15" y="15" width="70" height="70" rx="9.5" fill="#F4F3EF"/>'
        '<rect x="20.3" y="20.3" width="59.4" height="59.4" rx="6.2" stroke="#057A40" stroke-width="2.6"/>'
        '<path fill="#057A40" fill-rule="evenodd" d="M38.3 30.4H52.2C58.9 30.4 63 35.1 63 42.55C63 50 58.9 54.7 '
        "52.2 54.7H44.7V69.5H38.3ZM44.7 36.9V48.2H51.6C54.6 48.2 56.4 46 56.4 42.55C56.4 39.1 54.6 36.9 51.6 "
        '36.9Z"/>'
    )
    return _symbol("kerbside", _linear("kb-bg", ["#24272D", "#15171A", "#0D0E10"]), "url(#kb-bg)", glyph)


SPARKLE = "M50 37C51.4 51.5 55 56.3 71 60C55 63.7 51.4 68.5 50 83C48.6 68.5 45 63.7 29 60C45 56.3 48.6 51.5 50 37Z"


def _nomi() -> str:
    glyph = (
        '<rect width="100" height="100" fill="url(#nm-glow)"/>'
        '<path d="M28 0H72V5.5C72 10 69.5 12.5 65 12.5H35C30.5 12.5 28 10 28 5.5Z" fill="#050408"/>'
        '<circle cx="57" cy="6.2" r="1.6" fill="#1d2440"/>'
        f'<path d="{SPARKLE}" fill="url(#nm-star)"/>'
        '<path d="M70 26C70.5 30 71.6 31.3 75.5 32C71.6 32.7 70.5 34 70 38C69.5 34 68.4 32.7 64.5 32C68.4 31.3 '
        '69.5 30 70 26Z" fill="#fff" fill-opacity=".85"/>'
    )
    gradients = (
        _linear("nm-bg", ["#120D2B", "#261A5E", "#4631AE"])
        + _radial("nm-glow", "#A48BFF", 50, 66, 46, 0.8)
        + _linear("nm-star", ["#FFFFFF", "#E4DBFF"], 50, 37, 50, 83)
    )
    return _symbol("nomi", gradients, "url(#nm-bg)", glyph)


def _locsim() -> str:
    glyph = (
        '<g stroke="#fff" stroke-opacity=".16" stroke-width="3.2" stroke-linecap="round">'
        '<path d="M-4 72C18 62 34 80 58 66S92 54 106 60"/><path d="M20 -4C28 24 14 46 34 104"/></g>'
        '<circle cx="50" cy="52" r="29" stroke="#fff" stroke-opacity=".26" stroke-width="1.6"/>'
        '<circle cx="50" cy="52" r="41" stroke="#fff" stroke-opacity=".13" stroke-width="1.4"/>'
        '<path d="M71.5 29.5L30 47.2L49.2 51.3L53.2 70.5Z" fill="#fff"/>'
        '<path d="M71.5 29.5L49.2 51.3L53.2 70.5Z" fill="#D6E4FF"/>'
    )
    return _symbol("locsim", _linear("ls-bg", ["#4796FF", "#2A6EF5", "#1749D6"]), "url(#ls-bg)", glyph)


def _codegraph() -> str:
    glyph = (
        '<rect width="100" height="100" fill="url(#cg-glow)"/>'
        '<g stroke="#99F6E4" stroke-linecap="round">'
        '<path d="M27 30Q50 16 74 28M26 73Q50 88 75 74" stroke-opacity=".32" stroke-width="2.2"/>'
        '<path d="M50 52L27 30M50 52L74 28M50 52L26 73M50 52L75 74" stroke-opacity=".7" stroke-width="2.6"/></g>'
        '<g fill="#CCFBF1"><circle cx="27" cy="30" r="6.4"/><circle cx="74" cy="28" r="6.4"/>'
        '<circle cx="26" cy="73" r="6.4"/><circle cx="75" cy="74" r="6.4"/></g>'
        '<circle cx="50" cy="52" r="11" fill="#2DD4BF"/><circle cx="50" cy="52" r="11" stroke="#CCFBF1" '
        'stroke-opacity=".7" stroke-width="1.6"/><circle cx="50" cy="52" r="4.2" fill="#F0FDFA"/>'
    )
    gradients = _linear("cg-bg", ["#114247", "#0B2B31", "#071C22"]) + _radial("cg-glow", "#2DD4BF", 50, 52, 42, 0.38)
    return _symbol("codegraph", gradients, "url(#cg-bg)", glyph)


def _crossbar() -> str:
    glyph = (
        '<path d="M48 44h22a12 12 0 0 1 12 12v8a12 12 0 0 1-12 12h-2l7 9-14-9H48a12 12 0 0 1-12-12v-8a12 12 0 0 '
        '1 12-12Z" fill="#fff" fill-opacity=".55"/>'
        '<path d="M30 22h24a12 12 0 0 1 12 12v10a12 12 0 0 1-12 12H36l-13 9 5-9.6A12 12 0 0 1 18 44V34a12 12 0 0 '
        '1 12-12Z" fill="#fff"/>'
        '<g fill="#F2555A"><circle cx="32" cy="39.5" r="3"/><circle cx="42" cy="39.5" r="3"/>'
        '<circle cx="52" cy="39.5" r="3"/></g>'
    )
    return _symbol(
        "crossbar", _linear("cb-bg", ["#FF9E5E", "#F4575C", "#D03B82"], 0, 0, 100, 100), "url(#cb-bg)", glyph
    )


def _hookrelay() -> str:
    glyph = (
        '<circle cx="32" cy="23" r="6.2" stroke="#fff" stroke-width="4.6"/>'
        '<path d="M32 33V52a18 18 0 0 0 36 0V36" stroke="#fff" stroke-width="9" stroke-linecap="round"/>'
        '<path d="M58.5 41L68 29L77.5 41" stroke="#fff" stroke-width="9" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
    )
    return _symbol("hookrelay", _linear("hr-bg", ["#FFC24F", "#F99A2C", "#F0661E"]), "url(#hr-bg)", glyph)


def _contractguard() -> str:
    glyph = (
        '<path d="M50 18L75 27.5V47C75 63 65 74.5 50 81C35 74.5 25 63 25 47V27.5Z" fill="#fff"/>'
        '<path d="M38.5 49.5L46.5 57.5L62 41.5" stroke="#0E9F6E" stroke-width="6.5" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
    )
    return _symbol("contractguard", _linear("cgd-bg", ["#43DE92", "#12A873", "#0A7C57"]), "url(#cgd-bg)", glyph)


def _skills() -> str:
    glyph = (
        '<path d="M50 23L79 37.5L50 52L21 37.5Z" fill="#fff"/>'
        '<path d="M22 51L50 65L78 51" stroke="#fff" stroke-opacity=".85" stroke-width="6" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
        '<path d="M22 63.5L50 77.5L78 63.5" stroke="#fff" stroke-opacity=".6" stroke-width="6" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )
    return _symbol(
        "skills", _linear("sk-bg", ["#F472B6", "#C026D3", "#7C3AED"], 0, 0, 100, 100), "url(#sk-bg)", glyph
    )


PROJECT_ICONS = {
    "switchboard": _switchboard,
    "nomi": _nomi,
    "kerbside": _kerbside,
    "locsim": _locsim,
    "codegraph": _codegraph,
    "crossbar": _crossbar,
    "skills": _skills,
    "hookrelay": _hookrelay,
    "contractguard": _contractguard,
}


def icon(doc: Doc, name: str, x: float, y: float, size: float, attrs: str = "") -> str:
    base(doc)
    doc.define(f"ic-{name}", PROJECT_ICONS[name]())
    extra = f" {attrs}" if attrs else ""
    return f'<use href="#ic-{name}" x="{num(x)}" y="{num(y)}" width="{num(size)}" height="{num(size)}"{extra}/>'


# Brand tiles ---------------------------------------------------------------

BRANDS = {
    # slug: (label, gradient stops, glyph colour)
    "swift": ("Swift", ["#FF9A3D", "#F7632E", "#E8322A"], "#fff"),
    "swiftui": ("SwiftUI", ["#3AA0FF", "#2466F2", "#1B3FC9"], "#fff"),
    "go": ("Go", ["#2FD0F0", "#00ADD8", "#007FA8"], "#fff"),
    "typescript": ("TypeScript", ["#4A93E0", "#3178C6", "#235A97"], "#fff"),
    "python": ("Python", ["#4B8BBE", "#3776AB", "#2B5B84"], "#FFE873"),
    "javascript": ("JavaScript", ["#FFE94D", "#F7DF1E", "#E8C900"], "#1D1D1F"),
    "gnubash": ("Bash", ["#3A3B40", "#232427", "#131416"], "#9BE56B"),
    "mlx": ("MLX", ["#2B2B30", "#141417", "#050506"], "#fff"),
    "postgresql": ("PostgreSQL", ["#5B8DEF", "#336791", "#24476A"], "#fff"),
    "apachekafka": ("Kafka", ["#FFFFFF", "#F1F1F4", "#DCDCE2"], "#231F20"),
    "redis": ("Redis", ["#FF6A5B", "#FF4438", "#D22A1F"], "#fff"),
    "mongodb": ("MongoDB", ["#0E4A38", "#07301F", "#021A10"], "#00ED64"),
    "graphql": ("GraphQL", ["#F53DB5", "#E10098", "#A8007A"], "#fff"),
    "docker": ("Docker", ["#3FA9F5", "#2496ED", "#1D63ED"], "#fff"),
    "fastapi": ("FastAPI", ["#14B8A6", "#009688", "#00695F"], "#fff"),
    "nodedotjs": ("Node.js", ["#7CC85A", "#5FA04E", "#3F7A33"], "#fff"),
    "react": ("React", ["#2C3038", "#20232A", "#121418"], "#61DAFB"),
    "nextdotjs": ("Next.js", ["#2A2A2A", "#111111", "#000000"], "#fff"),
    "visualstudiocode": ("VS Code", ["#2BA5F0", "#007ACC", "#005A9E"], "#fff"),
    "modelcontextprotocol": ("MCP", ["#F7F7F9", "#E9E9EE", "#D6D6DE"], "#111"),
    "claude": ("Claude", ["#EB9A77", "#D97757", "#B85A3B"], "#fff"),
    "openai": ("OpenAI", ["#3A3A3F", "#1C1C1F", "#0A0A0B"], "#fff"),
    "webassembly": ("WebAssembly", ["#8573FF", "#654FF0", "#4A34D2"], "#fff"),
    "githubactions": ("Actions", ["#4DA3FF", "#2088FF", "#1464D9"], "#fff"),
}


GLYPH_SOURCE = {"swiftui": "swift"}
# Logos drawn as a filled square with the mark cut out; keep only the mark.
DROP_OUTER = {"swift", "swiftui", "typescript", "javascript", "webassembly", "linkedin"}
GLYPH_FIT = {"go": 60, "typescript": 44, "javascript": 44, "webassembly": 46, "gnubash": 48, "nextdotjs": 50}


def brand_path(slug: str) -> str:
    raw = _brand_svg(GLYPH_SOURCE.get(slug, slug))
    d = re.search(r'<path d="([^"]+)"', raw).group(1)

    recording = RecordingPen()
    parse_path(d, recording)
    contours, current = [], []
    for op, args in recording.value:
        if op == "moveTo" and current:
            contours.append(current)
            current = []
        current.append((op, args))
    if current:
        contours.append(current)

    def bounds(contour):
        pen = BoundsPen(None)
        for op, args in contour:
            getattr(pen, op)(*args)
        return pen.bounds

    if slug in DROP_OUTER and len(contours) > 1:
        areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in map(bounds, contours)]
        contours.pop(areas.index(max(areas)))

    box = BoundsPen(None)
    for contour in contours:
        for op, args in contour:
            getattr(box, op)(*args)
    x0, y0, x1, y1 = box.bounds
    fit = GLYPH_FIT.get(slug, 52)
    scale = fit / max(x1 - x0, y1 - y0)
    dx = 50 - (x0 + x1) / 2 * scale
    dy = 50 - (y0 + y1) / 2 * scale

    out = SVGPathPen(None, ntos=lambda v: num(v))
    transformed = TransformPen(out, (scale, 0, 0, scale, dx, dy))
    for contour in contours:
        for op, args in contour:
            getattr(transformed, op)(*args)
    return out.getCommands()


def brand(doc: Doc, slug: str, x: float, y: float, size: float, mono_face=None) -> str:
    base(doc)
    label, stops, glyph_color = BRANDS[slug]
    if slug == "mlx":
        doc.uses(mono_face, "MLX")
        glyph = (
            f'<text x="50" y="59.5" text-anchor="middle" font-family="{mono_face.css}" font-size="27" '
            f'letter-spacing="-.5" fill="{glyph_color}">MLX</text>'
        )
    else:
        glyph = f'<path d="{brand_path(slug)}" fill="{glyph_color}"/>'
    doc.define(
        f"bt-{slug}",
        _linear(f"bt-{slug}-bg", stops, 0, 0, 100, 100)
        + f'<symbol id="bt-{slug}" viewBox="0 0 100 100">'
        + f'<use href="#sq" fill="url(#bt-{slug}-bg)"/>'
        + f'<g clip-path="url(#sqc)">{glyph}<rect width="100" height="100" fill="url(#sheen)"/></g>'
        + '<use href="#sq" stroke="url(#rim)" stroke-width="2.2" clip-path="url(#sqc)"/>'
        + "</symbol>",
    )
    return f'<use href="#bt-{slug}" x="{num(x)}" y="{num(y)}" width="{num(size)}" height="{num(size)}"/>'


# Interface glyphs (24x24 grid unless noted) ---------------------------------


def glyph(name: str, x: float, y: float, size: float, color: str, opacity: float = 1.0) -> str:
    s = size / 24
    t = f'transform="translate({num(x)} {num(y)}) scale({num(s)})"'
    op = f' opacity="{num(opacity)}"' if opacity != 1 else ""
    stroke = f'stroke="{color}" stroke-linecap="round" stroke-linejoin="round"'
    shapes = {
        "sparkle": f'<path d="M12 1.5C12.6 8 14.5 10.4 22 12C14.5 13.6 12.6 16 12 22.5C11.4 16 9.5 13.6 2 12C9.5 '
        f'10.4 11.4 8 12 1.5Z" fill="{color}"/>',
        "wifi": f'<g {stroke} stroke-width="2.2" fill="none"><path d="M2.5 9.2a14 14 0 0 1 19 0"/>'
        f'<path d="M5.8 12.6a9.2 9.2 0 0 1 12.4 0"/><path d="M9.1 16a4.4 4.4 0 0 1 5.8 0"/></g>'
        f'<circle cx="12" cy="19.2" r="1.7" fill="{color}"/>',
        "battery": f'<rect x="1.5" y="6.5" width="18.5" height="11" rx="3.2" stroke="{color}" stroke-opacity=".55" '
        f'stroke-width="1.4"/><rect x="3.4" y="8.4" width="12.2" height="7.2" rx="1.7" fill="{color}"/>'
        f'<path d="M21.6 10v4" stroke="{color}" stroke-opacity=".55" stroke-width="1.6" stroke-linecap="round"/>',
        "control": f'<g fill="none" stroke="{color}" stroke-width="1.7"><rect x="2.5" y="4" width="19" height="7" '
        f'rx="3.5"/><rect x="2.5" y="13" width="19" height="7" rx="3.5"/></g>'
        f'<circle cx="17.9" cy="7.5" r="2.1" fill="{color}"/><circle cx="6.1" cy="16.5" r="2.1" fill="{color}"/>',
        "search": f'<g fill="none" {stroke} stroke-width="2.2"><circle cx="10.5" cy="10.5" r="6.5"/>'
        f'<path d="M15.5 15.5L21 21"/></g>',
        "switch": f'<g transform="scale(.24)"><path d="{S_PATH}" stroke="{color}" stroke-width="12" '
        f'stroke-linecap="round" fill="none"/><circle cx="73.6" cy="25" r="8.6" fill="{color}"/>'
        f'<circle cx="26.4" cy="75.8" r="8.6" fill="{color}"/></g>',
        "location": f'<path d="M20.5 3.5L3.5 10.9L11.4 12.6L13.1 20.5Z" fill="{color}"/>',
        "arrow": f'<g fill="none" {stroke} stroke-width="2.4"><path d="M7 17L17 7"/><path d="M8.5 7H17V15.5"/></g>',
        "mail": f'<g fill="none" {stroke} stroke-width="2"><rect x="2.5" y="4.5" width="19" height="15" rx="3.5"/>'
        f'<path d="M3.5 7.2L12 13.2L20.5 7.2"/></g>',
        "globe": f'<g fill="none" {stroke} stroke-width="1.9"><circle cx="12" cy="12" r="9.5"/>'
        f'<path d="M2.5 12H21.5"/><path d="M12 2.5C14.8 5.3 16 8.6 16 12S14.8 18.7 12 21.5C9.2 18.7 8 15.4 8 12S9.2 '
        f'5.3 12 2.5Z"/></g>',
        "check": f'<path d="M5.5 12.5L10 17L18.5 7.5" fill="none" {stroke} stroke-width="3"/>',
        "shield": f'<path d="M12 2.5L19.5 5.4V11C19.5 15.8 16.5 19.4 12 21.5C7.5 19.4 4.5 15.8 4.5 11V5.4Z" '
        f'fill="{color}"/>',
        "bolt": f'<path d="M13.5 2L5 13.5H11L10 22L19 10H13Z" fill="{color}"/>',
    }
    return f"<g {t}{op}>{shapes[name]}</g>"
