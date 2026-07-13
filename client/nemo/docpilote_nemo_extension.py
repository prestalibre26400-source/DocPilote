"""Extension Nemo native pour DocPilote.

Ajoute une entrée "DocPilote" au clic droit sur les documents supportés
(PDF, Word, ODT, texte, RTF), qui ouvre un vrai sous-menu au survol
(comme "Ouvrir avec"), sans fenêtre GTK flottante séparée.
"""
import os
import subprocess
import urllib.parse

from gi.repository import GObject, Nemo

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
            tip="Analyser ce document avec DocPilote",
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
            label="\U0001F511 Activer une licence",
            tip="Saisir votre clé de licence DocPilote Pro",
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
            label="DocPilote \u2014 Activer une licence",
            tip="Saisir votre clé de licence DocPilote Pro",
            icon="accessories-text-editor",
        )
        item.connect("activate", lambda _i: self._run("activate-license", []))
        return [item]
