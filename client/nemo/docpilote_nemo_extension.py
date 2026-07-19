"""Extension Nemo native pour DocPilote.

Ajoute une entrée "DocPilote" au clic droit sur les documents supportés
(PDF, Word, ODT, texte, RTF), qui ouvre un vrai sous-menu au survol
(comme "Ouvrir avec"), sans fenêtre GTK flottante séparée.
"""
import locale
import os
import subprocess
import urllib.parse

from gi.repository import GObject, Nemo

SUPPORTED_EXTENSIONS = (
    ".pdf", ".docx", ".odt", ".txt", ".md", ".rtf",
    ".doc", ".xls", ".ppt", ".xlsx", ".pptx", ".ods", ".odp",
)


# ---------------------------------------------------------------------------
# Internationalisation (FR par defaut, EN si systeme anglophone ou override).
# Duplique volontairement (pas de module partage entre extensions) -- meme
# logique que docpilote_client.py / l'extension Nautilus/Thunar.
# ---------------------------------------------------------------------------


def _detect_lang():
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


_LANG = _detect_lang()

_ACTIONS_SINGLE = {
    "fr": [
        ("summarize", "✦ Résumer"),
        ("respond", "✎ Préparer une réponse"),
        ("explain", "❓ Explique-moi ce document"),
        ("decide", "✓ Quelles actions dois-je entreprendre ?"),
        ("risks", "⚠️ Détecter les risques"),
        ("checklist", "☑ Créer une checklist"),
        ("extract", "{ } Extraire (JSON)"),
        ("ask", "? Interroger ce document"),
        ("transform", "⇄ Transformer..."),
    ],
    "en": [
        ("summarize", "✦ Summarize"),
        ("respond", "✎ Prepare a reply"),
        ("explain", "❓ Explain this document"),
        ("decide", "✓ What actions should I take?"),
        ("risks", "⚠️ Detect risks"),
        ("checklist", "☑ Create a checklist"),
        ("extract", "{ } Extract (JSON)"),
        ("ask", "? Ask this document"),
        ("transform", "⇄ Transform..."),
    ],
}

_ACTION_MULTI = {
    "fr": ("compare", "↔ Comparer ces 2 documents"),
    "en": ("compare", "↔ Compare these 2 documents"),
}

_MENU_TIP = {
    "fr": "Analyser ce document avec DocPilote",
    "en": "Analyze this document with DocPilote",
}

_LICENSE_LABEL = {
    "fr": "\U0001F511 Activer une licence",
    "en": "\U0001F511 Activate a license",
}

_LICENSE_BACKGROUND_LABEL = {
    "fr": "DocPilote \u2014 Activer une licence",
    "en": "DocPilote \u2014 Activate a license",
}

_LICENSE_TIP = {
    "fr": "Saisir votre clé de licence DocPilote Pro",
    "en": "Enter your DocPilote Pro license key",
}

ACTIONS_SINGLE = _ACTIONS_SINGLE.get(_LANG, _ACTIONS_SINGLE["fr"])
ACTION_MULTI = _ACTION_MULTI.get(_LANG, _ACTION_MULTI["fr"])
MENU_TIP = _MENU_TIP.get(_LANG, _MENU_TIP["fr"])
LICENSE_LABEL = _LICENSE_LABEL.get(_LANG, _LICENSE_LABEL["fr"])
LICENSE_BACKGROUND_LABEL = _LICENSE_BACKGROUND_LABEL.get(_LANG, _LICENSE_BACKGROUND_LABEL["fr"])
LICENSE_TIP = _LICENSE_TIP.get(_LANG, _LICENSE_TIP["fr"])

RUN_SCRIPT = os.environ.get(
    "DOCPILOTE_RUN_SCRIPT", "/opt/docpilote/client/docpilote-run.sh"
)


def _file_path(nemo_file):
    uri = nemo_file.get_uri()
    parsed = urllib.parse.urlparse(uri)
    return urllib.parse.unquote(parsed.path)


class DocPiloteExtension(GObject.GObject, Nemo.MenuProvider):
    def _run(self, action, paths):
        subprocess.Popen([RUN_SCRIPT, action] + paths)

    def get_file_items(self, window, files):
        pdfs = [f for f in files if not f.is_directory()]
        if not pdfs:
            return []

        # Ne s'affiche que si TOUS les fichiers sélectionnés sont supportés
        for f in pdfs:
            uri = f.get_uri()
            if not uri.lower().endswith(SUPPORTED_EXTENSIONS):
                return []

        paths = [_file_path(f) for f in pdfs]

        top_item = Nemo.MenuItem(
            name="DocPiloteExtension::root",
            label="DocPilote",
            tip=MENU_TIP,
            icon="accessories-text-editor",
        )

        submenu = Nemo.Menu()
        top_item.set_submenu(submenu)

        if len(paths) >= 2:
            action, label = ACTION_MULTI
            item = Nemo.MenuItem(
                name=f"DocPiloteExtension::{action}",
                label=label,
                tip=label,
            )
            item.connect("activate", lambda _i, a=action: self._run(a, paths))
            submenu.append_item(item)
        else:
            for action, label in ACTIONS_SINGLE:
                item = Nemo.MenuItem(
                    name=f"DocPiloteExtension::{action}",
                    label=label,
                    tip=label,
                )
                item.connect("activate", lambda _i, a=action: self._run(a, paths))
                submenu.append_item(item)

        license_item = Nemo.MenuItem(
            name="DocPiloteExtension::activate-license",
            label=LICENSE_LABEL,
            tip=LICENSE_TIP,
        )
        license_item.connect(
            "activate", lambda _i: self._run("activate-license", [])
        )
        submenu.append_item(license_item)

        return [top_item]

    def get_background_items(self, window, current_folder):
        # Permet d'activer une licence depuis un clic droit dans le vide
        # (dossier ou bureau), sans avoir besoin de sélectionner un document
        # ni de passer par le menu Applications.
        item = Nemo.MenuItem(
            name="DocPiloteExtension::background-activate-license",
            label=LICENSE_BACKGROUND_LABEL,
            tip=LICENSE_TIP,
            icon="accessories-text-editor",
        )
        item.connect("activate", lambda _i: self._run("activate-license", []))
        return [item]
