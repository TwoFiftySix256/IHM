from __future__ import annotations

import os
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import speech_recognition as sr

from assistant_voice.config import AssistantConfig


def main() -> None:
    config = AssistantConfig()

    profile_dir = config.data_dir / "voice_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    recognizer = sr.Recognizer()

    mic_index_raw = os.getenv("ASSISTANT_MIC_INDEX", "").strip()
    mic_index = int(mic_index_raw) if mic_index_raw.isdigit() else None

    phrases = [
        "Bonjour assistant, c'est moi qui parle.",
        "Je veux que tu reconnaisses uniquement ma voix.",
        "Assistant vocal, confirme que cette voix est autorisée.",
    ]

    print("Enregistrement du profil vocal.")
    print("Parlez clairement, dans un endroit calme.")
    print("Chaque enregistrement dure quelques secondes.")
    print()

    with sr.Microphone(device_index=mic_index) as source:
        print("Calibration du bruit ambiant...")
        recognizer.adjust_for_ambient_noise(source, duration=1)

        for i, phrase in enumerate(phrases, start=1):
            print("=" * 60)
            print(f"Échantillon {i}/3")
            print(f"Dites : {phrase}")
            time.sleep(1)

            audio = recognizer.listen(
                source,
                timeout=8,
                phrase_time_limit=6,
            )

            out_path = profile_dir / f"reference_{i}.wav"
            out_path.write_bytes(audio.get_wav_data())

            print(f"Enregistré : {out_path}")

    print()
    print("Profil vocal créé avec succès.")
    print(f"Dossier : {profile_dir}")


if __name__ == "__main__":
    main()