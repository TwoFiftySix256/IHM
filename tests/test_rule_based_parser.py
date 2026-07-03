from __future__ import annotations

from assistant_voice.rule_based_parser import parse_basic_french_command


def test_parse_task_create():
    command = parse_basic_french_command("rappelle-moi d'envoyer un mail au professeur à 9 h")
    assert command.intent == "task_create"
    assert "mail" in command.task["title"]
    assert command.task["time"] == "09:00"


def test_parse_confirmation():
    assert parse_basic_french_command("oui").intent == "confirm"
    assert parse_basic_french_command("annule").intent == "cancel"


def test_parse_system_folder():
    command = parse_basic_french_command("crée un dossier documents test")
    assert command.intent == "system_create_folder"
    assert command.action["path"] == "documents test"
