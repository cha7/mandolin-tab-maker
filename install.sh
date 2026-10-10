#!/bin/sh
# Mandolin Tab Maker installer for Macs with an Apple chip (and Linux). Paste into Terminal:
#
#   curl -fsSL https://raw.githubusercontent.com/cha7/mandolin-tab-maker/main/install.sh | sh
#
# Downloads the app into ~/MandolinTabMaker (MTAB_DIR to change it), installs uv (the
# Python package manager) into your user folder if it's missing, then the Python
# environment, puts a "Mandolin Tab Maker" launcher on the Desktop, and starts the app.
# Running it again updates the app and keeps your tabs (out/) and caches (work/, .venv/).
# Needs no git, Node.js or Python of your own.
set -eu

REPO="cha7/mandolin-tab-maker"
DIR="${MTAB_DIR:-$HOME/MandolinTabMaker}"

say() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nSorry: %s\n' "$1" >&2; exit 1; }

if [ "$(uname -s)" = "Darwin" ] && [ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" != "1" ]; then
  fail "Mandolin Tab Maker needs a Mac with an Apple chip (M1 or newer)."
fi

say "Downloading Mandolin Tab Maker into $DIR"
mkdir -p "$DIR"
curl -fsSL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$DIR" --strip-components=1 \
  || fail "couldn't download the app. Check your internet connection and try again."

UV="$(command -v uv 2>/dev/null || true)"
[ -n "$UV" ] || UV="$HOME/.local/bin/uv"
if [ ! -x "$UV" ]; then
  say "Installing uv (the Python package manager) into your user folder"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh || fail "couldn't install uv."
  UV="$HOME/.local/bin/uv"
fi

say "Installing the music tools (the first time downloads a few GB; this can take 10 to 30 minutes)"
cd "$DIR"
"$UV" sync --no-dev || fail "couldn't install the music tools. Run the same line again to retry."

LAUNCHER="$DIR/Mandolin Tab Maker.command"
cat > "$LAUNCHER" <<EOF
#!/bin/sh
# Starts Mandolin Tab Maker (made by install.sh). Close this window to stop it.
cd "$DIR" || exit 1
exec "$UV" run --no-dev mtab app
EOF
chmod +x "$LAUNCHER"
if [ "$(uname -s)" = "Darwin" ] && [ -d "$HOME/Desktop" ]; then
  # macOS may ask whether Terminal can use your Desktop folder: Allow puts the launcher there.
  cp "$LAUNCHER" "$HOME/Desktop/" 2>/dev/null || true
  NEXT="double-click \"Mandolin Tab Maker\" on your Desktop"
else
  NEXT="run \"$LAUNCHER\""
fi

say "Installed. Next time, $NEXT."
say "Starting Mandolin Tab Maker"
exec "$UV" run --no-dev mtab app
