# 📺 YouTube Downloader (Terminal Edition)

A terminal-based YouTube downloader built with **Pure Python**. It leverages `yt-dlp` for extracting media and `rich` for a clean, responsive terminal interface.

![Terminal Interface](https://img.shields.io/badge/UI-Terminal_Rich-blue?style=flat-square)
![Pure Python](https://img.shields.io/badge/Python-3.9+-yellow?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## ✨ Key Features

*   **⚡ Dynamic Quality Selection**: Fetches available resolutions (4K, 2K, 1080p, etc.) with **actual bitrates** displayed in the menu.
*   **🌍 Multilingual Support**: Localized in **English** and **Russian**.
*   **📦 Self-Managed or Pip-Installable**: Automatically checks for required libraries (`yt-dlp`, `rich`, `static-ffmpeg`, `mutagen`) or installs cleanly via `pip` / `pipx`.
*   **🔄 Automatic Startup Updates**: Checks both the app (GitHub) and Python modules (PyPI) at startup (can be toggled in Settings or skipped with `--no-update-check`).
*   **💻 System Integration**: Install globally as the `youtube` command from any terminal window.
*   **🎧 Pro Audio Mode**: Extract audio in **MP3, M4A, FLAC, or WAV** with automatic metadata and thumbnail tagging.
*   **📂 Playlist & Bulk Support**: Download entire playlists or batches of URLs from a `.txt` file.
*   **📜 History Tracking**: View and manage your recent downloads.

---

## 🚀 Quick Start & Installation

### Option 1: Package Install (`pip` / `pipx` — Recommended)

```bash
git clone https://github.com/kilowattsound/ytdownloader.git
cd ytdownloader
pip install .
# Or isolated with pipx:
pipx install .
```

### Option 2: Installer Script (macOS / Linux)

> **Security Tip:** Inspect `install.sh` before piping it directly to `bash`.

```bash
curl -fsSL https://raw.githubusercontent.com/kilowattsound/ytdownloader/main/install.sh -o install.sh
less install.sh
bash install.sh
```

Or run from a local clone:

```bash
git clone https://github.com/kilowattsound/ytdownloader.git
cd ytdownloader
chmod +x install.sh
./install.sh
```

Once installed, launch from anywhere:

```bash
youtube
youtube --version
youtube --no-update-check
```

### Option 3: Run Directly Without Global Install

```bash
git clone https://github.com/kilowattsound/ytdownloader.git
cd ytdownloader
pip install yt-dlp rich static-ffmpeg mutagen
python3 ytdownloader.py
```

---

## ⚙️ Configuration & Paths

-   **Downloads**: Saved to `~/Movies/YouTube` on macOS or `~/Videos/YouTube` on Linux/Windows by default (customizable in Settings).
-   **Config/History**: Stored in `~/.ytdl/` for persistence across sessions.
-   **Auto-Update Check**: Enabled by default on startup; toggle under **Settings → Auto-Check Updates on Startup** or bypass once with `--no-update-check`.
-   **YouTube Sign-In Cookies**: If YouTube asks to sign in (`"Sign in to confirm you're not a bot"`), configure cookies under **Settings → YouTube Cookies (Auth)** (using your signed-in browser or a `cookies.txt` file), or pass `--cookies-from-browser chrome` / `--cookies /path/to/cookies.txt`.

---

## 🙌 Credits

This project builds on these open-source libraries:
-   [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Media extraction engine.
-   [rich](https://github.com/Textualize/rich) - Terminal formatting and UI components.
-   [static-ffmpeg](https://github.com/zackees/static-ffmpeg) - Self-contained `ffmpeg` fallback.
-   [mutagen](https://github.com/quodlibet/mutagen) - Audio metadata and thumbnail embedding.
