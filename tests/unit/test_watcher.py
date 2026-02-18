"""Tests for the File Watcher module."""

from __future__ import annotations

import time
from pathlib import Path

from retrai.watcher import FileWatcher, _should_ignore

# ---------------------------------------------------------------------------
# _should_ignore
# ---------------------------------------------------------------------------


class TestShouldIgnore:
    def test_git_dir(self):
        assert _should_ignore(Path(".git/objects/abc")) is True

    def test_node_modules(self):
        assert _should_ignore(Path("node_modules/pkg/index.js")) is True

    def test_pycache(self):
        assert _should_ignore(Path("src/__pycache__/mod.cpython-312.pyc")) is True

    def test_pyc_extension(self):
        assert _should_ignore(Path("module.pyc")) is True

    def test_normal_file(self):
        assert _should_ignore(Path("src/main.py")) is False

    def test_normal_nested(self):
        assert _should_ignore(Path("src/utils/helpers.ts")) is False

    def test_retrai_dir(self):
        assert _should_ignore(Path(".retrai/memory.json")) is True


# ---------------------------------------------------------------------------
# FileWatcher snapshot and change detection
# ---------------------------------------------------------------------------


class TestFileWatcher:
    def test_snapshot(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "util.py").write_text("pass")

        watcher = FileWatcher(cwd=str(tmp_path))
        snap = watcher._take_snapshot()
        assert "main.py" in snap
        assert "sub/util.py" in snap

    def test_snapshot_ignores_git(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main")
        (tmp_path / "main.py").write_text("code")

        watcher = FileWatcher(cwd=str(tmp_path))
        snap = watcher._take_snapshot()
        assert "main.py" in snap
        assert ".git/HEAD" not in snap

    def test_detect_new_file(self, tmp_path):
        (tmp_path / "existing.py").write_text("old")
        watcher = FileWatcher(cwd=str(tmp_path))
        old_snap = watcher._take_snapshot()

        (tmp_path / "new_file.py").write_text("new")
        new_snap = watcher._take_snapshot()

        changes = watcher._detect_changes(old_snap, new_snap)
        assert "new_file.py" in changes

    def test_detect_modified_file(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("v1")
        watcher = FileWatcher(cwd=str(tmp_path))
        old_snap = watcher._take_snapshot()

        time.sleep(0.05)
        f.write_text("v2")
        new_snap = watcher._take_snapshot()

        changes = watcher._detect_changes(old_snap, new_snap)
        assert "main.py" in changes

    def test_detect_deleted_file(self, tmp_path):
        f = tmp_path / "to_delete.py"
        f.write_text("bye")
        watcher = FileWatcher(cwd=str(tmp_path))
        old_snap = watcher._take_snapshot()

        f.unlink()
        new_snap = watcher._take_snapshot()

        changes = watcher._detect_changes(old_snap, new_snap)
        assert "to_delete.py" in changes

    def test_no_changes(self, tmp_path):
        (tmp_path / "stable.py").write_text("const")
        watcher = FileWatcher(cwd=str(tmp_path))
        snap = watcher._take_snapshot()
        changes = watcher._detect_changes(snap, snap)
        assert changes == []

    def test_stop(self, tmp_path):
        watcher = FileWatcher(cwd=str(tmp_path))
        assert watcher._running is False
        watcher.stop()
        assert watcher._running is False

    def test_debounce_config(self, tmp_path):
        watcher = FileWatcher(
            cwd=str(tmp_path),
            debounce_ms=2000,
        )
        assert watcher.debounce_seconds == 2.0
