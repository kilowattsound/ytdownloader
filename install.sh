#!/bin/bash

# YouTube Downloader - System Installer
# Created for Terminal Edition

# Colors for pretty output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m' 
NC='\033[0m'

echo -e "${BLUE}${BOLD}--- YouTube Downloader Installer ---${NC}"
echo -e "${BLUE}Terminal Edition v2.2${NC}\n"

# 1. Check for Python 3
if ! command -v python3 &> /dev/null
then
    echo -e "${RED}[✖] Python 3 was not found. Please install Python 3 first.${NC}"
    exit 1
fi
echo -e "${GREEN}[✔] Python 3 detected${NC}"

# 2. Identify script location
SCRIPT_NAME="ytdownloader.py"
INSTALL_DIR="$HOME/.ytdl/bin"
REPO_URL="https://raw.githubusercontent.com/kilowattsound/ytdownloader/main"

# Check for curl (needed for standalone mode)
if ! command -v curl &> /dev/null
then
    echo -e "${YELLOW}[!] Note: 'curl' is not installed. Standalone installation may fail.${NC}"
fi

# Check if running from a local clone or standalone
if [ -f "./$SCRIPT_NAME" ]; then
    # Local installation from current directory
    SCRIPT_PATH="$(pwd)/$SCRIPT_NAME"
    echo -e "${GREEN}[✔] Local source script found: $SCRIPT_NAME${NC}"
else
    # Remote/Standalone installation
    if ! command -v curl &> /dev/null; then
        echo -e "${RED}[✖] Error: 'curl' is required for standalone mode. Please install it first.${NC}"
        exit 1
    fi
    echo -e "${YELLOW}[!] Standalone mode: Downloading source files...${NC}"
    mkdir -p "$INSTALL_DIR"
    if curl -sSL "$REPO_URL/$SCRIPT_NAME" -o "$INSTALL_DIR/$SCRIPT_NAME"; then
        SCRIPT_PATH="$INSTALL_DIR/$SCRIPT_NAME"
        echo -e "${GREEN}[✔] Successfully downloaded $SCRIPT_NAME${NC}"
    else
        echo -e "${RED}[✖] Error downloading $SCRIPT_NAME from GitHub.${NC}"
        echo -e "${YELLOW}[!] Please check your internet connection or the repository URL.${NC}"
        exit 1
    fi
fi

# 3. Make ytdl.py executable
echo -e "${YELLOW}[!] Setting executable permissions...${NC}"
chmod +x "$SCRIPT_PATH"

# 4. Create symlink in /usr/local/bin
DEST_PATH="/usr/local/bin/youtube"
echo -e "${YELLOW}[!] Creating global command: '$DEST_PATH'${NC}"

# Check if symlink already exists
if [ -L "$DEST_PATH" ] || [ -f "$DEST_PATH" ]; then
    echo -e "${YELLOW}[!] Note: $DEST_PATH already exists. Updating...${NC}"
    # Try to remove it first
    if [ "$EUID" -ne 0 ]; then
        if ! rm "$DEST_PATH" 2>/dev/null; then
            echo -e "${BLUE}[#] Requesting administrator permission to remove old link...${NC}"
            sudo rm "$DEST_PATH"
        fi
    else
        rm "$DEST_PATH"
    fi
fi

# Create symlink
if [ "$EUID" -ne 0 ]; then
    if ! ln -s "$SCRIPT_PATH" "$DEST_PATH" 2>/dev/null; then
        echo -e "${BLUE}[#] Requesting administrator permission to install to system...${NC}"
        if sudo ln -sf "$SCRIPT_PATH" "$DEST_PATH"; then
            echo -e "${GREEN}[✔] Successfully installed globally using sudo!${NC}"
        else
            echo -e "${RED}[✖] Error during installation. Please check permissions.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}[✔] Successfully installed globally!${NC}"
    fi
else
    ln -sf "$SCRIPT_PATH" "$DEST_PATH"
    echo -e "${GREEN}[✔] Successfully installed globally!${NC}"
fi

echo -e "\n${GREEN}${BOLD}Done!${NC}"
echo -e "You can now run the downloader from any terminal by typing: ${BOLD}youtube${NC}"

# 5. Check for stale binaries in other PATH locations
STALE_FOUND=false
for yt_path in $(which -a youtube 2>/dev/null); do
    if [ "$yt_path" != "$DEST_PATH" ]; then
        echo -e "${YELLOW}[!] Warning: Found a stale 'youtube' binary at: $yt_path${NC}"
        echo -e "${YELLOW}    This may override the new installation. Removing...${NC}"
        if rm "$yt_path" 2>/dev/null || sudo rm "$yt_path" 2>/dev/null; then
            echo -e "${GREEN}[✔] Removed stale binary: $yt_path${NC}"
        else
            echo -e "${RED}[✖] Could not remove $yt_path. Please remove it manually.${NC}"
        fi
        STALE_FOUND=true
    fi
done

if [ "$STALE_FOUND" = true ]; then
    echo -e "${GREEN}[✔] Stale binaries cleaned up.${NC}"
fi

echo -e "\n${BLUE}Happy downloading!${NC}"
        rm "$DEST_PATH"
    fi
fi

# Create symlink
if [ "$EUID" -ne 0 ]; then
    if ! ln -s "$SCRIPT_PATH" "$DEST_PATH" 2>/dev/null; then
        echo -e "${BLUE}[#] Requesting administrator permission to install to system...${NC}"
        if sudo ln -sf "$SCRIPT_PATH" "$DEST_PATH"; then
            echo -e "${GREEN}[✔] Successfully installed globally using sudo!${NC}"
        else
            echo -e "${RED}[✖] Error during installation. Please check permissions.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}[✔] Successfully installed globally!${NC}"
    fi
else
    ln -sf "$SCRIPT_PATH" "$DEST_PATH"
    echo -e "${GREEN}[✔] Successfully installed globally!${NC}"
fi

echo -e "\n${GREEN}${BOLD}Done!${NC}"
echo -e "You can now run the downloader from any terminal by typing: ${BOLD}youtube${NC}"

# 5. Check for stale binaries in other PATH locations
STALE_FOUND=false
while IFS= read -r yt_path; do
    if [ "$yt_path" != "$DEST_PATH" ]; then
        echo -e "${YELLOW}[!] Warning: Found a stale 'youtube' binary at: $yt_path${NC}"
        echo -e "${YELLOW}    This may override the new installation. Removing...${NC}"
        if rm "$yt_path" 2>/dev/null || sudo rm "$yt_path" 2>/dev/null; then
            echo -e "${GREEN}[✔] Removed stale binary: $yt_path${NC}"
        else
            echo -e "${RED}[✖] Could not remove $yt_path. Please remove it manually.${NC}"
        fi
        STALE_FOUND=true
    fi
done < <(which -a youtube 2>/dev/null)

if [ "$STALE_FOUND" = true ]; then
    echo -e "${GREEN}[✔] Stale binaries cleaned up.${NC}"
fi

echo -e "\n${BLUE}Happy downloading!${NC}"
