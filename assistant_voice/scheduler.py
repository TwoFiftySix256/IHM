from __future__ import annotations

import os
import random
import threading
import time
from datetime import datetime
from typing import Callable

from .models import Task
from .task_manager import TaskManager


class ReminderScheduler:
    """
    Planificateur local/offline des rappels vocaux.

    Caractéristiques :
    - fonctionne en arrière-plan ;
    - ne dépend pas d'Internet ;
    - déclenche deux alertes :
        1. rappel anticipé ;
        2. rappel principal à l'heure exacte ;
    - utilise des phrases humaines et variées.
    """

    def __init__(
        self,
        task_manager: TaskManager,
        speak: Callable[[str], None],
        check_interval_seconds: int = 10,
        early_minutes: int | None = None,
        user_display_name: str = "Ingenieur Hermesse Mbizi",
    ):
        self.task_manager = task_manager
        self.speak = speak
        self.check_interval_seconds = max(3, int(check_interval_seconds))
        self.user_display_name = user_display_name

        if early_minutes is None:
            early_minutes = int(os.getenv("ASSISTANT_EARLY_REMINDER_MINUTES", "5"))

        self.early_minutes = max(1, int(early_minutes))

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run_loop,
            name="ReminderScheduler",
            daemon=True,
        )

        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.check_once()
            except Exception as exc:
                print(f"[ReminderScheduler] Erreur : {exc}")

            self._stop_event.wait(self.check_interval_seconds)

    def check_once(self) -> None:
        now = datetime.now()

        alerts = self.task_manager.due_alerts(
            now=now,
            early_minutes=self.early_minutes,
        )

        for alert_type, task in alerts:
            message = self._build_human_message(alert_type, task, now)

            try:
                self.speak(message)
                self.task_manager.mark_alert_sent(task.task_id, alert_type)
            except Exception as exc:
                print(f"[ReminderScheduler] Impossible d'annoncer le rappel : {exc}")

    def _build_human_message(self, alert_type: str, task: Task, now: datetime) -> str:
        title = self._clean_title(task.title)

        if alert_type == "early":
            remaining_minutes = max(1, int(round((task.due_at - now).total_seconds() / 60)))

            templates = [
                "{user}, petite parenthese : dans environ {minutes} minute(s), vous avez prevu de {task}.",
                "Au fait, {user}, il vous reste a peu pres {minutes} minute(s) avant de {task}.",
                "Je vous previens un peu a l'avance, {user} : bientot, vous devrez {task}.",
                "Juste pour vous aider a vous organiser : dans environ {minutes} minute(s), il y a {task}.",
                "{user}, votre tache approche. Vous avez bientot a {task}.",
            ]

            return random.choice(templates).format(
                user=self.user_display_name,
                minutes=remaining_minutes,
                task=title,
            )

        templates = [
            "{user}, c'est le moment. Vous aviez prevu de {task}.",
            "Je vous le rappelle maintenant, {user} : il est temps de {task}.",
            "Petit rappel : l'heure est arrivee pour {task}.",
            "Nous y sommes, {user}. Vous devez maintenant {task}.",
            "Je vous rappelle gentiment que c'est maintenant le moment de {task}.",
            "Voila, c'est l'heure prevue pour {task}.",
        ]

        return random.choice(templates).format(user=self.user_display_name, task=title)

    @staticmethod
    def _clean_title(title: str) -> str:
        title = (title or "").strip()

        if not title:
            return "faire votre tâche"

        lowered = title.lower()

        # Rend l'annonce plus naturelle.
        # Exemple : "envoyer un mail" reste correct après "de".
        if lowered.startswith(("envoyer", "préparer", "respecter", "étudier", "réviser", "appeler", "faire")):
            return title

        return title
class ReminderService(ReminderScheduler):
    """
    Compatibilité avec l'ancien nom utilisé par gui_tk.py.

    Ancien système :
        ReminderService(task_manager, speak, check_seconds, grace_seconds)

    Nouveau système :
        ReminderScheduler(task_manager, speak, check_interval_seconds, early_minutes)

    Cette classe permet aux anciens fichiers comme gui_tk.py de continuer à fonctionner.
    """

    def __init__(
        self,
        task_manager,
        speak,
        check_seconds: int = 10,
        grace_seconds: int = 60,
        early_minutes: int | None = None,
        user_display_name: str = "Ingenieur Hermesse Mbizi",
    ):
        super().__init__(
            task_manager=task_manager,
            speak=speak,
            check_interval_seconds=check_seconds,
            early_minutes=early_minutes,
            user_display_name=user_display_name,
        )

        self.grace_seconds = grace_seconds
