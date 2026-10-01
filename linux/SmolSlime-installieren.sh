#!/usr/bin/env bash
# SmolSlime Configurator — Linux Installer
# Per Doppelklick ausfuehrbar. Kopiert das Programm nach ~/.local/share,
# legt einen Menueeintrag an und gibt dem angemeldeten Benutzer Zugriff auf
# die seriellen SlimeNRF-Geraete (sonst: "Permission denied: /dev/ttyACM0").
# Erneut ausfuehren = Update auf die neueste ...-Linux-Datei im selben Ordner.
set -euo pipefail

TITLE="SmolSlime Configurator"
INSTALL_DIR="$HOME/.local/share/smolslime-configurator"
DESKTOP_DIR="$HOME/.local/share/applications"
RULE_FILE="/etc/udev/rules.d/70-smolslime.rules"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GUI=0
if command -v kdialog >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    GUI=1
elif command -v zenity >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    GUI=2
fi

info() {
    case "$GUI" in
        1) kdialog --title "$TITLE" --msgbox "$(printf '%b' "$1")" ;;
        2) zenity --info --title="$TITLE" --text="$1" --width=360 ;;
        *) printf '%b\n' "$1" ;;
    esac
}
fail() {
    case "$GUI" in
        1) kdialog --title "$TITLE" --error "$(printf '%b' "$1")" ;;
        2) zenity --error --title="$TITLE" --text="$1" --width=360 ;;
        *) printf 'FEHLER: %b\n' "$1" >&2 ;;
    esac
    exit 1
}

# Neueste Programmdatei neben dem Installer (V9, spaeter V10 …)
BIN_SRC="$(ls -t "$SCRIPT_DIR"/SmolSlimeConfigurator*-Linux 2>/dev/null | head -1 || true)"
[ -n "$BIN_SRC" ] || fail "Keine Datei SmolSlimeConfigurator…-Linux in\n$SCRIPT_DIR gefunden."

# 0) Treiber pruefen. Ohne cdc_acm erscheinen Dongle und Tracker nie als
#    /dev/ttyACM*. Fehlt der Modulordner des laufenden Kernels, wurde der
#    Kernel aktualisiert, aber nicht neu gestartet.
KVER="$(uname -r)"
has_module() { [ -d "/sys/module/$1" ] || modinfo "$1" >/dev/null 2>&1; }

if ! has_module cdc_acm; then
    if [ ! -d "/usr/lib/modules/$KVER" ] && [ ! -d "/lib/modules/$KVER" ]; then
        fail "Die Treiber des laufenden Kernels ($KVER) fehlen.\nDas passiert nach einem Kernel-Update ohne Neustart.\n\nBitte den PC neu starten und den Installer erneut ausfuehren."
    fi
    fail "Der USB-Seriell-Treiber cdc_acm fehlt im Kernel $KVER.\nOhne ihn werden Dongle und Tracker nicht erkannt."
fi

WARN=""
for m in ch341 cp210x; do
    has_module "$m" || WARN="$WARN\n- Treiber $m fehlt (nur fuer ESP-Boards mit diesem USB-Chip noetig)"
done
command -v udisksctl >/dev/null 2>&1 || WARN="$WARN\n- udisksctl fehlt (Paket udisks2), Mehrfach-Flash findet die Laufwerke dann evtl. nicht"
if [ ! -d "/usr/lib/modules/$KVER" ] && [ ! -d "/lib/modules/$KVER" ]; then
    WARN="$WARN\n- Kernel wurde aktualisiert, aber noch nicht neu gestartet. Neue USB-Geraete brauchen evtl. einen Neustart"
fi

# 1) Programm kopieren
mkdir -p "$INSTALL_DIR"
cp -f "$BIN_SRC" "$INSTALL_DIR/SmolSlimeConfigurator"
chmod +x "$INSTALL_DIR/SmolSlimeConfigurator"

# 2) Menueeintrag
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/smolslime-configurator.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=SmolSlime Configurator
Comment=SlimeNRF-Tracker und Empfaenger einstellen
Exec=$INSTALL_DIR/SmolSlimeConfigurator
Path=$INSTALL_DIR
Icon=input-gaming
Terminal=false
Categories=Utility;
DESKTOP
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true

# 3) Geraete-Rechte (einmal Passwort). uaccess wirkt sofort fuer den
#    angemeldeten Benutzer; die Gruppe ist die Rueckfallebene (Arch: uucp,
#    Debian/Ubuntu: dialout) und greift nach dem naechsten Anmelden.
SERIAL_GROUP=""
getent group uucp >/dev/null && SERIAL_GROUP=uucp
getent group dialout >/dev/null && SERIAL_GROUP=dialout

if [ -f "$RULE_FILE" ] && { [ -z "$SERIAL_GROUP" ] || id -nG | tr ' ' '\n' | grep -qx "$SERIAL_GROUP"; }; then
    : # schon eingerichtet, kein Passwort noetig
else
    ROOT_CMD="
cat > '$RULE_FILE' << 'RULE'
# SmolSlime / SlimeNRF (pid.codes 1209) — Zugriff fuer angemeldeten Benutzer
SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"1209\", TAG+=\"uaccess\"
SUBSYSTEM==\"hidraw\", ATTRS{idVendor}==\"1209\", TAG+=\"uaccess\"
RULE
udevadm control --reload
udevadm trigger --subsystem-match=tty --subsystem-match=hidraw
${SERIAL_GROUP:+usermod -aG $SERIAL_GROUP '$USER'}
"
    if [ "$GUI" != "0" ] && command -v pkexec >/dev/null 2>&1; then
        pkexec /bin/sh -c "$ROOT_CMD" || fail "Rechte wurden nicht vergeben (Passwort abgebrochen?).\nDas Programm ist installiert, findet den Empfaenger aber nicht."
    else
        sudo /bin/sh -c "$ROOT_CMD"
    fi
fi

MSG="Installation abgeschlossen!\n\nStart ueber das Anwendungsmenue: SmolSlime Configurator\n\nFalls der Empfaenger schon steckt: einmal ab- und wieder einstecken."
[ -n "$WARN" ] && MSG="$MSG\n\nHinweise:$WARN"
info "$MSG"
