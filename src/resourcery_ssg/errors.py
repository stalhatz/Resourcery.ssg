"""
Process-level error type for Resourcery.ssg.

Single home for the exception raised by library functions on fatal,
process-aborting failures. Library functions print the human-readable
message (same text, same stream as always) and then raise
``ResourceryError`` carrying the identical message; entry points catch it
and call ``sys.exit(1)``. The module imports nothing to avoid any circular
import risk.
"""


class ResourceryError(Exception):
    """Raised by library functions on fatal, process-aborting failures.

    param: message — the human-readable error message (same text the
        library prints immediately before raising).

    Returns: None.
    """
