#!/bin/bash

set -euo pipefail

# YouTube Downloader - System Installer
# Terminal Edition

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

TMP_FILE=""
cleanup() {
    if [ -n "$TMP_FILE" ] && [ -f "$TMP_FILE" ]; then
        rm -f "$TMP_FILE"
    fi
}
trap cleanup EXIT

echo -e "${BLUE}${BOLD}--- YouTube Downloader Installer ---${NC}"
echo -e "${BLUE}Terminal Edition v2.3.1${NC}\n"

# 1. Check for Python >= 3.9
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}[✖] Python 3 was not found. Please install Python 3.9+ first.${NC}"
    exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo -e "${RED}[✖] Python 3.9 or higher is required.${NC}"
    exit 1
fi
echo -e "${GREEN}[✔] Python 3.9+ detected${NC}"

# 2. Install script into ~/.ytdl/bin/ytdownloader.py
SCRIPT_NAME="ytdownloader.py"
INSTALL_DIR="$HOME/.ytdl/bin"
SCRIPT_PATH="$INSTALL_DIR/$SCRIPT_NAME"
REPO_URL="https://raw.githubusercontent.com/kilowattsound/ytdownloader/main"

mkdir -p "$INSTALL_DIR"

if [ -f "./$SCRIPT_NAME" ]; then
    cp "./$SCRIPT_NAME" "$SCRIPT_PATH"
    echo -e "${GREEN}[✔] Installed local $SCRIPT_NAME to $SCRIPT_PATH${NC}"
else
    if ! command -v curl >/dev/null 2>&1; then
        echo -e "${RED}[✖] Error: 'curl' is required for standalone installation.${NC}"
        exit 1
    fi
    echo -e "${YELLOW}[!] Standalone mode: Downloading $SCRIPT_NAME...${NC}"
    TMP_FILE="$(mktemp)"
    if ! curl -fsSL "$REPO_URL/$SCRIPT_NAME" -o "$TMP_FILE"; then
        echo -e "${RED}[✖] Error downloading $SCRIPT_NAME from GitHub.${NC}"
        exit 1
    fi

    FIRST_LINE="$(head -n 1 "$TMP_FILE" || true)"
    if [ "$FIRST_LINE" != "#!/usr/bin/env python3" ]; then
        echo -e "${RED}[✖] Downloaded file failed validation (unexpected header).${NC}"
        exit 1
    fi

    mv "$TMP_FILE" "$SCRIPT_PATH"
    TMP_FILE=""
    echo -e "${GREEN}[✔] Successfully downloaded and verified $SCRIPT_NAME${NC}"
fi

# 3. Make script executable
echo -e "${YELLOW}[!] Setting executable permissions...${NC}"
chmod +x "$SCRIPT_PATH"

# 4. Ensure /usr/local/bin exists and create symlink
DEST_DIR="/usr/local/bin"
DEST_PATH="$DEST_DIR/youtube"
echo -e "${YELLOW}[!] Creating global command: '$DEST_PATH'${NC}"

if [ ! -d "$DEST_DIR" ]; then
    if [ "${EUID:-$(id -u)}" -ne 0 ]; then
        mkdir -p "$DEST_DIR" 2>/dev/null || sudo mkdir -p "$DEST_DIR"
    else
        mkdir -p "$DEST_DIR"
    fi
fi

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    if ln -sf "$SCRIPT_PATH" "$DEST_PATH" 2>/dev/null; then
        echo -e "${GREEN}[✔] Successfully installed globally!${NC}"
    else
        echo -e "${BLUE}[#] Requesting administrator permission to install to $DEST_DIR...${NC}"
        if sudo ln -sf "$SCRIPT_PATH" "$DEST_PATH"; then
            echo -e "${GREEN}[✔] Successfully installed globally using sudo!${NC}"
        else
            echo -e "${RED}[✖] Error during installation. Please check permissions.${NC}"
            exit 1
        fi
    fi
else
    ln -sf "$SCRIPT_PATH" "$DEST_PATH"
    echo -e "${GREEN}[✔] Successfully installed globally!${NC}"
fi

# 5. Warn if another 'youtube' binary shadows /usr/local/bin/youtube in PATH
if command -v type >/dev/null 2>&1; then
    while IFS= read -r yt_path; do
        if [ -n "$yt_path" ] && [ "$yt_path" != "$DEST_PATH" ]; then
            echo -e "${YELLOW}[!] Warning: Another 'youtube' command exists in PATH at: $yt_path${NC}"
            echo -e "${YELLOW}    If it takes precedence, remove or rename it manually.${NC}"
        fi
    done < <(type -aP youtube 2>/dev/null || true)
fi

echo -e "\n${GREEN}${BOLD}Done!${NC}"
echo -e "You can now run the downloader from any terminal by typing: ${BOLD}youtube${NC}"
echo -e "\n${BLUE}Happy downloading!${NC}"
