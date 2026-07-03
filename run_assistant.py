from __future__ import annotations

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from assistant_voice.command_router import CommandRouter
from assistant_voice.config import AssistantConfig
from assistant_voice.gemini_nlu import GeminiNLU
from assistant_voice.gui_tk import AssistantTkApp
from assistant_voice.scheduler import ReminderScheduler
from assistant_voice.storage import JsonTaskStorage
from assistant_voice.stt import SpeechToText
from assistant_voice.system_actions import SafeSystemActionExecutor
from assistant_voice.task_manager import TaskManager
from assistant_voice.tts import Speaker


def build_app() -> tuple[AssistantTkApp, ReminderScheduler]:
    config = AssistantConfig()

    # TTS local/offline
    speaker = Speaker()

    # Stockage local/offline des tâches
    storage = JsonTaskStorage(config.tasks_file)
    task_manager = TaskManager(storage)

    # NLU : Gemini si Internet disponible, parser local sinon
    nlu = GeminiNLU(config)

    # Actions système sécurisées
    system_executor = SafeSystemActionExecutor(config)

    # Routeur principal
    router = CommandRouter(
        nlu=nlu,
        task_manager=task_manager,
        system_executor=system_executor,
        speak=speaker.say_async,
        config=config,
    )

    # Service de rappels vocaux local/offline
    # Il déclenche :
    # 1. un rappel anticipé ;
    # 2. un rappel principal à l'heure exacte.
    reminder_scheduler = ReminderScheduler(
        task_manager=task_manager,
        speak=speaker.say_async,
        check_interval_seconds=config.reminder_check_seconds,
        user_display_name=config.user_display_name,
    )

    # Microphone
    try:
        stt = SpeechToText(language=config.language)
    except Exception as exc:
        print(f"[Microphone désactivé] {exc}")
        stt = None

    # Interface graphique
    app = AssistantTkApp(
        router,
        task_manager,
        reminder_scheduler,
        stt=stt,
        tts_controller=speaker,
    )

    speaker.say_async(
        f"Bonjour {config.user_display_name}, je suis {config.assistant_name}. "
        "Le service de rappel est actif. Dites mon nom pour me parler."
    )

    return app, reminder_scheduler


def main() -> None:
    app, reminder_scheduler = build_app()

    reminder_scheduler.start()

    try:
        app.mainloop()
    finally:
        reminder_scheduler.stop()


if __name__ == "__main__":
    main()
