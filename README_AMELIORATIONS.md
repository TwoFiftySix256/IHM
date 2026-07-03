# Assistant vocal - version plus humaine

Cette version ajoute :

- suppression vocale de toutes les tâches ;
- suppression/terminaison par position : « supprime la deuxième », « marque la première terminée » ;
- dialogue en plusieurs étapes : « ajoute une tâche » puis titre puis heure ;
- recherche intelligente de dossiers : Bureau, Documents, Téléchargements, Images, ou dossier par nom ;
- gestion des résultats ambigus : « le premier », « le deuxième » ;
- réponses vocales plus naturelles ;
- règles locales prioritaires pour les actions critiques afin d'éviter les erreurs de Gemini.

## Installation

```powershell
cd E:\assistant_vocal_humain\assistant_vocal_extension_humain
conda activate assistant-vocal
python -m pip install -r requirements.txt
python run_assistant.py
```

## .env conseillé

```env
GEMINI_API_KEY=COLLE_TA_CLE_ICI
ASSISTANT_TTS_ENGINE=windows
ASSISTANT_ALLOWED_ROOTS=E:\;C:\Users\TON_NOM\Desktop;C:\Users\TON_NOM\Documents;C:\Users\TON_NOM\Downloads
```

Remplace `TON_NOM` par le nom de session Windows.

## Exemples vocaux

- « ajoute une tâche »
- « préparer l'interrogation »
- « à 18 h 30 »
- « liste mes tâches »
- « supprime la deuxième »
- « oui »
- « supprime toutes les tâches »
- « ouvre mes documents »
- « ouvre téléchargements »
- « ouvre le dossier cours »
- « le premier » si plusieurs résultats sont proposés
