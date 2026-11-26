"""Worker local CATIA : execute les jobs depose par l'agent cloud dans CATIA V5.

A lancer sur le poste Windows qui possede CATIA V5-6R2017 :

    python worker/catia_worker.py

Configuration (variables d'environnement) :
- GITHUB_TOKEN          : token GitHub (PRs sur jobs/ et output/) - requis
- CATIAMISTRAL_REPO     : depot, defaut Cinemaplex/catiamistral
- CATIAMISTRAL_POLL     : intervalle de polling en secondes, defaut 20
- CATIAMISTRAL_DRY_RUN  : 1 = genere les macros sans toucher CATIA (pour tester)
- CATIAMISTRAL_OUTPUT   : dossier de sortie local, defaut ./output
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = os.environ.get("CATIAMISTRAL_REPO", "Cinemaplex/catiamistral")
POLL_SECONDS = int(os.environ.get("CATIAMISTRAL_POLL", "20"))
DRY_RUN = os.environ.get("CATIAMISTRAL_DRY_RUN", "0") == "1"
OUTPUT_DIR = os.path.abspath(os.environ.get("CATIAMISTRAL_OUTPUT", "output"))

API_BASE = f"https://api.github.com/repos/{REPO}/contents"
PENDING_DIR = "jobs/pending"
DONE_DIR = "jobs/done"
CAT_SCRIPT_LIBRARY_TYPE_VBSCRIPT = 0


def token() -> str:
    value = os.environ.get("GITHUB_TOKEN")
    if not value:
        sys.exit("Erreur : definissez GITHUB_TOKEN (un token avec acces au depot).")
    return value


def gh(method: str, path: str, body: dict | None = None) -> dict | None:
    request = urllib.request.Request(
        API_BASE + "/" + urllib.parse.quote(path),
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": "Bearer " + token(),
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        print(f"GitHub {method} {path} -> HTTP {error.code} : {error.read()[:200]!r}")
        return None
    return json.loads(payload) if payload else {}


def put_file(path: str, content: bytes, message: str) -> None:
    gh(
        "PUT",
        path,
        {"message": message, "content": base64.b64encode(content).decode()},
    )


def delete_file(path: str) -> None:
    file = gh("GET", path)
    if file and file.get("sha"):
        gh("DELETE", path, {"message": "worker: " + path, "sha": file["sha"]})


def catia_metrics(doc) -> dict:
    metrics = {}
    try:
        part = doc.Part
        metrics["part_name"] = part.Name
        metrics["bodies"] = part.Bodies.Count
        try:
            body = part.Bodies.Item(1)
            spa = doc.GetWorkbench("SPAWorkbench")
            meas = spa.GetMeasurable(body)
            metrics["mass_kg"] = round(float(meas.GetMass()), 6)
        except Exception:
            pass
    except Exception as error:
        metrics["metrics_error"] = str(error)
    return metrics


def catia_screenshot(doc, path: str) -> str | None:
    try:
        viewer = doc.ActiveWindow.ActiveViewer
        viewer.CaptureToFile("jpg", path)
        return path
    except Exception:
        return None


def run_in_catia(macro_path: str):
    import win32com.client

    catia = win32com.client.Dispatch("CATIA.Application")
    catia.Visible = True
    catia.SystemService.ExecuteScript(macro_path, CAT_SCRIPT_LIBRARY_TYPE_VBSCRIPT, [])
    return catia.ActiveDocument


def process_job(job: dict) -> None:
    job_id = job["job_id"]
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    macro_path = os.path.join(OUTPUT_DIR, job_id + ".catvbs")
    with open(macro_path, "w", encoding="latin-1", errors="replace") as handle:
        handle.write(job["vbscript"])

    result = {
        "job_id": job_id,
        "title": job.get("title", ""),
        "description": job.get("description", ""),
        "macro_path": macro_path,
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if DRY_RUN:
        result["status"] = "dry_run"
    else:
        try:
            doc = run_in_catia(macro_path)
            result["status"] = "success"
            result["metrics"] = catia_metrics(doc)
            shot = catia_screenshot(doc, os.path.join(OUTPUT_DIR, job_id + ".jpg"))
            if shot:
                result["screenshot_local"] = shot
        except Exception as error:
            result["status"] = "error"
            result["error"] = str(error)[:2000]

    put_file(
        f"{DONE_DIR}/{job_id}/result.json",
        json.dumps(result, indent=2, ensure_ascii=True).encode(),
        "worker: resultat " + job_id,
    )
    shot_path = result.get("screenshot_local")
    if shot_path and os.path.exists(shot_path):
        with open(shot_path, "rb") as handle:
            put_file(
                f"{DONE_DIR}/{job_id}/screenshot.jpg",
                handle.read(),
                "worker: capture " + job_id,
            )
        result["screenshot_repo"] = f"{DONE_DIR}/{job_id}/screenshot.jpg"
        put_file(
            f"{DONE_DIR}/{job_id}/result.json",
            json.dumps(result, indent=2, ensure_ascii=True).encode(),
            "worker: maj capture " + job_id,
        )
    delete_file(f"{PENDING_DIR}/{job_id}.json")
    print(f"Job {job_id} termine : {result['status']}")


def main() -> None:
    print(f"Worker CATIA : depot {REPO}, polling {POLL_SECONDS}s, dry_run={DRY_RUN}")
    while True:
        pending = gh("GET", PENDING_DIR)
        if pending is None:
            print("File jobs/pending introuvable ou depot inaccessible.")
        else:
            for item in pending:
                if item.get("type") != "file" or not item["name"].endswith(".json"):
                    continue
                job_file = gh("GET", f"{PENDING_DIR}/{item['name']}")
                if not job_file or not job_file.get("content"):
                    continue
                try:
                    job = json.loads(base64.b64decode(job_file["content"]))
                except (ValueError, KeyError):
                    continue
                try:
                    process_job(job)
                except Exception as error:
                    print(f"Job {job.get('job_id')} en echec : {error}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
