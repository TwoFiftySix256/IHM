from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import AssistantConfig


@dataclass
class ActionResult:
    ok: bool
    message: str
    path: Optional[str] = None
    candidates: Optional[list[str]] = None


class AmbiguousPathError(Exception):
    def __init__(self, candidates: list[str]):
        super().__init__("Plusieurs dossiers ou fichiers correspondent.")
        self.candidates = candidates


class SafeSystemActionExecutor:
    """
    Exécuteur sécurisé pour les actions système.

    Fonctionnalités :
    - ouvrir un dossier ou document ;
    - ouvrir plusieurs dossiers/documents ;
    - fermer un dossier ou document ouvert ;
    - fermer plusieurs dossiers/documents ;
    - fermer tout ce que l'assistant a ouvert ;
    - créer, renommer, supprimer de façon sécurisée ;
    - chercher uniquement dans C:, principalement dans le profil utilisateur ;
    - bloquer les dossiers système Windows.
    """

    def __init__(self, config: AssistantConfig):
        self.config = config
        self.opened_registry_file = self.config.data_dir / "opened_paths.json"

    # ============================================================
    # CRÉATION / RENOMMAGE / SUPPRESSION
    # ============================================================

    def create_file(self, path: str, content: str = "") -> ActionResult:
        try:
            target = self._safe_new_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)

            if target.exists():
                return ActionResult(False, f"Le fichier existe déjà : {target.name}", str(target))

            target.write_text(content, encoding="utf-8")
            return ActionResult(True, f"J'ai créé le fichier {target.name}.", str(target))

        except Exception as exc:
            return ActionResult(False, f"Je n'ai pas pu créer le fichier : {exc}")

    def create_folder(self, path: str) -> ActionResult:
        try:
            target = self._safe_new_path(path)
            target.mkdir(parents=True, exist_ok=True)
            return ActionResult(True, f"J'ai créé le dossier {target.name}.", str(target))

        except Exception as exc:
            return ActionResult(False, f"Je n'ai pas pu créer le dossier : {exc}")

    def rename_path(self, path: str, new_path: str) -> ActionResult:
        try:
            source = self._resolve_existing_path(path)
            target = self._safe_new_path(new_path)

            if target.exists():
                return ActionResult(False, f"Le nom {target.name} existe déjà.", str(target))

            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)

            self._forget_opened_path(source)
            self._remember_opened_path(target)

            return ActionResult(True, f"J'ai renommé en {target.name}.", str(target))

        except Exception as exc:
            return ActionResult(False, f"Je n'ai pas pu renommer : {exc}")

    def delete_path(self, path: str) -> ActionResult:
        try:
            target = self._resolve_existing_path(path)

            if self._is_blocked_system_path(target):
                return ActionResult(False, "Je refuse de supprimer un élément système protégé.", str(target))

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            trash_target = self.config.trash_dir / f"{target.name}_{timestamp}"

            shutil.move(str(target), str(trash_target))
            self._forget_opened_path(target)

            return ActionResult(
                True,
                f"J'ai déplacé {target.name} dans la corbeille interne.",
                str(trash_target),
            )

        except Exception as exc:
            return ActionResult(False, f"Je n'ai pas pu supprimer : {exc}")

    # ============================================================
    # OUVERTURE SIMPLE / MULTIPLE
    # ============================================================

    def open_path(self, path: str) -> ActionResult:
        try:
            target = self._resolve_existing_path(path)
            return self.open_exact_path(str(target))

        except AmbiguousPathError as exc:
            return ActionResult(
                False,
                "J'ai trouvé plusieurs éléments possibles. Précise lequel ouvrir.",
                candidates=exc.candidates,
            )

        except Exception:
            candidates = self.find_candidates(path)

            if candidates:
                return ActionResult(
                    False,
                    "J'ai trouvé plusieurs éléments possibles. Précise lequel ouvrir.",
                    candidates=candidates,
                )

            return ActionResult(
                False,
                f"Je n'ai pas trouvé : {path}. Donne le nom exact ou le chemin complet.",
                candidates=[],
            )

    def open_exact_path(self, exact_path: str) -> ActionResult:
        try:
            target = Path(exact_path).expanduser().resolve()

            if not target.exists():
                return ActionResult(False, f"Je n'ai pas trouvé {target.name}.", str(target))

            if not self._is_allowed_c_drive_path(target):
                return ActionResult(False, "Je peux ouvrir uniquement les éléments autorisés du disque C.", str(target))

            if self._is_blocked_system_path(target):
                return ActionResult(
                    False,
                    "Je ne peux pas ouvrir ce dossier, car il appartient à une zone système protégée.",
                    str(target),
                )

            if platform.system() == "Windows":
                if target.is_dir():
                    subprocess.Popen(["explorer", str(target)])
                else:
                    os.startfile(str(target))  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])

            self._remember_opened_path(target)

            if target.is_dir():
                return ActionResult(True, f"D'accord, j'ouvre le dossier {target.name}.", str(target))

            return ActionResult(True, f"D'accord, j'ouvre le document {target.name}.", str(target))

        except Exception as exc:
            return ActionResult(False, f"Je n'arrive pas à ouvrir cet élément : {exc}")

    def open_many_paths(self, paths: list[str]) -> ActionResult:
        if len(paths) > 5:
            return ActionResult(
                False,
                "Je peux ouvrir au maximum cinq éléments à la fois pour éviter de bloquer l'application.",
            )

        opened: list[str] = []
        failed: list[str] = []
        ambiguous: list[str] = []

        for item in paths:
            item = item.strip()

            if not item:
                continue

            result = self.open_path(item)

            if result.ok:
                opened.append(Path(result.path or item).name)
            elif result.candidates:
                ambiguous.append(item)
            else:
                failed.append(item)

        parts: list[str] = []

        if opened:
            parts.append(f"J'ai ouvert : {', '.join(opened)}")

        if ambiguous:
            parts.append(f"J'ai trouvé plusieurs possibilités pour : {', '.join(ambiguous)}")

        if failed:
            parts.append(f"Je n'ai pas trouvé : {', '.join(failed)}")

        if not parts:
            return ActionResult(False, "Je n'ai rien ouvert.")

        return ActionResult(bool(opened), ". ".join(parts) + ".")

    # ============================================================
    # FERMETURE SIMPLE / MULTIPLE
    # ============================================================

    def close_path(self, path: str) -> ActionResult:
        try:
            try:
                target = self._resolve_existing_path(path)
            except Exception:
                target = self._find_in_opened_registry(path)

                if target is None:
                    return ActionResult(False, f"Je ne trouve pas ce qui doit être fermé : {path}.")

            if self._is_blocked_system_path(target):
                return ActionResult(False, "Je ne ferme pas les dossiers système protégés.", str(target))

            closed = False

            if platform.system() == "Windows":
                if target.is_dir():
                    closed = self._close_explorer_window_for_folder(target)
                else:
                    closed = self._close_window_by_title(target.name)

            if closed:
                self._forget_opened_path(target)

                if target.is_dir():
                    return ActionResult(True, f"C'est fait, j'ai fermé le dossier {target.name}.", str(target))

                return ActionResult(True, f"C'est fait, j'ai fermé le document {target.name}.", str(target))

            return ActionResult(
                False,
                f"Je n'ai pas trouvé de fenêtre ouverte pour {target.name}.",
                str(target),
            )

        except Exception as exc:
            return ActionResult(False, f"Je n'ai pas pu fermer : {exc}")

    def close_many_paths(self, paths: list[str]) -> ActionResult:
        if len(paths) > 5:
            return ActionResult(
                False,
                "Je peux fermer au maximum cinq éléments à la fois pour éviter de bloquer l'application.",
            )

        closed: list[str] = []
        failed: list[str] = []

        for item in paths:
            item = item.strip()

            if not item:
                continue

            result = self.close_path(item)

            if result.ok:
                closed.append(item)
            else:
                failed.append(item)

        parts: list[str] = []

        if closed:
            parts.append(f"J'ai fermé : {', '.join(closed)}")

        if failed:
            parts.append(f"Je n'ai pas pu fermer : {', '.join(failed)}")

        if not parts:
            return ActionResult(False, "Je n'ai rien fermé.")

        return ActionResult(bool(closed), ". ".join(parts) + ".")

    def close_all_opened(self) -> ActionResult:
        opened = self._load_opened_paths()

        if not opened:
            return ActionResult(False, "Je n'ai aucun dossier ou document ouvert à fermer.")

        closed: list[str] = []
        failed: list[str] = []

        for raw_path in list(opened):
            path = Path(raw_path)

            if self._is_blocked_system_path(path):
                continue

            result = self.close_path(str(path))

            if result.ok:
                closed.append(path.name)
            else:
                failed.append(path.name)

        if closed and not failed:
            return ActionResult(True, f"C'est fait, j'ai fermé : {', '.join(closed)}.")

        if closed:
            return ActionResult(
                True,
                f"J'ai fermé : {', '.join(closed)}. Certains éléments n'étaient déjà plus ouverts.",
            )

        return ActionResult(False, "Je n'ai pas réussi à fermer les éléments ouverts.")

    # ============================================================
    # APPLICATIONS
    # ============================================================

    def launch_app(self, app: str) -> ActionResult:
        normalized = self._normalize_app_name(app)

        if normalized not in self.config.allowed_apps:
            return ActionResult(False, f"Je ne suis pas encore autorisé à lancer {app}.")

        try:
            subprocess.Popen([normalized], shell=False)
            return ActionResult(True, f"D'accord, je lance {app}.")

        except FileNotFoundError:
            return ActionResult(False, f"Je n'ai pas trouvé l'application {app}.")

        except Exception as exc:
            return ActionResult(False, f"Je n'ai pas pu lancer l'application : {exc}")

    # ============================================================
    # RÉSOLUTION DES CHEMINS
    # ============================================================

    def _resolve_existing_path(self, spoken_path: str) -> Path:
        raw = self._clean_spoken_path(spoken_path)

        if not raw:
            raise FileNotFoundError("Chemin vide.")

        alias = self._known_location(raw)

        if alias and alias.exists():
            alias = alias.resolve()

            if not self._is_allowed_c_drive_path(alias):
                raise PermissionError("Chemin non autorisé.")

            if self._is_blocked_system_path(alias):
                raise PermissionError("Dossier système bloqué.")

            return alias

        candidate = Path(raw).expanduser()

        if candidate.is_absolute():
            candidate = candidate.resolve()

            if not self._is_allowed_c_drive_path(candidate):
                raise PermissionError("Chemin non autorisé.")

            if self._is_blocked_system_path(candidate):
                raise PermissionError("Dossier système bloqué.")

            if candidate.exists():
                return candidate

            raise FileNotFoundError(str(candidate))

        for root in self._valid_roots():
            direct = (root / raw).resolve()

            if direct.exists() and self._is_allowed_c_drive_path(direct) and not self._is_blocked_system_path(direct):
                return direct

        candidates = self.find_candidates(raw)

        if len(candidates) == 1:
            return Path(candidates[0]).resolve()

        if len(candidates) > 1:
            raise AmbiguousPathError(candidates)

        raise FileNotFoundError(raw)

    def _safe_new_path(self, spoken_path: str) -> Path:
        raw = self._clean_spoken_path(spoken_path)

        if not raw:
            raise ValueError("Nom vide.")

        candidate = Path(raw).expanduser()

        if not candidate.is_absolute():
            base = Path.home() / "Documents"
            candidate = base / candidate

        candidate = candidate.resolve()

        if not self._is_allowed_c_drive_path(candidate):
            raise PermissionError("Je crée uniquement dans les zones autorisées du disque C.")

        if self._is_blocked_system_path(candidate):
            raise PermissionError("Ce chemin appartient à une zone système protégée.")

        if not self._is_under_allowed_root(candidate):
            raise PermissionError("Ce chemin n'est pas autorisé.")

        return candidate

    def find_candidates(self, name: str, limit: int = 5) -> list[str]:
        """
        Recherche uniquement dans le disque C, surtout dans C:\\Users\\<utilisateur>.
        La recherche est volontairement limitée pour éviter que l'interface Tkinter bloque.
        """
        wanted = self._normalize_name(name)
        results: list[str] = []

        if not wanted:
            return results

        alias = self._known_location(name)

        if alias:
            try:
                alias = alias.resolve()

                if (
                    alias.exists()
                    and self._is_allowed_c_drive_path(alias)
                    and not self._is_blocked_system_path(alias)
                ):
                    return [str(alias)]
            except Exception:
                pass

        safe_roots = self._valid_roots()

        checked = 0
        max_checked = 1500

        blocked_names = {
            "appdata",
            "node_modules",
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "windows",
            "system32",
            "program files",
            "program files (x86)",
            "programdata",
            "$recycle.bin",
            "system volume information",
        }

        for root in safe_roots:
            try:
                root = root.resolve()

                if not root.exists():
                    continue

                direct = (root / name).resolve()

                if (
                    direct.exists()
                    and self._is_allowed_c_drive_path(direct)
                    and not self._is_blocked_system_path(direct)
                ):
                    return [str(direct)]

                for current, dirs, files in os.walk(root):
                    checked += 1

                    if checked > max_checked:
                        return results[:limit]

                    current_path = Path(current).resolve()

                    if not self._is_allowed_c_drive_path(current_path):
                        dirs[:] = []
                        continue

                    if self._is_blocked_system_path(current_path):
                        dirs[:] = []
                        continue

                    try:
                        rel = current_path.relative_to(root)

                        if len(rel.parts) >= 4:
                            dirs[:] = []
                    except Exception:
                        pass

                    dirs[:] = [
                        d for d in dirs
                        if d.lower() not in blocked_names and not d.startswith(".")
                    ]

                    for folder in dirs:
                        folder_path = (current_path / folder).resolve()

                        if not self._is_allowed_c_drive_path(folder_path):
                            continue

                        if self._is_blocked_system_path(folder_path):
                            continue

                        normalized_folder = self._normalize_name(folder)

                        if normalized_folder == wanted or wanted in normalized_folder:
                            path = str(folder_path)

                            if path not in results:
                                results.append(path)

                        if len(results) >= limit:
                            return results[:limit]

                    for file in files:
                        file_path = (current_path / file).resolve()

                        if not self._is_allowed_c_drive_path(file_path):
                            continue

                        if self._is_blocked_system_path(file_path):
                            continue

                        normalized_file = self._normalize_name(file)

                        if normalized_file == wanted or wanted in normalized_file:
                            path = str(file_path)

                            if path not in results:
                                results.append(path)

                        if len(results) >= limit:
                            return results[:limit]

            except Exception:
                continue

        return results[:limit]

    # ============================================================
    # REGISTRE DES ÉLÉMENTS OUVERTS
    # ============================================================

    def _remember_opened_path(self, path: Path) -> None:
        try:
            paths = self._load_opened_paths()
            resolved = str(path.resolve())

            if resolved not in paths:
                paths.append(resolved)

            self._save_opened_paths(paths)

        except Exception:
            pass

    def _forget_opened_path(self, path: Path) -> None:
        try:
            resolved = str(path.resolve())
            paths = [p for p in self._load_opened_paths() if p != resolved]
            self._save_opened_paths(paths)

        except Exception:
            pass

    def _load_opened_paths(self) -> list[str]:
        try:
            if self.opened_registry_file.exists():
                data = json.loads(self.opened_registry_file.read_text(encoding="utf-8"))

                if isinstance(data, list):
                    return [str(item) for item in data]

        except Exception:
            pass

        return []

    def _save_opened_paths(self, paths: list[str]) -> None:
        try:
            self.opened_registry_file.parent.mkdir(parents=True, exist_ok=True)
            self.opened_registry_file.write_text(
                json.dumps(paths, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        except Exception:
            pass

    def _find_in_opened_registry(self, spoken_name: str) -> Optional[Path]:
        wanted = self._normalize_name(spoken_name)

        for raw_path in self._load_opened_paths():
            path = Path(raw_path)

            if wanted in self._normalize_name(path.name):
                return path

        return None

    # ============================================================
    # FERMETURE WINDOWS
    # ============================================================

    def _close_explorer_window_for_folder(self, folder: Path) -> bool:
        if platform.system() != "Windows":
            return False

        folder = folder.resolve()
        safe_target = str(folder).replace('"', '`"')

        script = f"""
$target = "{safe_target}"
$shell = New-Object -ComObject Shell.Application
$windows = $shell.Windows()
$closed = $false

foreach ($window in $windows) {{
    try {{
        $path = $window.Document.Folder.Self.Path
        if ($path -eq $target) {{
            $window.Quit()
            $closed = $true
        }}
    }} catch {{}}
}}

if ($closed) {{
    exit 0
}} else {{
    exit 1
}}
"""

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )

            return result.returncode == 0

        except Exception:
            return False

    def _close_window_by_title(self, title_part: str) -> bool:
        if platform.system() != "Windows":
            return False

        try:
            user32 = ctypes.windll.user32
            WM_CLOSE = 0x0010
            closed_any = False
            title_part_lower = title_part.lower()

            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def callback(hwnd, lparam):
                nonlocal closed_any

                if not user32.IsWindowVisible(hwnd):
                    return True

                length = user32.GetWindowTextLengthW(hwnd)

                if length <= 0:
                    return True

                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value

                if title_part_lower in title.lower():
                    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                    closed_any = True

                return True

            user32.EnumWindows(EnumWindowsProc(callback), 0)
            return closed_any

        except Exception:
            return False

    # ============================================================
    # SÉCURITÉ
    # ============================================================

    def _valid_roots(self) -> list[Path]:
        """
        Racines de recherche.
        On cherche uniquement dans C:, principalement dans le profil utilisateur.
        """
        roots: list[Path] = []

        home = Path.home()

        default_roots = [
            home,
            home / "Desktop",
            home / "Documents",
            home / "Downloads",
            home / "Pictures",
            home / "Music",
            home / "Videos",
        ]

        all_roots = default_roots + list(self.config.allowed_roots)

        for root in all_roots:
            try:
                resolved = root.expanduser().resolve()

                if not resolved.exists():
                    continue

                if not self._is_allowed_c_drive_path(resolved):
                    continue

                if self._is_blocked_system_path(resolved):
                    continue

                if resolved not in roots:
                    roots.append(resolved)

            except Exception:
                pass

        return roots

    def _is_allowed_c_drive_path(self, candidate: Path) -> bool:
        """
        Autorise uniquement C:.
        """
        try:
            candidate = candidate.expanduser().resolve()

            if platform.system() == "Windows":
                return candidate.drive.upper() == "C:"

            return True

        except Exception:
            return False

    def _is_under_allowed_root(self, candidate: Path) -> bool:
        try:
            candidate = candidate.resolve()

            for root in self._valid_roots():
                try:
                    candidate.relative_to(root.resolve())
                    return True
                except ValueError:
                    continue

        except Exception:
            pass

        return False

    def _is_blocked_system_path(self, candidate: Path) -> bool:
        """
        Bloque les zones système sensibles.
        Même si l'utilisateur met C:\\ dans .env, ces dossiers restent interdits.
        """
        if platform.system() != "Windows":
            return False

        try:
            candidate = candidate.expanduser().resolve()
        except Exception:
            return True

        system_drive = os.environ.get("SystemDrive", "C:")
        windir = Path(os.environ.get("WINDIR", f"{system_drive}\\Windows"))

        blocked = [
            windir,
            windir / "System32",
            windir / "SysWOW64",
            Path(f"{system_drive}\\Program Files"),
            Path(f"{system_drive}\\Program Files (x86)"),
            Path(f"{system_drive}\\ProgramData"),
            Path.home() / "AppData",
            Path(f"{system_drive}\\Recovery"),
            Path(f"{system_drive}\\System Volume Information"),
            Path(f"{system_drive}\\$Recycle.Bin"),
        ]

        for root in blocked:
            try:
                root = root.resolve()
                candidate.relative_to(root)
                return True
            except Exception:
                continue

        return False

    # ============================================================
    # TEXTE / ALIAS
    # ============================================================

    def _known_location(self, text: str) -> Optional[Path]:
        lowered = self._normalize_name(text)

        aliases = {
            "bureau": Path.home() / "Desktop",
            "desktop": Path.home() / "Desktop",

            "document": Path.home() / "Documents",
            "documents": Path.home() / "Documents",
            "mes documents": Path.home() / "Documents",

            "telechargement": Path.home() / "Downloads",
            "telechargements": Path.home() / "Downloads",
            "téléchargement": Path.home() / "Downloads",
            "téléchargements": Path.home() / "Downloads",
            "downloads": Path.home() / "Downloads",

            "image": Path.home() / "Pictures",
            "images": Path.home() / "Pictures",
            "photo": Path.home() / "Pictures",
            "photos": Path.home() / "Pictures",

            "musique": Path.home() / "Music",
            "musiques": Path.home() / "Music",

            "video": Path.home() / "Videos",
            "videos": Path.home() / "Videos",
            "vidéo": Path.home() / "Videos",
            "vidéos": Path.home() / "Videos",
        }

        return aliases.get(lowered)

    @staticmethod
    def _split_many(text: str) -> list[str]:
        text = text or ""

        text = re.sub(r"\s+et\s+", ";", text, flags=re.IGNORECASE)
        text = text.replace(",", ";")
        text = text.replace(" puis ", ";")
        text = text.replace(" ensuite ", ";")

        return [item.strip() for item in text.split(";") if item.strip()]

    @staticmethod
    def _clean_spoken_path(text: str) -> str:
        text = (text or "").strip().strip('"').strip("'")

        replacements = {
            "anti slash": "\\",
            "antislash": "\\",
            "slash": "\\",
            "barre oblique": "\\",
            "deux points": ":",
        }

        lowered = text.lower()

        for old, new in replacements.items():
            lowered = lowered.replace(old, new)

        text = lowered

        text = re.sub(
            r"^(ouvre|ouvrir|cherche|chercher|trouve|ferme|fermer|lance)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"^(le|la|les|un|une|mon|ma|mes)\s+", "", text, flags=re.IGNORECASE)
        text = re.sub(
            r"^(dossier|fichier|document|documents|répertoire|repertoire)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )

        return text.strip(" .,:;")

    @staticmethod
    def _normalize_name(text: str) -> str:
        text = (text or "").lower().strip()

        accents = {
            "à": "a",
            "â": "a",
            "ä": "a",
            "é": "e",
            "è": "e",
            "ê": "e",
            "ë": "e",
            "î": "i",
            "ï": "i",
            "ô": "o",
            "ö": "o",
            "ù": "u",
            "û": "u",
            "ü": "u",
            "ç": "c",
        }

        for a, b in accents.items():
            text = text.replace(a, b)

        text = re.sub(r"[^\w\s\\:/.$()_-]", " ", text)
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    @staticmethod
    def _normalize_app_name(app: str) -> str:
        app = (app or "").strip().lower()

        aliases = {
            "bloc note": "notepad",
            "bloc-notes": "notepad",
            "bloc notes": "notepad",
            "notepad": "notepad",

            "calculatrice": "calc",
            "calculette": "calc",

            "paint": "mspaint",

            "explorateur": "explorer",
            "explorateur de fichiers": "explorer",

            "visual studio code": "code",
            "vs code": "code",

            "google chrome": "chrome",
            "chrome": "chrome",

            "microsoft edge": "edge",
            "edge": "edge",
        }

        return aliases.get(app, app)