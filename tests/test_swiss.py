from keept.translate import swiss


def test_sharp_s_in_known_words():
    assert swiss.normalize("Bitte an den Strassenrand stellen.") == "Bitte an den Straßenrand stellen."
    assert swiss.normalize("Freundliche Grüsse") == "Freundliche Grüße"
    assert swiss.normalize("Fussgänger haben Vortritt.") == "Fußgänger haben Vorrang."
    assert swiss.normalize("Die Massnahmen gelten gemäss Reglement.") == "Die Maßnahmen gelten gemäß Reglement."
    assert swiss.normalize("Wir schliessen ausser am Sonntag.") == "Wir schließen außer am Sonntag."


def test_ss_after_short_vowels_stays():
    text = "Das Wasser muss in die Klasse, dass wir es wissen. Der Fluss, das Schloss, die Adresse."
    assert swiss.normalize(text) == text


def test_all_caps_keeps_ss():
    assert swiss.normalize("STRASSE GESPERRT") == "STRASSE GESPERRT"


def test_swiss_words():
    assert swiss.normalize("Kehrichtabfuhr") == "Müllabfuhr"
    assert swiss.normalize("der Hauskehricht und der Kehrichtsack") == "der Hausmüll und der Müllsack"
    assert swiss.normalize("Parkieren auf dem Trottoir ist verboten.") == "Parken auf dem Gehweg ist verboten."
    assert swiss.normalize("Das Auto war parkiert.") == "Das Auto war geparkt."
    assert swiss.normalize("Velos und Velofahrer auf dem Veloweg") == "Fahrräder und Radfahrer auf dem Radweg"
    assert swiss.normalize("Das Billett gilt im Spital.") == "Das Fahrkarte gilt im Krankenhaus."


def test_no_false_hits():
    text = "Das Hospital in Velours, die Velocity und der Parkplatz."
    assert swiss.normalize(text) == text


def test_vocabulary_decides_other_words():
    pieces = {"Meissel": 3, "Meißel": 1}.get
    assert swiss.normalize("Der Meissel", lambda w: pieces(w, 2)) == "Der Meißel"
    # without a vocabulary only the built-in list is used
    assert swiss.normalize("Der Meissel") == "Der Meissel"
