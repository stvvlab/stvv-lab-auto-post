#!/usr/bin/env bash
# Japanese text must never be rendered using missing glyphs. Prefer the small
# Ubuntu IPAex package to avoid a 61 MB Noto download on every cache miss.
set -euo pipefail

cache_dir="${STVV_FONT_CACHE_DIR:-${GITHUB_WORKSPACE:-$PWD}/.cache/stvv-fonts}"
cached_noto="$cache_dir/NotoSansCJK-Bold.ttc"
cached_ipa="$cache_dir/ipaexg.ttf"

valid_japanese_font() {
  # A non-empty corrupt file or a Latin-only font is not a valid cache hit.
  python - "$1" <<'PY'
import sys
from PIL import ImageFont
try:
    font = ImageFont.truetype(sys.argv[1], 32)
    first, second = font.getmask('試'), font.getmask('合')
    valid = bool(first.size[0] and first.size[1] and any(bytes(first)))
    valid = valid and (first.size != second.size or bytes(first) != bytes(second))
except (OSError, ValueError):
    valid = False
sys.exit(0 if valid else 1)
PY
}

font_ready() {
  for candidate in \
    "$cached_noto" \
    "$cached_ipa" \
    /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc \
    /usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc \
    /usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf; do
    if [[ ! -s "$candidate" ]] || ! valid_japanese_font "$candidate"; then
      continue
    fi
    mkdir -p "$cache_dir"
    if [[ "$candidate" == *ipaexg.ttf ]]; then
      destination="$cached_ipa"
    else
      destination="$cached_noto"
    fi
    if [[ "$candidate" != "$destination" ]]; then
      cp "$candidate" "$destination"
    fi
    if [[ -n "${GITHUB_ENV:-}" ]]; then
      echo "STVV_CARD_FONT=$destination" >> "$GITHUB_ENV"
    fi
    echo "FONT_READY: $destination"
    return 0
  done
  return 1
}

if font_ready; then
  exit 0
fi

apt_options=(-o Acquire::Retries=0 -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15)
# IPAex Gothic: ~3.3 MB on Ubuntu 24.04 versus ~61 MB for Noto CJK.
# Try the existing index first; refresh only if needed. No font => fail closed.
for attempt in 1 2; do
  if timeout --kill-after=5s 55s sudo apt-get "${apt_options[@]}" install -y --no-install-recommends fonts-ipaexfont-gothic; then
    if font_ready; then
      exit 0
    fi
  fi
  echo "Japanese font installation attempt ${attempt}/2 failed" >&2
  if [[ "$attempt" -eq 1 ]]; then
    timeout --kill-after=5s 35s sudo apt-get "${apt_options[@]}" update -qq || true
  fi
done
echo 'FONT_SETUP_FAILED: Japanese font unavailable; do not render tofu or publish' >&2
exit 1
