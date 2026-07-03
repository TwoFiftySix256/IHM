from __future__ import annotations

from datetime import datetime, timedelta

from assistant_voice.storage import JsonTaskStorage
from assistant_voice.task_manager import TaskManager


def test_add_list_and_mark_done(tmp_path):
    manager = TaskManager(JsonTaskStorage(tmp_path / "tasks.json"))
    task = manager.add_task("envoyer un mail au professeur", datetime.now() + timedelta(minutes=1))

    tasks = manager.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].title == "envoyer un mail au professeur"

    manager.mark_done(task.task_id)
    assert manager.list_tasks()[0].status == "terminée"


def test_due_tasks_are_detected_once(tmp_path):
    manager = TaskManager(JsonTaskStorage(tmp_path / "tasks.json"))
    task = manager.add_task("préparer une interrogation", datetime.now() - timedelta(seconds=10))

    due = manager.due_tasks(grace_seconds=60)
    assert [item.task_id for item in due] == [task.task_id]

    manager.mark_reminded(task.task_id)
    assert manager.due_tasks(grace_seconds=60) == []
