from __future__ import annotations

from pathlib import Path

import pytest

from assistant_voice.config import AssistantConfig
from assistant_voice.system_actions import SafeSystemActionExecutor


def _config(tmp_path: Path) -> AssistantConfig:
    return AssistantConfig(data_dir=tmp_path / "data", allowed_roots=[tmp_path])


def test_create_rename_and_delete_file(tmp_path):
    executor = SafeSystemActionExecutor(_config(tmp_path))

    created = executor.create_file(str(tmp_path / "a.txt"), "bonjour")
    assert created.ok
    assert (tmp_path / "a.txt").exists()

    renamed = executor.rename_path(str(tmp_path / "a.txt"), str(tmp_path / "b.txt"))
    assert renamed.ok
    assert (tmp_path / "b.txt").exists()

    deleted = executor.delete_path(str(tmp_path / "b.txt"))
    assert deleted.ok
    assert not (tmp_path / "b.txt").exists()
    assert Path(deleted.path).exists()


def test_path_outside_allowed_roots_is_refused(tmp_path):
    executor = SafeSystemActionExecutor(_config(tmp_path))
    with pytest.raises(PermissionError):
        executor.create_file("/tmp/not_allowed_file.txt")
