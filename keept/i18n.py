"""UI strings in the three supported languages. The UI follows the Windows language."""

from __future__ import annotations

# Languages the user interface itself is translated into (others fall back to English).
UI_LANGS = ("de", "en", "es")

_STRINGS = {
    "translate_screen": {"de": "Bildschirm übersetzen", "en": "Translate screen", "es": "Traducir pantalla"},
    "reading": {"de": "Text wird gelesen…", "en": "Reading text…", "es": "Leyendo texto…"},
    "translating": {"de": "Wird übersetzt…", "en": "Translating…", "es": "Traduciendo…"},
    "no_text": {
        "de": "Hier habe ich keinen Text gefunden",
        "en": "I couldn't find any text here",
        "es": "No he encontrado texto aquí",
    },
    "copy": {"de": "Kopieren", "en": "Copy", "es": "Copiar"},
    "copied": {"de": "Kopiert", "en": "Copied", "es": "Copiado"},
    "show_original": {"de": "Original", "en": "Original", "es": "Original"},
    "show_translation": {"de": "Übersetzung", "en": "Translation", "es": "Traducción"},
    "already_in": {
        "de": "Der Text ist bereits auf {lang}",
        "en": "The text is already in {lang}",
        "es": "El texto ya está en {lang}",
    },
    "downloading": {
        "de": "Sprachmodell wird heruntergeladen… {pct} %",
        "en": "Downloading language model… {pct}%",
        "es": "Descargando modelo de idioma… {pct} %",
    },
    "loading_model": {
        "de": "Sprachmodell wird vorbereitet…",
        "en": "Preparing language model…",
        "es": "Preparando modelo de idioma…",
    },
    "err_network": {
        "de": "Das Sprachmodell konnte nicht geladen werden. Prüfe die Internetverbindung.",
        "en": "Couldn't download the language model. Check your internet connection.",
        "es": "No he podido descargar el modelo de idioma. Revisa la conexión a internet.",
    },
    "err_integrity": {
        "de": "Das heruntergeladene Sprachmodell ist beschädigt oder wurde verändert und wurde verworfen.",
        "en": "The downloaded language model is damaged or was altered, so it was discarded.",
        "es": "El modelo de idioma descargado está dañado o ha sido alterado y se ha descartado.",
    },
    "err_disk": {
        "de": "Das Sprachmodell konnte nicht gespeichert werden. Ist die Festplatte voll?",
        "en": "Couldn't save the language model. Is the disk full?",
        "es": "No he podido guardar el modelo de idioma. ¿Está lleno el disco?",
    },
    "err_ocr": {
        "de": "Der Text konnte nicht gelesen werden",
        "en": "Couldn't read the text on screen",
        "es": "No he podido leer el texto de la pantalla",
    },
    "err_no_ocr": {
        "de": "Windows-Texterkennung fehlt. Details im Infobereich.",
        "en": "Windows text recognition is missing. See the tray icon.",
        "es": "Falta el reconocimiento de texto de Windows. Mira el icono de la bandeja.",
    },
    "err_translate": {
        "de": "Die Übersetzung ist fehlgeschlagen",
        "en": "Translation failed",
        "es": "La traducción ha fallado",
    },
    "err_capture": {
        "de": "Der Bildschirm konnte nicht aufgenommen werden",
        "en": "Couldn't capture the screen",
        "es": "No he podido capturar la pantalla",
    },
    "onboard_title": {
        "de": "In welche Sprache soll KeepT übersetzen?",
        "en": "Which language should KeepT translate into?",
        "es": "¿A qué idioma traduce KeepT?",
    },
    "onboard_done": {
        "de": "Fertig. Drücke {hotkey}, um den Bildschirm zu übersetzen.",
        "en": "All set. Press {hotkey} to translate your screen.",
        "es": "Listo. Pulsa {hotkey} para traducir la pantalla.",
    },
    # Tray
    "tray_translate": {"de": "Übersetzen ({hotkey})", "en": "Translate ({hotkey})", "es": "Traducir ({hotkey})"},
    "tray_target": {"de": "Zielsprache", "en": "Translate into", "es": "Traducir a"},
    "tray_system_lang": {
        "de": "Windows-Sprache ({lang})",
        "en": "Windows language ({lang})",
        "es": "Idioma de Windows ({lang})",
    },
    "tray_hotkey": {"de": "Tastenkürzel", "en": "Shortcut", "es": "Atajo de teclado"},
    "tray_hotkey_custom": {"de": "Eigenes Kürzel…", "en": "Custom shortcut…", "es": "Atajo personalizado…"},
    "tray_autostart": {"de": "Mit Windows starten", "en": "Start with Windows", "es": "Iniciar con Windows"},
    "tray_models": {"de": "Sprachmodelle", "en": "Language models", "es": "Modelos de idioma"},
    "tray_models_none": {
        "de": "Noch keine heruntergeladen",
        "en": "None downloaded yet",
        "es": "Ninguno descargado todavía",
    },
    "tray_models_delete": {"de": "Löschen", "en": "Delete", "es": "Eliminar"},
    "tray_models_open": {"de": "Ordner öffnen", "en": "Open folder", "es": "Abrir carpeta"},
    "tray_quit": {"de": "Beenden", "en": "Quit", "es": "Salir"},
    "tray_ready_title": {"de": "KeepT ist bereit", "en": "KeepT is ready", "es": "KeepT está listo"},
    "tray_ready_body": {
        "de": "Drücke {hotkey}, um Text auf dem Bildschirm zu übersetzen.",
        "en": "Press {hotkey} to translate text on your screen.",
        "es": "Pulsa {hotkey} para traducir el texto de la pantalla.",
    },
    "onboard_hotkey": {
        "de": "Kürzel: {hotkey} (du kannst es ändern)",
        "en": "Shortcut: {hotkey} (you can change it)",
        "es": "Atajo: {hotkey} (puedes cambiarlo)",
    },
    "hotkey_fallback": {
        "de": "{hotkey} ist nicht verfügbar (eine andere App nutzt es, oder die Tastatur sendet es nur mit Fn). "
              "KeepT verwendet jetzt {fallback}. Du kannst es im Menü ändern.",
        "en": "{hotkey} is not available (another app uses it, or the keyboard only sends it with Fn). "
              "KeepT now uses {fallback}. You can change it from the menu.",
        "es": "{hotkey} no está disponible (otra aplicación la usa o el teclado solo la envía con Fn). "
              "KeepT usa ahora {fallback}. Puedes cambiarlo desde el menú.",
    },
    "hotkey_busy": {
        "de": "Das Kürzel {hotkey} wird bereits von einer anderen App verwendet. Wähle im Menü ein anderes.",
        "en": "The shortcut {hotkey} is already used by another app. Pick another one from the menu.",
        "es": "El atajo {hotkey} ya lo usa otra aplicación. Elige otro desde el menú.",
    },
    "hotkey_taken_kept": {
        "de": "{new} wird bereits von einer anderen App verwendet. KeepT bleibt bei {old}.",
        "en": "{new} is already used by another app. KeepT keeps using {old}.",
        "es": "{new} ya lo usa otra aplicación. KeepT sigue usando {old}.",
    },
    "hotkey_taken_short": {
        "de": "Wird bereits von einer anderen App verwendet. Probiere eine andere Kombination.",
        "en": "Already used by another app. Try another combination.",
        "es": "Ya lo usa otra aplicación. Prueba otra combinación.",
    },
    "hotkey_none_active": {"de": "kein Kürzel aktiv", "en": "no shortcut active", "es": "sin atajo activo"},
    "tray_updates": {"de": "Nach Updates suchen", "en": "Check for updates", "es": "Buscar actualizaciones"},
    "tray_update_item": {"de": "KeepT {version} herunterladen", "en": "Download KeepT {version}",
                         "es": "Descargar KeepT {version}"},
    "update_title": {"de": "Neue KeepT-Version", "en": "New KeepT version", "es": "Nueva versión de KeepT"},
    "update_body": {
        "de": "KeepT {version} ist verfügbar. Klicke hier, um die Downloadseite zu öffnen.",
        "en": "KeepT {version} is available. Click here to open the download page.",
        "es": "KeepT {version} está disponible. Haz clic aquí para abrir la página de descarga.",
    },
    "tray_about": {"de": "Über KeepT", "en": "About KeepT", "es": "Acerca de KeepT"},
    "about_intro": {
        "de": "Übersetzt den Bildschirm direkt auf deinem PC. Keine Konten, keine Daten verlassen den Computer.",
        "en": "Translates your screen right on your PC. No accounts, nothing leaves your computer.",
        "es": "Traduce la pantalla en tu propio PC. Sin cuentas y sin que nada salga del ordenador.",
    },
    "about_licenses_folder": {"de": "Lizenztexte öffnen", "en": "Open license texts", "es": "Abrir textos de licencia"},
    "credit_models": {"de": "Übersetzungsmodelle", "en": "Translation models", "es": "Modelos de traducción"},
    "credit_libraries": {"de": "Bibliotheken", "en": "Libraries", "es": "Bibliotecas"},
    "credit_license": {"de": "Lizenz", "en": "License", "es": "Licencia"},
    "credit_license_unstated": {
        "de": "im Paket nicht angegeben",
        "en": "not stated in the package",
        "es": "no indicada en el paquete",
    },
    "credit_role_all_pairs": {"de": "alle Sprachpaare", "en": "all language pairs", "es": "todos los pares de idiomas"},
    "credit_role_langid": {"de": "Spracherkennung", "en": "language detection", "es": "detección de idioma"},
    "credit_role_ui": {"de": "Oberfläche", "en": "user interface", "es": "interfaz"},
    "credit_role_engine": {"de": "Übersetzungsengine", "en": "translation engine", "es": "motor de traducción"},
    "credit_role_tokens": {"de": "Textzerlegung", "en": "tokenization", "es": "segmentación del texto"},
    "credit_role_misc": {"de": "Laufzeit", "en": "runtime", "es": "ejecución"},
    "credit_note_converted": {
        "de": "Werden bei Bedarf von den offiziellen OPUS-MT-Servern geladen und verändert: lokal in das "
        "CTranslate2-Format (int8) umgewandelt.",
        "en": "Downloaded on demand from the official OPUS-MT storage and modified: converted locally to the "
        "CTranslate2 format (int8).",
        "es": "Se descargan cuando hacen falta desde los servidores oficiales de OPUS-MT y se modifican: se "
        "convierten en tu equipo al formato CTranslate2 (int8).",
    },
    "credit_note_lgpl": {
        "de": "Dynamisch gelinkt; die Qt-Bibliotheken im Programmordner können ersetzt werden.",
        "en": "Dynamically linked; the Qt libraries in the program folder can be replaced.",
        "es": "Enlazado dinámicamente; las bibliotecas de Qt de la carpeta del programa se pueden sustituir.",
    },
    "credit_full_texts": {
        "de": "Die vollständigen Lizenztexte liegen im Ordner „licenses“ des Programms.",
        "en": "The full license texts are in the program's \"licenses\" folder.",
        "es": "Los textos completos de las licencias están en la carpeta «licenses» del programa.",
    },
    "hotkey_dialog_title": {"de": "Tastenkürzel festlegen", "en": "Set shortcut", "es": "Elegir atajo"},
    "hotkey_dialog_body": {
        "de": "Drücke die neue Tastenkombination (mit Strg, Alt oder Umschalt). Esc zum Abbrechen.",
        "en": "Press the new key combination (with Ctrl, Alt or Shift). Esc to cancel.",
        "es": "Pulsa la nueva combinación (con Ctrl, Alt o Mayús). Esc para cancelar.",
    },
    "ocr_missing_title": {
        "de": "Texterkennung unvollständig",
        "en": "Text recognition incomplete",
        "es": "Reconocimiento de texto incompleto",
    },
    "ocr_missing_one": {
        "de": "Für {lang} fehlt die Windows-Texterkennung, der Text wird ungenauer gelesen. Installiere sie unter "
        "Einstellungen > Zeit und Sprache > Sprache ({lang} hinzufügen) oder in PowerShell als Administrator: "
        "Add-WindowsCapability -Online -Name \"Language.OCR~~~{tag}~0.0.1.0\"",
        "en": "Windows text recognition for {lang} is missing, so the text is read less accurately. Install it in "
        "Settings > Time & language > Language (add {lang}) or in PowerShell as administrator: "
        "Add-WindowsCapability -Online -Name \"Language.OCR~~~{tag}~0.0.1.0\"",
        "es": "Falta el reconocimiento de texto de Windows para {lang}, así que el texto se lee con menos precisión. "
        "Instálalo en Configuración > Hora e idioma > Idioma (agrega {lang}) o en PowerShell como administrador: "
        "Add-WindowsCapability -Online -Name \"Language.OCR~~~{tag}~0.0.1.0\"",
    },
    "ocr_missing_body": {
        "de": "Für {langs} fehlt die Windows-Texterkennung. Installiere sie unter Einstellungen > Zeit und Sprache > Sprache "
        "oder in PowerShell als Administrator: Add-WindowsCapability -Online -Name \"Language.OCR~~~{tag}~0.0.1.0\"",
        "en": "Windows text recognition is missing for {langs}. Install it in Settings > Time & language > Language, "
        "or in PowerShell as administrator: Add-WindowsCapability -Online -Name \"Language.OCR~~~{tag}~0.0.1.0\"",
        "es": "Falta el reconocimiento de texto de Windows para {langs}. Instálalo en Configuración > Hora e idioma > Idioma "
        "o en PowerShell como administrador: Add-WindowsCapability -Online -Name \"Language.OCR~~~{tag}~0.0.1.0\"",
    },
}

_ui_lang = "en"


def set_ui_lang(lang: str) -> None:
    global _ui_lang
    _ui_lang = lang if lang in UI_LANGS else "en"


def ui_lang() -> str:
    return _ui_lang


def tr(key: str, **kwargs) -> str:
    entry = _STRINGS[key]
    text = entry.get(_ui_lang) or entry["en"]
    return text.format(**kwargs) if kwargs else text


_KEY_NAMES = {
    "de": {"Ctrl": "Strg", "Shift": "Umschalt", "Space": "Leertaste"},
    "es": {"Shift": "Mayús", "Space": "Espacio"},
}


def hotkey_label(text: str) -> str:
    """Hotkey as printed on the user's keyboard, e.g. "Strg+Alt+T" on German Windows."""
    names = _KEY_NAMES.get(_ui_lang, {})
    return "+".join(names.get(part, part) for part in text.split("+"))


def lang_name(code: str) -> str:
    """Languages are always shown with their native name (Deutsch, Français, Polski...)."""
    from .languages import native_name

    return native_name(code)
