; DocPilote pour Windows — installeur NSIS (généré par gen_nsi.py)
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
!define PRODUCT_VERSION "1.0.3"
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
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\summarize" "MUIVerb" "Résumer"
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\summarize\command" "" '"$INSTDIR\docpilote_client.exe" summarize "%1"'
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\respond" "MUIVerb" "Préparer une réponse"
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\respond\command" "" '"$INSTDIR\docpilote_client.exe" respond "%1"'
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\explain" "MUIVerb" "Explique-moi ce document"
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\explain\command" "" '"$INSTDIR\docpilote_client.exe" explain "%1"'
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\decide" "MUIVerb" "Quelles actions dois-je entreprendre ?"
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\decide\command" "" '"$INSTDIR\docpilote_client.exe" decide "%1"'
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\risks" "MUIVerb" "Détecter les risques"
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\risks\command" "" '"$INSTDIR\docpilote_client.exe" risks "%1"'
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\checklist" "MUIVerb" "Créer une checklist"
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\checklist\command" "" '"$INSTDIR\docpilote_client.exe" checklist "%1"'
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\extract" "MUIVerb" "Extraire (JSON)"
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\extract\command" "" '"$INSTDIR\docpilote_client.exe" extract "%1"'
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\ask" "MUIVerb" "Interroger"
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\ask\command" "" '"$INSTDIR\docpilote_client.exe" ask "%1"'
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\transform" "MUIVerb" "Transformer"
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\transform\command" "" '"$INSTDIR\docpilote_client.exe" transform "%1"'
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\activate-license" "MUIVerb" "🔑 Activer une licence"
    WriteRegStr HKCU "Software\Classes\DocPilote.Actions\Shell\activate-license\command" "" '"$INSTDIR\docpilote_client.exe" activate-license'

    ; -------------------------------------------------------------
    ; Enregistrement du menu "DocPilote" (cascade) + verbe "Comparer"
    ; pour chaque extension de fichier supportée
    ; -------------------------------------------------------------

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pdf\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pdf\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pdf\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pdf\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pdf\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pdf\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pdf\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.docx\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.docx\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.docx\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.docx\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.docx\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.docx\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.docx\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.doc\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.doc\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.doc\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.doc\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.doc\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.doc\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.doc\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xlsx\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xlsx\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xlsx\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xlsx\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xlsx\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xlsx\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xlsx\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xls\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xls\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xls\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xls\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xls\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xls\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.xls\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pptx\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pptx\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pptx\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pptx\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pptx\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pptx\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pptx\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ppt\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ppt\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ppt\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ppt\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ppt\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ppt\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ppt\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odt\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odt\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odt\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odt\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odt\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odt\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odt\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ods\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ods\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ods\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ods\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ods\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ods\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ods\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odp\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odp\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odp\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odp\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odp\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odp\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.odp\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.txt\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.txt\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.txt\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.txt\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.txt\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.txt\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.txt\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.md\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.md\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.md\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.md\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.md\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.md\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.md\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.rtf\shell\DocPilote" "MUIVerb" "DocPilote"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.rtf\shell\DocPilote" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.rtf\shell\DocPilote" "ExtendedSubCommandsKey" "DocPilote.Actions"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.rtf\shell\DocPilote" "" ""

    ; Verbe "Comparer" séparé (top-level, pas dans la cascade) — nécessite
    ; MultiSelectModel=Player pour recevoir les 2 fichiers sélectionnés en un
    ; seul appel plutôt qu'un appel par fichier (comportement non confirmé
    ; en conditions réelles, cf. en-tête du script).
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.rtf\shell\DocPiloteCompare" "" "DocPilote — Comparer (2 fichiers)"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.rtf\shell\DocPiloteCompare" "MultiSelectModel" "Player"
    WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.rtf\shell\DocPiloteCompare\command" "" '"$INSTDIR\docpilote_client.exe" compare %1'

    ; Activer une licence depuis le clic droit dans le vide (fond de dossier),
    ; sans devoir selectionner un document au prealable -- equivalent Windows
    ; du get_background_items() de l'extension Nautilus Linux.
    WriteRegStr HKCU "Software\Classes\Directory\Background\shell\DocPiloteActivateLicense" "" "DocPilote — Activer une licence"
    WriteRegStr HKCU "Software\Classes\Directory\Background\shell\DocPiloteActivateLicense" "Icon" "$INSTDIR\docpilote_client.exe"
    WriteRegStr HKCU "Software\Classes\Directory\Background\shell\DocPiloteActivateLicense\command" "" '"$INSTDIR\docpilote_client.exe" activate-license'

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
    DeleteRegKey HKCU "Software\Classes\DocPilote.Actions\Shell\summarize"
    DeleteRegKey HKCU "Software\Classes\DocPilote.Actions\Shell\respond"
    DeleteRegKey HKCU "Software\Classes\DocPilote.Actions\Shell\explain"
    DeleteRegKey HKCU "Software\Classes\DocPilote.Actions\Shell\decide"
    DeleteRegKey HKCU "Software\Classes\DocPilote.Actions\Shell\risks"
    DeleteRegKey HKCU "Software\Classes\DocPilote.Actions\Shell\checklist"
    DeleteRegKey HKCU "Software\Classes\DocPilote.Actions\Shell\extract"
    DeleteRegKey HKCU "Software\Classes\DocPilote.Actions\Shell\ask"
    DeleteRegKey HKCU "Software\Classes\DocPilote.Actions\Shell\transform"
    DeleteRegKey HKCU "Software\Classes\DocPilote.Actions\Shell\activate-license"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.pdf\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.pdf\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.docx\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.docx\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.doc\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.doc\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.xlsx\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.xlsx\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.xls\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.xls\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.pptx\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.pptx\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.ppt\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.ppt\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.odt\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.odt\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.ods\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.ods\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.odp\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.odp\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.txt\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.txt\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.md\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.md\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.rtf\shell\DocPilote"
    DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.rtf\shell\DocPiloteCompare"
    DeleteRegKey HKCU "Software\Classes\Directory\Background\shell\DocPiloteActivateLicense"

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
