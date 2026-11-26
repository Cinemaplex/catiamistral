# CATIA V5 + Mistral (catiamistral)

Agent de conception dans le cloud (Vibe) qui pilote une station **CATIA V5-6R2017**
via une file d'attente GitHub. Description de piece en francais -> macro VBScript
generee par l'agent -> execution dans CATIA sur votre poste -> resultats, mesures
et captures remontes a l'agent qui itere.

```
+---------------------- Vibe / Mistral (cloud) ----------------------+
|  Agent "catiamistral" (mistralai-agents, main.py)                   |
|  - lit vos exigences clients PDF (OCR) dans data/                   |
|  - planifie la conception, genere les macros VBScript               |
|  - depose les jobs, lit les resultats, itere                        |
+--------------------- depot GitHub ----------------------------------+
|        jobs/pending/ (agent -> worker)   jobs/done/ (worker -> agent)|
+---------------------- poste Windows ---------------------------------+
|  Worker local (CATIA V5-6R2017), worker/catia_worker.py             |
|  execute la macro, mesure (masse, corps), capture un jpg, publie    |
+-----------------------------------------------------------------------+
```

Aucun port ouvert, aucun tunnel : votre poste ne fait que des connexions sortantes
vers GitHub.

## 1. Cote cloud : deployer l'agent

```bash
# depot pousse sur GitHub, connecteur GitHub actif dans Mistral Studio
pip install mistral-cli
mistral agents deploy --secret-binding GITHUB_TOKEN=secret:workspace:github-token
```

Le deploiement construit l'image depuis le `Dockerfile` et enregistre l'agent sous
le nom `catiamistral`. Creer au prealable un secret d'espace de travail
`github-token` (console.mistral.ai -> Secrets) contenant un token GitHub fine-grained
avec acces contenus (lecture/ecriture) a ce depot.

Discuter avec l'agent : `mistral agents chat catiamistral`, ou depuis Vibe Web
(Managed Agents dans Mistral Studio).

## 2. Cote poste : lancer le worker CATIA

Sur le poste Windows avec CATIA V5-6R2017 (Python >= 3.10) :

```powershell
pip install pywin32
setx GITHUB_TOKEN "votre-token-github"
python worker\catia_worker.py
```

- `CATIAMISTRAL_DRY_RUN=1` pour tester le flux complet sans toucher CATIA.
- Les fichiers produits sont sauvegardes dans `output/` et la capture publiee dans
  `jobs/done/<job_id>/screenshot.jpg` (lue ensuite par l'agent).

## 3. Donnees techniques clients

Deposez vos PDF (dossiers techniques, plans, cahiers des charges) dans le dossier
`data/` du depot. L'agent les lit par OCR (`ingest_pdf_spec`) et en extrait
dimensions, tolerances et regles avant de concevoir.

## Utilisation stand-alone (sans agent deploye)

L'ancien pont local reste disponible :

```powershell
python catia_bridge.py "cree une plaque rectangulaire 100x50x10 mm avec 4 trous M8 aux coins"
```

## Variables d'environnement

| Variable | Cote | Role |
| --- | --- | --- |
| `GITHUB_TOKEN` | agent + worker | acces depot (jobs, resultats, data) |
| `MISTRAL_API_KEY` | agent local | API Mistral (le deploiement managed n'en a pas besoin) |
| `CATIAMISTRAL_REPO` | les deux | defaut `Cinemaplex/catiamistral` |
| `CATIAMISTRAL_POLL` | worker | polling en secondes (20) |
| `CATIAMISTRAL_DRY_RUN` | worker | 1 = sans CATIA |
| `CATIAMISTRAL_OUTPUT` | worker | dossier local de sortie (`./output`) |
| `MISTRAL_MODEL` | catia_bridge.py | modele du pont stand-alone |
| `CATIA_MACRO_PATH` | catia_bridge.py | chemin de la macro generee |

## Securite

- Utilisez un token GitHub fine-grained limite a ce depot (contenus RW).
- Relisez les macros dans `jobs/pending/` : ce sont des scripts executes dans CATIA.
- Les donnees clients ne transitent que par votre depot : ne deposer dans `data/`
  que ce que vous avez le droit de versionner.
