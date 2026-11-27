# How KeepT works

[Back to the README](../README.md)

You press F1, you click, the translation appears. Here's what happens in between, for the curious.

## 1. Freeze

KeepT takes a picture of the monitor under your mouse and shows it full screen, frozen, with a glowing border. That's the overlay. From now on, everything happens on that picture, so the text can't scroll away while you aim.

The overlay is kept out of screen captures only while it's closed. That way KeepT never reads (and translates again) its own translation when you press F1 twice, while your own screenshots of an open overlay (Win+Shift+S) do show the translation.

## 2. Read

Text recognition works in two steps:

1. **Windows finds the text.** The OCR built into Windows finds the lines and blocks of text in a fraction of a second. KeepT groups the lines into blocks (paragraphs, buttons, labels) by how close and how aligned they are.
2. **A second pair of eyes reads it.** Windows is quick, but in small or grey text it tends to turn periods into "_", lose umlauts and read "1°" as "10". So a small open recognizer (PP-OCRv5 latin from PaddleOCR, 7.9 MB, runs on your CPU) reads every line again. On our test set of 28 real screens, it took exact words from 96.8 to 99.1 %, and umlauts and accents from 82 to 99 %.

The blocks you point at or select are read first; the rest of the screen follows in the background, and waits politely while a translation is running. If KeepT isn't sure what a block says (an icon, a decorative font), it leaves it alone rather than paint a wrong translation over it.

Windows needs its OCR pack for a language. If one is missing, KeepT tells you how to add it (Settings > Time & language > Language).

## 3. Work out the language

Every block gets its own language, so a letter in German, French and Italian is translated paragraph by paragraph from the right language. Short labels follow the language of the screen unless the words clearly say otherwise. A label that is just a language name ("DEUTSCH", "FRANÇAIS") gets translated from a table, because translation models love to turn "DEUTSCH" into "SPANISH".

## 4. Translate

KeepT translates between German, English, Spanish, French, Italian, Portuguese, Dutch and Polish, in any direction. It uses OPUS-MT models from the University of Helsinki, running locally with CTranslate2. There's a direct model for most pairs; the rest go through English (German to Polish becomes German to English to Polish, without you noticing).

Some things must come out exactly as they went in:

- **E-mail addresses and links** are never translated.
- **Numbers, dates, times and amounts** are checked after translating. If one changed, the sentence is translated again with the numbers protected. If it still goes wrong, that sentence stays in the original language. A wrong date or amount is worse than no translation.
- **Place names**: Swiss municipalities (from the official list) and the word after a postal code, like "3999 Musterwil", stay as they are everywhere on the screen, even in blocks translated before KeepT got to read the address.

## 5. Paint

Each translation goes on top of its original block, on a background sampled from the screen around it, in a light or dark colour that matches, starting at the original size and shrinking a little if it has to. A translation never spreads over another block of text, and items on one line ("Grüsse · salutations · saluti") are laid out together, at one size, with their separators.

## Models

No translation model ships inside the installer. Each one (about 80 to 250 MB) is downloaded once: during installation for the languages you choose, from the tray "Languages" window, or the first time you translate text in another language, with the progress shown in the pill. Models live in `%LOCALAPPDATA%\KeepT\models` and you can delete them from the tray.

After 10 minutes without use, KeepT frees them from memory and goes back to being a quiet tray icon. As soon as you press the shortcut, it reloads them in the background.

## The tray menu

Right-click the tray icon for the target language, "Languages" (add or remove languages, with their download size), the shortcut, start with Windows, the update check, the downloaded models and the credits.
