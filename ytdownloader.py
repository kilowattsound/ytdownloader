#!/usr/bin/env python3
"""
YouTube Downloader - Terminal Edition
A beautiful command-line YouTube downloader with rich formatting (Pure Python)
"""

import subprocess
import sys
import os
from pathlib import Path
import json
from datetime import datetime
import time
import re
import threading
import queue
import shutil
import urllib.request
import ssl

VERSION = "2.2"
REPO_URL = "kilowattsound/ytdownloader"

def ensure_dependencies():
    """Ensure required Python modules are installed"""
    missing = []
    try:
        import rich
    except ImportError:
        missing.append('rich')
    
    try:
        import yt_dlp
    except ImportError:
        missing.append('yt-dlp')

    try:
        import static_ffmpeg
    except ImportError:
        missing.append('static-ffmpeg')
    
    if missing:
        print("\n" + "="*50)
        print("Dependency Check")
        print("="*50)
        print(f"Missing modules: {', '.join(missing)}")
        choice = input(f"\nWould you like to install the missing modules? [y/n] (y): ").lower() or 'y'
        
        if choice == 'y':
            print("\nInstalling modules... this may take a moment.")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
                print("\n✔ Modules installed successfully!")
                print("Restarting script...\n")
                os.execv(sys.executable, ['python3'] + sys.argv)
            except Exception as e:
                print(f"\n✖ Error installing modules: {e}")
                print("Please install them manually using: pip install " + " ".join(missing))
                sys.exit(1)
        else:
            print(f"\n✖ This script requires {', '.join(missing)} to run.")
            sys.exit(1)

# Run dependency check before importing anything else
ensure_dependencies()

# Now safe to import
from rich.console import Console
from rich.progress import (
    Progress, BarColumn, TextColumn, TimeRemainingColumn, 
    TransferSpeedColumn, ProgressColumn, SpinnerColumn
)
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import box
from rich.live import Live
from rich.text import Text
from rich.layout import Layout
from rich.align import Align
from rich import print as rprint
import yt_dlp
try:
    import static_ffmpeg
except ImportError:
    static_ffmpeg = None

RICH_AVAILABLE = True

TRANSLATIONS = {
    'en': {
        'title': 'YouTube Downloader',
        'subtitle': f'Terminal Edition v{VERSION}',
        'main_menu': 'Main Menu',
        'download_video': 'Download Video',
        'download_audio': 'Download Audio Only',
        'download_playlist': 'Download Playlist',
        'view_history': 'View Download History',
        'settings': 'Settings',
        'about': 'About',
        'bulk_download': 'Bulk Download',
        'exit': 'Exit',
        'select_option': 'Select an option',
        'enter_url': 'Enter YouTube URL',
        'fetching_info': 'Fetching video information...',
        'video_info': 'Video Information',
        'property': 'Property',
        'value': 'Value',
        'select_quality': 'Select Quality',
        'best_quality': 'Best Quality',
        'start_download': 'Start download?',
        'saving_to': 'Saving to',
        'download_complete': 'Download completed successfully!',
        'download_failed': 'Download failed!',
        'press_enter': 'Press Enter to continue...',
        'no_url': 'No URL provided!',
        'invalid_url': 'Invalid YouTube URL!',
        'download_path': 'Download Path',
        'change_path': 'Change download location',
        'check_updates': 'Check for library updates',
        'check_github': 'Check for app updates (GitHub)',
        'change_lang': 'Change Language',
        'install_system': 'Install to System (Global Alias)',
        'install_success': 'Successfully installed! You can now run "youtube" from any terminal.',
        'install_fail': 'Installation failed. You might need sudo permissions.',
        'already_installed': 'The "youtube" command is already installed!',
        'back_to_menu': 'Back to main menu',
        'lang_name': 'English',
        'history_title': 'Download History',
        'no_history': 'No download history yet.',
        'bulk_file_prompt': 'Enter the path to your .txt file containing YouTube URLs (one per line).',
        'file_not_found': 'File not found!',
        'confirm_exit': 'Goodbye!',
        'downloading': 'Downloading...',
        'preparing': 'Preparing...',
        'finished': 'Finished',
        'app_up_to_date': 'YouTube Downloader is up to date!',
        'app_update_available': 'New version available: v{}',
        'update_app_prompt': 'Would you like to update the application now?',
        'updating_app': 'Updating script... please wait.',
        'app_updated': 'Application updated successfully!',
        'about_text': f"""
Version: {VERSION} (Pure Python Edition)
Author: Terminal Edition
Powered by: yt_dlp library and ffmpeg

* Features:
  • Download videos in multiple qualities (4K, 1080p, 720p, etc.)
  • Extract audio as MP3
  • Download entire playlists
  • Download history tracking
  • Animated progress bars
  • Beautiful terminal interface
  • Self-managing dependencies

📦 Dependencies:
  • yt-dlp (Python library)
  • rich (Python library)
  • ffmpeg (Optional system binary for merging)

[⚙] Installation:
  The script automatically manages its own Python dependencies!
  Install globally from Settings -> Install to System
  After installation, simply run: youtube

💡 Support:
  https://github.com/yt-dlp/yt-dlp

🎉 Enjoy downloading!
"""
    },
    'ru': {
        'title': 'YouTube Загрузчик',
        'subtitle': f'Терминальная версия v{VERSION}',
        'main_menu': 'Главное меню',
        'download_video': 'Скачать видео',
        'download_audio': 'Скачать только аудио',
        'download_playlist': 'Скачать плейлист',
        'view_history': 'История загрузок',
        'settings': 'Настройки',
        'about': 'О программе',
        'bulk_download': 'Массовая загрузка',
        'exit': 'Выход',
        'select_option': 'Выберите опцию',
        'enter_url': 'Введите URL YouTube',
        'fetching_info': 'Получение информации о видео...',
        'video_info': 'Информация о видео',
        'property': 'Свойство',
        'value': 'Значение',
        'select_quality': 'Выберите качество',
        'best_quality': 'Лучшее качество',
        'start_download': 'Начать загрузку?',
        'saving_to': 'Сохранение в',
        'download_complete': 'Загрузка успешно завершена!',
        'download_failed': 'Ошибка загрузки!',
        'press_enter': 'Нажмите Enter, чтобы продолжить...',
        'no_url': 'URL не указан!',
        'invalid_url': 'Неверный URL YouTube!',
        'download_path': 'Путь загрузки',
        'change_path': 'Изменить путь сохранения',
        'check_updates': 'Проверить обновления библиотек',
        'check_github': 'Проверить обновления приложения (GitHub)',
        'change_lang': 'Сменить язык',
        'install_system': 'Установить в систему (Глобальный псевдоним)',
        'install_success': 'Успешно установлено! Теперь вы можете запускать "youtube" из любого терминала.',
        'install_fail': 'Ошибка установки. Возможно, потребуются права sudo.',
        'already_installed': 'Команда "youtube" уже установлена!',
        'back_to_menu': 'Назад в главное меню',
        'lang_name': 'Русский',
        'history_title': 'История загрузок',
        'no_history': 'История загрузок пуста.',
        'bulk_file_prompt': 'Введите путь к .txt файлу с URL YouTube (один на строку).',
        'file_not_found': 'Файл не найден!',
        'confirm_exit': 'До свидания!',
        'downloading': 'Загрузка...',
        'preparing': 'Подготовка...',
        'finished': 'Завершено',
        'app_up_to_date': 'YouTube Downloader обновлен!',
        'app_update_available': 'Доступна новая версия: v{}',
        'update_app_prompt': 'Хотите обновить приложение сейчас?',
        'updating_app': 'Обновление скрипта... пожалуйста, подождите.',
        'app_updated': 'Приложение успешно обновлено!',
        'about_text': f"""
Версия: {VERSION} (Pure Python Edition)
Автор: Terminal Edition
Работает на: библиотеке yt_dlp и ffmpeg

* Возможности:
  • Скачивание видео в разных качествах (4K, 1080p, 720p и т.д.)
  • Извлечение аудио в формате MP3
  • Скачивание целых плейлистов
  • Отслеживание истории загрузок
  • Анимированные индикаторы выполнения
  • Красивый терминальный интерфейс
  • Самоуправляемые зависимости

📦 Зависимости:
  • yt-dlp (библиотека Python)
  • rich (библиотека Python)
  • ffmpeg (Необязательный системный бинарный файл для слияния)

[⚙] Установка:
  Скрипт автоматически управляет своими зависимостями Python!
  Установите глобально: Настройки -> Установить в систему
  После установки просто запустите: youtube

💡 Поддержка:
  https://github.com/yt-dlp/yt-dlp

🎉 Приятного скачивания!
"""
    }
}

class TerminalYouTubeDownloader:
    def __init__(self):
        self.download_path = str(Path.home() / "Movies/YouTube")
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path, exist_ok=True)
            
        # Setup configuration directory
        self.config_dir = os.path.join(os.path.expanduser("~"), ".ytdl")
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
            
        self.history_file = os.path.join(self.config_dir, "history.json")
        self.config_file = os.path.join(self.config_dir, "config.json")
        
        # Migration from old location
        old_history = os.path.join(os.path.expanduser("~"), ".yt_downloader_history.json")
        old_config = os.path.join(os.path.expanduser("~"), ".yt_downloader_config.json")
        if os.path.exists(old_history) and not os.path.exists(self.history_file):
            shutil.move(old_history, self.history_file)
        if os.path.exists(old_config) and not os.path.exists(self.config_file):
            shutil.move(old_config, self.config_file)
        
        # Dependency check flags
        self.ytdlp_available = False
        self.ytdlp_version = "Unknown"
        self.ffmpeg_available = False
        self.language = 'en'
        
        # Precompile Regex
        self.percent_re = re.compile(r'(\d+\.?\d*)%')
        self.speed_re = re.compile(r'at\s+([\d\.]+\s*[KMGT]?i?B/s)', re.IGNORECASE)
        self.eta_re = re.compile(r'ETA\s+([\d:]+)', re.IGNORECASE)
        
        # Colors for non-rich mode
        self.colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'bold': '\033[1m',
            'reset': '\033[0m'
        }
        
        self.load_config()
        self.check_dependencies()
        
        if RICH_AVAILABLE:
            self.console = Console()
        
    def _t(self, key):
        """Translate a key to the current language"""
        return TRANSLATIONS.get(self.language, TRANSLATIONS['en']).get(key, key)
    
    def print_color(self, text, color='white', bold=False):
        """Print colored text (fallback when rich is not available)"""
        if RICH_AVAILABLE:
            if bold:
                self.console.print(f"[bold {color}]{text}[/bold {color}]")
            else:
                self.console.print(f"[{color}]{text}[/{color}]")
        else:
            style = self.colors.get(color, self.colors['white'])
            if bold:
                style = self.colors['bold'] + style
            print(f"{style}{text}{self.colors['reset']}")
    
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def check_dependencies(self):
        """Check if required tools are installed"""
        self.ytdlp_available = True  # We already checked in ensure_dependencies()
        self.ytdlp_version = yt_dlp.version.__version__
        self.ffmpeg_available = False
        self.ffmpeg_path = "ffmpeg"
        
        # Check system ffmpeg first
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.ffmpeg_available = True
        except Exception:
            pass
            
        # If not found, try static_ffmpeg
        if not self.ffmpeg_available and static_ffmpeg:
            try:
                # This ensures the binary is downloaded/ready
                static_ffmpeg.add_paths()
                self.ffmpeg_available = True
                # The library doesn't expose a simple version string, but we know it's there
            except Exception:
                pass
    
    def load_config(self):
        """Load saved configuration"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.download_path = config.get('download_path', self.download_path)
                    self.language = config.get('language', 'en')
            except:
                pass
    
    def save_config(self):
        """Save configuration"""
        config = {
            'download_path': self.download_path,
            'language': self.language
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except:
            pass
    
    def load_history(self):
        """Load download history"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_to_history(self, url, format_type, quality, title):
        """Save download to history"""
        history = self.load_history()
        history.insert(0, {
            'url': url,
            'title': title,
            'timestamp': datetime.now().isoformat(),
            'format': format_type,
            'quality': quality
        })
        # Keep last 100 downloads
        history = history[:100]
        try:
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
        except:
            pass
    
    def clean_url(self, url, preserve_playlist=False):
        """Clean and validate YouTube URL"""
        url = url.strip()
        
        # Remove timestamp parameters if present
        if '&t=' in url:
            url = url.split('&t=')[0]
        if '?t=' in url:
            url = url.split('?t=')[0]
        
        # Remove other common parameters
        if not preserve_playlist and '&list=' in url:
            url = url.split('&list=')[0]
        
        # Handle youtu.be format
        if 'youtu.be' in url:
            parts = url.split('/')[-1].split('?')
            video_id = parts[0]
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Preserve list if requested
            if preserve_playlist and len(parts) > 1 and 'list=' in parts[1]:
                import urllib.parse
                qs = urllib.parse.parse_qs(parts[1])
                if 'list' in qs:
                    url += f"&list={qs['list'][0]}"
        
        return url
    
    def get_video_info(self, url):
        """Get video information and available formats using yt_dlp library"""
        try:
            # Clean URL first
            url = self.clean_url(url)
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
            }
            
            info_dict = None
            if RICH_AVAILABLE:
                with self.console.status(f"[bold yellow]{self._t('fetching_info')}[/bold yellow]", spinner="dots"):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info_dict = ydl.extract_info(url, download=False)
            else:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=False)
            
            if not info_dict:
                return None
            
            # Format upload date
            upload_date = info_dict.get('upload_date', 'N/A')
            if upload_date != 'N/A' and len(upload_date) == 8:
                try:
                    upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
                except:
                    pass

            # Extract available video formats (resolutions)
            formats = info_dict.get('formats', [])
            available_qualities = {}
            for f in formats:
                h = f.get('height')
                # Filter for useful video formats
                if h and f.get('vcodec') != 'none':
                    tbr = f.get('tbr', 0)
                    # We want the highest bitrate for each specific height
                    if h not in available_qualities or tbr > available_qualities[h]['tbr']:
                        available_qualities[h] = {
                            'height': h,
                            'tbr': tbr,
                            'ext': f.get('ext', 'unknown'),
                            'vcodec': f.get('vcodec', 'unknown'),
                        }
            
            # Sort qualities by resolution height descending
            sorted_qualities = sorted(available_qualities.values(), key=lambda x: x['height'], reverse=True)
            
            info = {
                'title': info_dict.get('title', 'Unknown'),
                'duration': self.format_duration(info_dict.get('duration', 0)),
                'uploader': info_dict.get('uploader', 'Unknown'),
                'upload_date': upload_date,
                'views': f"{info_dict.get('view_count', 0):,}" if info_dict.get('view_count') else "N/A",
                'likes': f"{info_dict.get('like_count', 0):,}" if info_dict.get('like_count') else "N/A",
                'available_qualities': sorted_qualities
            }
            
            return info
        except Exception as e:
            self.print_color(f"⚠ {self._t('fetching_info')} Error: {str(e)}", "yellow")
            return None
    
    def format_duration(self, seconds):
        """Format duration in seconds to readable format"""
        if seconds <= 0:
            return "Unknown"
            
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def show_video_info(self, info):
        """Display video information"""
        if RICH_AVAILABLE:
            table = Table(title=f"[▶] {self._t('video_info')}", box=box.ROUNDED)
            table.add_column(self._t('property'), style="cyan bold")
            table.add_column(self._t('value'), style="white")
            
            table.add_row("Title", info['title'])
            table.add_row("Channel", info['uploader'])
            table.add_row("Duration", info['duration'])
            table.add_row("Upload Date", info['upload_date'])
            table.add_row("Views", info['views'])
            table.add_row("Likes", info['likes'])
            
            self.console.print(table)
        else:
            print("\n" + "="*50)
            print(self._t('video_info'))
            print("="*50)
            print(f"Title: {info['title']}")
            print(f"Channel: {info['uploader']}")
            print(f"Duration: {info['duration']}")
            print(f"Upload Date: {info['upload_date']}")
            print(f"Views: {info['views']}")
            print(f"Likes: {info['likes']}")
            print("="*50)
    
    def download_with_progress(self, url, format_type, quality, audio_format="mp3"):
        """Download with animated progress bar using yt_dlp library"""
        # Clean URL first
        url = self.clean_url(url)
        
        ydl_opts = {
            'format': 'bestaudio/best' if format_type == 'audio' else 
                      ('bestvideo+bestaudio/best' if quality == 'best' else 
                       f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'),
            'outtmpl': os.path.join(self.download_path, '%(title)s.%(ext)s'),
            'merge_output_format': audio_format if format_type == 'audio' else 'mp4',
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
        }

        if format_type == 'audio':
            ydl_opts.update({
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': audio_format,
                    'preferredquality': '192',
                }],
            })

        # Shared progress state
        progress_data = {'percent': 0, 'speed': '0B/s', 'eta': '00:00', 'status': 'preparing'}

        def progress_hook(d):
            if d['status'] == 'downloading':
                progress_data['status'] = 'downloading'
                try:
                    p = d.get('_percent_str', '0%').replace('%', '').strip()
                    progress_data['percent'] = float(p)
                    progress_data['speed'] = d.get('_speed_str', 'N/A')
                    progress_data['eta'] = d.get('_eta_str', 'N/A')
                except:
                    pass
            elif d['status'] == 'finished':
                progress_data['status'] = 'finished'
                progress_data['percent'] = 100

        ydl_opts['progress_hooks'] = [progress_hook]

        try:
            if RICH_AVAILABLE:
                sys.stdout.write('\033[?7l')
                sys.stdout.flush()
                try:
                    with Progress(
                        SpinnerColumn(spinner_name="dots12", style="cyan"),
                        TextColumn("[progress.description]{task.description}"),
                        TextColumn("[cyan]{task.fields[custom_bar]}[/cyan]"),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        console=self.console,
                        transient=True
                    ) as progress:
                        task = progress.add_task(f"[↓] {self._t('downloading')}", total=100, custom_bar="░" * 20)
                        
                        # Run download in a separate thread to keep UI interactive
                        def run_download():
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([url])

                        download_thread = threading.Thread(target=run_download)
                        download_thread.start()
                        
                        while download_thread.is_alive():
                            filled = int(20 * progress_data['percent'] / 100)
                            bar_str = '█' * filled + '░' * (20 - filled)
                            desc = f"[↓] {self._t('downloading')} {progress_data['speed']} • ETA: {progress_data['eta']}"
                            progress.update(task, completed=progress_data['percent'], custom_bar=bar_str, description=desc)
                            time.sleep(0.1)
                            
                        # Final update
                        progress.update(task, completed=100, custom_bar='█' * 20, description=f"✔ {self._t('download_complete')}")
                finally:
                    sys.stdout.write('\033[?7h')
                    sys.stdout.flush()
            else:
                # Fallback non-rich mode
                print(f"\n{self.colors['blue']}[↓] {self._t('downloading')}{self.colors['reset']}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                print(f"\n✔ {self._t('download_complete')}")
            
            return 0 # Success
        except Exception as e:
            self.print_color(f"✖ Error: {str(e)}", "red")
            return 1
    
    def show_header(self):
        """Display animated header"""
        if RICH_AVAILABLE:
            # Create an animated header with gradient effect
            header_text = Text()
            header_text.append(self._t('title').split(' ')[0], style="bold red")
            if ' ' in self._t('title'):
                header_text.append(" " + " ".join(self._t('title').split(' ')[1:]), style="bold white")
            
            subtitle = Text("\n" + self._t('subtitle'), style="dim blue")
            
            layout = Layout()
            layout.split(
                Layout(name="header", size=5),
                Layout(name="body")
            )
            
            header_panel = Panel(
                Align.center(header_text),
                border_style="blue",
                padding=(1, 2)
            )
            
            self.console.print(header_panel)
            self.console.print(Align.center(subtitle))
            self.console.print()
        else:
            title = self._t('title')
            print(f"{self.colors['bold']}{self.colors['red']}{title}{self.colors['reset']}")
            print(f"{self.colors['blue']}{self._t('subtitle')}{self.colors['reset']}")
            print("-" * 50)
    
    def show_menu(self):
        """Display main menu"""
        if RICH_AVAILABLE:
            table = Table(title=self._t('main_menu'), box=box.ROUNDED, border_style="cyan")
            table.add_column(self._t('value').replace('Value', 'Option'), style="cyan bold", no_wrap=True)
            table.add_column(self._t('property').replace('Property', 'Description'), style="white")
            
            table.add_row("1", f"[cyan]↓[/cyan] {self._t('download_video')}")
            table.add_row("2", f"[blue]♪[/blue] {self._t('download_audio')}")
            table.add_row("3", f"[purple]≡[/purple] {self._t('download_playlist')}")
            table.add_row("4", f"[yellow]◷[/yellow] {self._t('view_history')}")
            table.add_row("5", f"[white]⚙[/white] {self._t('settings')}")
            table.add_row("6", f"[blue]ℹ[/blue] {self._t('about')}")
            table.add_row("7", f"[cyan]≣[/cyan] {self._t('bulk_download')}")
            table.add_row("8", f"[red]✖[/red] {self._t('exit')}")
            
            self.console.print(table)
        else:
            print("\n" + "="*50)
            print(self._t('main_menu'))
            print("="*50)
            print(f"1. ↓ {self._t('download_video')}")
            print(f"2. ♪ {self._t('download_audio')}")
            print(f"3. ≡ {self._t('download_playlist')}")
            print(f"4. ◷ {self._t('view_history')}")
            print(f"5. ⚙ {self._t('settings')}")
            print(f"6. ℹ {self._t('about')}")
            print(f"7. ≣ {self._t('bulk_download')}")
            print(f"8. ✖ {self._t('exit')}")
            print("="*50)
    
    def download_video(self, audio_only=False):
        """Download a single video"""
        self.clear_screen()
        self.show_header()
        
        # Get URL
        if RICH_AVAILABLE:
            url = Prompt.ask(f"\n[bold cyan]{self._t('enter_url')}[/bold cyan]")
        else:
            url = input(f"\n{self._t('enter_url')}: ")
        
        if not url:
            self.print_color(f"✖ {self._t('no_url')}", "red")
            time.sleep(2)
            return
        
        # Clean URL
        original_url = url
        url = self.clean_url(url)
        
        # Validate URL
        if not any(domain in url.lower() for domain in ['youtube.com', 'youtu.be']):
            self.print_color("✖ Invalid YouTube URL!", "red")
            time.sleep(2)
            return
        
        # Get video info
        self.print_color(f"★ {self._t('fetching_info')}", "yellow")
        info = self.get_video_info(url)
        
        if info:
            self.show_video_info(info)
        else:
            self.print_color("⚠ Could not fetch video details, but will attempt download...", "yellow")
        
        # Quality selection
        if not audio_only:
            qualities = []
            if info and 'available_qualities' in info:
                # Add "Best Quality" first
                qualities.append((f"★ {self._t('best_quality')}", "best"))
                
                for q in info['available_qualities']:
                    h = q['height']
                    tbr = q['tbr']
                    
                    # Format bitrate nicely
                    if tbr > 1000:
                        bitrate_str = f"{tbr/1000:.1f} Mbps"
                    elif tbr > 0:
                        bitrate_str = f"{int(tbr)} kbps"
                    else:
                        bitrate_str = "N/A"
                        
                    # Add standard resolution names
                    name = f"{h}p"
                    if h == 2160: name = "4K (2160p)"
                    elif h == 1440: name = "2K (1440p)"
                    elif h == 1080: name = "1080p FHD"
                    elif h == 720: name = "720p HD"
                    
                    qualities.append((f"▶ {name} - [dim]{bitrate_str}[/dim]", str(h)))
            else:
                # Fallback to hardcoded list if fetching failed
                qualities = [
                    (f"* {self._t('best_quality')}", "best"),
                    ("▶ 4K (2160p)", "2160"),
                    ("▶ 2K (1440p)", "1440"),
                    ("▶ 1080p", "1080"),
                    ("▶ 720p", "720"),
                    ("▶ 480p", "480"),
                    ("▶ 360p", "360")
                ]
            
            self.print_color(f"\n{self._t('select_quality')}:", "cyan")
            for i, (name, _) in enumerate(qualities, 1):
                print(f"  {i}. {name}")
            
            if RICH_AVAILABLE:
                try:
                    choice = IntPrompt.ask("Your choice", default=1)
                except:
                    choice = 1
            else:
                try:
                    choice = int(input(f"Your choice (1-{len(qualities)}) [1]: ") or "1")
                except:
                    choice = 1
            
            quality = qualities[choice-1][1] if 1 <= choice <= len(qualities) else "best"
        else:
            quality = "best"
            
        audio_format = "mp3"
        
        if audio_only:
            formats = [("MP3", "mp3"), ("M4A", "m4a"), ("FLAC", "flac"), ("WAV", "wav")]
            self.print_color(f"\n{self._t('select_audio_format')}", "cyan")
            for i, (name, _) in enumerate(formats, 1):
                print(f"  {i}. {name}")
                
            if RICH_AVAILABLE:
                try:
                    fmt_choice = IntPrompt.ask("Your choice", default=1)
                except:
                    fmt_choice = 1
            else:
                try:
                    fmt_choice = int(input(f"Your choice (1-{len(formats)}) [1]: ") or "1")
                except:
                    fmt_choice = 1
                    
            audio_format = formats[fmt_choice-1][1] if 1 <= fmt_choice <= len(formats) else "mp3"
        
        # Confirm download
        if RICH_AVAILABLE:
            confirm = Confirm.ask(f"\n[bold green]{self._t('start_download')}[/bold green]", default=True)
        else:
            confirm = (input(f"\n{self._t('start_download')} (y/n): ").lower() or 'y') == 'y'
        
        if not confirm:
            self.print_color(self._t('download_cancelled'), "yellow")
            time.sleep(1)
            return
        
        # Download
        self.print_color(f"\n[>] Saving to: {self.download_path}", "cyan")
        print()
        format_type = "audio" if audio_only else "video"
        
        return_code = self.download_with_progress(url, format_type, quality, audio_format=audio_format)
        
        print()
        if return_code == 0:
            self.print_color(f"✔ {self._t('download_complete')}", "green")
            self.save_to_history(original_url, format_type, quality, info['title'] if info else "Unknown")
        else:
            self.print_color(f"✖ {self._t('download_failed')}", "red")
        
        input(f"\n{self._t('press_enter')}")
    
    def download_playlist(self):
        """Download an entire playlist using yt_dlp library"""
        self.clear_screen()
        self.show_header()
        
        # Get URL
        if RICH_AVAILABLE:
            url = Prompt.ask(f"\n[bold cyan]{self._t('enter_url')}[/bold cyan]")
        else:
            url = input(f"\n{self._t('enter_url')}: ")
        
        if not url:
            self.print_color(f"✖ {self._t('no_url')}", "red")
            time.sleep(2)
            return
        
        # Clean URL
        url = self.clean_url(url, preserve_playlist=True)
        
        # Get playlist info
        self.print_color("★ Fetching playlist information...", "yellow")
        
        try:
            ydl_opts_info = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'nocheckcertificate': True,
            }
            
            playlist_info = None
            if RICH_AVAILABLE:
                with self.console.status(f"[bold yellow]{self._t('fetching_info')}...[/bold yellow]", spinner="dots"):
                    with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                        playlist_info = ydl.extract_info(url, download=False)
            else:
                self.print_color(f"{self._t('fetching_info')}...", "yellow")
                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    playlist_info = ydl.extract_info(url, download=False)
            
            if not playlist_info or 'entries' not in playlist_info:
                self.print_color("✖ Could not fetch playlist details!", "red")
                time.sleep(2)
                return
                
            entries = list(playlist_info['entries'])
            video_count = len(entries)
            
            self.print_color(f"\n[≡] Playlist contains {video_count} videos", "green")
            
            # Confirm download
            if RICH_AVAILABLE:
                confirm = Confirm.ask(f"\n[bold green]Download entire playlist ({video_count} videos)?[/bold green]", default=False)
            else:
                confirm = input(f"\nDownload entire playlist ({video_count} videos)? (y/n): ").lower() == 'y'
            
            if not confirm:
                self.print_color("Download cancelled.", "yellow")
                time.sleep(1)
                return
            
            # Download playlist
            self.print_color(f"\n[>] {self._t('saving_to')}: {self.download_path}", "cyan")
            print()
            
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': os.path.join(self.download_path, '%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'nocheckcertificate': True,
                'quiet': True,
                'no_warnings': True,
                'noplaylist': False,
            }

            # Shared state for progress
            state = {'downloaded_count': 0}

            def progress_hook(d):
                if d['status'] == 'finished':
                    state['downloaded_count'] += 1

            ydl_opts['progress_hooks'] = [progress_hook]

            if RICH_AVAILABLE:
                sys.stdout.write('\033[?7l')
                sys.stdout.flush()
                try:
                    with Progress(
                        SpinnerColumn(spinner_name="dots12", style="cyan"),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(bar_width=20, complete_char="█", incomplete_char="░"),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        console=self.console,
                        transient=True
                    ) as progress:
                        task = progress.add_task("[≡] Downloading playlist...", total=video_count)
                        
                        def run_dl():
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([url])
                        
                        dl_thread = threading.Thread(target=run_dl)
                        dl_thread.start()
                        
                        while dl_thread.is_alive():
                            desc = f"[≡] Downloading: {state['downloaded_count']+1}/{video_count}"
                            progress.update(task, completed=state['downloaded_count'], description=desc)
                            time.sleep(0.5)
                        
                        progress.update(task, completed=video_count, description="✔ Playlist Download Complete")
                finally:
                    sys.stdout.write('\033[?7h')
                    sys.stdout.flush()
            else:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            
            print()
            self.print_color(f"✔ {self._t('download_complete')}", "green")
            
        except Exception as e:
            self.print_color(f"\n✖ {self._t('download_failed')} {str(e)}", "red")
        
        input(f"\n{self._t('press_enter')}")
    
    def show_history(self):
        """Display download history"""
        self.clear_screen()
        self.show_header()
        
        history = self.load_history()
        
        if not history:
            self.print_color(f"[-] {self._t('no_history')}", "yellow")
            time.sleep(2)
            return
        
        if RICH_AVAILABLE:
            table = Table(title=f"[◷] {self._t('history_title')}", box=box.ROUNDED, border_style="cyan")
            table.add_column("#", style="cyan bold", no_wrap=True)
            table.add_column("Title", style="white")
            table.add_column("Format", style="green")
            table.add_column("Quality", style="blue")
            table.add_column("Date", style="dim")
            
            for i, item in enumerate(history[:20], 1):
                title = item.get('title', 'Unknown')[:60]
                if len(item.get('title', '')) > 60:
                    title += "..."
                
                table.add_row(
                    str(i),
                    title,
                    "[♪] Audio" if item.get('format') == 'audio' else "▶ Video",
                    item.get('quality', 'best'),
                    item.get('timestamp', '')[:10]
                )
            
            self.console.print(table)
        else:
            print("\n" + "="*80)
            print(self._t('history_title'))
            print("="*80)
            for i, item in enumerate(history[:20], 1):
                print(f"{i}. {item.get('title', 'Unknown')[:60]}")
                print(f"   Format: {'Audio' if item.get('format') == 'audio' else 'Video'} | Quality: {item.get('quality', 'best')}")
                print(f"   Date: {item.get('timestamp', 'Unknown')[:10]}")
                print("-"*80)
        
        input(f"\n{self._t('press_enter')}")
    
    def show_settings(self):
        """Show and edit settings"""
        self.clear_screen()
        self.show_header()
        
        if RICH_AVAILABLE:
            table = Table(title=f"⚙ {self._t('settings')}", box=box.ROUNDED, border_style="cyan")
            table.add_column(self._t('property'), style="cyan bold")
            table.add_column(self._t('value'), style="white")
            
            table.add_row(self._t('download_path'), self.download_path)
            table.add_row("yt-dlp", "[green]✔ Connected[/green]" if self.ytdlp_available else "[red]✖ Missing[/red]")
            table.add_row("ffmpeg", "[green]✔ Connected[/green]" if self.ffmpeg_available else "[red]✖ Missing[/red]")
            table.add_row(self._t('change_lang'), self._t('lang_name'))
            
            self.console.print(table)
            
            self.print_color(f"\n{self._t('main_menu')}:", "yellow")
            print(f"  1. {self._t('change_path')}")
            print(f"  2. {self._t('check_updates')}")
            print(f"  3. {self._t('check_github')}")
            print(f"  4. {self._t('change_lang')}")
            print(f"  5. {self._t('install_system')}")
            print(f"  6. {self._t('back_to_menu')}")
            
            try:
                choice = IntPrompt.ask(f"\n{self._t('select_option')}", default=6)
            except:
                choice = 6
        else:
            print(f"\n{self._t('download_path')}: {self.download_path}")
            print(f"yt-dlp: ✔ Version {self.ytdlp_version}")
            print(f"ffmpeg: {'✔ Connected' if self.ffmpeg_available else '✖ Missing'}")
            print(f"Language: {self._t('lang_name')}")
            print(f"\n{self._t('main_menu')}:")
            print(f"  1. {self._t('change_path')}")
            print(f"  2. {self._t('check_updates')}")
            print(f"  3. {self._t('check_github')}")
            print(f"  4. {self._t('change_lang')}")
            print(f"  5. {self._t('install_system')}")
            print(f"  6. {self._t('back_to_menu')}")
            try:
                choice = int(input(f"\n{self._t('select_option')} (1-6) [6]: ") or "6")
            except:
                choice = 6
        
        if choice == 1:
            self.print_color(f"\nCurrent path: {self.download_path}", "cyan")
            if RICH_AVAILABLE:
                new_path = Prompt.ask("Enter new download path", default=self.download_path)
            else:
                new_path = input(f"Enter new download path [{self.download_path}]: ") or self.download_path
            
            if new_path:
                if new_path.startswith('~'):
                    new_path = os.path.expanduser(new_path)
                
                if not os.path.exists(new_path):
                    try:
                        os.makedirs(new_path, exist_ok=True)
                    except Exception as e:
                        self.print_color(f"✖ Error creating directory: {e}", "red")
                        time.sleep(2)
                        return
                        
                self.download_path = new_path
                self.save_config()
                self.print_color("✔ Settings saved!", "green")
                time.sleep(1.5)
        elif choice == 2:
            self.check_for_updates()
        elif choice == 3:
            self.check_github_updates()
        elif choice == 4:
            self.print_color(f"\n{self._t('select_language')} / Выберите язык:", "cyan")
            print("  1. English")
            print("  2. Русский")
            
            if RICH_AVAILABLE:
                try:
                    lang_choice = IntPrompt.ask(self._t('select_option'), default=1)
                except:
                    lang_choice = 1
            else:
                try:
                    lang_choice = int(input(f"{self._t('select_option')} (1-2) [1]: ") or "1")
                except:
                    lang_choice = 1
            
            self.language = 'en' if lang_choice == 1 else 'ru'
            self.save_config()
            self.print_color(f"✔ {self._t('lang_name')}!", "green")
            time.sleep(1.5)
        elif choice == 5:
            self.install_to_system()
        elif choice == 6:
            return

    def install_to_system(self):
        """Install the script to the system using a symbolic link"""
        self.clear_screen()
        self.show_header()
        
        script_path = os.path.abspath(__file__)
        dest_path = "/usr/local/bin/youtube"
        
        self.print_color(f"★ {self._t('install_system')}: {dest_path}", "yellow")
        
        try:
            # 1. Make script executable
            os.chmod(script_path, 0o755)
            
            # 2. Handle existing symlink
            if os.path.lexists(dest_path):
                if os.path.islink(dest_path) and os.path.abspath(os.readlink(dest_path)) == script_path:
                    self.print_color(f"\n✔ {self._t('already_installed')}", "green")
                    time.sleep(2)
                    return
                else:
                    # Remove old symlink/file if it exists but points elsewhere
                    try:
                        os.remove(dest_path)
                    except PermissionError:
                        self.print_color(f"\n✖ {self._t('install_fail')}\nTry running manually: sudo ln -sf {script_path} {dest_path}", "red")
                        time.sleep(5)
                        return
            
            # 3. Create symlink
            os.symlink(script_path, dest_path)
            self.print_color(f"\n✔ {self._t('install_success')}", "green")
            
        except PermissionError:
            self.print_color(f"\n✖ {self._t('install_fail')}\nTry running manually: sudo ln -sf {script_path} {dest_path}", "red")
        except Exception as e:
            self.print_color(f"\n✖ Error during installation: {e}", "red")
            
        input(f"\n{self._t('press_enter')}")

    def check_for_updates(self):
        """Check for updates to Python libraries"""
        self.clear_screen()
        self.show_header()
        self.print_color(f"★ {self._t('checking_updates')} (this may take a few seconds)", "yellow")
        
        try:
            # Run pip list --outdated in JSON format
            cmd = [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            outdated = json.loads(result.stdout)
            
            # Map of package name to (current, latest)
            updates = {}
            target_packages = ['yt-dlp', 'rich', 'static-ffmpeg']
            
            for pkg in outdated:
                if pkg['name'].lower() in target_packages:
                    updates[pkg['name'].lower()] = (pkg['version'], pkg['latest_version'])
            
            if not updates:
                self.print_color(f"\n✔ {self._t('up_to_date')}", "green")
                time.sleep(2)
                return
            
            if RICH_AVAILABLE:
                table = Table(title=f"[!] {self._t('updates_available')}", box=box.ROUNDED, border_style="yellow")
                table.add_column("Package", style="cyan bold")
                table.add_column("Current", style="white")
                table.add_column("Latest", style="green bold")
                
                for pkg, (current, latest) in updates.items():
                    table.add_row(pkg, current, latest)
                
                self.console.print(table)
            else:
                print(f"\n{self._t('updates_available')}:")
                for pkg, (current, latest) in updates.items():
                    print(f"  • {pkg}: {current} -> {latest}")
            
            confirm = False
            if RICH_AVAILABLE:
                confirm = Confirm.ask(f"\n{self._t('install_updates_prompt')}", default=True)
            else:
                confirm = (input(f"\n{self._t('install_updates_prompt')} (y/n) [y]: ").lower() or 'y') == 'y'

            if confirm:
                self.apply_updates(list(updates.keys()))
            
        except Exception as e:
            self.print_color(f"\n✖ Error checking for updates: {e}", "red")
            time.sleep(3)

    def apply_updates(self, packages):
        """Upgrade the specified packages"""
        self.print_color(f"\n[>] {self._t('updating_libs')}", "cyan")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + packages)
            self.print_color(f"\n✔ {self._t('updates_installed')}", "green")
            self.print_color(self._t('restarting'), "yellow")
            time.sleep(2)
            os.execv(sys.executable, ['python3'] + sys.argv)
        except Exception as e:
            self.print_color(f"\n✖ Error applying updates: {e}", "red")
            input(f"\n{self._t('press_enter')}")

    def check_github_updates(self):
        """Check for updates of the script itself from GitHub"""
        self.clear_screen()
        self.show_header()
        self.print_color(f"★ {self._t('checking_updates')}...", "yellow")
        
        try:
            url = f"https://raw.githubusercontent.com/{REPO_URL}/main/ytdownloader.py"
            # Use an unverified context by default to resolve macOS certificate issues
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(url, timeout=10, context=context) as response:
                content = response.read().decode('utf-8')
                
            # Find version using regex
            version_match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            
            if version_match:
                remote_version = version_match.group(1)
                
                if remote_version != VERSION:
                    self.print_color(f"\n[!] {self._t('app_update_available').format(remote_version)}", "yellow", bold=True)
                    
                    confirm = False
                    if RICH_AVAILABLE:
                        confirm = Confirm.ask(f"\n{self._t('update_app_prompt')}", default=True)
                    else:
                        confirm = (input(f"\n{self._t('update_app_prompt')} (y/n) [y]: ").lower() or 'y') == 'y'
                        
                    if confirm:
                        self.apply_app_update(content)
                else:
                    self.print_color(f"\n✔ {self._t('app_up_to_date')}", "green")
                    time.sleep(2)
            else:
                self.print_color("\n✖ Could not parse remote version information.", "red")
                time.sleep(2)
                
        except Exception as e:
            self.print_color(f"\n✖ Error checking GitHub: {e}", "red")
            time.sleep(3)

    def apply_app_update(self, content):
        """Apply the update by overwriting the current script"""
        self.print_color(f"\n[>] {self._t('updating_app')}", "cyan")
        try:
            script_path = os.path.abspath(__file__)
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            self.print_color(f"\n✔ {self._t('app_updated')}", "green")
            self.print_color(self._t('restarting'), "yellow")
            time.sleep(2)
            os.execv(sys.executable, ['python3'] + sys.argv)
        except Exception as e:
            self.print_color(f"\n✖ Error applying update: {e}", "red")
            input(f"\n{self._t('press_enter')}")
    
    def show_about(self):
        """Show about information"""
        self.clear_screen()
        self.show_header()
        
        about_text = self._t('about_text')
        
        if RICH_AVAILABLE:
            self.console.print(Panel(about_text, title=self._t('about'), border_style="blue"))
        else:
            print(f"--- {self._t('about')} ---")
            print(about_text)
        
        input(f"\n\n{self._t('press_enter')}")
    
    def download_bulk(self):
        """Batch download from a text file"""
        self.clear_screen()
        self.show_header()
        
        self.print_color(self._t('bulk_file_prompt'), "cyan")
        if RICH_AVAILABLE:
            filepath = Prompt.ask(f"\n[bold cyan]{self._t('property').replace('Property', 'File Path')}[/bold cyan]")
        else:
            filepath = input("\nFile Path: ")
            
        if not filepath or not os.path.exists(filepath):
            self.print_color(f"✖ {self._t('file_not_found')}", "red")
            time.sleep(2)
            return
            
        with open(filepath, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
        if not urls:
            self.print_color("⚠ No URLs found in the file", "yellow")
            time.sleep(2)
            return
            
        self.print_color(f"Found {len(urls)} URLs. Initiating bulk download...", "green")
        
        # Ask for format
        self.print_color("\nDownload Format:", "cyan")
        print("  1. ▶ Video (Best Quality)")
        print("  2. [♪] Audio Only (MP3)")
        
        if RICH_AVAILABLE:
            try:
                choice = IntPrompt.ask("Your choice", default=1)
            except:
                choice = 1
        else:
            try:
                choice = int(input("Your choice (1-2) [1]: ") or "1")
            except:
                choice = 1
                
        audio_only = (choice == 2)
        format_type = "audio" if audio_only else "video"
        
        for i, url in enumerate(urls, 1):
            self.print_color(f"\n=============================================", "cyan")
            self.print_color(f"[{i}/{len(urls)}] Processing: {url}", "blue", bold=True)
            self.download_with_progress(url, format_type, "best", audio_format="mp3")
            
        self.print_color("\n✔ Bulk download operations completed!", "green")
        if RICH_AVAILABLE:
            input("\nPress Enter to continue...")
        else:
            input("\nPress Enter to continue...")

    def run(self):
        """Main application loop"""
        while True:
            self.clear_screen()
            self.show_header()
            self.show_menu()
            
            if RICH_AVAILABLE:
                try:
                    choice = Prompt.ask(f"\n[bold cyan]{self._t('select_option')}[/bold cyan]", choices=["1", "2", "3", "4", "5", "6", "7", "8"], default="1")
                except:
                    choice = "1"
            else:
                choice = input(f"\n{self._t('select_option')} (1-8): ") or "1"
            
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
                sys.exit(0)

def main():
    try:
        app = TerminalYouTubeDownloader()
        app.run()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n✖ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()