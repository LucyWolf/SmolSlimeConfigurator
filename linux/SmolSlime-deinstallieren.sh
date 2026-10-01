#!/usr/bin/env bash
# SmolSlime Configurator — Linux Uninstaller
# Die Geraete-Regel bleibt, wenn sie per Abbruch nicht entfernt werden darf.
set -uo pipefail

rm -rf "$HOME/.local/share/smolslime-configurator"
rm -f "$HOME/.local/share/applications/smolslime-configurator.desktop"

if [ -f /etc/udev/rules.d/70-smolslime.rules ]; then
    pkexec /bin/sh -c 'rm -f /etc/udev/rules.d/70-smolslime.rules && udevadm control --reload' || true
fi

if command -v kdialog >/dev/null 2>&1; then
    kdialog --title "SmolSlime Configurator" --msgbox "SmolSlime Configurator wurde entfernt."
else
    echo "SmolSlime Configurator wurde entfernt."
fi
