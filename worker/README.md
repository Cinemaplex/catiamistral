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

## Execution au demarrage (optionnel)

Planificateur de taches Windows -> au connexion de session, action :
`python.exe C:\chemin\catiamistral\worker\catia_worker.py`.
