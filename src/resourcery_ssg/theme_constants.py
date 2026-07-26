"""
Single source of truth for heading style → font weight/spacing/download weights mapping.
Imported by both font_acquirer.py and build.py to ensure CSS and font downloads stay in sync.
"""

HEADING_STYLE_CONFIG = {
    "natural": {
        "heading_weight": 700,
        "letter_spacing": "0",
        "weights": [400, 600, 700],
    },
    "editorial": {
        "heading_weight": 800,
        "letter_spacing": "-0.03em",
        "weights": [400, 600, 800],
    },
    "elegant": {
        "heading_weight": 300,
        "letter_spacing": "0.07em",
        "weights": [300, 400, 600],
    },
    "uppercase": {
        "heading_weight": 700,
        "letter_spacing": "0.10em",
        "weights": [400, 600, 700],
    },
}

BODY_WEIGHTS = [400, 600]
DEFAULT_STYLE = "natural"


def get_heading_weight(heading_style: str) -> int:
    """Return the font weight integer for a given heading style name.

    heading_style: key into HEADING_STYLE_CONFIG; falls back to DEFAULT_STYLE if missing.

    Returns: integer font weight (e.g. 700).
    """

    return HEADING_STYLE_CONFIG.get(heading_style, HEADING_STYLE_CONFIG[DEFAULT_STYLE])[
        "heading_weight"
    ]


def get_heading_letter_spacing(heading_style: str) -> str:
    """Return the letter-spacing CSS value for a given heading style name.

    heading_style: key into HEADING_STYLE_CONFIG; falls back to DEFAULT_STYLE if missing.

    Returns: CSS letter-spacing string (e.g. '0', '-0.03em').
    """

    return HEADING_STYLE_CONFIG.get(heading_style, HEADING_STYLE_CONFIG[DEFAULT_STYLE])[
        "letter_spacing"
    ]


def get_required_weights(heading_style: str) -> list:
    """Return the sorted deduplicated list of font weights needed for a given heading_style.

    heading_style: key into HEADING_STYLE_CONFIG; falls back to DEFAULT_STYLE if missing.

    Returns: sorted list of integer weight values covering both body and heading.
    """

    style_weights = HEADING_STYLE_CONFIG.get(
        heading_style, HEADING_STYLE_CONFIG[DEFAULT_STYLE]
    )["weights"]
    return sorted(set(BODY_WEIGHTS + style_weights))


def weights_to_api_param(weights: list) -> str:
    """Convert a list of integer weights to a Google Fonts ital,wght parameter string.

    weights: list of integer font weights (e.g. [400, 600, 700]).

    Returns: semicolon-separated string of '0,<weight>' pairs.
    """

    return ";".join(f"0,{w}" for w in weights)
