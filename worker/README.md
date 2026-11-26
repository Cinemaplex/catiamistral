# Worker local CATIA

`catia_worker.py` s'execute sur le poste Windows qui possede CATIA V5-6R2017.
Il surveille le dossier `jobs/pending/` du depot GitHub, execute chaque macro
VBScript dans CATIA via COM, puis publie result.json (+ capture .jpg) dans
`jobs/done/<job_id>/` puis supprime le job pending.

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
