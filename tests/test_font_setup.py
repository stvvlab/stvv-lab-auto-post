"""Exercise bounded Japanese font installation offline; never run real apt/sudo."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class FontSetupTests(unittest.TestCase):
    def real_font(self):
        candidates = [
            os.getenv("STVV_CARD_FONT", ""),
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return Path(candidate)
        self.skipTest("No installed Japanese test font")

    def run_installer(self, *, existing=False, cached=False, succeed_on=0):
        source_font = self.real_font()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            font = root / "font.ttf"
            if existing:
                shutil.copyfile(source_font, font)
            cache = root / "cache"
            if cached:
                cache.mkdir()
                shutil.copyfile(source_font, cache / "ipaexg.ttf")
            source = (Path(__file__).resolve().parents[1] /
                      "scripts/install-card-font.sh").read_text()
            for location in ("opentype", "truetype"):
                source = source.replace(
                    f"/usr/share/fonts/{location}/noto/NotoSansCJK-Bold.ttc",
                    str(font))
            source = source.replace(
                "/usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf",
                str(font))
            script = root / "install.sh"
            script.write_text(source)
            (root / "timeout").write_text('#!/bin/bash\nshift 2\nexec "$@"\n')
            (root / "sudo").write_text("""#!/bin/bash
echo "$*" >> "$CALLS"
if [[ "$*" == *" install "* ]]; then
  count=$(cat "$COUNT" 2>/dev/null || echo 0)
  count=$((count + 1))
  echo "$count" > "$COUNT"
  if [[ "$count" == "$SUCCEED_ON" ]]; then
    cp "$REAL_FONT" "$FONT"
    exit 0
  fi
fi
exit 1
""")
            for name in ("timeout", "sudo"):
                (root / name).chmod(0o755)
            env = dict(os.environ, PATH=str(root) + ":" + os.environ["PATH"],
                       CALLS=str(root / "calls"), COUNT=str(root / "count"),
                       FONT=str(font), REAL_FONT=str(source_font),
                       SUCCEED_ON=str(succeed_on), STVV_FONT_CACHE_DIR=str(cache),
                       GITHUB_ENV=str(root / "github-env"))
            result = subprocess.run(["bash", str(script)], env=env,
                                    capture_output=True, text=True, timeout=8)
            calls = (root / "calls").read_text() if (root / "calls").exists() else ""
            if result.returncode == 0:
                cached_fonts = [cache / "ipaexg.ttf", cache / "NotoSansCJK-Bold.ttc"]
                present = [p for p in cached_fonts if p.is_file()]
                self.assertEqual(len(present), 1)
                self.assertEqual(present[0].read_bytes(), source_font.read_bytes())
                self.assertIn("STVV_CARD_FONT=" + str(present[0]),
                              (root / "github-env").read_text())
            return result, calls

    def test_restored_cache_needs_no_apt_or_sudo(self):
        result, calls = self.run_installer(cached=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, "")

    def test_existing_font_needs_no_network(self):
        result, calls = self.run_installer(existing=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, "")

    def test_failed_refresh_and_first_install_can_recover(self):
        result, calls = self.run_installer(succeed_on=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls.count(" install "), 2)
        self.assertIn("Acquire::http::Timeout=15", calls)
        self.assertIn("fonts-ipaexfont-gothic", calls)

    def test_exhausted_attempts_fail_closed(self):
        result, calls = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls.count(" install "), 2)
        self.assertIn("FONT_SETUP_FAILED", result.stderr)
