# CATIA V5 + Mistral AI

Pont entre l'API Mistral et CATIA V5 (V5-6R2017) : décrivez une pièce en français,
et le script génère une macro VBScript puis l'exécute dans CATIA via son API COM.

## Fonctionnement

- Les serveurs Mistral génèrent le **code d'automatisation** (macro VBScript).
- CATIA, sur votre poste Windows, exécute la macro et calcule la géométrie 3D localement.

## Fichiers

- `main.py` : complétion de chat minimale (test de connexion à l'API Mistral).
- `catia_bridge.py` : génération + exécution d'une macro CATIA à partir d'une description.

## Installation (Windows, Python >= 3.9)

```powershell
pip install mistralai
pip install pywin32
```

## Clé API

1. Connectez-vous sur <https://console.mistral.ai> (Studio)
2. Menu **API Keys** -> **Create new key**, copiez la clé.
3. Définissez-la dans PowerShell :

```powershell
setx MISTRAL_API_KEY "votre-cle"
```

Fermez puis rouvrez le terminal après `setx`, ou pour la session courante uniquement :

```powershell
$env:MISTRAL_API_KEY = "votre-cle"
```

## Exécution (depuis ce dossier)

```powershell
python main.py
python catia_bridge.py "crée une plaque rectangulaire 100x50x10 mm avec 4 trous percés de M8 aux coins"
```

La macro générée est enregistrée dans `generated_macro.catvbs`, affichée avec son explication,
et exécutée dans CATIA après confirmation (`o`).

## Options

- `MISTRAL_MODEL` : modèle à utiliser (défaut `mistral-small-latest`), ex. `mistral-large-latest`.
- `CATIA_MACRO_PATH` : chemin du fichier macro généré (défaut `generated_macro.catvbs`).

## Prérequis CATIA

- CATIA V5-6R2017 installé sur la même machine Windows, avec la licence incluant l'automatisation.
- CATIA est démarré automatiquement par le script s'il est fermé.
- Relisez toujours la macro générée avant de l'exécuter : il s'agit de code exécuté dans CATIA.
