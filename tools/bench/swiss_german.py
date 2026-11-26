"""Does rewriting Swiss Standard German before translating help? chrF against references.

    python tools/bench/swiss_german.py [target]

Sentences are typical Swiss texts (municipal notices, signs, public transport, letters) with
Swiss spelling and words. Each is translated as it is and after keept.translate.swiss.normalize,
with the installed de->target model. Reference translations are Spanish, so the score is only
printed for target "es"; for other targets the outputs are printed for a manual look.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from keept.translate import swiss  # noqa: E402
from keept.translate.translator import Translator, route  # noqa: E402

SENTENCES = [
    ("Die Kehrichtabfuhr findet jeden Dienstag statt.", "La recogida de basura tiene lugar todos los martes."),
    ("Bitte stellen Sie die Säcke bis spätestens 7.00 Uhr an den Strassenrand.",
     "Por favor, coloque las bolsas en el borde de la carretera a más tardar a las 7:00."),
    ("Ab dem 1. Dezember wird der Hauskehricht am Dienstag abgeholt.",
     "A partir del 1 de diciembre, la basura doméstica se recogerá el martes."),
    ("Freundliche Grüsse", "Saludos cordiales"),
    ("Parkieren auf dem Trottoir ist verboten.", "Está prohibido aparcar en la acera."),
    ("Velos dürfen nicht im Treppenhaus abgestellt werden.", "No se pueden dejar bicicletas en la escalera."),
    ("Die Strasse ist wegen Bauarbeiten gesperrt.", "La calle está cerrada por obras."),
    ("Das Billett muss vor der Fahrt gelöst werden.", "El billete debe comprarse antes del viaje."),
    ("Er wurde ins Spital gebracht.", "Fue llevado al hospital."),
    ("Die Massnahmen gelten ab sofort.", "Las medidas se aplican a partir de ahora."),
    ("Fussgänger haben Vortritt.", "Los peatones tienen prioridad."),
    ("Wir schliessen um 18 Uhr.", "Cerramos a las 18 horas."),
    ("Das Auto war auf dem Trottoir parkiert.", "El coche estaba aparcado en la acera."),
    ("Der Kehrichtsack muss gebührenpflichtig sein.", "La bolsa de basura debe ser de pago."),
    ("Grösse und Gewicht spielen keine Rolle.", "El tamaño y el peso no importan."),
    ("Bitte rufen Sie mich auf dem Natel an.", "Por favor, llámeme al móvil."),
    ("Der Abwart ist heute nicht da.", "El conserje no está hoy."),
    ("Die Velofahrer müssen den Veloweg benutzen.", "Los ciclistas deben usar el carril bici."),
    ("Gemäss Reglement ist das Grillieren im Park erlaubt.",
     "Según el reglamento, está permitido hacer barbacoa en el parque."),
    ("Bei starkem Schneefall kann sich die Abfuhr verschieben.",
     "En caso de fuertes nevadas, la recogida puede retrasarse."),
    ("Das Sperrgut wird zweimal im Jahr abgeholt.", "Los residuos voluminosos se recogen dos veces al año."),
    ("Grüngut gehört nicht in den Kehrichtsack.", "Los residuos verdes no van en la bolsa de basura."),
    ("Allfällige Fragen beantworten wir gerne innert drei Tagen.",
     "Respondemos con gusto a posibles preguntas en un plazo de tres días."),
    ("Der Zug fährt auf Perron 4 ab.", "El tren sale del andén 4."),
    ("Die Hauptstrasse bleibt bis Ende Monat geschlossen.", "La calle principal permanece cerrada hasta fin de mes."),
    ("Wegen eines Unterbruchs fallen alle Züge aus.", "Debido a una interrupción, se cancelan todos los trenes."),
    ("Das Schulhaus liegt ausserhalb des Dorfes.", "La escuela está fuera del pueblo."),
    ("Der Coiffeur ist am Montag geschlossen.", "La peluquería está cerrada el lunes."),
]


def chrf(hyp: str, ref: str, n: int = 6, beta: float = 2.0) -> float:
    """chrF (Popović 2015): character n-gram F-score, spaces removed, n = 1..6, beta 2."""
    hyp, ref = hyp.replace(" ", ""), ref.replace(" ", "")
    precisions, recalls = [], []
    for k in range(1, n + 1):
        h = Counter(hyp[i:i + k] for i in range(len(hyp) - k + 1))
        r = Counter(ref[i:i + k] for i in range(len(ref) - k + 1))
        if not h or not r:
            continue
        match = sum((h & r).values())
        precisions.append(match / sum(h.values()))
        recalls.append(match / sum(r.values()))
    if not precisions:
        return 0.0
    p, r = sum(precisions) / len(precisions), sum(recalls) / len(recalls)
    return 0.0 if p + r == 0 else 100 * (1 + beta ** 2) * p * r / (beta ** 2 * p + r)


def main() -> int:
    tgt = sys.argv[1] if len(sys.argv) > 1 else "es"
    tr = Translator()
    tr.prepare("de", tgt)
    models = [tr.model(p) for p in route("de", tgt)]

    def run(texts):
        for m in models:
            texts = m.translate(texts)
        return texts

    tok = models[0].tokenizer
    src = [s for s, _ in SENTENCES]
    norm = [swiss.normalize(s, lambda w: len(tok.encode(w))) for s in src]
    before, after = run(src), run(norm)
    if tgt == "es":
        sb = [chrf(h, r) for h, (_, r) in zip(before, SENTENCES)]
        sa = [chrf(h, r) for h, (_, r) in zip(after, SENTENCES)]
        for (s, r), b, a, x, y in zip(SENTENCES, before, after, sb, sa):
            mark = "+" if y > x + 1 else "-" if y < x - 1 else "="
            print(f"{mark} {x:5.1f} -> {y:5.1f}  {s}\n      as is:      {b}\n      normalized: {a}")
        print(f"\nchrF as is {sum(sb) / len(sb):.1f}, normalized {sum(sa) / len(sa):.1f} "
              f"({sum(y > x + 1 for x, y in zip(sb, sa))} better, {sum(y < x - 1 for x, y in zip(sb, sa))} worse, "
              f"{len(SENTENCES)} sentences)")
    else:
        for s, b, a in zip(src, before, after):
            print(f"{s}\n   as is:      {b}\n   normalized: {a}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
