from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class VerificationResult:
    accepted: bool
    message: str
    best_score: Optional[float] = None


class SpeakerVerifier:
    """
    Vérification de locuteur basée sur les embeddings SpeechBrain ECAPA-TDNN.

    Cette version évite :
    - verify_files(), qui provoquait l'erreur k2_fsa ;
    - torchaudio.load(), qui demandait TorchCodec.

    Elle utilise :
    - soundfile pour lire les fichiers WAV ;
    - scipy pour rééchantillonner en 16 kHz ;
    - SpeechBrain EncoderClassifier pour extraire l'empreinte vocale ;
    - similarité cosinus pour comparer les voix.
    """

    def __init__(
        self,
        profile_dir: str | Path,
        model_dir: str | Path,
        threshold: float = 0.50,
        min_matches: int = 1,
        enabled: bool = True,
    ):
        self.profile_dir = Path(profile_dir).expanduser().resolve()
        self.model_dir = Path(model_dir).expanduser().resolve()
        self.threshold = float(threshold)
        self.min_matches = max(1, int(min_matches))
        self.enabled = bool(enabled)

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self._model = None

        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    @classmethod
    def from_config(cls, config) -> "SpeakerVerifier":
        enabled = os.getenv("ASSISTANT_SPEAKER_AUTH", "0").strip() == "1"

        threshold = float(os.getenv("ASSISTANT_SPEAKER_THRESHOLD", "0.50"))
        min_matches = int(os.getenv("ASSISTANT_SPEAKER_MIN_MATCHES", "1"))

        return cls(
            profile_dir=config.data_dir / "voice_profile",
            model_dir=config.data_dir / "models" / "spkrec-ecapa-voxceleb",
            threshold=threshold,
            min_matches=min_matches,
            enabled=enabled,
        )

    def reference_files(self) -> list[Path]:
        return sorted(self.profile_dir.glob("reference_*.wav"))

    def has_profile(self) -> bool:
        return len(self.reference_files()) > 0

    def verify_wav(self, wav_path: str | Path) -> VerificationResult:
        if not self.enabled:
            return VerificationResult(
                accepted=True,
                message="Vérification vocale désactivée.",
                best_score=None,
            )

        wav_path = Path(wav_path).expanduser().resolve()

        if not wav_path.exists():
            return VerificationResult(
                accepted=False,
                message="Fichier audio de test introuvable.",
                best_score=None,
            )

        references = self.reference_files()

        print("[SpeakerVerifier] Fichier test :", wav_path)
        print("[SpeakerVerifier] Références trouvées :", len(references))

        if not references:
            return VerificationResult(
                accepted=False,
                message="Aucun profil vocal trouvé. Relancez enroll_voice.py.",
                best_score=None,
            )

        try:
            model = self._load_model()
            print("[SpeakerVerifier] Modèle EncoderClassifier chargé.")
        except Exception as exc:
            return VerificationResult(
                accepted=False,
                message=f"Impossible de charger le modèle SpeechBrain : {type(exc).__name__}: {exc}",
                best_score=None,
            )

        try:
            test_embedding = self._extract_embedding(model, wav_path)
        except Exception as exc:
            return VerificationResult(
                accepted=False,
                message=f"Impossible d'extraire l'empreinte vocale du test : {type(exc).__name__}: {exc}",
                best_score=None,
            )

        matches = 0
        scores: list[float] = []
        errors: list[str] = []

        for ref in references:
            try:
                print("[SpeakerVerifier] Comparaison avec :", ref.name)

                ref_embedding = self._extract_embedding(model, ref)
                score = self._cosine_similarity(ref_embedding, test_embedding)

                accepted = score >= self.threshold

                print("[SpeakerVerifier] Score cosinus :", score)
                print("[SpeakerVerifier] Seuil :", self.threshold)
                print("[SpeakerVerifier] Accepté :", accepted)

                scores.append(score)

                if accepted:
                    matches += 1

            except Exception as exc:
                err = f"{ref.name} -> {type(exc).__name__}: {exc}"
                print("[SpeakerVerifier] ERREUR :", err)
                errors.append(err)

        if not scores:
            detail = errors[0] if errors else "Erreur inconnue."
            return VerificationResult(
                accepted=False,
                message=f"Aucune comparaison n'a réussi. Détail : {detail}",
                best_score=None,
            )

        best_score = max(scores)

        if matches >= self.min_matches:
            return VerificationResult(
                accepted=True,
                message=(
                    f"Voix autorisée. "
                    f"Correspondances : {matches}. "
                    f"Meilleur score : {best_score:.4f}."
                ),
                best_score=best_score,
            )

        return VerificationResult(
            accepted=False,
            message=(
                f"Voix non autorisée. "
                f"Correspondances : {matches}. "
                f"Meilleur score : {best_score:.4f}."
            ),
            best_score=best_score,
        )

    def _load_model(self):
        if self._model is not None:
            return self._model

        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except Exception:
            from speechbrain.pretrained import EncoderClassifier  # type: ignore

        try:
            from speechbrain.utils.fetching import LocalStrategy
            local_strategy = LocalStrategy.COPY
        except Exception:
            local_strategy = "copy"

        self._model = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=str(self.model_dir),
            local_strategy=local_strategy,
            run_opts={"device": "cpu"},
        )

        return self._model

    def _extract_embedding(self, model, wav_path: Path):
        """
        Lit le WAV avec soundfile, convertit en mono 16 kHz,
        puis extrait l'empreinte vocale avec SpeechBrain.
        """
        import math

        import numpy as np
        import soundfile as sf
        import torch
        from scipy.signal import resample_poly

        audio, sample_rate = sf.read(str(wav_path), dtype="float32", always_2d=False)

        if audio is None:
            raise ValueError("Audio vide ou illisible.")

        audio = np.asarray(audio, dtype=np.float32)

        # Si stéréo ou multi-canaux : conversion mono
        if audio.ndim == 2:
            audio = audio.mean(axis=1)

        if audio.ndim != 1:
            raise ValueError(f"Format audio inattendu : shape={audio.shape}")

        if audio.size < 1600:
            raise ValueError("Audio trop court pour extraire une empreinte vocale.")

        # Rééchantillonnage vers 16 kHz si nécessaire
        target_rate = 16000

        if int(sample_rate) != target_rate:
            gcd = math.gcd(int(sample_rate), target_rate)
            up = target_rate // gcd
            down = int(sample_rate) // gcd
            audio = resample_poly(audio, up, down).astype(np.float32)

        # Nettoyage valeurs anormales
        audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)

        max_abs = float(np.max(np.abs(audio))) if audio.size else 0.0

        if max_abs <= 1e-6:
            raise ValueError("Audio silencieux ou presque silencieux.")

        # Normalisation légère
        if max_abs > 1.0:
            audio = audio / max_abs

        waveform = torch.from_numpy(audio).float().unsqueeze(0)

        with torch.no_grad():
            embedding = model.encode_batch(waveform)

        return embedding.squeeze().detach().cpu()

    @staticmethod
    def _cosine_similarity(embedding_a, embedding_b) -> float:
        import torch.nn.functional as F

        a = embedding_a.flatten().float()
        b = embedding_b.flatten().float()

        if a.numel() == 0 or b.numel() == 0:
            return 0.0

        score = F.cosine_similarity(a.unsqueeze(0), b.unsqueeze(0)).item()
        return float(score)