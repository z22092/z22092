# /// script
# requires-python = ">=3.12"
# dependencies = ["fonttools==4.68.0", "brotli==1.2.1"]
# ///
"""Build the self-contained SVG assets for the GitHub profile README."""

import base64
import hashlib
import io
import urllib.error
import urllib.request

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
