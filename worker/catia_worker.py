"""Worker local CATIA : execute les jobs depose par l'agent cloud dans CATIA V5.

A lancer sur le poste Windows qui possede CATIA V5-6R2017 :

    python worker/catia_worker.py

Configuration (variables d'environnement) :
- GITHUB_TOKEN          : token GitHub (PRs sur jobs/ et output/) - requis
- CATIAMISTRAL_REPO     : depot, defaut Cinemaplex/catiamistral
- CATIAMISTRAL_POLL     : intervalle de polling en secondes, defaut 20
- CATIAMISTRAL_DRY_RUN  : 1 = genere les macros sans toucher CATIA (pour tester)
- CATIAMISTRAL_OUTPUT   : dossier de sortie local, defaut ./output
- CATIAMISTRAL_LICENSES : licences CATIA disponibles, defaut "MD2,GSD,ST1"

Deux types de jobs :
- design  : execute une macro VBScript (champ 'vbscript') dans CATIA.
- measure : ouvre les fichiers CATIA listes dans 'inputs' (CATPart, CATProduct,
  CATShape, CGR, STEP/IGES) et releve les donnees dimensionnelles (masse, volume,
  surface, centre de gravite, parametres) pour l'avant-projet de l'agent.
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
LICENSES = os.environ.get("CATIAMISTRAL_LICENSES", "MD2,GSD,ST1")
MEASURE_EXTENSIONS = (
    ".catpart",
    ".catproduct",
    ".catshape",
    ".cgr",
    ".step",
    ".stp",
    ".igs",
    ".iges",
)
STEP_EXTENSIONS = (".step", ".stp", ".igs", ".iges")


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


def download_repo_file(repo_path: str, local_path: str) -> str:
    request = urllib.request.Request(
        API_BASE + "/" + urllib.parse.quote(repo_path),
        method="GET",
        headers={
            "Authorization": "Bearer " + token(),
            "Accept": "application/vnd.github.raw",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
    with open(local_path, "wb") as handle:
        handle.write(payload)
    return local_path


def is_license_error(message: str) -> bool:
    low = message.lower()
    return "license" in low or "licence" in low


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


def extract_dimensions(doc, repo_path: str) -> dict:
    """Releve dimensionnel d'un document CATIA ouvert (PartDesign ou Product)."""
    info: dict = {"source": repo_path}
    try:
        part = doc.Part
        info["document_type"] = "CATPart"
        info["part_name"] = part.Name
        try:
            info["bodies"] = part.Bodies.Count
        except Exception:
            pass
        sketches = 0
        try:
            for i in range(1, part.Bodies.Count + 1):
                try:
                    sketches += part.Bodies.Item(i).Sketches.Count
                except Exception:
                    pass
        except Exception:
            pass
        info["sketches"] = sketches
        try:
            spa = doc.GetWorkbench("SPAWorkbench")
            body = part.Bodies.Item(1) if part.Bodies.Count else part.MainBody
            ref = part.CreateReferenceFromObject(body)
            meas = spa.GetMeasurable(ref)
            for key, getter in (
                ("mass_kg", "GetMass"),
                ("volume_m3", "GetVolume"),
                ("area_m2", "GetArea"),
            ):
                try:
                    info[key] = round(float(getattr(meas, getter)()), 6)
                except Exception:
                    pass
            try:
                import pythoncom

                from win32com.client import VARIANT

                cog = VARIANT(
                    pythoncom.VT_ARRAY | pythoncom.VT_BYREF | pythoncom.VT_R8,
                    [0.0, 0.0, 0.0],
                )
                meas.GetCOG(cog)
                info["cog_m"] = [round(value, 4) for value in list(cog.value)]
            except Exception:
                pass
        except Exception:
            pass
        try:
            params = part.Parameters
            listed = []
            for i in range(1, min(params.Count, 200) + 1):
                try:
                    param = params.Item(i)
                    listed.append({"name": param.Name, "value": str(param.Value)})
                except Exception:
                    pass
            info["parameters"] = listed
        except Exception:
            pass
    except Exception:
        try:
            product = doc.Product
            info["document_type"] = "CATProduct"
            info["product_name"] = product.PartNumber
            try:
                info["children"] = product.Products.Count
            except Exception:
                pass
        except Exception as error:
            info["measure_error"] = str(error)[:500]
    return info


def process_measure_job(job: dict, result: dict) -> None:
    inputs = job.get("inputs") or []
    if not inputs:
        result["status"] = "error"
        result["error"] = "Job measure sans champ 'inputs'."
        return
    if DRY_RUN:
        result["status"] = "dry_run"
        result["inputs"] = inputs
        return
    import win32com.client

    download_dir = os.path.join(OUTPUT_DIR, "downloads")
    os.makedirs(download_dir, exist_ok=True)
    catia = win32com.client.Dispatch("CATIA.Application")
    catia.Visible = True
    dimensions = []
    for repo_path in inputs:
        name = os.path.basename(repo_path)
        ext = os.path.splitext(name)[1].lower()
        if ext not in MEASURE_EXTENSIONS:
            dimensions.append(
                {
                    "source": repo_path,
                    "error": "Extension non supportee : " + (ext or "aucune"),
                }
            )
            continue
        local = os.path.join(download_dir, name)
        try:
            download_repo_file(repo_path, local)
        except Exception as error:
            dimensions.append(
                {"source": repo_path, "error": "telechargement : " + str(error)[:300]}
            )
            continue
        doc = None
        try:
            if ext in STEP_EXTENSIONS:
                doc = catia.Documents.NewFrom(local)
            else:
                doc = catia.Documents.Open(local)
            dimensions.append(extract_dimensions(doc, repo_path))
        except Exception as error:
            entry = {"source": repo_path, "error": str(error)[:800]}
            if is_license_error(entry["error"]):
                entry["license_check"] = LICENSES
            dimensions.append(entry)
        finally:
            try:
                if doc is not None:
                    doc.Close()
            except Exception:
                pass
    result["status"] = "success"
    result["dimensions"] = dimensions
    result["note"] = (
        "Unites SI : masse kg, longueurs/COG en metres, volume m3, surface m2."
    )


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
    result = {
        "job_id": job_id,
        "type": job.get("type", "design"),
        "title": job.get("title", ""),
        "description": job.get("description", ""),
        "licenses_expected": LICENSES,
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if job.get("type") == "measure":
        process_measure_job(job, result)
    else:
        macro_path = os.path.join(OUTPUT_DIR, job_id + ".catvbs")
        with open(macro_path, "w", encoding="latin-1", errors="replace") as handle:
            handle.write(job["vbscript"])
        result["macro_path"] = macro_path

    if result.get("status"):
        pass
    elif DRY_RUN:
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
            message = str(error)[:2000]
            result["status"] = "license_error" if is_license_error(message) else "error"
            result["error"] = message

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
    print(
        f"Worker CATIA : depot {REPO}, polling {POLL_SECONDS}s, "
        f"dry_run={DRY_RUN}, licences={LICENSES}"
    )
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
