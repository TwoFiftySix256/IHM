from __future__ import annotations

import json
import re
from datetime import date, datetime

from .config import AssistantConfig
from .models import ParsedCommand
from .rule_based_parser import parse_basic_french_command


SYSTEM_PROMPT = """
Tu es le cerveau de Yollande, une assistante vocale Python pour PC.
Ton utilisateur principal est l'Ingenieur Hermesse Mbizi.
Tu dois comprendre la phrase de l'utilisateur et retourner uniquement un JSON.

Intentions autorisées :
- task_create
- task_create_partial
- task_list
- task_complete
- task_delete
- task_delete_all
- system_create_file
- system_create_folder
- system_open_path
- system_rename_path
- system_delete_path
- system_launch_app
- choose_option
- confirm
- cancel
- chat
- unknown

Format strict :
{
  "intent": "...",
  "speak": "réponse orale courte, naturelle et humaine",
  "need_confirmation": false,
  "task": {
    "title": "",
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "task_id": "",
    "position": 1
  },
  "action": {
    "path": "",
    "new_path": "",
    "app": "",
    "position": 1
  }
}

Règles :
- Pour supprimer une tâche ou un fichier, need_confirmation doit être true.
- Pour supprimer toutes les tâches, intent = task_delete_all et need_confirmation = true.
- Pour "oui", "ok", "confirme", intent = confirm.
- Pour "non", "annule", intent = cancel.
- La réponse orale doit être courte, fluide, chaleureuse et naturelle.
- Évite le style robotique, les listes et les annonces trop rigides.
- Adresse-toi à l'Ingenieur Hermesse Mbizi de façon professionnelle, sans exagérer.
- Ne retourne jamais de texte hors JSON.
""".strip()


LOCAL_FIRST_INTENTS = {
    "confirm",
    "cancel",
    "choose_option",
    "task_list",
    "task_create",
    "task_create_partial",
    "task_complete",
    "task_delete",
    "task_delete_all",
    "system_create_file",
    "system_create_folder",
    "system_open_path",
    "system_launch_app",
}


class GeminiNLU:
    def __init__(self, config: AssistantConfig):
        self.config = config
        self._client = None

        if config.offline_mode:
            return

        if config.gemini_api_key:
            try:
                from google import genai

                self._client = genai.Client(api_key=config.gemini_api_key)
            except Exception:
                self._client = None

    def parse(self, user_text: str) -> ParsedCommand:
        text = (user_text or "").strip()

        if not text:
            return ParsedCommand(intent="unknown", speak="Je n'ai rien entendu.")

        # PRIORITÉ AUX RÈGLES LOCALES.
        # C'est ça qui empêche l'assistant de répondre comme un robot à tout.
        local = parse_basic_french_command(text)

        if local.intent in LOCAL_FIRST_INTENTS:
            return local

        # Si Gemini n'est pas disponible, on retourne le résultat local.
        if self._client is None:
            return local

        today = date.today().isoformat()
        now = datetime.now().strftime("%H:%M")

        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Date du jour : {today}\n"
            f"Heure actuelle : {now}\n"
            f"Phrase utilisateur : {text!r}\n"
            "JSON :"
        )

        try:
            response = self._client.models.generate_content(
                model=self.config.gemini_model,
                contents=prompt,
            )

            raw_text = getattr(response, "text", "") or ""
            data = self._extract_json(raw_text)
            parsed = ParsedCommand.from_dict(data)

            # Si Gemini répond chat/unknown mais que le local avait compris quelque chose,
            # on garde le local.
            if parsed.intent in {"chat", "unknown"} and local.intent not in {"chat", "unknown"}:
                return local

            return parsed

        except Exception:
            return local

    @staticmethod
    def _extract_json(raw_text: str) -> dict:
        cleaned = (raw_text or "").strip()

        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            cleaned = match.group(0)

        return json.loads(cleaned)
