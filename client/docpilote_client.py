#!/usr/bin/env python3
"""DocPilote — orchestrateur client.
Appelé par l'extension Nemo native avec : action fichier1 [fichier2].
Affiche un vrai curseur "chargement" système pendant l'appel API,
puis le résultat via zenity.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

API_URL = "https://docpilote.prestalibre.org/api"
PRICING_URL = "https://docpilote.prestalibre.org/#pricing"

CLIENT_VERSION = "0.13.5"
LICENSE_FILE = os.path.expanduser("~/.config/docpilote/license.key")
VERSION_CHECK_CACHE = os.path.expanduser("~/.cache/docpilote/last_version_check.json")
VERSION_CHECK_INTERVAL_S = 12 * 3600  # ne vérifie qu'une fois toutes les 12h max

def get_device_id():
    """Identifiant stable de la machine, hashe (jamais envoye en clair) : sert
    a lier une licence a un appareil (voir check_device_binding cote API).
    /etc/machine-id est l'identifiant standard Linux, genere a l'installation
    du systeme, stable tant que l'OS n'est pas reinstalle. Best-effort : si
    illisible, on retombe sur un identifiant vide (pas de liaison possible,
    pas de blocage cote client -> le serveur traite ca comme un client
    ancien sans support device)."""
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read().strip()
            if raw:
                return hashlib.sha256(raw.encode("utf-8")).hexdigest()
        except OSError:
            continue
    return ""


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


def zenity(args, input_text=None):
    result = subprocess.run(
        ["zenity"] + args,
        input=input_text,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip()


def grab_busy_cursor():
    """Force le curseur système "chargement" (comme un vrai spinner OS)
    pendant toute la durée du traitement, peu importe la fenêtre survolée.
    Retourne une fonction release() à appeler à la fin."""
    invisible = Gtk.Window(type=Gtk.WindowType.POPUP)
    invisible.set_default_size(1, 1)
    invisible.move(-100, -100)
    invisible.show_all()
    gdk_win = invisible.get_window()

    display = Gdk.Display.get_default()
    seat = display.get_default_seat()
    cursor = Gdk.Cursor.new_from_name(display, "progress")

    status = seat.grab(
        gdk_win,
        Gdk.SeatCapabilities.POINTER,
        False,
        cursor,
        None,
        None,
        None,
    )

    def release():
        try:
            seat.ungrab()
        except Exception:  # noqa: BLE001
            pass
        invisible.destroy()

    if status != Gdk.GrabStatus.SUCCESS:
        invisible.destroy()
        return lambda: None

    return release


def run_with_busy_cursor(work_fn):
    """Exécute work_fn() (bloquant) dans un thread, curseur "chargement"
    affiché pendant ce temps, retourne (résultat, erreur).

    Le curseur est TOUJOURS libéré à la fin (try/finally), même en cas
    d'exception, et un garde-fou (watchdog) force la sortie de la boucle
    GTK après 130s au cas où le thread de travail resterait bloqué sans
    jamais appeler Gtk.main_quit() (timeout HTTP mal géré, etc.)."""
    result_box = {}
    release_cursor = grab_busy_cursor()

    def worker():
        try:
            result_box["value"] = work_fn()
        except Exception as exc:  # noqa: BLE001
            result_box["error"] = str(exc)
        GLib.idle_add(Gtk.main_quit)

    def watchdog():
        result_box.setdefault("error", "Délai d'attente dépassé (le service ne répond pas).")
        Gtk.main_quit()
        return False

    watchdog_id = GLib.timeout_add(130000, watchdog)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    try:
        Gtk.main()
    finally:
        try:
            GLib.source_remove(watchdog_id)
        except Exception:  # noqa: BLE001
            pass
        release_cursor()
    return result_box.get("value"), result_box.get("error")


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
            + "\n\nActivez une licence (menu Applications → DocPilote — Activer une licence) "
            "ou abonnez-vous : " + PRICING_URL
        )

    if resp.status_code != 200:
        raise RuntimeError(data.get("detail", "Erreur du service DocPilote"))

    return data.get("result", "")


def _pango_escape(text):
    """Echappe les caracteres speciaux Pango/XML (a appliquer AVANT toute
    insertion de balises Pango, jamais apres, sous peine de casser le
    markup lui-meme)."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _apply_inline_pango(escaped_text):
    """Applique gras/italique inline sur un texte DEJA echappe (le texte ne
    doit contenir aucun caractere XML brut a ce stade, uniquement des
    entites &amp;/&lt;/&gt; et des marqueurs Markdown ** / *)."""
    # Gras : **texte** (avant l'italique, car ** contient des *)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped_text)
    # Italique : *texte* (ce qui reste apres extraction du gras)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    return text


def markdown_to_pango(content):
    """Convertit un sous-ensemble basique de Markdown (ce que Mistral renvoie
    en pratique : titres, gras, italique, listes a puces/numerotees) en
    balisage Pango, pour un affichage lisible dans un Gtk.Label plutot
    qu'un texte brut avec des '**' et '#' visibles tels quels.

    Volontairement limite (pas de vrai parseur Markdown, pas de tableaux/
    liens/code) : couvre ce qui sort reellement des prompts DocPilote, sans
    ajouter de dependance (python-markdown, WebKit...)."""
    out_lines = []
    for raw_line in content.split("\n"):
        line = raw_line.rstrip()
        stripped = line.strip()

        # Titres Markdown (#, ##, ###...) -> ligne en gras, taille agrandie
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = _pango_escape(heading_match.group(2).strip())
            size = "x-large" if level == 1 else "large"
            out_lines.append(f'<span size="{size}" weight="bold">{text}</span>')
            continue

        # Listes a puces (-, *, +) -> prefixe "• "
        bullet_match = re.match(r"^[-*+]\s+(.*)$", stripped)
        if bullet_match:
            text = _apply_inline_pango(_pango_escape(bullet_match.group(1)))
            out_lines.append(f"    • {text}")
            continue

        # Listes numerotees (1. 2. ...) -> gardees telles quelles, juste le
        # gras/italique inline est applique
        numbered_match = re.match(r"^(\d+\.)\s+(.*)$", stripped)
        if numbered_match:
            num = numbered_match.group(1)
            text = _apply_inline_pango(_pango_escape(numbered_match.group(2)))
            out_lines.append(f"    {num} {text}")
            continue

        # Ligne normale : echappement + gras/italique inline
        out_lines.append(_apply_inline_pango(_pango_escape(line)))

    return "\n".join(out_lines)


def show_result_window(title, content):
    """Fenetre de resultat GTK avec rendu Markdown basique (gras/italique/
    titres/listes) via Pango markup, dans un Gtk.Label selectionnable et
    scrollable. Remplace l'ancien zenity --text-info (texte brut, '**'
    et '#' visibles tels quels) sans ajouter de dependance (pas de
    WebKit, pas de python-markdown)."""
    pango_content = markdown_to_pango(content)

    window = Gtk.Window(title=title)
    window.set_default_size(680, 520)
    window.set_position(Gtk.WindowPosition.CENTER)

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    vbox.set_border_width(12)
    window.add(vbox)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_vexpand(True)
    vbox.pack_start(scrolled, True, True, 0)

    label = Gtk.Label()
    try:
        label.set_markup(pango_content)
    except GLib.Error:
        # Filet de securite : si le markup genere est malgre tout invalide
        # (cas Markdown non prevu), on retombe sur le texte brut echappe
        # plutot que de faire planter l'affichage du resultat.
        label.set_text(content)
    label.set_line_wrap(True)
    label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    label.set_selectable(True)
    label.set_xalign(0.0)
    label.set_yalign(0.0)
    label.set_margin_start(6)
    label.set_margin_end(6)
    scrolled.add(label)

    button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    button_box.set_halign(Gtk.Align.END)
    vbox.pack_start(button_box, False, False, 0)

    result_box = {"action": None}

    def on_copy(_btn):
        result_box["action"] = "copy"
        window.close()

    def on_export(_btn):
        result_box["action"] = "export"
        window.close()

    def on_close(_btn):
        window.close()

    copy_btn = Gtk.Button(label="📋 Copier")
    copy_btn.connect("clicked", on_copy)
    button_box.pack_start(copy_btn, False, False, 0)

    export_btn = Gtk.Button(label="💾 Exporter")
    export_btn.connect("clicked", on_export)
    button_box.pack_start(export_btn, False, False, 0)

    close_btn = Gtk.Button(label="Fermer")
    close_btn.connect("clicked", on_close)
    button_box.pack_start(close_btn, False, False, 0)

    window.connect("destroy", lambda _w: Gtk.main_quit())
    window.show_all()
    Gtk.main()

    if result_box["action"] == "copy":
        copy_to_clipboard(content)
    elif result_box["action"] == "export":
        _, dest = zenity(
            [
                "--file-selection",
                "--save",
                "--confirm-overwrite",
                "--title=Exporter le résultat",
                "--filename=resultat.txt",
            ]
        )
        if dest:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(content)
            subprocess.run(
                ["notify-send", "DocPilote", f"Exporté vers {dest}"], check=False
            )


def copy_to_clipboard(text):
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_text(text, -1)
    clipboard.store()
    subprocess.run(
        ["notify-send", "DocPilote", "Copié dans le presse-papiers"], check=False
    )


def show_error(message):
    zenity(["--error", "--title=DocPilote", f"--text={message}", "--width=380"])


def _version_tuple(v):
    parts = []
    for chunk in v.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_for_update():
    """Vérifie en arrière-plan (thread démon, best-effort) s'il existe une
    version plus récente que celle installée, et notifie l'utilisateur via
    notify-send si c'est le cas. Ne bloque jamais l'action en cours et ne
    vérifie qu'une fois par intervalle (cache local) pour ne pas spammer
    l'API à chaque clic droit."""

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

            resp = requests.get(f"{API_URL}/version", timeout=4)
            if resp.status_code != 200:
                return
            data = resp.json()
            latest = data.get("version", "")
            download_url = data.get("download_url", "")

            os.makedirs(os.path.dirname(VERSION_CHECK_CACHE), exist_ok=True)
            with open(VERSION_CHECK_CACHE, "w", encoding="utf-8") as f:
                json.dump({"last_check_at": now, "last_notified_version": cache.get("last_notified_version", "")}, f)

            if not latest or _version_tuple(latest) <= _version_tuple(CLIENT_VERSION):
                return

            # Ne notifie qu'une seule fois par nouvelle version détectée
            if cache.get("last_notified_version") == latest:
                return

            subprocess.run(
                [
                    "notify-send",
                    "--icon=software-update-available",
                    "DocPilote — nouvelle version disponible",
                    f"v{latest} est disponible (vous avez v{CLIENT_VERSION}). "
                    f"Téléchargez-la : {download_url}",
                ],
                check=False,
            )

            with open(VERSION_CHECK_CACHE, "w", encoding="utf-8") as f:
                json.dump({"last_check_at": now, "last_notified_version": latest}, f)
        except Exception:  # noqa: BLE001
            pass  # la vérification de version ne doit jamais faire planter une action

    threading.Thread(target=worker, daemon=True).start()


def basename_label(files):
    names = [os.path.basename(f) for f in files]
    return " / ".join(names)


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


def activate_license():
    """Action independante (pas de fichier requis) : demande une cle de
    licence a l'utilisateur, la verifie aupres du serveur, et l'enregistre
    localement si valide. Accessible depuis le menu Applications (pas besoin
    de selectionner un document)."""
    import requests

    existing = load_license_key()
    prefill = existing or ""
    # Le lien d'abonnement est affiche directement dans le texte du prompt
    # (zenity --entry n'a pas de veritable lien cliquable) : sans ca, un
    # utilisateur qui ouvre cette fenetre sans avoir encore de cle n'a aucun
    # moyen de savoir qu'il doit d'abord s'abonner -- le lien n'apparaissait
    # auparavant que dans le message d'erreur, apres une tentative de cle
    # invalide.
    _, key = zenity(
        [
            "--entry",
            "--title=DocPilote — Activer une licence",
            "--text=Collez votre clé de licence (reçue par email après l'abonnement) :\n"
            f"Pas encore de licence ? Abonnez-vous ici : {PRICING_URL}",
            f"--entry-text={prefill}",
            "--width=440",
        ]
    )
    key = (key or "").strip()
    if not key:
        sys.exit(0)

    try:
        resp = requests.get(
            f"{API_URL}/license/status",
            params={"key": key, "device_id": get_device_id()},
            timeout=10,
        )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        show_error(f"Impossible de vérifier la licence (réseau) : {exc}")
        sys.exit(1)

    if data.get("device_conflict"):
        show_error(data.get("message", "Cette licence est déjà active sur un autre appareil."))
        sys.exit(1)

    if not data.get("valid"):
        show_error(
            "Cette clé de licence n'est pas valide ou n'est plus active.\n"
            "Vérifiez qu'elle a bien été copiée en entier, ou abonnez-vous ici :\n"
            f"{PRICING_URL}"
        )
        sys.exit(1)

    save_license_key(key)
    subprocess.run(
        ["notify-send", "DocPilote", "Licence activée — usage illimité !"],
        check=False,
    )


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
        show_error("Sélectionnez exactement 2 documents pour comparer.")
        sys.exit(1)

    question = None
    target = None

    if action == "ask":
        _, question = zenity(
            [
                "--entry",
                "--title=DocPilote — Interroger",
                f"--text=Posez votre question sur : {basename_label(files)}",
                "--width=420",
            ]
        )
        if not question:
            sys.exit(0)

    if action == "transform":
        radiolist_args = [
            "--list",
            "--radiolist",
            "--title=DocPilote — Transformer",
            f"--text=Transformer « {basename_label(files)} » en :",
            "--column=",
            "--column=Format",
            "--width=420",
            "--height=320",
        ]
        for i, (key, label) in enumerate(TRANSFORM_TARGETS):
            radiolist_args.append("TRUE" if i == 0 else "FALSE")
            radiolist_args.append(label)
        _, chosen_label = zenity(radiolist_args)
        if not chosen_label:
            sys.exit(0)
        target = next((k for k, v in TRANSFORM_TARGETS if v == chosen_label), "mail")

    result, error = run_with_busy_cursor(
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
