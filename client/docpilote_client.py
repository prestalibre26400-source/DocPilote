#!/usr/bin/env python3
"""DocPilote — orchestrateur client.
Appelé par l'extension Nemo native avec : action fichier1 [fichier2].
Affiche un vrai curseur "chargement" système pendant l'appel API,
puis le résultat via zenity.
"""
import hashlib
import json
import locale
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

CLIENT_VERSION = "0.13.7"
LICENSE_FILE = os.path.expanduser("~/.config/docpilote/license.key")
VERSION_CHECK_CACHE = os.path.expanduser("~/.cache/docpilote/last_version_check.json")
VERSION_CHECK_INTERVAL_S = 12 * 3600  # ne vérifie qu'une fois toutes les 12h max


# ---------------------------------------------------------------------------
# Internationalisation (FR par defaut, EN si systeme anglophone ou override)
#
# Pas de framework i18n/gettext : le volume de strings (~30) ne le justifie
# pas. DOCPILOTE_LANG force la langue (utile pour tester/deboguer), sinon
# detection via la locale systeme -> "en" si elle commence par "en", "fr"
# dans tous les autres cas (comportement historique inchange par defaut).
# ---------------------------------------------------------------------------


def detect_lang():
    override = os.environ.get("DOCPILOTE_LANG", "").strip().lower()
    if override in ("fr", "en"):
        return override
    candidates = []
    try:
        loc = locale.getlocale()[0]
        if loc:
            candidates.append(loc)
    except Exception:  # noqa: BLE001
        pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        val = os.environ.get(var)
        if val:
            candidates.append(val)
    for c in candidates:
        if c.lower().startswith("en"):
            return "en"
    return "fr"


LANG = detect_lang()

STRINGS = {
    "fr": {
        "invalid_response": "Réponse invalide du service",
        "quota_reached_activate": (
            "\n\nActivez une licence (menu Applications → DocPilote — Activer une "
            "licence) ou abonnez-vous : "
        ),
        "service_error": "Erreur du service DocPilote",
        "copy_btn": "\U0001F4CB Copier",
        "export_btn": "\U0001F4BE Exporter",
        "close_btn": "Fermer",
        "copied_clipboard": "Copié dans le presse-papiers",
        "exported_to": "Exporté vers {dest}",
        "export_result_title": "Exporter le résultat",
        "export_filename": "resultat.txt",
        "file_not_found": "Fichier introuvable : {f}",
        "unknown_action": "Action inconnue : {action}",
        "select_two_docs": "Sélectionnez exactement 2 documents pour comparer.",
        "invalid_call_action": "Appel invalide (action manquante).",
        "invalid_call_file": "Appel invalide (action ou fichier manquant).",
        "ask_title": "DocPilote — Interroger",
        "ask_prompt": "Posez votre question sur : {name}",
        "transform_title": "DocPilote — Transformer",
        "transform_prompt": "Transformer « {name} » en :",
        "empty_result": (
            "DocPilote n'a reçu aucun résultat du service (réponse vide). "
            "Réessayez, et si le problème persiste, contactez le support."
        ),
        "activate_license_title": "DocPilote — Activer une licence",
        "paste_license_label": (
            "Collez votre clé de licence\n(reçue par email après l'abonnement) :"
        ),
        "subscribe_link": "Pas encore de licence ? S'abonner (paiement sécurisé)",
        "cancel_btn": "Annuler",
        "validate_btn": "Valider",
        "license_invalid": (
            "Cette clé de licence n'est pas valide ou n'est plus active.\n"
            "Vérifiez qu'elle a bien été copiée en entier, ou abonnez-vous ici :\n{url}"
        ),
        "license_network_error": "Impossible de vérifier la licence (réseau) : {exc}",
        "license_activated": "Licence activée — usage illimité !",
        "update_available_title": "DocPilote — nouvelle version disponible",
        "update_available_body": (
            "v{latest} est disponible (vous avez v{current}). Téléchargez-la : {url}"
        ),
        "titles": {
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
        },
        "transform_targets": [
            ("mail", "Mail"),
            ("procedure", "Procédure"),
            ("synthese", "Synthèse"),
            ("tableau", "Tableau"),
            ("presentation", "Présentation"),
            ("compte_rendu", "Compte rendu"),
        ],
    },
    "en": {
        "invalid_response": "Invalid response from the service",
        "quota_reached_activate": (
            "\n\nActivate a license (Applications menu → DocPilote — Activate a "
            "license) or subscribe: "
        ),
        "service_error": "DocPilote service error",
        "copy_btn": "\U0001F4CB Copy",
        "export_btn": "\U0001F4BE Export",
        "close_btn": "Close",
        "copied_clipboard": "Copied to clipboard",
        "exported_to": "Exported to {dest}",
        "export_result_title": "Export result",
        "export_filename": "result.txt",
        "file_not_found": "File not found: {f}",
        "unknown_action": "Unknown action: {action}",
        "select_two_docs": "Select exactly 2 documents to compare.",
        "invalid_call_action": "Invalid call (missing action).",
        "invalid_call_file": "Invalid call (missing action or file).",
        "ask_title": "DocPilote — Ask a question",
        "ask_prompt": "Ask your question about: {name}",
        "transform_title": "DocPilote — Transform",
        "transform_prompt": "Transform \u201c{name}\u201d into:",
        "empty_result": (
            "DocPilote received no result from the service (empty response). "
            "Try again, and contact support if the problem persists."
        ),
        "activate_license_title": "DocPilote — Activate a license",
        "paste_license_label": (
            "Paste your license key\n(received by email after subscribing):"
        ),
        "subscribe_link": "No license yet? Subscribe (secure payment)",
        "cancel_btn": "Cancel",
        "validate_btn": "Validate",
        "license_invalid": (
            "This license key is not valid or is no longer active.\n"
            "Check that it was copied in full, or subscribe here:\n{url}"
        ),
        "license_network_error": "Could not verify the license (network): {exc}",
        "license_activated": "License activated — unlimited usage!",
        "update_available_title": "DocPilote — new version available",
        "update_available_body": (
            "v{latest} is available (you have v{current}). Download it: {url}"
        ),
        "titles": {
            "activate-license": "Activate a license",
            "summarize": "Summarize",
            "respond": "Prepare a reply",
            "explain": "Explain this document",
            "decide": "Actions to take",
            "risks": "Risks detected",
            "checklist": "Checklist",
            "extract": "Extracted data (JSON)",
            "ask": "Answer",
            "transform": "Transform",
            "compare": "Compare",
        },
        "transform_targets": [
            ("mail", "Email"),
            ("procedure", "Procedure"),
            ("synthese", "Executive summary"),
            ("tableau", "Table"),
            ("presentation", "Presentation"),
            ("compte_rendu", "Meeting minutes"),
        ],
    },
}


def t(key):
    return STRINGS.get(LANG, STRINGS["fr"]).get(key, STRINGS["fr"].get(key, key))


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


TRANSFORM_TARGETS = STRINGS.get(LANG, STRINGS["fr"]).get("transform_targets", STRINGS["fr"]["transform_targets"])
TITLES = STRINGS.get(LANG, STRINGS["fr"]).get("titles", STRINGS["fr"]["titles"])


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
        result_box.setdefault(
            "error",
            "Délai d'attente dépassé (le service ne répond pas)."
            if LANG == "fr"
            else "Timeout exceeded (the service is not responding).",
        )
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
                data={"license_key": license_key, "device_id": device_id, "lang": LANG},
                timeout=120,
            )
    elif action == "extract":
        with open(files[0], "rb") as f:
            resp = requests.post(
                f"{API_URL}/extract",
                files={"file": f},
                data={"license_key": license_key, "device_id": device_id, "lang": LANG},
                timeout=120,
            )
    elif action == "ask":
        with open(files[0], "rb") as f:
            resp = requests.post(
                f"{API_URL}/ask",
                files={"file": f},
                data={"question": question, "license_key": license_key, "device_id": device_id, "lang": LANG},
                timeout=120,
            )
    elif action == "transform":
        with open(files[0], "rb") as f:
            resp = requests.post(
                f"{API_URL}/transform",
                files={"file": f},
                data={"target": target, "license_key": license_key, "device_id": device_id, "lang": LANG},
                timeout=120,
            )
    else:
        with open(files[0], "rb") as f:
            resp = requests.post(
                f"{API_URL}/process",
                files={"file": f},
                data={"plugin": action, "license_key": license_key, "device_id": device_id, "lang": LANG},
                timeout=120,
            )

    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(t("invalid_response"))

    if resp.status_code == 402:
        raise RuntimeError(
            data.get("detail", "Quota gratuit atteint" if LANG == "fr" else "Free quota reached")
            + t("quota_reached_activate") + PRICING_URL
        )

    if resp.status_code != 200:
        raise RuntimeError(data.get("detail", t("service_error")))

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
            # _apply_inline_pango est indispensable ici : un titre Markdown
            # peut lui-meme contenir du gras/italique (ex: "## **Conclusion :**",
            # ce que Mistral genere en pratique) -- sans cette conversion, les
            # '**' restaient visibles tels quels UNIQUEMENT sur les titres,
            # alors que le gras inline dans le corps du texte etait converti
            # normalement (signale par un client via capture d'ecran).
            text = _apply_inline_pango(_pango_escape(heading_match.group(2).strip()))
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

    copy_btn = Gtk.Button(label=t("copy_btn"))
    copy_btn.connect("clicked", on_copy)
    button_box.pack_start(copy_btn, False, False, 0)

    export_btn = Gtk.Button(label=t("export_btn"))
    export_btn.connect("clicked", on_export)
    button_box.pack_start(export_btn, False, False, 0)

    close_btn = Gtk.Button(label=t("close_btn"))
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
                f"--title={t('export_result_title')}",
                f"--filename={t('export_filename')}",
            ]
        )
        if dest:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(content)
            subprocess.run(
                ["notify-send", "DocPilote", t("exported_to").format(dest=dest)], check=False
            )


def copy_to_clipboard(text):
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_text(text, -1)
    clipboard.store()
    subprocess.run(
        ["notify-send", "DocPilote", t("copied_clipboard")], check=False
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
                    t("update_available_title"),
                    t("update_available_body").format(
                        latest=latest, current=CLIENT_VERSION, url=download_url
                    ),
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
    de selectionner un document).

    Fenetre GTK custom (pas zenity --entry) : un Gtk.LinkButton donne un
    vrai lien cliquable vers PRICING_URL, contrairement au texte brut mis
    dans le prompt zenity precedemment (signale par un client via capture
    d'ecran -- le lien s'affichait mais n'etait pas cliquable, il fallait
    le copier-coller a la main)."""
    existing = load_license_key()

    window = Gtk.Window(title=t("activate_license_title"))
    window.set_default_size(440, 200)
    window.set_position(Gtk.WindowPosition.CENTER)
    window.set_resizable(False)

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    vbox.set_border_width(16)
    window.add(vbox)

    label = Gtk.Label(label=t("paste_license_label"))
    label.set_xalign(0.0)
    vbox.pack_start(label, False, False, 0)

    entry = Gtk.Entry()
    entry.set_text(existing or "")
    entry.set_activates_default(True)
    vbox.pack_start(entry, False, False, 0)

    link = Gtk.LinkButton.new_with_label(PRICING_URL, t("subscribe_link"))
    link.set_halign(Gtk.Align.START)
    vbox.pack_start(link, False, False, 0)

    button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    button_box.set_halign(Gtk.Align.END)
    vbox.pack_start(button_box, False, False, 0)

    result_box = {"key": None}

    def on_cancel(_btn):
        result_box["key"] = None
        window.close()

    def on_validate(_btn=None):
        result_box["key"] = entry.get_text().strip()
        window.close()

    cancel_btn = Gtk.Button(label=t("cancel_btn"))
    cancel_btn.connect("clicked", on_cancel)
    button_box.pack_start(cancel_btn, False, False, 0)

    validate_btn = Gtk.Button(label=t("validate_btn"))
    validate_btn.set_can_default(True)
    validate_btn.connect("clicked", on_validate)
    button_box.pack_start(validate_btn, False, False, 0)

    window.set_default(validate_btn)
    entry.connect("activate", on_validate)
    window.connect("destroy", lambda _w: Gtk.main_quit())
    window.show_all()
    entry.grab_focus()
    Gtk.main()

    key = (result_box["key"] or "").strip()
    if not key:
        sys.exit(0)

    import requests

    try:
        resp = requests.get(
            f"{API_URL}/license/status",
            params={"key": key, "device_id": get_device_id()},
            timeout=10,
        )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        show_error(t("license_network_error").format(exc=exc))
        sys.exit(1)

    if data.get("device_conflict"):
        default_msg = (
            "Cette licence est déjà active sur un autre appareil."
            if LANG == "fr"
            else "This license is already active on another device."
        )
        show_error(data.get("message", default_msg))
        sys.exit(1)

    if not data.get("valid"):
        show_error(t("license_invalid").format(url=PRICING_URL))
        sys.exit(1)

    save_license_key(key)
    subprocess.run(
        ["notify-send", "DocPilote", t("license_activated")],
        check=False,
    )


def main():
    check_for_update()

    args = sys.argv[1:]
    if not args:
        show_error(t("invalid_call_action"))
        sys.exit(1)

    if args[0] == "activate-license":
        activate_license()
        return

    if len(args) < 2:
        show_error(t("invalid_call_file"))
        sys.exit(1)

    action = args[0]
    files = args[1:]

    for f in files:
        if not os.path.isfile(f):
            show_error(t("file_not_found").format(f=f))
            sys.exit(1)

    if action not in TITLES:
        show_error(t("unknown_action").format(action=action))
        sys.exit(1)

    if action == "compare" and len(files) < 2:
        show_error(t("select_two_docs"))
        sys.exit(1)

    question = None
    target = None

    if action == "ask":
        _, question = zenity(
            [
                "--entry",
                f"--title={t('ask_title')}",
                f"--text={t('ask_prompt').format(name=basename_label(files))}",
                "--width=420",
            ]
        )
        if not question:
            sys.exit(0)

    if action == "transform":
        radiolist_args = [
            "--list",
            "--radiolist",
            f"--title={t('transform_title')}",
            f"--text={t('transform_prompt').format(name=basename_label(files))}",
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
        show_error(t("empty_result"))
        sys.exit(1)

    title = f"DocPilote — {TITLES.get(action, action)} — {basename_label(files)}"
    show_result_window(title, result)


if __name__ == "__main__":
    main()
