# Privacy

[Back to the README](../README.md)

Short version: what's on your screen stays on your PC.

Screenshots, recognized text and translations are processed on your computer and never sent anywhere. There are no accounts and no telemetry. KeepT doesn't know (and doesn't want to know) what you're reading.

## What KeepT sends over the network

Only two things, and neither one carries anything about you or your screen:

1. **Downloading translation models.** During installation for the languages you choose, and later the first time another language pair is needed. They come from the [models-v1 release](https://github.com/carranza-javier/KeepT/releases/tag/models-v1) of this repository. Each file is checked against the SHA-256 pinned in the app and thrown away if it doesn't match. Only if GitHub can't be reached does KeepT download the original model from the official OPUS-MT servers of the University of Helsinki and convert it on your PC.
2. **Checking for a new version**, at most once a day, by reading the list of releases from the public GitHub API. KeepT only shows a notice with a link and never installs anything by itself. You can switch this off in the installer or in the tray menu.

GitHub and the University of Helsinki may log these requests (for example your IP address) according to their own privacy policies.

## What stays on your PC

- Translation models, in `%LOCALAPPDATA%\KeepT\models`.
- Settings, in `%APPDATA%\KeepT\config.json`.
- A log file with timings and errors, in `%LOCALAPPDATA%\KeepT\keept.log`. It contains no screenshots and no text from your screen.

Uninstalling KeepT (Settings > Apps) removes the models and settings too.
