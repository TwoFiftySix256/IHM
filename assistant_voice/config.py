from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


def _default_data_dir() -> Path:
    return Path(os.environ.get("ASSISTANT_DATA_DIR", Path.home() / ".genie_voice_assistant")).expanduser()


def _env_allowed_roots() -> list[Path] | None:
    """
    Permet de contrôler depuis .env les zones où l'assistant peut agir.
    Exemple Windows:
    ASSISTANT_ALLOWED_ROOTS=E:\\;C:\\Users\\Genie\\Desktop;C:\\Users\\Genie\\Documents
    """
    raw = os.environ.get("ASSISTANT_ALLOWED_ROOTS", "").strip()
    if not raw:
        return None

    roots: list[Path] = []
    for item in raw.split(";"):
        item = item.strip().strip('"').strip("'")
        if not item:
            continue
        try:
            roots.append(Path(item).expanduser().resolve())
        except OSError:
            continue

    return roots or None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw in {"1", "true", "yes", "y", "on", "oui"}:
        return True
    if raw in {"0", "false", "no", "n", "off", "non"}:
        return False
    return default


def _default_allowed_roots() -> list[Path]:
    env_roots = _env_allowed_roots()
    if env_roots:
        return env_roots

    candidates = [
        Path.cwd(),
        Path.home(),
        Path.home() / "Desktop",
        Path.home() / "Bureau",
        Path.home() / "Documents",
        Path.home() / "Downloads",
        Path.home() / "Téléchargements",
        Path.home() / "Pictures",
        Path.home() / "Images",
        Path.home() / "Music",
        Path.home() / "Videos",
        _default_data_dir(),
    ]

    roots: list[Path] = []
    for path in candidates:
        try:
            resolved = path.expanduser().resolve()
            if resolved not in roots:
                roots.append(resolved)
        except OSError:
            continue
    return roots


@dataclass
class AssistantConfig:
    """Configuration centrale de l'assistant.

    Les racines autorisées limitent les actions fichiers afin d'éviter qu'une
    phrase mal comprise modifie une zone sensible du système.
    """

    assistant_name: str = "Yollande"
    user_display_name: str = "Ingenieur Hermesse Mbizi"
    wake_words: tuple[str, ...] = (
        "yollande",
        "yolande",
        "hollande",
        "yo lande",
    )
    require_wake_word: bool = field(
        default_factory=lambda: _env_bool("ASSISTANT_REQUIRE_WAKE_WORD", True)
    )
    activation_timeout_seconds: int = 45
    language: str = "fr-FR"
    offline_mode: bool = field(
        default_factory=lambda: _env_bool("ASSISTANT_OFFLINE_MODE", False)
    )
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_key_env: str = "GEMINI_API_KEY"

    data_dir: Path = field(default_factory=_default_data_dir)
    tasks_file: Path | None = None
    trash_dir: Path | None = None
    allowed_roots: list[Path] = field(default_factory=_default_allowed_roots)

    allowed_apps: set[str] = field(
        default_factory=lambda: {
            "notepad",
            "calc",
            "mspaint",
            "explorer",
            "code",
            "chrome",
            "firefox",
            "edge",
            "cmd",
            "powershell",
            "wordpad",
        }
    )

    reminder_check_seconds: int = 15
    reminder_grace_seconds: int = 60

    def __post_init__(self) -> None:
        self.data_dir = self.data_dir.expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if self.tasks_file is None:
            self.tasks_file = self.data_dir / "tasks.json"
        else:
            self.tasks_file = self.tasks_file.expanduser().resolve()

        if self.trash_dir is None:
            self.trash_dir = self.data_dir / "trash"
        else:
            self.trash_dir = self.trash_dir.expanduser().resolve()

        self.trash_dir.mkdir(parents=True, exist_ok=True)
        self.allowed_roots = [p.expanduser().resolve() for p in self.allowed_roots]

    @property
    def gemini_api_key(self) -> str | None:
        value = os.environ.get(self.gemini_api_key_env, "").strip()
        return value or None

    def set_allowed_roots(self, roots: Iterable[str | Path]) -> None:
        self.allowed_roots = [Path(root).expanduser().resolve() for root in roots]
