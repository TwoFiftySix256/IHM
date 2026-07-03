from __future__ import annotations

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

from assistant_voice.config import AssistantConfig
from assistant_voice.stt import SpeechToText
from assistant_voice.tts import Speaker


def main() -> None:
    config = AssistantConfig()
    speaker = Speaker()

    print("[1/2] Test de la voix...")
    speaker.say("Oui, Ingenieur Hermes, la voix de Yollande fonctionne.")
    print("Si vous n'avez rien entendu, le probleme vient de la sortie audio ou du moteur TTS Windows.")

    print("\n[2/2] Test du micro...")
    print("Dites maintenant : Yollande, liste mes taches")

    try:
        stt = SpeechToText(language=config.language)
    except Exception as exc:
        print(f"Micro indisponible : {exc}")
        return

    result = stt.listen_once()
    if result.ok:
        print(f"Yollande a entendu : {result.text!r}")
    else:
        print(f"Erreur micro/STT : {result.error}")


if __name__ == "__main__":
    main()
