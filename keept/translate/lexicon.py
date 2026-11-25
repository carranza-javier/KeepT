"""Frequent words and common interface words per supported language.

Statistical detection is unreliable for labels of one to four words ("Restart now" scores
almost as German as English). These lists let a short label be recognised by its own words.
A word may belong to several languages ("cancelar" is Spanish and Portuguese).
"""

from __future__ import annotations

import re

_WORDS = {
    "en": """the and or of to in on at up out for with from by are your you we this that here there now new all more less not yes
        save cancel settings setting accept reject decline next back previous close delete remove edit view help sign
        log login logout restart release notes note update updates download install search home file files share copy
        paste undo redo send reply continue skip done apply change changes account profile password welcome learn read
        show hide details options privacy terms start stop play pause try again later version about contact message
        messages today yesterday please retry submit upload create add select manage print language allow agree got
        it's don't can't see what's""",
    "de": """der die das den dem des und oder nicht in an auf mit für von zu ist sind sie ihr ihre ihren ihrem alle jetzt neu
        neue speichern abbrechen einstellungen akzeptieren ablehnen weiter zurück öffnen schließen löschen bearbeiten
        hilfe anmelden abmelden neustarten neu starten aktualisierung aktualisieren herunterladen installieren suchen
        datei dateien teilen kopieren einfügen senden antworten fertig übernehmen ändern änderungen konto passwort
        willkommen mehr erfahren anzeigen ausblenden optionen datenschutz beenden später erneut versuchen bitte über
        kontakt nachricht nachrichten heute gestern hochladen erstellen hinzufügen auswählen verwalten ja nein
        zustimmen weitere startseite drucken sprache zulassen jetzt""",
    "es": """el la los las del y con para por un una su sus tu tus no sí todo todos todas ahora nuevo nueva guardar
        cancelar configuración ajustes aceptar rechazar siguiente atrás anterior abrir cerrar eliminar borrar editar
        ver ayuda iniciar sesión reiniciar actualizar actualización descargar instalar buscar inicio archivo archivos
        compartir copiar pegar deshacer enviar responder continuar omitir listo aplicar cambiar cambios cuenta perfil
        contraseña bienvenido bienvenida más saber mostrar ocultar detalles opciones privacidad términos empezar
        detener intentar acerca contacto mensaje mensajes hoy ayer subir crear añadir agregar seleccionar
        administrar notas versión idioma imprimir permitir de en o""",
    "pt": """o os as do da dos das e ou em com para por um uma seu sua não sim tudo todos agora novo nova guardar
        cancelar aceitar rejeitar seguinte anterior abrir fechar eliminar apagar editar ver ajuda iniciar sessão
        reiniciar atualizar atualização transferir baixar instalar pesquisar início ficheiro ficheiros arquivo
        arquivos partilhar compartilhar copiar colar enviar responder continuar concluído aplicar alterar
        alterações conta perfil senha bem-vindo mais mostrar ocultar detalhes opções privacidade termos tentar
        novamente sobre contacto contato mensagem hoje ontem criar adicionar selecionar definições configurações
        idioma notas versão imprimir permitir de""",
    "fr": """le la les de des du et ou en avec pour par un une votre vos tout tous maintenant nouveau nouvelle
        enregistrer annuler paramètres accepter refuser suivant précédent retour ouvrir fermer supprimer modifier
        voir aide connexion déconnexion connecter redémarrer mise jour télécharger installer rechercher accueil
        fichier fichiers partager copier coller envoyer répondre continuer ignorer terminé appliquer changer
        modifications compte profil mot passe bienvenue plus afficher masquer détails options confidentialité
        conditions démarrer arrêter réessayer propos contact message aujourd'hui hier créer ajouter sélectionner
        gérer oui non langue imprimer autoriser à""",
    "it": """il lo la gli le di del della e o in con per da un una tuo tua tutto tutti ora adesso nuovo nuova salva
        salvare annulla impostazioni accetta rifiuta avanti indietro apri chiudi elimina modifica visualizza aiuto
        accedi esci riavvia aggiorna aggiornamento scarica installa cerca condividi copia incolla invia rispondi
        continua salta fatto applica cambia modifiche profilo benvenuto altro mostra nascondi dettagli opzioni
        termini avvia riprova più tardi informazioni contatto messaggio oggi ieri crea aggiungi seleziona gestisci
        sì no lingua stampa note consenti""",
    "nl": """de het een en of van in aan met voor op naar uw je jouw alle alles nu nieuw nieuwe opslaan annuleren
        instellingen accepteren weigeren afwijzen volgende vorige terug openen sluiten verwijderen bewerken bekijken
        inloggen aanmelden afmelden uitloggen opnieuw starten bijwerken downloaden installeren zoeken bestand
        bestanden delen kopiëren plakken verzenden versturen antwoorden doorgaan overslaan klaar toepassen wijzigen
        wijzigingen profiel wachtwoord welkom meer tonen weergeven verbergen opties voorwaarden stoppen probeer
        bericht vandaag gisteren uploaden maken toevoegen selecteren beheren ja nee taal afdrukken niet toestaan""",
    "pl": """i w z na do dla od po nie tak wszystko wszystkie teraz nowy nowa nowe zapisz anuluj ustawienia
        zaakceptuj akceptuj odrzuć dalej wstecz poprzedni otwórz zamknij usuń edytuj wyświetl pomoc zaloguj wyloguj
        się uruchom ponownie aktualizuj aktualizacja pobierz zainstaluj szukaj wyszukaj plik pliki udostępnij kopiuj
        wklej wyślij odpowiedz kontynuuj pomiń gotowe zastosuj zmień zmiany konto profil hasło witaj więcej pokaż
        ukryj szczegóły opcje prywatność warunki rozpocznij zatrzymaj spróbuj później wiadomość dzisiaj wczoraj
        prześlij utwórz dodaj wybierz zarządzaj język drukuj twój twoje zezwól""",
}

LEXICON: dict[str, frozenset[str]] = {lang: frozenset(words.split()) for lang, words in _WORDS.items()}

# Labels up to this many words are judged by their own words.
SHORT_WORDS = 4

_WORD = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def is_short(text: str) -> bool:
    return 0 < len(words(text)) <= SHORT_WORDS


def languages_of(text: str) -> set[str]:
    """Languages whose lexicon covers the label clearly (all its words, or all but one of four).
    Empty when the label is long, has no known words, or is only partly known (a name, a
    truncated text): then the statistical detector decides."""
    ws = words(text)
    if not ws or len(ws) > SHORT_WORDS:
        return set()
    need = len(ws) if len(ws) < 4 else 3
    counts = {lang: sum(w in lex for w in ws) for lang, lex in LEXICON.items()}
    best = max(counts.values())
    if best < need:
        return set()
    return {lang for lang, c in counts.items() if c == best}


def foreign_leftovers(source: str, translation: str, target: str) -> list[str]:
    """Words copied unchanged from a short source into its translation that belong to another
    language and not to the target, as in "Publicación notes": the translation mixes languages.

    Only lowercase source words count (capitalised ones are usually names, as in "Google
    Play"), and only short texts, where a leftover word cannot be a normal loanword in a
    sentence."""
    if len(words(source)) > 2 * SHORT_WORDS:
        return []
    target_lex = LEXICON.get(target, frozenset())
    lowercase_src = {w for w in _WORD.findall(source) if w == w.lower()}
    leftovers = []
    for w in words(translation):
        if (w in lowercase_src and len(w) >= 3 and w not in target_lex
                and any(w in lex for lang, lex in LEXICON.items() if lang != target)):
            leftovers.append(w)
    return leftovers
