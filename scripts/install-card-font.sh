#!/usr/bin/env bash
# A stalled Ubuntu mirror must not consume the entire posting job.
set -euo pipefail

cache_dir="${STVV_FONT_CACHE_DIR:-${GITHUB_WORKSPACE:-$PWD}/.cache/stvv-fonts}"
cached_font="$cache_dir/NotoSansCJK-Bold.ttc"

font_ready() {
  for candidate in "$cached_font" \
    /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc \
    /usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc; do
    if [[ -s "$candidate" ]]; then
      mkdir -p "$cache_dir"
      if [[ "$candidate" != "$cached_font" ]]; then
        cp "$candidate" "$cached_font"
      fi
      if [[ -n "${GITHUB_ENV:-}" ]]; then
        echo "STVV_CARD_FONT=$cached_font" >> "$GITHUB_ENV"
      fi
      echo "FONT_READY: $cached_font"
      return 0
    fi
  done
  return 1
}

if font_ready; then
  exit 0
fi

apt_options=(-o Acquire::Retries=0 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20)
# Existing package indexes may still be usable if the refresh times out.
timeout --kill-after=5s 45s sudo apt-get "${apt_options[@]}" update -qq || true
for attempt in 1 2; do
  if timeout --kill-after=5s 90s sudo apt-get "${apt_options[@]}" install -y --no-install-recommends fonts-noto-cjk; then
    if font_ready; then
      exit 0
    fi
  fi
  echo "Japanese font installation attempt ${attempt}/2 did not produce the required font" >&2
done
echo 'FONT_SETUP_FAILED: posting cannot proceed without Japanese font' >&2
exit 1
