# DocPilote

Un clic droit sur un document, et rien d'autre.

DocPilote ajoute une action de menu contextuel dans votre gestionnaire de
fichiers (Nautilus, Nemo, Thunar, Dolphin, Windows Explorer) pour interroger
vos documents (PDF, Word, Excel, PowerPoint, OpenDocument, texte, RTF) via
l'API Mistral : résumé, checklist, détection de risques, extraction JSON,
transformation, comparaison, etc. Pas de chatbot, pas d'explorateur, pas de
superflu.

Service officiel hébergé : **https://docpilote.prestalibre.org**

## Pourquoi ce dépôt est open source

Le code de DocPilote est entièrement public sous licence **AGPLv3**. Rien
n'est caché : vous pouvez lire, auditer, modifier et redéployer l'intégralité
du client et du serveur.

Ce que le projet open source ne fournit pas : l'hébergement clé en main, la
clé API Mistral prête à l'emploi, les mises à jour automatiques (dépôt apt),
et le support. C'est ce que finance l'abonnement DocPilote Pro sur
[docpilote.prestalibre.org](https://docpilote.prestalibre.org) — le service
géré, pas le code.

Si vous voulez self-hoster : il vous faut votre propre clé API Mistral et un
serveur pour faire tourner `server/main.py`. Tout est documenté ci-dessous.

## Structure du dépôt

```
client/
  docpilote_client.py                    # Client Linux (appelle l'API, affiche le résultat)
  docpilote-run.sh                       # Wrapper de lancement
  docpilote-activate-license.desktop     # Entrée menu "Activer une licence"
  nautilus/docpilote_nautilus_extension.py
  nemo/docpilote_nemo_extension.py
  thunar/docpilote_thunar_extension.py
  kio/docpilote.desktop                  # Service menu KDE/Dolphin
  windows/docpilote_client_windows.py    # Client Windows

server/
  main.py               # API FastAPI (relai Mistral, quotas, licences, Stripe)
  requirements.txt
  .env.example          # Variables d'environnement à renseigner (aucun secret)

packaging/
  debian/                # control, postinst, postrm pour le .deb
  docpilote.nsi          # Installeur Windows NSIS
```

## Lancer le serveur en local

```bash
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# éditez .env avec votre clé API Mistral et vos propres secrets
uvicorn main:app --host 127.0.0.1 --port 3014
```

**Ne commitez jamais votre fichier `.env`** — il contient vos clés API et
secrets. Il est déjà exclu par `.gitignore`.

## Client Linux

Le client (`docpilote_client.py`) et les extensions de gestionnaire de
fichiers appellent l'API configurée via `API_URL` (par défaut le service
officiel). Pour pointer vers votre propre serveur, modifiez `API_URL` dans
`client/docpilote_client.py` avant packaging.

Packaging `.deb` : voir `packaging/debian/`.

## Licence

Ce projet est publié sous licence **GNU Affero General Public License v3.0**
(AGPLv3) — voir [LICENSE](LICENSE). En résumé : vous êtes libres d'utiliser,
modifier et redistribuer ce code, y compris en le faisant tourner en tant que
service réseau, à condition de republier vos modifications sous la même
licence.

Le nom **DocPilote** et son identité visuelle restent la propriété de
Prestalibre et ne sont pas couverts par la licence AGPLv3 — merci de
renommer votre fork si vous le distribuez.

## Contact

Une question sur le traitement des données ou sur le projet ?
Écrivez à prestalibre26400@gmail.com ou ouvrez une issue sur ce dépôt.
