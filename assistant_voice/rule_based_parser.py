from __future__ import annotations

import re
from datetime import date, timedelta

from .models import ParsedCommand


TIME_PATTERNS = [
    re.compile(r"(?:à|a|vers|pour)\s*(\d{1,2})\s*h(?:eures?)?\s*(\d{1,2})?", re.IGNORECASE),
    re.compile(r"(?:à|a|vers|pour)\s*(\d{1,2})\s*[:.]\s*(\d{1,2})", re.IGNORECASE),
    re.compile(r"^\s*(\d{1,2})\s*h(?:eures?)?\s*(\d{1,2})?\s*$", re.IGNORECASE),
    re.compile(r"^\s*(\d{1,2})\s*[:.]\s*(\d{1,2})\s*$", re.IGNORECASE),
]

ORDINALS = {
    "premier": 1,
    "première": 1,
    "1er": 1,
    "1ère": 1,
    "un": 1,
    "une": 1,
    "deuxième": 2,
    "deuxieme": 2,
    "second": 2,
    "seconde": 2,
    "deux": 2,
    "troisième": 3,
    "troisieme": 3,
    "trois": 3,
    "quatrième": 4,
    "quatrieme": 4,
    "quatre": 4,
    "cinquième": 5,
    "cinquieme": 5,
    "cinq": 5,
}


def parse_time_parts(text: str) -> tuple[int, int] | None:
    for pattern in TIME_PATTERNS:
        match = pattern.search(text or "")
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)

            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute

    return None


def _parse_date(text: str) -> str:
    lowered = (text or "").lower()
    today = date.today()

    if "après-demain" in lowered or "apres-demain" in lowered:
        return (today + timedelta(days=2)).isoformat()

    if "demain" in lowered:
        return (today + timedelta(days=1)).isoformat()

    return today.isoformat()


def _parse_position(text: str) -> int | None:
    lowered = (text or "").lower()

    for word, number in ORDINALS.items():
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            return number

    match = re.search(r"\b(\d+)\b", lowered)
    if match:
        return int(match.group(1))

    return None


def _clean_text(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .,:;!?")


def _clean_target(text: str) -> str:
    cleaned = _clean_text(text)

    cleaned = re.sub(r"^(ouvre|ouvrir|cherche|trouve|affiche)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(le|la|les|un|une|mon|ma|mes)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(dossier|fichier|répertoire|repertoire)\s+", "", cleaned, flags=re.IGNORECASE)

    return cleaned.strip(" .,:;!?")


def _remove_task_prefix(text: str) -> str:
    title = _clean_text(text)

    title = re.sub(r"^(supprime|supprimer|efface|effacer|retire|retirer)\s+", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^(la|le|les|ma|mon|mes|une|un)\s+", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^(tâche|tache|rappel)\s+", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^(numéro|numero)\s+", "", title, flags=re.IGNORECASE)

    return title.strip(" .,:;!?")


def parse_basic_french_command(text: str) -> ParsedCommand:
    original = _clean_text(text)
    lowered = original.lower()

    if not lowered:
        return ParsedCommand(intent="unknown", speak="Je n'ai rien entendu.")

    # Confirmation
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
        "oui supprime",
        "oui vas-y",
        "oui vas y",
        "supprime",
    }

    if lowered in confirmations or lowered.startswith("oui "):
        return ParsedCommand(intent="confirm", speak="Très bien, je confirme.")

    # Annulation
    cancellations = {
        "non",
        "annule",
        "annuler",
        "stop",
        "laisse tomber",
        "pas maintenant",
        "ne fais pas",
        "ne supprime pas",
    }

    if lowered in cancellations:
        return ParsedCommand(intent="cancel", speak="D'accord, j'annule.")

    # Choix : le premier, le deuxième...
    if lowered.startswith(
        (
            "le premier",
            "la première",
            "premier",
            "première",
            "le deuxième",
            "la deuxième",
            "deuxième",
            "deuxieme",
            "le troisième",
            "la troisième",
            "troisième",
            "troisieme",
        )
    ):
        return ParsedCommand(
            intent="choose_option",
            action={"position": _parse_position(original) or 1},
            speak="D'accord, je prends ce choix.",
        )

    # Liste des tâches
    if (
        ("liste" in lowered or "affiche" in lowered or "montre" in lowered)
        and ("tâche" in lowered or "tache" in lowered)
    ) or "mes tâches" in lowered or "mes taches" in lowered:
        return ParsedCommand(intent="task_list", speak="Voici les tâches enregistrées.")

    # Supprimer toutes les tâches
    if any(word in lowered for word in ["supprime", "supprimer", "efface", "effacer", "retire", "retirer", "vide"]):
        if any(
            expr in lowered
            for expr in [
                "toutes les tâches",
                "toutes les taches",
                "mes tâches",
                "mes taches",
                "les tâches enregistrées",
                "les taches enregistrées",
                "les taches enregistrees",
                "tout",
            ]
        ):
            return ParsedCommand(
                intent="task_delete_all",
                need_confirmation=True,
                speak="Voulez-vous vraiment supprimer toutes les tâches enregistrées ?",
            )

    # Supprimer une tâche
    if any(word in lowered for word in ["supprime", "supprimer", "efface", "effacer", "retire", "retirer"]):
        position = _parse_position(original)
        title = _remove_task_prefix(original)

        task: dict = {}

        if position:
            task["position"] = position

        if title and title.lower() not in ORDINALS and not title.isdigit():
            task["title"] = title

        return ParsedCommand(
            intent="task_delete",
            task=task,
            need_confirmation=True,
            speak="Je peux supprimer cette tâche. Confirmez-vous ?",
        )

    # Marquer une tâche terminée
    if any(word in lowered for word in ["terminée", "terminee", "terminer", "fini", "faite", "marque"]):
        if "tâche" in lowered or "tache" in lowered or "rappel" in lowered or _parse_position(original):
            position = _parse_position(original)
            title = _remove_task_prefix(original)

            task: dict = {}

            if position:
                task["position"] = position

            if title and title.lower() not in ORDINALS and not title.isdigit():
                task["title"] = title

            return ParsedCommand(
                intent="task_complete",
                task=task,
                speak="Très bien, je marque la tâche comme terminée.",
            )

    # Créer une tâche en une phrase
    if any(
        trigger in lowered
        for trigger in [
            "rappelle-moi",
            "rappelle moi",
            "ajoute",
            "ajoute une tâche",
            "ajoute une tache",
            "crée une tâche",
            "cree une tache",
            "nouvelle tâche",
            "nouvelle tache",
        ]
    ):
        parsed_time = parse_time_parts(original)

        title = original
        title = re.sub(r"rappelle[- ]moi\s*(de|d')?", "", title, flags=re.IGNORECASE)
        title = re.sub(r"ajoute\s*(une\s*)?(tâche|tache)?", "", title, flags=re.IGNORECASE)
        title = re.sub(r"crée\s*(une\s*)?(tâche|tache)?", "", title, flags=re.IGNORECASE)
        title = re.sub(r"cree\s*(une\s*)?(tâche|tache)?", "", title, flags=re.IGNORECASE)
        title = re.sub(r"nouvelle\s*(tâche|tache)", "", title, flags=re.IGNORECASE)
        title = re.sub(r"(?:à|a|vers|pour)\s*\d{1,2}\s*(h|:|\.)\s*\d{0,2}.*", "", title, flags=re.IGNORECASE)
        title = title.strip(" .,:;!?")

        if parsed_time:
            hour, minute = parsed_time

            return ParsedCommand(
                intent="task_create",
                task={
                    "title": title or "tâche sans titre",
                    "date": _parse_date(original),
                    "time": f"{hour:02d}:{minute:02d}",
                },
                speak=f"C'est noté : {title}, à {hour:02d} h {minute:02d}.",
            )

        if title:
            return ParsedCommand(
                intent="task_create_partial",
                task={"title": title, "date": _parse_date(original)},
                speak=f"D'accord pour {title}. À quelle heure dois-je vous rappeler ?",
            )

        return ParsedCommand(
            intent="task_create_partial",
            task={},
            speak="Bien sûr. Quel est le titre de la tâche ?",
        )

    # Créer un dossier
    if "crée un dossier" in lowered or "cree un dossier" in lowered:
        name = re.sub(r".*dossier", "", original, flags=re.IGNORECASE).strip(" .,:;!?")

        return ParsedCommand(
            intent="system_create_folder",
            action={"path": name},
            speak=f"Je crée le dossier {name}.",
        )

    # Créer un fichier
    if "crée un fichier" in lowered or "cree un fichier" in lowered:
        name = re.sub(r".*fichier", "", original, flags=re.IGNORECASE).strip(" .,:;!?")

        return ParsedCommand(
            intent="system_create_file",
            action={"path": name},
            speak=f"Je crée le fichier {name}.",
        )

    # Ouvrir un dossier ou fichier
        # Ouvrir un ou plusieurs dossiers/documents
    if lowered.startswith("ouvre") or lowered.startswith("ouvrir"):
        target = _clean_target(original)

        if target.lower() in {"internet", "google", "chrome", "navigateur", "edge", "microsoft edge"}:
            app = "chrome" if target.lower() in {"internet", "google", "chrome", "navigateur"} else "edge"
            return ParsedCommand(
                intent="system_launch_app",
                action={"app": app},
                speak="D'accord, j'ouvre Internet.",
            )

        # Plusieurs éléments : "ouvre documents et téléchargements"
        parts = re.split(r"\s+et\s+|,| puis | ensuite ", target, flags=re.IGNORECASE)
        parts = [p.strip(" .,:;!?") for p in parts if p.strip(" .,:;!?")]

        if len(parts) > 1:
            return ParsedCommand(
                intent="system_open_many_paths",
                action={"paths": parts},
                speak="D'accord, j'ouvre ces éléments.",
            )

        return ParsedCommand(
            intent="system_open_path",
            action={"path": target},
            speak=f"D'accord, je cherche {target}.",
        )
        # Fermer tous les éléments ouverts par l'assistant
    if any(lowered.startswith(x) for x in ["ferme tout", "fermer tout", "ferme tous", "fermer tous"]):
        return ParsedCommand(
            intent="system_close_all_opened",
            action={},
            need_confirmation=True,
            speak="Voulez-vous vraiment fermer tous les dossiers et documents que j'ai ouverts ?",
        )

    # Fermer un ou plusieurs dossiers/documents
    if lowered.startswith("ferme") or lowered.startswith("fermer"):
        target = _clean_target(original)

        parts = re.split(r"\s+et\s+|,| puis | ensuite ", target, flags=re.IGNORECASE)
        parts = [p.strip(" .,:;!?") for p in parts if p.strip(" .,:;!?")]

        if len(parts) > 1:
            return ParsedCommand(
                intent="system_close_many_paths",
                action={"paths": parts},
                need_confirmation=True,
                speak="Voulez-vous vraiment fermer ces éléments ?",
            )

        return ParsedCommand(
            intent="system_close_path",
            action={"path": target},
            need_confirmation=True,
            speak=f"Voulez-vous vraiment fermer {target} ?",
        )

    # Lancer une application
    if lowered.startswith("lance"):
        app = re.sub(r"^lance", "", original, flags=re.IGNORECASE).strip(" .,:;!?")

        if app.lower() in {"internet", "google", "navigateur"}:
            app = "chrome"

        return ParsedCommand(
            intent="system_launch_app",
            action={"app": app},
            speak=f"D'accord, je lance {app}.",
        )

    # Rien trouvé localement : on laisse Gemini gérer.
    return ParsedCommand(
        intent="unknown",
        speak="Je n'ai pas encore compris cette demande.",
    )