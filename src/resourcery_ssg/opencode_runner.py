"""
Shared opencode subprocess runner for Resourcery.ssg.

Single home for how opencode is invoked: binary resolution, the
``opencode run`` command build, environment setup, and the
returncode/timeout error translation. Orchestrators resolve the binary
with ``resolve_opencode_bin`` and run the agent via ``run_opencode``;
``check_outputs`` answers which expected output files are absent from a
working directory (callers keep their own error-message formatting).
"""

import os
import shutil
import subprocess
from pathlib import Path

from resourcery_ssg.logutil import get_logger

logger = get_logger(__name__)

# Default timeout for the opencode subprocess (seconds)
OPENCODE_TIMEOUT = 300


def resolve_opencode_bin(opencode_bin: str) -> str:
    """Resolve the opencode binary to an absolute path.

    param: opencode_bin — path or name of the opencode binary.

    Returns: the resolved binary path.

    FileNotFoundError: the binary is not found on PATH.
    """
    opencode_bin_resolved = shutil.which(opencode_bin)
    if opencode_bin_resolved is None:
        raise FileNotFoundError(
            f"opencode binary '{opencode_bin}' not found on PATH. "
            f"Use --opencode-path or set PATH accordingly."
        )
    return opencode_bin_resolved


def run_opencode(
    instruction_file,
    model,
    agent_def_file,
    work_dir,
    *,
    opencode_bin: str,
    timeout: int = OPENCODE_TIMEOUT,
) -> subprocess.CompletedProcess:
    """Invoke opencode as an agent in a working directory.

    Builds the ``opencode run`` command, sets ``OPENCODE_DISABLE_PROJECT_CONFIG``,
    runs the subprocess, and translates non-zero exits and timeouts into
    ``RuntimeError``.

    param: instruction_file — path to the instruction markdown file.
    param: model — LLM model identifier (e.g. "gpt-4o").
    param: agent_def_file — path to the agent definition file.
    param: work_dir — the working directory opencode runs in.
    param: opencode_bin — the resolved binary path as returned by
        ``resolve_opencode_bin``.
    param: timeout — subprocess timeout in seconds; defaults to
        ``OPENCODE_TIMEOUT`` (300).

    Returns: the CompletedProcess of the successful run.

    RuntimeError: the process exits non-zero, or it times out.
    """
    # Prepare environment
    env = os.environ.copy()
    env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"

    cmd = [
        opencode_bin,
        "run",
        "Execute the instructions in the attached file.",
        "--file", str(instruction_file),
        "--model", model,
        "--agent", str(agent_def_file),
        "--auto",
        "--dir", str(work_dir),
    ]

    logger.debug(f"  Command: {' '.join(cmd)}")
    logger.debug(f"  Working directory: {work_dir}")
    logger.debug(f"  Instruction file: {instruction_file}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"opencode process timed out after {timeout} seconds. "
            f"Check the model and prompt, or increase the timeout."
        )

    if result.returncode != 0:
        error_msg = (
            f"opencode process failed with exit code {result.returncode}.\n"
        )
        if result.stdout:
            error_msg += f"stdout:\n{result.stdout}\n"
        if result.stderr:
            error_msg += f"stderr:\n{result.stderr}\n"
        raise RuntimeError(error_msg)

    return result


def check_outputs(work_dir, filenames) -> list[str]:
    """List the filenames missing from a working directory.

    param: work_dir — the working directory to check (path-like).
    param: filenames — iterable of filenames to look for.

    Returns: the filenames from *filenames* that do not exist under
        *work_dir* (empty list when all present).
    """
    work_dir = Path(work_dir)
    return [f for f in filenames if not (work_dir / f).exists()]
