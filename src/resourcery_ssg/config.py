"""
Config loading, merging, and resolution for Resourcery.ssg.

Provides a single `load_resourcery_config()` function that implements the
priority chain: CLI overrides > environment / .env > user config > committed config.
All ${VAR} references are resolved against os.environ first, then vars sections.
"""

import os
import re
from pathlib import Path
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Dict, Optional, Union

import yaml

_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_env(path: Optional[Path] = None) -> None:
    """Load a .env file into ``os.environ``.

    Uses ``python-dotenv`` if available; otherwise does a simple manual parse.

    Args:
        path: Path to the .env file. Defaults to ``Path.cwd() / ".env"``.
    """
    env_path = path or (Path.cwd() / ".env")
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
        return
    except ImportError:
        pass

    # Manual fallback parser
    text = env_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def _resolve_var(value: str, env: Dict[str, str], vars_dict: Dict[str, str]) -> str:
    """Resolve all ``${VAR}`` references in a string.

    Resolution order: environment dict → *vars_dict* → leave as-is.

    Args:
        value: A string that may contain ``${VAR}`` placeholders.
        env: Environment-variable lookup dict (usually ``os.environ``).
        vars_dict: The merged ``vars:`` section from config files.

    Returns:
        String with all placeholders replaced.
    """

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in env:
            return env[var_name]
        if var_name in vars_dict:
            return vars_dict[var_name]
        return match.group(0)  # leave unmodified if not found

    return _VAR_PATTERN.sub(_replacer, value)


def _resolve_all(
    obj: Any, env: Dict[str, str], vars_dict: Dict[str, str]
) -> Any:
    """Recursively walk a nested dict/list tree and resolve ${VAR} in all strings.

    Args:
        obj: A nested structure of dicts, lists, and strings.
        env: Environment-variable lookup dict.
        vars_dict: The merged ``vars:`` section.

    Returns:
        A new structure with all strings resolved.
    """
    if isinstance(obj, str):
        return _resolve_var(obj, env, vars_dict)
    if isinstance(obj, dict):
        return {k: _resolve_all(v, env, vars_dict) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_all(item, env, vars_dict) for item in obj]
    return obj


def _deep_merge(base: Dict, overlay: Dict) -> Dict:
    """Deep-merge *overlay* into *base* (both dicts)."""
    result = deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


def load_resourcery_config(
    config_path: Optional[Union[str, Path]] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Load, merge, resolve, and return the full configuration.

    Resolution order (highest to lowest priority):
      1. *overrides* dict (typically parsed CLI args)
      2. Environment variables (including those from a ``.env`` file)
      3. User config file at *config_path* (if provided)
      4. Committed ``config.yaml`` bundled with the package

    Args:
        config_path: Optional path to a user-supplied YAML config file.
        overrides: Optional flat dict like ``{"build.output": "/tmp/out"}``.
            Dotted keys are expanded into nested dicts before overlaying.

    Returns:
        A frozen (read-only) mapping with per-command sections resolved to
        absolute :class:`Path` objects where appropriate.

    Raises:
        ConfigError: If the committed config cannot be found or parsed.
    """
    # 1. Load .env file from CWD
    _load_env()

    # 2. Build environment lookup (os.environ values only — .env was loaded above)
    env = dict(os.environ)

    # 3. Locate the committed config.yaml bundled with this package
    committed_cfg_path = Path(__file__).resolve().parent / "config.yaml"
    if not committed_cfg_path.exists():
        raise ConfigError(
            f"Committed config.yaml not found at {committed_cfg_path}. "
            f"Ensure the package is correctly installed."
        )

    with open(committed_cfg_path, "r", encoding="utf-8") as f:
        committed: Dict = yaml.safe_load(f) or {}

    # 4. If a user config was provided, load and deep-merge
    if config_path is not None:
        user_path = Path(config_path)
        if not user_path.exists():
            raise ConfigError(f"User config file not found: {user_path}")
        with open(user_path, "r", encoding="utf-8") as f:
            user_cfg: Dict = yaml.safe_load(f) or {}
        merged = _deep_merge(committed, user_cfg)
    else:
        merged = deepcopy(committed)

    # 5. Build the vars dict: committed vars + user vars (user overrides committed)
    vars_dict = dict(merged.get("vars", {}))

    # 6. Resolve ALL ${VAR} references (vars + per-command sections)
    #    First, resolve the vars dict itself (so STATIC_DIR-based vars like
    #    FONTS_DIR get resolved)
    vars_dict = _resolve_all(vars_dict, env, vars_dict)

    #    Now resolve the entire config (excluding vars, which we already resolved)
    resolved = {"vars": vars_dict}
    for section_name in merged:
        if section_name == "vars":
            continue
        resolved[section_name] = _resolve_all(
            merged[section_name], env, vars_dict
        )

    # 7. Apply CLI overrides on top of resolved values
    if overrides:
        overrides_expanded = _expand_dotted_overrides(overrides)
        resolved = _deep_merge(resolved, overrides_expanded)

    # 8. Resolve all paths relative to CWD and convert to Path where they look
    #    like paths (string values containing '/' or ending in a known pattern)
    resolved = _resolve_paths(resolved)

    # 9. Return a frozen mapping to prevent mutation
    return _freeze(resolved)


# ---------------------------------------------------------------------------
# Internal helpers for overrides and path resolution
# ---------------------------------------------------------------------------


def _expand_dotted_overrides(flat: Dict[str, Any]) -> Dict[str, Any]:
    """Expand a flat dict with dotted keys into a nested dict.

    Example:
        ``{"build.output": "/tmp/out"}`` → ``{"build": {"output": "/tmp/out"}}``
    """
    result: Dict = {}
    for key, value in flat.items():
        parts = key.split(".")
        target = result
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        # Only set if value is not None (allows CLI default None to be skipped)
        if value is not None:
            target[parts[-1]] = value
    return result


# Keys whose string values must never be converted to Path objects.
# These are non-path strings like model names, binary names, etc.
_NON_PATH_KEYS = frozenset({
    "model",
    "opencode_bin",
    "agent",
})


def _resolve_paths(obj: Any, exclude_keys: frozenset = _NON_PATH_KEYS) -> Any:
    """Walk a nested structure converting path-like strings to absolute Paths.

    A string is considered path-like if it starts with ``.`` or ``/`` or contains
    a path separator. Simple alphanumeric names are left as-is.

    Keys in *exclude_keys* are never converted — their string values are kept
    as plain strings even if they look path-like (e.g. model names like
    ``opencode-go/deepseek-v4-flash`` contain ``/`` but are not filesystem paths).
    """
    if isinstance(obj, dict):
        return {
            k: v if k in exclude_keys else _resolve_paths(v, exclude_keys)
            for k, v in obj.items()
        }
    if isinstance(obj, str):
        # Treat as path if it looks like one
        if obj.startswith((".", "/")) or "/" in obj or "\\" in obj:
            return Path(obj).resolve()
        return obj
    if isinstance(obj, list):
        return [_resolve_paths(item, exclude_keys) for item in obj]
    return obj


def _freeze(obj: Any) -> Any:
    """Recursively freeze dicts into read-only MappingProxyType."""
    if isinstance(obj, dict):
        return MappingProxyType({k: _freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(_freeze(item) for item in obj)
    return obj
