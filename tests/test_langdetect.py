import pytest

from keept.translate.langdetect import detect

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
