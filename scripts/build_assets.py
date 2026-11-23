# /// script
# requires-python = ">=3.12"
# dependencies = ["fonttools==4.68.0", "brotli==1.2.1"]
# [tool.uv]
# exclude-newer = "2026-11-23T00:00:00Z"
# ///
"""Build the self-contained SVG assets for the GitHub profile README."""

import base64
import hashlib
import html
import argparse
import io
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont


class BuildError(Exception):
    """Raised when an asset cannot be built reproducibly."""


PALETTE = {
    "bg": "#0e0607",
    "line": "#3b1d20",
    "main": "#e8112d",
    "main2": "#ff7a1a",
    "alt": "#ff9a3c",
    "dim": "#937f80",
    "text": "#f4e8e8",
}

FONT_SOURCES = {
    "display": (
        "https://raw.githubusercontent.com/rsms/inter/v4.1/docs/font-files/InterDisplay-Black.woff2",
        "05650cb83c70fda2a465eade0c0a1a6c25d37ec49df3cd74b7e564683f9729f1",
    ),
    "mono": (
        "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/v2.304/fonts/ttf/JetBrainsMono-Regular.ttf",
        "a0bf60ef0f83c5ed4d7a75d45838548b1f6873372dfac88f71804491898d138f",
    ),
}


def load_font(kind: str) -> bytes:
    """Download a pinned font and verify its sha256 (checked on every call)."""
    url, expected = FONT_SOURCES[kind]
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = resp.read()
    except (urllib.error.URLError, OSError) as exc:
        raise BuildError(f"could not download {kind} font from {url}: {exc}") from exc
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise BuildError(f"{kind} font sha256 mismatch: expected {expected}, got {actual}")
    return data


def subset_woff2(font: bytes, text: str) -> bytes:
    """Subset a font to the characters in `text` and return it as WOFF2."""
    source = TTFont(io.BytesIO(font), recalcTimestamp=False)
    cmap = source.getBestCmap()
    missing = sorted({c for c in text if ord(c) not in cmap})
    if missing:
        raise BuildError(f"glyphs missing from font: {missing}")
    options = subset.Options(flavor="woff2")
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text)
    subsetter.subset(source)
    source.flavor = "woff2"
    out = io.BytesIO()
    source.save(out)
    return out.getvalue()


def font_face(family: str, woff2: bytes) -> str:
    b64 = base64.b64encode(woff2).decode("ascii")
    return f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{b64}) format('woff2');}}"


def format_stars(n: int) -> str:
    if n < 1000:
        return str(n)
    return f"{n / 1000:.1f}".removesuffix(".0") + "k"


DISPLAY_FAMILY = 'font-family="zDisplay, sans-serif"'
MONO_FAMILY = 'font-family="zMono, monospace"'

BANNER_TITLE = "Jefferson. Software engineer, AI-assisted engineering."
BANNER_NAME = "JEFFERSON"
BANNER_ID = ("ID//", "Z22092")
BANNER_SECTOR = ("SECTOR//", "LATAM.FIN")
BANNER_STATUS = ("STATUS//", "ONLINE")
BANNER_ROLE = ("SOFTWARE ENGINEER ", "/", " AI-ASSISTED ENGINEERING")

HAZARD_BOX = (600, 176, 190, 18)
# The mockup used a 16-unit pattern rotated 45 degrees: horizontal period 16*sqrt(2).
HAZARD_PERIOD = round(16 * math.sqrt(2), 2)
HAZARD_STRIPE = round(8 * math.sqrt(2), 2)


def _hazard_stripes() -> str:
    """Slanted 45-degree stripes; one extra period on the left so a one-period drift loops."""
    x0, y0, w, h = HAZARD_BOX
    shapes = []
    n = math.ceil((w + h + 2 * HAZARD_PERIOD) / HAZARD_PERIOD)
    for i in range(n + 1):
        x = round(x0 - h - HAZARD_PERIOD + i * HAZARD_PERIOD, 2)
        pts = [(x + h, y0), (x + h + HAZARD_STRIPE, y0), (x + HAZARD_STRIPE, y0 + h), (x, y0 + h)]
        shapes.append('<path d="M' + " L".join(f"{round(px, 2):g} {py:g}" for px, py in pts) + ' Z"/>')
    return "".join(shapes)


def _font_css(display: bytes, display_text: str, mono: bytes, mono_text: str) -> str:
    """The two embedded @font-face rules, each subset to the text it renders."""
    return font_face("zDisplay", subset_woff2(display, display_text)) + font_face(
        "zMono", subset_woff2(mono, mono_text)
    )


def render_banner(display: bytes, mono: bytes) -> str:
    """Return the complete HUD banner as a self-contained SVG document."""
    p = PALETTE
    display_text = BANNER_NAME
    mono_text = "".join(BANNER_ID + BANNER_SECTOR + BANNER_STATUS + BANNER_ROLE)
    style = (
        _font_css(display, display_text, mono, mono_text)
        + "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}"
        + f"@keyframes drift{{from{{transform:translateX(0)}}to{{transform:translateX({HAZARD_PERIOD:g}px)}}}}"
        + ".online{animation:pulse 2s ease-in-out infinite}"
        + ".hazard{animation:drift 2s linear infinite}"
        + "@media (prefers-reduced-motion: reduce){.online,.hazard{animation:none}}"
    )
    hx, hy, hw, hh = HAZARD_BOX
    bars = "".join(
        f'<rect x="{640 + i * 5}" y="60" width="{1 + (i * 7) % 3}" height="70"/>' for i in range(28)
    )
    role_a, role_sep, role_b = BANNER_ROLE
    return f"""<svg viewBox="0 0 820 220" width="100%" xmlns="http://www.w3.org/2000/svg">
<title>{BANNER_TITLE}</title>
<style>{style}</style>
<defs>
 <linearGradient id="g" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{p['main']}"/><stop offset="1" stop-color="{p['main2']}"/></linearGradient>
 <clipPath id="hz"><rect x="{hx}" y="{hy}" width="{hw}" height="{hh}"/></clipPath>
</defs>
<path d="M0 0 H790 L820 30 V220 H30 L0 190 Z" fill="{p['bg']}" stroke="{p['line']}"/>
<g {MONO_FAMILY} font-size="10.5" letter-spacing="2" fill="{p['dim']}">
 <text x="34" y="30">{BANNER_ID[0]}<tspan fill="{p['alt']}">{BANNER_ID[1]}</tspan></text>
 <text x="170" y="30">{BANNER_SECTOR[0]}<tspan fill="{p['alt']}">{BANNER_SECTOR[1]}</tspan></text>
 <text x="360" y="30">{BANNER_STATUS[0]}<tspan class="online" fill="{p['main']}">{BANNER_STATUS[1]}</tspan></text>
</g>
<text x="30" y="122" {DISPLAY_FAMILY} font-weight="900" font-size="92" letter-spacing="-2" fill="url(#g)">{BANNER_NAME}</text>
<rect x="34" y="140" width="6" height="18" fill="{p['alt']}"/>
<text x="50" y="155" {MONO_FAMILY} font-size="14" letter-spacing="2" fill="{p['text']}">{role_a}<tspan fill="{p['dim']}">{role_sep}</tspan>{role_b}</text>
<g clip-path="url(#hz)"><g class="hazard" fill="{p['alt']}">{_hazard_stripes()}</g></g>
<g fill="{p['main2']}" opacity=".7">{bars}</g>
<g stroke="{p['alt']}" stroke-width="2" fill="none"><path d="M14 172 V206 H48"/><path d="M806 48 V14 H772"/></g>
</svg>
"""


CARD_TITLE = "taskiq-postgresql: broker, result backend and schedule source for taskiq, all in one PostgreSQL database."
CARD_KICKER = ("MODULE//", "OSS.01")
CARD_NAME = "TASKIQ-POSTGRESQL"
CARD_LINES = ("Broker, result backend and schedule source for taskiq,", "all in one PostgreSQL database.")
CARD_STAR = "\u2605"
CARD_SEP = "\u25a0"
CARD_DIGITS = "0123456789.k"


def render_card(stars: int, version: str, display: bytes, mono: bytes) -> str:
    """Return the taskiq-postgresql card as a self-contained SVG document."""
    p = PALETTE
    count = format_stars(stars)
    ver = html.escape("V" + version.upper())
    display_text = CARD_NAME + CARD_STAR
    mono_text = "".join(CARD_KICKER + CARD_LINES) + "PY " + CARD_SEP + " " + ver + " PYPI" + CARD_DIGITS + count
    style = _font_css(display, display_text, mono, mono_text)
    sep = f'<tspan fill="{p["alt"]}">{CARD_SEP}</tspan>'
    # white-space:pre on the root keeps the double spaces around the separators.
    return f"""<svg viewBox="0 0 560 124" width="560" xmlns="http://www.w3.org/2000/svg" style="white-space:pre">
<title>{CARD_TITLE}</title>
<style>{style}</style>
<defs><linearGradient id="c" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{p['main']}"/><stop offset="1" stop-color="{p['main2']}"/></linearGradient></defs>
<path d="M0 0 H540 L560 20 V124 H20 L0 104 Z" fill="{p['bg']}" stroke="{p['line']}"/>
<rect x="0" y="0" width="5" height="124" fill="{p['main']}"/>
<text x="24" y="26" {MONO_FAMILY} font-size="10" letter-spacing="2" fill="{p['dim']}">{CARD_KICKER[0]}<tspan fill="{p['alt']}">{CARD_KICKER[1]}</tspan></text>
<text x="24" y="54" {DISPLAY_FAMILY} font-weight="900" font-size="24" fill="url(#c)">{CARD_NAME}</text>
<text x="24" y="78" {MONO_FAMILY} font-size="12" fill="{p['text']}">{CARD_LINES[0]}</text>
<text x="24" y="94" {MONO_FAMILY} font-size="12" fill="{p['text']}">{CARD_LINES[1]}</text>
<text x="24" y="114" {MONO_FAMILY} font-size="11" letter-spacing="1.5" fill="{p['dim']}">PY {sep}  <tspan {DISPLAY_FAMILY}>{CARD_STAR}</tspan> {count}  {sep}  {ver}  {sep}  PYPI</text>
</svg>
"""


REPO_STARS_URL = "https://api.github.com/repos/z22092/taskiq-postgresql"
PYPI_URL = "https://pypi.org/pypi/taskiq-postgresql/json"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "assets"


def _get_json(url: str, headers: dict[str, str]) -> dict:
    """GET a URL and decode its JSON body; any failure becomes a BuildError."""
    request = urllib.request.Request(url, headers={"User-Agent": "z22092-profile-builder", **headers})
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise BuildError(f"could not fetch {url}: {exc}") from exc
    if not isinstance(data, dict):
        raise BuildError(f"unexpected JSON from {url}: expected an object")
    return data


def fetch_stars(token: str | None) -> int:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    stars = _get_json(REPO_STARS_URL, headers).get("stargazers_count")
    if not isinstance(stars, int) or isinstance(stars, bool):
        raise BuildError(f"no integer stargazers_count in response from {REPO_STARS_URL}")
    return stars


def fetch_version() -> str:
    info = _get_json(PYPI_URL, {})
    version = info.get("info", {}).get("version") if isinstance(info.get("info"), dict) else None
    if not isinstance(version, str) or not version:
        raise BuildError(f"no info.version in response from {PYPI_URL}")
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the profile README SVG assets.")
    parser.add_argument("--stars", type=int, help="star count (default: fetched from GitHub)")
    parser.add_argument("--version", help="package version (default: fetched from PyPI)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    args = parser.parse_args(argv)
    try:
        stars = args.stars if args.stars is not None else fetch_stars(os.environ.get("GITHUB_TOKEN"))
        version = args.version if args.version is not None else fetch_version()
        display = load_font("display")
        mono = load_font("mono")
        files = {
            "banner.svg": render_banner(display, mono),
            "taskiq-postgresql.svg": render_card(stars, version, display, mono),
        }
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (args.out / name).write_bytes(content.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
