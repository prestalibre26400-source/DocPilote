#!/usr/bin/env python3
"""DocPilote (Windows) — orchestrateur client.
Appelé par le menu contextuel Explorer avec : action fichier1 [fichier2].
Affiche une fenêtre "Analyse en cours..." pendant l'appel API,
puis le résultat dans une fenêtre Tkinter (Copier / Exporter / Fermer).

Port direct de la logique du client Linux (docpilote_client.py, GTK/zenity)
vers Tkinter (inclus nativement avec Python, aucune dépendance graphique
supplémentaire) pour permettre une compilation autonome via PyInstaller.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

API_URL = "https://docpilote.prestalibre.org/api"
PRICING_URL = "https://docpilote.prestalibre.org/#pricing"

CLIENT_VERSION = "1.0.6"

APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
LICENSE_FILE = os.path.join(APPDATA, "DocPilote", "license.key")
VERSION_CHECK_CACHE = os.path.join(LOCALAPPDATA, "DocPilote", "last_version_check.json")
VERSION_CHECK_INTERVAL_S = 12 * 3600  # ne vérifie qu'une fois toutes les 12h max

TRANSFORM_TARGETS = [
    ("mail", "Mail"),
    ("procedure", "Procédure"),
    ("synthese", "Synthèse"),
    ("tableau", "Tableau"),
    ("presentation", "Présentation"),
    ("compte_rendu", "Compte rendu"),
]

TITLES = {
    "activate-license": "Activer une licence",
    "summarize": "Résumer",
    "respond": "Préparer une réponse",
    "explain": "Explique-moi ce document",
    "decide": "Actions à entreprendre",
    "risks": "Risques détectés",
    "checklist": "Checklist",
    "extract": "Données extraites (JSON)",
    "ask": "Réponse",
    "transform": "Transformer",
    "compare": "Comparer",
}


def get_device_id():
    """Identifiant stable de la machine, hashe (jamais envoye en clair) : sert
    a lier une licence a un appareil (voir check_device_binding cote API).
    MachineGuid (HKLM\\SOFTWARE\\Microsoft\\Cryptography) est l'identifiant
    standard Windows, genere a l'installation de l'OS, stable tant que
    Windows n'est pas reinstalle. Best-effort : si illisible (permissions,
    cle absente), on retombe sur une chaine vide -> pas de liaison possible,
    pas de blocage cote client (le serveur traite ca comme un client sans
    support device)."""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
        ) as key:
            raw, _ = winreg.QueryValueEx(key, "MachineGuid")
        if raw:
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    except Exception:  # noqa: BLE001
        pass
    return ""


# ---------------------------------------------------------------------------
# Utilitaires fichiers de licence / cache
# ---------------------------------------------------------------------------

def load_license_key():
    if os.path.isfile(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, encoding="utf-8") as f:
                return f.read().strip()
        except Exception:  # noqa: BLE001
            return ""
    return ""


def save_license_key(key):
    os.makedirs(os.path.dirname(LICENSE_FILE), exist_ok=True)
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        f.write(key.strip())


def basename_label(files):
    names = [os.path.basename(f) for f in files]
    return " / ".join(names)


# ---------------------------------------------------------------------------
# Appels API (identiques au client Linux : mêmes endpoints/paramètres)
# ---------------------------------------------------------------------------

def api_call(files, action, question=None, target=None):
    import requests

    license_key = load_license_key()
    device_id = get_device_id()

    if action == "compare":
        with open(files[0], "rb") as f1, open(files[1], "rb") as f2:
            resp = requests.post(
                f"{API_URL}/compare",
                files={"file1": f1, "file2": f2},
                data={"license_key": license_key, "device_id": device_id},
                timeout=120,
            )
    elif action == "extract":
        with open(files[0], "rb") as f:
            resp = requests.post(
                f"{API_URL}/extract",
                files={"file": f},
                data={"license_key": license_key, "device_id": device_id},
                timeout=120,
            )
    elif action == "ask":
        with open(files[0], "rb") as f:
            resp = requests.post(
                f"{API_URL}/ask",
                files={"file": f},
                data={"question": question, "license_key": license_key, "device_id": device_id},
                timeout=120,
            )
    elif action == "transform":
        with open(files[0], "rb") as f:
            resp = requests.post(
                f"{API_URL}/transform",
                files={"file": f},
                data={"target": target, "license_key": license_key, "device_id": device_id},
                timeout=120,
            )
    else:
        with open(files[0], "rb") as f:
            resp = requests.post(
                f"{API_URL}/process",
                files={"file": f},
                data={"plugin": action, "license_key": license_key, "device_id": device_id},
                timeout=120,
            )

    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError("Réponse invalide du service")

    if resp.status_code == 402:
        raise RuntimeError(
            data.get("detail", "Quota gratuit atteint")
            + "\n\nActivez une licence (menu Démarrer → DocPilote — Activer une "
            "licence) ou abonnez-vous : " + PRICING_URL
        )

    if resp.status_code != 200:
        raise RuntimeError(data.get("detail", "Erreur du service DocPilote"))

    return data.get("result", "")


# ---------------------------------------------------------------------------
# Indicateur "Analyse en cours..." (équivalent du curseur "progress" GTK
# côté Linux : Tkinter n'offre pas de grab de curseur système multi-fenêtre
# fiable sous Windows, donc on affiche une petite fenêtre toujours au premier
# plan avec une barre de progression indéterminée pendant le traitement)
# ---------------------------------------------------------------------------

def run_with_busy_window(work_fn, message="DocPilote analyse le document..."):
    result_box = {}
    done_event = threading.Event()

    def worker():
        try:
            result_box["value"] = work_fn()
        except Exception as exc:  # noqa: BLE001
            result_box["error"] = str(exc)
        done_event.set()

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    root = tk.Tk()
    root.withdraw()
    busy = tk.Toplevel(root)
    busy.title("DocPilote")
    busy.attributes("-topmost", True)
    busy.resizable(False, False)
    busy.geometry("360x90")
    try:
        busy.eval("tk::PlaceWindow . center")
    except Exception:  # noqa: BLE001
        pass
    tk.Label(busy, text=message, font=("Segoe UI", 10), pady=14).pack()
    bar = ttk.Progressbar(busy, mode="indeterminate", length=280)
    bar.pack(pady=6)
    bar.start(12)

    # Garde-fou : force la fermeture après 130s si le thread ne répond jamais
    watchdog_deadline = time.time() + 130

    def poll():
        if done_event.is_set():
            root.quit()
            return
        if time.time() > watchdog_deadline:
            result_box.setdefault(
                "error", "Délai d'attente dépassé (le service ne répond pas)."
            )
            root.quit()
            return
        root.after(100, poll)

    root.after(100, poll)
    root.mainloop()
    try:
        busy.destroy()
        root.destroy()
    except Exception:  # noqa: BLE001
        pass

    return result_box.get("value"), result_box.get("error")


# ---------------------------------------------------------------------------
# Fenêtre de résultat
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Rendu Markdown basique -> tags Tkinter (equivalent du markup Pango cote
# Linux). Tkinter n'a pas de moteur de markup inline comme Pango : le rendu
# se fait en inserant le texte segment par segment dans le Text widget, en
# appliquant un tag (style de police) a chaque segment reconnu. Couvre les
# memes cas que le client Linux (titres, gras, italique, listes), sans
# dependance supplementaire (tout est natif Tkinter/tkinter.font).
# ---------------------------------------------------------------------------

_INLINE_TOKEN_RE = re.compile(r"(\*\*.+?\*\*|\*.+?\*)")


def _insert_inline_markdown(text_widget, line, base_tag=None):
    """Insere une ligne dans le widget Text en appliquant les tags 'bold'/
    'italic' sur les segments **gras**/*italique*, et base_tag (ex: heading)
    sur toute la ligne le cas echeant."""
    pos = 0
    for match in _INLINE_TOKEN_RE.finditer(line):
        if match.start() > pos:
            plain = line[pos:match.start()]
            tags = (base_tag,) if base_tag else ()
            text_widget.insert("end", plain, tags)
        token = match.group(0)
        if token.startswith("**"):
            inner = token[2:-2]
            tags = (base_tag, "bold") if base_tag else ("bold",)
        else:
            inner = token[1:-1]
            tags = (base_tag, "italic") if base_tag else ("italic",)
        text_widget.insert("end", inner, tags)
        pos = match.end()
    if pos < len(line):
        remainder = line[pos:]
        tags = (base_tag,) if base_tag else ()
        text_widget.insert("end", remainder, tags)


def _render_markdown_into_text(text_widget, content):
    """Convertit un sous-ensemble basique de Markdown (titres, gras,
    italique, listes a puces/numerotees) en insertions taguees dans un
    tk.Text, ligne par ligne. Meme perimetre volontairement limite que la
    version Linux (markdown_to_pango) : couvre ce que Mistral renvoie en
    pratique, pas un vrai parseur Markdown complet."""
    lines = content.split("\n")
    for i, raw_line in enumerate(lines):
        line = raw_line.rstrip()
        stripped = line.strip()

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        bullet_match = re.match(r"^[-*+]\s+(.*)$", stripped) if not heading_match else None
        numbered_match = (
            re.match(r"^(\d+\.)\s+(.*)$", stripped)
            if not heading_match and not bullet_match
            else None
        )

        if heading_match:
            level = len(heading_match.group(1))
            tag = "h1" if level == 1 else "h2"
            _insert_inline_markdown(text_widget, heading_match.group(2).strip(), base_tag=tag)
        elif bullet_match:
            text_widget.insert("end", "    \u2022 ")
            _insert_inline_markdown(text_widget, bullet_match.group(1))
        elif numbered_match:
            text_widget.insert("end", f"    {numbered_match.group(1)} ")
            _insert_inline_markdown(text_widget, numbered_match.group(2))
        else:
            _insert_inline_markdown(text_widget, line)

        if i < len(lines) - 1:
            text_widget.insert("end", "\n")


def show_result_window(title, content):
    """Fenetre de resultat Tkinter avec rendu Markdown basique (gras/
    italique/titres/listes) via des tags sur le Text widget. Remplace
    l'ancien affichage en texte brut ('**', '#' visibles tels quels), sans
    ajouter de dependance (pas de moteur HTML/Markdown externe)."""
    root = tk.Tk()
    root.title(title)
    root.geometry("700x540")

    base_font = ("Segoe UI", 10)
    text = tk.Text(root, wrap="word", font=base_font)
    text.tag_configure("bold", font=("Segoe UI", 10, "bold"))
    text.tag_configure("italic", font=("Segoe UI", 10, "italic"))
    text.tag_configure("h1", font=("Segoe UI", 15, "bold"), spacing3=4)
    text.tag_configure("h2", font=("Segoe UI", 12, "bold"), spacing3=2)

    _render_markdown_into_text(text, content)
    text.config(state="disabled")
    scrollbar = ttk.Scrollbar(root, command=text.yview)
    text.configure(yscrollcommand=scrollbar.set)
    text.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
    scrollbar.pack(side="left", fill="y", pady=10)

    btn_frame = tk.Frame(root)
    btn_frame.pack(side="bottom", fill="x", padx=10, pady=8)

    def copy_to_clipboard():
        root.clipboard_clear()
        root.clipboard_append(content)
        messagebox.showinfo("DocPilote", "Copié dans le presse-papiers.", parent=root)

    def export_to_file():
        dest = filedialog.asksaveasfilename(
            title="Exporter le résultat",
            defaultextension=".txt",
            initialfile="resultat.txt",
        )
        if dest:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("DocPilote", f"Exporté vers {dest}", parent=root)

    tk.Button(btn_frame, text="📋 Copier", command=copy_to_clipboard).pack(
        side="left", padx=(0, 6)
    )
    tk.Button(btn_frame, text="💾 Exporter", command=export_to_file).pack(
        side="left", padx=(0, 6)
    )
    tk.Button(btn_frame, text="Fermer", command=root.destroy).pack(side="right")

    root.mainloop()


def show_error(message):
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("DocPilote", message, parent=root)
    root.destroy()


# ---------------------------------------------------------------------------
# Vérification de nouvelle version (best-effort, jamais bloquant)
# ---------------------------------------------------------------------------

def _version_tuple(v):
    parts = []
    for chunk in v.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _show_update_toast(latest, download_url):
    try:
        root = tk.Tk()
        root.withdraw()
        toast = tk.Toplevel(root)
        toast.title("DocPilote")
        toast.attributes("-topmost", True)
        toast.geometry("380x110")
        tk.Label(
            toast,
            text=f"Nouvelle version disponible : v{latest}\n(vous avez v{CLIENT_VERSION})",
            font=("Segoe UI", 10),
            pady=10,
        ).pack()

        def open_download():
            try:
                os.startfile(download_url)  # noqa: S606 (Windows uniquement)
            except Exception:  # noqa: BLE001
                pass
            toast.destroy()
            root.destroy()

        frame = tk.Frame(toast)
        frame.pack(pady=6)
        tk.Button(frame, text="Télécharger", command=open_download).pack(
            side="left", padx=4
        )
        tk.Button(
            frame, text="Plus tard", command=lambda: (toast.destroy(), root.destroy())
        ).pack(side="left", padx=4)
        toast.after(15000, lambda: (toast.destroy(), root.destroy()))
        root.mainloop()
    except Exception:  # noqa: BLE001
        pass


def check_for_update():
    """Vérifie en arrière-plan (thread démon, best-effort) s'il existe une
    version plus récente que celle installée. Ne bloque jamais l'action en
    cours et ne vérifie qu'une fois par intervalle (cache local)."""

    def worker():
        try:
            now = time.time()
            cache = {}
            if os.path.isfile(VERSION_CHECK_CACHE):
                try:
                    with open(VERSION_CHECK_CACHE, encoding="utf-8") as f:
                        cache = json.load(f)
                except Exception:  # noqa: BLE001
                    cache = {}

            last_check = cache.get("last_check_at", 0)
            if now - last_check < VERSION_CHECK_INTERVAL_S:
                return

            import requests

            resp = requests.get(f"{API_URL}/version-windows", timeout=4)
            if resp.status_code != 200:
                return
            data = resp.json()
            latest = data.get("version", "")
            download_url = data.get("download_url", "")

            os.makedirs(os.path.dirname(VERSION_CHECK_CACHE), exist_ok=True)
            with open(VERSION_CHECK_CACHE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "last_check_at": now,
                        "last_notified_version": cache.get("last_notified_version", ""),
                    },
                    f,
                )

            if not latest or _version_tuple(latest) <= _version_tuple(CLIENT_VERSION):
                return

            if cache.get("last_notified_version") == latest:
                return

            with open(VERSION_CHECK_CACHE, "w", encoding="utf-8") as f:
                json.dump({"last_check_at": now, "last_notified_version": latest}, f)

            _show_update_toast(latest, download_url)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Activation de licence (action indépendante, accessible depuis le menu
# Démarrer sans avoir besoin de sélectionner un fichier)
# ---------------------------------------------------------------------------

def activate_license():
    import requests

    root = tk.Tk()
    root.title("DocPilote — Activer une licence")
    root.geometry("460x200")

    tk.Label(
        root,
        text="Collez votre clé de licence\n(reçue par email après l'abonnement) :",
        font=("Segoe UI", 10),
        pady=10,
    ).pack()

    entry_var = tk.StringVar(value=load_license_key())
    entry = tk.Entry(root, textvariable=entry_var, width=40, font=("Segoe UI", 10))
    entry.pack(pady=4)
    entry.focus_set()

    # Lien visible vers la page d'abonnement : sans ca, quelqu'un qui ouvre
    # cette fenetre sans avoir encore de cle n'a aucun moyen de savoir qu'il
    # doit d'abord s'abonner (le lien PRICING_URL n'apparaissait auparavant
    # que dans le message d'erreur, apres avoir tente une cle invalide).
    pricing_link = tk.Label(
        root,
        text="Pas encore de licence ? S'abonner (paiement securise)",
        font=("Segoe UI", 9, "underline"),
        fg="#2a6fdb",
        cursor="hand2",
    )
    pricing_link.pack(pady=(0, 4))

    def open_pricing(_event=None):
        try:
            os.startfile(PRICING_URL)  # noqa: S606 (Windows uniquement)
        except Exception:  # noqa: BLE001
            pass

    pricing_link.bind("<Button-1>", open_pricing)

    status_label = tk.Label(root, text="", font=("Segoe UI", 9), fg="#555")
    status_label.pack(pady=4)

    def submit():
        key = entry_var.get().strip()
        if not key:
            root.destroy()
            return
        status_label.config(text="Vérification en cours...")
        root.update_idletasks()
        try:
            resp = requests.get(
                f"{API_URL}/license/status",
                params={"key": key, "device_id": get_device_id()},
                timeout=10,
            )
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "DocPilote", f"Impossible de vérifier la licence (réseau) : {exc}",
                parent=root,
            )
            return

        if data.get("device_conflict"):
            messagebox.showerror(
                "DocPilote",
                data.get("message", "Cette licence est déjà active sur un autre appareil."),
                parent=root,
            )
            return

        if not data.get("valid"):
            messagebox.showerror(
                "DocPilote",
                "Cette clé de licence n'est pas valide ou n'est plus active.\n"
                "Vérifiez qu'elle a bien été copiée en entier, ou abonnez-vous ici :\n"
                f"{PRICING_URL}",
                parent=root,
            )
            return

        save_license_key(key)
        messagebox.showinfo(
            "DocPilote", "Licence activée — usage illimité !", parent=root
        )
        root.destroy()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=8)
    tk.Button(btn_frame, text="Activer", command=submit, width=12).pack(
        side="left", padx=6
    )
    tk.Button(btn_frame, text="Annuler", command=root.destroy, width=12).pack(
        side="left", padx=6
    )

    root.bind("<Return>", lambda _e: submit())
    root.mainloop()


# ---------------------------------------------------------------------------
# Boîtes de dialogue auxiliaires (question pour "ask", cible pour "transform")
# ---------------------------------------------------------------------------

def ask_question_dialog(files):
    result = {"value": None}
    root = tk.Tk()
    root.title("DocPilote — Interroger")
    root.geometry("440x140")

    tk.Label(
        root,
        text=f"Posez votre question sur :\n{basename_label(files)}",
        font=("Segoe UI", 10),
        pady=8,
    ).pack()
    entry_var = tk.StringVar()
    entry = tk.Entry(root, textvariable=entry_var, width=48, font=("Segoe UI", 10))
    entry.pack(pady=6)
    entry.focus_set()

    def submit():
        result["value"] = entry_var.get().strip()
        root.destroy()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=8)
    tk.Button(btn_frame, text="Valider", command=submit, width=12).pack(
        side="left", padx=6
    )
    tk.Button(btn_frame, text="Annuler", command=root.destroy, width=12).pack(
        side="left", padx=6
    )
    root.bind("<Return>", lambda _e: submit())
    root.mainloop()
    return result["value"]


def choose_transform_target_dialog(files):
    result = {"value": None}
    root = tk.Tk()
    root.title("DocPilote — Transformer")
    root.geometry("380x320")

    tk.Label(
        root,
        text=f"Transformer « {basename_label(files)} » en :",
        font=("Segoe UI", 10),
        pady=8,
        wraplength=340,
    ).pack()

    choice = tk.StringVar(value=TRANSFORM_TARGETS[0][0])
    for key, label in TRANSFORM_TARGETS:
        tk.Radiobutton(
            root, text=label, variable=choice, value=key, font=("Segoe UI", 10)
        ).pack(anchor="w", padx=30, pady=2)

    def submit():
        result["value"] = choice.get()
        root.destroy()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Valider", command=submit, width=12).pack(
        side="left", padx=6
    )
    tk.Button(btn_frame, text="Annuler", command=root.destroy, width=12).pack(
        side="left", padx=6
    )
    root.mainloop()
    return result["value"]


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    check_for_update()

    args = sys.argv[1:]
    if not args:
        show_error("Appel invalide (action manquante).")
        sys.exit(1)

    if args[0] == "activate-license":
        activate_license()
        return

    if len(args) < 2:
        show_error("Appel invalide (action ou fichier manquant).")
        sys.exit(1)

    action = args[0]
    files = args[1:]

    for f in files:
        if not os.path.isfile(f):
            show_error(f"Fichier introuvable : {f}")
            sys.exit(1)

    if action not in TITLES:
        show_error(f"Action inconnue : {action}")
        sys.exit(1)

    if action == "compare" and len(files) < 2:
        show_error(
            "Sélectionnez exactement 2 documents pour comparer.\n\n"
            "Astuce Windows : sélectionnez les 2 fichiers avant de faire le "
            "clic droit."
        )
        sys.exit(1)

    question = None
    target = None

    if action == "ask":
        question = ask_question_dialog(files)
        if not question:
            sys.exit(0)

    if action == "transform":
        target = choose_transform_target_dialog(files)
        if not target:
            sys.exit(0)

    result, error = run_with_busy_window(
        lambda: api_call(files, action, question=question, target=target)
    )

    if error:
        show_error(error)
        sys.exit(1)

    if not result:
        show_error(
            "DocPilote n'a reçu aucun résultat du service (réponse vide). "
            "Réessayez, et si le problème persiste, contactez le support."
        )
        sys.exit(1)

    title = f"DocPilote — {TITLES.get(action, action)} — {basename_label(files)}"
    show_result_window(title, result)


if __name__ == "__main__":
    main()
