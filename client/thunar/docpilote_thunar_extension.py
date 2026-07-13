"""Extension Thunar native pour DocPilote.

Ajoute une entrée "DocPilote" au clic droit sur les documents supportés
(PDF, Word, Excel, PowerPoint, OpenDocument, texte, RTF), qui ouvre un vrai
sous-menu au survol (comme "Ouvrir avec"), via l'API officielle
thunarx-python (Thunarx.MenuProvider / Thunarx.MenuItem.set_menu()).

API confirmée via l'exemple officiel embarqué dans le paquet Debian
thunarx-python (thunarx-submenu-plugin.py) :
    get_file_menu_items(self, window, files)
(signature fixe, contrairement à Nautilus qui a changé son API entre
versions — Thunar n'a pas eu ce problème de rupture).
"""
import os
import subprocess
import urllib.parse

from gi.repository import GObject, Thunarx

SUPPORTED_EXTENSIONS = (
    ".pdf", ".docx", ".odt", ".txt", ".md", ".rtf",
    ".doc", ".xls", ".ppt", ".xlsx", ".pptx", ".ods", ".odp",
)

ACTIONS_SINGLE = [
    ("summarize", "✦ Résumer"),
    ("respond", "✎ Préparer une réponse"),
    ("explain", "❓ Explique-moi ce document"),
    ("decide", "✓ Quelles actions dois-je entreprendre ?"),
    ("risks", "⚠️ Détecter les risques"),
    ("checklist", "☑ Créer une checklist"),
    ("extract", "{ } Extraire (JSON)"),
    ("ask", "? Interroger ce document"),
    ("transform", "⇄ Transformer..."),
]

ACTION_MULTI = ("compare", "↔ Comparer ces 2 documents")

RUN_SCRIPT = os.environ.get(
    "DOCPILOTE_RUN_SCRIPT", "/opt/docpilote/client/docpilote-run.sh"
)


def _file_path(thunar_file):
    uri = thunar_file.get_uri()
    parsed = urllib.parse.urlparse(uri)
    return urllib.parse.unquote(parsed.path)


class DocPiloteExtension(GObject.GObject, Thunarx.MenuProvider):
    def _run(self, action, paths):
        subprocess.Popen([RUN_SCRIPT, action] + paths)

    def get_file_menu_items(self, window, files):
        docs = [f for f in files if not f.is_directory()]
        if not docs:
            return []

        for f in docs:
            uri = f.get_uri()
            if not uri.lower().endswith(SUPPORTED_EXTENSIONS):
                return []

        paths = [_file_path(f) for f in docs]

        top_item = Thunarx.MenuItem(
            name="DocPiloteExtension::root",
            label="DocPilote",
            tooltip="Analyser ce document avec DocPilote",
            icon="accessories-text-editor",
        )

        submenu = Thunarx.Menu()

        if len(paths) >= 2:
            action, label = ACTION_MULTI
            item = Thunarx.MenuItem(
                name=f"DocPiloteExtension::{action}",
                label=label,
                tooltip=label,
            )
            item.connect("activate", lambda _i, a=action: self._run(a, paths))
            submenu.append_item(item)
        else:
            for action, label in ACTIONS_SINGLE:
                item = Thunarx.MenuItem(
                    name=f"DocPiloteExtension::{action}",
                    label=label,
                    tooltip=label,
                )
                item.connect("activate", lambda _i, a=action: self._run(a, paths))
                submenu.append_item(item)

        license_item = Thunarx.MenuItem(
            name="DocPiloteExtension::activate-license",
            label="\U0001F511 Activer une licence",
            tooltip="Saisir votre clé de licence DocPilote Pro",
        )
        license_item.connect("activate", lambda _i: self._run("activate-license", []))
        submenu.append_item(license_item)

        top_item.set_menu(submenu)

        return (top_item,)

    def get_folder_menu_items(self, window, folder):
        # Permet d'activer une licence depuis un clic droit dans le vide
        # (dossier ou bureau), sans avoir besoin de sélectionner un document
        # ni de passer par le menu Applications.
        item = Thunarx.MenuItem(
            name="DocPiloteExtension::background-activate-license",
            label="DocPilote \u2014 Activer une licence",
            tooltip="Saisir votre clé de licence DocPilote Pro",
            icon="accessories-text-editor",
        )
        item.connect("activate", lambda _i: self._run("activate-license", []))
        return (item,)
