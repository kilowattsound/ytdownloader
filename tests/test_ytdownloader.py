import io
import json
import os
import ssl
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ytdownloader as ytdl


class FakeConsole:
    """Minimal console stub for testing TerminalYouTubeDownloader without rich."""

    def __init__(self):
        self.messages = []

    def print(self, *args, **kwargs):
        self.messages.append((args, kwargs))

    def clear(self):
        pass


class TestHelpers(unittest.TestCase):
    def test_parse_version_ordering_and_prefixes(self):
        self.assertEqual(ytdl.parse_version("2.3.0"), (2, 3, 0))
        self.assertEqual(ytdl.parse_version("v2.10.1"), (2, 10, 1))
        self.assertTrue(ytdl.parse_version("v2.10.0") > ytdl.parse_version("2.3.0"))
        self.assertFalse(ytdl.parse_version("2.2.5") > ytdl.parse_version("2.3.0"))
        self.assertEqual(ytdl.parse_version("2.3.0rc1"), (2, 3, 0))

    def test_is_valid_youtube_url(self):
        valid = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtube.com/shorts/abc123",
            "https://m.youtube.com/playlist?list=PL12345",
            "https://music.youtube.com/watch?v=abc123",
            "https://youtu.be/dQw4w9WgXcQ",
        ]
        for url in valid:
            with self.subTest(url=url):
                self.assertTrue(ytdl.is_valid_youtube_url(url))

        invalid = [
            "",
            "not a url",
            "ftp://youtube.com/watch?v=abc",
            "https://evil.com/youtube.com/watch?v=abc",
            "https://notyoutube.com/watch?v=abc",
            "https://www.youtube.com/",
        ]
        for url in invalid:
            with self.subTest(url=url):
                self.assertFalse(ytdl.is_valid_youtube_url(url))

    def test_clean_url_query_ordering_and_youtu_be(self):
        # Timestamp before v or list should not wipe out v or list
        self.assertEqual(
            ytdl.clean_url("https://www.youtube.com/watch?t=12&v=abc&list=PL123", preserve_playlist=False),
            "https://www.youtube.com/watch?v=abc",
        )
        self.assertEqual(
            ytdl.clean_url("https://www.youtube.com/watch?t=12&v=abc&list=PL123", preserve_playlist=True),
            "https://www.youtube.com/watch?v=abc&list=PL123",
        )
        self.assertEqual(
            ytdl.clean_url("https://www.youtube.com/watch?list=PL123&v=abc", preserve_playlist=False),
            "https://www.youtube.com/watch?v=abc",
        )
        # youtu.be with trailing slash
        self.assertEqual(
            ytdl.clean_url("https://youtu.be/abc123/?t=45&list=PL123", preserve_playlist=False),
            "https://www.youtube.com/watch?v=abc123",
        )
        self.assertEqual(
            ytdl.clean_url("https://youtu.be/abc123/?t=45&list=PL123", preserve_playlist=True),
            "https://www.youtube.com/watch?v=abc123&list=PL123",
        )

    def test_format_duration_speed_and_eta(self):
        self.assertEqual(ytdl.format_duration(None), "Unknown")
        self.assertEqual(ytdl.format_duration(0), "Unknown")
        self.assertEqual(ytdl.format_duration(-5), "Unknown")
        self.assertEqual(ytdl.format_duration(45.9), "45s")
        self.assertEqual(ytdl.format_duration(125), "2m 5s")
        self.assertEqual(ytdl.format_duration(3661), "1h 1m 1s")

        self.assertEqual(ytdl.format_speed(None), "N/A")
        self.assertEqual(ytdl.format_speed(0), "N/A")
        self.assertEqual(ytdl.format_speed(512), "512 B/s")
        self.assertEqual(ytdl.format_speed(2048), "2.0 KB/s")
        self.assertEqual(ytdl.format_speed(3 * 1024 * 1024), "3.0 MB/s")

        self.assertEqual(ytdl.format_eta(None), "N/A")
        self.assertEqual(ytdl.format_eta(-1), "N/A")
        self.assertEqual(ytdl.format_eta(65), "01:05")
        self.assertEqual(ytdl.format_eta(3665), "1:01:05")

    def test_compute_progress_percent(self):
        self.assertAlmostEqual(
            ytdl.compute_progress_percent({"downloaded_bytes": 50, "total_bytes": 200}),
            25.0,
        )
        self.assertAlmostEqual(
            ytdl.compute_progress_percent({"downloaded_bytes": 150, "total_bytes_estimate": 100}),
            100.0,
        )
        # ANSI color codes in _percent_str
        self.assertAlmostEqual(
            ytdl.compute_progress_percent({"_percent_str": "\x1b[0;94m 42.5%\x1b[0m"}),
            42.5,
        )
        self.assertIsNone(ytdl.compute_progress_percent({"_percent_str": "N/A"}))

    def test_extract_available_qualities_none_safe(self):
        formats = [
            {"height": None, "tbr": 128, "vcodec": "mp4a"},
            {"height": 720, "tbr": None, "vcodec": "avc1"},
            {"height": 720, "tbr": 2500, "vcodec": "avc1"},
            {"height": 1080, "tbr": 4500, "vcodec": "vp9"},
            {"height": 1080, "tbr": 5000, "vcodec": "none"},
        ]
        qualities = ytdl.extract_available_qualities(formats)
        self.assertEqual([q["height"] for q in qualities], [1080, 720])
        self.assertEqual(qualities[1]["tbr"], 2500)

    def test_build_ydl_opts(self):
        vid_opts = ytdl.build_ydl_opts("/tmp/dl", "video", quality="1080", ffmpeg_available=True)
        self.assertNotIn("nocheckcertificate", vid_opts)
        self.assertEqual(vid_opts["merge_output_format"], "mp4")
        self.assertIn("[%(id)s]", vid_opts["outtmpl"])

        no_ff_opts = ytdl.build_ydl_opts("/tmp/dl", "video", quality="720", ffmpeg_available=False)
        self.assertNotIn("merge_output_format", no_ff_opts)
        self.assertEqual(no_ff_opts["format"], "best[height<=720]/best")

        wav_opts = ytdl.build_ydl_opts("/tmp/dl", "audio", audio_format="wav", embed_metadata=True, mutagen_available=True)
        self.assertNotIn("merge_output_format", wav_opts)
        self.assertNotIn("writethumbnail", wav_opts)
        self.assertEqual([p["key"] for p in wav_opts["postprocessors"]], ["FFmpegExtractAudio", "FFmpegMetadata"])

        mp3_opts = ytdl.build_ydl_opts("/tmp/dl", "audio", audio_format="mp3", embed_metadata=True, mutagen_available=True)
        self.assertTrue(mp3_opts["writethumbnail"])
        self.assertEqual(
            [p["key"] for p in mp3_opts["postprocessors"]],
            ["FFmpegExtractAudio", "FFmpegMetadata", "EmbedThumbnail"],
        )

        mp3_no_mutagen = ytdl.build_ydl_opts("/tmp/dl", "audio", audio_format="mp3", embed_metadata=True, mutagen_available=False)
        self.assertNotIn("writethumbnail", mp3_no_mutagen)
        self.assertEqual([p["key"] for p in mp3_no_mutagen["postprocessors"]], ["FFmpegExtractAudio", "FFmpegMetadata"])

        pl_opts = ytdl.build_ydl_opts("/tmp/dl", "video", is_playlist=True)
        self.assertTrue(pl_opts["ignoreerrors"])
        self.assertFalse(pl_opts["noplaylist"])
        self.assertIn("%(playlist)s", pl_opts["outtmpl"])

    def test_normalize_user_path(self):
        self.assertEqual(ytdl.normalize_user_path('  "/tmp/my file.txt"  '), "/tmp/my file.txt")
        self.assertEqual(ytdl.normalize_user_path("'/tmp/my file.txt'"), "/tmp/my file.txt")
        self.assertEqual(ytdl.normalize_user_path(r"/tmp/my\ file.txt"), "/tmp/my file.txt")
        self.assertEqual(ytdl.normalize_user_path("~/urls.txt"), os.path.expanduser("~/urls.txt"))

    def test_translations_parity_and_non_empty(self):
        en_keys = set(ytdl.TRANSLATIONS["en"].keys())
        ru_keys = set(ytdl.TRANSLATIONS["ru"].keys())
        self.assertEqual(en_keys, ru_keys)
        for lang in ("en", "ru"):
            for key, val in ytdl.TRANSLATIONS[lang].items():
                self.assertTrue(isinstance(val, str) and len(val.strip()) > 0, f"Empty {lang}.{key}")

    def test_build_ssl_context_verifies_certs(self):
        ctx = ytdl.build_ssl_context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)


class TestPersistenceAndApp(unittest.TestCase):
    def test_atomic_write_and_utf8_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dl_dir = os.path.join(tmpdir, "downloads")
            cfg_dir = os.path.join(tmpdir, "cfg")
            app = ytdl.TerminalYouTubeDownloader(
                console=FakeConsole(),
                config_dir=cfg_dir,
                download_path=dl_dir,
                check_deps=False,
            )
            app.language = "ru"
            app.embed_metadata = False
            app.save_config()
            app.save_to_history("https://youtu.be/abc", "audio", "best", "Тестовое видео [тег]")

            app2 = ytdl.TerminalYouTubeDownloader(
                console=FakeConsole(),
                config_dir=cfg_dir,
                download_path=dl_dir,
                check_deps=False,
            )
            self.assertEqual(app2.language, "ru")
            self.assertFalse(app2.embed_metadata)
            history = app2.load_history()
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["title"], "Тестовое видео [тег]")

    def test_install_to_system_detects_realpath_no_circular_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dl_dir = os.path.join(tmpdir, "dl")
            cfg_dir = os.path.join(tmpdir, "cfg")
            real_script = os.path.join(tmpdir, "real_yt.py")
            with open(real_script, "w", encoding="utf-8") as handle:
                handle.write("#!/usr/bin/env python3\n")
            link_path = os.path.join(tmpdir, "youtube")
            os.symlink(real_script, link_path)

            app = ytdl.TerminalYouTubeDownloader(
                console=FakeConsole(),
                config_dir=cfg_dir,
                download_path=dl_dir,
                check_deps=False,
            )

            with mock.patch("os.name", "posix"), mock.patch("time.sleep"):
                # Simulating running via symlink path should recognize it's already installed
                app.install_to_system(dest_path=link_path, script_path=link_path)

            self.assertTrue(os.path.islink(link_path))
            self.assertEqual(os.path.realpath(link_path), os.path.realpath(real_script))

    def test_check_github_updates_strict_tls_and_no_downgrade(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = ytdl.TerminalYouTubeDownloader(
                console=FakeConsole(),
                config_dir=os.path.join(tmpdir, "cfg"),
                download_path=os.path.join(tmpdir, "dl"),
                check_deps=False,
            )

            class FakeResponse(io.BytesIO):
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.close()

            contexts_seen = []

            def fake_urlopen(req, timeout=10, context=None):
                contexts_seen.append(context)
                url = req.full_url if hasattr(req, "full_url") else str(req)
                if "api.github.com" in url:
                    return FakeResponse(json.dumps({"tag_name": "v2.0.0"}).encode("utf-8"))
                return FakeResponse(b'#!/usr/bin/env python3\nVERSION = "2.0.0"\n')

            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), mock.patch("time.sleep"):
                app.check_github_updates()

            self.assertTrue(len(contexts_seen) >= 2)
            for ctx in contexts_seen:
                self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
            # Older remote version 2.0.0 must not prompt for update
            printed = " ".join(str(msg[0][0]) for msg in app.console.messages if msg[0])
            self.assertIn("up to date", printed)

    def test_apply_app_update_rejects_invalid_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = ytdl.TerminalYouTubeDownloader(
                console=FakeConsole(),
                config_dir=os.path.join(tmpdir, "cfg"),
                download_path=os.path.join(tmpdir, "dl"),
                check_deps=False,
            )
            with mock.patch.object(app, "_pause"):
                app.apply_app_update("<html>404 Not Found</html>")

            printed = " ".join(str(msg[0][0]) for msg in app.console.messages if msg[0])
            self.assertIn("integrity/syntax", printed)

    def test_cli_version_flag(self):
        script_path = Path(__file__).resolve().parent.parent / "ytdownloader.py"
        result = subprocess.run(
            [sys.executable, str(script_path), "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), f"YouTube Downloader v{ytdl.VERSION}")

    def test_cli_no_update_check_flag(self):
        args = ytdl.parse_cli_args(["--no-update-check"])
        self.assertTrue(args.no_update_check)
        default_args = ytdl.parse_cli_args([])
        self.assertFalse(default_args.no_update_check)

    def test_fetch_module_updates_detects_outdated_and_verifies_ssl(self):
        class FakeResponse(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        contexts_seen = []

        def fake_urlopen(req, timeout=10, context=None):
            contexts_seen.append(context)
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "/yt-dlp/" in url:
                return FakeResponse(json.dumps({"info": {"version": "2099.1.1"}}).encode("utf-8"))
            return FakeResponse(json.dumps({"info": {"version": "1.0.0"}}).encode("utf-8"))

        def fake_version(pkg):
            return {"yt-dlp": "2025.1.1", "rich": "1.0.0", "static-ffmpeg": "1.0.0", "mutagen": "1.0.0"}[pkg]

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), mock.patch(
            "importlib.metadata.version", side_effect=fake_version
        ):
            updates = ytdl.fetch_module_updates(timeout=4, ignore_errors=False)

        self.assertEqual(updates, {"yt-dlp": ("2025.1.1", "2099.1.1")})
        self.assertEqual(len(contexts_seen), len(ytdl.MANAGED_PACKAGES))
        for ctx in contexts_seen:
            self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)

    def test_auto_check_updates_config_and_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_dir = os.path.join(tmpdir, "cfg")
            dl_dir = os.path.join(tmpdir, "dl")
            app = ytdl.TerminalYouTubeDownloader(
                console=FakeConsole(),
                config_dir=cfg_dir,
                download_path=dl_dir,
                check_deps=False,
            )
            self.assertTrue(app.auto_check_updates)
            app.auto_check_updates = False
            app.save_config()

            app2 = ytdl.TerminalYouTubeDownloader(
                console=FakeConsole(),
                config_dir=cfg_dir,
                download_path=dl_dir,
                check_deps=False,
            )
            self.assertFalse(app2.auto_check_updates)

            # Constructor override should not overwrite saved config
            app2.auto_check_updates = True
            app2.save_config()
            app3 = ytdl.TerminalYouTubeDownloader(
                console=FakeConsole(),
                config_dir=cfg_dir,
                download_path=dl_dir,
                check_deps=False,
                auto_check_updates=False,
            )
            self.assertFalse(app3.auto_check_updates)
            with open(app3.config_file, "r", encoding="utf-8") as handle:
                self.assertTrue(json.load(handle)["auto_check_updates"])

    def test_check_startup_updates_applies_app_and_module_updates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = ytdl.TerminalYouTubeDownloader(
                console=FakeConsole(),
                config_dir=os.path.join(tmpdir, "cfg"),
                download_path=os.path.join(tmpdir, "dl"),
                check_deps=False,
            )
            fake_confirm = mock.Mock()
            fake_confirm.ask.side_effect = [True, True]
            new_script = '#!/usr/bin/env python3\nVERSION = "9.9.9"\n'

            with mock.patch.object(ytdl, "Confirm", fake_confirm), mock.patch.object(
                ytdl, "fetch_app_update", return_value=("9.9.9", new_script)
            ), mock.patch.object(
                ytdl, "fetch_module_updates", return_value={"yt-dlp": ("2025.1.1", "2026.1.1")}
            ), mock.patch.object(app, "apply_app_update") as mock_app_upd, mock.patch.object(
                app, "apply_updates"
            ) as mock_mod_upd:
                app.check_startup_updates()

            mock_app_upd.assert_called_once_with(new_script)
            mock_mod_upd.assert_called_once_with(["yt-dlp"])

    def test_check_startup_updates_offline_silent_and_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = ytdl.TerminalYouTubeDownloader(
                console=FakeConsole(),
                config_dir=os.path.join(tmpdir, "cfg"),
                download_path=os.path.join(tmpdir, "dl"),
                check_deps=False,
            )
            with mock.patch.object(
                ytdl, "fetch_app_update", side_effect=OSError("offline")
            ), mock.patch.object(
                ytdl, "fetch_module_updates", side_effect=OSError("offline")
            ):
                app.check_startup_updates()

            self.assertEqual(app.console.messages, [])

            app.auto_check_updates = False
            with mock.patch.object(ytdl, "fetch_app_update") as mock_app, mock.patch.object(
                ytdl, "fetch_module_updates"
            ) as mock_mod:
                app.check_startup_updates()

            mock_app.assert_not_called()
            mock_mod.assert_not_called()


if __name__ == "__main__":
    unittest.main()
