"""Unit tests for resourcery_ssg.opencode_runner — the shared opencode seam."""

import logging
import subprocess
from types import SimpleNamespace

import pytest

from resourcery_ssg.opencode_runner import (
    OPENCODE_TIMEOUT,
    check_outputs,
    resolve_opencode_bin,
    run_opencode,
)


class TestResolveOpencodeBin:
    @pytest.mark.unit
    def test_found_returns_resolved_path(self, monkeypatch):
        seen = []

        def fake_which(name):
            seen.append(name)
            return "/fake/opencode"

        monkeypatch.setattr(
            "resourcery_ssg.opencode_runner.shutil.which", fake_which
        )
        assert resolve_opencode_bin("opencode") == "/fake/opencode"
        assert seen == ["opencode"]

    @pytest.mark.unit
    def test_not_found_raises_exact_message(self, monkeypatch):
        monkeypatch.setattr(
            "resourcery_ssg.opencode_runner.shutil.which", lambda name: None
        )
        with pytest.raises(FileNotFoundError) as exc_info:
            resolve_opencode_bin("opencode")
        assert str(exc_info.value) == (
            "opencode binary 'opencode' not found on PATH. "
            "Use --opencode-path or set PATH accordingly."
        )


class TestRunOpencode:
    """Fake ``subprocess.run``; assert on the built command and kwargs."""

    @staticmethod
    def _install_fake(monkeypatch, result):
        calls = []

        def fake(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return result

        monkeypatch.setattr(
            "resourcery_ssg.opencode_runner.subprocess.run", fake
        )
        return calls

    @staticmethod
    def _call(work_dir, instruction_file, agent_def_file, **kwargs):
        return run_opencode(
            instruction_file,
            "gpt-4o",
            agent_def_file,
            work_dir,
            opencode_bin="/fake/opencode",
            **kwargs,
        )

    @pytest.mark.unit
    def test_builds_exact_argv(self, tmp_path, monkeypatch):
        calls = self._install_fake(
            monkeypatch, SimpleNamespace(returncode=0, stdout="", stderr="")
        )
        self._call(
            tmp_path / "work_dir",
            tmp_path / "instruction.md",
            tmp_path / "agent.md",
        )
        cmd, _ = calls[0]
        assert cmd == [
            "/fake/opencode",
            "run",
            "Execute the instructions in the attached file.",
            "--file", str(tmp_path / "instruction.md"),
            "--model", "gpt-4o",
            "--agent", str(tmp_path / "agent.md"),
            "--auto",
            "--dir", str(tmp_path / "work_dir"),
        ]

    @pytest.mark.unit
    def test_env_and_run_kwargs(self, tmp_path, monkeypatch):
        calls = self._install_fake(
            monkeypatch, SimpleNamespace(returncode=0, stdout="", stderr="")
        )
        self._call(tmp_path, tmp_path / "instruction.md", tmp_path / "agent.md")
        _, kwargs = calls[0]
        assert "OPENCODE_DISABLE_PROJECT_CONFIG" in kwargs["env"]
        assert kwargs["env"]["OPENCODE_DISABLE_PROJECT_CONFIG"] == "1"
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True

    @pytest.mark.unit
    def test_default_timeout_forwarded(self, tmp_path, monkeypatch):
        calls = self._install_fake(
            monkeypatch, SimpleNamespace(returncode=0, stdout="", stderr="")
        )
        self._call(tmp_path, tmp_path / "instruction.md", tmp_path / "agent.md")
        assert calls[0][1]["timeout"] == 300
        assert OPENCODE_TIMEOUT == 300

    @pytest.mark.unit
    def test_custom_timeout_forwarded(self, tmp_path, monkeypatch):
        calls = self._install_fake(
            monkeypatch, SimpleNamespace(returncode=0, stdout="", stderr="")
        )
        self._call(
            tmp_path,
            tmp_path / "instruction.md",
            tmp_path / "agent.md",
            timeout=42,
        )
        assert calls[0][1]["timeout"] == 42

    @pytest.mark.unit
    def test_success_returns_completed_process(self, tmp_path, monkeypatch):
        result = SimpleNamespace(returncode=0, stdout="", stderr="")
        self._install_fake(monkeypatch, result)
        returned = self._call(
            tmp_path, tmp_path / "instruction.md", tmp_path / "agent.md"
        )
        assert returned is result

    @pytest.mark.unit
    def test_nonzero_returncode_exact_message(self, tmp_path, monkeypatch):
        result = SimpleNamespace(returncode=1, stdout="out", stderr="err")
        self._install_fake(monkeypatch, result)
        with pytest.raises(RuntimeError) as exc_info:
            self._call(
                tmp_path, tmp_path / "instruction.md", tmp_path / "agent.md"
            )
        assert str(exc_info.value) == (
            "opencode process failed with exit code 1.\n"
            "stdout:\nout\n"
            "stderr:\nerr\n"
        )

    @pytest.mark.unit
    def test_nonzero_returncode_omits_empty_stdout_block(self, tmp_path, monkeypatch):
        result = SimpleNamespace(returncode=2, stdout="", stderr="boom")
        self._install_fake(monkeypatch, result)
        with pytest.raises(RuntimeError) as exc_info:
            self._call(
                tmp_path, tmp_path / "instruction.md", tmp_path / "agent.md"
            )
        assert "stdout:" not in str(exc_info.value)
        assert "stderr:\nboom\n" in str(exc_info.value)

    @pytest.mark.unit
    def test_timeout_translation_exact_message(self, tmp_path, monkeypatch):
        def fake(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

        monkeypatch.setattr(
            "resourcery_ssg.opencode_runner.subprocess.run", fake
        )
        with pytest.raises(RuntimeError) as exc_info:
            self._call(
                tmp_path, tmp_path / "instruction.md", tmp_path / "agent.md"
            )
        assert str(exc_info.value) == (
            "opencode process timed out after 300 seconds. "
            "Check the model and prompt, or increase the timeout."
        )

    @pytest.mark.unit
    def test_timeout_translation_reflects_custom_timeout(self, tmp_path, monkeypatch):
        def fake(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

        monkeypatch.setattr(
            "resourcery_ssg.opencode_runner.subprocess.run", fake
        )
        with pytest.raises(RuntimeError) as exc_info:
            self._call(
                tmp_path,
                tmp_path / "instruction.md",
                tmp_path / "agent.md",
                timeout=42,
            )
        assert str(exc_info.value) == (
            "opencode process timed out after 42 seconds. "
            "Check the model and prompt, or increase the timeout."
        )

    @pytest.mark.unit
    def test_emits_debug_records(self, tmp_path, monkeypatch, caplog):
        calls = self._install_fake(
            monkeypatch, SimpleNamespace(returncode=0, stdout="", stderr="")
        )
        instruction_file = tmp_path / "instruction.md"
        agent_def_file = tmp_path / "agent.md"
        work_dir = tmp_path / "work_dir"
        caplog.set_level(logging.DEBUG)

        self._call(work_dir, instruction_file, agent_def_file)

        cmd, _ = calls[0]
        runner_records = [
            r.message
            for r in caplog.records
            if r.levelno == logging.DEBUG
            and r.name == "resourcery_ssg.opencode_runner"
        ]
        assert f"  Command: {' '.join(cmd)}" in runner_records
        assert f"  Working directory: {work_dir}" in runner_records
        assert f"  Instruction file: {instruction_file}" in runner_records


class TestCheckOutputs:
    @pytest.mark.unit
    def test_all_present_returns_empty(self, tmp_path):
        work_dir = tmp_path / "work_dir"
        work_dir.mkdir()
        (work_dir / "links.json").write_text("{}", encoding="utf-8")
        assert check_outputs(work_dir, ["links.json"]) == []

    @pytest.mark.unit
    def test_returns_only_missing(self, tmp_path):
        work_dir = tmp_path / "work_dir"
        work_dir.mkdir()
        (work_dir / "links.json").write_text("{}", encoding="utf-8")
        (work_dir / "design.json").write_text("{}", encoding="utf-8")
        assert check_outputs(
            work_dir, ["links.json", "design.json", "site.config.json"]
        ) == ["site.config.json"]

    @pytest.mark.unit
    def test_empty_filenames_returns_empty(self, tmp_path):
        work_dir = tmp_path / "work_dir"
        work_dir.mkdir()
        assert check_outputs(work_dir, []) == []

    @pytest.mark.unit
    def test_str_work_dir_normalized(self, tmp_path):
        work_dir = tmp_path / "work_dir"
        work_dir.mkdir()
        assert check_outputs(str(work_dir), ["missing.json"]) == ["missing.json"]
