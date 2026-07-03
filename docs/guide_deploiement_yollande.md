# Guide de Déploiement et d'Installation de Yollande

Ce guide explique comment installer et lancer Yollande sur une autre machine,
avec un démarrage simplifié par icône de bureau ou lancement automatique en
arrière-plan.

## 1. Prérequis système

### Windows

- Windows 10 ou Windows 11.
- Python 3.11 ou 3.12 recommandé.
- Microphone fonctionnel et autorisé dans les paramètres de confidentialité.
- Sortie audio fonctionnelle.
- PowerShell disponible.
- Pour la synthèse vocale rapide : `pywin32` recommandé.
- Pour le microphone avec `SpeechRecognition` : `PyAudio`.

### Linux

- Python 3.11 ou 3.12 recommandé.
- Microphone accessible par PulseAudio ou PipeWire.
- Paquets audio système, selon distribution :

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip portaudio19-dev libasound2-dev
```

### macOS

- Python 3.11 ou 3.12 recommandé.
- Xcode Command Line Tools.
- Microphone autorisé dans les préférences de confidentialité.
- PortAudio, si PyAudio doit être compilé :

```bash
brew install portaudio
```

## 2. Installation du projet

Cloner le projet :

```bash
git clone <URL_DU_DEPOT> IHM-bot
cd IHM-bot
```

Créer un environnement virtuel :

### Windows PowerShell

```powershell
python -m venv IHM
.\IHM\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Linux / macOS

```bash
python3 -m venv IHM
source IHM/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Configuration

Créer un fichier `.env` à la racine du projet :

```env
ASSISTANT_REQUIRE_WAKE_WORD=1
ASSISTANT_AUTO_LISTEN=1
ASSISTANT_START_MINIMIZED=0
ASSISTANT_OFFLINE_MODE=0
ASSISTANT_TTS_ENGINE=auto
ASSISTANT_EARLY_REMINDER_MINUTES=5
ASSISTANT_STT_TIMEOUT=5
ASSISTANT_STT_PHRASE_TIME_LIMIT=7
ASSISTANT_STT_PAUSE_THRESHOLD=0.55
ASSISTANT_AMBIENT_NOISE_SECONDS=0.25
```

Pour forcer les fonctions essentielles en mode offline :

```env
ASSISTANT_OFFLINE_MODE=1
```

Dans ce mode, les commandes de tâches sont traitées par le parseur local et
Gemini n'est pas utilisé. Les tâches et rappels restent enregistrés localement.

Note : selon le backend utilisé, la reconnaissance vocale peut encore dépendre
d'Internet. Pour un mode vocal 100 % offline, il faut intégrer un moteur STT
local comme Vosk ou Whisper local.

## 4. Lancement manuel de test

### Windows

```powershell
.\IHM\Scripts\Activate.ps1
python run_assistant.py
```

### Linux / macOS

```bash
source IHM/bin/activate
python run_assistant.py
```

Phrase de test :

```text
Yollande, rappelle-moi de préparer le rapport à 14 h 30
```

Diagnostic voix et micro :

```bash
python diagnostic_voice_io.py
```

## 5. Script de lancement en arrière-plan

### Windows : fichier `launch_yollande.bat`

Créer un fichier `launch_yollande.bat` à la racine du projet :

```bat
@echo off
cd /d "%~dp0"
set ASSISTANT_AUTO_LISTEN=1
set ASSISTANT_REQUIRE_WAKE_WORD=1
start "" "%~dp0IHM\Scripts\pythonw.exe" "%~dp0run_assistant.py"
exit /b
```

Ce script utilise `pythonw.exe`, ce qui évite d'afficher une fenêtre terminal.

Le projet contient aussi un script prêt à l'emploi :

```powershell
.\ops\windows\Yollande.bat
```

### Linux / macOS : fichier `launch_yollande.sh`

Créer un fichier `launch_yollande.sh` :

```bash
#!/usr/bin/env bash
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

export ASSISTANT_AUTO_LISTEN=1
export ASSISTANT_REQUIRE_WAKE_WORD=1

source "$APP_DIR/IHM/bin/activate"
nohup python "$APP_DIR/run_assistant.py" > "$APP_DIR/yollande.log" 2>&1 &
```

Rendre le script exécutable :

```bash
chmod +x launch_yollande.sh
```

## 6. Raccourci sur le Bureau

### Windows

Méthode automatique :

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\create_desktop_shortcut.ps1
```

Méthode manuelle :

1. Clic droit sur le Bureau.
2. Choisir **Nouveau > Raccourci**.
3. Indiquer comme cible :

```text
C:\Users\<USER>\IHM-bot\launch_yollande.bat
```

4. Nommer le raccourci `Yollande`.
5. Clic droit sur le raccourci > **Propriétés**.
6. Cliquer sur **Changer d'icône**.
7. Choisir une icône système ou un fichier `.ico` personnalisé.

### Linux : fichier `.desktop`

Créer le fichier `~/Desktop/yollande.desktop` :

```ini
[Desktop Entry]
Type=Application
Name=Yollande
Comment=Assistant vocal Yollande
Exec=/chemin/vers/IHM-bot/launch_yollande.sh
Icon=utilities-terminal
Terminal=false
Categories=Utility;
```

Rendre le lanceur exécutable :

```bash
chmod +x ~/Desktop/yollande.desktop
```

Selon l'environnement graphique, il peut être nécessaire de faire clic droit
sur l'icône puis **Autoriser le lancement**.

### macOS : lanceur simple

Créer un script `launch_yollande.command` :

```bash
#!/usr/bin/env bash
cd "$(dirname "$0")"
source IHM/bin/activate
python run_assistant.py
```

Puis :

```bash
chmod +x launch_yollande.command
```

Placer ce fichier sur le Bureau ou dans le Dock.

## 7. Lancement automatique au démarrage

### Windows : Planificateur de tâches

Le projet fournit un script d'installation :

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\install_startup_task.ps1
```

Pour supprimer le lancement automatique :

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\uninstall_startup_task.ps1
```

### Linux : systemd utilisateur

Copier le fichier de service :

```bash
mkdir -p ~/.config/systemd/user
cp ops/linux/yollande.service ~/.config/systemd/user/yollande.service
```

Adapter les chemins `WorkingDirectory` et `ExecStart`, puis :

```bash
systemctl --user daemon-reload
systemctl --user enable --now yollande.service
```

Vérifier le statut :

```bash
systemctl --user status yollande.service
```

### macOS : Launchd

Copier le fichier plist :

```bash
cp ops/macos/com.hermes.yollande.plist ~/Library/LaunchAgents/
```

Adapter les chemins dans le fichier si nécessaire, puis charger :

```bash
launchctl load ~/Library/LaunchAgents/com.hermes.yollande.plist
```

## 8. Vérification offline des tâches et rappels

1. Mettre dans `.env` :

```env
ASSISTANT_OFFLINE_MODE=1
```

2. Lancer l'application.
3. Créer une tâche :

```text
Yollande, rappelle-moi de tester le mode offline à 18 h
```

4. Couper Internet.
5. Vérifier que la tâche reste visible dans l'interface.
6. Attendre l'heure du rappel.

Le rappel est déclenché par le scheduler local et ne dépend pas de Gemini.

## 9. Dépannage rapide

Tester la voix :

```bash
python diagnostic_voice_io.py
```

Si le micro ne répond pas :

- vérifier les permissions système ;
- vérifier le périphérique par défaut ;
- tester un autre index micro avec `ASSISTANT_MIC_INDEX`.

Si la voix ne sort pas sous Windows :

```env
ASSISTANT_TTS_ENGINE=windows
```

Si les réponses sont trop lentes :

```env
ASSISTANT_STT_PAUSE_THRESHOLD=0.45
ASSISTANT_AMBIENT_NOISE_SECONDS=0.15
```

Réduire ces valeurs améliore la vitesse, mais peut couper certaines phrases si
l'utilisateur parle lentement.
