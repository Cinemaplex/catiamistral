import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from mistralai import agents

REPO = os.environ.get("CATIAMISTRAL_REPO", "Cinemaplex/catiamistral")
API_BASE = f"https://api.github.com/repos/{REPO}/contents"
PENDING_DIR = "jobs/pending"
DONE_DIR = "jobs/done"
DATA_DIR = "data"
REFERENCE_PATH = "skills/catia_v5/SKILL.md"
CLOUD_JITTER_MSG = "Depot GitHub indisponible, reessaie plus tard."


def _github_headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise agents.ToolError(
            "GITHUB_TOKEN n'est pas defini. Le token doit etre fourni au deploiement "
            "via --secret-binding GITHUB_TOKEN=secret:workspace:<nom>, ou exporte "
            "localement."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh_request(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        method=method,
        data=data,
        headers={**_github_headers(), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        raise agents.ToolError(f"GitHub API {error.code} sur {method} {url} : {detail}") from error
    except urllib.error.URLError as error:
        raise agents.ToolError(CLOUD_JITTER_MSG) from error
    return json.loads(payload) if payload else {}


def _put_file(path: str, content: bytes, message: str) -> dict:
    return _gh_request(
        "PUT",
        API_BASE + "/" + urllib.parse.quote(path),
        {
            "message": message,
            "content": base64.b64encode(content).decode(),
        },
    )


def _get_file(path: str) -> dict:
    return _gh_request("GET", API_BASE + "/" + urllib.parse.quote(path))


def _mistral_client():
    try:
        from mistralai.workflows.client import get_mistral_client

        return get_mistral_client()
    except Exception:
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise agents.ToolError(
                "Client Mistral indisponible : ni MISTRAL_API_KEY ni client de"
                " deploiement. Definis MISTRAL_API_KEY localement."
            )
        from mistralai import Mistral

        return Mistral(api_key=api_key)


@agents.tool(model_access="direct")
def read_catia_reference() -> str:
    """Renvoie la reference complete du modele objet CATIA V5-6R2017 (VBScript)."""
    ref = Path(__file__).resolve().parent / REFERENCE_PATH
    return ref.read_text(encoding="utf-8")


@agents.tool(model_access="direct")
def ingest_pdf_spec(pdf_path_in_repo: str) -> str:
    """Lit un PDF technique du depot (dossier data/) par OCR et renvoie son texte.
    pdf_path_in_repo est le chemin du fichier dans le depot, ex. 'data/dossier_client.pdf'.
    """
    if not pdf_path_in_repo.startswith(DATA_DIR + "/"):
        raise agents.ToolError(
            f"Les donnees clients sont attendues sous '{DATA_DIR}/'."
        )
    file = _get_file(pdf_path_in_repo)
    content = base64.b64decode(file.get("content") or "")
    if not content:
        raise agents.ToolError(f" '{pdf_path_in_repo}' est vide ou inexistant.")
    mime = mimetypes.guess_type(pdf_path_in_repo)[0] or "application/pdf"
    data_uri = "data:" + mime + ";base64," + base64.b64encode(content).decode()
    client = _mistral_client()
    try:
        response = client.ocr.process(
            model="mistral-ocr-latest",
            document={"document_url": data_uri},
        )
    except Exception as error:
        raise agents.ToolError(f"OCR Mistral en echec sur ce PDF : {error}") from error
    pages = getattr(response, "pages", None) or []
    return "\n\n".join(p.markdown or "" for p in pages)


@agents.tool(model_access="direct")
def create_design_job(title: str, description: str, vbscript: str) -> dict:
    """Depose une macro VBScript dans la file d'attente : le worker local l'executera
    dans CATIA V5-6R2017. Renvoie {'job_id': ...} a suivre avec get_job_result().
    """
    if "Option Explicit" not in vbscript:
        raise agents.ToolError("La macro doit contenir 'Option Explicit'.")
    if any(ord(c) > 255 for c in vbscript):
        raise agents.ToolError(
            "La macro doit rester en caracteres latins (encodage latin-1 cote worker)."
        )
    job_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    job = {
        "job_id": job_id,
        "title": title,
        "description": description,
        "vbscript": vbscript.rstrip() + "\n",
        "created_by": "agent",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _put_file(
        f"{PENDING_DIR}/{job_id}.json",
        json.dumps(job, indent=2).encode(),
        f"agent: job {job_id} {title[:60]}",
    )
    return {"job_id": job_id, "status": "queued"}


@agents.tool(model_access="direct")
def list_design_jobs() -> dict:
    """Liste les jobs en attente et les job récemment terminés dans le dépôt."""
    def _list(folder: str) -> list[str]:
        try:
            listing = _gh_request("GET", API_BASE + "/" + urllib.parse.quote(folder))
        except agents.ToolError as error:
            if "404" in str(error):
                return []
            raise
        return [item["name"].removesuffix(".json") for item in listing if item.get("type") == "file"]

    return {"pending": _list(PENDING_DIR), "done": _list(DONE_DIR)}


@agents.tool(model_access="direct")
def read_repo_file(path_in_repo: str) -> dict:
    """Lit un fichier du dépôt (texte ou image). Les images sont renvoyées
    comme data URI base64, le texte comme chaîne UTF-8."""
    file = _get_file(path_in_repo)
    content = base64.b64decode(file.get("content") or "")
    mime = mimetypes.guess_type(path_in_repo)[0] or ""
    if mime.startswith("image/"):
        return {
            "path": path_in_repo,
            "content_type": "image",
            "content": "data:" + mime + ";base64," + base64.b64encode(content).decode(),
        }
    try:
        text = content.decode("utf-8")
        content_type = "text"
    except UnicodeDecodeError:
        text = base64.b64encode(content).decode()
        content_type = "binary"
    return {"path": path_in_repo, "content_type": content_type, "content": text}


@agents.tool(model_access="direct")
def get_job_result(job_id: str) -> dict:
    """Lit le resultat d'un job. Renvoie status 'pending' si le worker n'a pas
    encore fini, sinon le statut d'execution dans CATIA, les mesures et les chemins.
    """
    try:
        return _get_file(f"{DONE_DIR}/{job_id}/result.json")
    except agents.ToolError as error:
        if "404" in str(error):
            return {"job_id": job_id, "status": "pending"}
        raise
