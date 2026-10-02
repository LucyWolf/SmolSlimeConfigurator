#!/usr/bin/env bash
# Veroeffentlicht eine neue Fassung: Tag setzen, Release als Entwurf anlegen, dann baut
# GitHub Actions (.github/workflows/release.yml) die Linux- und die Windows-Datei, startet
# beide im Selbsttest und veroeffentlicht das Release erst, wenn alles geklappt hat.
# Die Version kommt aus APP_VERSION in SmolSlimeConfiguratorV9.py, der Tag ist v<Version>.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=LucyWolf/SmolSlimeConfigurator

VER=$(sed -n 's/^APP_VERSION = "\(.*\)"$/\1/p' SmolSlimeConfiguratorV9.py)
[ -n "$VER" ] || { echo "APP_VERSION nicht gefunden"; exit 1; }
if gh release view "v$VER" --repo "$REPO" >/dev/null 2>&1 || git rev-parse -q --verify "refs/tags/v$VER" >/dev/null; then
    echo "v$VER gibt es schon – APP_VERSION erhöhen (letzte Stelle zählt bis 99)."
    exit 1
fi
[ -z "$(git status --porcelain)" ] || { echo "Ungespeicherte Änderungen – erst committen."; exit 1; }
git fetch -q origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || { echo "HEAD ist nicht origin/main – erst pushen."; exit 1; }

PREV=$(git describe --tags --abbrev=0 2>/dev/null || true)
NOTES=$(if [ -n "$PREV" ]; then git log --format='- %s' "$PREV"..HEAD; else echo "Erste Fassung."; fi)

git tag "v$VER"
git push -q origin "v$VER"
gh release create "v$VER" linux/SmolSlimeConfigurator-installieren.sh linux/SmolSlimeConfigurator-arch-installer.desktop linux/SmolSlimeConfigurator-deb-installer.desktop linux/SmolSlimeConfigurator-installer.desktop --repo "$REPO" --draft --verify-tag \
    --title "v$VER" --notes "$NOTES"
gh workflow run release.yml --repo "$REPO" -f tag="v$VER"
sleep 8
RUN=$(gh run list --repo "$REPO" --workflow release.yml --limit 1 --json databaseId -q '.[0].databaseId')
echo "Build läuft: https://github.com/$REPO/actions/runs/$RUN"
gh run watch "$RUN" --repo "$REPO" --exit-status >/dev/null && echo "v$VER veröffentlicht: https://github.com/$REPO/releases/tag/v$VER"
