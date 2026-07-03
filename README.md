# Yollande - agent vocal intelligent pour PC

Cette archive ajoute un module indépendant d'assistant vocal à un projet Python existant, sans modifier les fichiers déjà présents. Elle respecte l'idée du cahier des charges : interaction vocale, liste de tâches journalières, statut des tâches, service de rappel en arrière-plan, confirmation orale et contrôle utilisateur.

## Ce que contient l'extension

```text
assistant_vocal_extension/
├── assistant_voice/
│   ├── config.py              # configuration globale
│   ├── gemini_nlu.py          # compréhension NLU avec Gemini
│   ├── stt.py                 # speech-to-text avec SpeechRecognition
│   ├── tts.py                 # text-to-speech avec pyttsx3
│   ├── task_manager.py        # logique de gestion des tâches
│   ├── scheduler.py           # rappels en arrière-plan
│   ├── system_actions.py      # actions système sécurisées
│   ├── command_router.py      # orchestration des commandes
│   └── gui_tk.py              # interface Tkinter simple
├── run_assistant.py           # point d'entrée autonome
├── requirements.txt
├── .env.example
└── tests/
```

## Installation

```bash
cd assistant_vocal_extension
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # Linux/macOS
pip install -r requirements.txt
```

Pour le microphone, `SpeechRecognition` utilise `PyAudio`. Si l'installation échoue sous Windows :

```bash
py -m pip install pipwin
pipwin install pyaudio
```

## Configuration Gemini

Créez une clé API Gemini gratuite dans Google AI Studio, puis définissez la variable d'environnement :

```bash
set GEMINI_API_KEY=votre_cle_api       # Windows CMD
# $env:GEMINI_API_KEY="votre_cle_api"  # PowerShell
# export GEMINI_API_KEY="votre_cle_api" # Linux/macOS
```

Le module utilise le SDK officiel `google-genai` et le modèle configuré dans `AssistantConfig.gemini_model`.

## Lancement autonome

```bash
python run_assistant.py
```

Yollande attend son nom avant d'executer une demande vocale. Exemple :

```text
Yollande, rappelle-moi d'envoyer un mail au professeur a 9 h.
```

Exemples de phrases :

- « rappelle-moi d'envoyer un mail au professeur à 9 h »
- « rappelle-moi de préparer une interrogation à 14 h 30 »
- « rappelle-moi de respecter mon heure d'étude personnelle à 20 h »
- « liste mes tâches »
- « marque la tâche mail comme terminée »
- « crée un dossier rapports »
- « lance la calculatrice »

## Intégration dans un projet existant

Copiez le dossier `assistant_voice/` et `requirements.txt` dans votre projet, puis appelez le module depuis le fichier principal existant :

```python
from assistant_voice.command_router import CommandRouter
from assistant_voice.config import AssistantConfig
from assistant_voice.gemini_nlu import GeminiNLU
from assistant_voice.scheduler import ReminderService
from assistant_voice.storage import JsonTaskStorage
from assistant_voice.system_actions import SafeSystemActionExecutor
from assistant_voice.task_manager import TaskManager
from assistant_voice.tts import Speaker

config = AssistantConfig()
speaker = Speaker()
task_manager = TaskManager(JsonTaskStorage(config.tasks_file))
router = CommandRouter(
    GeminiNLU(config),
    task_manager,
    SafeSystemActionExecutor(config),
    speak=speaker.say,
)
reminders = ReminderService(task_manager, speak=speaker.say)
reminders.start()

# Ensuite, branchez router.handle_text(...) sur votre interface existante.
```

## Sécurité des actions système

L'assistant ne reçoit jamais l'autorisation d'exécuter une commande shell libre. Gemini retourne seulement une intention structurée. Python valide ensuite l'action avec une liste blanche :

- chemins limités aux dossiers autorisés ;
- applications limitées à `allowed_apps` ;
- suppression déplacée vers une corbeille interne ;
- confirmation obligatoire pour suppression/renommage.

## Tests

Les tests unitaires évitent le microphone et Gemini pour rester exécutables partout :

```bash
python -m pytest -q
```

## Demarrage automatique bureau

Les fichiers de deploiement sont dans `ops/`.

Windows :

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\create_desktop_shortcut.ps1
powershell -ExecutionPolicy Bypass -File .\ops\windows\install_startup_task.ps1
```

Linux systemd et macOS Launchd :

- `ops/linux/yollande.service`
- `ops/macos/com.hermes.yollande.plist`

Voir `ops/README.md` pour les commandes d'installation.

## Limite connue

Le cahier des charges demande de préférence une analyse vocale locale/offline. Cette version utilise `SpeechRecognition` en mode Google Web Speech pour le prototype en ligne, conformément à la demande d'intégration en ligne. Pour une version strictement offline, remplacez seulement `stt.py` par un adaptateur Vosk : l'architecture ne change pas.

## Correction TTS Windows

Si le micro fonctionne mais que l'assistant ne répond pas oralement, lancez :

```powershell
python diagnostic_tts.py
```

Sous Windows, cette version utilise la voix native Windows SAPI en priorité. Pour la forcer :

```powershell
$env:ASSISTANT_TTS_ENGINE="windows"
python run_assistant.py
```
