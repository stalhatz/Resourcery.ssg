"""
Pure WCAG colour math and CSS unit parsing for Resourcery.ssg.

Stdlib-only module (zero project imports) holding the deterministic helpers
used by design checks: relative luminance and contrast ratio per WCAG 2.1,
plus ``parse_em`` for CSS ``em`` values. Moved verbatim from ``validate.py``
as part of the validate-module split.
"""

from typing import Optional


def _hex_to_srgb(hex_color: str) -> tuple:
    """Convert a six-digit hex color to sRGB (0-1) tuple.

    hex_color: e.g. "#2563eb".

    Returns: (r, g, b) tuple of floats 0-1.
    """

    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (r, g, b)


def _linearize(channel: float) -> float:
    """Linearize a single sRGB channel value for luminance calculation.

    channel: sRGB value 0-1.

    Returns: linearized value.
    """

    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """Compute WCAG 2.1 relative luminance from a hex color.

    hex_color: six-digit hex string e.g. "#ffffff".

    Returns: luminance value 0-1.
    """

    r, g, b = _hex_to_srgb(hex_color)
    r_lin = _linearize(r)
    g_lin = _linearize(g)
    b_lin = _linearize(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(color1: str, color2: str) -> float:
    """Compute WCAG 2.1 contrast ratio between two hex colors.

    color1: first hex color string.
    color2: second hex color string.

    Returns: contrast ratio (1.0–21.0). Higher = more contrast.
    """

    l1 = relative_luminance(color1)
    l2 = relative_luminance(color2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def parse_em(value: str) -> Optional[float]:
    """Parse a CSS em string to a float, stripping the unit.

    value: e.g. "0.05em", "0", "-0.03em".

    Returns: float value or None if unparseable.
    """

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        cleaned = value.strip().rstrip("em").rstrip("EM")
        return float(cleaned)
    except (ValueError, TypeError):
        return None
