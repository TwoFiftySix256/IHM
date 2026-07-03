from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ListenResult:
    text: str
    ok: bool = True
    error: str = ""


class SpeechToText:
    """Capture vocale basée sur SpeechRecognition.

    Mode actuel : écoute ponctuelle ou écoute continue depuis l'interface.
    Le moteur `recognize_google` nécessite Internet. Si le micro n'est pas
    détecté, utilisez `python diagnostic_audio.py` pour identifier le problème.
    """

    def __init__(
        self,
        language: str = "fr-FR",
        timeout: int | None = None,
        phrase_time_limit: int | None = None,
        microphone_index: Optional[int] = None,
    ):
        self.language = language
        self.timeout = timeout if timeout is not None else int(os.getenv("ASSISTANT_STT_TIMEOUT", "5"))
        self.phrase_time_limit = (
            phrase_time_limit
            if phrase_time_limit is not None
            else int(os.getenv("ASSISTANT_STT_PHRASE_TIME_LIMIT", "7"))
        )
        self.ambient_noise_duration = float(os.getenv("ASSISTANT_AMBIENT_NOISE_SECONDS", "0.25"))
        self._ambient_adjusted = False
        env_index = os.environ.get("ASSISTANT_MIC_INDEX", "").strip()
        if microphone_index is None and env_index.isdigit():
            microphone_index = int(env_index)
        self.microphone_index = microphone_index
        try:
            import speech_recognition as sr  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "SpeechRecognition n'est pas installé. Installez requirements.txt et PyAudio."
            ) from exc
        self.sr = sr
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = float(os.getenv("ASSISTANT_STT_PAUSE_THRESHOLD", "0.55"))

    def list_microphones(self) -> list[str]:
        return list(self.sr.Microphone.list_microphone_names())

    def listen_once(self) -> ListenResult:
        sr = self.sr
        try:
            with sr.Microphone(device_index=self.microphone_index) as source:
                if not self._ambient_adjusted:
                    self.recognizer.adjust_for_ambient_noise(
                        source,
                        duration=self.ambient_noise_duration,
                    )
                    self._ambient_adjusted = True
                audio = self.recognizer.listen(
                    source,
                    timeout=self.timeout,
                    phrase_time_limit=self.phrase_time_limit,
                )
            text = self.recognizer.recognize_google(audio, language=self.language)
            return ListenResult(text=text.strip())
        except sr.WaitTimeoutError:
            return ListenResult(text="", ok=False, error="Aucune voix détectée. Rapprochez-vous du micro ou choisissez le bon micro.")
        except sr.UnknownValueError:
            return ListenResult(text="", ok=False, error="J'ai entendu un son, mais je n'ai pas compris la phrase.")
        except Exception as exc:
            return ListenResult(text="", ok=False, error=f"Erreur microphone/STT : {exc}")
