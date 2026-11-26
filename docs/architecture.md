# Architecture catiamistral

## Vue d'ensemble

```
Agent (cloud, mistralai-agents)     Worker (Windows, CATIA V5-6R2017)
        |                                       |
        |  1. jobs/pending/<id>.json  (PUT)     |
        |-------------------------------------->|
        |            2. ExecuteScript + mesures + screenshot
        |  3. jobs/done/<id>/result.json  (PUT) |
        |<--------------------------------------|
        |  4. get_job_result() -> iteration     |
```

Composants :

- `main.py` + `agent_tools.py` + `skills/catia_v5/SKILL.md` : l'agent.
  Deploye comme worker managed (`mistral agents deploy`), il traite une demande
  de conception en plusieurs jobs CATIA successifs.
- `worker/catia_worker.py` : process resident sur le poste CATIA. Uniquement des
  appels sortants HTTPS vers api.github.com. Ne jamais l'exposer sur le reseau.
- `data/` : PDF techniques clients (source des exigences).
- `jobs/` : file d'attente. `pending/` = a executer, `done/` = resultats.
- `output/` (poste seulement) : macros .catvbs, fichiers .CATPart, captures.

## Pourquoi une file GitHub plutot qu'une API directe

- L'agent cloud ne peut pas joindre votre poste (pas d'entree reseau) et votre
  poste ne doit pas s'exposer.
- Le depot sert d'agent de message auditable : chaque macro et chaque resultat
  est versionne, consultable et rejouable.
- Aucune infrastructure a heberger : GitHub est le seul intermediaire.

## Cycle d'un job

1. L'agent genere un VBScript autonome (voir `skills/catia_v5/SKILL.md` pour les
   motifs valides en V5-6R2017) et le depose dans `jobs/pending/<id>.json`.
2. Le worker (polling ~20 s) telecharge le job, ecrit la macro en latin-1 dans
   `output/`, la soumet a `CATIA.Application.SystemService.ExecuteScript`.
3. Le worker mesure la piece (nom, corps, masse si SPA disponible), capture la
   vue active, et publie `jobs/done/<id>/result.json` (+ `screenshot.jpg`).
4. L'agent lit le resultat, corrige/itere via un nouveau job, ou livre le resume.
5. Le worker supprime le fichier pending ; l'historique complet reste dans git.

## Limites connues

- Un job = une macro autonome : l'etat persistant de la conception est porte par
  les fichiers CATIA sur le poste (le worker, comme l'utilisateur, travaille
  document par document).
- Les perimetres necessitant GSD avance ou Knowledgeware expert peuvent demander
  d'enrichir `skills/catia_v5/SKILL.md` avec vos macros internes reconnues.
- Le token GitHub du worker est stocke dans l'environnement Windows : utiliser un
  fine-grained token limite a ce depot.
