"""
JSON reading utilities for Resourcery.ssg.

Single home for all JSON loading across the CLI modules, with one error
semantics: raise with file-path context. ``load_json`` reads a JSON file and
``loads_json`` parses a JSON string; both raise ``JsonLoadError`` (a
``ValueError`` carrying the offending ``path`` and the underlying ``cause``)
on failure.
"""

import json
from pathlib import Path
from typing import Any, Optional


class JsonLoadError(ValueError):
    """Raised when JSON cannot be read or parsed.

    param: message — the human-readable error message naming the file or
        source and the underlying cause.
    param: path — the file that failed to load, or None when parsing a
        string without a file context.
    param: cause — the underlying exception (OSError or json.JSONDecodeError).

    Returns: None.
    """

    def __init__(self, message: str, *, path: Optional[Path] = None, cause: Optional[BaseException] = None):
        super().__init__(message)
        self.path = path
        self.cause = cause


def load_json(path) -> Any:
    """Load and parse a JSON file from disk.

    param: path — filesystem path to the JSON file.

    Returns: the parsed JSON value (dict, list, etc.).

    JsonLoadError: the file is missing, unreadable, or contains invalid JSON.
    """

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise JsonLoadError(
            f"Failed to parse JSON in {path}: {e}", path=Path(path), cause=e
        ) from e
    except OSError as e:
        raise JsonLoadError(
            f"Failed to read JSON from {path}: {e}", path=Path(path), cause=e
        ) from e


def loads_json(text: str, *, path: Optional[Path] = None, source: Optional[str] = None) -> Any:
    """Parse a JSON string.

    param: text — the JSON string to parse.
    param: path — optional file the text was read from; embedded in the
        error message and stored on the exception.
    param: source — optional non-file context label for the error message.

    Returns: the parsed JSON value (dict, list, etc.).

    JsonLoadError: the text is not valid JSON.
    """

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        if path is not None:
            msg = f"Failed to parse JSON in {path}: {e}"
        elif source is not None:
            msg = f"Failed to parse JSON from {source}: {e}"
        else:
            msg = f"Failed to parse JSON: {e}"
        raise JsonLoadError(
            msg, path=Path(path) if path is not None else None, cause=e
        ) from e
