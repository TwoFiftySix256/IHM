from __future__ import annotations

from pathlib import Path

from assistant_voice.command_router import CommandRouter
from assistant_voice.config import AssistantConfig
from assistant_voice.rule_based_parser import parse_basic_french_command
from assistant_voice.storage import JsonTaskStorage
from assistant_voice.system_actions import SafeSystemActionExecutor
from assistant_voice.task_manager import TaskManager


class LocalNlu:
    def parse(self, text: str):
        return parse_basic_french_command(text)


def _router(tmp_path: Path) -> tuple[CommandRouter, list[str]]:
    config = AssistantConfig(
        data_dir=tmp_path / "data",
        allowed_roots=[tmp_path],
        require_wake_word=True,
        activation_timeout_seconds=45,
    )
    spoken: list[str] = []
    manager = TaskManager(JsonTaskStorage(tmp_path / "tasks.json"))
    router = CommandRouter(
        nlu=LocalNlu(),
        task_manager=manager,
        system_executor=SafeSystemActionExecutor(config),
        speak=spoken.append,
        config=config,
    )
    return router, spoken


def test_wake_word_is_required(tmp_path):
    router, spoken = _router(tmp_path)

    response = router.handle_text("liste mes taches")

    assert response == "J'ai entendu, mais appelez-moi d'abord par mon nom : Yollande."
    assert spoken == [response]


def test_wake_word_activates_command(tmp_path):
    router, spoken = _router(tmp_path)

    response = router.handle_text("Yollande, liste mes taches")

    assert "Aucune" in response
    assert spoken == [response]


def test_common_wake_word_transcription_variants(tmp_path):
    router, spoken = _router(tmp_path)

    response = router.handle_text("Yolande, liste mes taches")

    assert "Aucune" in response
    assert spoken == [response]


def test_active_window_accepts_follow_up(tmp_path):
    router, spoken = _router(tmp_path)

    router.handle_text("Yollande")
    response = router.handle_text("liste mes taches")

    assert "Aucune" in response
    assert spoken[-1] == response
