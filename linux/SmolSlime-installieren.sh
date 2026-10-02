#!/usr/bin/env bash
# SmolSlime Configurator — Linux Installer
# Per Doppelklick ausfuehrbar (oder ueber smolslime-*-installer.desktop aus dem Netz geladen).
# Laedt bei Bedarf die neueste Programmdatei, installiert fehlende Pakete
# (udisks2, XWayland), kopiert das Programm nach ~/.local/share,
# legt einen Menueeintrag an und gibt dem angemeldeten Benutzer Zugriff auf
# die seriellen SlimeNRF-Geraete (sonst: "Permission denied: /dev/ttyACM0").
# Ist er schon installiert, fragt das Skript: aktualisieren oder deinstallieren.
set -euo pipefail

TITLE="SmolSlime Configurator"
INSTALL_DIR="$HOME/.local/share/smolslime-configurator"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
RULE_FILE="/etc/udev/rules.d/70-smolslime.rules"
# Ueber die Leitung gestartet (curl | bash) gibt es keinen Skriptordner
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$PWD/x}")" && pwd)"
RELEASE_URL="https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest/download"

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

as_root() {
    if [ "$GUI" != "0" ] && command -v pkexec >/dev/null 2>&1; then
        pkexec /bin/sh -c "$1"
    else
        sudo /bin/sh -c "$1"
    fi
}

uninstall() {
    rm -rf "$INSTALL_DIR"
    rm -f "$DESKTOP_DIR/smolslime-configurator.desktop" "$ICON_DIR/smolslime-configurator.png"
    if [ -f "$RULE_FILE" ]; then
        as_root "rm -f '$RULE_FILE' && udevadm control --reload" || true
    fi
    info "SmolSlime Configurator wurde entfernt.\n\nDeine Einstellungen unter ~/.config/smolslime bleiben erhalten."
    exit 0
}

# Schon installiert? Dann aktualisieren oder deinstallieren
if [ -x "$INSTALL_DIR/SmolSlimeConfigurator" ]; then
    Q="SmolSlime Configurator ist schon installiert."
    case "$GUI" in
        1) set +e; kdialog --title "$TITLE" --yesnocancel "$Q" --yes-label "Aktualisieren" --no-label "Deinstallieren"
           CHOICE=$?; set -e ;;
        2) set +e; OUT=$(zenity --question --title="$TITLE" --text="$Q" --ok-label="Aktualisieren" \
                --cancel-label="Abbrechen" --extra-button="Deinstallieren"); RC=$?; set -e
           if [ "$OUT" = "Deinstallieren" ]; then CHOICE=1; elif [ "$RC" = 0 ]; then CHOICE=0; else CHOICE=2; fi ;;
        *) read -rp "$Q [a]ktualisieren, [d]einstallieren, [x] abbrechen: " A
           case "$A" in a|A) CHOICE=0 ;; d|D) CHOICE=1 ;; *) CHOICE=2 ;; esac ;;
    esac
    case "$CHOICE" in
        0) ;;
        1) uninstall ;;
        *) exit 0 ;;
    esac
fi

# Programmdatei: neben dem Installer, sonst die neueste aus dem Release laden
BIN_SRC=""
[ -n "${SMOLSLIME_FROM_WEB:-}" ] || BIN_SRC="$(ls -t "$SCRIPT_DIR"/SmolSlimeConfigurator*-Linux 2>/dev/null | head -1 || true)"
if [ -z "$BIN_SRC" ]; then
    command -v curl >/dev/null 2>&1 || fail "curl fehlt – damit wird die Programmdatei geladen."
    TMP_BIN="$(mktemp)"
    trap 'rm -f "$TMP_BIN"' EXIT
    case "$GUI" in
        1) kdialog --title "$TITLE" --passivepopup "Lade die neueste Version herunter …" 8 & ;;
        2) zenity --notification --text="SmolSlime Configurator: Lade die neueste Version herunter …" & ;;
        *) echo "Lade die neueste Version herunter …" ;;
    esac
    curl -fL --retry 2 -o "$TMP_BIN" "$RELEASE_URL/SmolSlimeConfigurator-Linux" 2>/dev/null \
        || fail "Download fehlgeschlagen.\nBesteht eine Internetverbindung?"
    BIN_SRC="$TMP_BIN"
fi

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
# Fehlende Pakete gleich mit der Rechte-Abfrage nachinstallieren (ein Passwort fuer alles)
PKGS_ARCH=""; PKGS_DEB=""; PKGS_RPM=""; PKGS_SUSE=""
if ! command -v udisksctl >/dev/null 2>&1; then
    PKGS_ARCH="$PKGS_ARCH udisks2"; PKGS_DEB="$PKGS_DEB udisks2"; PKGS_RPM="$PKGS_RPM udisks2"; PKGS_SUSE="$PKGS_SUSE udisks2"
fi
if [ -n "${WAYLAND_DISPLAY:-}" ] && ! command -v Xwayland >/dev/null 2>&1; then
    PKGS_ARCH="$PKGS_ARCH xorg-xwayland"; PKGS_DEB="$PKGS_DEB xwayland"
    PKGS_RPM="$PKGS_RPM xorg-x11-server-Xwayland"; PKGS_SUSE="$PKGS_SUSE xwayland"
fi
PKG_CMD=""
if [ -n "$PKGS_ARCH" ]; then
    if command -v pacman >/dev/null 2>&1; then PKG_CMD="pacman -S --needed --noconfirm$PKGS_ARCH"
    elif command -v apt-get >/dev/null 2>&1; then PKG_CMD="DEBIAN_FRONTEND=noninteractive apt-get install -y$PKGS_DEB"
    elif command -v dnf >/dev/null 2>&1; then PKG_CMD="dnf install -y$PKGS_RPM"
    elif command -v zypper >/dev/null 2>&1; then PKG_CMD="zypper --non-interactive install$PKGS_SUSE"
    else WARN="$WARN\n- Fehlende Pakete bitte von Hand installieren:$PKGS_ARCH"
    fi
fi
if [ ! -d "/usr/lib/modules/$KVER" ] && [ ! -d "/lib/modules/$KVER" ]; then
    WARN="$WARN\n- Kernel wurde aktualisiert, aber noch nicht neu gestartet. Neue USB-Geraete brauchen evtl. einen Neustart"
fi

# 1) Programm kopieren
mkdir -p "$INSTALL_DIR"
cp -f "$BIN_SRC" "$INSTALL_DIR/SmolSlimeConfigurator"
chmod +x "$INSTALL_DIR/SmolSlimeConfigurator"

# 2) Menueeintrag. StartupWMClass = Fensterklasse der App, damit KDE/GNOME
#    (auch unter Wayland) das Fenster dem Eintrag und seinem Icon zuordnen.
mkdir -p "$DESKTOP_DIR"
ICON=input-gaming
mkdir -p "$ICON_DIR"
if [ -f "$SCRIPT_DIR/icon.png" ]; then
    cp -f "$SCRIPT_DIR/icon.png" "$ICON_DIR/smolslime-configurator.png"
else
    # Das Release enthaelt kein Icon mehr: aus dem Repo holen
    curl -fsSL -o "$ICON_DIR/smolslime-configurator.png" \
        "https://raw.githubusercontent.com/LucyWolf/SmolSlimeConfigurator/main/icon.png" 2>/dev/null \
        || rm -f "$ICON_DIR/smolslime-configurator.png"
fi
[ -f "$ICON_DIR/smolslime-configurator.png" ] && ICON=smolslime-configurator
cat > "$DESKTOP_DIR/smolslime-configurator.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=SmolSlime Configurator
Comment=SlimeNRF-Tracker und Empfaenger einstellen
Exec=$INSTALL_DIR/SmolSlimeConfigurator
Path=$INSTALL_DIR
Icon=$ICON
StartupWMClass=smolslime-configurator
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

if [ -z "$PKG_CMD" ] && [ -f "$RULE_FILE" ] && grep -q 1915 "$RULE_FILE" && { [ -z "$SERIAL_GROUP" ] || id -nG | tr ' ' '\n' | grep -qx "$SERIAL_GROUP"; }; then
    : # schon eingerichtet, kein Passwort noetig
else
    ROOT_CMD="
cat > '$RULE_FILE' << 'RULE'
# SmolSlime / SlimeNRF (pid.codes 1209) — Zugriff fuer angemeldeten Benutzer
SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"1209\", TAG+=\"uaccess\"
SUBSYSTEM==\"hidraw\", ATTRS{idVendor}==\"1209\", TAG+=\"uaccess\"
# Nordic-Bootloader der Holyiot-/eByte-/Nordic-Dongles (Flashen der Dongle-Firmware)
SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"1915\", TAG+=\"uaccess\"
RULE
udevadm control --reload
udevadm trigger --subsystem-match=tty --subsystem-match=hidraw
${SERIAL_GROUP:+usermod -aG $SERIAL_GROUP '$USER'}
${PKG_CMD:+$PKG_CMD || echo 'Pakete nicht installiert' >&2}
"
    as_root "$ROOT_CMD" || fail "Rechte wurden nicht vergeben (Passwort abgebrochen?).\nDas Programm ist installiert, findet den Empfaenger aber nicht."
fi

MSG="Installation abgeschlossen!\n\nStart ueber das Anwendungsmenue: SmolSlime Configurator\n\nFalls der Empfaenger schon steckt: einmal ab- und wieder einstecken."
[ -n "$WARN" ] && MSG="$MSG\n\nHinweise:$WARN"
info "$MSG"
