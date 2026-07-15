#!/usr/bin/env python3
"""Génère docpilote.nsi à partir d'un template, en développant les blocs de
registre répétitifs par extension (NSIS n'a pas de boucle native pratique
pour ce cas — plus simple et plus fiable de générer le texte explicitement)."""

EXTENSIONS = [
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".odt", ".ods", ".odp", ".txt", ".md", ".rtf",
]

ACTIONS = [
    ("summarize", "Résumer"),
    ("respond", "Préparer une réponse"),
    ("explain", "Explique-moi ce document"),
    ("decide", "Quelles actions dois-je entreprendre ?"),
    ("risks", "Détecter les risques"),
    ("checklist", "Créer une checklist"),
    ("extract", "Extraire (JSON)"),
    ("ask", "Interroger"),
    ("transform", "Transformer"),
]

HEADER = r'''; DocPilote pour Windows — installeur NSIS (généré par gen_nsi.py)
; Installation par utilisateur (HKCU + %LOCALAPPDATA%), sans droits admin requis.
;
; Menu contextuel construit via le pattern officiel Microsoft
; "ExtendedSubCommandsKey" (cascading menu réutilisable) : un seul jeu
; d'actions déclaré sous DocPilote.Actions, référencé par chaque extension
; de fichier supportée. Voir :
; https://learn.microsoft.com/windows/win32/shell/how-to-create-cascading-menus-with-the-extendedsubcommandskey-registry-entry
;
; "Comparer" (2 fichiers) est enregistré séparément en verbe top-level avec
; MultiSelectModel=Player (pattern utilisé par Windows Media Player pour
; ouvrir plusieurs fichiers sélectionnés en une seule instance) — NON
; TESTÉ en conditions réelles (aucune machine Windows physique disponible
; pour ce projet), à valider par Camille lors du premier vrai test.

!define PRODUCT_NAME "DocPilote"
!define PRODUCT_VERSION "1.0.4"
!define PRODUCT_PUBLISHER "Prestalibre"
!define PRODUCT_URL "https://docpilote.prestalibre.org"

Name "${PRODUCT_NAME}"
OutFile "DocPilote-Setup-${PRODUCT_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\DocPilote"
RequestExecutionLevel user
SetCompressor /SOLID lzma

!include "MUI2.nsh"
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "French"

Section "Install"
    SetOutPath "$INSTDIR"
    File "docpilote_client.exe"

    WriteUninstaller "$INSTDIR\uninstall.exe"

    WriteRegStr HKCU "Software\DocPilote" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\DocPilote" "Version" "${PRODUCT_VERSION}"

    ; -------------------------------------------------------------
    ; Jeu d'actions partagé (cascade), 9 actions mono-fichier
    ; -------------------------------------------------------------
'''

FOOTER_ACTIONS_END = ""

CASCADE_PER_EXT_TEMPLATE = '''
    WriteRegStr HKCU "Software\\Classes\\SystemFileAssociations\\{ext}\\shell\\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\\Classes\\SystemFileAssociations\\{ext}\\shell\\DocPilote" "Icon" "$INSTDIR\\docpilote_client.exe"
    WriteRegStr HKCU "Software\\Classes\\SystemFileAssociations\\{ext}\\shell\\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\\Classes\\SystemFileAssociations\\{ext}\\shell\\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\\Classes\\SystemFileAssociations\\{ext}\\shell\\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\\Classes\\SystemFileAssociations\\{ext}\\shell\\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\\Classes\\SystemFileAssociations\\{ext}\\shell\\DocPiloteCompare\\command" "" '"$INSTDIR\\docpilote_client.exe" compare %1'
'''

ACTION_TEMPLATE = '''    WriteRegStr HKCU "Software\\Classes\\DocPilote.Actions\\Shell\\{key}" "MUIVerb" "{label}"
    WriteRegStr HKCU "Software\\Classes\\DocPilote.Actions\\Shell\\{key}\\command" "" '"$INSTDIR\\docpilote_client.exe" {key} "%1"'
'''

# "Activer une licence" n'agit pas sur un fichier (pas de %1) : ajoutee a la
# meme cascade DocPilote.Actions que les 9 actions ci-dessus, ce qui la fait
# apparaitre en bas du sous-menu DocPilote au clic droit sur un document
# supporte -- meme emplacement que sur Linux (extension Nautilus/Nemo/Thunar).
ACTIVATE_LICENSE_CASCADE_ENTRY = '''    WriteRegStr HKCU "Software\\Classes\\DocPilote.Actions\\Shell\\activate-license" "MUIVerb" "\U0001F511 Activer une licence"
    WriteRegStr HKCU "Software\\Classes\\DocPilote.Actions\\Shell\\activate-license\\command" "" '"$INSTDIR\\docpilote_client.exe" activate-license'
'''

# Verbe separe sur le clic droit "fond de dossier" (aucun fichier selectionne)
# -- equivalent de get_background_items() de l'extension Nautilus Linux, qui
# permet d'activer une licence sans devoir selectionner un document au prealable.
ACTIVATE_LICENSE_BACKGROUND = r'''
    ; Activer une licence depuis le clic droit dans le vide (fond de dossier),
    ; sans devoir selectionner un document au prealable -- equivalent Windows
    ; du get_background_items() de l'extension Nautilus Linux.
    WriteRegStr HKCU "Software\Classes\Directory\Background\shell\DocPiloteActivateLicense" "" "DocPilote — Activer une licence"
    WriteRegStr HKCU "Software\Classes\Directory\Background\shell\DocPiloteActivateLicense" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\Directory\Background\shell\DocPiloteActivateLicense\command" "" '"$INSTDIR\docpilote_client.exe" activate-license'
'''

MIDDLE = '''
    ; -------------------------------------------------------------
    ; Enregistrement du menu "DocPilote" (cascade) + verbe "Comparer"
    ; pour chaque extension de fichier supportée
    ; -------------------------------------------------------------
'''

SHORTCUTS = r'''
    ; Raccourci menu Démarrer : "DocPilote — Activer une licence"
    CreateDirectory "$SMPROGRAMS\DocPilote"
    CreateShortcut "$SMPROGRAMS\DocPilote\DocPilote - Activer une licence.lnk" \
        "$INSTDIR\docpilote_client.exe" "activate-license" \
        "$INSTDIR\docpilote_client.exe" 0
    CreateShortcut "$SMPROGRAMS\DocPilote\Desinstaller DocPilote.lnk" \
        "$INSTDIR\uninstall.exe"

    ; Notifie l'Explorateur que les associations de fichiers ont changé
    ; (best-effort, l'utilisateur peut aussi simplement rouvrir une fenêtre)
    System::Call 'shell32::SHChangeNotify(i 0x8000000, i 0, i 0, i 0)'
SectionEnd

Function un.onInit
FunctionEnd

Section "Uninstall"
    ; Suppression des actions cascade partagées
'''

UNINSTALL_ACTION_TEMPLATE = '    DeleteRegKey HKCU "Software\\Classes\\DocPilote.Actions\\Shell\\{key}"\n'

UNINSTALL_PER_EXT_TEMPLATE = '''    DeleteRegKey HKCU "Software\\Classes\\SystemFileAssociations\\{ext}\\shell\\DocPilote"
    DeleteRegKey HKCU "Software\\Classes\\SystemFileAssociations\\{ext}\\shell\\DocPiloteCompare"
'''

FOOTER = r'''
    DeleteRegKey HKCU "Software\Classes\DocPilote.Actions"
    DeleteRegKey HKCU "Software\DocPilote"

    Delete "$SMPROGRAMS\DocPilote\DocPilote - Activer une licence.lnk"
    Delete "$SMPROGRAMS\DocPilote\Desinstaller DocPilote.lnk"
    RMDir "$SMPROGRAMS\DocPilote"

    Delete "$INSTDIR\docpilote_client.exe"
    Delete "$INSTDIR\uninstall.exe"
    RMDir "$INSTDIR"

    System::Call 'shell32::SHChangeNotify(i 0x8000000, i 0, i 0, i 0)'
SectionEnd
'''


def main():
    parts = [HEADER]
    for key, label in ACTIONS:
        parts.append(ACTION_TEMPLATE.format(key=key, label=label))
    parts.append(ACTIVATE_LICENSE_CASCADE_ENTRY)

    parts.append(MIDDLE)
    for ext in EXTENSIONS:
        parts.append(CASCADE_PER_EXT_TEMPLATE.format(ext=ext))

    parts.append(ACTIVATE_LICENSE_BACKGROUND)

    parts.append(SHORTCUTS)
    for key, _ in ACTIONS:
        parts.append(UNINSTALL_ACTION_TEMPLATE.format(key=key))
    parts.append(UNINSTALL_ACTION_TEMPLATE.format(key="activate-license"))
    for ext in EXTENSIONS:
        parts.append(UNINSTALL_PER_EXT_TEMPLATE.format(ext=ext))
    parts.append(
        '    DeleteRegKey HKCU "Software\\Classes\\Directory\\Background\\shell\\DocPiloteActivateLicense"\n'
    )

    parts.append(FOOTER)

    with open("docpilote.nsi", "w", encoding="utf-8") as f:
        f.write("".join(parts))
    print("docpilote.nsi generated")


if __name__ == "__main__":
    main()
