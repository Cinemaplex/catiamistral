import os
import sys

from mistralai.client import Mistral


def main() -> None:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        sys.exit("Erreur : définissez MISTRAL_API_KEY, par exemple : export MISTRAL_API_KEY=\"votre-clé\"")

    client = Mistral(api_key=api_key)

    response = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "user", "content": "Qui est le meilleur peintre français ?"},
        ],
    )

    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
