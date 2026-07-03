from __future__ import annotations

import base64
import os
import subprocess
import threading


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class Speaker:
    """Synthèse vocale robuste.

    Sous Windows, on utilise d'abord la voix native SAPI via PowerShell,
    car pyttsx3 peut parfois s'installer mais rester silencieux avec Anaconda.

    Variables utiles :
    - ASSISTANT_TTS_ENGINE=windows : force la voix Windows native.
    - ASSISTANT_TTS_ENGINE=pyttsx3 : force pyttsx3.
    - ASSISTANT_TTS_ENGINE=auto : choix automatique, valeur par défaut.
    """

    def __init__(self, rate: int = 175, volume: float = 1.0):
        self._lock = threading.Lock()
        self._process_lock = threading.Lock()
        self._active_process: subprocess.Popen | None = None
        self._engine = None
        self._pyttsx3_available = False
        self.rate = rate
        self.volume = max(0.0, min(1.0, float(volume)))
        self.mode = os.getenv("ASSISTANT_TTS_ENGINE", "auto").strip().lower() or "auto"

        if self.mode != "windows":
            try:
                import pyttsx3  # type: ignore

                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", rate)
                self._engine.setProperty("volume", self.volume)
                self._pyttsx3_available = True
            except Exception:
                self._pyttsx3_available = False

    def say(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return

        with self._lock:
            # Sur Windows, la voix native SAPI est la plus fiable avec Anaconda.
            if self.mode in {"auto", "windows"} and os.name == "nt":
                if self._say_windows_sapi(text):
                    return

            # Secours pyttsx3.
            if self.mode in {"auto", "pyttsx3"} and self._pyttsx3_available and self._engine is not None:
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                    return
                except Exception:
                    pass

            # Dernier secours : texte console.
            print(f"[Assistant] {text}")

    def say_async(self, text: str) -> None:
        threading.Thread(target=self.say, args=(text,), daemon=True).start()

    def interrupt(self) -> None:
        with self._process_lock:
            process = self._active_process
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass

        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass

    def _say_windows_sapi(self, text: str) -> bool:
        try:
            if self._say_windows_com(text):
                return True

            volume = int(round(self.volume * 100))
            # SAPI Rate va de -10 à 10. On mappe grossièrement 175 vers 0.
            sapi_rate = max(-10, min(10, int(round((self.rate - 175) / 20))))
            script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Volume = {volume}
$synth.Rate = {sapi_rate}
$synth.Speak({_ps_single_quote(text)})
"""
            encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
            process = subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-EncodedCommand",
                    encoded,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with self._process_lock:
                self._active_process = process
            try:
                process.wait(timeout=90)
            finally:
                with self._process_lock:
                    if self._active_process is process:
                        self._active_process = None
            return True
        except Exception:
            return False

    def _say_windows_com(self, text: str) -> bool:
        try:
            import pythoncom  # type: ignore
            import win32com.client  # type: ignore

            pythoncom.CoInitialize()
            try:
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                voice.Volume = int(round(self.volume * 100))
                voice.Rate = max(-10, min(10, int(round((self.rate - 175) / 20))))
                voice.Speak(text)
            finally:
                pythoncom.CoUninitialize()
            return True
        except Exception:
            return False
