import pytest

from keept.translate.langdetect import detect, may_already_be
from keept.translate.lexicon import foreign_leftovers

SENTENCES = [
    ("Die Datei konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.", "de"),
    ("Melden Sie sich an, um auf Ihre Dateien zuzugreifen.", "de"),
    ("The file could not be saved. Please try again later.", "en"),
    ("Click here to download the latest version", "en"),
    ("No se pudo guardar el archivo. Inténtalo de nuevo más tarde.", "es"),
    ("¿Dónde está la estación de tren?", "es"),
    ("Le fichier n'a pas pu être enregistré. Veuillez réessayer.", "fr"),
    ("Impossibile salvare il file. Riprova più tardi.", "it"),
    ("Não foi possível guardar o ficheiro. Tente novamente mais tarde.", "pt"),
    ("Het bestand kon niet worden opgeslagen. Probeer het later opnieuw.", "nl"),
    ("Nie można zapisać pliku. Spróbuj ponownie później.", "pl"),
    # OCR with the German engine reads "ó" as "ö"
    ("Configuraciön de Ia cuenta", "es"),
]

# Button labels: ambiguous alone, right with the language of the rest of the screen.
BUTTONS = {
    "de": ["Speichern", "Abbrechen", "Einstellungen", "Alle akzeptieren", "Weiter"],
    "en": ["Save", "Cancel", "Settings", "Accept all", "Next"],
    "es": ["Guardar", "Cancelar", "Configuración", "Aceptar todo", "Siguiente"],
    "fr": ["Enregistrer", "Annuler", "Paramètres", "Tout accepter", "Suivant"],
    "it": ["Salva", "Annulla", "Impostazioni", "Accetta tutto", "Avanti"],
    "pt": ["Guardar", "Cancelar", "Definições", "Aceitar tudo", "Seguinte"],
    "nl": ["Opslaan", "Annuleren", "Instellingen", "Alles accepteren", "Volgende"],
    "pl": ["Zapisz", "Anuluj", "Ustawienia", "Zaakceptuj wszystko", "Dalej"],
}


@pytest.mark.parametrize("text, lang", SENTENCES)
def test_detects_sentences(text, lang):
    assert detect(text)[0] == lang


@pytest.mark.parametrize("lang", list(BUTTONS))
def test_short_labels_with_screen_prior(lang):
    assert [detect(t, prior=lang)[0] for t in BUTTONS[lang]] == [lang] * len(BUTTONS[lang])


def test_strong_evidence_beats_prior():
    assert detect("Die Datei konnte nicht gespeichert werden.", prior="en")[0] == "de"
    assert detect("Le fichier n'a pas pu être enregistré. Veuillez réessayer.", prior="es")[0] == "fr"


def test_no_letters():
    assert detect("12:45 - 3/7") == (None, 0.0)
    assert detect("12:45", prior="es") == ("es", 0.0)


def test_probability_range():
    lang, p = detect("The file could not be saved and the application will close now.")
    assert lang == "en" and 0.5 < p <= 1.0


def test_short_names_stay_in_the_screen_language():
    # Folder names in a German Explorer window must not switch to another language.
    for name in ("Bulería", "SERCLE", "YTB", "Lumis Kaffeebar", "Konzert Februar"):
        assert detect(name, prior="de")[0] == "de", name


# Short labels in another language than the rest of the screen: judged by their own words.
# (label, screen language, real language)
FOREIGN_LABELS = [
    ("Restart now", "de", "en"),
    ("Release notes", "de", "en"),
    ("Guardar cambios", "de", "es"),
    ("Accept all", "es", "en"),
    ("Sign in", "es", "en"),
    ("Save changes", "de", "en"),
    ("Alle akzeptieren", "en", "de"),
    ("Speichern", "es", "de"),
    ("Jetzt neu starten", "en", "de"),
    ("Einstellungen", "es", "de"),
    ("Aceptar todo", "en", "es"),
    ("Iniciar sesión", "de", "es"),
    ("Cerrar", "en", "es"),
    ("Configuración", "de", "es"),
]


@pytest.mark.parametrize("text, screen, lang", FOREIGN_LABELS)
def test_short_foreign_label_detected_by_its_own_words(text, screen, lang):
    assert detect(text, prior=screen)[0] == lang


# Labels that may already be in the target language stay as they are; clearly foreign ones not.
@pytest.mark.parametrize("text, target, keep", [
    ("Guardar cambios", "es", True),
    ("Cancelar", "es", True),
    ("Aceptar todo", "es", True),
    ("Restart now", "es", False),
    ("Release notes", "es", False),
    ("Alle akzeptieren", "es", False),
    ("Restart now", "de", False),
    ("Release notes", "de", False),
    ("Speichern", "de", True),
    ("Willkommen zurück", "en", False),
    ("Save changes", "en", True),
    ("Guardar cambios", "en", False),
    # long texts are never skipped this way
    ("No se pudo guardar el archivo. Inténtalo de nuevo más tarde.", "es", False),
])
def test_may_already_be_in_target(text, target, keep):
    assert may_already_be(text, target) is keep


def test_mixed_translation_is_detected():
    assert foreign_leftovers("Release notes", "Publicación notes", "es") == ["notes"]
    assert foreign_leftovers("Restart now", "Neu starten now", "de") == ["now"]
    assert foreign_leftovers("Release notes", "Notas de la versión", "es") == []
    # names and loanwords are not mixing
    assert foreign_leftovers("Open in Google Play", "Abrir en Google Play", "es") == []
    long = "This update improves battery life and fixes a crash that happened when opening large files."
    assert foreign_leftovers(long, "Esta update mejora la batería y corrige un fallo al abrir archivos grandes.", "es") == []
