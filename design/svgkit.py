"""Fonts, text measurement and SVG assembly shared by the artwork generator.

Text is set in Inter and JetBrains Mono (both SIL OFL). SVGs shown through an
<img> tag cannot load external files, so every document embeds a WOFF2 subset
containing only the glyphs it actually uses.
"""

from __future__ import annotations

import base64
import io
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import uharfbuzz as hb
from fontTools import subset as ftsubset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

DESIGN = Path(__file__).resolve().parent
CACHE = DESIGN / ".cache"

SOURCES = {
    "inter": ("Inter.ttf", "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf"),
    "mono": ("JetBrainsMono.ttf", "https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf"),
}

LAYOUT_FEATURES = ["kern", "liga", "calt", "ccmp", "locl", "mark", "mkmk", "case", "tnum"]


SANS_FALLBACK = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO_FALLBACK = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


@dataclass(frozen=True)
class Face:
    family: str
    wght: int
    opsz: int = 0

    @property
    def id(self) -> str:
        return f"{self.family[0]}{self.wght}{self.opsz or ''}"

    @property
    def css(self) -> str:
        """font-family value, with system fonts in case a viewer blocks embedded fonts."""
        return f"{self.id},{MONO_FALLBACK if self.family == 'mono' else SANS_FALLBACK}"


TITLE = Face("inter", 700, 32)
HEADLINE = Face("inter", 650, 28)
SEMI = Face("inter", 600, 18)
MEDIUM = Face("inter", 500, 16)
BODY = Face("inter", 400, 18)
MONO = Face("mono", 400)
MONO_BOLD = Face("mono", 700)


def _source(family: str) -> Path:
    name, url = SOURCES[family]
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-fsSL", "-o", str(path), url], check=True)
    return path


class FontStore:
    def __init__(self) -> None:
        self._bytes: dict[Face, bytes] = {}
        self._hb: dict[Face, tuple[hb.Font, int]] = {}
        self._subsets: dict[tuple[Face, str], str] = {}

    def static(self, face: Face) -> bytes:
        if face not in self._bytes:
            path = CACHE / "instances" / f"{face.id}.ttf"
            if not path.exists():
                axes = {"wght": face.wght}
                if face.family == "inter":
                    axes["opsz"] = face.opsz or 14
                font = instantiateVariableFont(TTFont(_source(face.family)), axes)
                path.parent.mkdir(parents=True, exist_ok=True)
                font.save(path)
            self._bytes[face] = path.read_bytes()
        return self._bytes[face]

    def _shaper(self, face: Face) -> tuple[hb.Font, int]:
        if face not in self._hb:
            hb_face = hb.Face(hb.Blob(self.static(face)))
            self._hb[face] = (hb.Font(hb_face), hb_face.upem)
        return self._hb[face]

    def measure(self, face: Face, text: str, size: float, spacing: float = 0.0) -> float:
        font, upem = self._shaper(face)
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf, {})
        advance = sum(pos.x_advance for pos in buf.glyph_positions)
        return advance / upem * size + spacing * len(text)

    def woff2(self, face: Face, chars: str) -> bytes:
        font = TTFont(io.BytesIO(self.static(face)))
        options = ftsubset.Options()
        options.flavor = "woff2"
        options.layout_features = LAYOUT_FEATURES
        options.hinting = False
        options.notdef_outline = True
        subsetter = ftsubset.Subsetter(options)
        subsetter.populate(text=chars)
        subsetter.subset(font)
        out = io.BytesIO()
        font.flavor = "woff2"
        font.save(out)
        return out.getvalue()

    def woff2_b64(self, face: Face, chars: str) -> str:
        key = (face, chars)
        if key not in self._subsets:
            self._subsets[key] = base64.b64encode(self.woff2(face, chars)).decode()
        return self._subsets[key]


FONTS = FontStore()


def num(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def measure(face: Face, text: str, size: float, spacing: float = 0.0) -> float:
    return FONTS.measure(face, text, size, spacing)


def wrap(face: Face, text: str, size: float, width: float) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and measure(face, candidate, size) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def superellipse(size: float = 100.0, exponent: float = 5.0, steps: int = 144) -> str:
    """Closed path for the continuous-corner shape Apple uses for app icons."""
    half = size / 2
    points = []
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        c, s = math.cos(angle), math.sin(angle)
        x = half + half * math.copysign(abs(c) ** (2 / exponent), c)
        y = half + half * math.copysign(abs(s) ** (2 / exponent), s)
        points.append(f"{num(x)} {num(y)}")
    return "M" + "L".join(points) + "Z"


def rounded_rect_path(x: float, y: float, w: float, h: float, r: float) -> str:
    k = 0.5523 * r
    return (
        f"M{num(x + r)} {num(y)}H{num(x + w - r)}"
        f"C{num(x + w - r + k)} {num(y)} {num(x + w)} {num(y + r - k)} {num(x + w)} {num(y + r)}"
        f"V{num(y + h - r)}"
        f"C{num(x + w)} {num(y + h - r + k)} {num(x + w - r + k)} {num(y + h)} {num(x + w - r)} {num(y + h)}"
        f"H{num(x + r)}"
        f"C{num(x + r - k)} {num(y + h)} {num(x)} {num(y + h - r + k)} {num(x)} {num(y + h - r)}"
        f"V{num(y + r)}"
        f"C{num(x)} {num(y + r - k)} {num(x + r - k)} {num(y)} {num(x + r)} {num(y)}Z"
    )


class Doc:
    """An SVG document that tracks which glyphs each font face needs."""

    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.height = height
        self.parts: list[str] = []
        self.defs: list[str] = []
        self.css: list[str] = []
        self.glyphs: dict[Face, set[str]] = {}
        self._defined: set[str] = set()

    def add(self, *chunks: str) -> None:
        self.parts.extend(chunks)

    def define(self, key: str, chunk: str) -> None:
        if key not in self._defined:
            self._defined.add(key)
            self.defs.append(chunk)

    def style(self, css: str) -> None:
        self.css.append(css)

    def uses(self, face: Face, text: str) -> None:
        self.glyphs.setdefault(face, set()).update(text)

    def text(
        self,
        x: float,
        y: float,
        text: str,
        face: Face,
        size: float,
        fill: str,
        anchor: str = "start",
        spacing: float = 0.0,
        opacity: float | None = None,
        attrs: str = "",
    ) -> str:
        self.uses(face, text)
        out = [f'<text x="{num(x)}" y="{num(y)}" font-family="{face.css}" font-size="{num(size)}" fill="{fill}"']
        if anchor != "start":
            out.append(f' text-anchor="{anchor}"')
        if spacing:
            out.append(f' letter-spacing="{num(spacing)}"')
        if opacity is not None:
            out.append(f' fill-opacity="{num(opacity)}"')
        if attrs:
            out.append(f" {attrs}")
        out.append(f">{esc(text)}</text>")
        return "".join(out)

    def runs(
        self,
        x: float,
        y: float,
        runs: list[tuple[str, Face, str]],
        size: float,
        anchor: str = "start",
        attrs: str = "",
    ) -> str:
        """One line of text made of differently styled runs that flow inline."""
        spans = []
        for text, face, fill in runs:
            self.uses(face, text)
            spans.append(f'<tspan font-family="{face.css}" fill="{fill}">{esc(text)}</tspan>')
        anchor_attr = f' text-anchor="{anchor}"' if anchor != "start" else ""
        extra = f" {attrs}" if attrs else ""
        return (
            f'<text x="{num(x)}" y="{num(y)}" font-size="{num(size)}" xml:space="preserve"{anchor_attr}{extra}>'
            + "".join(spans)
            + "</text>"
        )

    def svg(self) -> str:
        faces = "".join(
            f"@font-face{{font-family:{face.id};src:url(data:font/woff2;base64,"
            f"{FONTS.woff2_b64(face, ''.join(sorted(chars)))}) format('woff2')}}"
            for face, chars in sorted(self.glyphs.items(), key=lambda item: item[0].id)
        )
        style = f"<style>{faces}text{{font-kerning:normal}}{''.join(self.css)}</style>"
        defs = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{num(self.width)}" height="{num(self.height)}" '
            f'viewBox="0 0 {num(self.width)} {num(self.height)}" fill="none">'
            f"{style}{defs}{''.join(self.parts)}</svg>\n"
        )
