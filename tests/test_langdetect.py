import pytest

from keept.translate.langdetect import detect


@pytest.mark.parametrize(
    "text, lang",
    [
        ("Die Datei konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.", "de"),
        ("Wir verwenden Cookies, um Inhalte zu personalisieren und die Zugriffe zu analysieren.", "de"),
        ("Melden Sie sich an, um auf Ihre Dateien zuzugreifen.", "de"),
        ("Größe ändern", "de"),
        ("The file could not be saved. Please try again later.", "en"),
        ("This update improves battery life and fixes a crash when opening large files.", "en"),
        ("Click here to download the latest version", "en"),
        ("No se pudo guardar el archivo. Inténtalo de nuevo más tarde.", "es"),
        ("¿Dónde está la estación de tren?", "es"),
        ("Configuración de la cuenta", "es"),
        ("Guardar cambios", "es"),
        ("Contraseña", "es"),
        # OCR with the German engine reads "ó" as "ö"
        ("Configuraciön de Ia cuenta", "es"),
    ],
)
def test_detects_language(text, lang):
    assert detect(text)[0] == lang


def test_prior_decides_ambiguous_short_text():
    assert detect("OK", prior="es")[0] == "es"
    assert detect("Login", prior="de")[0] == "de"


def test_no_evidence_without_prior():
    assert detect("12:45 - 3/7") == (None, 0.0)


def test_strong_evidence_beats_prior():
    assert detect("Die Datei konnte nicht gespeichert werden.", prior="en")[0] == "de"


def test_confidence_range():
    lang, conf = detect("The file could not be saved and the application will close now.")
    assert lang == "en" and 0.5 < conf <= 1.0
