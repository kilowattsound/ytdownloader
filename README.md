# 📺 YouTube Downloader (Terminal Edition)
 
A high-performance, aesthetically pleasing terminal-based YouTube downloader built with **Pure Python**. It leverages `yt-dlp` for extracting media and `rich` for a beautiful, responsive user interface.

![Terminal Interface](https://img.shields.io/badge/UI-Terminal_Rich-blue?style=flat-square)
![Pure Python](https://img.shields.io/badge/Python-3.8+-yellow?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## ✨ Key Features

*   **⚡ Dynamic Quality selection**: Automatically fetches real available resolutions (4K, 2K, 1080p, etc.) with **actual bitrates** displayed in the menu.
*   **🌍 Multilingual Support**: Fully localized in **English** and **Russian**.
*   **📦 Pure Python & Self-Managed**: Automatically checks for and installs required libraries (`yt-dlp`, `rich`, `static-ffmpeg`).
*   **💻 System Integration**: One-click installation to your system path. Run `youtube` from any terminal window.
*   **🎧 Pro Audio Mode**: Extract audio in multiple formats (MP3, M4A, FLAC, WAV).
*   **📂 Playlist & Bulk Support**: Download entire playlists or batches of URLs from a `.txt` file.
*   **📜 History Tracking**: Keep track of your past downloads with a built-in history viewer.

---

## 🚀 Quick Start & Installation

### One-line Installation (Recommended)
Run this command in your terminal to automatically install the script to your system:
```bash
curl -sSL https://raw.githubusercontent.com/kilowattsound/ytdownloader/main/install.sh | bash
```

### Manual Installation (GitHub Clone)
To install the downloader onto your system globally, simply clone the repository and run the installer:

```bash
git clone https://github.com/kilowattsound/ytdownloader.git
cd ytdownloader
chmod +x install.sh
./install.sh
```

Once installed, you can launch the application from anywhere using:
```bash
youtube
```

---

## 🛠 Manual Installation

If you prefer to run it without installing globally:

1.  Clone the repository:
    ```bash
    git clone https://github.com/kilowattsound/ytdownloader.git
    cd ytdownloader
    ```
2.  Install dependencies:
    ```bash
    pip install yt-dlp rich static-ffmpeg
    ```
3.  Run the script:
    ```bash
    python3 ytdownloader.py
    ```

---

## ⚙️ Configuration & Paths

-   **Downloads**: Saved to `~/Movies/YouTube` by default (customizable in Settings).
-   **Config/History**: Stored in `~/.ytdl/` for persistence across sessions.

---

## 🙌 Credits

This project wouldn't be possible without these amazing open-source libraries:
-   [yt-dlp](https://github.com/yt-dlp/yt-dlp) - The powerful video extraction engine.
-   [rich](https://github.com/Textualize/rich) - Professional terminal formatting and UI components.
-   [static-ffmpeg](https://github.com/zackees/static-ffmpeg) - Self-contained media processing.

---

*Enjoying the tool? Feel free to star the repo! ⭐*
-   [rich](https://github.com/Textualize/rich) - Professional terminal formatting and UI components.
-   [static-ffmpeg](https://github.com/zackees/static-ffmpeg) - Self-contained media processing.

---

*Enjoying the tool? Feel free to star the repo! ⭐*
