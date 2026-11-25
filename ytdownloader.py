#!/usr/bin/env python3
"""
YouTube Downloader - Terminal Edition
A command-line YouTube downloader with rich formatting (Pure Python).
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "2.3.0"
REPO_URL = "kilowattsound/ytdownloader"
STARTUP_UPDATE_TIMEOUT = 4

ALLOWED_YOUTUBE_HOSTS = frozenset({
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
})
EMBED_THUMBNAIL_FORMATS = frozenset({"mp3", "m4a", "flac"})
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
MANAGED_PACKAGES = ("yt-dlp", "rich", "static-ffmpeg", "mutagen")

# Lazy-loaded third-party references (populated in _load_third_party_modules)
Console = None
Progress = None
TextColumn = None
SpinnerColumn = None
Panel = None
Prompt = None
Confirm = None
IntPrompt = None
Table = None
box = None
Text = None
Align = None
escape = None
yt_dlp = None
static_ffmpeg = None
MUTAGEN_AVAILABLE = False


def _load_third_party_modules():
    """Import third-party libraries after dependency verification."""
    global Console, Progress, TextColumn, SpinnerColumn, Panel
    global Prompt, Confirm, IntPrompt, Table, box, Text, Align, escape
    global yt_dlp, static_ffmpeg, MUTAGEN_AVAILABLE

    from rich.console import Console as _Console
    from rich.progress import (
        Progress as _Progress,
        TextColumn as _TextColumn,
        SpinnerColumn as _SpinnerColumn,
    )
    from rich.panel import Panel as _Panel
    from rich.prompt import Prompt as _Prompt, Confirm as _Confirm, IntPrompt as _IntPrompt
    from rich.table import Table as _Table
    from rich import box as _box
    from rich.text import Text as _Text
    from rich.align import Align as _Align
    from rich.markup import escape as _escape
    import yt_dlp as _yt_dlp

    Console = _Console
    Progress = _Progress
    TextColumn = _TextColumn
    SpinnerColumn = _SpinnerColumn
    Panel = _Panel
    Prompt = _Prompt
    Confirm = _Confirm
    IntPrompt = _IntPrompt
    Table = _Table
    box = _box
    Text = _Text
    Align = _Align
    escape = _escape
    yt_dlp = _yt_dlp

    try:
        import static_ffmpeg as _static_ffmpeg
        static_ffmpeg = _static_ffmpeg
    except ImportError:
        static_ffmpeg = None

    MUTAGEN_AVAILABLE = importlib.util.find_spec("mutagen") is not None


def _safe_escape(value):
    """Escape text for Rich markup when Rich is loaded."""
    text = str(value)
    if escape is not None:
        return escape(text)
    return text


def ensure_dependencies():
    """Ensure required Python modules are installed."""
    required = [
        ("rich", "rich"),
        ("yt_dlp", "yt-dlp"),
        ("static_ffmpeg", "static-ffmpeg"),
        ("mutagen", "mutagen"),
    ]
    missing = [pkg for mod, pkg in required if importlib.util.find_spec(mod) is None]

    if not missing:
        return

    print("\n" + "=" * 50)
    print("Dependency Check")
    print("=" * 50)
    print(f"Missing modules: {', '.join(missing)}")
    try:
        choice = (input("\nWould you like to install the missing modules? [y/n] (y): ").strip().lower() or "y")
    except (EOFError, KeyboardInterrupt):
        choice = "n"

    if choice == "y":
        print("\nInstalling modules... this may take a moment.")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            print("\n✔ Modules installed successfully!")
            print("Restarting script...\n")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as exc:
            print(f"\n✖ Error installing modules: {exc}")
            print("If your Python environment is externally managed (PEP 668),")
            print("create a virtual environment or use pipx:")
            print(f"  python3 -m venv ~/.ytdl/venv && ~/.ytdl/venv/bin/pip install {' '.join(missing)}")
            sys.exit(1)
    else:
        print(f"\n✖ This script requires {', '.join(missing)} to run.")
        sys.exit(1)


def parse_version(version_str):
    """Parse a version string like 'v2.3.0' into a comparable tuple of ints."""
    if not version_str:
        return (0,)
    cleaned = str(version_str).strip().lstrip("vV")
    parts = []
    for segment in cleaned.split("."):
        match = re.match(r"^(\d+)", segment)
        if match:
            parts.append(int(match.group(1)))
    return tuple(parts) if parts else (0,)


def is_valid_youtube_url(url):
    """Validate that a URL uses http(s) and points to an allowed YouTube host."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url.strip())
    except ValueError:
        return False

    if parsed.scheme.lower() not in ("http", "https"):
        return False

    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_YOUTUBE_HOSTS:
        return False

    return bool(parsed.path.strip("/")) or bool(parsed.query)


def clean_url(url, preserve_playlist=False):
    """Normalize a YouTube URL while cleanly stripping tracking/timestamp params."""
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return url

    host = (parsed.hostname or "").lower()
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)

    if host in ("youtu.be", "www.youtu.be"):
        segments = [seg for seg in parsed.path.split("/") if seg]
        if not segments:
            return url
        video_id = segments[0]
        new_params = [("v", video_id)]
        if preserve_playlist:
            for key, val in query_pairs:
                if key == "list" and val:
                    new_params.append(("list", val))
                    break
        return urllib.parse.urlunparse((
            "https",
            "www.youtube.com",
            "/watch",
            "",
            urllib.parse.urlencode(new_params),
            "",
        ))

    drop_keys = {"t"} if preserve_playlist else {"t", "list", "index"}
    filtered = [(k, v) for k, v in query_pairs if k not in drop_keys]
    return urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        urllib.parse.urlencode(filtered),
        "",
    ))


def format_duration(seconds):
    """Format duration in seconds into a human-readable string."""
    if seconds is None:
        return "Unknown"
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "Unknown"
    if total <= 0:
        return "Unknown"

    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def format_speed(speed_bytes):
    """Format numeric download speed in bytes/sec."""
    if speed_bytes is None:
        return "N/A"
    try:
        val = float(speed_bytes)
    except (TypeError, ValueError):
        return "N/A"
    if val <= 0:
        return "N/A"

    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if val < 1024.0 or unit == "GB/s":
            if unit == "B/s":
                return f"{int(val)} {unit}"
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return "N/A"


def format_eta(eta_seconds):
    """Format numeric ETA in seconds as MM:SS or H:MM:SS."""
    if eta_seconds is None:
        return "N/A"
    try:
        total = int(eta_seconds)
    except (TypeError, ValueError):
        return "N/A"
    if total < 0:
        return "N/A"

    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def compute_progress_percent(progress_dict):
    """Compute bounded [0.0, 100.0] download progress from yt-dlp hook dict."""
    if not isinstance(progress_dict, dict):
        return None

    downloaded = progress_dict.get("downloaded_bytes")
    total = progress_dict.get("total_bytes") or progress_dict.get("total_bytes_estimate")
    if downloaded is not None and total:
        try:
            total_f = float(total)
            if total_f > 0:
                pct = (float(downloaded) / total_f) * 100.0
                return max(0.0, min(100.0, pct))
        except (TypeError, ValueError):
            pass

    raw_pct = progress_dict.get("_percent_str")
    if isinstance(raw_pct, str):
        cleaned = ANSI_ESCAPE_RE.sub("", raw_pct).replace("%", "").strip()
        try:
            pct = float(cleaned)
            return max(0.0, min(100.0, pct))
        except ValueError:
            return None
    return None


def extract_available_qualities(formats):
    """Extract highest-bitrate video formats per resolution height, sorted descending."""
    available = {}
    for fmt in formats or []:
        if not isinstance(fmt, dict):
            continue
        height = fmt.get("height")
        if not isinstance(height, (int, float)) or height <= 0:
            continue
        if fmt.get("vcodec") == "none":
            continue

        height_int = int(height)
        tbr = fmt.get("tbr") or 0
        if height_int not in available or tbr > available[height_int]["tbr"]:
            available[height_int] = {
                "height": height_int,
                "tbr": tbr,
                "ext": fmt.get("ext") or "unknown",
                "vcodec": fmt.get("vcodec") or "unknown",
            }
    return sorted(available.values(), key=lambda x: x["height"], reverse=True)


def get_default_download_path():
    """Return platform-appropriate default download folder."""
    if sys.platform == "darwin":
        return str(Path.home() / "Movies" / "YouTube")
    return str(Path.home() / "Videos" / "YouTube")


def build_ssl_context():
    """Build a verified TLS SSLContext (using certifi if available)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_module_updates(timeout=10, ignore_errors=False):
    """Query PyPI concurrently for newer versions of managed packages."""
    ssl_ctx = build_ssl_context()

    def _check_pkg(pkg):
        try:
            installed_ver = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            return None

        req = urllib.request.Request(
            f"https://pypi.org/pypi/{pkg}/json",
            headers={"User-Agent": f"ytdownloader/{VERSION}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            if ignore_errors:
                return None
            raise

        latest_ver = payload.get("info", {}).get("version")
        if latest_ver and parse_version(latest_ver) > parse_version(installed_ver):
            return (pkg, installed_ver, latest_ver)
        return None

    updates = {}
    with ThreadPoolExecutor(max_workers=len(MANAGED_PACKAGES)) as pool:
        for result in pool.map(_check_pkg, MANAGED_PACKAGES):
            if result is not None:
                pkg, installed_ver, latest_ver = result
                updates[pkg] = (installed_ver, latest_ver)
    return updates


def fetch_app_update(timeout=10):
    """Fetch remote script version and source from GitHub using verified TLS."""
    ssl_ctx = build_ssl_context()
    ref = "main"
    try:
        api_req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO_URL}/releases/latest",
            headers={"User-Agent": f"ytdownloader/{VERSION}", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(api_req, timeout=timeout, context=ssl_ctx) as api_resp:
            release_data = json.loads(api_resp.read().decode("utf-8"))
        tag = release_data.get("tag_name")
        if tag:
            ref = tag
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise

    raw_url = f"https://raw.githubusercontent.com/{REPO_URL}/{ref}/ytdownloader.py"
    raw_req = urllib.request.Request(raw_url, headers={"User-Agent": f"ytdownloader/{VERSION}"})
    with urllib.request.urlopen(raw_req, timeout=timeout, context=ssl_ctx) as response:
        content = response.read().decode("utf-8")

    version_match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not version_match:
        return None, None
    return version_match.group(1), content


def atomic_write_text(path, content, encoding="utf-8", preserve_mode=False):
    """Atomically write text to a file via a same-directory temp file and os.replace."""
    target = os.path.abspath(path)
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".tmp", dir=parent or ".")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if preserve_mode and os.path.exists(target):
            shutil.copymode(target, tmp_path)
        os.replace(tmp_path, target)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def normalize_user_path(raw):
    """Strip surrounding quotes, unescape spaces if unquoted, and expand ~."""
    text = (raw or "").strip()
    if len(text) >= 2 and ((text[0] == '"' and text[-1] == '"') or (text[0] == "'" and text[-1] == "'")):
        text = text[1:-1]
    else:
        text = text.replace("\\ ", " ")
    return os.path.expanduser(text)


def build_ydl_opts(
    download_path,
    format_type,
    quality="best",
    audio_format="mp3",
    embed_metadata=True,
    ffmpeg_available=True,
    mutagen_available=True,
    is_playlist=False,
):
    """Build yt-dlp options dictionary cleanly without insecure TLS flags."""
    if is_playlist:
        outtmpl = os.path.join(download_path, "%(playlist)s/%(playlist_index)s - %(title)s [%(id)s].%(ext)s")
    else:
        outtmpl = os.path.join(download_path, "%(title)s [%(id)s].%(ext)s")

    opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "color": {"stdout": "never", "stderr": "never"},
    }

    if is_playlist:
        opts["noplaylist"] = False
        opts["ignoreerrors"] = True

    if format_type == "audio":
        opts["format"] = "bestaudio/best"
        preferred_quality = "0" if audio_format in ("flac", "wav") else "192"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
            "preferredquality": preferred_quality,
        }]
        if embed_metadata:
            postprocessors.append({"key": "FFmpegMetadata"})
            if audio_format in EMBED_THUMBNAIL_FORMATS and mutagen_available:
                postprocessors.append({"key": "EmbedThumbnail"})
                opts["writethumbnail"] = True
        opts["postprocessors"] = postprocessors
    else:
        if ffmpeg_available:
            opts["format"] = (
                "bestvideo+bestaudio/best"
                if quality == "best"
                else f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"
            )
            opts["merge_output_format"] = "mp4"
        else:
            opts["format"] = "best" if quality == "best" else f"best[height<={quality}]/best"

    return opts


TRANSLATIONS = {
    "en": {
        "title": "YouTube Downloader",
        "subtitle": f"Terminal Edition v{VERSION}",
        "main_menu": "Main Menu",
        "download_video": "Download Video",
        "download_audio": "Download Audio Only",
        "download_playlist": "Download Playlist",
        "view_history": "View Download History",
        "settings": "Settings",
        "about": "About",
        "bulk_download": "Bulk Download",
        "exit": "Exit",
        "select_option": "Select an option",
        "enter_url": "Enter YouTube URL",
        "fetching_info": "Fetching video information...",
        "video_info": "Video Information",
        "property": "Property",
        "value": "Value",
        "option": "Option",
        "description": "Description",
        "col_title": "Title",
        "col_channel": "Channel",
        "col_duration": "Duration",
        "col_upload_date": "Upload Date",
        "col_views": "Views",
        "col_likes": "Likes",
        "col_format": "Format",
        "col_quality": "Quality",
        "col_date": "Date",
        "col_package": "Package",
        "col_current": "Current",
        "col_latest": "Latest",
        "select_quality": "Select Quality",
        "best_quality": "Best Quality",
        "your_choice": "Your choice",
        "start_download": "Start download?",
        "saving_to": "Saving to",
        "download_complete": "Download completed successfully!",
        "download_failed": "Download failed!",
        "download_interrupted": "Download cancelled by user.",
        "press_enter": "Press Enter to continue...",
        "no_url": "No URL provided!",
        "invalid_url": "Invalid YouTube URL!",
        "download_path": "Download Path",
        "change_path": "Change download location",
        "current_path": "Current path",
        "enter_new_path": "Enter new download path",
        "settings_saved": "Settings saved!",
        "error_creating_dir": "Error creating directory",
        "check_updates": "Check for library updates",
        "check_github": "Check for app updates (GitHub)",
        "auto_check_updates": "Auto-Check Updates on Startup",
        "auto_check_updates_toggled": "Startup Update Check: {}",
        "checking_startup_updates": "Checking for app & library updates...",
        "change_lang": "Change Language",
        "embed_metadata": "Audio Auto-Tagging",
        "embed_metadata_desc": "Embed title, artist & thumbnail in supported audio files",
        "embed_metadata_toggled": "Audio Auto-Tagging {}",
        "enabled": "Enabled",
        "disabled": "Disabled",
        "connected": "Connected",
        "missing": "Missing",
        "install_system": "Install to System (Global Alias)",
        "install_success": 'Successfully installed! You can now run "youtube" from any terminal.',
        "install_fail": "Installation failed. You might need sudo permissions.",
        "already_installed": 'The "youtube" command is already installed!',
        "windows_install_unsupported": "Global /usr/local/bin symlink install is for macOS/Linux. On Windows, install with: pip install .",
        "back_to_menu": "Back to main menu",
        "lang_name": "English",
        "history_title": "Download History",
        "history_showing": "Showing {} of {} saved entries.",
        "no_history": "No download history yet.",
        "clear_history_prompt": "Clear download history?",
        "history_cleared": "Download history cleared.",
        "video_label": "Video",
        "audio_label": "Audio",
        "bulk_file_prompt": "Enter the path to your .txt file containing YouTube URLs (one per line).",
        "file_path": "File Path",
        "file_not_found": "File not found!",
        "bulk_no_urls": "No URLs found in the file.",
        "bulk_found_urls": "Found {} URLs. Initiating bulk download...",
        "bulk_select_format": "Download Format",
        "bulk_video_best": "Video (Best Quality)",
        "bulk_audio_mp3": "Audio Only (MP3)",
        "bulk_processing": "[{}/{}] Processing: {}",
        "bulk_summary": "Bulk download finished: {} succeeded, {} failed, {} skipped (invalid URL).",
        "bulk_read_error": "Error reading file",
        "confirm_exit": "Goodbye!",
        "downloading": "Downloading...",
        "status_postprocessing": "Finalizing...",
        "download_cancelled": "Download cancelled.",
        "checking_updates": "Checking for updates...",
        "up_to_date": "All libraries are up to date!",
        "updates_available": "Updates Available",
        "install_updates_prompt": "Install updates now?",
        "updating_libs": "Updating libraries...",
        "updates_installed": "Libraries updated successfully!",
        "updating_libs_check_error": "Error checking for updates",
        "pep668_hint": "Your Python environment is externally managed (PEP 668). Upgrade inside your virtualenv or via pipx.",
        "restarting": "Restarting application...",
        "select_language": "Select Language",
        "settings_options": "Options",
        "invalid_choice": "Invalid choice.",
        "uninstall_system": "Uninstall from System",
        "uninstall_confirm": "Are you sure you want to uninstall YouTube Downloader?",
        "uninstall_success": "YouTube Downloader has been uninstalled from your system.",
        "uninstall_data_prompt": "Also delete configuration and download history?",
        "uninstall_not_installed": "YouTube Downloader is not installed on this system.",
        "removed_item": "Removed {}",
        "remove_failed": "Could not remove {}: {}",
        "app_up_to_date": "YouTube Downloader is up to date!",
        "app_update_available": "New version available: v{}",
        "update_app_prompt": "Would you like to update the application now?",
        "updating_app": "Updating script... please wait.",
        "app_updated": "Application updated successfully!",
        "parse_version_error": "Could not parse remote version information.",
        "update_validation_error": "Downloaded update failed integrity/syntax verification.",
        "github_error": "Error checking GitHub",
        "ssl_cert_hint": "TLS certificate verification failed. Ensure your system CA certificates or 'certifi' are up to date.",
        "select_audio_format": "Select Audio Format",
        "fetch_fallback_warn": "Could not fetch video details; attempting download with selected fallback...",
        "wav_thumbnail_note": "Note: WAV containers do not support embedded thumbnails; skipping thumbnail embed.",
        "mutagen_missing_note": "Note: 'mutagen' is not installed; skipping thumbnail embed.",
        "ffmpeg_missing_warn": "Warning: ffmpeg is unavailable. Falling back to single-stream download (audio extraction may fail).",
        "playlist_count": "Playlist contains {} videos",
        "playlist_empty": "Playlist is empty or unavailable.",
        "playlist_confirm": "Download entire playlist ({} videos)?",
        "playlist_fetch_error": "Could not fetch playlist details!",
        "playlist_downloading": "Downloading playlist...",
        "playlist_downloading_item": "Downloading: {}/{}",
        "playlist_complete": "Playlist download complete",
        "about_text": f"""
Version: {VERSION} (Pure Python Edition)
Author: Terminal Edition
Powered by: yt-dlp, rich, static-ffmpeg, and mutagen

* Features:
  • Download videos in multiple qualities (4K, 1080p, 720p, etc.)
  • Extract audio as MP3, M4A, FLAC, or WAV with auto-tagging
  • Download entire playlists and bulk URL lists
  • Download history tracking
  • Animated progress bars
  • Self-managing dependencies

📦 Dependencies:
  • yt-dlp (Video extraction engine)
  • rich (Terminal UI)
  • static-ffmpeg (Bundled ffmpeg fallback)
  • mutagen (Audio thumbnail & metadata tagging)

[⚙] Installation:
  Install globally from Settings -> Install to System
  or install as a package via: pip install .
  After installation, simply run: youtube (check version: youtube --version)

💡 Support:
  https://github.com/yt-dlp/yt-dlp

🎉 Enjoy downloading!
""",
    },
    "ru": {
        "title": "YouTube Загрузчик",
        "subtitle": f"Терминальная версия v{VERSION}",
        "main_menu": "Главное меню",
        "download_video": "Скачать видео",
        "download_audio": "Скачать только аудио",
        "download_playlist": "Скачать плейлист",
        "view_history": "История загрузок",
        "settings": "Настройки",
        "about": "О программе",
        "bulk_download": "Массовая загрузка",
        "exit": "Выход",
        "select_option": "Выберите опцию",
        "enter_url": "Введите URL YouTube",
        "fetching_info": "Получение информации о видео...",
        "video_info": "Информация о видео",
        "property": "Свойство",
        "value": "Значение",
        "option": "Опция",
        "description": "Описание",
        "col_title": "Название",
        "col_channel": "Канал",
        "col_duration": "Длительность",
        "col_upload_date": "Дата загрузки",
        "col_views": "Просмотры",
        "col_likes": "Лайки",
        "col_format": "Формат",
        "col_quality": "Качество",
        "col_date": "Дата",
        "col_package": "Пакет",
        "col_current": "Текущая",
        "col_latest": "Последняя",
        "select_quality": "Выберите качество",
        "best_quality": "Лучшее качество",
        "your_choice": "Ваш выбор",
        "start_download": "Начать загрузку?",
        "saving_to": "Сохранение в",
        "download_complete": "Загрузка успешно завершена!",
        "download_failed": "Ошибка загрузки!",
        "download_interrupted": "Загрузка отменена пользователем.",
        "press_enter": "Нажмите Enter, чтобы продолжить...",
        "no_url": "URL не указан!",
        "invalid_url": "Неверный URL YouTube!",
        "download_path": "Путь загрузки",
        "change_path": "Изменить путь сохранения",
        "current_path": "Текущий путь",
        "enter_new_path": "Введите новый путь сохранения",
        "settings_saved": "Настройки сохранены!",
        "error_creating_dir": "Ошибка создания каталога",
        "check_updates": "Проверить обновления библиотек",
        "check_github": "Проверить обновления приложения (GitHub)",
        "auto_check_updates": "Автопроверка обновлений при запуске",
        "auto_check_updates_toggled": "Автопроверка обновлений при запуске: {}",
        "checking_startup_updates": "Проверка обновлений приложения и библиотек...",
        "change_lang": "Сменить язык",
        "embed_metadata": "Авто-теги аудио",
        "embed_metadata_desc": "Встраивать название, исполнителя и обложку в поддерживаемые аудиофайлы",
        "embed_metadata_toggled": "Авто-теги аудио: {}",
        "enabled": "Включено",
        "disabled": "Отключено",
        "connected": "Подключено",
        "missing": "Отсутствует",
        "install_system": "Установить в систему (Глобальная команда)",
        "install_success": 'Успешно установлено! Теперь вы можете запускать "youtube" из любого терминала.',
        "install_fail": "Ошибка установки. Возможно, потребуются права sudo.",
        "already_installed": 'Команда "youtube" уже установлена!',
        "windows_install_unsupported": "Глобальная символическая ссылка /usr/local/bin предназначена для macOS/Linux. В Windows установите через: pip install .",
        "back_to_menu": "Назад в главное меню",
        "lang_name": "Русский",
        "history_title": "История загрузок",
        "history_showing": "Показано {} из {} сохранённых записей.",
        "no_history": "История загрузок пуста.",
        "clear_history_prompt": "Очистить историю загрузок?",
        "history_cleared": "История загрузок очищена.",
        "video_label": "Видео",
        "audio_label": "Аудио",
        "bulk_file_prompt": "Введите путь к .txt файлу с URL YouTube (один на строку).",
        "file_path": "Путь к файлу",
        "file_not_found": "Файл не найден!",
        "bulk_no_urls": "В файле не найдено URL.",
        "bulk_found_urls": "Найдено URL: {}. Начинаем массовую загрузку...",
        "bulk_select_format": "Формат загрузки",
        "bulk_video_best": "Видео (Лучшее качество)",
        "bulk_audio_mp3": "Только аудио (MP3)",
        "bulk_processing": "[{}/{}] Обработка: {}",
        "bulk_summary": "Массовая загрузка завершена: успешно {}, ошибок {}, пропущено (неверный URL) {}.",
        "bulk_read_error": "Ошибка чтения файла",
        "confirm_exit": "До свидания!",
        "downloading": "Загрузка...",
        "status_postprocessing": "Завершение...",
        "download_cancelled": "Загрузка отменена.",
        "checking_updates": "Проверка обновлений...",
        "up_to_date": "Все библиотеки обновлены!",
        "updates_available": "Доступны обновления",
        "install_updates_prompt": "Установить обновления сейчас?",
        "updating_libs": "Обновление библиотек...",
        "updates_installed": "Библиотеки успешно обновлены!",
        "updating_libs_check_error": "Ошибка проверки обновлений",
        "pep668_hint": "Среда Python управляется извне (PEP 668). Обновляйте пакеты внутри виртуального окружения или через pipx.",
        "restarting": "Перезапуск приложения...",
        "select_language": "Выберите язык",
        "settings_options": "Опции",
        "invalid_choice": "Неверный выбор.",
        "uninstall_system": "Удалить из системы",
        "uninstall_confirm": "Вы уверены, что хотите удалить YouTube Downloader?",
        "uninstall_success": "YouTube Downloader удалён из вашей системы.",
        "uninstall_data_prompt": "Также удалить конфигурацию и историю загрузок?",
        "uninstall_not_installed": "YouTube Downloader не установлен в этой системе.",
        "removed_item": "Удалено: {}",
        "remove_failed": "Не удалось удалить {}: {}",
        "app_up_to_date": "YouTube Downloader обновлён!",
        "app_update_available": "Доступна новая версия: v{}",
        "update_app_prompt": "Хотите обновить приложение сейчас?",
        "updating_app": "Обновление скрипта... пожалуйста, подождите.",
        "app_updated": "Приложение успешно обновлено!",
        "parse_version_error": "Не удалось разобрать информацию о версии.",
        "update_validation_error": "Загруженное обновление не прошло проверку целостности/синтаксиса.",
        "github_error": "Ошибка проверки GitHub",
        "ssl_cert_hint": "Ошибка проверки TLS-сертификата. Убедитесь, что системные сертификаты или пакет 'certifi' актуальны.",
        "select_audio_format": "Выберите формат аудио",
        "fetch_fallback_warn": "Не удалось получить сведения о видео; выполняется загрузка с выбранным резервным качеством...",
        "wav_thumbnail_note": "Примечание: контейнеры WAV не поддерживают встраивание обложки; обложка будет пропущена.",
        "mutagen_missing_note": "Примечание: пакет 'mutagen' не установлен; встраивание обложки пропущено.",
        "ffmpeg_missing_warn": "Предупреждение: ffmpeg недоступен. Выполняется загрузка одним потоком (извлечение аудио может не сработать).",
        "playlist_count": "В плейлисте найдено видео: {}",
        "playlist_empty": "Плейлист пуст или недоступен.",
        "playlist_confirm": "Скачать весь плейлист ({} видео)?",
        "playlist_fetch_error": "Не удалось получить данные плейлиста!",
        "playlist_downloading": "Загрузка плейлиста...",
        "playlist_downloading_item": "Загрузка: {}/{}",
        "playlist_complete": "Загрузка плейлиста завершена",
        "about_text": f"""
Версия: {VERSION} (Pure Python Edition)
Автор: Terminal Edition
Работает на: yt-dlp, rich, static-ffmpeg и mutagen

* Возможности:
  • Скачивание видео в разных качествах (4K, 1080p, 720p и т.д.)
  • Извлечение аудио в MP3, M4A, FLAC и WAV с авто-тегами
  • Скачивание целых плейлистов и списков URL из файла
  • Отслеживание истории загрузок
  • Анимированные индикаторы выполнения
  • Самоуправляемые зависимости

📦 Зависимости:
  • yt-dlp (движок загрузки)
  • rich (терминальный интерфейс)
  • static-ffmpeg (встроенный резервный ffmpeg)
  • mutagen (теги и обложки для аудио)

[⚙] Установка:
  Установите глобально: Настройки -> Установить в систему
  или как пакет: pip install .
  После установки просто запустите: youtube (проверка версии: youtube --version)

💡 Поддержка:
  https://github.com/yt-dlp/yt-dlp

🎉 Приятного скачивания!
""",
    },
}


class TerminalYouTubeDownloader:
    """Interactive terminal YouTube downloader powered by yt-dlp and Rich."""

    def __init__(
        self,
        console=None,
        config_dir=None,
        download_path=None,
        check_deps=True,
        auto_check_updates=None,
    ):
        self.download_path = download_path or get_default_download_path()
        os.makedirs(self.download_path, exist_ok=True)

        self.config_dir = config_dir or os.path.join(os.path.expanduser("~"), ".ytdl")
        os.makedirs(self.config_dir, exist_ok=True)

        self.history_file = os.path.join(self.config_dir, "history.json")
        self.config_file = os.path.join(self.config_dir, "config.json")

        # Migration from legacy home-directory dotfiles
        old_history = os.path.join(os.path.expanduser("~"), ".yt_downloader_history.json")
        old_config = os.path.join(os.path.expanduser("~"), ".yt_downloader_config.json")
        if os.path.exists(old_history) and not os.path.exists(self.history_file):
            shutil.move(old_history, self.history_file)
        if os.path.exists(old_config) and not os.path.exists(self.config_file):
            shutil.move(old_config, self.config_file)

        self.ytdlp_available = False
        self.ytdlp_version = "Unknown"
        self.ffmpeg_available = False
        self.language = "en"
        self.embed_metadata = True
        self.auto_check_updates = True

        self.console = console if console is not None else Console()
        self.load_config()
        if auto_check_updates is not None:
            self.auto_check_updates = bool(auto_check_updates)
        if check_deps:
            self.check_dependencies()

    def _t(self, key):
        """Translate a key to the active language."""
        return TRANSLATIONS.get(self.language, TRANSLATIONS["en"]).get(key, key)

    def print_color(self, text, color="white", bold=False):
        """Print styled text safely without interpreting Rich markup tags."""
        style = f"bold {color}" if bold else color
        self.console.print(str(text), style=style, markup=False)

    def clear_screen(self):
        """Clear terminal screen using Rich Console."""
        self.console.clear()

    def check_dependencies(self):
        """Detect yt-dlp version and system or static ffmpeg availability."""
        self.ytdlp_available = yt_dlp is not None
        if yt_dlp is not None and getattr(yt_dlp, "version", None) is not None:
            self.ytdlp_version = yt_dlp.version.__version__
        self.ffmpeg_available = False

        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.ffmpeg_available = True
        except Exception:
            pass

        if not self.ffmpeg_available and static_ffmpeg is not None:
            try:
                static_ffmpeg.add_paths()
                self.ffmpeg_available = True
            except Exception:
                pass

    def load_config(self):
        """Load saved configuration from config.json."""
        if not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as handle:
                config = json.load(handle)
            self.download_path = config.get("download_path", self.download_path)
            lang = config.get("language", "en")
            self.language = lang if lang in TRANSLATIONS else "en"
            self.embed_metadata = bool(config.get("embed_metadata", True))
            self.auto_check_updates = bool(config.get("auto_check_updates", True))
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            self.print_color(f"⚠ Failed to load config: {exc}", "yellow")

    def save_config(self):
        """Persist configuration atomically."""
        config = {
            "download_path": self.download_path,
            "language": self.language,
            "embed_metadata": self.embed_metadata,
            "auto_check_updates": self.auto_check_updates,
        }
        try:
            atomic_write_text(self.config_file, json.dumps(config, indent=2, ensure_ascii=False))
        except OSError as exc:
            self.print_color(f"⚠ Failed to save config: {exc}", "yellow")

    def load_history(self):
        """Load download history list from history.json."""
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def save_to_history(self, url, format_type, quality, title):
        """Prepend a download entry and persist up to 100 entries atomically."""
        history = self.load_history()
        history.insert(0, {
            "url": url,
            "title": title,
            "timestamp": datetime.now().isoformat(),
            "format": format_type,
            "quality": quality,
        })
        history = history[:100]
        try:
            atomic_write_text(self.history_file, json.dumps(history, indent=2, ensure_ascii=False))
        except OSError as exc:
            self.print_color(f"⚠ Failed to save history: {exc}", "yellow")

    def clear_history(self):
        """Clear saved download history."""
        try:
            atomic_write_text(self.history_file, "[]")
        except OSError as exc:
            self.print_color(f"⚠ Failed to clear history: {exc}", "yellow")

    def get_video_info(self, url):
        """Fetch video metadata and available resolutions via yt-dlp."""
        try:
            cleaned = clean_url(url)
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "color": {"stdout": "never", "stderr": "never"},
            }
            with self.console.status(f"[bold yellow]{_safe_escape(self._t('fetching_info'))}[/bold yellow]", spinner="dots"):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(cleaned, download=False)

            if not info_dict:
                return None

            upload_date = info_dict.get("upload_date")
            if isinstance(upload_date, str) and len(upload_date) == 8 and upload_date.isdigit():
                upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
            elif not upload_date:
                upload_date = "N/A"

            view_count = info_dict.get("view_count")
            like_count = info_dict.get("like_count")

            return {
                "title": info_dict.get("title") or "Unknown",
                "duration": format_duration(info_dict.get("duration")),
                "uploader": info_dict.get("uploader") or "Unknown",
                "upload_date": upload_date,
                "views": f"{view_count:,}" if view_count is not None else "N/A",
                "likes": f"{like_count:,}" if like_count is not None else "N/A",
                "available_qualities": extract_available_qualities(info_dict.get("formats")),
            }
        except Exception as exc:
            self.print_color(f"⚠ {self._t('fetching_info')} Error: {exc}", "yellow")
            return None

    def show_video_info(self, info):
        """Display video metadata in a Rich table."""
        table = Table(title=f"[▶] {_safe_escape(self._t('video_info'))}", box=box.ROUNDED)
        table.add_column(self._t("property"), style="cyan bold")
        table.add_column(self._t("value"), style="white")

        table.add_row(self._t("col_title"), _safe_escape(info["title"]))
        table.add_row(self._t("col_channel"), _safe_escape(info["uploader"]))
        table.add_row(self._t("col_duration"), _safe_escape(info["duration"]))
        table.add_row(self._t("col_upload_date"), _safe_escape(info["upload_date"]))
        table.add_row(self._t("col_views"), _safe_escape(info["views"]))
        table.add_row(self._t("col_likes"), _safe_escape(info["likes"]))

        self.console.print(table)

    def download_with_progress(self, url, format_type, quality, audio_format="mp3"):
        """Download a single video or audio stream with a Rich progress bar."""
        cleaned = clean_url(url)

        if not self.ffmpeg_available:
            self.print_color(f"⚠ {self._t('ffmpeg_missing_warn')}", "yellow")

        if format_type == "audio" and self.embed_metadata:
            if audio_format not in EMBED_THUMBNAIL_FORMATS:
                self.print_color(f"ℹ {self._t('wav_thumbnail_note')}", "cyan")
            elif not MUTAGEN_AVAILABLE:
                self.print_color(f"ℹ {self._t('mutagen_missing_note')}", "cyan")

        ydl_opts = build_ydl_opts(
            download_path=self.download_path,
            format_type=format_type,
            quality=quality,
            audio_format=audio_format,
            embed_metadata=self.embed_metadata,
            ffmpeg_available=self.ffmpeg_available,
            mutagen_available=MUTAGEN_AVAILABLE,
            is_playlist=False,
        )

        progress_data = {
            "percent": 0.0,
            "speed": "N/A",
            "eta": "N/A",
            "status": "preparing",
        }
        cancel_event = threading.Event()

        def progress_hook(d):
            if cancel_event.is_set():
                raise yt_dlp.utils.DownloadCancelled("Cancelled by user")
            status = d.get("status")
            if status == "downloading":
                progress_data["status"] = "downloading"
                pct = compute_progress_percent(d)
                if pct is not None:
                    progress_data["percent"] = pct
                progress_data["speed"] = format_speed(d.get("speed"))
                progress_data["eta"] = format_eta(d.get("eta"))
            elif status == "finished":
                progress_data["status"] = "finished"
                progress_data["percent"] = 100.0

        ydl_opts["progress_hooks"] = [progress_hook]

        try:
            with Progress(
                SpinnerColumn(spinner_name="dots12", style="cyan"),
                TextColumn("[progress.description]{task.description}"),
                TextColumn("[cyan]{task.fields[custom_bar]}[/cyan]"),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=self.console,
                transient=True,
            ) as progress:
                task = progress.add_task(
                    f"[↓] {_safe_escape(self._t('downloading'))}",
                    total=100,
                    custom_bar="░" * 20,
                )

                dl_error = {"error": None}

                def run_download():
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([cleaned])
                    except Exception as exc:
                        dl_error["error"] = exc

                download_thread = threading.Thread(target=run_download, daemon=True)
                download_thread.start()

                try:
                    while download_thread.is_alive():
                        pct = max(0.0, min(100.0, progress_data["percent"]))
                        filled = max(0, min(20, int(20 * pct / 100.0)))
                        bar_str = "█" * filled + "░" * (20 - filled)
                        if progress_data["status"] == "finished":
                            desc = f"[↓] {_safe_escape(self._t('status_postprocessing'))}"
                        else:
                            desc = (
                                f"[↓] {_safe_escape(self._t('downloading'))} "
                                f"{progress_data['speed']} • ETA: {progress_data['eta']}"
                            )
                        progress.update(task, completed=pct, custom_bar=bar_str, description=desc)
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    cancel_event.set()
                    download_thread.join(timeout=2.0)
                    self.print_color(f"\n⚠ {self._t('download_interrupted')}", "yellow")
                    return 1

                if dl_error["error"]:
                    raise dl_error["error"]

                progress.update(
                    task,
                    completed=100,
                    custom_bar="█" * 20,
                    description=f"✔ {_safe_escape(self._t('download_complete'))}",
                )
            return 0
        except Exception as exc:
            self.print_color(f"✖ Error: {exc}", "red")
            return 1

    def show_header(self):
        """Display application header panel."""
        if Text is None or Panel is None or Align is None:
            self.print_color(f"{self._t('title')} - {self._t('subtitle')}", "blue", bold=True)
            return
        title_str = self._t("title")
        parts = title_str.split(" ", 1)
        header_text = Text()
        header_text.append(parts[0], style="bold red")
        if len(parts) > 1:
            header_text.append(" " + parts[1], style="bold white")

        subtitle = Text("\n" + self._t("subtitle"), style="dim blue")
        header_panel = Panel(
            Align.center(header_text),
            border_style="blue",
            padding=(1, 2),
        )
        self.console.print(header_panel)
        self.console.print(Align.center(subtitle))
        self.console.print()

    def show_menu(self):
        """Display main menu table."""
        table = Table(title=self._t("main_menu"), box=box.ROUNDED, border_style="cyan")
        table.add_column(self._t("option"), style="cyan bold", no_wrap=True)
        table.add_column(self._t("description"), style="white")

        table.add_row("1", f"[cyan]↓[/cyan] {_safe_escape(self._t('download_video'))}")
        table.add_row("2", f"[blue]♪[/blue] {_safe_escape(self._t('download_audio'))}")
        table.add_row("3", f"[purple]≡[/purple] {_safe_escape(self._t('download_playlist'))}")
        table.add_row("4", f"[yellow]◷[/yellow] {_safe_escape(self._t('view_history'))}")
        table.add_row("5", f"[white]⚙[/white] {_safe_escape(self._t('settings'))}")
        table.add_row("6", f"[blue]ℹ[/blue] {_safe_escape(self._t('about'))}")
        table.add_row("7", f"[cyan]≣[/cyan] {_safe_escape(self._t('bulk_download'))}")
        table.add_row("8", f"[red]✖[/red] {_safe_escape(self._t('exit'))}")

        self.console.print(table)

    def _pause(self):
        """Wait for user to press Enter without crashing on EOF."""
        try:
            input(f"\n{self._t('press_enter')}")
        except (EOFError, KeyboardInterrupt):
            pass

    def download_video(self, audio_only=False):
        """Download a single video or audio track."""
        self.clear_screen()
        self.show_header()

        url = Prompt.ask(f"\n[bold cyan]{_safe_escape(self._t('enter_url'))}[/bold cyan]")
        if not url or not url.strip():
            self.print_color(f"✖ {self._t('no_url')}", "red")
            time.sleep(1.5)
            return

        original_url = url.strip()
        url = clean_url(original_url)

        if not is_valid_youtube_url(url):
            self.print_color(f"✖ {self._t('invalid_url')}", "red")
            time.sleep(1.5)
            return

        info = self.get_video_info(url)
        if info:
            self.show_video_info(info)
        else:
            self.print_color(f"⚠ {self._t('fetch_fallback_warn')}", "yellow")

        if not audio_only:
            qualities = []
            if info and info.get("available_qualities"):
                qualities.append((f"★ {_safe_escape(self._t('best_quality'))}", "best"))
                for q in info["available_qualities"]:
                    h = q["height"]
                    tbr = q["tbr"]
                    if tbr > 1000:
                        bitrate_str = f"{tbr / 1000:.1f} Mbps"
                    elif tbr > 0:
                        bitrate_str = f"{int(tbr)} kbps"
                    else:
                        bitrate_str = "N/A"

                    name = f"{h}p"
                    if h == 2160:
                        name = "4K (2160p)"
                    elif h == 1440:
                        name = "2K (1440p)"
                    elif h == 1080:
                        name = "1080p FHD"
                    elif h == 720:
                        name = "720p HD"
                    qualities.append((f"▶ {name} - [dim]{bitrate_str}[/dim]", str(h)))
            else:
                qualities = [
                    (f"★ {_safe_escape(self._t('best_quality'))}", "best"),
                    ("▶ 4K (2160p)", "2160"),
                    ("▶ 2K (1440p)", "1440"),
                    ("▶ 1080p", "1080"),
                    ("▶ 720p", "720"),
                    ("▶ 480p", "480"),
                    ("▶ 360p", "360"),
                ]

            self.print_color(f"\n{self._t('select_quality')}:", "cyan")
            for idx, (label, _) in enumerate(qualities, 1):
                self.console.print(f"  {idx}. {label}")

            valid_choices = [str(i) for i in range(1, len(qualities) + 1)]
            choice_str = Prompt.ask(
                self._t("your_choice"),
                choices=valid_choices,
                default="1",
            )
            quality = qualities[int(choice_str) - 1][1]
        else:
            quality = "best"

        audio_format = "mp3"
        if audio_only:
            formats = [("MP3", "mp3"), ("M4A", "m4a"), ("FLAC", "flac"), ("WAV", "wav")]
            self.print_color(f"\n{self._t('select_audio_format')}:", "cyan")
            for idx, (label, _) in enumerate(formats, 1):
                self.console.print(f"  {idx}. {label}")

            fmt_choice = Prompt.ask(
                self._t("your_choice"),
                choices=["1", "2", "3", "4"],
                default="1",
            )
            audio_format = formats[int(fmt_choice) - 1][1]

        confirm = Confirm.ask(f"\n[bold green]{_safe_escape(self._t('start_download'))}[/bold green]", default=True)
        if not confirm:
            self.print_color(self._t("download_cancelled"), "yellow")
            time.sleep(1)
            return

        self.print_color(f"\n[>] {self._t('saving_to')}: {self.download_path}", "cyan")
        self.console.print()
        format_type = "audio" if audio_only else "video"

        return_code = self.download_with_progress(url, format_type, quality, audio_format=audio_format)

        self.console.print()
        if return_code == 0:
            self.print_color(f"✔ {self._t('download_complete')}", "green")
            self.save_to_history(original_url, format_type, quality, info["title"] if info else "Unknown")
        else:
            self.print_color(f"✖ {self._t('download_failed')}", "red")

        self._pause()

    def download_playlist(self):
        """Download an entire playlist with deduplicated per-video progress."""
        self.clear_screen()
        self.show_header()

        url = Prompt.ask(f"\n[bold cyan]{_safe_escape(self._t('enter_url'))}[/bold cyan]")
        if not url or not url.strip():
            self.print_color(f"✖ {self._t('no_url')}", "red")
            time.sleep(1.5)
            return

        url = clean_url(url, preserve_playlist=True)
        if not is_valid_youtube_url(url):
            self.print_color(f"✖ {self._t('invalid_url')}", "red")
            time.sleep(1.5)
            return

        if "list=" in url and "watch?" in url:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            if "list" in params:
                url = f"https://www.youtube.com/playlist?list={params['list'][0]}"

        try:
            ydl_opts_info = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "noplaylist": False,
                "color": {"stdout": "never", "stderr": "never"},
            }

            with self.console.status(f"[bold yellow]{_safe_escape(self._t('fetching_info'))}[/bold yellow]", spinner="dots"):
                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    playlist_info = ydl.extract_info(url, download=False)

            if not playlist_info or "entries" not in playlist_info:
                self.print_color(f"✖ {self._t('playlist_fetch_error')}", "red")
                time.sleep(2)
                return

            entries = [e for e in (playlist_info.get("entries") or []) if e is not None]
            video_count = len(entries)
            if video_count == 0:
                self.print_color(f"⚠ {self._t('playlist_empty')}", "yellow")
                time.sleep(2)
                return

            self.print_color(f"\n[≡] {self._t('playlist_count').format(video_count)}", "green")

            confirm = Confirm.ask(
                f"\n[bold green]{_safe_escape(self._t('playlist_confirm').format(video_count))}[/bold green]",
                default=False,
            )
            if not confirm:
                self.print_color(self._t("download_cancelled"), "yellow")
                time.sleep(1)
                return

            if not self.ffmpeg_available:
                self.print_color(f"⚠ {self._t('ffmpeg_missing_warn')}", "yellow")

            self.print_color(f"\n[>] {self._t('saving_to')}: {self.download_path}", "cyan")
            self.console.print()

            ydl_opts = build_ydl_opts(
                download_path=self.download_path,
                format_type="video",
                quality="best",
                ffmpeg_available=self.ffmpeg_available,
                is_playlist=True,
            )

            completed_ids = set()
            seen_counter = [0]
            lock = threading.Lock()
            cancel_event = threading.Event()

            def _record_completion(info_dict):
                vid_id = (info_dict or {}).get("id")
                with lock:
                    if vid_id:
                        completed_ids.add(vid_id)
                    else:
                        seen_counter[0] += 1
                        completed_ids.add(f"_anon_{seen_counter[0]}")

            def progress_hook(d):
                if cancel_event.is_set():
                    raise yt_dlp.utils.DownloadCancelled("Cancelled by user")
                # Only count single-stream completions directly when no postprocessor merge runs
                if d.get("status") == "finished" and not self.ffmpeg_available:
                    _record_completion(d.get("info_dict"))

            def postprocessor_hook(d):
                if d.get("status") == "finished":
                    _record_completion(d.get("info_dict"))

            ydl_opts["progress_hooks"] = [progress_hook]
            if self.ffmpeg_available:
                ydl_opts["postprocessor_hooks"] = [postprocessor_hook]

            with Progress(
                SpinnerColumn(spinner_name="dots12", style="cyan"),
                TextColumn("[progress.description]{task.description}"),
                TextColumn("[cyan]{task.fields[custom_bar]}[/cyan]"),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=self.console,
                transient=True,
            ) as progress:
                task = progress.add_task(
                    f"[≡] {_safe_escape(self._t('playlist_downloading'))}",
                    total=video_count,
                    custom_bar="░" * 20,
                )

                dl_error = {"error": None}

                def run_dl():
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])
                    except Exception as exc:
                        dl_error["error"] = exc

                dl_thread = threading.Thread(target=run_dl, daemon=True)
                dl_thread.start()

                try:
                    while dl_thread.is_alive():
                        with lock:
                            completed = min(len(completed_ids), video_count)
                        filled = max(0, min(20, int(20 * completed / video_count)))
                        bar_str = "█" * filled + "░" * (20 - filled)
                        current_idx = min(completed + 1, video_count)
                        desc = f"[≡] {_safe_escape(self._t('playlist_downloading_item').format(current_idx, video_count))}"
                        progress.update(task, completed=completed, custom_bar=bar_str, description=desc)
                        time.sleep(0.25)
                except KeyboardInterrupt:
                    cancel_event.set()
                    dl_thread.join(timeout=2.0)
                    self.print_color(f"\n⚠ {self._t('download_interrupted')}", "yellow")
                    self._pause()
                    return

                if dl_error["error"]:
                    raise dl_error["error"]

                progress.update(
                    task,
                    completed=video_count,
                    custom_bar="█" * 20,
                    description=f"✔ {_safe_escape(self._t('playlist_complete'))}",
                )

            self.console.print()
            self.print_color(f"✔ {self._t('download_complete')}", "green")
            playlist_title = playlist_info.get("title") or f"Playlist ({video_count} videos)"
            self.save_to_history(url, "video", f"playlist ({video_count})", playlist_title)
        except Exception as exc:
            self.print_color(f"\n✖ {self._t('download_failed')} {exc}", "red")

        self._pause()

    def show_history(self):
        """Display recent download history and optionally allow clearing it."""
        self.clear_screen()
        self.show_header()

        history = self.load_history()
        if not history:
            self.print_color(f"[-] {self._t('no_history')}", "yellow")
            time.sleep(1.5)
            return

        table = Table(title=f"[◷] {_safe_escape(self._t('history_title'))}", box=box.ROUNDED, border_style="cyan")
        table.add_column("#", style="cyan bold", no_wrap=True)
        table.add_column(self._t("col_title"), style="white")
        table.add_column(self._t("col_format"), style="green")
        table.add_column(self._t("col_quality"), style="blue")
        table.add_column(self._t("col_date"), style="dim")

        shown = history[:20]
        for idx, item in enumerate(shown, 1):
            raw_title = item.get("title") or "Unknown"
            title = raw_title[:60] + ("..." if len(raw_title) > 60 else "")
            fmt_label = f"[♪] {_safe_escape(self._t('audio_label'))}" if item.get("format") == "audio" else f"▶ {_safe_escape(self._t('video_label'))}"
            table.add_row(
                str(idx),
                _safe_escape(title),
                fmt_label,
                _safe_escape(item.get("quality", "best")),
                _safe_escape(str(item.get("timestamp", ""))[:10]),
            )

        self.console.print(table)
        self.print_color(self._t("history_showing").format(len(shown), len(history)), "dim")

        if Confirm.ask(f"\n{_safe_escape(self._t('clear_history_prompt'))}", default=False):
            self.clear_history()
            self.print_color(f"✔ {self._t('history_cleared')}", "green")
            time.sleep(1.2)
            return

        self._pause()

    def show_settings(self):
        """Display and interactively edit application settings in a loop."""
        while True:
            self.clear_screen()
            self.show_header()

            table = Table(title=f"⚙ {_safe_escape(self._t('settings'))}", box=box.ROUNDED, border_style="cyan")
            table.add_column(self._t("property"), style="cyan bold")
            table.add_column(self._t("value"), style="white")

            table.add_row(self._t("download_path"), _safe_escape(self.download_path))
            ytdlp_status = (
                f"[green]✔ v{_safe_escape(self.ytdlp_version)}[/green]"
                if self.ytdlp_available
                else f"[red]✖ {_safe_escape(self._t('missing'))}[/red]"
            )
            ffmpeg_status = (
                f"[green]✔ {_safe_escape(self._t('connected'))}[/green]"
                if self.ffmpeg_available
                else f"[red]✖ {_safe_escape(self._t('missing'))}[/red]"
            )
            table.add_row("yt-dlp", ytdlp_status)
            table.add_row("ffmpeg", ffmpeg_status)
            table.add_row(self._t("change_lang"), _safe_escape(self._t("lang_name")))
            meta_status = (
                f"[green]✔ {_safe_escape(self._t('enabled'))}[/green]"
                if self.embed_metadata
                else f"[red]✖ {_safe_escape(self._t('disabled'))}[/red]"
            )
            table.add_row(self._t("embed_metadata"), meta_status)
            auto_upd_status = (
                f"[green]✔ {_safe_escape(self._t('enabled'))}[/green]"
                if self.auto_check_updates
                else f"[red]✖ {_safe_escape(self._t('disabled'))}[/red]"
            )
            table.add_row(self._t("auto_check_updates"), auto_upd_status)

            self.console.print(table)

            self.print_color(f"\n{self._t('settings_options')}:", "yellow")
            self.console.print(f"  1. {_safe_escape(self._t('change_path'))}")
            self.console.print(f"  2. {_safe_escape(self._t('check_updates'))}")
            self.console.print(f"  3. {_safe_escape(self._t('check_github'))}")
            self.console.print(f"  4. {_safe_escape(self._t('change_lang'))}")
            self.console.print(f"  5. {_safe_escape(self._t('embed_metadata'))} ({'✔' if self.embed_metadata else '✖'})")
            self.console.print(f"  6. {_safe_escape(self._t('auto_check_updates'))} ({'✔' if self.auto_check_updates else '✖'})")
            self.console.print(f"  7. {_safe_escape(self._t('install_system'))}")
            self.console.print(f"  8. [red]{_safe_escape(self._t('uninstall_system'))}[/red]")
            self.console.print(f"  9. {_safe_escape(self._t('back_to_menu'))}")

            choice = Prompt.ask(
                f"\n{_safe_escape(self._t('select_option'))}",
                choices=["1", "2", "3", "4", "5", "6", "7", "8", "9"],
                default="9",
            )

            if choice == "1":
                self.print_color(f"\n{self._t('current_path')}: {self.download_path}", "cyan")
                raw_path = Prompt.ask(_safe_escape(self._t("enter_new_path")), default=self.download_path)
                new_path = normalize_user_path(raw_path)
                if new_path:
                    try:
                        os.makedirs(new_path, exist_ok=True)
                    except OSError as exc:
                        self.print_color(f"✖ {self._t('error_creating_dir')}: {exc}", "red")
                        time.sleep(2)
                        continue
                    self.download_path = new_path
                    self.save_config()
                    self.print_color(f"✔ {self._t('settings_saved')}", "green")
                    time.sleep(1.2)
            elif choice == "2":
                self.check_for_updates()
            elif choice == "3":
                self.check_github_updates()
            elif choice == "4":
                self.print_color(f"\n{self._t('select_language')}:", "cyan")
                self.console.print("  1. English")
                self.console.print("  2. Русский")
                lang_choice = Prompt.ask(
                    _safe_escape(self._t("select_option")),
                    choices=["1", "2"],
                    default="1" if self.language == "en" else "2",
                )
                self.language = "en" if lang_choice == "1" else "ru"
                self.save_config()
                self.print_color(f"✔ {self._t('lang_name')}!", "green")
                time.sleep(1.2)
            elif choice == "5":
                self.embed_metadata = not self.embed_metadata
                self.save_config()
                status = self._t("enabled") if self.embed_metadata else self._t("disabled")
                self.print_color(f"✔ {self._t('embed_metadata_toggled').format(status)}", "green")
                time.sleep(1.2)
            elif choice == "6":
                self.auto_check_updates = not self.auto_check_updates
                self.save_config()
                status = self._t("enabled") if self.auto_check_updates else self._t("disabled")
                self.print_color(f"✔ {self._t('auto_check_updates_toggled').format(status)}", "green")
                time.sleep(1.2)
            elif choice == "7":
                self.install_to_system()
            elif choice == "8":
                self.uninstall_from_system()
            elif choice == "9":
                return

    def install_to_system(self, dest_path="/usr/local/bin/youtube", script_path=None):
        """Install the script globally via symlink using realpath to avoid symlink loops."""
        self.clear_screen()
        self.show_header()

        if os.name == "nt":
            self.print_color(f"ℹ {self._t('windows_install_unsupported')}", "yellow")
            self._pause()
            return

        resolved_script = os.path.realpath(script_path or __file__)
        self.print_color(f"★ {self._t('install_system')}: {dest_path}", "yellow")

        try:
            os.chmod(resolved_script, 0o755)
            dest_parent = os.path.dirname(dest_path)
            if dest_parent and not os.path.exists(dest_parent):
                os.makedirs(dest_parent, exist_ok=True)

            if os.path.lexists(dest_path):
                if os.path.islink(dest_path) and os.path.realpath(dest_path) == resolved_script:
                    self.print_color(f"\n✔ {self._t('already_installed')}", "green")
                    time.sleep(1.5)
                    return
                try:
                    os.remove(dest_path)
                except PermissionError:
                    self.print_color(
                        f"\n✖ {self._t('install_fail')}\nsudo ln -sf {resolved_script} {dest_path}",
                        "red",
                    )
                    self._pause()
                    return

            os.symlink(resolved_script, dest_path)
            self.print_color(f"\n✔ {self._t('install_success')}", "green")
        except PermissionError:
            self.print_color(
                f"\n✖ {self._t('install_fail')}\nsudo ln -sf {resolved_script} {dest_path}",
                "red",
            )
        except Exception as exc:
            self.print_color(f"\n✖ Error: {exc}", "red")

        self._pause()

    def uninstall_from_system(self):
        """Uninstall global symlinks and optionally remove ~/.ytdl data."""
        self.clear_screen()
        self.show_header()

        candidate_links = [
            "/usr/local/bin/youtube",
            os.path.join(os.path.expanduser("~"), ".local", "bin", "youtube"),
        ]
        script_dir = os.path.join(os.path.expanduser("~"), ".ytdl", "bin")
        found_links = [p for p in candidate_links if os.path.lexists(p)]

        if not found_links and not os.path.exists(script_dir):
            self.print_color(f"\n[-] {self._t('uninstall_not_installed')}", "yellow")
            self._pause()
            return

        if not Confirm.ask(f"\n[bold red]{_safe_escape(self._t('uninstall_confirm'))}[/bold red]", default=False):
            return

        for link_path in found_links:
            try:
                try:
                    os.remove(link_path)
                except PermissionError:
                    subprocess.run(["sudo", "rm", link_path], check=True)
                self.print_color(f"✔ {self._t('removed_item').format(link_path)}", "green")
            except Exception as exc:
                self.print_color(f"✖ {self._t('remove_failed').format(link_path, exc)}", "red")

        running_real = os.path.realpath(__file__)
        removed_self = False
        if os.path.exists(script_dir):
            try:
                removed_self = running_real.startswith(os.path.realpath(script_dir) + os.sep)
                shutil.rmtree(script_dir)
                self.print_color(f"✔ {self._t('removed_item').format(script_dir)}", "green")
            except Exception as exc:
                self.print_color(f"✖ {self._t('remove_failed').format(script_dir, exc)}", "red")

        if os.path.exists(self.config_dir) and Confirm.ask(
            f"\n{_safe_escape(self._t('uninstall_data_prompt'))}", default=False
        ):
            try:
                shutil.rmtree(self.config_dir)
                self.print_color(f"✔ {self._t('removed_item').format(self.config_dir)}", "green")
            except Exception as exc:
                self.print_color(f"✖ {self._t('remove_failed').format(self.config_dir, exc)}", "red")

        self.print_color(f"\n✔ {self._t('uninstall_success')}", "green")
        if removed_self:
            sys.exit(0)
        self._pause()

    def _display_module_updates(self, updates):
        """Render available Python module updates as a Rich table or plain list."""
        if Table is not None and box is not None:
            table = Table(
                title=f"[!] {_safe_escape(self._t('updates_available'))}",
                box=box.ROUNDED,
                border_style="yellow",
            )
            table.add_column(self._t("col_package"), style="cyan bold")
            table.add_column(self._t("col_current"), style="white")
            table.add_column(self._t("col_latest"), style="green bold")

            for pkg, (current, latest) in updates.items():
                table.add_row(pkg, _safe_escape(current), _safe_escape(latest))

            self.console.print(table)
        else:
            self.print_color(f"\n[!] {self._t('updates_available')}:", "yellow", bold=True)
            for pkg, (current, latest) in updates.items():
                self.print_color(f"  • {pkg}: {current} -> {latest}", "cyan")

    def check_startup_updates(self):
        """Automatically check for app and library updates at startup."""
        if not self.auto_check_updates:
            return

        def _fetch_all():
            with ThreadPoolExecutor(max_workers=2) as pool:
                app_future = pool.submit(fetch_app_update, STARTUP_UPDATE_TIMEOUT)
                mod_future = pool.submit(fetch_module_updates, STARTUP_UPDATE_TIMEOUT, True)

                try:
                    remote_version, app_content = app_future.result()
                except Exception:
                    remote_version, app_content = None, None

                try:
                    module_updates = mod_future.result()
                except Exception:
                    module_updates = {}

            return remote_version, app_content, module_updates

        if hasattr(self.console, "status"):
            with self.console.status(
                f"[bold yellow]{_safe_escape(self._t('checking_startup_updates'))}[/bold yellow]",
                spinner="dots",
            ):
                remote_version, app_content, module_updates = _fetch_all()
        else:
            remote_version, app_content, module_updates = _fetch_all()

        has_app_update = bool(
            remote_version
            and app_content
            and parse_version(remote_version) > parse_version(VERSION)
        )
        if not has_app_update and not module_updates:
            return

        if has_app_update:
            self.print_color(f"\n[!] {self._t('app_update_available').format(remote_version)}", "yellow", bold=True)
            if Confirm.ask(f"\n{_safe_escape(self._t('update_app_prompt'))}", default=True):
                self.apply_app_update(app_content)

        if module_updates:
            self._display_module_updates(module_updates)
            if Confirm.ask(f"\n{_safe_escape(self._t('install_updates_prompt'))}", default=True):
                self.apply_updates(list(module_updates.keys()))

    def check_for_updates(self):
        """Check PyPI directly for updates to managed Python dependencies."""
        self.clear_screen()
        self.show_header()
        self.print_color(f"★ {self._t('checking_updates')}", "yellow")

        try:
            updates = fetch_module_updates(timeout=10, ignore_errors=False)

            if not updates:
                self.print_color(f"\n✔ {self._t('up_to_date')}", "green")
                time.sleep(1.5)
                return

            self._display_module_updates(updates)
            if Confirm.ask(f"\n{_safe_escape(self._t('install_updates_prompt'))}", default=True):
                self.apply_updates(list(updates.keys()))
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                self.print_color(f"\n✖ {self._t('ssl_cert_hint')}", "red")
            else:
                self.print_color(f"\n✖ {self._t('updating_libs_check_error')}: {exc}", "red")
            time.sleep(2.5)
        except Exception as exc:
            self.print_color(f"\n✖ {self._t('updating_libs_check_error')}: {exc}", "red")
            time.sleep(2.5)

    def apply_updates(self, packages):
        """Upgrade outdated packages via pip and restart."""
        self.print_color(f"\n[>] {self._t('updating_libs')}", "cyan")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + packages)
            self.print_color(f"\n✔ {self._t('updates_installed')}", "green")
            self.print_color(self._t("restarting"), "yellow")
            time.sleep(1.5)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as exc:
            self.print_color(f"\n✖ {exc}", "red")
            self.print_color(self._t("pep668_hint"), "yellow")
            self._pause()

    def check_github_updates(self):
        """Check GitHub Releases (falling back to main) using verified TLS."""
        self.clear_screen()
        self.show_header()
        self.print_color(f"★ {self._t('checking_updates')}", "yellow")

        try:
            remote_version, content = fetch_app_update(timeout=10)
            if not remote_version:
                self.print_color(f"\n✖ {self._t('parse_version_error')}", "red")
                time.sleep(2)
                return

            if parse_version(remote_version) > parse_version(VERSION):
                self.print_color(f"\n[!] {self._t('app_update_available').format(remote_version)}", "yellow", bold=True)
                if Confirm.ask(f"\n{_safe_escape(self._t('update_app_prompt'))}", default=True):
                    self.apply_app_update(content)
            else:
                self.print_color(f"\n✔ {self._t('app_up_to_date')}", "green")
                time.sleep(2)
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                self.print_color(f"\n✖ {self._t('ssl_cert_hint')}", "red")
            else:
                self.print_color(f"\n✖ {self._t('github_error')}: {exc}", "red")
            time.sleep(3)
        except Exception as exc:
            self.print_color(f"\n✖ {self._t('github_error')}: {exc}", "red")
            time.sleep(3)

    def apply_app_update(self, content):
        """Validate Python syntax/header, atomically write update, and restart."""
        self.print_color(f"\n[>] {self._t('updating_app')}", "cyan")
        try:
            if not content.lstrip("\ufeff").startswith("#!/usr/bin/env python3"):
                raise ValueError(self._t("update_validation_error"))
            compile(content, "ytdownloader.py", "exec")

            script_path = os.path.realpath(__file__)
            atomic_write_text(script_path, content, encoding="utf-8", preserve_mode=True)

            self.print_color(f"\n✔ {self._t('app_updated')}", "green")
            self.print_color(self._t("restarting"), "yellow")
            time.sleep(1.5)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as exc:
            self.print_color(f"\n✖ {exc}", "red")
            self._pause()

    def show_about(self):
        """Show application details and dependency info."""
        self.clear_screen()
        self.show_header()

        self.console.print(Panel(_safe_escape(self._t("about_text")), title=_safe_escape(self._t("about")), border_style="blue"))
        self._pause()

    def download_bulk(self):
        """Batch download URLs from a UTF-8 text file."""
        self.clear_screen()
        self.show_header()

        self.print_color(self._t("bulk_file_prompt"), "cyan")
        raw_path = Prompt.ask(f"\n[bold cyan]{_safe_escape(self._t('file_path'))}[/bold cyan]")
        filepath = normalize_user_path(raw_path)

        if not filepath or not os.path.isfile(filepath):
            self.print_color(f"✖ {self._t('file_not_found')}", "red")
            time.sleep(2)
            return

        try:
            with open(filepath, "r", encoding="utf-8") as handle:
                urls = [line.strip() for line in handle if line.strip() and not line.lstrip().startswith("#")]
        except OSError as exc:
            self.print_color(f"✖ {self._t('bulk_read_error')}: {exc}", "red")
            time.sleep(2)
            return

        if not urls:
            self.print_color(f"⚠ {self._t('bulk_no_urls')}", "yellow")
            time.sleep(2)
            return

        self.print_color(self._t("bulk_found_urls").format(len(urls)), "green")

        self.print_color(f"\n{self._t('bulk_select_format')}:", "cyan")
        self.console.print(f"  1. ▶ {_safe_escape(self._t('bulk_video_best'))}")
        self.console.print(f"  2. [♪] {_safe_escape(self._t('bulk_audio_mp3'))}")

        choice = Prompt.ask(self._t("your_choice"), choices=["1", "2"], default="1")
        format_type = "audio" if choice == "2" else "video"

        succeeded = 0
        failed = 0
        skipped = 0

        for idx, raw_url in enumerate(urls, 1):
            self.print_color("\n" + "=" * 45, "cyan")
            self.print_color(self._t("bulk_processing").format(idx, len(urls), raw_url), "blue", bold=True)
            cleaned = clean_url(raw_url)
            if not is_valid_youtube_url(cleaned):
                self.print_color(f"✖ {self._t('invalid_url')}", "red")
                skipped += 1
                continue

            rc = self.download_with_progress(cleaned, format_type, "best", audio_format="mp3")
            if rc == 0:
                succeeded += 1
                self.save_to_history(raw_url, format_type, "best", raw_url)
            else:
                failed += 1

        self.print_color(f"\n✔ {self._t('bulk_summary').format(succeeded, failed, skipped)}", "green")
        self._pause()

    def run(self):
        """Run the main interactive menu loop."""
        self.clear_screen()
        self.show_header()
        self.check_startup_updates()

        while True:
            self.clear_screen()
            self.show_header()
            self.show_menu()

            try:
                choice = Prompt.ask(
                    f"\n[bold cyan]{_safe_escape(self._t('select_option'))}[/bold cyan]",
                    choices=["1", "2", "3", "4", "5", "6", "7", "8"],
                    default="1",
                )
            except (EOFError, KeyboardInterrupt):
                self.print_color(f"\n\n👋 {self._t('confirm_exit')}", "green")
                return

            if choice == "1":
                self.download_video(audio_only=False)
            elif choice == "2":
                self.download_video(audio_only=True)
            elif choice == "3":
                self.download_playlist()
            elif choice == "4":
                self.show_history()
            elif choice == "5":
                self.show_settings()
            elif choice == "6":
                self.show_about()
            elif choice == "7":
                self.download_bulk()
            elif choice == "8":
                self.print_color(f"\n👋 {self._t('confirm_exit')}", "green")
                return


def parse_cli_args(argv=None):
    """Parse command-line options before third-party imports."""
    parser = argparse.ArgumentParser(
        prog="youtube",
        description="YouTube Downloader - Terminal Edition",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="Show application version and exit",
    )
    parser.add_argument(
        "--no-update-check",
        action="store_true",
        help="Skip automatic app and library update checks on startup",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """Application entrypoint."""
    args = parse_cli_args(argv)
    if args.version:
        print(f"YouTube Downloader v{VERSION}")
        return 0

    try:
        ensure_dependencies()
        _load_third_party_modules()
        app = TerminalYouTubeDownloader(
            auto_check_updates=False if args.no_update_check else None,
        )
        app.run()
        return 0
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        return 0
    except Exception as exc:
        print(f"\n✖ Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
