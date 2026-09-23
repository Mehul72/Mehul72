"""Generates the profile artwork in ../assets.

Setup, from this folder. Fonts and brand icons download into .cache on first run.

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

Build:

    .venv/bin/python build.py            # everything
    .venv/bin/python build.py header     # one scene while iterating

Preview: serve the repo root with `python3 -m http.server 8765` and open
http://127.0.0.1:8765/design/preview/readme.html (add ?theme=light for light mode,
&t=14.5 to pause every animation at 14.5 seconds). preview/frame.html?src=...&t=...
shows a single scene, and shoot.py saves any of these pages as a PNG.
"""

from __future__ import annotations

import sys
from pathlib import Path

from icons import BRANDS, brand, brand_path, glyph, icon
from icons import base as icon_base
from svgkit import BODY, FONTS, HEADLINE, MEDIUM, MONO, MONO_BOLD, SEMI, TITLE, Doc, measure, num, rounded_rect_path, wrap

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

THEMES = ("dark", "light")


def is_dark(theme: str) -> bool:
    return theme == "dark"


# Shared pieces ------------------------------------------------------------


def linear(gid: str, stops: list[tuple[float, str, float]], x1=0, y1=0, x2=0, y2=1, units: str = "") -> str:
    body = "".join(
        f'<stop offset="{num(o)}" stop-color="{c}"' + (f' stop-opacity="{num(a)}"' if a != 1 else "") + "/>"
        for o, c, a in stops
    )
    unit_attr = f' gradientUnits="{units}"' if units else ""
    return (
        f'<linearGradient id="{gid}" x1="{num(x1)}" y1="{num(y1)}" x2="{num(x2)}" y2="{num(y2)}"{unit_attr}>'
        f"{body}</linearGradient>"
    )


def radial(gid: str, color: str, opacity: float, mid: float = 0.45) -> str:
    return (
        f'<radialGradient id="{gid}"><stop offset="0" stop-color="{color}" stop-opacity="{num(opacity)}"/>'
        f'<stop offset="{num(mid)}" stop-color="{color}" stop-opacity="{num(opacity * 0.45)}"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>'
    )


def glass(doc: Doc, gid: str, x, y, w, h, r, theme: str, strength: float = 1.0) -> str:
    """A Liquid Glass style platter: translucent body, bright rim, soft inner light."""
    dark = is_dark(theme)
    fill_top, fill_bottom = ((0.16, 0.07) if dark else (0.62, 0.38))
    doc.define(
        f"glass-{gid}",
        linear(f"{gid}-fill", [(0, "#fff", fill_top * strength), (1, "#fff", fill_bottom * strength)])
        + linear(
            f"{gid}-rim",
            [(0, "#fff", 0.62 if dark else 0.95), (0.35, "#fff", 0.1 if dark else 0.5),
             (0.7, "#fff", 0.05 if dark else 0.3), (1, "#fff", 0.28 if dark else 0.8)],
        ),
    )
    path = rounded_rect_path(x, y, w, h, r)
    edge = "" if dark else f'<path d="{rounded_rect_path(x - .5, y - .5, w + 1, h + 1, r + .5)}" stroke="#000" stroke-opacity=".07"/>'
    return (
        f'<path d="{path}" fill="url(#{gid}-fill)"/>'
        + edge
        + f'<path d="{path}" stroke="url(#{gid}-rim)" stroke-width="1.2"/>'
        + f'<path d="{rounded_rect_path(x + 2, y + 2, w - 4, h - 4, max(r - 2, 1))}" stroke="#fff" '
        f'stroke-opacity="{".05" if dark else ".35"}" stroke-width="2"/>'
    )


def shadow_filter(doc: Doc, fid: str, ambient: tuple[float, float, float], key: tuple[float, float, float]) -> str:
    """Two-part drop shadow (blur, offset, opacity) for a wide soft shadow plus a tight contact one."""
    layers = []
    for i, (blur, dy, opacity) in enumerate((ambient, key)):
        layers.append(
            f'<feGaussianBlur in="SourceAlpha" stdDeviation="{num(blur)}"/><feOffset dy="{num(dy)}"/>'
            f'<feComponentTransfer result="s{i}"><feFuncA type="linear" slope="{num(opacity)}"/></feComponentTransfer>'
        )
    doc.define(
        fid,
        f'<filter id="{fid}" x="-30%" y="-30%" width="160%" height="170%" color-interpolation-filters="sRGB">'
        + "".join(layers)
        + '<feMerge><feMergeNode in="s0"/><feMergeNode in="s1"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
    )
    return f'filter="url(#{fid})"'


def soft_shadow(x, y, w, h, r, opacity: float, spread: int = 7, step: float = 3.0, dy: float = 6) -> str:
    """Layered rounded rects standing in for a blur, which is costly to animate."""
    layers = []
    for i in range(spread, 0, -1):
        grow = i * step
        layers.append(
            f'<path d="{rounded_rect_path(x - grow, y - grow + dy, w + 2 * grow, h + 2 * grow, r + grow)}" '
            f'fill="#000" fill-opacity="{num(opacity / spread)}"/>'
        )
    return "".join(layers)


class Timeline:
    """Builds SMIL values/keyTimes/keySplines from (time, value) frames."""

    EASE = "0.42 0 0.58 1"
    OUT = "0.16 0.84 0.3 1"
    LINEAR = "0 0 1 1"

    def __init__(self, total: float) -> None:
        self.total = total
        self.frames: list[tuple[float, str, str]] = []

    def at(self, t: float, value, spline: str = EASE) -> "Timeline":
        self.frames.append((t, str(value), spline))
        return self

    def animate(self, attribute: str, kind: str = "animate", extra: str = "") -> str:
        frames = sorted(self.frames, key=lambda f: f[0])
        if frames[0][0] > 0:
            frames.insert(0, (0.0, frames[0][1], self.LINEAR))
        if frames[-1][0] < self.total:
            frames.append((self.total, frames[-1][1], self.LINEAR))
        values = ";".join(v for _, v, _ in frames)
        times = ";".join(num(min(t / self.total, 1) if i < len(frames) - 1 else 1) for i, (t, _, _) in enumerate(frames))
        splines = ";".join(s for _, _, s in frames[:-1])
        tag = "animateTransform" if kind == "transform" else "animate"
        return (
            f'<{tag} attributeName="{attribute}" {extra} dur="{num(self.total)}s" repeatCount="indefinite" '
            f'values="{values}" keyTimes="{times}" calcMode="spline" keySplines="{splines}"/>'
        )


# Header -------------------------------------------------------------------

HEADER_W, HEADER_H = 1280, 470

WALLPAPER = {
    "dark": {
        "base": ("#06050E", "#0B0A1B"),
        "blobs": [
            (250, 110, 560, 330, "#7C3AED", 0.7),
            (1010, 60, 600, 340, "#2563EB", 0.6),
            (760, 480, 520, 280, "#DB2777", 0.44),
            (110, 480, 440, 250, "#0891B2", 0.46),
            (1210, 440, 320, 200, "#F59E0B", 0.2),
        ],
        # path, colours along the ribbon, stroke widths (outer to inner), opacity per layer
        "ribbons": [
            ("M-120 440C180 300 430 440 700 330S1120 150 1420 170", ("#8B5CF6", "#EC4899", "#F59E0B"),
             (280, 180, 104, 48, 12), (0.05, 0.06, 0.08, 0.12, 0.22)),
            ("M-100 70C260 170 520 20 820 110S1180 310 1400 250", ("#22D3EE", "#3B82F6", "#A78BFA"),
             (200, 118, 58, 14), (0.04, 0.05, 0.07, 0.14)),
        ],
    },
    "light": {
        "base": ("#F4F0FF", "#E9F1FF"),
        "blobs": [
            (250, 110, 560, 330, "#A78BFA", 0.55),
            (1010, 60, 600, 340, "#60A5FA", 0.45),
            (760, 480, 520, 280, "#F472B6", 0.34),
            (110, 480, 440, 250, "#2DD4BF", 0.30),
            (1210, 440, 320, 200, "#FBBF24", 0.24),
        ],
        "ribbons": [
            ("M-120 440C180 300 430 440 700 330S1120 150 1420 170", ("#C4B5FD", "#F9A8D4", "#FDBA74"),
             (280, 180, 104, 48, 12), (0.1, 0.12, 0.14, 0.2, 0.5)),
            ("M-100 70C260 170 520 20 820 110S1180 310 1400 250", ("#FFFFFF", "#FFFFFF", "#FFFFFF"),
             (200, 118, 58, 14), (0.1, 0.12, 0.16, 0.45)),
        ],
    },
}

DRIFT_CSS = (
    ".blob{transform-box:fill-box;transform-origin:50% 50%}"
    ".b0{animation:b0 24s ease-in-out infinite alternate}"
    ".b1{animation:b1 28s ease-in-out infinite alternate}"
    ".b2{animation:b2 22s ease-in-out infinite alternate}"
    ".b3{animation:b3 26s ease-in-out infinite alternate}"
    ".b4{animation:b4 30s ease-in-out infinite alternate}"
    "@keyframes b0{to{transform:translate(140px,50px) scale(1.12)}}"
    "@keyframes b1{to{transform:translate(-160px,40px) scale(1.08)}}"
    "@keyframes b2{to{transform:translate(-120px,-60px) scale(1.15)}}"
    "@keyframes b3{to{transform:translate(110px,-40px) scale(1.1)}}"
    "@keyframes b4{to{transform:translate(-90px,-30px) scale(1.2)}}"
    ".r0{animation:r0 32s ease-in-out infinite alternate}"
    ".r1{animation:r1 26s ease-in-out infinite alternate}"
    "@keyframes r0{to{transform:translate(-70px,26px)}}"
    "@keyframes r1{to{transform:translate(60px,-18px)}}"
    "@media (prefers-reduced-motion:reduce){.blob,.r0,.r1{animation:none}}"
)


def wallpaper(
    doc: Doc, theme: str, w: float = HEADER_W, h: float = HEADER_H, prefix: str = "wp", animated: bool = True
) -> str:
    """The aurora wallpaper, drawn in header coordinates and scaled to fit."""
    spec = WALLPAPER[theme]
    top, bottom = spec["base"]
    doc.define(f"{prefix}-base", linear(f"{prefix}-base", [(0, top, 1), (1, bottom, 1)]))
    out = [f'<rect width="{HEADER_W}" height="{HEADER_H}" fill="url(#{prefix}-base)"/>']
    for i, (cx, cy, rx, ry, color, opacity) in enumerate(spec["blobs"]):
        doc.define(f"{prefix}-g{i}", radial(f"{prefix}-g{i}", color, opacity))
        cls = f' class="blob b{i}"' if animated else ""
        out.append(f'<ellipse{cls} cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#{prefix}-g{i})"/>')
    for i, (d, colors, widths, opacities) in enumerate(spec["ribbons"]):
        gid = f"{prefix}-r{i}"
        c0, c1, c2 = colors
        doc.define(
            gid,
            linear(gid, [(0, c0, 0), (0.22, c0, 1), (0.5, c1, 1), (0.78, c2, 1), (1, c2, 0)],
                   -120, 0, 1420, 0, units="userSpaceOnUse"),
        )
        strokes = "".join(
            f'<path d="{d}" stroke="url(#{gid})" stroke-opacity="{num(o)}" stroke-width="{wd}" stroke-linecap="round"/>'
            for wd, o in zip(widths, opacities)
        )
        out.append(f'<g class="r{i}">{strokes}</g>' if animated else f"<g>{strokes}</g>")
    body = "".join(out)
    if (w, h) != (HEADER_W, HEADER_H):
        body = f'<g transform="scale({num(w / HEADER_W)} {num(h / HEADER_H)})">{body}</g>'
    return body


def notch_path(cx: float, w: float, h: float, r: float, f: float) -> str:
    k = 0.5523
    x0, x1 = cx - w / 2, cx + w / 2
    return (
        f"M{num(x0 - f)} 0C{num(x0 - f + f * k)} 0 {num(x0)} {num(f - f * k)} {num(x0)} {num(f)}"
        f"L{num(x0)} {num(h - r)}C{num(x0)} {num(h - r + r * k)} {num(x0 + r - r * k)} {num(h)} {num(x0 + r)} {num(h)}"
        f"L{num(x1 - r)} {num(h)}C{num(x1 - r + r * k)} {num(h)} {num(x1)} {num(h - r + r * k)} {num(x1)} {num(h - r)}"
        f"L{num(x1)} {num(f)}C{num(x1)} {num(f - f * k)} {num(x1 + f - f * k)} 0 {num(x1 + f)} 0Z"
    )


ACTIVITIES = [
    ("switchboard", "Switchboard", "New release · everyday tools in your menu bar", "check"),
    ("nomi", "Nomi", "Thinking on-device, on Apple Silicon", "wave"),
    ("codegraph", "codegraph", "impact_of → 32 symbols across 10 files", "ms"),
    ("kerbside", "Kerbside NSW", "Parking time left", "timer"),
    ("hookrelay", "HookRelay", "Delivered · at least once, never silently lost", "ok"),
    ("crossbar", "Crossbar", "One thread across Codex and Claude Code", "agents"),
    ("contractguard", "ContractGuard", "Breaking API change caught before merge", "breaking"),
]

DOCK = ["switchboard", "nomi", "kerbside", "locsim", "codegraph", "crossbar", "skills", "hookrelay", "contractguard"]

SLOT = 4.0
LEAD = 0.9
CYCLE = LEAD + SLOT * len(ACTIVITIES)
ISLAND_W = 500
TRAILING_W = {"check": 24, "wave": 40, "ms": 42, "timer": 68, "ok": 58, "agents": 52, "breaking": 90}


def trailing(doc: Doc, kind: str, right: float, cy: float) -> str:
    if kind == "check":
        return (
            f'<circle cx="{num(right - 12)}" cy="{num(cy)}" r="12" fill="#30D158"/>'
            + glyph("check", right - 21, cy - 9, 18, "#04210F")
        )
    if kind == "wave":
        bars = []
        heights = [(6, 18, 9), (10, 22, 7), (16, 8, 20), (8, 20, 12), (5, 14, 7)]
        for i, (a, b, c) in enumerate(heights):
            x = right - 40 + i * 8
            vals = ";".join(str(v) for v in (a, b, c, a))
            ys = ";".join(num(cy - v / 2) for v in (a, b, c, a))
            dur = 0.9 + i * 0.13
            bars.append(
                f'<rect x="{num(x)}" y="{num(cy - a / 2)}" width="4" height="{a}" rx="2" fill="url(#wave)">'
                f'<animate attributeName="height" values="{vals}" dur="{num(dur)}s" repeatCount="indefinite"/>'
                f'<animate attributeName="y" values="{ys}" dur="{num(dur)}s" repeatCount="indefinite"/></rect>'
            )
        doc.define("wave", linear("wave", [(0, "#E9D5FF", 1), (1, "#8B5CF6", 1)]))
        return "".join(bars)
    if kind == "ms":
        return doc.text(right, cy + 5.5, "31 ms", SEMI, 16, "#5EEAD4", anchor="end")
    if kind == "timer":
        return doc.text(right, cy + 6, "1:42:07", SEMI, 18, "#34D399", anchor="end")
    if kind == "ok":
        return glyph("check", right - 58, cy - 9, 18, "#4ADE80") + doc.text(right, cy + 5.5, "200", SEMI, 16, "#4ADE80", anchor="end")
    if kind == "agents":
        out = []
        for i, (slug, bg, ink) in enumerate([("openai", "#F5F5F7", "#0A0A0B"), ("claude", "#D97757", "#fff")]):
            cx = right - 37 + i * 22
            out.append(
                f'<circle cx="{num(cx)}" cy="{num(cy)}" r="15" fill="{bg}" stroke="#000" stroke-width="2.5"/>'
                f'<path d="{brand_path(slug)}" fill="{ink}" transform="translate({num(cx - 15)} {num(cy - 15)}) scale(.3)"/>'
            )
        return "".join(out)
    if kind == "breaking":
        label = "1 breaking"
        width = measure(SEMI, label, 13) + 20
        return (
            f'<rect x="{num(right - width)}" y="{num(cy - 12)}" width="{num(width)}" height="24" rx="12" '
            f'fill="#FF9F0A" fill-opacity=".18"/>'
            + doc.text(right - width / 2, cy + 4.5, label, SEMI, 13, "#FFB340", anchor="middle")
        )
    raise ValueError(kind)


def header(theme: str) -> Doc:
    dark = is_dark(theme)
    W, H = HEADER_W, HEADER_H
    doc = Doc(W, H)
    doc.style(DRIFT_CSS)
    ink = "#F5F5F7" if dark else "#1D1D1F"
    doc.define("screen", f'<clipPath id="screen"><rect width="{W}" height="{H}" rx="26"/></clipPath>')

    parts = [wallpaper(doc, theme)]

    # A soft scrim keeps the headline legible over the brightest part of the aurora.
    doc.define("scrim", radial("scrim", "#000" if dark else "#fff", 0.3 if dark else 0.5, 0.5))
    parts.append(f'<ellipse cx="640" cy="235" rx="520" ry="150" fill="url(#scrim)"/>')

    # Menu bar
    parts.append(f'<rect width="{W}" height="32" fill="{"#05040C" if dark else "#fff"}" fill-opacity="{".36" if dark else ".46"}"/>')
    parts.append(f'<rect y="32" width="{W}" height="1" fill="{"#fff" if dark else "#000"}" fill-opacity=".06"/>')
    parts.append(glyph("sparkle", 20, 9, 15, ink))
    x = 48
    for i, item in enumerate(["Mehul", "Projects", "Stack", "Activity", "Contact"]):
        face = SEMI if i == 0 else MEDIUM
        parts.append(doc.text(x, 21.5, item, face, 14, ink, opacity=1 if i == 0 else 0.86))
        x += measure(face, item, 14) + 18
    assert x - 18 < 640 - ISLAND_W / 2 - 24, "menu items run under the expanded notch"
    clock = "Sydney, AU"
    right = W - 20
    parts.append(doc.text(right, 21.5, clock, MEDIUM, 14, ink, anchor="end", opacity=0.9))
    right -= measure(MEDIUM, clock, 14) + 18
    for name, size in [("control", 17), ("search", 15), ("wifi", 17), ("battery", 21), ("switch", 16), ("sparkle", 15)]:
        right -= size
        parts.append(glyph(name, right, 16 - size / 2, size, ink, opacity=0.9))
        right -= 16

    # Headline
    doc.define(
        "title-fill",
        linear("title-fill", [(0, "#FFFFFF", 1), (1, "#D9D3FF", 1)] if dark else [(0, "#15151B", 1), (1, "#43359C", 1)]),
    )
    parts.append(doc.text(640, 226, "Mehul", TITLE, 134, "url(#title-fill)", anchor="middle", spacing=-4.5))
    sep = ("  ·  ", MEDIUM, ink)
    tag_runs = [
        ("Native Mac & iPhone apps", MEDIUM, ink), sep, ("Reliable backends", MEDIUM, ink), sep,
        ("Tools for AI coding agents", MEDIUM, ink),
    ]
    parts.append(doc.runs(640, 276, tag_runs, 23, anchor="middle", attrs=f'fill-opacity="{".8" if dark else ".74"}"'))

    # Status pills
    pill_h, pill_y = 36, 302
    pills = [("location", "Sydney, Australia"), ("live", "Open to collaboration")]
    widths = [16 + 16 + 9 + measure(MEDIUM, label, 15) + 18 for _, label in pills]
    gap = 12
    px = 640 - (sum(widths) + gap) / 2
    doc.style(
        ".pulse{transform-box:fill-box;transform-origin:50% 50%;animation:pulse 2.4s ease-out infinite}"
        "@keyframes pulse{0%{transform:scale(1);opacity:.55}70%,100%{transform:scale(2.6);opacity:0}}"
    )
    for (kind, label), width in zip(pills, widths):
        parts.append(glass(doc, "pill", px, pill_y, width, pill_h, pill_h / 2, theme))
        gx, cy = px + 16, pill_y + pill_h / 2
        if kind == "location":
            parts.append(glyph("location", gx, cy - 8, 16, "#0A84FF" if not dark else "#64D2FF"))
        else:
            parts.append(
                f'<circle class="pulse" cx="{num(gx + 8)}" cy="{num(cy)}" r="4.5" fill="#30D158"/>'
                f'<circle cx="{num(gx + 8)}" cy="{num(cy)}" r="4.5" fill="#30D158"/>'
            )
        parts.append(doc.text(gx + 16 + 9, cy + 5.2, label, MEDIUM, 15, ink, opacity=0.92))
        px += width + gap

    # Dock
    size, gap, pad = 58, 14, 13
    dock_w = len(DOCK) * size + (len(DOCK) - 1) * gap + 2 * pad
    dock_h = size + 2 * pad
    dock_x, dock_y = (W - dock_w) / 2, H - 22 - dock_h
    parts.append(soft_shadow(dock_x, dock_y, dock_w, dock_h, 28, 0.22 if dark else 0.08, spread=6, step=3, dy=8))
    parts.append(glass(doc, "dock", dock_x, dock_y, dock_w, dock_h, 28, theme))
    starts = {name: LEAD + i * SLOT for i, (name, *_rest) in enumerate(ACTIVITIES)}
    for i, name in enumerate(DOCK):
        ix = dock_x + pad + i * (size + gap)
        iy = dock_y + pad
        bounce = ""
        if name in starts:
            s = starts[name]
            tl = Timeline(CYCLE)
            tl.at(s, "0 0", Timeline.OUT).at(s + 0.17, "0 -18", Timeline.EASE).at(s + 0.36, "0 0", Timeline.OUT)
            tl.at(s + 0.5, "0 -8", Timeline.EASE).at(s + 0.64, "0 0", Timeline.LINEAR)
            bounce = tl.animate("transform", kind="transform", extra='type="translate"')
        parts.append(
            f'<ellipse cx="{num(ix + size / 2)}" cy="{num(iy + size - 1)}" rx="{num(size * 0.42)}" ry="5" '
            f'fill="#000" fill-opacity="{".35" if dark else ".14"}"/>'
            f"<g>{bounce}{icon(doc, name, ix, iy, size)}</g>"
        )
        parts.append(
            f'<circle cx="{num(ix + size / 2)}" cy="{num(dock_y + dock_h - 5)}" r="2" fill="{ink}" '
            f'fill-opacity="{".7" if dark else ".5"}"/>'
        )

    # Notch, expanding into a live activity for each project in turn
    compact = notch_path(640, 176, 32, 11, 7)
    overshoot = notch_path(640, ISLAND_W + 14, 95, 31, 12)
    expanded = notch_path(640, ISLAND_W, 92, 30, 12)
    shape = Timeline(CYCLE)
    for i in range(len(ACTIVITIES)):
        s = LEAD + i * SLOT
        shape.at(s, compact, Timeline.OUT).at(s + 0.34, overshoot, Timeline.EASE).at(s + 0.56, expanded, Timeline.LINEAR)
        shape.at(s + 3.1, expanded, Timeline.EASE).at(s + 3.5, compact, Timeline.LINEAR)
    parts.append(f'<path d="{compact}" fill="#000">{shape.animate("d")}</path>')
    parts.append('<circle cx="640" cy="15" r="3.2" fill="#0B0F1E"/><circle cx="639.2" cy="14.2" r="1" fill="#2A3558"/>')

    left, right, cy = 640 - ISLAND_W / 2 + 22, 640 + ISLAND_W / 2 - 24, 60
    for i, (name, title, subtitle, kind) in enumerate(ACTIVITIES):
        text_end = left + 58 + max(measure(SEMI, title, 16), measure(MEDIUM, subtitle, 13.5))
        assert text_end < right - TRAILING_W[kind] - 12, f"{name} activity text collides with its badge"
        s = LEAD + i * SLOT
        fade = Timeline(CYCLE)
        fade.at(s + 0.26, 0, Timeline.EASE).at(s + 0.56, 1, Timeline.LINEAR).at(s + 2.92, 1, Timeline.EASE).at(s + 3.16, 0, Timeline.LINEAR)
        rise = Timeline(CYCLE)
        rise.at(s + 0.26, "0 6", Timeline.OUT).at(s + 0.62, "0 0", Timeline.LINEAR).at(s + 2.92, "0 0", Timeline.EASE).at(s + 3.16, "0 -4", Timeline.LINEAR)
        motion = rise.animate("transform", kind="transform", extra='type="translate"')
        parts.append(
            f'<g opacity="0">{fade.animate("opacity")}{motion}'
            + icon(doc, name, left, cy - 22, 44)
            + doc.text(left + 58, cy - 3, title, SEMI, 16, "#fff")
            + doc.text(left + 58, cy + 17, subtitle, MEDIUM, 13.5, "#fff", opacity=0.62)
            + trailing(doc, kind, right, cy)
            + "</g>"
        )

    border = f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="25.5" stroke="{"#fff" if dark else "#000"}" stroke-opacity="{".1" if dark else ".08"}"/>'
    doc.add('<g clip-path="url(#screen)">', *parts, "</g>", border)
    return doc


# About: "About This Mac" for a person, beside a terminal ---------------------

ABOUT_ROWS = [
    ("Builds", "Mac & iPhone apps"),
    ("Also", "Backends, tools for AI agents"),
    ("Speaks", "Swift, Go, TypeScript, Python"),
    ("Based in", "Sydney, Australia"),
    ("Status", "Open to collaboration"),
]

PROMPT = [("mehul@mac", "#7EE787"), (" ~", "#79C0FF"), (" % ", "#E6EDF3")]

TERMINAL = [
    ("cmd", "cat now.md"),
    ("kv", "shipping", "Switchboard", ", a menu bar toolkit for macOS"),
    ("kv", "building", "Nomi", ", an on-device assistant in the notch"),
    ("kv", "hacking", "codegraph", " and **Crossbar**, tools for AI agents"),
    ("blank",),
    ("cmd", "cat how-i-build.md"),
    ("num", "01", "Local first. No accounts unless they earn it."),
    ("num", "02", "Say what the system guarantees, then prove it."),
    ("num", "03", "Small tools for small, recurring annoyances."),
    ("num", "04", "Measure it: tokens, milliseconds, percentiles."),
    ("blank",),
    ("prompt",),
]


def traffic_lights(x: float, y: float) -> str:
    out = []
    for i, (fill, edge) in enumerate([("#FF5F57", "#E0443E"), ("#FEBC2E", "#DEA123"), ("#28C840", "#1AAB29")]):
        out.append(f'<circle cx="{num(x + i * 22)}" cy="{num(y)}" r="7" fill="{fill}" stroke="{edge}" stroke-width=".8"/>')
    return "".join(out)


def macbook(doc: Doc, theme: str, cx: float, top: float) -> str:
    dark = is_dark(theme)
    lid_w, lid_h = 232, 146
    x0 = cx - lid_w / 2
    sx, sy, sw, sh = x0 + 7, top + 7, lid_w - 14, lid_h - 14
    scale = sh / HEADER_H
    shift = sx - (HEADER_W * scale - sw) / 2
    doc.define("mb-screen", f'<clipPath id="mb-screen"><rect x="{num(sx)}" y="{num(sy)}" width="{num(sw)}" height="{num(sh)}" rx="4"/></clipPath>')
    doc.define(
        "mb-base",
        linear("mb-base", [(0, "#4A4B51", 1), (1, "#1D1E21", 1)] if dark else [(0, "#ECEDF0", 1), (1, "#A7A9B0", 1)]),
    )
    screen = (
        f'<g transform="translate({num(shift)} {num(sy)}) scale({num(scale)})">'
        + wallpaper(doc, theme, prefix="mb", animated=False)
        + f'<rect width="{HEADER_W}" height="32" fill="{"#000" if dark else "#fff"}" fill-opacity=".35"/>'
        + doc.text(640, 238, "Mehul", TITLE, 134, "#fff" if dark else "#1D1D1F", anchor="middle", spacing=-4.5)
        + glass(doc, "mbdock", 309, 370, 662, 84, 28, theme)
        + "".join(icon(doc, name, 322 + i * 72, 383, 58) for i, name in enumerate(DOCK))
        + f'<path d="{notch_path(640, 176, 32, 11, 7)}" fill="#000"/>'
        + "</g>"
    )
    base_y = top + lid_h
    return (
        f'<ellipse cx="{num(cx)}" cy="{num(base_y + 12)}" rx="150" ry="7" fill="#000" fill-opacity="{".5" if dark else ".16"}"/>'
        + f'<rect x="{num(x0)}" y="{num(top)}" width="{lid_w}" height="{lid_h}" rx="11" fill="#0A0A0C" '
        f'stroke="{"#56565E" if dark else "#B8BAC1"}" stroke-width="1.4"/>'
        + f'<g clip-path="url(#mb-screen)">{screen}</g>'
        + f'<path d="M{num(cx - 140)} {num(base_y)}H{num(cx + 140)}V{num(base_y + 5)}Q{num(cx + 140)} {num(base_y + 10)} '
        f'{num(cx + 131)} {num(base_y + 10)}H{num(cx - 131)}Q{num(cx - 140)} {num(base_y + 10)} {num(cx - 140)} '
        f'{num(base_y + 5)}Z" fill="url(#mb-base)"/>'
        + f'<rect x="{num(cx - 24)}" y="{num(base_y)}" width="48" height="3.6" rx="1.8" fill="#000" fill-opacity=".28"/>'
    )


def about(theme: str) -> Doc:
    dark = is_dark(theme)
    W, H = 1280, 648
    doc = Doc(W, H)
    ink = "#F5F5F7" if dark else "#1D1D1F"
    muted = "#98989F" if dark else "#6E6E73"
    parts = []
    # Blur is kept small enough to fade out inside the canvas; windows sit 24 units from its edges.
    lift = shadow_filter(doc, "lift", (18, 14, 0.5) if dark else (13, 10, 0.13), (3, 2, 0.3) if dark else (2.5, 2, 0.07))

    # Terminal, sitting behind the About window
    tx, ty, tw, th = 500, 70, 756, 500
    parts.append(f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="20" fill="#0B0B10" {lift}/>')
    doc.define(
        "term-bg",
        linear("term-bg", [(0, "#101017", 1), (1, "#0B0B10", 1)])
        + radial("term-glow-a", "#8B5CF6", 0.22, 0.5)
        + radial("term-glow-b", "#22D3EE", 0.12, 0.5)
        + f'<clipPath id="term-clip"><rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="20"/></clipPath>',
    )
    parts.append(
        '<g clip-path="url(#term-clip)">'
        f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" fill="url(#term-bg)"/>'
        f'<ellipse cx="{tx + tw - 60}" cy="{ty + 40}" rx="420" ry="260" fill="url(#term-glow-a)"/>'
        f'<ellipse cx="{tx + 120}" cy="{ty + th}" rx="380" ry="220" fill="url(#term-glow-b)"/>'
        f'<rect x="{tx}" y="{ty}" width="{tw}" height="52" fill="#fff" fill-opacity=".045"/>'
        f'<rect x="{tx}" y="{ty + 52}" width="{tw}" height="1" fill="#fff" fill-opacity=".08"/>'
        "</g>"
        f'<rect x="{tx + .5}" y="{ty + .5}" width="{tw - 1}" height="{th - 1}" rx="19.5" stroke="#fff" '
        f'stroke-opacity="{".14" if dark else ".1"}"/>'
    )
    parts.append(doc.text(tx + tw / 2 + 12, ty + 32, "mehul — -zsh — 80×24", MEDIUM, 15, "#fff", anchor="middle", opacity=0.55))

    size, lead = 18, 30
    char = 0.6 * size
    col = tx + 64
    y = ty + 102
    prompt_w = sum(len(t) for t, _ in PROMPT) * char
    clock = 0.35
    for n, line in enumerate(TERMINAL):
        kind = line[0]
        if kind == "blank":
            y += lead * 0.7
            continue
        if kind in ("cmd", "prompt"):
            appear = clock
            runs = [(t, MONO_BOLD if i == 0 else MONO, c) for i, (t, c) in enumerate(PROMPT)]
            cursor_x = col + prompt_w
            reveal = "" if n == 0 else f'<set attributeName="opacity" to="1" begin="{num(appear)}s" fill="freeze"/>'
            hidden = "" if n == 0 else ' opacity="0"'
            parts.append(f"<g{hidden}>{reveal}{doc.runs(col, y, runs, size)}</g>")
            if kind == "prompt":
                parts.append(
                    f'<rect x="{num(cursor_x)}" y="{num(y - 16)}" width="{num(char)}" height="21" rx="1.5" fill="#E6EDF3" opacity="0">'
                    f'<set attributeName="opacity" to="1" begin="{num(appear)}s" fill="freeze"/>'
                    f'<animate attributeName="opacity" values="1;0" dur="1.1s" calcMode="discrete" begin="{num(appear)}s" '
                    'repeatCount="indefinite"/></rect>'
                )
                break
            command = line[1]
            start = appear + 0.3
            step = 0.075
            steps = len(command)
            widths = ";".join(num(k * char) for k in range(steps + 1))
            xs = ";".join(num(cursor_x + k * char) for k in range(steps + 1))
            times = ";".join(num(k / steps) for k in range(steps + 1))
            dur = steps * step
            clip = f"type-{n}"
            doc.define(
                clip,
                f'<clipPath id="{clip}"><rect x="{num(cursor_x)}" y="{num(y - 20)}" width="0" height="28">'
                f'<animate attributeName="width" values="{widths}" keyTimes="{times}" calcMode="discrete" '
                f'begin="{num(start)}s" dur="{num(dur)}s" fill="freeze"/></rect></clipPath>',
            )
            parts.append(
                f'<g clip-path="url(#{clip})">' + doc.text(cursor_x, y, command, MONO, size, "#F0F6FC") + "</g>"
            )
            done = start + dur + 0.25
            parts.append(
                f'<rect x="{num(cursor_x)}" y="{num(y - 16)}" width="{num(char)}" height="21" rx="1.5" fill="#E6EDF3" opacity="0">'
                f'<set attributeName="opacity" to="1" begin="{num(appear)}s"/>'
                f'<set attributeName="opacity" to="0" begin="{num(done)}s" fill="freeze"/>'
                f'<animate attributeName="x" values="{xs}" keyTimes="{times}" calcMode="discrete" begin="{num(start)}s" '
                f'dur="{num(dur)}s" fill="freeze"/></rect>'
            )
            clock = done
        else:
            clock += 0.09
            if kind == "kv":
                _, key, name, rest = line
                runs = [(f"{key:<11}", MONO, "#C4B5FD"), (name, MONO_BOLD, "#FFFFFF")]
                for i, chunk in enumerate(rest.split("**")):
                    if chunk:
                        runs.append((chunk, MONO_BOLD, "#FFFFFF") if i % 2 else (chunk, MONO, "#C9D1D9"))
            else:
                _, index, text = line
                runs = [(f"{index}  ", MONO_BOLD, "#67E8F9"), (text, MONO, "#C9D1D9")]
            assert col + (2 + sum(len(t) for t, _, _ in runs)) * char < tx + tw - 36, f"terminal line {n} is too long"
            parts.append(
                f'<g opacity="0"><set attributeName="opacity" to="1" begin="{num(clock)}s" fill="freeze"/>'
                + doc.runs(col + char * 2, y, runs, size)
                + "</g>"
            )
            if TERMINAL[n + 1][0] != "kv" and TERMINAL[n + 1][0] != "num":
                clock += 0.35
        y += lead

    # About This Mehul
    ax, ay, aw, ah = 24, 22, 500, 572
    doc.define(
        "about-bg",
        linear("about-bg", [(0, "#2A2A31", 1), (1, "#1F1F25", 1)] if dark else [(0, "#FFFFFF", 1), (1, "#F5F5F8", 1)]),
    )
    parts.append(
        f'<rect x="{ax}" y="{ay}" width="{aw}" height="{ah}" rx="22" fill="url(#about-bg)" {lift}/>'
        f'<rect x="{ax + .5}" y="{ay + .5}" width="{aw - 1}" height="{ah - 1}" rx="21.5" '
        f'stroke="{"#fff" if dark else "#000"}" stroke-opacity="{".13" if dark else ".1"}"/>'
        f'<rect x="{ax + 22}" y="{ay + 1.5}" width="{aw - 44}" height="1" fill="#fff" fill-opacity="{".12" if dark else ".9"}"/>'
    )
    parts.append(traffic_lights(ax + 28, ay + 28))
    cx = ax + aw / 2
    parts.append(macbook(doc, theme, cx, ay + 62))
    parts.append(doc.text(cx, ay + 270, "Mehul", TITLE, 38, ink, anchor="middle", spacing=-0.8))
    parts.append(doc.text(cx, ay + 300, "Software Engineer", BODY, 19, muted, anchor="middle"))
    label_x, value_x = ax + 168, ax + 184
    row_y = ay + 352
    for label, value in ABOUT_ROWS:
        parts.append(doc.text(label_x, row_y, label, SEMI, 17, muted, anchor="end"))
        vx = value_x
        if label == "Status":
            parts.append(f'<circle cx="{num(vx + 5)}" cy="{num(row_y - 6)}" r="5" fill="#30D158"/>')
            vx += 18
        assert vx + measure(MEDIUM, value, 17) < ax + aw - 26, f"about row {label!r} is too wide"
        parts.append(doc.text(vx, row_y, value, MEDIUM, 17, ink))
        row_y += 31
    button_w = measure(MEDIUM, "More Info…", 16) + 34
    parts.append(
        f'<rect x="{num(cx - button_w / 2)}" y="{ay + 496}" width="{num(button_w)}" height="32" rx="9" '
        f'fill="{"#fff" if dark else "#000"}" fill-opacity="{".1" if dark else ".05"}" '
        f'stroke="{"#fff" if dark else "#000"}" stroke-opacity="{".1" if dark else ".08"}"/>'
        + doc.text(cx, ay + 517.5, "More Info…", MEDIUM, 16, ink, anchor="middle")
    )
    parts.append(doc.text(cx, ay + 552, "™ and © 2018–2026 Mehul. All rights reserved.", BODY, 13.5, muted, anchor="middle", opacity=0.85))

    doc.add(*parts)
    return doc


# Project cards -----------------------------------------------------------------

LANG_COLORS = {"Swift": "#F05138", "TypeScript": "#3178C6", "Go": "#00ADD8", "Python": "#3572A5"}

PROJECTS = [
    dict(
        repo="switchboard", name="Switchboard", kind="macOS menu bar app", icon="switchboard", accent="#3FD1BC",
        lang="Swift", tags=["AppKit", "SwiftUI", "Core Audio"],
        desc="A little more control over your Mac: everyday settings, per-app audio, clipboard history and "
        "window tools, all in the menu bar.",
    ),
    dict(
        repo="nomi", name="Nomi", kind="macOS assistant · in progress", icon="nomi", accent="#8B6CFF",
        lang="Swift", tags=["MLX", "Qwen3", "Vision"],
        desc="An assistant that lives in the MacBook notch and runs its language model on Apple Silicon. "
        "No API keys, no accounts, no cloud.",
    ),
    dict(
        repo="kerbside", name="Kerbside NSW", kind="iPhone app", icon="kerbside", accent="#22A35A",
        lang="Swift", tags=["ActivityKit", "WidgetKit", "Vision"],
        desc="Remember where you parked, what the NSW sign said and how long is left, with Lock Screen "
        "and Dynamic Island countdowns.",
    ),
    dict(
        repo="ios-location-simulator", name="iOS Location Simulator", kind="Developer tool", icon="locsim",
        accent="#3B82F6", lang="Python", tags=["FastAPI", "pymobiledevice3", "Leaflet"],
        desc="Override the GPS your iPhone reports from a map in your browser. Walk, drive or replay GPX "
        "routes, with no jailbreak.",
    ),
    dict(
        repo="codegraph", name="codegraph", kind="MCP server & CLI", icon="codegraph", accent="#2DD4BF",
        lang="TypeScript", tags=["MCP", "tree-sitter", "WebAssembly"],
        desc="A local code knowledge graph for AI coding agents. Answers “what calls this?” in a few "
        "hundred tokens instead of fifteen thousand.",
    ),
    dict(
        repo="crossbar", name="Crossbar", kind="VS Code extension", icon="crossbar", accent="#F2555A",
        lang="TypeScript", tags=["VS Code API", "React", "Claude Agent SDK"],
        desc="One chat for your coding agents: a VS Code sidebar that keeps a single conversation across "
        "Codex and Claude Code.",
    ),
    dict(
        repo="hookrelay", name="HookRelay", kind="Webhook delivery platform", icon="hookrelay", accent="#F59E0B",
        lang="Go", tags=["PostgreSQL", "Kafka", "Redis"],
        desc="Multi-tenant webhooks with an explicit guarantee: at least once, never silently lost. "
        "Retries, leases, dead letters and replay.",
    ),
    dict(
        repo="contract-guard", name="ContractGuard", kind="GitHub App", icon="contractguard", accent="#22C55E",
        lang="Go", tags=["GraphQL", "Next.js", "MongoDB"],
        desc="Catches breaking OpenAPI and GraphQL changes before a pull request merges, and reports "
        "them as GitHub Checks.",
    ),
]

CARD_W, CARD_H = 640, 310
CARD_PAD_X, CARD_PAD_TOP, CARD_PAD_BOTTOM = 16, 6, 10


def card(theme: str, project: dict) -> Doc:
    dark = is_dark(theme)
    W, H = CARD_W + 2 * CARD_PAD_X, CARD_H + CARD_PAD_TOP + CARD_PAD_BOTTOM
    doc = Doc(W, H)
    ink = "#F5F5F7" if dark else "#1D1D1F"
    muted = "#9A9AA3" if dark else "#6E6E73"
    body = "#C8C8D0" if dark else "#3C3C43"
    x0, y0 = CARD_PAD_X, CARD_PAD_TOP
    accent = project["accent"]
    doc.define(
        "card",
        linear("card-bg", [(0, "#17171E", 1), (1, "#0F0F14", 1)] if dark else [(0, "#FFFFFF", 1), (1, "#FAFAFC", 1)])
        + f'<radialGradient id="card-glow" cx="{x0 + CARD_W - 40}" cy="{y0 - 20}" r="360" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{accent}" stop-opacity="{".34" if dark else ".2"}"/>'
        f'<stop offset=".55" stop-color="{accent}" stop-opacity="{".08" if dark else ".05"}"/>'
        f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
        + f'<clipPath id="card-clip"><rect x="{x0}" y="{y0}" width="{CARD_W}" height="{CARD_H}" rx="30"/></clipPath>',
    )
    lift = "" if dark else " " + shadow_filter(doc, "card-lift", (4, 3, 0.06), (1.5, 1, 0.06))
    parts = [
        f'<rect x="{x0}" y="{y0}" width="{CARD_W}" height="{CARD_H}" rx="30" fill="url(#card-bg)"{lift}/>',
        f'<g clip-path="url(#card-clip)"><rect x="{x0}" y="{y0}" width="{CARD_W}" height="{CARD_H}" fill="url(#card-glow)"/></g>',
        f'<rect x="{x0 + .5}" y="{y0 + .5}" width="{CARD_W - 1}" height="{CARD_H - 1}" rx="29.5" '
        f'stroke="{"#fff" if dark else "#000"}" stroke-opacity="{".09" if dark else ".08"}"/>',
        f'<rect x="{x0 + 30}" y="{y0 + .5}" width="{CARD_W - 60}" height="1" fill="#fff" fill-opacity="{".1" if dark else "1"}"/>',
    ]
    icon_shadow = shadow_filter(doc, "icon-lift", (5, 4, 0.35 if dark else 0.14), (1, 1, 0.25 if dark else 0.08))
    parts.append(f"<g {icon_shadow}>" + icon(doc, project["icon"], x0 + 28, y0 + 28, 88) + "</g>")

    name_size = 31
    while measure(HEADLINE, project["name"], name_size, -0.4) > CARD_W - 136 - 84:
        name_size -= 1
    parts.append(doc.text(x0 + 136, y0 + 66, project["name"], HEADLINE, name_size, ink, spacing=-0.4))
    parts.append(doc.text(x0 + 136, y0 + 97, project["kind"], MEDIUM, 18, muted))

    bx, by = x0 + CARD_W - 50, y0 + 52
    parts.append(
        f'<circle cx="{bx}" cy="{by}" r="21" fill="{"#fff" if dark else "#000"}" fill-opacity="{".07" if dark else ".04"}" '
        f'stroke="{"#fff" if dark else "#000"}" stroke-opacity="{".1" if dark else ".06"}"/>'
        + glyph("arrow", bx - 10, by - 10, 20, ink, opacity=0.8)
    )

    lines = wrap(BODY, project["desc"], 20, CARD_W - 56)
    assert len(lines) <= 3, f"{project['name']} description wraps to {len(lines)} lines"
    for i, line in enumerate(lines):
        parts.append(doc.text(x0 + 28, y0 + 158 + i * 30, line, BODY, 20, body))

    fy = y0 + CARD_H - 44
    lx = x0 + 28
    parts.append(f'<circle cx="{num(lx + 7)}" cy="{num(fy)}" r="7" fill="{LANG_COLORS[project["lang"]]}"/>')
    parts.append(doc.text(lx + 22, fy + 6, project["lang"], SEMI, 17, ink, opacity=0.9))
    cx = lx + 22 + measure(SEMI, project["lang"], 17) + 18
    for tag in project["tags"]:
        tw = measure(MEDIUM, tag, 15.5) + 26
        parts.append(
            f'<rect x="{num(cx)}" y="{num(fy - 16)}" width="{num(tw)}" height="32" rx="16" '
            f'fill="{"#fff" if dark else "#000"}" fill-opacity="{".06" if dark else ".035"}" '
            f'stroke="{"#fff" if dark else "#000"}" stroke-opacity="{".08" if dark else ".06"}"/>'
            + doc.text(cx + tw / 2, fy + 5.5, tag, MEDIUM, 15.5, body, anchor="middle")
        )
        cx += tw + 8
    assert cx < x0 + CARD_W - 20, f"{project['name']} tags overflow the card"
    doc.add(*parts)
    return doc


# Section titles ------------------------------------------------------------------

SECTIONS = {
    "projects": ("PROJECTS", "Small tools. Solid systems.", "Native apps, backends, and tools for AI coding agents."),
    "stack": ("STACK", "What I build with.", "From Swift on the Mac to Go services and agent tooling."),
    "activity": ("ACTIVITY", "Lately on GitHub.", "Refreshed every day by a GitHub Action in this repo."),
    "contact": ("CONTACT", "Let’s build something.", "Open to collaborating on native apps and developer tools."),
}


def section(theme: str, key: str) -> Doc:
    dark = is_dark(theme)
    eyebrow, title, subtitle = SECTIONS[key]
    doc = Doc(1280, 176)
    doc.define(
        "eyebrow",
        linear("eyebrow", [(0, "#A78BFA" if dark else "#7C3AED", 1), (1, "#67E8F9" if dark else "#0891B2", 1)],
               540, 0, 740, 0, units="userSpaceOnUse"),
    )
    doc.add(
        doc.text(640, 50, eyebrow, SEMI, 16, "url(#eyebrow)", anchor="middle", spacing=3.6),
        doc.text(640, 114, title, TITLE, 54, "#F5F5F7" if dark else "#1D1D1F", anchor="middle", spacing=-1.6),
        doc.text(640, 156, subtitle, BODY, 22, "#9A9AA3" if dark else "#6E6E73", anchor="middle"),
    )
    return doc


# Stack ----------------------------------------------------------------------------

STACK = [
    ("LANGUAGES & APPLE", ["swift", "swiftui", "go", "typescript", "python", "javascript", "gnubash", "mlx"]),
    ("BACKEND & DATA", ["postgresql", "apachekafka", "redis", "mongodb", "graphql", "docker", "fastapi", "nodedotjs"]),
    ("WEB & AI TOOLING", ["react", "nextdotjs", "visualstudiocode", "modelcontextprotocol", "claude", "openai",
                          "webassembly", "githubactions"]),
]


def stack(theme: str) -> Doc:
    dark = is_dark(theme)
    tile, pitch = 86, 142
    grid_w = pitch * 7 + tile
    x0 = (1280 - grid_w) / 2
    row_h = 186
    H = 44 + row_h * len(STACK) + 6
    doc = Doc(1280, H)
    ink = "#E5E5EA" if dark else "#1D1D1F"
    muted = "#8E8E96" if dark else "#86868B"
    parts = [
        f'<rect x="24" y="8" width="1232" height="{H - 16}" rx="40" fill="{"#fff" if dark else "#000"}" '
        f'fill-opacity="{".025" if dark else ".018"}" stroke="{"#fff" if dark else "#000"}" '
        f'stroke-opacity="{".07" if dark else ".05"}"/>'
    ]
    lift = shadow_filter(doc, "tile-lift", (6, 5, 0.4 if dark else 0.14), (1.2, 1, 0.3 if dark else 0.08))
    y = 48
    for caption, slugs in STACK:
        parts.append(doc.text(x0, y + 8, caption, SEMI, 15, muted, spacing=2.4))
        parts.append(f'<rect x="{num(x0 + measure(SEMI, caption, 15, 2.4) + 14)}" y="{y + 3}" '
                     f'width="{num(grid_w - measure(SEMI, caption, 15, 2.4) - 14)}" height="1" '
                     f'fill="{"#fff" if dark else "#000"}" fill-opacity="{".08" if dark else ".07"}"/>')
        for i, slug in enumerate(slugs):
            tx = x0 + i * pitch
            parts.append(f"<g {lift}>" + brand(doc, slug, tx, y + 30, tile, MONO_BOLD) + "</g>")
            parts.append(doc.text(tx + tile / 2, y + 30 + tile + 32, BRANDS[slug][0], MEDIUM, 17, ink, anchor="middle"))
        y += row_h
    doc.add(*parts)
    return doc


# Contact buttons ----------------------------------------------------------------

CONTACTS = {
    "linkedin": ("LinkedIn", ["#2A8BE6", "#0A66C2", "#084D94"], "brand"),
    "email": ("Email", ["#5AC8FA", "#3478F6", "#5E5CE6"], "mail"),
    "website": ("Website", ["#34D399", "#14B8A6", "#0E7490"], "globe"),
}


def contact(theme: str, key: str) -> Doc:
    dark = is_dark(theme)
    label, stops, kind = CONTACTS[key]
    ink = "#F5F5F7" if dark else "#1D1D1F"
    text_w = measure(SEMI, label, 22)
    pill_h, tile = 64, 42
    pill_w = 11 + tile + 14 + text_w + 16 + 20 + 22
    W, H = pill_w + 12, pill_h + 14
    doc = Doc(W, H)
    x0, y0 = 6, 4
    lift = "" if dark else " " + shadow_filter(doc, "pill-lift", (4, 3, 0.08), (1, 1, 0.06))
    parts = [
        f'<rect x="{x0}" y="{y0}" width="{num(pill_w)}" height="{pill_h}" rx="{pill_h / 2}" '
        f'fill="{"#1A1A21" if dark else "#fff"}"{lift}/>',
        f'<rect x="{x0 + .5}" y="{y0 + .5}" width="{num(pill_w - 1)}" height="{pill_h - 1}" rx="{pill_h / 2 - .5}" '
        f'stroke="{"#fff" if dark else "#000"}" stroke-opacity="{".12" if dark else ".08"}"/>',
    ]
    tx, ty = x0 + 11, y0 + (pill_h - tile) / 2
    doc.define(f"ct-{key}", linear(f"ct-{key}", [(i / 2, c, 1) for i, c in enumerate(stops)], 0, 0, 1, 1))
    icon_base(doc)
    s = tile / 100
    if kind == "brand":
        mark = f'<path d="{brand_path("linkedin")}" fill="#fff" transform="translate(20 20) scale(.6)"/>'
    else:
        mark = glyph(kind, 25, 25, 50, "#fff")
    parts.append(
        f'<g transform="translate({num(tx)} {num(ty)}) scale({num(s)})">'
        f'<use href="#sq" fill="url(#ct-{key})"/>{mark}'
        '<use href="#sq" stroke="url(#rim)" stroke-width="2.2" clip-path="url(#sqc)"/></g>'
    )
    lx = tx + tile + 14
    parts.append(doc.text(lx, y0 + pill_h / 2 + 7.5, label, SEMI, 22, ink))
    parts.append(glyph("arrow", lx + text_w + 14, y0 + pill_h / 2 - 10, 20, ink, opacity=0.55))
    doc.add(*parts)
    return doc


# Footer ---------------------------------------------------------------------------


def footer(theme: str) -> Doc:
    dark = is_dark(theme)
    doc = Doc(1280, 190)
    doc.define(
        "footer-line",
        linear("footer-line", [(0, "#8B5CF6", 0), (0.3, "#8B5CF6", 1), (0.5, "#EC4899", 1), (0.7, "#22D3EE", 1),
                               (1, "#22D3EE", 0)], 160, 0, 1120, 0, units="userSpaceOnUse")
        + radial("footer-glow", "#8B5CF6", 0.28 if dark else 0.14, 0.5),
    )
    doc.add(
        '<ellipse cx="640" cy="40" rx="420" ry="46" fill="url(#footer-glow)"/>',
        '<rect x="160" y="39" width="960" height="1.5" fill="url(#footer-line)"/>',
        glyph("sparkle", 626, 78, 28, "#C4B5FD" if dark else "#7C3AED"),
        doc.text(640, 146, "Thanks for stopping by.", SEMI, 24, "#F5F5F7" if dark else "#1D1D1F", anchor="middle"),
        doc.text(640, 178, "Built in Sydney, one small tool at a time.", BODY, 19, "#9A9AA3" if dark else "#6E6E73", anchor="middle"),
    )
    return doc


# Entry point ----------------------------------------------------------------

SCENES = {
    "header": header,
    "about": about,
    "stack": stack,
    "footer": footer,
}
PER_ITEM = {
    "card": (card, {p["repo"]: p for p in PROJECTS}),
    "section": (section, {k: k for k in SECTIONS}),
    "contact": (contact, {k: k for k in CONTACTS}),
}


ACTIVITY_FONTS = ROOT / "scripts" / "fonts"
UI_CHARS = "".join(chr(c) for c in range(32, 127)) + "·–—’…"


def activity_fonts() -> None:
    """Font subsets for scripts/activity.py, which runs in Actions without fontTools."""
    ACTIVITY_FONTS.mkdir(parents=True, exist_ok=True)
    for file, face, chars in [
        ("inter-display-digits.woff2", TITLE, "0123456789,."),
        ("inter-semibold.woff2", SEMI, UI_CHARS),
        ("inter-medium.woff2", MEDIUM, UI_CHARS),
    ]:
        path = ACTIVITY_FONTS / file
        path.write_bytes(FONTS.woff2(face, chars))
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size / 1024:.1f} KB")


def write(name: str, doc: Doc) -> None:
    ASSETS.mkdir(exist_ok=True)
    path = ASSETS / f"{name}.svg"
    path.write_text(doc.svg())
    print(f"{path.relative_to(ROOT)}  {path.stat().st_size / 1024:.1f} KB")


def main(selected: list[str]) -> None:
    for scene in selected or ["fonts", *SCENES, *PER_ITEM]:
        if scene == "fonts":
            activity_fonts()
            continue
        for theme in THEMES:
            if scene in SCENES:
                write(f"{scene}-{theme}", SCENES[scene](theme))
            else:
                make, items = PER_ITEM[scene]
                for key, item in items.items():
                    write(f"{scene}-{key}-{theme}", make(theme, item))


if __name__ == "__main__":
    main(sys.argv[1:])
