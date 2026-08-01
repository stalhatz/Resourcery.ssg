"""
Logging setup and helpers for Resourcery.ssg.

Single home for the stdlib ``logging`` wiring: level-string parsing, the
user-facing ``INFO_USER`` level (25), and ``setup_logging(config)`` — the
console/file handler layout with the uniform stream split
(DEBUG/INFO/INFO_USER → stdout, WARN/ERROR → stderr) and a per-run
timestamped log file. Entry points call ``setup_logging(config)`` exactly
once, immediately after ``load_resourcery_config()``; library functions
only ever call ``get_logger(__name__)`` and work with or without
``setup_logging`` (stdlib lastResort keeps WARNING+ visible by default).
"""

import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

# User-facing UX level: above INFO, below WARN.
INFO_USER = 25
logging.addLevelName(INFO_USER, "INFO_USER")

_STRUCTURED_FORMAT = (
    "%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d %(funcName)s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARN,
    "WARNING": logging.WARN,
    "ERROR": logging.ERROR,
}
_VALID_LEVELS = "DEBUG, INFO, WARN, ERROR"

# Root handlers created by setup_logging — removed on re-configuration.
_OWNED_HANDLERS: list = []


def parse_log_level(value: Optional[str]) -> int:
    """Parse a level string into its numeric stdlib logging level.

    param: value — level string (case-insensitive); ``WARNING`` is accepted
        as an alias for ``WARN``.

    Returns: the numeric logging level (10/20/30/40).

    ValueError: the value is None, empty, or not a recognised level.
    """
    if value is None or str(value).strip() == "":
        raise ValueError(
            f"Invalid log level: {value!r}. Valid levels: {_VALID_LEVELS}"
        )
    key = str(value).upper()
    if key not in _LEVELS:
        raise ValueError(
            f"Invalid log level: {value!r}. Valid levels: {_VALID_LEVELS}"
        )
    return _LEVELS[key]


def get_logger(name: str) -> logging.Logger:
    """Return a stdlib logger named after the calling module.

    param: name — logger name; pass ``__name__``.

    Returns: a stdlib Logger attached to the handlers configured by
        ``setup_logging`` (or stdlib defaults when unconfigured).
    """
    return logging.getLogger(name)


def log_user(msg: str) -> None:
    """Emit an ``INFO_USER`` record on the caller's module logger.

    param: msg — plain-text user-facing message (rendered without metadata).

    Returns: None.
    """
    try:
        name = sys._getframe(1).f_globals.get("__name__", "resourcery_ssg")
    except Exception:
        name = "resourcery_ssg"
    logging.getLogger(name).log(INFO_USER, msg)


@contextmanager
def log_timing(logger, message, level=logging.DEBUG):
    """Emit f"{message} completed in {elapsed:.1f}s" at *level* on block exit.

    Built on time.perf_counter with one-decimal rounding. The record is
    emitted from the finally block, so it fires on success *and* on
    exception paths (including SystemExit) — a failed phase still leaves
    its duration in the log file. Tests assert presence only, never values.

    param: logger — the module logger to emit on.
    param: message — the subject prefix, e.g. "Step 'validate'" or "Command";
        the helper appends " completed in {elapsed:.1f}s".
    param: level — record level; defaults to DEBUG (per-phase), entry
        points pass ``logging.INFO`` for the per-command record.

    Yields: None.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.log(level, f"{message} completed in {elapsed:.1f}s")


class _LevelRangeFilter(logging.Filter):
    """Pass records whose level is within [min_level, max_level)."""

    def __init__(self, min_level: int, max_level: Optional[int] = None) -> None:
        super().__init__()
        self._min_level = min_level
        self._max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < self._min_level:
            return False
        if self._max_level is not None and record.levelno >= self._max_level:
            return False
        return True


class _NoInfoUserFilter(logging.Filter):
    """Drop ``INFO_USER`` (level 25) records — they never reach log files."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno != INFO_USER


class _ConsoleFormatter(logging.Formatter):
    """Console formatter: plain text for INFO_USER, structured otherwise."""

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno == INFO_USER:
            return record.getMessage()
        return super().format(record)


class _StdStreamHandler(logging.StreamHandler):
    """StreamHandler whose stream is resolved at emit time.

    Resolves ``sys.stdout``/``sys.stderr`` lazily so records stay
    observable by pytest's ``capsys`` (which replaces those objects per
    test, after this handler may have been constructed) and by callers
    that redirect the streams mid-run.
    """

    def __init__(self, stream_name: str) -> None:
        logging.Handler.__init__(self)  # avoid binding sys.stderr
        self._stream_name = stream_name
        self.terminator = "\n"

    @property
    def stream(self):  # type: ignore[override]
        return sys.stdout if self._stream_name == "stdout" else sys.stderr

    def flush(self) -> None:
        self.acquire()
        try:
            stream = self.stream
            if stream and hasattr(stream, "flush"):
                stream.flush()
        finally:
            self.release()

    def close(self) -> None:
        """Close the handler without closing the underlying stream.

        The stream is sys.stdout/sys.stderr (or pytest's per-test capsys
        replacement) — owned by the process, not by the handler.
        """
        self.acquire()
        try:
            self.flush()
            self._closed = True
        finally:
            self.release()


def setup_logging(config) -> None:
    """Configure console + file logging from the ``logging`` config section.

    Idempotent: handlers attached by a previous ``setup_logging`` call are
    removed first (tracked via the module registry), so re-configuration
    never duplicates records. Foreign root handlers — e.g. pytest's caplog
    capture handler — are preserved, keeping record-level assertions usable
    in tests whose code paths call ``setup_logging`` themselves. Levels are
    parsed *before* any mutation so an invalid level leaves the previous
    configuration intact. Attaches:

    - a stdout handler for DEBUG/INFO/INFO_USER (records < WARN),
    - a stderr handler for WARN/ERROR (records >= WARN),
    - a per-run file handler ``logs_dir / resourcery-YYYYMMDD-HHMMSS.log``
      when ``logs_dir`` is set, at ``file_level``, hard-filtering
      ``INFO_USER`` records.

    param: config — the resolved config dict (read-only access to its
        ``logging`` section is enough; ``None`` yields defaults).

    Returns: None.

    ValueError: ``logging.level`` or ``logging.file_level`` is not a
        recognised level string.
    """
    section = (config or {}).get("logging", {}) if config else {}
    console_level = parse_log_level(section.get("level", "INFO"))
    file_level = parse_log_level(section.get("file_level", "DEBUG"))
    logs_dir = section.get("logs_dir")

    root = logging.getLogger()
    for handler in list(_OWNED_HANDLERS):
        root.removeHandler(handler)
        handler.close()
    _OWNED_HANDLERS.clear()
    root.setLevel(min(console_level, file_level))

    console_formatter = _ConsoleFormatter(_STRUCTURED_FORMAT, datefmt=_DATE_FORMAT)

    stdout_handler = _StdStreamHandler("stdout")
    stdout_handler.setLevel(console_level)
    stdout_handler.addFilter(_LevelRangeFilter(0, logging.WARN))
    stdout_handler.setFormatter(console_formatter)
    root.addHandler(stdout_handler)
    _OWNED_HANDLERS.append(stdout_handler)

    stderr_handler = _StdStreamHandler("stderr")
    stderr_handler.setLevel(max(console_level, logging.WARN))
    stderr_handler.addFilter(_LevelRangeFilter(logging.WARN))
    stderr_handler.setFormatter(console_formatter)
    root.addHandler(stderr_handler)
    _OWNED_HANDLERS.append(stderr_handler)

    if logs_dir:
        logs_path = Path(logs_dir)
        logs_path.mkdir(parents=True, exist_ok=True)
        file_name = f"resourcery-{datetime.now():%Y%m%d-%H%M%S}.log"
        file_handler = logging.FileHandler(logs_path / file_name, encoding="utf-8")
        file_handler.setLevel(file_level)
        file_handler.addFilter(_NoInfoUserFilter())
        file_handler.setFormatter(
            logging.Formatter(_STRUCTURED_FORMAT, datefmt=_DATE_FORMAT)
        )
        root.addHandler(file_handler)
        _OWNED_HANDLERS.append(file_handler)
