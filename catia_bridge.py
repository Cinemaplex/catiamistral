import os
import re
import sys

from mistralai.client import Mistral

MODEL = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
MACRO_PATH = os.environ.get("CATIA_MACRO_PATH", "generated_macro.catvbs")

CAT_SCRIPT_LIBRARY_TYPE_VBSCRIPT = 0

SYSTEM_PROMPT = """Tu es un expert en automatisation de CATIA V5 via son API COM.
Ta réponse doit contenir exactement une macro VBScript (.catvbs) complète, prête à être
exécutée par CATIA.Application.SystemService.ExecuteScript.

Règles :
- Entoure le code d'un bloc ```vbscript ... ```
- Utilise uniquement le modèle objet d'automatisation CATIA V5 : CATIA (racine),
  Documents, PartDocument, Part, HybridBody, HybridShapeFactory, Sketch,
  Sketcher factory, Pad, Pocket, Shaft, Body, etc.
- Démarre par : Option Explicit et Dim CATIA, puis CATIA est l'application déjà lancée
  (ne pas faire de CreateObject("CATIA.Application") nécessairement, mais autorisé si CATIA n'est pas démarré).
- Crée un nouveau PartDocument si aucun document actif approprié n'existe.
- Pas d'interaction utilisateur (pas de InputBox, pas de MsgBox bloquante).
- Après le bloc de code, ajoute une ligne 'EXPLICATION:' suivie d'une phrase en français
  décrivant ce que fait la macro."""


def generate_macro(client: Mistral, user_request: str) -> tuple[str, str]:
    response = client.chat.complete(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_request},
        ],
    )
    text = response.choices[0].message.content or ""
    match = re.search(r"```(?:vbscript)?\s*(.*?)```", text, re.DOTALL)
    if not match:
        raise ValueError("Aucun bloc de code VBScript dans la réponse du modèle.")
    code = match.group(1).strip()
    explanation = text.split("EXPLICATION:")[-1].strip()
    return code, explanation


def run_in_catia(script_path: str) -> None:
    import win32com.client

    catia = win32com.client.Dispatch("CATIA.Application")
    catia.Visible = True
    catia.SystemService.ExecuteScript(script_path, CAT_SCRIPT_LIBRARY_TYPE_VBSCRIPT, [])


def main() -> None:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        sys.exit("Erreur : définissez MISTRAL_API_KEY, par exemple : export MISTRAL_API_KEY=\"votre-clé\"")

    user_request = " ".join(sys.argv[1:]) or input("Décrivez la pièce à modéliser : ")

    client = Mistral(api_key=api_key)
    code, explanation = generate_macro(client, user_request)

    with open(MACRO_PATH, "w", encoding="latin-1") as f:
        f.write(code)

    print(f"Macro générée ({MODEL}) -> {MACRO_PATH}")
    print(f"Explication : {explanation}")

    if sys.platform != "win32":
        print("CATIA V5 n'est automatisable que sous Windows : exécutez ce script sur votre poste pour lancer la macro.")
        return

    confirm = input("Exécuter la macro dans CATIA maintenant ? [o/N] ")
    if confirm.strip().lower() == "o":
        run_in_catia(MACRO_PATH)
        print("Macro exécutée dans CATIA.")


if __name__ == "__main__":
    main()
