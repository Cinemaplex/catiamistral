# Worker local CATIA

`catia_worker.py` s'execute sur le poste Windows qui possede CATIA V5-6R2017.
Il surveille le dossier `jobs/pending/` du depot GitHub, execute chaque macro
VBScript dans CATIA via COM, puis publie result.json (+ capture .jpg) dans
`jobs/done/<job_id>/` puis supprime le job pending.

Deux types de jobs :
- **design** : execution d'une macro VBScript dans CATIA.
- **measure** (avant-projet) : telecharge les fichiers listes dans `inputs`
  (`data/`), les ouvre dans CATIA (import STEP via `Documents.NewFrom` si ST1)
  et releve masse, volume, surface, centre de gravite, corps, esquisses et
  parametres (unites SI) publies dans `dimensions` de result.json.

Licences attendues sur la station (configurables) :

| Licence | Role |
| --- | --- |
| MD2 | Part/Product Design, esquisses, volumes |
| GSD | Generative Shape Design (wireframe, surfaces) |
| ST1 | import STEP (.step/.stp) |

Pour adapter : `$env:CATIAMISTRAL_LICENSES = "MD2,GSD,ST1"`.
Si une licence manque, le resultat porte le statut `license_error` avec le
message CATIA ; CATIA doit rester licence au titre du poste (Dassault).

## Fichiers clients : reseau local ou GitHub (transparent)

Definissez `CATIAMISTRAL_DATA_DIR` (ex. `\\serveur\donnees`) : le worker
cherche chaque fichier CAO du releve d'abord sur ce partage, sinon le
telecharge depuis GitHub. L'origine reelle de chaque fichier est tracee dans
result.json (champ `origin`). Aucune regle a changer au quotidien.

Diagnostic des origines (web vs reseau) :

```powershell
powershell -ExecutionPolicy Bypass -File worker\check_sources.ps1
```

## Premier lancement

```powershell
cd catiamistral
pip install pywin32
$env:GITHUB_TOKEN = "votre-token"
python worker\catia_worker.py
```

Test sans CATIA :

```powershell
$env:CATIAMISTRAL_DRY_RUN = "1"
python worker\catia_worker.py
```

## Ce que fait le worker sur chaque job

1. Ecrit la macro dans `output/<job_id>.catvbs` (encodage latin-1, comme les
   macros CATIA classiques).
2. Se connecte a CATIA (`Dispatch("CATIA.Application")`, demarre CATIA si ferme)
   et execute la macro via `SystemService.ExecuteScript`.
3. Recupere : nom de la piece, nombre de corps, masse (SPAWorkbench si licence),
   capture de la vue active.
4. Publie `jobs/done/<job_id>/result.json` et `screenshot.jpg`, supprime le job
   pending.

## Verification de l'installation (avant le 1er lancement)

Teste Python, pywin32, le token, le depot, la presence de CATIA, les licences,
le dossier reseau optionnel et les droits d'ecriture - et affiche quoi faire
pour chaque anomalie :

```powershell
powershell -ExecutionPolicy Bypass -File worker\verify_install.ps1
```

## Execution au demarrage (optionnel)

Planificateur de taches Windows -> au connexion de session, action :
`python.exe C:\chemin\catiamistral\worker\catia_worker.py`.

## Desinstallation propre (repartir de zero)

```powershell
powershell -ExecutionPolicy Bypass -File worker\uninstall_worker.ps1
```

Le script arrete le worker, supprime la tache planifiee, efface les variables
d'environnement du projet, desinstalle pywin32 et propose la suppression du
dossier du projet (confirmation demandee). CATIA, Windows et Python ne sont
pas touches. Le depot GitHub reste en ligne (a supprimer web si besoin).
Option `-KeepToken` : conserve `GITHUB_TOKEN` pour re-installer vite.
