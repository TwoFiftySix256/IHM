from __future__ import annotations

import random
import re
import time as time_module
from datetime import date, datetime, time
from typing import Callable

from .config import AssistantConfig
from .gemini_nlu import GeminiNLU
from .models import ParsedCommand, Task
from .rule_based_parser import parse_time_parts
from .system_actions import ActionResult, SafeSystemActionExecutor
from .task_manager import TaskManager


class CommandRouter:
    """
    Routeur principal de l'assistant vocal.

    Il gère :
    - les tâches ;
    - les confirmations ;
    - les suppressions ;
    - les choix par position ;
    - les actions système ;
    - le dialogue en plusieurs étapes.
    """

    def __init__(
        self,
        nlu: GeminiNLU,
        task_manager: TaskManager,
        system_executor: SafeSystemActionExecutor,
        speak: Callable[[str], None] | None = None,
        config: AssistantConfig | None = None,
    ):
        self.config = config or AssistantConfig()
        self.nlu = nlu
        self.task_manager = task_manager
        self.system = system_executor
        self.speak = speak or (lambda text: None)
        self._activated_until = 0.0
        self._last_wake_prompt_at = 0.0

        # Action dangereuse en attente de confirmation
        self.pending: ParsedCommand | None = None

        # Choix en attente, par exemple plusieurs dossiers trouvés
        self.pending_choice: dict | None = None

        # Conversation en plusieurs étapes, par exemple création de tâche
        self.pending_conversation: dict | None = None

        # Dernière liste de tâches lue à l'utilisateur
        self.last_tasks: list[Task] = []

    def handle_text(self, text: str) -> str:
        """
        Point d'entrée principal appelé par l'interface.

        Correction importante :
        si une action est en attente de confirmation, on traite d'abord
        les réponses comme "oui", "ok", "confirme", "oui supprime"
        localement, avant d'envoyer la phrase à Gemini.
        """
        raw_text = (text or "").strip()
        raw_text, activated_by_name = self._strip_wake_word(raw_text)

        if activated_by_name:
            self._activated_until = time_module.monotonic() + self.config.activation_timeout_seconds

        if activated_by_name and not raw_text:
            return self._say(f"Oui, {self.config.user_display_name}, je vous ecoute.")

        if not raw_text:
            return self._say("Je n'ai rien entendu. Pouvez-vous répéter ?")

        # 1. Priorité absolue aux confirmations locales
        if (
            self.config.require_wake_word
            and not self._is_active()
            and not self.pending
            and not self.pending_choice
            and not self.pending_conversation
        ):
            message = "J'ai entendu, mais appelez-moi d'abord par mon nom : Yollande."
            now = time_module.monotonic()
            if now - self._last_wake_prompt_at >= 8:
                self._last_wake_prompt_at = now
                return self._say(message)
            return message

        if self.pending and self._looks_like_confirmation(raw_text):
            return self._confirm_pending()

        # 2. Priorité absolue aux annulations locales
        if self.pending and self._looks_like_cancel(raw_text):
            self._clear_pending_states()
            return self._say("D'accord, j'annule l'action.")

        # 3. Choix local : le premier, le deuxième, etc.
        if self.pending_choice:
            choice_position = self._extract_position(raw_text)
            if choice_position is not None:
                return self._choose_option(choice_position)

        # 4. Analyse normale par NLU / parser
        parsed = self.nlu.parse(raw_text)

        if parsed.intent == "confirm":
            return self._confirm_pending()

        if parsed.intent == "cancel":
            self._clear_pending_states()
            return self._say("D'accord, j'annule.")

        if parsed.intent == "choose_option":
            position = int(parsed.action.get("position") or 1)
            return self._choose_option(position)

        if self.pending_conversation:
            return self._continue_conversation(raw_text, parsed)

        if parsed.need_confirmation:
            return self._prepare_confirmation(parsed)

        return self._execute(parsed)

    def _confirm_pending(self) -> str:
        """
        Exécute l'action qui était en attente de confirmation.
        """
        if not self.pending:
            return self._say("Il n'y a aucune action en attente de confirmation.")

        command = self.pending
        self.pending = None

        return self._execute(command, confirmed=True)

    def _prepare_confirmation(self, parsed: ParsedCommand) -> str:
        """
        Prépare une action qui demande confirmation.
        Exemple : suppression d'une tâche ou suppression d'un fichier.
        """
        if parsed.intent == "task_delete":
            try:
                task = self._resolve_task(parsed.task)
                parsed.task["task_id"] = task.task_id
                parsed.task["title"] = task.title
                parsed.speak = f"Voulez-vous vraiment supprimer la tâche {task.title} ?"
            except Exception:
                parsed.speak = "Je peux supprimer cette tâche, mais confirmez-vous vraiment ?"

        if parsed.intent == "task_delete_all":
            count = len(self.task_manager.list_tasks())
            if count == 0:
                return self._say("Il n'y a aucune tâche à supprimer.")
            parsed.speak = f"J'ai trouvé {count} tâche(s). Voulez-vous vraiment tout supprimer ?"

        self.pending = parsed
        return self._say(parsed.speak or "Confirmez-vous cette action ?")

    def _execute(self, parsed: ParsedCommand, confirmed: bool = False) -> str:
        """
        Exécute réellement une commande déjà analysée.
        """
        try:
            intent = parsed.intent

            # -------------------------
            # Création de tâche en dialogue
            # -------------------------
            if intent == "task_create_partial":
                title = (parsed.task.get("title") or "").strip()
                day = parsed.task.get("date") or date.today().isoformat()

                self.pending_conversation = {
                    "kind": "create_task",
                    "title": title,
                    "date": day,
                }

                if not title:
                    return self._say("Bien sûr. Quel est le titre de la tâche ?")

                return self._say(f"D'accord pour {title}. À quelle heure dois-je vous rappeler ?")

            # -------------------------
            # Création directe d'une tâche
            # -------------------------
            if intent == "task_create":
                due_at = self._task_due_at(parsed.task)
                title = parsed.task.get("title") or "tâche sans titre"

                task = self.task_manager.add_task(title, due_at)

                return self._say(
                    self._variant(
                        [
                            f"C'est noté : {task.title}, à {task.due_at.strftime('%H h %M')}.",
                            f"Très bien, je vous rappellerai {task.title} à {task.due_at.strftime('%H h %M')}.",
                            f"Parfait, j'ai enregistré {task.title} pour {task.due_at.strftime('%H h %M')}.",
                        ]
                    )
                )

            # -------------------------
            # Liste des tâches
            # -------------------------
            if intent == "task_list":
                tasks = self.task_manager.list_tasks()
                self.last_tasks = tasks

                if not tasks:
                    return self._say("Aucune tâche enregistrée pour le moment.")

                message = "Voici vos tâches : " + "; ".join(
                    f"{i + 1}. {task.title}, {task.due_at.strftime('%H h %M')}, {task.status}"
                    for i, task in enumerate(tasks)
                )

                return self._say(message)

            # -------------------------
            # Marquer une tâche comme terminée
            # -------------------------
            if intent == "task_complete":
                task = self._resolve_task(parsed.task)
                task = self.task_manager.mark_done(task.task_id)
                self.last_tasks = self.task_manager.list_tasks()

                return self._say(f"Très bien, la tâche {task.title} est maintenant terminée.")

            # -------------------------
            # Supprimer toutes les tâches
            # -------------------------
            if intent == "task_delete_all":
                if not confirmed:
                    self.pending = parsed
                    count = len(self.task_manager.list_tasks())

                    if count == 0:
                        return self._say("Il n'y a aucune tâche à supprimer.")

                    return self._say(f"J'ai trouvé {count} tâche(s). Voulez-vous vraiment tout supprimer ?")

                count = self.task_manager.delete_all_tasks()

                if count == 0:
                    return self._say("Il n'y avait aucune tâche à supprimer.")

                self.last_tasks = []

                return self._say(f"C'est fait, j'ai supprimé {count} tâche(s).")

            # -------------------------
            # Supprimer une tâche précise
            # -------------------------
            if intent == "task_delete":
                if not confirmed:
                    return self._prepare_confirmation(parsed)

                task_id = parsed.task.get("task_id") or ""

                if not task_id:
                    task = self._resolve_task(parsed.task)
                    task_id = task.task_id

                task = self.task_manager.delete_task(task_id)
                self.last_tasks = self.task_manager.list_tasks()

                return self._say(f"C'est fait, la tâche {task.title} est supprimée.")

            # -------------------------
            # Créer un fichier
            # -------------------------
            if intent == "system_create_file":
                return self._say_result(
                    self.system.create_file(parsed.action.get("path", ""))
                )

            # -------------------------
            # Créer un dossier
            # -------------------------
            if intent == "system_create_folder":
                return self._say_result(
                    self.system.create_folder(parsed.action.get("path", ""))
                )

            # -------------------------
            # Ouvrir un dossier ou fichier
            # -------------------------
            if intent == "system_open_path":
                result = self.system.open_path(parsed.action.get("path", ""))

                if result.candidates:
                    self.pending_choice = {
                        "kind": "open_path",
                        "candidates": result.candidates,
                    }

                return self._say_result(result)
                        # -------------------------
            # Ouvrir plusieurs dossiers ou documents
            # -------------------------
            if intent == "system_open_many_paths":
                paths = parsed.action.get("paths") or []

                if isinstance(paths, str):
                    paths = [paths]

                return self._say_result(self.system.open_many_paths(paths))

            # -------------------------
            # Lancer une application
            # -------------------------
            if intent == "system_launch_app":
                return self._say_result(
                    self.system.launch_app(parsed.action.get("app", ""))
                )

            # -------------------------
            # Renommer un fichier ou dossier
            # -------------------------
            if intent == "system_rename_path":
                if not confirmed:
                    self.pending = parsed
                    return self._say(
                        parsed.speak or "Voulez-vous vraiment renommer cet élément ?"
                    )

                return self._say_result(
                    self.system.rename_path(
                        parsed.action.get("path", ""),
                        parsed.action.get("new_path", ""),
                    )
                )

            # -------------------------
            # Supprimer fichier ou dossier
            # -------------------------
            if intent == "system_delete_path":
                if not confirmed:
                    self.pending = parsed
                    return self._say(
                        parsed.speak or "Voulez-vous vraiment supprimer cet élément ?"
                    )

                return self._say_result(
                    self.system.delete_path(parsed.action.get("path", ""))
                )
                        # -------------------------
            # Fermer un dossier ou document
            # -------------------------
            if intent == "system_close_path":
                if not confirmed:
                    self.pending = parsed
                    return self._say(parsed.speak or "Voulez-vous vraiment fermer cet élément ?")

                return self._say_result(
                    self.system.close_path(parsed.action.get("path", ""))
                )

            # -------------------------
            # Fermer plusieurs dossiers ou documents
            # -------------------------
            if intent == "system_close_many_paths":
                if not confirmed:
                    self.pending = parsed
                    return self._say(parsed.speak or "Voulez-vous vraiment fermer ces éléments ?")

                paths = parsed.action.get("paths") or []

                if isinstance(paths, str):
                    paths = [paths]

                return self._say_result(self.system.close_many_paths(paths))

            # -------------------------
            # Fermer tout ce que l'assistant a ouvert
            # -------------------------
            if intent == "system_close_all_opened":
                if not confirmed:
                    self.pending = parsed
                    return self._say(
                        parsed.speak
                        or "Voulez-vous vraiment fermer tous les dossiers et documents que j'ai ouverts ?"
                    )

                return self._say_result(self.system.close_all_opened())

            # -------------------------
            # Discussion simple
            # -------------------------
            if intent == "chat":
                return self._say(
                    parsed.speak
                    or "Je suis là. Vous pouvez me dicter une tâche ou une action."
                )

            return self._say(
                parsed.speak
                or "Je n'ai pas compris la demande. Reformulez simplement, s'il vous plaît."
            )

        except Exception as exc:
            return self._say(f"Je n'ai pas pu exécuter l'action : {exc}")

    def _continue_conversation(self, text: str, parsed: ParsedCommand) -> str:
        """
        Continue une conversation commencée.
        Exemple :
        Utilisateur : ajoute une tâche
        Assistant : Quel est le titre ?
        Utilisateur : préparer l'interrogation
        Assistant : À quelle heure ?
        """
        state = self.pending_conversation or {}

        if state.get("kind") != "create_task":
            self.pending_conversation = None
            return self._execute(parsed)

        title = (state.get("title") or "").strip()
        day = state.get("date") or date.today().isoformat()
        parsed_time = parse_time_parts(text)

        if not title:
            if parsed.intent == "task_create":
                self.pending_conversation = None
                return self._execute(parsed)

            title = text.strip(" .,:;")

            self.pending_conversation = {
                "kind": "create_task",
                "title": title,
                "date": day,
            }

            return self._say(f"D'accord pour {title}. À quelle heure dois-je vous rappeler ?")

        if parsed_time:
            hour, minute = parsed_time
            self.pending_conversation = None

            due_at = datetime.combine(
                date.fromisoformat(day),
                time(hour=hour, minute=minute),
            )

            task = self.task_manager.add_task(title, due_at)

            return self._say(
                f"Parfait, j'ai enregistré {task.title} pour {task.due_at.strftime('%H h %M')}."
            )

        if parsed.intent == "task_create":
            self.pending_conversation = None
            return self._execute(parsed)

        return self._say(
            "J'ai le titre, mais il me manque l'heure. Dites par exemple : à 18 h 30."
        )

    def _choose_option(self, position: int) -> str:
        """
        Choisit une option proposée précédemment.
        Exemple : ouvrir le premier dossier trouvé.
        """
        if not self.pending_choice:
            return self._say("Je n'ai aucun choix en attente.")

        candidates = self.pending_choice.get("candidates") or []

        if position < 1 or position > len(candidates):
            return self._say("Je ne trouve pas ce numéro dans les choix proposés.")

        selected = candidates[position - 1]
        kind = self.pending_choice.get("kind")
        self.pending_choice = None

        if kind == "open_path":
            if hasattr(self.system, "open_exact_path"):
                return self._say_result(self.system.open_exact_path(selected))

            return self._say_result(self.system.open_path(selected))

        return self._say("Je ne sais pas quoi faire avec ce choix.")

    def _resolve_task(self, task_data: dict) -> Task:
        """
        Trouve une tâche soit par :
        - task_id ;
        - position : première, deuxième, etc. ;
        - titre approximatif.
        """
        if task_data.get("task_id"):
            return self.task_manager._find(task_data["task_id"])

        if task_data.get("position"):
            position = int(task_data["position"])

            if self.last_tasks and 1 <= position <= len(self.last_tasks):
                return self.last_tasks[position - 1]

            return self.task_manager.get_by_position(position)

        return self.task_manager._find(task_data.get("title") or "")

    def _task_due_at(self, task_data: dict) -> datetime:
        raw_date = task_data.get("date") or date.today().isoformat()
        raw_time = task_data.get("time") or "09:00"

        parsed_date = date.fromisoformat(raw_date)
        hour, minute = [int(part) for part in raw_time.split(":", 1)]

        return datetime.combine(parsed_date, time(hour=hour, minute=minute))

    def _say_result(self, result: ActionResult) -> str:
        prefix = "" if result.ok else "Attention. "
        return self._say(prefix + result.message)

    def _clear_pending_states(self) -> None:
        self.pending = None
        self.pending_choice = None
        self.pending_conversation = None

    @staticmethod
    def _looks_like_confirmation(text: str) -> bool:
        lowered = (text or "").lower().strip(" .,!?:;")

        confirmations = {
            "oui",
            "oui oui",
            "ok",
            "okay",
            "d'accord",
            "dac",
            "vas-y",
            "vas y",
            "confirme",
            "je confirme",
            "c'est bon",
            "cest bon",
            "allez",
            "continue",
            "supprime",
            "supprime la",
            "supprime le",
            "supprime les",
            "oui supprime",
            "oui supprime la",
            "oui supprime le",
            "oui supprime les",
            "oui vas-y",
            "oui vas y",
        }

        return (
            lowered in confirmations
            or lowered.startswith("oui ")
            or lowered.startswith("ok ")
            or lowered.startswith("confirme ")
        )

    @staticmethod
    def _looks_like_cancel(text: str) -> bool:
        lowered = (text or "").lower().strip(" .,!?:;")

        cancellations = {
            "non",
            "non non",
            "annule",
            "annuler",
            "stop",
            "laisse",
            "laisse tomber",
            "pas maintenant",
            "ne supprime pas",
            "n'efface pas",
            "ne fais pas",
        }

        return lowered in cancellations

    @staticmethod
    def _extract_position(text: str) -> int | None:
        lowered = (text or "").lower().strip(" .,!?:;")

        positions = {
            "le premier": 1,
            "la première": 1,
            "premier": 1,
            "première": 1,
            "un": 1,
            "une": 1,
            "le deuxième": 2,
            "la deuxième": 2,
            "deuxième": 2,
            "deuxieme": 2,
            "deux": 2,
            "le troisième": 3,
            "la troisième": 3,
            "troisième": 3,
            "troisieme": 3,
            "trois": 3,
            "le quatrième": 4,
            "la quatrième": 4,
            "quatrième": 4,
            "quatrieme": 4,
            "quatre": 4,
            "le cinquième": 5,
            "la cinquième": 5,
            "cinquième": 5,
            "cinquieme": 5,
            "cinq": 5,
        }

        if lowered in positions:
            return positions[lowered]

        for key, value in positions.items():
            if key in lowered:
                return value

        return None

    def _say(self, message: str) -> str:
        self.speak(message)
        return message

    @staticmethod
    def _variant(options: list[str]) -> str:
        return random.choice(options)

    def _is_active(self) -> bool:
        if not self.config.require_wake_word:
            return True
        return time_module.monotonic() <= self._activated_until

    def _strip_wake_word(self, text: str) -> tuple[str, bool]:
        cleaned = (text or "").strip()

        for wake_word in self.config.wake_words:
            wake_word = wake_word.strip()
            if not wake_word:
                continue

            pattern = re.compile(rf"\b{re.escape(wake_word)}\b[,:\s-]*", re.IGNORECASE)
            match = pattern.search(cleaned)

            if match:
                without_name = (cleaned[: match.start()] + cleaned[match.end() :]).strip()
                return without_name, True

        return cleaned, False
