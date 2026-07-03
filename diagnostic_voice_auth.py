from __future__ import annotations

import os
import tempfile

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import speech_recognition as sr

from assistant_voice.config import AssistantConfig
from assistant_voice.speaker_verifier import SpeakerVerifier


def main() -> None:
    config = AssistantConfig()
    verifier = SpeakerVerifier.from_config(config)

    print("Diagnostic de reconnaissance du locuteur")
    print("Profil vocal trouvé :", verifier.has_profile())
    print("Dossier profil :", verifier.profile_dir)
    print()

    recognizer = sr.Recognizer()

    mic_index_raw = os.getenv("ASSISTANT_MIC_INDEX", "").strip()
    mic_index = int(mic_index_raw) if mic_index_raw.isdigit() else None

    with sr.Microphone(device_index=mic_index) as source:
        print("Calibration du bruit ambiant...")
        recognizer.adjust_for_ambient_noise(source, duration=1)

        print("Parlez maintenant...")
        audio = recognizer.listen(source, timeout=8, phrase_time_limit=6)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio.get_wav_data())
        tmp_path = tmp.name

    result = verifier.verify_wav(tmp_path)

    print()
    print("Résultat :", result.accepted)
    print("Message :", result.message)
    print("Score :", result.best_score)

    try:
        os.remove(tmp_path)
    except Exception:
        pass


if __name__ == "__main__":
    main()