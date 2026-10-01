#!/usr/bin/env bash
# Baut die Linux-Einzeldatei im Container und veroeffentlicht sie als GitHub-Release.
# Die Version kommt aus APP_VERSION in SmolSlimeConfiguratorV9.py, der Tag ist v<Version>.
# Der eingebaute Updater findet das Release ueber den Dateinamen SmolSlimeConfigurator-Linux.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=LucyWolf/SmolSlimeConfigurator

VER=$(sed -n 's/^APP_VERSION = "\(.*\)"$/\1/p' SmolSlimeConfiguratorV9.py)
[ -n "$VER" ] || { echo "APP_VERSION nicht gefunden"; exit 1; }
if gh release view "v$VER" --repo "$REPO" >/dev/null 2>&1; then
    echo "v$VER ist schon veröffentlicht – APP_VERSION erhöhen (letzte Stelle zählt bis 99)."
    exit 1
fi
[ -z "$(git status --porcelain)" ] || { echo "Ungespeicherte Änderungen – erst committen."; exit 1; }
git fetch -q origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || { echo "HEAD ist nicht origin/main – erst pushen."; exit 1; }

OUT=$(mktemp -d)
docker run --rm -v "$PWD":/src:ro -v "$OUT":/out python:3.10-bookworm bash -c "
  pip install -q pyinstaller customtkinter pyserial requests 2>/dev/null
  mkdir /w && cp /src/SmolSlimeConfiguratorV9.py /src/icon.png /w/ && cd /w
  pyinstaller -y --log-level ERROR --onefile --windowed --add-data icon.png:. --add-binary /src/bin/nrfutil:. \
      --name SmolSlimeConfigurator-Linux SmolSlimeConfiguratorV9.py
  cp dist/SmolSlimeConfigurator-Linux /out/ && chown $(id -u):$(id -g) /out/*"
cp linux/SmolSlime-installieren.sh linux/SmolSlime-deinstallieren.sh "$OUT/"

PREV=$(git describe --tags --abbrev=0 2>/dev/null || true)
NOTES=$(if [ -n "$PREV" ]; then git log --format='- %s' "$PREV"..HEAD; else echo "Erste Fassung."; fi)
gh release create "v$VER" "$OUT"/* --repo "$REPO" --target main --title "v$VER" --notes "$NOTES"
rm -rf "$OUT"
