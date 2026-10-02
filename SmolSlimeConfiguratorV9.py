# Import all needed stuff
import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import time
import sys
import os
import shutil
import requests
import subprocess
import platform
import tempfile
import json
import webbrowser
import re
import glob
import hashlib
import binascii
import struct
import urllib.parse
from tkinter import filedialog
import tkinter as tk
import queue
# For safety...
serial_queue = queue.Queue()
ser_lock = threading.Lock()

# Set theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Set variables and start serial
ser = None
connected = False
read_thread = None
stop_read = threading.Event()
custom_fw_path = None

# Version dieser Fassung. Die letzte Stelle zaehlt bis 99 (1.0.9 -> 1.0.10),
# nie rueckwaerts: der Updater vergleicht sie mit dem neuesten GitHub-Release.
APP_VERSION = "1.0.39"
UPDATE_REPO = "LucyWolf/SmolSlimeConfigurator"
UPDATE_ASSET = "SmolSlimeConfigurator-Windows.exe" if sys.platform.startswith("win") else "SmolSlimeConfigurator-Linux"

# OS temp dir
def get_settings_path():
    if sys.platform.startswith("linux"):
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        path = os.path.join(base, "smolslime")
    elif sys.platform.startswith("win"):
        path = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SmolSlime")
    else:
        path = os.path.expanduser("~/Library/Application Support/SmolSlime")

    os.makedirs(path, exist_ok=True)
    return os.path.join(path, "config.json")

SETTINGS_PATH = get_settings_path()


default_settings = {
    "theme": "dark",
    "accent": "slimevr",
    "tooltips": True,
    "favorites": ["Custom (User provided .uf2 / .hex)"],
    "seen_favorite_hint": False,
    "firmware_source": "main", 
    "custom_firmware_repo": "",
    "lang": "en",
}

settings = default_settings.copy()

# Scaling for linux based on DPI
def set_linux_scaling():
    try:
        import subprocess
        dpi = subprocess.check_output(
            ["xrdb", "-query"], stderr=subprocess.DEVNULL
        ).decode()
        for line in dpi.splitlines():
            if "Xft.dpi" in line:
                dpi_value = float(line.split()[-1])
                scale = dpi_value / 96
                ctk.set_widget_scaling(scale)
                ctk.set_window_scaling(scale)
                return
    except Exception:
        pass

    ctk.set_widget_scaling(1.25)
    ctk.set_window_scaling(1.25)

if sys.platform.startswith("linux"):
    set_linux_scaling()


def load_settings():
    global settings
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                settings.update(json.load(f))
        except Exception:
            pass

def save_settings():
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f)

# Farbschema wie das DIY Firmware-Tool (Optik des SlimeVR-Servers): Marineblau,
# Kacheln in Blaugrau, Lila fuer Auswahl und Hauptknoepfe. Wird auf das
# eingebaute dark-blue-Schema gelegt und als Datei neben die Einstellungen geschrieben.
SV_PURPLE = "#7c4dcc"
SV_PURPLE_H = "#6a3fb5"
SV_TEXT = ["#16212e", "#e6edf5"]
SV_BUTTON = ["#c5d1df", "#1d3a57"]
SV_BUTTON_H = ["#b3c2d4", "#264b70"]
SV_BORDER = ["#9fb0c3", "#2a4561"]
SV_FIELD = ["#f4f7fb", "#0b1a2a"]
SLIMEVR_THEME = {
    "CTk": {"fg_color": ["#e9eef5", "#0b1724"]},
    "CTkToplevel": {"fg_color": ["#e9eef5", "#0b1724"]},
    "CTkFrame": {"fg_color": ["#dce4ee", "#0f2133"], "top_fg_color": ["#cfd9e5", "#16304a"], "border_color": SV_BORDER},
    "CTkButton": {"fg_color": SV_BUTTON, "hover_color": SV_BUTTON_H, "border_color": SV_BORDER,
                  "text_color": SV_TEXT, "text_color_disabled": ["gray55", "gray50"]},
    "CTkLabel": {"text_color": SV_TEXT},
    "CTkEntry": {"fg_color": SV_FIELD, "border_color": SV_BORDER, "text_color": SV_TEXT},
    "CTkCheckBox": {"fg_color": SV_PURPLE, "hover_color": SV_PURPLE_H, "border_color": SV_BORDER, "text_color": SV_TEXT},
    "CTkRadioButton": {"fg_color": SV_PURPLE, "hover_color": SV_PURPLE_H, "border_color": SV_BORDER, "text_color": SV_TEXT},
    "CTkSwitch": {"progress_color": SV_PURPLE, "text_color": SV_TEXT},
    "CTkProgressBar": {"fg_color": SV_BUTTON, "progress_color": SV_PURPLE},
    "CTkSlider": {"button_color": SV_PURPLE, "button_hover_color": SV_PURPLE_H},
    "CTkOptionMenu": {"fg_color": SV_BUTTON, "button_color": ["#b3c2d4", "#16304a"],
                      "button_hover_color": ["#a3b4c8", "#264b70"], "text_color": SV_TEXT},
    "CTkComboBox": {"fg_color": SV_FIELD, "border_color": SV_BORDER, "button_color": SV_BORDER, "text_color": SV_TEXT},
    "CTkScrollbar": {"button_color": SV_BORDER, "button_hover_color": ["#8193a8", "#36597d"]},
    "CTkSegmentedButton": {"fg_color": ["#c5d1df", "#16304a"], "selected_color": SV_PURPLE,
                           "selected_hover_color": SV_PURPLE_H, "unselected_color": ["#c5d1df", "#16304a"],
                           "unselected_hover_color": SV_BUTTON_H, "text_color": ["#ffffff", "#e6edf5"]},
    "CTkTextbox": {"fg_color": ["#f4f7fb", "#08131f"], "border_color": SV_BORDER, "text_color": SV_TEXT,
                   "scrollbar_button_color": SV_BORDER, "scrollbar_button_hover_color": ["#8193a8", "#36597d"]},
    "CTkScrollableFrame": {"label_fg_color": ["#cfd9e5", "#16304a"]},
    "DropdownMenu": {"fg_color": ["#e9eef5", "#0f2133"], "hover_color": ["#cfd9e5", "#1d3a57"], "text_color": SV_TEXT},
}

def apply_accent(name):
    if name != "slimevr":
        ctk.set_default_color_theme(name)
        return
    import customtkinter
    base = os.path.join(os.path.dirname(customtkinter.__file__), "assets", "themes", "dark-blue.json")
    with open(base) as f:
        theme = json.load(f)
    for widget, colors in SLIMEVR_THEME.items():
        theme.setdefault(widget, {}).update(colors)
    path = os.path.join(os.path.dirname(SETTINGS_PATH), "theme_slimevr.json")
    with open(path, "w") as f:
        json.dump(theme, f)
    ctk.set_default_color_theme(path)

load_settings()
# Bestehende Installationen bekommen das neue Schema einmal als Standard
if settings.get("theme_version", 0) < 1:
    settings["accent"] = "slimevr"
    settings["theme_version"] = 1
    save_settings()
ctk.set_appearance_mode(settings["theme"])
# Akzentfarbe ist nicht mehr waehlbar: andere Schemata (z.B. "green") faerbten die Auswahlmenues ein
apply_accent("slimevr")

# Sprache der Oberflaeche: Englisch, umstellbar auf Deutsch (wirkt nach Neustart, damit nichts halb umgestellt ist)
LANG = "de" if settings.get("lang") == "de" else "en"

def T(de, en):
    return de if LANG == "de" else en

if sys.platform.startswith("linux"):
    set_linux_scaling()

FIRMWARE_REPOS = {
    "main": "https://api.github.com/repos/Shine-Bright-Meow/SlimeNRF-Firmware-CI/releases/latest",
    "kounocom": "https://api.github.com/repos/kounocom/SlimeNRF-Firmware-CI/releases/latest"
}

# Pull data from latest releases + file browser
def fetch_latest_firmware_assets():
    source = settings.get("firmware_source", "main")

    if source == "custom":
        api_url = settings.get("custom_firmware_repo", "").strip()
        if not api_url:
            append_text("Custom firmware repo is empty.\n", "error")
            return {}
    else:
        api_url = FIRMWARE_REPOS.get(source, FIRMWARE_REPOS["main"])

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        assets = data.get("assets", [])
        fw_dict = {}

        for asset in assets:
            name = asset.get("name", "")
            url = asset.get("browser_download_url", "")
            if name.endswith((".uf2", ".hex")):
                fw_dict[name] = url

        if not fw_dict:
            append_text("No UF2 or HEX found in latest release. check internet and if still issue, post a issue on github, https://icmt.cc\n", "error")

        return fw_dict

    except Exception as e:
        append_text(f"[Error fetching firmware list] {e}\n", "error")
        return {}


# Start base window, size & name
try:
    # className = WM_CLASS; KDE/GNOME ordnen das Fenster damit dem Menueeintrag (Icon) zu
    app = ctk.CTk(className="smolslime-configurator")
except tk.TclError:
    if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"):
        msg = (T("SmolSlime Configurator braucht XWayland (die X11-Ebene von Wayland).\n"
               "Bitte XWayland installieren bzw. in der Sitzung aktivieren.", "SmolSlime Configurator needs XWayland (the X11 layer of Wayland).\nPlease install XWayland"
            " or enable it in your session."))
        print(msg, file=sys.stderr)
        for cmd in (["kdialog", "--error", msg], ["zenity", "--error", f"--text={msg}"], ["notify-send", msg]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd)
                break
        sys.exit(1)
    raise
app.title(f"SmolSlime Configurator v{APP_VERSION}")
app.geometry("1080x640")

# Overdone tooltip overlay
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)
        global TOOLTIPS_ENABLED
        TOOLTIPS_ENABLED = settings.get("tooltips", True)

    def show_tip(self, event=None):
        if not TOOLTIPS_ENABLED or self.tipwindow or not self.text:
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        bg_color = "#333333" if settings["theme"] == "dark" else "#FFFFFF"
        fg_color = "#FFFFFF" if settings["theme"] == "dark" else "#000000"

        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg=bg_color)

        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background=bg_color,
            foreground=fg_color,
            relief=tk.SOLID,
            borderwidth=1,
            font=("tahoma", "8", "normal"),
        )
        label.pack(ipadx=5, ipady=2)

    def hide_tip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


# Sniff them sweet sweet Smol Slimes (Looks for the COM port)
def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    filtered = []
# Filter out all ports except USB
    for port in ports:
        if sys.platform.startswith("linux"):
            if "ttyACM" in port.device or "ttyUSB" in port.device:
                filtered.append(port.device)
        else:
            filtered.append(port.device)

    return filtered

# Refresh the dropdown menu 
def refresh_ports():
    ports = list_serial_ports()
    if ports:
        port_option.configure(values=ports)
        port_option.set(ports[0])
    else:
        port_option.configure(values=[T("Keine Ports gefunden", "No ports found")])
        port_option.set(T("Keine Ports gefunden", "No ports found"))

# Linux sperrt /dev/ttyACM* fuer normale Benutzer (Arch: Gruppe uucp). Statt
# "Permission denied" einmal per Passwortfenster eine udev-Regel setzen, die
# dem angemeldeten Benutzer SlimeNRF-Geraete (USB-Hersteller 1209) freigibt.
UDEV_RULE_PATH = "/etc/udev/rules.d/70-smolslime.rules"

def is_permission_error(e):
    return getattr(e, "errno", None) == 13 or "Permission denied" in str(e)

def fix_serial_permissions(parent=None):
    if not sys.platform.startswith("linux") or not shutil.which("pkexec"):
        return False
    if not ask_yes_no(
        T("Keine Berechtigung", "No permission"),
        T("Linux erlaubt den Zugriff auf den USB-Anschluss nicht.\n\n"
        "Jetzt einmalig einrichten? Danach fragt ein Fenster nach deinem Passwort.", "Linux does not allow access to the USB port.\n\nSet it up once now? A window will then ask"
            " for your password."),
        parent=parent or app,
    ):
        return False
    # 1209 = SlimeNRF-Dongles/-Tracker, 1915 = Nordic-Bootloader der Holyiot-/eByte-/Nordic-Dongles
    rules = ['SUBSYSTEM=="tty", ATTRS{idVendor}=="1209", TAG+="uaccess"',
             'SUBSYSTEM=="tty", ATTRS{idVendor}=="1915", TAG+="uaccess"']
    script = (
        "printf '%s\\n' " + " ".join(f"'{r}'" for r in rules) + f" > {UDEV_RULE_PATH}"
        " && udevadm control --reload"
        " && udevadm trigger --subsystem-match=tty --action=change"
        " && udevadm settle --timeout=5"
    )
    if subprocess.run(["getent", "group", "uucp"], capture_output=True).returncode == 0:
        script += f" ; usermod -aG uucp {os.environ.get('USER', '')}"
    try:
        ok = subprocess.run(["pkexec", "/bin/sh", "-c", script]).returncode == 0
    except Exception:
        ok = False
    append_text(T("USB-Rechte eingerichtet.\n", "USB permissions set up.\n") if ok else T("USB-Rechte nicht eingerichtet.\n", "USB permissions not set up.\n"), "success" if ok else "error")
    return ok

# Mehrere Geraete gleichzeitig: jedes verbundene Geraet (Dongle, Tracker) hat
# eine eigene Verbindung und ein eigenes Terminal, links wird umgeschaltet.
# So kann man Dongle und Tracker koppeln, ohne das Programm zweimal zu oeffnen.
# "ser"/"connected" zeigen immer auf das gewaehlte Geraet, damit send_command
# und das Firmware-Flashen unveraendert weiterarbeiten.
class Device:
    def __init__(self, info):
        self.port = info.device
        self.serial_number = info.serial_number or ""
        self.location = (info.location or "").split(":")[0]
        self.product = info.product or info.description or ""
        self.usb_id = (info.vid, info.pid)
        self.ser = None
        self.stop = threading.Event()
        self.paused = False      # waehrend des Flashens nicht neu verbinden
        self.manual_off = False  # vom Benutzer getrennt
        self.last_error = None
        self.number = 0
        self.console = None
        self.button = None
        self.listeners = []      # bekommen jede empfangene Zeile (z.B. Antwort auf write_config)

    @property
    def key(self):
        return self.serial_number or self.location or self.port

    @property
    def is_dongle(self):
        return bool(self.serial_number) and self.serial_number == settings.get("dongle_serial")

    @property
    def is_receiver(self):
        return self.is_dongle or "receiver" in self.product.lower() or self.usb_id == SLIMENRF_RECEIVER_ID

    @property
    def connected(self):
        return self.ser is not None and self.ser.is_open

    # Nach dem Umflashen (Tracker <-> Dongle) bleibt die Seriennummer gleich, Name und Kennung aendern sich
    def refresh(self, info):
        self.port = info.device
        self.product = info.product or info.description or self.product
        self.usb_id = (info.vid, info.pid)

    def matches(self, info):
        if self.serial_number:
            return info.serial_number == self.serial_number
        return (info.location or "").split(":")[0] == self.location

devices = []
active_device = None

def device_name(dev):
    custom = settings.get("device_names", {}).get(dev.key)
    if custom:
        return custom
    if dev.is_dongle:
        return "📡 Dongle"
    if dev.is_receiver:
        return T("Empfänger", "Receiver")
    return f"Tracker {dev.number}"

def make_console():
    box = ctk.CTkTextbox(console_area, height=220, corner_radius=10)
    box.tag_config("red", foreground="red")
    box.tag_config("green", foreground="lime")
    box.configure(state="disabled")
    return box

def get_or_add_device(info):
    for dev in devices:
        if dev.matches(info):
            dev.refresh(info)
            return dev
    dev = Device(info)
    dev.number = 1 + sum(1 for d in devices if not d.is_receiver)
    dev.console = make_console()
    dev.button = ctk.CTkButton(device_list, text=device_name(dev), width=110,
                               command=lambda d=dev: select_device(d))
    dev.button.bind("<Button-3>", lambda e, d=dev: open_device_menu(d, e))
    ToolTip(dev.button, T("Rechtsklick: trennen, umbenennen, als Dongle festlegen", "Right-click: disconnect, rename, set as dongle"))
    devices.append(dev)
    refresh_sidebar()
    return dev

def refresh_sidebar():
    for dev in devices:
        dev.button.pack_forget()
    for dev in sorted(devices, key=lambda d: not d.is_dongle):
        active = dev is active_device
        dev.button.configure(
            text=device_name(dev),
            fg_color=SV_PURPLE if active else FW_CARD2,
            text_color=("white" if active else ctk.ThemeManager.theme["CTkButton"]["text_color"]) if dev.connected else "gray50",
        )
        dev.button.pack(fill="x", pady=2)

def sync_active():
    global ser, connected
    dev = active_device
    ser = dev.ser if dev and dev.connected else None
    connected = ser is not None
    if dev is None:
        status_label.configure(text=T("Nicht verbunden", "Not connected"), text_color="red")
    elif connected:
        status_label.configure(text=T(f"{device_name(dev)}: verbunden mit {dev.port}", f"{device_name(dev)}: Connected to {dev.port}"), text_color="green")
    else:
        status_label.configure(text=T(f"{device_name(dev)}: getrennt", f"{device_name(dev)}: disconnected"), text_color="orange")

def select_device(dev):
    global active_device, console
    active_device = dev
    console.pack_forget()
    console = dev.console if dev else base_console
    console.pack(fill="both", expand=True)
    if dev and tab_view.get() != TAB_SETTINGS:
        tab_view.set(T("Empfänger", "Receiver") if dev.is_receiver else "Tracker")
    refresh_sidebar()
    sync_active()

def connect_device(dev, ask=True, parent=None, quiet=False):
    dev.last_error = None
    try:
        dev.ser = serial.Serial(dev.port, 115200, timeout=1)
    except serial.SerialException as e:
        dev.ser = None
        dev.last_error = e
        if ask and is_permission_error(e) and fix_serial_permissions(parent):
            return connect_device(dev, ask=False, parent=parent, quiet=quiet)
        if not quiet:
            append_text(T(f"Verbindung fehlgeschlagen: {e}\n", f"Failed to connect: {e}\n"), "error", dev)
        refresh_sidebar()
        sync_active()
        return False
    dev.stop = threading.Event()
    threading.Thread(target=read_serial, args=(dev,), daemon=True).start()
    append_text(T(f"Verbunden mit {dev.port}\n", f"Connected to {dev.port}\n"), "success", dev)
    refresh_sidebar()
    sync_active()
    return True

def disconnect_device(dev):
    dev.stop.set()
    try:
        if dev.ser:
            with ser_lock:
                dev.ser.close()
    except Exception:
        pass
    dev.ser = None

def device_lost(dev, msg):
    if dev.ser is None and dev.stop.is_set():
        return
    disconnect_device(dev)
    if msg:
        append_text(msg, "error", dev)
    refresh_sidebar()
    sync_active()

# "Entfernen" gilt, bis das Geraet abgesteckt wird; sonst kaeme es nach 2 s automatisch zurueck
ignored_keys = set()
perm_state = {"asked": False}

def remove_device(dev):
    ignored_keys.add(dev.key)
    disconnect_device(dev)
    devices.remove(dev)
    dev.button.destroy()
    if dev is active_device:
        select_device(devices[0] if devices else None)
    dev.console.destroy()
    refresh_sidebar()

def open_device_menu(dev, event):
    menu = tk.Menu(app, tearoff=0)
    if dev.connected:
        menu.add_command(label=T("Trennen", "Disconnect"), command=lambda: (setattr(dev, "manual_off", True), device_lost(dev, T("Getrennt.\n", "Disconnected.\n"))))
    else:
        menu.add_command(label=T("Verbinden", "Connect"), command=lambda: (setattr(dev, "manual_off", False), connect_device(dev)))
    if dev.is_dongle:
        menu.add_command(label=T("Dongle-Festlegung aufheben", "Unset as dongle"), command=lambda: set_dongle(None))
    elif dev.serial_number:
        menu.add_command(label=T("Als Dongle festlegen", "Set as dongle"), command=lambda: set_dongle(dev))
    menu.add_command(label=T("Umbenennen…", "Rename…"), command=lambda: rename_device(dev))
    menu.add_separator()
    menu.add_command(label=T("Entfernen", "Remove"), command=lambda: remove_device(dev))
    menu.tk_popup(event.x_root, event.y_root)

def set_dongle(dev):
    settings["dongle_serial"] = dev.serial_number if dev else ""
    save_settings()
    refresh_sidebar()
    sync_active()
    if dev:
        append_text(T("Als Dongle festgelegt. Er verbindet sich ab jetzt von selbst.\n", "Set as dongle. It will now connect automatically.\n"), "success", dev)

def rename_device(dev):
    name = ctk.CTkInputDialog(text=T("Neuer Name (leer = Standard):", "New name (empty = default):"), title=T("Umbenennen", "Rename")).get_input()
    if name is None:
        return
    names = settings.setdefault("device_names", {})
    if name.strip():
        names[dev.key] = name.strip()
    else:
        names.pop(dev.key, None)
    save_settings()
    refresh_sidebar()
    sync_active()

# Getrennte Geraete wieder verbinden (nach Neustart, Flash, Umstecken) und
# den festgelegten Dongle von selbst dazuholen.
def port_key(p):
    return p.serial_number or (p.location or "").split(":")[0] or p.device

def watch_devices():
    try:
        ports = serial.tools.list_ports.comports()
        ignored_keys.intersection_update({port_key(p) for p in ports})  # abgesteckt -> wieder erkennen
        # Neu angesteckte SlimeNRF-Geraete (USB-Hersteller 1209: Dongle und Tracker) selbst
        # aufnehmen und verbinden. Der UF2-Bootloader beim Flashen hat eine andere Kennung.
        for p in ports:
            if p.vid != 0x1209 or port_key(p) in ignored_keys or any(d.matches(p) for d in devices):
                continue
            dev = get_or_add_device(p)
            # Nach den USB-Rechten nur einmal pro Sitzung fragen, nicht bei jedem Einstecken
            ok = connect_device(dev, ask=not perm_state["asked"], quiet=True)
            if not ok and dev.last_error is not None and is_permission_error(dev.last_error):
                perm_state["asked"] = True
                append_text(T(f"{device_name(dev)}: keine Berechtigung für {dev.port}. Über „Geräteverwaltung → Alle angesteckten verbinden“ einrichten.\n", f"{device_name(dev)}: no permission for {dev.port}. Set it up via “Device Manager → Connect"
                    " all plugged in”.\n"),
                            "error", dev)
            if ok and active_device is None:
                select_device(dev)
        dongle = settings.get("dongle_serial")
        if dongle and not any(d.serial_number == dongle for d in devices):
            info = next((p for p in ports if p.serial_number == dongle), None)
            if info:
                dev = get_or_add_device(info)
                if connect_device(dev, ask=False, quiet=True) and active_device is None:
                    select_device(dev)
        for dev in devices:
            if dev.connected or dev.paused or dev.manual_off:
                continue
            info = next((p for p in ports if dev.matches(p)), None)
            if info:
                dev.refresh(info)
                connect_device(dev, ask=False, quiet=True)
    except Exception:
        pass
    app.after(2000, watch_devices)

# Dongle und alle verbundenen Tracker gleichzeitig in den Kopplungsmodus
def pair_all():
    dongle = next((d for d in devices if d.is_dongle and d.connected), None) \
        or next((d for d in devices if d.is_receiver and d.connected), None)
    trackers = [d for d in devices if not d.is_receiver and d.connected]
    if not dongle:
        append_text(T("Kein Dongle verbunden.\n", "No dongle connected.\n"), "error")
        return
    if not trackers:
        append_text(T("Kein Tracker verbunden.\n", "No tracker connected.\n"), "error")
        return
    send_command("pair", dongle)
    for d in trackers:
        send_command("pair", d)
    append_text(T(f"Kopplungsmodus: Dongle + {len(trackers)} Tracker.\n", f"Pairing mode: dongle + {len(trackers)} tracker(s).\n"), "success")

# El button to connect your Smol Slimes to El program
def connect_to_port():
    port = port_option.get()
    if not port or "No ports" in port:
        append_text(T("Kein gültiger Port gewählt.\n", "No valid port selected.\n"), "error")
        return
    info = next((p for p in serial.tools.list_ports.comports() if p.device == port), None)
    if info is None:
        append_text(T(f"{port} ist nicht mehr da.\n", f"{port} is gone.\n"), "error")
        refresh_ports()
        return
    dev = get_or_add_device(info)
    dev.manual_off = False
    if not dev.connected and not connect_device(dev):
        status_label.configure(text=T("Verbindung fehlgeschlagen", "Connection failed"), text_color="red")
    select_device(dev)


# Send commands via serial,
def send_command(cmd, dev=None):
    dev = dev or active_device
    if dev and dev.connected:
        try:
            with ser_lock:
                dev.ser.write((cmd + "\n").encode())
            append_text(f">>> {cmd}\n", None, dev)
        except (serial.SerialException, OSError) as e:
            device_lost(dev, T(f"[Fehler] Senden fehlgeschlagen: {e}\n", f"[Error] Serial write failed: {e}\n"))
    else:
        append_text(T("Nicht verbunden.\n", "Not connected.\n"), "error", dev)

def read_serial(dev):
    s = dev.ser
    while not dev.stop.is_set():
        try:
            if s.in_waiting:
                with ser_lock:
                    line = s.readline().decode(errors="ignore").rstrip('\r\n \t')
                if line:
                    serial_queue.put((dev, line + "\n", None))
            else:
                time.sleep(0.01)
        except Exception as e:
            if not dev.stop.is_set():
                serial_queue.put((dev, None, T(f"Gerät getrennt: {e}\n", f"Device disconnected: {e}\n")))
            break


def disconnect_serial():
    if active_device:
        device_lost(active_device, None)

# Let the code add MORE!! (more lines of serial that is)
def append_text(text, color=None, dev=None):
    box = dev.console if dev and dev.console else console
    box.configure(state="normal")
    tag = None
    if color == "error":
        tag = "red"
    elif color == "success":
        tag = "green"

    at_bottom = box.yview()[1] == 1.0

    if tag:
        box.insert("end", text, tag)
    else:
        box.insert("end", text)

    if at_bottom:
        box.see("end")

    box.update_idletasks()
    box.configure(state="disabled")

# The thing that asks for the custom .U2F
def on_tracker_change(choice):
    global custom_fw_path
    if choice == "Custom…":
        path = filedialog.askopenfilename(title="Select firmware (.uf2 or .hex)", filetypes=[("Firmware files", "*.uf2 *.hex"), (T("UF2-Dateien", "UF2 files"), "*.uf2"), ("HEX files", "*.hex")])
        if path:
            custom_fw_path = path
            send_button.configure(text=f"Flash: {os.path.basename(path)}")
        else:
            tracker_select.set(tracker_names[0])
    else:
        custom_fw_path = None
        send_button.configure(text="Flash Firmware")


# Top UI | Yk the serial buttons
# Kopfzeile wie im DIY Firmware-Tool
header = ctk.CTkFrame(app, fg_color="transparent")
header.pack(fill="x", padx=16, pady=(12, 0))
header_text = ctk.CTkFrame(header, fg_color="transparent")
header_text.pack(side="left")
ctk.CTkLabel(header_text, text="SmolSlime Configurator", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
ctk.CTkLabel(header_text, text=T(f"Tracker und Dongle verbinden, einstellen und flashen · v{APP_VERSION}",
                                       f"Connect, configure and flash trackers and dongles · v{APP_VERSION}"),
             text_color=("gray35", "gray65")).pack(anchor="w")
# Werkzeuge oben rechts; die alte Leiste darunter wird nicht mehr angezeigt
header_buttons = ctk.CTkFrame(header, fg_color="transparent")
header_buttons.pack(side="right", anchor="n", pady=(4, 0))

top_frame = ctk.CTkFrame(app)
# Die alte Leiste (Anschluss, Connect, Firmware) wird nicht mehr gezeigt: Geraete verbinden sich
# selbst, geflasht wird ueber das DIY Firmware-Tool. Die Widgets bleiben, weil aeltere Funktionen
# (connect_to_port, Status, Einzel-Flash) sie noch ansprechen.

initial_ports = list_serial_ports()
if not initial_ports:
    initial_ports = [T("Keine Ports gefunden", "No ports found")]

port_option = ctk.CTkOptionMenu(top_frame, values=initial_ports)
port_option.set(initial_ports[0])
port_option.pack(side="left", padx=5)
ToolTip(port_option, "Select the port for your device")

btn_refresh = ctk.CTkButton(top_frame, text="↻", width=10, command=refresh_ports)
btn_refresh.pack(side="left", padx=5)
ToolTip(btn_refresh, "Refresh serial port")

btn_connect = ctk.CTkButton(top_frame, text=T("Verbinden", "Connect"), command=connect_to_port,
                            fg_color=SV_PURPLE, hover_color=SV_PURPLE_H, text_color="white")
btn_connect.pack(side="left", padx=5)
ToolTip(btn_connect, "Connect to the selected serial port")

progress_bar = ctk.CTkProgressBar(app, width=1000)
progress_bar.set(0)
progress_bar.pack_forget()

firmware_urls = {"Custom (User provided .uf2 / .hex)": None}

# Fill the dropdown menu with latest releases
selected_firmware = tk.StringVar(value="Select Firmware")

current_os = platform.system()
if current_os == "Darwin":
    mac_or_other = "Middle"
else:
    mac_or_other = "Right"
    
def open_firmware_popup(target=None):
    fw_buttons = {}
    global firmware_urls
    popup = ctk.CTkToplevel(app)
    popup.title("Select Firmware")
    popup.geometry("300x400")
    popup.transient(app)
    
    # R-Click Hint (Middle-Click on mac)
    if not settings.get("seen_favorite_hint", False):
        hint_popup = ctk.CTkToplevel(popup)
        hint_popup.title("Tip")
        hint_popup.geometry("260x100")
        hint_popup.transient(popup)

        hint_label = ctk.CTkLabel(
            hint_popup,
            text=f"{mac_or_other} click firmware to star it!\nFavorites appear first and in gold",
            justify="center",
            wraplength=220
        )
        hint_label.pack(expand=True, fill="both", padx=10, pady=10)

        ok_button = ctk.CTkButton(hint_popup, text="Got it!", command=hint_popup.destroy)
        ok_button.pack(pady=(0, 10))

        settings["seen_favorite_hint"] = True
        save_settings()

        hint_popup.wait_visibility()
        hint_popup.grab_set()


    def open_docs():
        webbrowser.open("https://docs.slimevr.dev/smol-slimes/firmware/smol-pre-compiled-firmware.html#-tracker")

    help_button = ctk.CTkButton(
        popup, text="Which Firmware to pick?", command=open_docs,
        fg_color="red", hover_color="#cc0000", text_color="white"
    )
    help_button.pack(padx=10, pady=(10, 5), fill="x")

    # Search bar
    search_var = tk.StringVar()

    search_entry = ctk.CTkEntry(popup, placeholder_text="Search firmware or paste URL...", textvariable=search_var)
    search_entry.pack(padx=10, pady=(0, 5), fill="x")

    scroll_frame = ctk.CTkScrollableFrame(popup, width=280, height=320)
    scroll_frame.pack(padx=10, pady=(0, 10), fill="both", expand=True)
    canvas = scroll_frame._parent_canvas

    def scrollf(event):
        if sys.platform.startswith("linux"):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
        else:
            canvas.yview_scroll(-1 * int(event.delta / 120), "units")

    if sys.platform.startswith("linux"):
        canvas.bind("<Button-4>", scrollf)
        canvas.bind("<Button-5>", scrollf)
    else:
        canvas.bind("<MouseWheel>", scrollf)
# fave ting ting
    def toggle_favorite(fw):
        favs = settings.setdefault("favorites", [])
        is_fav = fw in favs

        if is_fav:
            favs.remove(fw)
        else:
            favs.append(fw)

        save_settings()

        btn = fw_buttons.get(fw)
        if not btn:
            return

        btn.configure(
            text=("☆ " if not is_fav else "") + fw,
            text_color="gold" if not is_fav else ctk.ThemeManager.theme["CTkButton"]["text_color"]
        )

        if not is_fav:
            children = scroll_frame.winfo_children()
            if children and children[0] is not btn:
                btn.pack_forget()
                btn.pack(fill="x", pady=2, before=children[0])

            scroll_frame._parent_canvas.yview_moveto(0)


    def select_fw(fw):
        (target or selected_firmware).set(fw)
        popup.destroy()

    def update_list(*args):
        fw_buttons.clear()

        search_term = search_var.get().lower()
        for widget in scroll_frame.winfo_children():
            widget.destroy()

        favs = settings.get("favorites", [])
        items = list(firmware_urls.keys())
        sorted_items = sorted(items, key=lambda x: (x not in favs, x.lower()))

        for fw in sorted_items:
            if search_term in fw.lower():
                is_fav = fw in favs
                btn = ctk.CTkButton(
                    scroll_frame,
                    text=("☆ " if is_fav else "") + fw,
                    command=lambda f=fw: select_fw(f),
                    text_color="gold" if is_fav else None
                )
                btn.pack(fill="x", pady=2)

                # Right click (or middle click on mac)
                btn.bind("<Button-3>", lambda e, f=fw: toggle_favorite(f))

                fw_buttons[fw] = btn


    def on_paste_url(*args):
        text = search_var.get().strip()
        match = re.search(r'([^/\\]+\.uf2)$', text)
        if match:
            filename = match.group(1)
            search_var.set(filename)
        update_list()

    search_var.trace_add("write", on_paste_url)
    
    def _on_mousewheel(event):
        scroll_frame._parent_canvas.yview_scroll(-1 * (event.delta // 120), "units")

    scroll_frame.bind_all("<MouseWheel>", _on_mousewheel)
    scroll_frame.bind_all("<Button-4>", lambda e: scroll_frame._parent_canvas.yview_scroll(-1, "units"))
    scroll_frame.bind_all("<Button-5>", lambda e: scroll_frame._parent_canvas.yview_scroll(1, "units"))

    update_list()
    popup.after(10, lambda: popup.grab_set())

# Button to open firmware popup
firmware_button = ctk.CTkButton(
    top_frame, textvariable=selected_firmware, command=open_firmware_popup, width=200
)
firmware_button.pack(side="left", padx=5)
ToolTip(firmware_button, "Select the Firmware version for your smolslime")

# Populate firmware menu
def populate_firmware_menu():
    global firmware_urls
    auto_fw = fetch_latest_firmware_assets()
    if auto_fw:
        firmware_urls = {**auto_fw, "Custom (User provided .uf2 / .hex)": None}
    else:
        firmware_urls = {"Custom (User provided .uf2 / .hex)": None}


# populate_firmware_menu lief frueher bei jedem Start fuer die alte Leiste und verbrauchte
# eine der 60 GitHub-API-Abfragen pro Stunde; es laeuft nur noch, wenn man die Quelle in Settings aendert.

# Loading bar
def animate_progress(target, step=0.02, interval=50):
    current = progress_bar.get()
    if current < target:
        progress_bar.set(min(current + step, target))
        app.after(interval, lambda: animate_progress(target, step, interval))
    else:
        if target == 1.0:
            app.after(2000, lambda: progress_bar.pack_forget())

def get_nrfutil_path():
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        return os.path.join(base_path, "nrfutil")
    else:
        return "nrfutil"

# HEX flashing usin command thingy, Shud work gud
def flash_hex_firmware(file_path):
    global ser, connected
    if not ser or not ser.is_open:
        append_text("Device not connected.\n", "error")
        return
    
    append_text("Entering bootloader...\n")
    send_command("dfu")
    time.sleep(2)

    port = ser.port
    flashing_dev = active_device
    if flashing_dev:
        flashing_dev.paused = True
    append_text(f"Starting Flash on port: {port}...\n")
    ser.close()
    ser = None
    connected = False
    nrfutil_cmd = get_nrfutil_path()

    try:
        dfu_package = os.path.splitext(file_path)[0] + "_dfu_package.zip"

        append_text("Generating DFU package...\n")
        subprocess.run([
            nrfutil_cmd, "pkg", "generate",
            "--hw-version", "52",
            "--application-version", "1",
            "--sd-req", "0x00",
            "--application", file_path,
            dfu_package
        ], check=True, shell=False)

        append_text("Flashing DFU package via serial...\n")
        subprocess.run([
            nrfutil_cmd, "dfu", "serial",
            "--package", dfu_package,
            "--port", port,
            "--baud-rate", "115200"
        ], check=True, shell=False)

        append_text("YAY! FW Flashed!!!\n", "success")
        progress_bar.set(1.0)

    except FileNotFoundError:
        append_text("Error 420: run 'pip install nrfutil'.\n", "error")
    except subprocess.CalledProcessError as e:
        append_text(f"Error code: {e}\n", "error")
    finally:
        if flashing_dev:
            flashing_dev.paused = False
        try:
            if os.path.exists(dfu_package):
                os.remove(dfu_package)
        except Exception:
            pass



# Download the firmware once user selected and pressed the Firmware button,
# and also the actual logic for flashing (Resets, puts into DFU, waits for drive to appear, moves the .U2F to the drive)
def download_firmware():
    selection = selected_firmware.get()


    if selection == "Select Firmware":
        append_text("Please select a firmware option.\n", "error")
        return

    

    if selection == "Custom (User provided .uf2 / .hex)":
        file_path = filedialog.askopenfilename(filetypes=[("Firmware files", "*.uf2 *.hex"), (T("UF2-Dateien", "UF2 files"), "*.uf2"), ("HEX files", "*.hex")])
        if not file_path:
            append_text("No custom firmware selected.\n")
            return
        append_text(f"Selected custom firmware: {file_path}\n")
        local_path = file_path
        if local_path.endswith(".hex"):
            append_text("Starting flashing... [HEX]\n", "success")
            flash_hex_firmware(local_path)
            return
    else:
        firmware_url = firmware_urls.get(selection)
        if not firmware_url:
            append_text("No firmware URL for selected firmware.\n")
            return

        local_path = os.path.join(tempfile.gettempdir(), os.path.basename(firmware_url))

        try:
            append_text(f"Downloading firmware from {firmware_url}...\n", "success")
            response = requests.get(firmware_url, stream=True, timeout=20)
            response.raise_for_status()
            with open(local_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)

            append_text(f"Firmware downloaded to: {local_path}\n", "success")
            if local_path.endswith(".hex"):
                append_text("yoo HEX file! Loading...\n", "success")
                flash_hex_firmware(local_path)
                return

        except Exception as e:
            append_text(f"[Error] Firmware download failed: {e}\n", "error")
            return
    progress_bar.pack(pady=(5,5))
    animate_progress(0.2)

    append_text("Clearing Connection data and entering bootloader mode...\n")
    send_command("clear")
    time.sleep(0.5)
    send_command("dfu")
    animate_progress(0.4)

    append_text("Waiting up to 5 seconds for UF2 device to appear. If you have issues, please post an issue https://github.com/ICantMakeThings/SmolSlimeConfigurator \n")
    time.sleep(5)

    mount_point = None
    system = platform.system()
    candidate_paths = []

    try:
        if system == "Windows":
            import win32api
            candidate_paths = win32api.GetLogicalDriveStrings().split('\000')[:-1]

        elif system == "Darwin":
            candidate_paths = [
                os.path.join("/Volumes", d)
                for d in os.listdir("/Volumes")
            ]

        elif system == "Linux":
            mount_roots = [
                "/run/media",
                "/media",
                "/mnt"
            ]

            for media_root in mount_roots:
                if not os.path.isdir(media_root):
                    continue

                for root, dirs, _ in os.walk(media_root):
                    for d in dirs:
                        candidate_paths.append(os.path.join(root, d))

        for path in candidate_paths:
            try:
                if os.path.isfile(os.path.join(path, "INFO_UF2.TXT")):
                    mount_point = path
                    break
            except Exception:
                continue


        if mount_point and os.path.isdir(mount_point):
            dest = os.path.join(mount_point, os.path.basename(local_path))
            append_text(f"Copying firmware to {dest}...\n")
            shutil.copy(local_path, dest)
            append_text(f"DONE: Firmware successfully flashed to {mount_point}\n", "success")
            animate_progress(1.0)
            app.after(2000, lambda: progress_bar.pack_forget())

        else:
            append_text("ERROR: Could not find NICENANO or UF2 boot device. Is the device in DFU/bootloader mode?\n", "error")
        progress_bar.pack_forget()

    except Exception as e:
        append_text(f"[Error flashing] {e}\n", "error")
        append_text("NOTE! On windows [WinError 433] doesn't mean it failed!\n", "success")
        progress_bar.pack_forget()


# Mehrere Tracker auf einmal flashen (nur .uf2). Ablauf: alle verbinden ->
# jedem "dfu" schicken -> warten bis die UF2-Laufwerke da sind -> Datei auf
# jedes kopieren -> pruefen, ob der Tracker danach wieder als Port auftaucht.
# Tracker und Laufwerk gehoeren ueber den USB-Steckplatz (z.B. "1-5.2")
# zusammen; der bleibt beim Wechsel in den Bootloader gleich.
SLIMENRF_RECEIVER_ID = (0x1209, 0x7690)   # USB-Kennung des SlimeNRF-Empfaengers

def list_tracker_ports():
    found = []
    for p in serial.tools.list_ports.comports():
        if sys.platform.startswith("linux") and not ("ttyACM" in p.device or "ttyUSB" in p.device):
            continue
        # Bootloader (UF2/Adafruit 239A, Nordic 1915:521F) sind keine Geraete zum Verbinden; die flasht
        # Schritt 5 direkt ("Im Bootloader"). Sonst oeffnete die App denselben Anschluss doppelt.
        if p.vid == 0x239A or (p.vid, p.pid) == NORDIC_DFU_ID:
            continue
        name = p.product or p.description or ""
        found.append({
            "device": p.device,
            "name": name,
            "location": (p.location or "").split(":")[0],
            "serial": p.serial_number or "",
            "receiver": "receiver" in name.lower() or (p.vid, p.pid) == SLIMENRF_RECEIVER_ID
                        or (bool(p.serial_number) and p.serial_number == settings.get("dongle_serial")),
        })
    return found

def port_label(p):
    return f"{p['device']}  {p['name']}" if p["name"] else p["device"]

def read_mounts():
    mounts = {}
    try:
        with open("/proc/mounts") as f:
            for line in f:
                dev, path = line.split()[:2]
                mounts.setdefault(dev, path.replace("\\040", " "))
    except Exception:
        pass
    return mounts

# Kleine USB-Datentraeger mit ihrem Steckplatz (nur Linux)
def find_usb_drives():
    drives = {}
    mounts = read_mounts()
    for blk in glob.glob("/sys/block/sd*"):
        real = os.path.realpath(blk)
        if "/usb" not in real:
            continue
        try:
            with open(os.path.join(blk, "size")) as f:
                size = int(f.read()) * 512
        except Exception:
            continue
        if size == 0 or size > 256 * 1024 * 1024:
            continue
        locs = re.findall(r"/(\d+-[\d.]+):\d+\.\d+/", real)
        name = os.path.basename(blk)
        devs = ["/dev/" + name] + ["/dev/" + os.path.basename(x) for x in glob.glob(os.path.join(blk, name + "*"))]
        mount = next((mounts[d] for d in devs if d in mounts), None)
        serial_no, vid = "", ""
        up = real
        while up not in ("/", ""):
            if os.path.isfile(os.path.join(up, "idVendor")):
                try:
                    with open(os.path.join(up, "idVendor")) as f:
                        vid = f.read().strip().lower()
                    with open(os.path.join(up, "serial")) as f:
                        serial_no = f.read().strip()
                except Exception:
                    pass
                break
            up = os.path.dirname(up)
        drives[name] = {"devs": devs, "location": locs[-1] if locs else "", "mount": mount, "serial": serial_no,
                        "vid": vid}
    return drives

# Geraete, die schon im UF2-Bootloader stecken (manueller DFU, oder ohne startfaehige Firmware):
# [{"root", "serial", "location"}]. Unter Windows ist die Seriennummer unbekannt.
def bootloader_drives():
    if not sys.platform.startswith("linux"):
        return [{"root": r, "serial": "", "location": ""} for r in uf2_drive_roots()]
    found = []
    for d in find_usb_drives().values():
        root = mount_drive(d)
        if root and os.path.isfile(os.path.join(root, "INFO_UF2.TXT")):
            found.append({"root": root, "serial": d["serial"], "location": d["location"]})
    return found

# Ohne Nachfrage darf udisks nur fuer Programme in der aktiven Desktop-Sitzung einhaengen. Klappt das
# nicht, einmal je Laufwerk mit Passwortfenster nachfragen (nicht bei jedem Abfragen im Sekundentakt).
mount_asked = set()
mount_errors = {}   # Geraetepfad -> letzte Fehlermeldung von udisksctl

def mount_drive(drive):
    if drive["mount"]:
        return drive["mount"]
    for dev in reversed(drive["devs"]):
        res = subprocess.run(["udisksctl", "mount", "-b", dev, "--no-user-interaction"],
                             capture_output=True, text=True, timeout=15)
        mount = read_mounts().get(dev)
        if not mount and "NotAuthorized" in (res.stderr or "") and dev not in mount_asked:
            mount_asked.add(dev)
            res = subprocess.run(["udisksctl", "mount", "-b", dev], capture_output=True, text=True, timeout=90)
            mount = read_mounts().get(dev)
        if mount:
            mount_errors.pop(dev, None)
            return mount
        mount_errors[dev] = (res.stderr or "").strip().splitlines()[-1] if res.stderr else T("unbekannter Fehler", "unknown error")
    return None

# Wurzelpfade aller UF2-Bootloader-Laufwerke. Linux haengt neue kleine
# USB-Datentraeger dafuer ein, Windows prueft nur vorhandene Laufwerksbuchstaben.
def uf2_drive_roots():
    if sys.platform.startswith("win"):
        import ctypes
        import string
        ctypes.windll.kernel32.SetErrorMode(1)  # kein "Kein Datentraeger"-Fenster bei leeren Kartenlesern
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        roots = [f"{c}:\\" for i, c in enumerate(string.ascii_uppercase) if mask & (1 << i)]
    elif sys.platform == "darwin":
        roots = [os.path.join("/Volumes", d) for d in os.listdir("/Volumes")]
    else:
        roots = [m for m in (mount_drive(d) for d in find_usb_drives().values()) if m]
    found = []
    for root in roots:
        try:
            if os.path.isfile(os.path.join(root, "INFO_UF2.TXT")):
                found.append(root)
        except OSError:
            pass
    return found

multi_win = None

# Firmware-Tool im Stil des SlimeVR-Servers: Quelle -> Board -> Version ->
# Bauweise -> Geraete -> Flash-Methode -> Flashen. Board und Bauweise stehen
# im Dateinamen, z.B. SlimeNRF_Tracker_TDMA_NoSleep_SPI_Mag_ProMicro.uf2.
FW_SOURCES = [
    {"id": "main", "name": "SlimeNRF-Firmware-CI", "owner": "Shine-Bright-Meow", "badge": T("Offiziell", "Official"),
     "repo": "Shine-Bright-Meow/SlimeNRF-Firmware-CI"},
    {"id": "kounocom", "name": "SlimeNRF-Firmware-CI", "owner": "kounocom", "badge": T("Drittanbieter", "Third party"),
     "repo": "kounocom/SlimeNRF-Firmware-CI"},
    {"id": "jitingcn", "name": "SlimeVR-Tracker-nRF", "owner": "jitingcn", "badge": T("Drittanbieter", "Third party"),
     "repo": "jitingcn/SlimeVR-Tracker-nRF"},
    {"id": "all", "name": T("Alle Quellen", "All sources"), "owner": T("jeweils neueste", "newest of each"), "badge": T("Alle", "All"), "repo": "*"},
    {"id": "file", "name": T("Eigene Datei", "Own file"), "owner": T(".uf2 vom Rechner", ".uf2 from this computer"), "badge": T("Datei", "File"), "repo": None},
]

FW_OPTION_GROUPS = [
    ("variant", T("Bauform", "Form factor"), ["StackedSmol", "Chrysalis"]),
    ("bus", T("Sensor-Anschluss", "Sensor bus"), ["SPI", "I2C"]),
    ("pins", T("smSPI-Belegung", "smSPI pinout"), ["SmolPins"]),
    ("mag", "Magnetometer", ["Mag"]),
    ("clk", T("Sensor-Takt (CLK_CTL)", "Sensor clock (CLK_CTL)"), ["CLK"]),   # an/aus; NoCLK wird beim Einlesen umgerechnet
    ("sleep", T("Schlafmodus (WOM)", "Sleep mode (WOM)"), [T("Schlafen", "Sleep")]),   # an/aus; NoSleep wird beim Einlesen umgerechnet
    ("sw0", T("Taster an SW0", "Button on SW0"), ["SW0"]),
    ("tdma", T("Funkmodus TDMA", "TDMA radio mode"), ["TDMA"]),
    ("data", T("Datensammlung (CDC)", "Data collection (CDC)"), ["DataCollect"]),
]
FW_OPTION_TOKENS = {t for _, _, toks in FW_OPTION_GROUPS for t in toks}

# Erklaerungen fuer Leute ohne Vorwissen. Grundlage: Kconfig der offiziellen
# Firmware und das Build-Skript der CI (was jede Option beim Bauen umschaltet).
FW_OPTION_HELP = {
    "variant": T("Wie der Tracker um den Controller herum aufgebaut ist. „Stacked Smol“: der Sensor sitzt huckepack "
               "direkt auf dem ProMicro. Chrysalis ist eine fertige Tracker-Platine (SPI, mit Taster). „Normal (Non-Stacked)“: "
               "so heißt es auch in der SlimeVR-Doku – der Sensor sitzt nicht auf dem ProMicro, sondern ist z. B. "
               "mit Kabeln verbunden.", "How the tracker is built around the controller. “Stacked Smol”: the sensor sits piggyback"
        " directly on the ProMicro. Chrysalis is a ready-made tracker board (SPI, with button)."
        " “Normal (Non-Stacked)”: as the SlimeVR docs call it – the sensor does not sit on the"
        " ProMicro but is connected e.g. with wires."),
    "bus": T("Wie der Bewegungssensor mit dem Controller verbunden ist. SPI ist schneller und weniger störanfällig "
           "und wird deshalb empfohlen. I2C braucht weniger Drähte und funktioniert auch. Wichtig: Die Wahl muss "
           "zu deiner Verdrahtung passen, sonst wird der Sensor nicht gefunden.", "How the motion sensor is connected to the controller. SPI is faster and less prone to"
        " interference, so it is recommended. I2C needs fewer wires and works too. Important: the"
        " choice must match your wiring, otherwise the sensor is not found."),
    "pins": T("Nur bei SPI: eine andere Pinbelegung, bei der CS an P0.24 und INT an P1.00 liegen. Nur wählen, "
            "wenn dein Schaltplan das so vorgibt – sonst bleibt der Haken aus.", "SPI only: a different pinout with CS on P0.24 and INT on P1.00. Only select it if your"
        " schematic says so – otherwise leave it unchecked."),
    "mag": T("Ein Magnetometer ist ein Kompass-Sensor. Er verhindert, dass sich die Drehung des Trackers mit der Zeit "
           "langsam verschiebt (Drift). Nur einschalten, wenn wirklich einer verbaut ist. In der Nähe von Metall, "
           "Magneten oder Lautsprechern kann er stören.", "A magnetometer is a compass sensor. It keeps the tracker's rotation from slowly shifting"
        " over time (drift). Only enable it if one is actually fitted. Near metal, magnets or"
        " speakers it can cause trouble."),
    "clk": T("Leitung, über die der Controller den Takt des Sensors steuert. Im Schaltplan der SlimeVR-Doku heißt "
           "sie CLK_CTL – beim Stacked Smol Pin 111 (P1.11), beim normalen ProMicro laut Firmware P0.20. Nur "
           "einschalten, wenn diese Leitung verlötet ist. Nicht verwechseln mit INT: das ist die Interrupt-Leitung, "
           "die immer verlötet sein muss.", "Line through which the controller drives the sensor's clock. In the SlimeVR docs schematic"
        " it is called CLK_CTL – on the Stacked Smol pin 111 (P1.11), on the normal ProMicro P0.20"
        " according to the firmware. Only enable it if this line is soldered. Not to be confused"
        " with INT: that is the interrupt line, which must always be soldered."),
    "sleep": T("An (empfohlen): Liegt der Tracker still, legt er sich schlafen und wacht bei Bewegung von selbst "
             "wieder auf (WOM = Wake on Motion). Das spart viel Akku. Aus: Der Tracker bleibt immer wach und "
             "reagiert sofort, aber der Akku hält deutlich kürzer. Aus nur, wenn dein Sensor das Aufwecken durch "
             "Bewegung nicht kann.", "On (recommended): when the tracker lies still it goes to sleep and wakes up by itself on"
        " movement (WOM = Wake on Motion). This saves a lot of battery. Off: the tracker always"
        " stays awake and reacts instantly, but the battery lasts much shorter. Only off if your"
        " sensor cannot wake on motion."),
    "sw0": T("Nur für einen Taster (drücken, federt zurück) zwischen Pin P1.00 und GND. Damit kannst du koppeln "
           "(5 Sekunden halten), ausschalten und aufwecken. Ein Ein/Aus-Schiebeschalter zwischen Akku und Board "
           "ist kein SW0 – dafür nicht anhaken. Ein Taster am RST-Pin funktioniert auch ohne diese Option. "
           "Beim Stacked Smol (P0.06) und beim Chrysalis ist der Taster fest eingebaut und immer an.", "Only for a push button (press, springs back) between pin P1.00 and GND. It lets you pair"
        " (hold 5 seconds), power off and wake up. An on/off slide switch between battery and board"
        " is not SW0 – do not check it for that. A button on the RST pin works without this option"
        " too. On the Stacked Smol (P0.06) and the Chrysalis the button is built in and always on."),
    "tdma": T("Neuerer Funkmodus mit festen Zeitfenstern pro Tracker – kann bei vielen Trackern stabiler sein. "
            "Achtung: Der Dongle braucht dann ebenfalls TDMA-Firmware, sonst verbinden sie sich nicht.", "Newer radio mode with fixed time slots per tracker – can be more stable with many"
        " trackers. Note: the dongle then needs TDMA firmware too, otherwise they will not connect."),
    "data": T("Gibt zusätzlich Rohdaten über USB aus. Nur für Fehlersuche oder Entwicklung.", "Additionally outputs raw data over USB. Only for debugging or development."),
}

FW_CHOICE_LABELS = {
    "bus": {"SPI": T("SPI (empfohlen)", "SPI (recommended)"), "I2C": "I2C"},
    "variant": {"StackedSmol": "Stacked Smol", None: "Normal (Non-Stacked)"},
}

# Laufzeit-Einstellungen der offiziellen Firmware (write_config <name> <wert>).
# (name, Beschriftung, Art, Standard in Anzeige-Einheit, Einheit, Faktor zur Firmware-Einheit, Erklaerung)
FW_SETTINGS = [
    ("Sensor", [
        ("sensor_use_mag", T("Magnetometer benutzen", "Use magnetometer"), "bool", True, "", 1,
         T("Schaltet den Kompass-Sensor ein oder aus, falls einer verbaut ist.", "Turns the compass sensor on or off, if one is fitted.")),
        ("use_sensor_clock", T("Sensor-Takt (CLK_CTL) benutzen", "Use sensor clock (CLK_CTL)"), "bool", True, "", 1,
         T("Nutzt die Takt-Leitung CLK_CTL zum Sensor, falls sie verlötet ist.", "Uses the CLK_CTL clock line to the sensor, if it is soldered.")),
        ("sensor_use_6_side_calibration", T("6-Seiten-Kalibrierung", "6-side calibration"), "bool", True, "", 1,
         T("Genauere Kalibrierung des Beschleunigungssensors. Wird in der Konsole mit „6-side“ durchgeführt.", "More accurate accelerometer calibration. Run it in the console with “6-side”.")),
        ("sensor_accel_odr", T("Messrate Beschleunigung", "Accelerometer rate"), "int", 100, "Hz", 1,
         T("Wie oft pro Sekunde gemessen wird. Höher = genauer, aber mehr Rechenzeit und Stromverbrauch.", "How many times per second it measures. Higher = more accurate, but more processing and"
             " power use.")),
        ("sensor_gyro_odr", T("Messrate Gyroskop", "Gyroscope rate"), "int", 200, "Hz", 1,
         T("Wie oft pro Sekunde die Drehung gemessen wird. Bei rauschenden Sensoren (BMI270, LSM6DS3TR-C) "
         "ist ein niedrigerer Wert besser.", "How many times per second rotation is measured. For noisy sensors (BMI270, LSM6DS3TR-C) a"
             " lower value is better.")),
        ("sensor_accel_fs", T("Messbereich Beschleunigung", "Accelerometer range"), "int", 4, "g", 1,
         T("Kleiner = feiner und rauschärmer, aber schnelle Bewegungen können „überlaufen“.", "Smaller = finer and less noisy, but fast movements can “overflow”.")),
        ("sensor_gyro_fs", T("Messbereich Gyroskop", "Gyroscope range"), "int", 1000, "°/s", 1,
         T("Kleiner = feiner, aber sehr schnelle Drehungen können „überlaufen“.", "Smaller = finer, but very fast rotations can “overflow”.")),
    ]),
    (T("Energie und Schlaf", "Power and sleep"), [
        ("use_imu_timeout", T("Bei Stillstand schlafen", "Sleep when still"), "bool", True, "", 1,
         T("Liegt der Tracker still, geht der Sensor in einen Schlafzustand. Spart viel Akku.", "When the tracker lies still, the sensor goes to sleep. Saves a lot of battery.")),
        ("imu_timeout_ramp_min", T("Schlafen frühestens nach", "Sleep at the earliest after"), "int", 5, "s", 1000,
         T("So lange muss der Tracker mindestens stillliegen, bevor er schläft.", "How long the tracker must lie still at least before it sleeps.")),
        ("imu_timeout_ramp_max", T("Schlafen spätestens nach", "Sleep at the latest after"), "int", 15, "s", 1000,
         T("Längste Wartezeit bei Stillstand, bevor er schläft.", "Longest wait while still before it sleeps.")),
        ("use_imu_wake_up", T("Aufwecken durch Bewegung", "Wake on motion"), "bool", True, "", 1,
         T("Der Sensor weckt den Tracker auf, sobald er bewegt wird.", "The sensor wakes the tracker as soon as it is moved.")),
        ("sensor_lp_timeout", T("Stromsparmodus nach", "Low-power mode after"), "int", 500, "ms", 1,
         T("Nach so vielen Millisekunden ohne Bewegung misst der Sensor sparsamer.", "After this many milliseconds without movement the sensor measures more sparingly.")),
        ("sensor_use_low_power_2", T("Zusätzliche Sparmodi", "Extra power saving"), "bool", False, "", 1,
         T("Noch sparsamer bei Stillstand, reagiert dafür minimal verzögert.", "Even more frugal when still, but reacts with a tiny delay.")),
        ("delay_sleep_on_status", T("Nicht schlafen bei Statusmeldung", "Stay awake on status message"), "bool", True, "", 1,
         T("Verschiebt den Schlaf, solange eine Meldung anliegt oder gekoppelt wird.", "Delays sleep while a status is shown or pairing is in progress.")),
    ]),
    (T("Zeitlimit bei Nichtbenutzung", "Inactivity timeout"), [
        ("use_active_timeout", T("Zeitlimit benutzen", "Use timeout"), "bool", True, "", 1,
         T("Liegt der Tracker lange Zeit unbewegt herum (z. B. vergessen), legt er sich nach dem Zeitlimit "
         "schlafen oder schaltet sich ganz aus.", "If the tracker lies unmoved for a long time (e.g. forgotten), it goes to sleep or powers"
             " off completely after the timeout.")),
        ("active_timeout_mode", T("Danach", "Then"), "enum", 0, "", {0: T("Schlafen", "Sleep"), 1: T("Ausschalten", "Power off")},
         T("Schlafen: wacht bei Bewegung wieder auf (braucht „Aufwecken durch Bewegung“). Ausschalten: muss "
         "per Taster wieder eingeschaltet werden (braucht „Ausschalten per Taster“).", "Sleep: wakes up again on movement (needs “Wake on motion”). Power off: must be switched on"
             " again with the button (needs “Power off by button”).")),
        ("active_timeout_delay", T("Zeitlimit", "Timeout"), "int", 15, "min", 60000,
         T("Nach so vielen Minuten ohne Bewegung greift das Zeitlimit.", "The timeout applies after this many minutes without movement.")),
        ("active_timeout_threshold", T("Schwelle", "Threshold"), "int", 15, "s", 1000,
         T("Nach so vielen Sekunden Stillstand beginnt das Zeitlimit zu zählen.", "The timeout starts counting after this many seconds of standstill.")),
    ]),
    (T("Taster", "Button"), [
        ("user_extra_actions", T("Mehrfachdruck-Aktionen", "Multi-press actions"), "bool", False, "", 1,
         T("Mehrmals drücken zum Kalibrieren, Koppeln oder für den Bootloader.", "Press several times to calibrate, pair or enter the bootloader.")),
        ("ignore_reset", T("Reset-Taster ignorieren", "Ignore reset button"), "bool", True, "", 1,
         T("Der Reset-Taster löst keine Zusatzaktionen aus.", "The reset button does not trigger extra actions.")),
        ("user_shutdown", T("Ausschalten per Taster", "Power off by button"), "bool", True, "", 1,
         T("Der Tracker lässt sich per Taster bzw. Reset ausschalten.", "The tracker can be powered off with the button or reset.")),
    ]),
    ("LED", [
        ("led_default_color", T("Farbe im Normalbetrieb", "Color in normal operation"), "color", None, "", 1,
         T("Farbe der Status-LED, falls der Tracker eine RGB-LED hat.", "Color of the status LED, if the tracker has an RGB LED.")),
    ]),
    (T("Funk und Akku", "Radio and battery"), [
        ("radio_tx_power", T("Sendeleistung", "Transmit power"), "int", 8, "dBm", 1,
         T("Weniger = etwas weniger Reichweite, dafür längere Akkulaufzeit. Höchstwert meist 8.", "Less = slightly less range, but longer battery life. Maximum usually 8.")),
        ("connection_timeout_delay", T("Abschalten ohne Dongle nach", "Power off without dongle after"), "int", 5, "min", 60000,
         T("Findet der Tracker keinen Dongle, schaltet er sich nach dieser Zeit ab.", "If the tracker finds no dongle, it powers off after this time.")),
        ("connection_over_hid", T("Daten per USB-HID ausgeben", "Output data over USB HID"), "bool", False, "", 1,
         T("Nur für Sonderfälle: Daten per USB statt nur per Funk.", "Special cases only: data over USB instead of radio only.")),
        ("battery_low_runtime_threshold", T("Akku-Warnung unter", "Battery warning below"), "int", 3, "h", 3600000,
         T("Warnt, wenn die geschätzte Restlaufzeit darunter fällt.", "Warns when the estimated remaining runtime drops below this.")),
    ]),
]

FW_BG = ("#e9eef5", "#0b1724")
FW_CARD = ("#dce4ee", "#0f2133")
FW_CARD2 = ("#cfd9e5", "#16304a")
FW_PURPLE = "#7c4dcc"
FW_PURPLE_H = "#6a3fb5"
FW_SLATE = ("#8fa1b5", "#34506b")
FW_GREEN = "#2e9e5b"
FW_DIM = ("gray35", "gray65")

# Rueckfrage im Stil der App statt des grauen System-Dialogs von Tk. Gibt True bei "Ja" zurueck.
def ask_yes_no(title, text, parent=None):
    parent = parent or app
    result = {"ok": False}
    w = ctk.CTkToplevel(parent)
    w.title(title)
    w.configure(fg_color=FW_BG)
    w.resizable(False, False)
    w.transient(parent)
    ctk.CTkLabel(w, text=title, font=ctk.CTkFont(size=18, weight="bold"), anchor="w").pack(
        fill="x", padx=22, pady=(18, 6))
    ctk.CTkLabel(w, text=text, anchor="w", justify="left", wraplength=460).pack(fill="x", padx=22)

    def close(ok):
        result["ok"] = ok
        w.destroy()

    row = ctk.CTkFrame(w, fg_color="transparent")
    row.pack(fill="x", padx=22, pady=(18, 18))
    ctk.CTkButton(row, text=T("Ja", "Yes"), width=110, fg_color=FW_PURPLE, hover_color=FW_PURPLE_H,
                  text_color="white", command=lambda: close(True)).pack(side="right")
    ctk.CTkButton(row, text=T("Abbrechen", "Cancel"), width=110, fg_color=FW_SLATE,
                  command=lambda: close(False)).pack(side="right", padx=(0, 8))
    w.protocol("WM_DELETE_WINDOW", lambda: close(False))
    w.bind("<Return>", lambda e: close(True))
    w.bind("<Escape>", lambda e: close(False))
    # mittig ueber dem aufrufenden Fenster
    w.update_idletasks()
    x = parent.winfo_rootx() + max(0, (parent.winfo_width() - w.winfo_reqwidth()) // 2)
    y = parent.winfo_rooty() + max(0, (parent.winfo_height() - w.winfo_reqheight()) // 3)
    w.geometry(f"+{x}+{y}")
    try:
        w.wait_visibility()
        w.grab_set()
    except tk.TclError:
        pass
    w.focus_set()
    parent.wait_window(w)
    return result["ok"]

fw_release_cache = {}

# Erklaerungen stehen hinter einem ?-Knopf, damit die Seite uebersichtlich bleibt
# Farb-LED (RGB) laut Board-Dateien der offiziellen Firmware: nur Boards mit pwm-led1 und pwm-led2 nutzen
# die LED-Farbe. True/False, None = Board nicht in der offiziellen Firmware, also ungeprueft.
def board_has_rgb(board, options=()):
    if board == "ProMicro":
        return "Chrysalis" in options          # Stacked Smol und Normal: nur die einfarbige LED (P0.15)
    if board in ("Mochi", "XIAO", "XIAO_Sense", "SlimevrMini4", "SlimevrMini4R9", "SlimevrMini4R11"):
        return True
    if board in ("SlimevrMini", "SlimevrMini2", "SlimevrMini3_R6", "SlimevrMini3_R7", "R3"):
        return False
    return None

# dasselbe ueber die Zeile "Target: ..." aus der Antwort auf info
def target_has_rgb(target):
    t = target.lower()
    if any(k in t for k in ("chrysalis", "mochi", "xiao", "slimevrmini_p4")):
        return True
    if any(k in t for k in ("promicro", "slimevrmini_p", "slimenrf_r")):
        return False
    return None

LED_UNKNOWN_NOTE = T("ob dieses Board eine Farb-LED hat, ist nicht geprüft", "whether this board has a color LED has not been checked")

# Im DIY Firmware-Tool legt schon die Bauweise (Schritt 2 oben) Magnetometer und Sensor-Takt fest;
# unten bei den optionalen Einstellungen waeren sie doppelt. Die Geraeteverwaltung zeigt sie weiter.
FW_TOOL_SKIP_SETTINGS = {"sensor_use_mag", "use_sensor_clock"}

# Bilder zu den Bauformen (assets/bauform/<datei>), werden unter dem "?" mit angezeigt
FW_VARIANT_IMAGES = [("Stacked Smol", "stacked.png"), ("Chrysalis", "chrysalis.png"), ("Normal (Non-Stacked)", "normal.png")]

# Bild in voller Groesse (Schaltplaene sind klein kaum lesbar)
def show_big_image(path, caption):
    win = ctk.CTkToplevel(app)
    win.title(caption)
    img = tk.PhotoImage(file=path)
    pic = tk.Label(win, image=img, borderwidth=0, highlightthickness=0, cursor="hand2")
    pic.image = img
    pic.pack(padx=8, pady=8)
    pic.bind("<Button-1>", lambda e: win.destroy())
    win.after(100, win.focus)

def bauform_images(parent):
    outer = ctk.CTkFrame(parent, fg_color="transparent")
    row = ctk.CTkFrame(outer, fg_color="transparent")
    row.pack(anchor="w")
    shown = 0
    for caption, fname in FW_VARIANT_IMAGES:
        path = resource_path(os.path.join("assets", "bauform", fname))
        if not os.path.isfile(path):
            continue
        try:
            img = tk.PhotoImage(file=path)
        except tk.TclError:
            continue
        factor = max(1, -(-img.width() // 220))   # auf hoechstens ~220 px Breite verkleinern
        img = img.subsample(factor, factor)
        cell = ctk.CTkFrame(row, fg_color="transparent")
        cell.pack(side="left", padx=(0, 16), anchor="n")
        pic = tk.Label(cell, image=img, borderwidth=0, highlightthickness=0)
        pic.image = img   # Referenz halten, sonst raeumt Tk das Bild weg
        pic.pack()
        pic.configure(cursor="hand2")
        pic.bind("<Button-1>", lambda e, p=path, c=caption: show_big_image(p, c))
        ctk.CTkLabel(cell, text=caption, text_color=FW_DIM).pack()
        shown += 1
    if shown:
        ctk.CTkLabel(outer, text=T("Schaltpläne: SlimeVR-Doku (MIT-Lizenz)", "Schematics: SlimeVR docs (MIT license)"), text_color=FW_DIM,
                     font=ctk.CTkFont(size=11)).pack(anchor="w")
    return outer

def label_with_help(parent, row, text, help_text, bold=False, padx=12, images=None):
    head = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(head, text=text, anchor="w",
                 font=ctk.CTkFont(weight="bold") if bold else None).pack(side="left")
    help_l = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(help_l, text=help_text, anchor="w", justify="left", wraplength=640,
                 text_color=FW_DIM).pack(anchor="w")
    if images:
        images(help_l).pack(anchor="w", pady=(6, 0))
    help_l.grid(row=row + 1, column=0, columnspan=3, sticky="w", padx=padx, pady=(2, 4))
    help_l.grid_remove()

    def flip():
        if help_l.winfo_ismapped():
            help_l.grid_remove()
        else:
            help_l.grid()
    if help_text:
        ctk.CTkButton(head, text="?", width=22, height=22, corner_radius=11, fg_color=FW_SLATE,
                      hover_color=FW_PURPLE, command=flip).pack(side="left", padx=(6, 0))
    return head


# Zwei Namensschemata: SlimeNRF_Tracker_SPI_Mag_ProMicro (CI) und
# SlimeNRF_ProMicro_StackedSmol_Tracker_I2C bzw. Aero_Tracker_Pro (jitingcn).
# Bekannte Optionen werden herausgezogen, der Rest ist das Board.
FW_TOKEN_ALIASES = {t.lower(): t for t in (FW_OPTION_TOKENS - {T("Schlafen", "Sleep"), "SmolPins"}) | {"NoCLK", "NoSleep", "smSPI"}}

def parse_fw_name(name):
    base, _, ext = name.rpartition(".")
    if ext not in ("uf2", "hex") or not base:
        return None
    tokens = [t for t in base.replace("DataCollect_CDC", "DataCollect").split("_") if t]
    role = "dongle" if any(t.lower() == "receiver" for t in tokens) else "tracker"
    rest = [t for t in tokens if t.lower() not in ("slimenrf", "tracker", "receiver", "uf2", "hex")]
    # jitingcn: ProMicro_StackedSmol_601N1 = Stacked-Smol-Variante mit eigenem Sensormodul -> Bauform, kein Board
    if any(t.lower() == "stackedsmol" for t in rest):
        extra = [t for t in rest if t.lower() not in FW_TOKEN_ALIASES and t.lower() not in ("nosleepclk", "promicro")]
        if extra:
            rest = [t for t in rest if t not in extra and t.lower() != "stackedsmol"] + ["StackedSmol_" + "_".join(extra)]
    opts = set(FW_TOKEN_ALIASES[t.lower()] for t in rest if t.lower() in FW_TOKEN_ALIASES)
    if any(t.lower() == "nosleepclk" for t in rest):
        opts |= {"NoSleep", "CLK"}
    if role == "tracker":   # Taster/Takt/Anschluss/Schlaf gibt es nur bei Trackern
        # Stacked Smol und Chrysalis haben den Taster fest eingebaut (SW0 ist in ihrem Board immer an)
        if any(t.lower().startswith(("stackedsmol", "chrysalis")) for t in rest):
            opts.add("SW0")
        # Sensor-Takt gibt es nur an/aus. Ohne Angabe ist er beim Stacked Smol und bei Chrysalis an (ihr Board
        # legt die Leitung fest), beim normalen ProMicro aus. Danach steht "CLK" genau dann drin, wenn er an ist.
        board_clk = any(t.lower().startswith(("stackedsmol", "chrysalis")) for t in rest)
        clk_on = "CLK" in opts or (board_clk and "NoCLK" not in opts)
        opts -= {"CLK", "NoCLK"}
        if clk_on:
            opts.add("CLK")
        # Sensor-Anschluss nur SPI oder I2C. Ohne Angabe ist der ProMicro I2C, Chrysalis und Bao sind SPI;
        # smSPI ist SPI mit anderer Pinbelegung. Unbekannt bleibt es nur bei den Stacked-Smol-Sondervarianten.
        if "smSPI" in opts:
            opts -= {"smSPI"}
            opts |= {"SPI", "SmolPins"}
        elif not opts & {"SPI", "I2C"} and any(t.lower() == "promicro" for t in rest) \
                and not any(t.startswith("StackedSmol_") for t in rest):
            opts.add("SPI" if any(t.lower() in ("bao", "chrysalis") for t in rest) else "I2C")
        # Schlafmodus ebenso als an/aus: "NoSleep" im Namen heisst aus, sonst an
        if "NoSleep" in opts:
            opts.discard("NoSleep")
        else:
            opts.add(T("Schlafen", "Sleep"))
    return {
        "role": role,
        "board": "_".join(t for t in rest if t.lower() not in FW_TOKEN_ALIASES and t.lower() != "nosleepclk"
                          and not t.startswith("StackedSmol_"))
                 or ("ProMicro" if any(t.lower().startswith("stackedsmol") for t in rest) else "Standard"),
        "options": frozenset(opts) | frozenset(t for t in rest if t.startswith("StackedSmol_")),
        "ext": ext,
        "name": name,
    }

def fw_sources():
    sources = list(FW_SOURCES)
    m = re.search(r"repos/([^/]+)/([^/]+)", settings.get("custom_firmware_repo", "") or "")
    if m:
        sources.insert(-2, {"id": "custom", "name": m.group(2), "owner": m.group(1), "badge": "Eigene",
                            "repo": f"{m.group(1)}/{m.group(2)}"})
    return sources

# Die GitHub-API erlaubt ohne Anmeldung nur 60 Abfragen pro Stunde je Internetanschluss; alle Rechner
# im Haus teilen sie sich. Die normalen Seiten (Weiterleitung, Release-Feed, Dateiliste) haben kein
# solches Limit, deshalb kommt alles von dort.
def fetch_release_assets(repo, tag):
    response = requests.get(f"https://github.com/{repo}/releases/expanded_assets/{tag}", timeout=20)
    response.raise_for_status()
    assets = []
    for part in response.text.split(f'href="/{repo}/releases/download/{tag}/')[1:]:
        name = urllib.parse.unquote(part.split('"', 1)[0])
        # Die offizielle CI laedt zusaetzlich Builds aus jitingcns Code hoch (..._JitingCat). Wer eine
        # Quelle waehlt, bekommt nur deren eigene Firmware; jitingcn hat eine eigene Quelle.
        if "jitingcat" in name.lower():
            continue
        # Bao steht nicht in der SlimeVR-Doku (die CI baut es aus einem Zusatz-Repo)
        if re.search(r"(^|_)Bao(_|\.)", name):
            continue
        info = parse_fw_name(name)
        if info:
            date = re.search(r'datetime="(\d{4}-\d\d-\d\d)', part)
            info["url"] = f"https://github.com/{repo}/releases/download/{tag}/{name}"
            info["date"] = date.group(1) if date else ""
            assets.append(info)
    return assets

def fetch_releases(repo):
    if repo in fw_release_cache:
        return fw_release_cache[repo]
    # Das stabile Release (bei Shine-Bright-Meow "latest" mit allen Varianten) steht vorn; es wurde frueh
    # angelegt und taucht unter den neuesten Tages-Builds sonst gar nicht auf.
    stable = ""
    response = requests.get(f"https://github.com/{repo}/releases/latest", allow_redirects=False, timeout=15)
    if response.status_code in (301, 302):
        stable = response.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]
    tags = [stable] if stable else []
    feed = requests.get(f"https://github.com/{repo}/releases.atom", timeout=15)
    if feed.ok:
        for tag in re.findall(r'/releases/tag/([^"<]+)"', feed.text):
            tag = urllib.parse.unquote(tag)
            if tag not in tags:
                tags.append(tag)
    releases = [{"tag": t, "stable": t == stable, "assets": None} for t in tags[:20]]
    # Dateien gleich fuer das erste Release mit Firmware laden, die anderen erst bei Auswahl
    while releases:
        releases[0]["assets"] = fetch_release_assets(repo, releases[0]["tag"])
        if releases[0]["assets"]:
            break
        releases.pop(0)
    fw_release_cache[repo] = releases
    return releases

def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

# "SlimeNRF Tracker ProMicro" -> ProMicro, "SlimeNRF Receiver Holyiot-21017" -> Holyiot_Dongle
def guess_board(product, boards):
    p = norm_name(product)
    for b in sorted(boards, key=len, reverse=True):
        if norm_name(b) in p:
            return b
    for b in boards:
        if norm_name(b.split("_")[0]) in p:
            return b
    return None

def open_multiflash_window(role=None):
    global multi_win
    if multi_win is not None and multi_win.winfo_exists():
        multi_win.focus()
        return

    win = ctk.CTkToplevel(app, fg_color=FW_BG)
    multi_win = win
    win.title(T("DIY Firmware-Tool", "DIY Firmware Tool"))
    win.geometry("880x780")
    win.transient(app)

    st = {"source": None, "releases": [], "release": None, "role": "tracker", "board": None,
          "asset": None, "file": None, "busy": False}
    ver_map = {}
    board_map = {}
    rows = []
    label_to_port = {}
    clear_var = tk.BooleanVar(value=False)
    cur = {"i": 0}
    steps = []

    def ui(fn):
        app.after(0, fn)

    head = ctk.CTkFrame(win, fg_color="transparent")
    head.pack(fill="x", padx=20, pady=(16, 4))
    ctk.CTkLabel(head, text=T("DIY Firmware-Tool", "DIY Firmware Tool"), font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
    ctk.CTkLabel(head, text=T("Erlaubt dir das Konfigurieren und Flashen von DIY-Trackern und Dongles", "Lets you configure and flash DIY trackers and dongles"), text_color=FW_DIM).pack(anchor="w")

    body = ctk.CTkScrollableFrame(win, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    def make_step(i, title, subtitle):
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        row.grid_columnconfigure(1, weight=1)
        circle = ctk.CTkLabel(row, text=str(i + 1), width=30, height=30, corner_radius=15, fg_color=FW_SLATE,
                              text_color="white", font=ctk.CTkFont(weight="bold"))
        circle.grid(row=0, column=0, sticky="n", padx=(6, 12), pady=2)
        title_l = ctk.CTkLabel(row, text=title, font=ctk.CTkFont(size=15, weight="bold"), anchor="w")
        title_l.grid(row=0, column=1, sticky="w")
        sub = ctk.CTkLabel(row, text=subtitle, text_color=FW_DIM, anchor="w")
        frame = ctk.CTkFrame(row, fg_color="transparent")
        for w in (circle, title_l):
            w.bind("<Button-1>", lambda e, i=i: go(i) if i < cur["i"] and not st["busy"] else None)
        steps.append({"circle": circle, "sub": sub, "frame": frame})
        return frame

    def nav(frame, row, next_cmd=None, next_text=T("Nächster Schritt", "Next step"), back=True):
        bar = ctk.CTkFrame(frame, fg_color="transparent")
        bar.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        if back:
            ctk.CTkButton(bar, text=T("Zurück", "Back"), width=100, fg_color="transparent", border_width=1,
                          border_color=FW_SLATE, command=go_back).pack(side="left")
        if not next_cmd:
            return None
        btn = ctk.CTkButton(bar, text=next_text, width=160, fg_color=FW_PURPLE, hover_color=FW_PURPLE_H,
                            command=next_cmd, state="disabled")
        btn.pack(side="right")
        return btn

    def go_back():
        if st["busy"]:
            return
        # Bei eigener Datei gibt es nichts zu konfigurieren
        go(0 if cur["i"] == 2 and st["file"] else cur["i"] - 1)

    # ---------- 1: Firmware waehlen ----------
    f1 = make_step(0, T("Wähle die Firmware zum Flashen aus", "Choose the firmware to flash"), T("Quelle, Board und Version", "Source, board and version"))
    for c in range(3):
        f1.grid_columnconfigure(c, weight=1, uniform="s1")

    # Vorerst nur Tracker; st["role"] bleibt fuer einen spaeteren Dongle-Zweig drin
    def column(c, title):
        box = ctk.CTkFrame(f1, fg_color="transparent")
        box.grid(row=1, column=c, sticky="nsew", padx=6)
        ctk.CTkLabel(box, text=title, font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x")
        inner = ctk.CTkFrame(box, fg_color=FW_CARD, corner_radius=10)
        inner.pack(fill="both", expand=True, pady=(4, 0))
        return inner

    col_src = column(0, T("Firmware-Quelle", "Firmware source"))
    col_board = column(1, T("Boardtyp", "Board type"))
    col_ver = column(2, T("Firmware-Version", "Firmware version"))

    src_cards = {}
    for src in fw_sources():
        if src["id"] == "all":
            continue   # keine eigene Karte; nur ueber "In allen Quellen suchen" erreichbar
        card = ctk.CTkFrame(col_src, fg_color=FW_CARD2, corner_radius=8, border_width=2, border_color=FW_CARD2)
        card.pack(fill="x", padx=8, pady=4)
        t = ctk.CTkLabel(card, text=src["name"], anchor="w", font=ctk.CTkFont(weight="bold"))
        t.pack(fill="x", padx=10, pady=(6, 0))
        line = ctk.CTkFrame(card, fg_color="transparent")
        line.pack(fill="x", padx=10, pady=(0, 6))
        o = ctk.CTkLabel(line, text=src["owner"], anchor="w", text_color=FW_DIM)
        o.pack(side="left")
        badge = ctk.CTkLabel(line, text=f" {src['badge']} ", corner_radius=6, height=18,
                             fg_color=FW_PURPLE if src["badge"] == T("Offiziell", "Official") else FW_SLATE,
                             text_color="white", font=ctk.CTkFont(size=11))
        badge.pack(side="right")
        if src["repo"] not in (None, "*"):
            # GitHub-Seite der Quelle im Browser, zum selbst Nachlesen
            link = ctk.CTkButton(card, text="↗", width=26, height=22, corner_radius=6, fg_color=FW_SLATE,
                                 hover_color=FW_PURPLE, text_color="white",
                                 command=lambda r=src["repo"]: webbrowser.open(f"https://github.com/{r}"))
            link.place(relx=1.0, x=-8, y=6, anchor="ne")
            ToolTip(link, T(f"github.com/{src['repo']} im Browser öffnen", f"Open github.com/{src['repo']} in the browser"))
        for w in (card, t, line, o, badge):
            w.bind("<Button-1>", lambda e, s=src: select_source(s))
        src_cards[src["id"]] = card

    role_seg = ctk.CTkSegmentedButton(col_board, values=["Tracker", "Dongle"],
                                      command=lambda v: set_role("dongle" if v == "Dongle" else "tracker"))
    role_seg.set("Tracker")
    role_seg.pack(fill="x", padx=10, pady=(12, 0))
    board_menu = ctk.CTkOptionMenu(col_board, values=[T("Keine Quelle ausgewählt", "No source selected")], state="disabled",
                                   command=lambda v: set_board(board_map.get(v)))
    board_menu.set(T("Keine Quelle ausgewählt", "No source selected"))
    board_menu.pack(fill="x", padx=10, pady=12)

    def pick_file():
        path = filedialog.askopenfilename(parent=win, title=T("UF2-Datei wählen", "Choose UF2 file"), filetypes=[(T("UF2-Dateien", "UF2 files"), "*.uf2")])
        if path:
            st["file"] = path
            file_btn.configure(text=os.path.basename(path))
            update_next1()

    file_btn = ctk.CTkButton(col_board, text=T("Datei wählen…", "Choose file…"), command=pick_file)

    ver_menu = ctk.CTkOptionMenu(col_ver, values=[T("Keine Quelle ausgewählt", "No source selected")], state="disabled",
                                 command=lambda v: select_version(v))
    ver_menu.set(T("Keine Quelle ausgewählt", "No source selected"))
    ver_menu.pack(fill="x", padx=10, pady=12)
    ctk.CTkLabel(col_ver, text=T("Der Dongle muss dieselbe\nVersion haben.", "The dongle must have the\nsame version."), text_color=FW_DIM,
                 justify="left").pack(anchor="w", padx=10, pady=(0, 10))

    def next1():
        if st["file"] and st["source"]["repo"] is None:
            info = parse_fw_name(os.path.basename(st["file"])) or {}
            st["asset"] = {"name": os.path.basename(st["file"]), "url": None, "path": st["file"], "ext": "uf2",
                           "options": info.get("options", frozenset()), "board": info.get("board", "")}
            go(2)
        else:
            go(1)

    next1_btn = nav(f1, 2, next_cmd=next1, back=False)

    def update_next1():
        if st["source"] and st["source"]["repo"] is None:
            ok = bool(st["file"])
        else:
            ok = bool(st["release"] and st["board"])
        next1_btn.configure(state="normal" if ok else "disabled")

    def select_source(src):
        if st["busy"]:
            return
        st["source"], st["release"], st["board"] = src, None, None
        for sid, card in src_cards.items():
            card.configure(border_color=FW_PURPLE if sid == src["id"] else FW_CARD2)
        if src["repo"] is None:
            board_menu.pack_forget()
            file_btn.pack(fill="x", padx=10, pady=12)
            ver_menu.configure(values=[T("Eigene Datei", "Own file")], state="disabled")
            ver_menu.set(T("Eigene Datei", "Own file"))
            update_next1()
            return
        st["file"] = None
        file_btn.pack_forget()
        board_menu.pack(fill="x", padx=10, pady=12)
        for m in (board_menu, ver_menu):
            m.configure(state="disabled")
            m.set(T("Lade…", "Loading…"))
        update_next1()

        def work():
            if src["repo"] == "*":
                merged, err = [], None
                for other in fw_sources():
                    if other["repo"] in (None, "*"):
                        continue
                    try:
                        rels = fetch_releases(other["repo"])
                    except Exception as e:
                        err = e
                        continue
                    if rels:
                        merged += [dict(a, src=other, tag=rels[0]["tag"]) for a in rels[0]["assets"]]
                rels = [{"tag": T("neueste je Quelle", "newest per source"), "assets": merged}] if merged else []
                err = None if merged else err
            else:
                try:
                    rels, err = fetch_releases(src["repo"]), None
                    rels = [dict(rel, assets=None if rel["assets"] is None
                                 else [dict(a, src=src, tag=rel["tag"]) for a in rel["assets"]]) for rel in rels]
                except Exception as e:
                    rels, err = [], e
            ui(lambda: releases_loaded(src, rels, err))
        threading.Thread(target=work, daemon=True).start()

    def releases_loaded(src, rels, err):
        if st["source"] is not src:
            return
        st["releases"] = rels
        if err or not rels:
            ver_menu.set(T("Fehler beim Laden", "Error while loading") if err else T("Keine Firmware gefunden", "No firmware found"))
            board_menu.set("–")
            if err:
                append_text(f"[Firmware-Tool] {src['repo']}: {err}\n", "error")
            update_next1()
            return
        ver_map.clear()
        for k, rel in enumerate(rels):
            ver_map[rel["tag"] + (T("  (stabil)", "  (stable)") if rel.get("stable") and src["repo"] != "*" else "")] = rel
        labels = list(ver_map)
        ver_menu.configure(values=labels, state="normal")
        ver_menu.set(labels[0])
        select_version(labels[0])

    def select_version(label):
        rel = ver_map.get(label)
        src = st["source"]
        if rel is not None and rel.get("assets") is None:
            board_menu.configure(state="disabled")
            board_menu.set(T("Lade…", "Loading…"))

            def work():
                try:
                    assets = [dict(a, src=src, tag=rel["tag"]) for a in fetch_release_assets(src["repo"], rel["tag"])]
                except Exception as e:
                    assets = []
                    ui(lambda e=e: append_text(f"[Firmware-Tool] {src['repo']} {rel['tag']}: {e}\n", "error"))

                def done():
                    rel["assets"] = assets
                    if st["source"] is src:
                        select_version(label)
                ui(done)
            threading.Thread(target=work, daemon=True).start()
            return
        st["release"] = rel
        refresh_boards()
        if st.pop("auto_next", False) and st["board"]:
            go(1)   # "In allen Quellen suchen": gleich wieder zur Bauweise

    def set_board(board):
        st["board"] = board
        update_next1()

    def set_role(role):
        if st["busy"] or role == st["role"]:
            return
        st["role"] = role
        st["board"] = None
        role_seg.set("Dongle" if role == "dongle" else "Tracker")
        if st["release"]:
            refresh_boards()

    def refresh_boards():
        boards = sorted({a["board"] for a in st["release"]["assets"] if a["role"] == st["role"]}) if st["release"] else []
        board_map.clear()
        board_map.update({b.replace("_", " "): b for b in boards})
        if not boards:
            board_menu.configure(values=[T("Keine für diesen Gerätetyp", "None for this device type")], state="disabled")
            board_menu.set(T("Keine für diesen Gerätetyp", "None for this device type"))
            set_board(None)
            return
        pick = st["board"] if st["board"] in boards else None
        saved = settings.get("fw_last", {}).get(st["role"], {})
        if not pick and saved.get("board") in boards:
            pick = saved["board"]
        if not pick:
            products = [d.product for d in devices if d.is_receiver == (st["role"] == "dongle")]
            products += [p["name"] for p in list_tracker_ports() if p["receiver"] == (st["role"] == "dongle")]
            pick = next((b for b in (guess_board(p, boards) for p in products) if b),
                        "ProMicro" if "ProMicro" in boards else boards[0])
        board_menu.configure(values=list(board_map), state="normal")
        board_menu.set(pick.replace("_", " "))
        set_board(pick)

    # ---------- 2: Board konfigurieren ----------
    f2 = make_step(1, T("Konfiguriere dein Board", "Configure your board"), T("Bauweise deines Trackers", "How your tracker is built"))
    f2.grid_columnconfigure(0, weight=1)

    def enter_config():
        for w in f2.winfo_children():
            w.destroy()
        assets = [a for a in st["release"]["assets"] if a["role"] == st["role"] and a["board"] == st["board"]]
        sets = [a["options"] for a in assets]
        saved = settings.get("fw_last", {}).get(st["role"], {})
        saved_opts = frozenset(saved.get("options", []))
        # Vorschlag: gespeicherte Wahl, sonst die schlichteste Bauweise ohne Sonderplatine (Bao/Chrysalis)
        base = saved_opts if saved.get("board") == st["board"] and saved_opts in sets else \
            min(sets, key=lambda o: (len(o - {T("Schlafen", "Sleep")}) + (0 if T("Schlafen", "Sleep") in o else 1)
                                     + 10 * any(t in ("Chrysalis", "Bao") or t.startswith("StackedSmol") for t in o),
                                     sorted(o)))
        fixed = frozenset.intersection(*sets)
        choice_vars = {}
        box_widgets = {}
        radio_widgets = {}   # key -> [(Radioknopf, in dieser Quelle vorhanden)]

        box = ctk.CTkFrame(f2, fg_color=FW_CARD, corner_radius=10)
        box.grid(row=0, column=0, sticky="ew", padx=6)
        box.grid_columnconfigure(1, weight=1)
        result_box = ctk.CTkFrame(f2, fg_color="transparent")
        result_box.grid(row=1, column=0, sticky="ew", padx=6, pady=(8, 0))
        result = ctk.CTkLabel(result_box, text="", anchor="w", justify="left")
        result.pack(fill="x")
        suggest = ctk.CTkFrame(result_box, fg_color="transparent")

        def group_of(t):
            for key, label, toks in FW_OPTION_GROUPS:
                if t in toks or (key == "variant" and t.startswith("StackedSmol_")):
                    return key, label, toks
            return None, t, [t]

        def choice_text(key, t):
            return FW_CHOICE_LABELS.get(key, {}).get(t) or \
                (f"Stacked Smol ({t[12:]})" if t and t.startswith("StackedSmol_") else t) or T("Platinen-Standard", "Board default")

        # Was sich gegenueber der Auswahl aendert, z.B. "Taster an SW0 aus"
        def describe(chosen, opts):
            parts = []
            for key, label, toks in FW_OPTION_GROUPS:
                a = next((t for t in chosen if group_of(t)[0] == key), None)
                b = next((t for t in opts if group_of(t)[0] == key), None)
                if a != b:
                    parts.append(T(f"{label} {'an' if b else 'aus'}", f"{label} {'on' if b else 'off'}") if len(toks) == 1 else f"{label}: {choice_text(key, b)}")
            return ", ".join(parts)

        def apply_options(opts):
            for key, (var, tok) in choice_vars.items():
                if tok:
                    var.set(tok in opts)
                else:
                    var.set(next((t for t in opts if group_of(t)[0] == key), ""))
            update_result()
        adv = ctk.CTkFrame(f2, fg_color="transparent")
        adv.grid(row=2, column=0, sticky="ew", padx=6, pady=(10, 0))
        nxt = nav(f2, 3, next_cmd=lambda: go(2))

        def update_result():
            # Was bei der gewaehlten Bauform fest vorgegeben ist (Chrysalis: SPI, Takt, Taster; Stacked Smol:
            # Taster), wird automatisch eingestellt und gesperrt - sonst landet man bei "gibt es nicht".
            if "variant" in choice_vars:
                variant = choice_vars["variant"][0].get() or None
                vname = choice_text("variant", variant)
                vsets = [o for o in sets if next((t for t in o if group_of(t)[0] == "variant"), None) == variant]
                for key, (var, tok) in choice_vars.items():
                    if key == "variant" or not vsets:
                        continue
                    vals = {next((t for t in o if group_of(t)[0] == key), None) for o in vsets}
                    locked = len(vals) == 1
                    if locked:
                        v = next(iter(vals))
                        var.set(v is not None) if tok else var.set(v or "")
                    if tok and key in box_widgets:
                        if not locked:
                            text = T("An", "On")
                        elif key == "sw0" and variant and variant.startswith("StackedSmol"):
                            text = T("An – beim Stacked Smol eingebaut (P0.06)", "On – built into the Stacked Smol (P0.06)")
                        else:
                            text = T(f"An – bei {vname} immer", f"On – always with {vname}") if var.get() else T(f"Aus – gibt es bei {vname} nicht", f"Off – not available with {vname}")
                        box_widgets[key].configure(state="disabled" if locked else "normal", text=text)
                    elif not tok:
                        for rb, available in radio_widgets.get(key, []):
                            rb.configure(state="normal" if available and (not locked or rb.cget("value") == var.get())
                                         else "disabled")
            chosen = set(fixed)
            for var, tok in choice_vars.values():
                if tok and var.get():
                    chosen.add(tok)
                elif not tok and var.get():
                    chosen.add(var.get())
            order = [s["id"] for s in fw_sources()]
            def fits(a):
                o = a["options"]
                return o == chosen or (not o & {"SPI", "I2C"} and o == chosen - {"SPI", "I2C"})
            match = sorted((a for a in assets if fits(a)),
                           key=lambda a: (a["ext"] != "uf2", order.index(a["src"]["id"]) if a["src"]["id"] in order else 99))
            st["asset"] = match[0] if match else None
            if match:
                a = match[0]
                date = T(f" · Datei vom {a['date'][8:10]}.{a['date'][5:7]}.{a['date'][:4]}", f" · file from {a['date'][:10]}") if a.get("date") else ""
                result.configure(text=T(f"✅  {a['name']}\n      Quelle: {a['src']['owner']} / {a['src']['name']} · {a['tag']}{date}", f"✅  {a['name']}\n      Source: {a['src']['owner']} / {a['src']['name']} · {a['tag']}{date}"),
                                 text_color=("green", "lime"))
                nxt.configure(state="normal")
            else:
                tip = "" if st["source"]["id"] == "all" else T("\n      Tipp: „In allen Quellen suchen“ findet oft mehr Kombinationen.", "\n      Tip: “Search all sources” often finds more combinations.")
                result.configure(text=T("❌  Diese Kombination gibt es in dieser Version nicht.", "❌  This combination does not exist in this version.") + tip, text_color="red")
                nxt.configure(state="disabled")
            apply_led_visibility()
            # Bei fehlender Kombination die naechstliegenden vorhandenen Dateien anbieten
            for w in suggest.winfo_children():
                w.destroy()
            suggest.pack_forget()  # Tk schrumpft einen geleerten Rahmen nicht, also ganz ausblenden
            if not match:
                suggest.pack(fill="x")
                near = sorted({a["options"] for a in assets}, key=lambda o: (len(o ^ chosen), len(o), sorted(o)))[:3]
                if st["source"]["id"] != "all":
                    # Andere Quellen bauen oft mehr (z.B. Stacked Smol mit I2C nur kounocom/jitingcn)
                    def search_all(chosen=frozenset(chosen)):
                        settings.setdefault("fw_last", {})[st["role"]] = {
                            "source": "all", "board": st["board"], "options": sorted(chosen)}
                        st["auto_next"] = True
                        go(0)
                        select_source(next(x for x in fw_sources() if x["id"] == "all"))
                    ctk.CTkButton(suggest, text=T("🔍 In allen Quellen suchen", "🔍 Search all sources"), fg_color=FW_PURPLE,
                                  hover_color=FW_PURPLE_H, text_color="white",
                                  command=search_all).pack(anchor="w", pady=(6, 2))
                ctk.CTkLabel(suggest, text=T("Am nächsten dran gibt es:", "Closest available:"), anchor="w").pack(fill="x", pady=(6, 2))
                for opts in near:
                    ctk.CTkButton(suggest, text=describe(chosen, opts), anchor="w",
                                  command=lambda o=opts: apply_options(o)).pack(anchor="w", pady=2)

        r = 0
        for key, label, toks in FW_OPTION_GROUPS:
            if key == "variant":
                toks = toks + sorted({t for o in sets for t in o if t.startswith("StackedSmol_")})
            present = [t for t in toks if any(t in s for s in sets)]
            has_none = any(not (s & set(toks)) for s in sets)
            choices = present + ([None] if has_none and key != "bus" else [])
            if len(choices) < 2 and not (key == "bus" and present):
                continue
            current = next((t for t in base if t in toks), None)
            names = FW_CHOICE_LABELS.get(key, {})
            label_with_help(box, r, label, FW_OPTION_HELP.get(key, ""), bold=True,
                            images=bauform_images if key == "variant" else None).grid(
                row=r, column=0, sticky="nw", padx=12, pady=(10, 0))
            if len(toks) == 1:
                var = tk.BooleanVar(value=current is not None)
                box_widgets[key] = ctk.CTkCheckBox(box, text=T("An", "On"), variable=var, command=update_result)
                box_widgets[key].grid(row=r, column=1, sticky="w", pady=(10, 0))
                choice_vars[key] = (var, toks[0])
            else:
                var = tk.StringVar(value=current or "")
                fr = ctk.CTkFrame(box, fg_color="transparent")
                fr.grid(row=r, column=1, sticky="w", pady=(10, 0))
                # Beim Sensor-Anschluss auch zeigen, was diese Quelle nicht hat, damit die Wahl sichtbar bleibt
                shown = choices + ([t for t in toks if t not in present] if key == "bus" else [])
                for i, t in enumerate(shown):
                    available = t in choices
                    text = names.get(t) or (f"Stacked Smol ({t[12:]})" if t and t.startswith("StackedSmol_") else t)
                    text += "" if available else T(" – nicht in dieser Quelle", " – not in this source")
                    rb = ctk.CTkRadioButton(fr, text=text, variable=var, value=t or "", command=update_result,
                                            state="normal" if available else "disabled")
                    rb.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 14), pady=2)
                    radio_widgets.setdefault(key, []).append((rb, available))
                choice_vars[key] = (var, None)
            r += 2
        if r == 0:
            ctk.CTkLabel(box, text=T("Für dieses Board gibt es nur eine Bauweise.", "There is only one build for this board."), text_color=FW_DIM).grid(
                row=0, column=0, sticky="w", padx=12, pady=10)
        update_result()
        if st["role"] == "tracker":
            build_settings(adv)
        else:
            setting_widgets.clear()
            led_ui.clear()

    # Laufzeit-Einstellungen: "Standard" = nichts schreiben. Werte stehen in
    # der Anzeige-Einheit (s, min, h); beim Schreiben wird umgerechnet.
    setting_widgets = {}
    led_ui = {}   # Gruppenueberschrift, Zeile und Hinweis der LED-Farbe

    def led_state():
        return board_has_rgb(st["board"], st["asset"]["options"] if st.get("asset") else ())

    def apply_led_visibility():
        if not led_ui:
            return
        state = led_state()
        for key in ("group", "head", "cell"):
            led_ui[key].grid() if state is not False else led_ui[key].grid_remove()
        led_ui["note"].configure(text="" if state else LED_UNKNOWN_NOTE)

    def build_settings(parent):
        setting_widgets.clear()
        saved = settings.get("fw_settings", {})
        parent.grid_columnconfigure(0, weight=1)
        holder = ctk.CTkFrame(parent, fg_color=FW_CARD, corner_radius=10)
        toggle = ctk.CTkButton(parent, text=T("▸ Firmware-Einstellungen (optional)", "▸ Firmware settings (optional)"), anchor="w", fg_color="transparent",
                               hover_color=FW_CARD2, font=ctk.CTkFont(weight="bold"))
        toggle.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(parent, text=T("Werden nach dem Flashen in jeden Tracker geschrieben. „Standard“ lässt den Wert "
                                  "unverändert. Geht nur mit Firmware, die Einstellungen kennt (offizielle Firmware).", "Written to every tracker after flashing. “Default” leaves the value unchanged. Only works"
            " with firmware that supports settings (official firmware)."),
                     text_color=FW_DIM, anchor="w", justify="left", wraplength=700).grid(row=1, column=0, sticky="w", padx=4)

        def flip():
            if holder.winfo_ismapped():
                holder.grid_forget()
                toggle.configure(text=T("▸ Firmware-Einstellungen (optional)", "▸ Firmware settings (optional)"))
            else:
                holder.grid(row=2, column=0, sticky="ew", pady=(6, 0))
                toggle.configure(text=T("▾ Firmware-Einstellungen (optional)", "▾ Firmware settings (optional)"))
        toggle.configure(command=flip)
        if saved:
            flip()

        reset_var = tk.BooleanVar(value=bool(settings.get("fw_settings_reset", False)))
        ctk.CTkCheckBox(holder, text=T("Vorher alle Einstellungen im Tracker auf Standard zurücksetzen", "Reset all tracker settings to default first"),
                        variable=reset_var).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 4))
        setting_widgets["__reset__"] = reset_var
        row = 1
        led_ui.clear()
        for group, items in FW_SETTINGS:
            group_label = ctk.CTkLabel(holder, text=group, font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
            group_label.grid(row=row, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 2))
            row += 1
            for name, label, kind, default, unit, factor, help_text in items:
                if name in FW_TOOL_SKIP_SETTINGS:
                    continue
                head = label_with_help(holder, row, label, help_text, padx=24)
                head.grid(row=row, column=0, sticky="w", padx=(24, 8), pady=(4, 0))
                cell = ctk.CTkFrame(holder, fg_color="transparent")
                cell.grid(row=row, column=1, sticky="w", pady=(4, 0))
                if kind == "bool":
                    std = T("Standard", "Default")
                    w = ctk.CTkSegmentedButton(cell, values=[std, T("An", "On"), T("Aus", "Off")])
                    w.set({True: T("An", "On"), False: T("Aus", "Off")}.get(saved.get(name), std))
                    w.pack(side="left")
                elif kind == "enum":
                    std = T("Standard", "Default")
                    w = ctk.CTkSegmentedButton(cell, values=[std] + list(factor.values()))
                    w.set(factor.get(saved.get(name), std))
                    w.pack(side="left")
                elif kind == "int":
                    w = ctk.CTkEntry(cell, width=90, placeholder_text=f"{default}")
                    if name in saved:
                        w.insert(0, str(saved[name]))
                    w.pack(side="left")
                    ctk.CTkLabel(cell, text=T(f"{unit}   (leer = Standard, meist {default} {unit})", f"{unit}   (empty = default, usually {default} {unit})"), text_color=FW_DIM).pack(side="left", padx=6)
                else:  # color
                    w = {"rgb": saved.get(name)}
                    swatch = ctk.CTkButton(cell, text=T("Farbe wählen…", "Choose color…"), width=130)

                    def pick(w=w, swatch=swatch):
                        from tkinter import colorchooser
                        c = colorchooser.askcolor(parent=win, title=T("LED-Farbe", "LED color"))
                        if c and c[0]:
                            w["rgb"] = [int(v) for v in c[0]]
                            swatch.configure(fg_color=c[1], text=c[1])

                    def clear(w=w, swatch=swatch):
                        w["rgb"] = None
                        swatch.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"], text=T("Farbe wählen…", "Choose color…"))
                    swatch.configure(command=pick)
                    swatch.pack(side="left")
                    ctk.CTkButton(cell, text=T("Standard", "Default"), width=80, fg_color="transparent", border_width=1,
                                  border_color=FW_SLATE, command=clear).pack(side="left", padx=6)
                    if w["rgb"]:
                        hexc = "#%02x%02x%02x" % tuple(w["rgb"])
                        swatch.configure(fg_color=hexc, text=hexc)
                    note = ctk.CTkLabel(cell, text="", text_color=FW_DIM)
                    note.pack(side="left", padx=6)
                    led_ui.update(group=group_label, head=head, cell=cell, note=note)
                setting_widgets[name] = (kind, w, factor)
                row += 2
        ctk.CTkLabel(holder, text="").grid(row=row, column=0, pady=2)
        apply_led_visibility()

    # -> (Befehle, Fehlertext). Speichert die Auswahl fuer das naechste Mal.
    def collect_settings():
        if not setting_widgets:
            return [], None
        values, cmds = {}, []
        reset = setting_widgets["__reset__"].get()
        if reset:
            cmds.append("reset_config all")
        for name, entry in setting_widgets.items():
            if name == "__reset__":   # ist nur das Kaestchen "vorher zuruecksetzen", kein (Art, Widget, Faktor)
                continue
            kind, w, factor = entry
            if kind == "bool":
                v = w.get()
                if v in (T("An", "On"), T("Aus", "Off")):
                    values[name] = v == T("An", "On")
                    cmds.append(f"write_config {name} {1 if v == 'An' else 0}")
            elif kind == "enum":
                inv = {label: key for key, label in factor.items()}
                if w.get() in inv:
                    values[name] = inv[w.get()]
                    cmds.append(f"write_config {name} {inv[w.get()]}")
            elif kind == "int":
                text = w.get().strip().replace(",", ".")
                if text:
                    try:
                        num = float(text)
                    except ValueError:
                        return None, T(f"„{text}“ ist keine Zahl.", f"“{text}” is not a number.")
                    values[name] = int(num) if num.is_integer() else num
                    cmds.append(f"write_config {name} {int(round(num * factor))}")
            elif kind == "color" and w["rgb"] and led_state() is not False:
                values[name] = w["rgb"]
                for ch, v in zip("rgb", w["rgb"]):
                    cmds.append(f"write_config led_default_color_{ch} {round(v * 10000 / 255)}")
        settings["fw_settings"] = values
        settings["fw_settings_reset"] = reset
        save_settings()
        return cmds, None

    # ---------- 3: Geraete waehlen ----------
    f3 = make_step(2, T("Geräte auswählen", "Select devices"), T("Welche angesteckten Geräte die Firmware bekommen", "Which plugged-in devices get the firmware"))
    f3.grid_columnconfigure(0, weight=1)
    list_frame = ctk.CTkScrollableFrame(f3, height=220, fg_color=FW_CARD, corner_radius=10)
    list_frame.grid(row=0, column=0, sticky="ew", padx=6)
    dev_bar = ctk.CTkFrame(f3, fg_color="transparent")
    dev_bar.grid(row=1, column=0, sticky="ew", padx=6, pady=(6, 0))

    def role_matches(p_or_dev_is_receiver):
        return p_or_dev_is_receiver == (st["role"] == "dongle")

    def refresh_choices():
        label_to_port.clear()
        for p in list_tracker_ports():
            lbl = port_label(p) + ("  (Dongle)" if p["receiver"] else "")
            label_to_port[lbl] = p
        values = list(label_to_port.keys()) or [T("Keine Ports gefunden", "No ports found")]
        for r in rows:
            r["menu"].configure(values=values)
        return values

    def set_status(r, text, color=None):
        color = color or ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        r["status"].configure(text=text, text_color=color)
        if r.get("status2") is not None and r["status2"].winfo_exists():
            r["status2"].configure(text=f"{device_name(r['dev']) if r['dev'] else r['var'].get()}: {text}", text_color=color)

    def row_port(r):
        return label_to_port.get(r["var"].get())

    def remove_row(r):
        if st["busy"]:
            return
        r["frame"].destroy()
        rows.remove(r)
        update_next3()

    def add_row(label=None):
        values = refresh_choices()
        if label is None:
            used = {r["var"].get() for r in rows}
            free = [v for v in values if v not in used and v in label_to_port and role_matches(label_to_port[v]["receiver"])]
            label = free[0] if free else T("Kein passendes Gerät gefunden", "No matching device found")
        frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        frame.pack(fill="x", pady=2)
        r = {"frame": frame, "var": tk.StringVar(value=label), "dev": None}
        ctk.CTkLabel(frame, text=f"#{len(rows) + 1}", width=30).pack(side="left", padx=(5, 0))
        r["menu"] = ctk.CTkOptionMenu(frame, values=values, variable=r["var"], width=330,
                                      command=lambda _v, rr=r: (rr.update(dev=None), set_status(rr, ""), update_next3()))
        r["menu"].pack(side="left", padx=5, pady=4)
        r["status"] = ctk.CTkLabel(frame, text="", anchor="w")
        r["status"].pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(frame, text="−", width=28, command=lambda rr=r: remove_row(rr)).pack(side="right", padx=5)
        rows.append(r)

    def add_all_detected():
        refresh_choices()
        used = {r["var"].get() for r in rows}
        for lbl, p in list(label_to_port.items()):
            if role_matches(p["receiver"]) and lbl not in used:
                add_row(lbl)

    def connect_all():
        if st["busy"]:
            return
        refresh_choices()
        asked = False
        infos = serial.tools.list_ports.comports()
        for r in rows:
            p = row_port(r)
            info = next((i for i in infos if p and i.device == p["device"]), None)
            if not info:
                r["dev"] = None
                set_status(r, T("kein Port", "no port"), "red")
                continue
            dev = get_or_add_device(info)
            dev.manual_off = False
            r["dev"] = dev
            if dev.connected or connect_device(dev, ask=not asked, parent=win):
                if role_matches(dev.is_receiver):
                    set_status(r, T(f"verbunden ({device_name(dev)})", f"connected ({device_name(dev)})"), "green")
                else:
                    # z.B. ProMicro mit Tracker-Firmware soll Dongle werden (oder umgekehrt)
                    set_status(r, T(f"verbunden ({device_name(dev)}) – wird zum "
                                  f"{'Dongle' if st['role'] == 'dongle' else 'Tracker'} umgeflasht", f"connected ({device_name(dev)}) – will be reflashed as {'dongle' if st['role'] == 'dongle' else 'tracker'}"), "orange")
                continue
            e = dev.last_error
            if e is not None and is_permission_error(e):
                asked = True
            set_status(r, T("keine Berechtigung", "no permission") if e is not None and is_permission_error(e) else T(f"Fehler: {e}", f"Error: {e}"), "red")
        update_next3()

    def valid_targets():
        return [r for r in rows if r["dev"] and r["dev"].connected]

    b_add = ctk.CTkButton(dev_bar, text=T("+ Gerät", "+ Device"), width=90, command=add_row)
    b_add.pack(side="left", padx=(0, 5))
    b_all = ctk.CTkButton(dev_bar, text=T("Alle erkannten", "All detected"), width=120, command=add_all_detected)
    b_all.pack(side="left", padx=5)
    b_conn = ctk.CTkButton(dev_bar, text=T("Alle verbinden", "Connect all"), width=120, command=connect_all)
    b_conn.pack(side="left", padx=5)
    ToolTip(b_add, T("Weiteres Gerät hinzufügen", "Add another device"))
    ToolTip(b_all, T("Alle angesteckten Geräte dieses Typs übernehmen", "Take all plugged-in devices of this type"))
    boot_info = ctk.CTkLabel(f3, text="", anchor="w", text_color="orange")
    boot_info.grid(row=3, column=0, sticky="w", padx=6, pady=(6, 0))
    next3_btn = nav(f3, 2, next_cmd=lambda: go(3))

    # Geraete, die schon im Bootloader stecken (ohne Einhaengen gezaehlt): die flasht Schritt 5 direkt
    def bootloader_count():
        if st.get("asset") and st["asset"].get("ext") == "hex":
            return len(nordic_bootloader_ports())
        if sys.platform.startswith("linux"):
            return sum(1 for d in find_usb_drives().values() if d.get("vid") == "239a")
        return len(uf2_drive_roots())

    def update_next3():
        n = bootloader_count()
        boot_info.configure(text=T(f"{n} Gerät(e) im Bootloader – werden in Schritt 5 direkt mitgeflasht", f"{n} device(s) in bootloader – will be flashed directly in step 5") if n else "")
        next3_btn.configure(state="normal" if valid_targets() or n else "disabled")

    def enter_devices():
        for r in list(rows):
            if r["dev"] and not role_matches(r["dev"].is_receiver):
                r["frame"].destroy()
                rows.remove(r)
        if not rows:
            add_all_detected()
            if not rows:
                add_row()
        update_next3()

    # ---------- 4: Flash-Methode ----------
    f4 = make_step(3, T("Flash-Methode", "Flash method"), T("Wie die Firmware auf das Gerät kommt", "How the firmware gets onto the device"))
    f4.grid_columnconfigure(0, weight=1)

    def enter_method():
        for w in f4.winfo_children():
            w.destroy()
        is_uf2 = st["asset"]["ext"] == "uf2"
        box = ctk.CTkFrame(f4, fg_color=FW_CARD, corner_radius=10)
        box.grid(row=0, column=0, sticky="ew", padx=6)
        method = tk.StringVar(value="uf2" if is_uf2 else "serial")
        ctk.CTkRadioButton(box, text=T("UF2-Laufwerk – Gerät startet in den Bootloader, die Datei wird kopiert", "UF2 drive – the device starts its bootloader, the file is copied"),
                           variable=method, value="uf2", state="normal" if is_uf2 else "disabled").pack(anchor="w", padx=12, pady=(10, 4))
        ctk.CTkRadioButton(box, text=T("Seriell (Nordic-Bootloader) – für .hex, z. B. Holyiot-, eByte-, Nordic-Dongle", "Serial (Nordic bootloader) – for .hex, e.g. Holyiot, eByte, Nordic dongle"),
                           variable=method, value="serial", state="disabled" if is_uf2 else "normal").pack(anchor="w", padx=12, pady=(4, 10))
        if st["role"] == "tracker":
            ctk.CTkCheckBox(box, text=T("Kopplungsdaten vorher löschen (danach neu koppeln)", "Clear pairing data first (pair again afterwards)"),
                            variable=clear_var).pack(anchor="w", padx=12, pady=(0, 10))
        nxt = nav(f4, 2, next_cmd=lambda: go(4), next_text=T("Weiter zum Flashen", "Continue to flashing"))
        nxt.configure(state="normal")
        if not is_uf2:
            hexbox = ctk.CTkFrame(f4, fg_color=FW_CARD, corner_radius=10)
            hexbox.grid(row=1, column=0, sticky="ew", padx=6, pady=(8, 0))
            ctk.CTkLabel(hexbox, text=(
                T("Beim HolyIOT-21017 bittet dich die App, den mitgelieferten Magneten an die LED zu halten. Andere "
                "Dongles schickt sie per „dfu“ in den Nordic-Bootloader, sonst von Hand (eByte: rechter Knopf · "
                "Nordic-Dongle: seitlicher Knopf). Die LED pulsiert dann, und die App überträgt die Firmware.\n"
                "Falls es nicht klappt, geht es weiterhin mit nRF Connect („Programmer“).", "For the HolyIOT-21017 the app asks you to hold the included magnet to the LED. Other"
                    " dongles are sent into the Nordic bootloader with “dfu”, otherwise by hand (eByte: right"
                    " button · Nordic dongle: side button). The LED then pulses and the app transfers the"
                    " firmware.\nIf it does not work, nRF Connect (“Programmer”) still works.")),
                anchor="w", justify="left", wraplength=700).pack(anchor="w", padx=12, pady=(10, 6))
            ctk.CTkButton(hexbox, text=T("Anleitung mit nRF Connect ↗", "Guide with nRF Connect ↗"),
                          command=lambda: webbrowser.open(
                              "https://docs.slimevr.dev/smol-slimes/firmware/smol-flashing-firmware.html")).pack(
                anchor="w", padx=12, pady=(0, 10))

    # ---------- 5: Flashen ----------
    f5 = make_step(4, T("Flashen", "Flash"), T("Firmware aufspielen", "Install firmware"))
    f5.grid_columnconfigure(0, weight=1)
    flash_ctl = {}

    def enter_flash():
        for w in f5.winfo_children():
            w.destroy()
        targets = valid_targets()
        src = st["asset"].get("src") or st["source"]
        version = st["asset"].get("tag") or T("eigene Datei", "own file")
        cmds, _ = collect_settings()
        extra = T(f"\nEinstellungen:  {len(cmds or [])} Befehl(e) nach dem Flashen", f"\nSettings:  {len(cmds or [])} command(s) after flashing") if cmds else ""
        box = ctk.CTkFrame(f5, fg_color=FW_CARD, corner_radius=10)
        box.grid(row=0, column=0, sticky="ew", padx=6)
        ctk.CTkLabel(box, text=T(f"Firmware:  {st['asset']['name']}\nQuelle:  {src['owner']} / {src['name']}  ·  {version}{extra}", f"Firmware:  {st['asset']['name']}\nSource:  {src['owner']} / {src['name']}  ·  {version}{extra}"),
                     anchor="w", justify="left").pack(anchor="w", padx=12, pady=(10, 6))
        for r in targets:
            r["status2"] = ctk.CTkLabel(box, text=T(f"{device_name(r['dev'])}: bereit", f"{device_name(r['dev'])}: ready"), anchor="w")
            r["status2"].pack(anchor="w", padx=24)
        # Schon im Bootloader steckende Geraete (UF2-Laufwerk bzw. Nordic-Bootloader) werden direkt mitgeflasht
        pre = []
        if st["asset"]["ext"] == "hex":
            for port in nordic_bootloader_ports():
                line = ctk.CTkFrame(box, fg_color="transparent")
                line.pack(anchor="w", padx=24)
                ctk.CTkLabel(line, text=T(f"Im Nordic-Bootloader ({port.device}):", f"In Nordic bootloader ({port.device}):"), anchor="w").pack(side="left")
                lbl = ctk.CTkLabel(line, text=T(" bereit – wird direkt beschrieben", " ready – will be written directly"), anchor="w")
                lbl.pack(side="left")
                pre.append({"nordic": port.device, "dev": None, "status": lbl, "status2": None,
                            "drive": {"serial": port.serial_number or "", "location": "", "root": ""}})
        for d in (bootloader_drives() if st["asset"]["ext"] == "uf2" else []):
            line = ctk.CTkFrame(box, fg_color="transparent")
            line.pack(anchor="w", padx=24)
            name = T(f"Im Bootloader ({d['serial'] or os.path.basename(d['root'].rstrip(os.sep)) or d['root']})", f"In bootloader ({d['serial'] or os.path.basename(d['root'].rstrip(os.sep)) or d['root']})")
            ctk.CTkLabel(line, text=f"{name}:", anchor="w").pack(side="left")
            lbl = ctk.CTkLabel(line, text=T(" bereit – wird direkt beschrieben", " ready – will be written directly"), anchor="w")
            lbl.pack(side="left")
            pre.append({"drive": d, "dev": None, "status": lbl, "status2": None})
        info = ctk.CTkLabel(f5, text="", anchor="w", text_color=FW_DIM)
        info.grid(row=1, column=0, sticky="ew", padx=6, pady=(8, 0))
        bar = ctk.CTkFrame(f5, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        back = ctk.CTkButton(bar, text=T("Zurück", "Back"), width=100, fg_color="transparent", border_width=1,
                             border_color=FW_SLATE, command=go_back)
        back.pack(side="left")
        start = ctk.CTkButton(bar, text=T("⬇ Flashen starten", "⬇ Start flashing"), width=180, fg_color="green", hover_color="#006400",
                              command=lambda: flash_start(targets, pre))
        start.pack(side="right")
        flash_ctl.update(info=info, start=start, back=back)

        # Solange nicht geflasht wird: pruefen, ob die Geraete noch dran sind (abgezogen -> Fehler statt nichts)
        watch_msgs = {"none": T("Kein Gerät verbunden – Gerät anstecken und in Schritt 3 verbinden.", "No device connected – plug one in and connect it in step 3.")}

        def watch():
            if not f5.winfo_exists() or cur["i"] != 4 or st["busy"] or not start.winfo_exists():
                return
            gone = [r for r in targets if not r["dev"].connected]
            for r in targets:
                if r.get("status2") is not None and r["status2"].winfo_exists():
                    ok = r["dev"].connected
                    r["status2"].configure(text=f"{device_name(r['dev'])}: " + (T("bereit", "ready") if ok else T("getrennt – abgezogen?", "disconnected – unplugged?")),
                                           text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"] if ok else "red")
            # Nur eigene Hinweise ueberschreiben, nicht z.B. "Abgebrochen" nach der Sicherheitsfrage
            own = info.cget("text") in ("", watch_msgs["none"]) or info.cget("text").endswith(T("übersprungen.", "skipped."))
            if (not targets or len(gone) == len(targets)) and not pre:
                info.configure(text=watch_msgs["none"], text_color="red")
                start.configure(state="disabled")
            else:
                if own:
                    if gone:
                        info.configure(text=T(f"{len(gone)} Gerät(e) getrennt, die werden übersprungen.", f"{len(gone)} device(s) disconnected, they will be skipped."), text_color="orange")
                    else:
                        info.configure(text="", text_color=FW_DIM)
                start.configure(state="normal")
            win.after(1000, watch)
        watch()

    def remember_choice():
        if st["source"]["repo"] is None:
            return
        settings.setdefault("fw_last", {})[st["role"]] = {
            "source": st["source"]["id"], "board": st["board"], "options": sorted(st["asset"]["options"]),
        }
        save_settings()

    def flash_start(targets, pre=()):
        targets = [r for r in targets if r["dev"] and r["dev"].connected]   # inzwischen abgezogene auslassen
        pre = [r for r in pre if (r.get("nordic") and any(p.device == r["nordic"] for p in nordic_bootloader_ports()))
               or (r["drive"]["root"] and os.path.isfile(os.path.join(r["drive"]["root"], "INFO_UF2.TXT")))]
        if st["busy"] or not (targets or pre):
            flash_ctl["info"].configure(text=T("Kein Gerät verbunden.", "No device connected."), text_color="red")
            return
        # Sicherung gegen falsche Firmware: Board der Datei mit dem Namen des Geraets vergleichen
        board = st["asset"].get("board") or st.get("board") or ""
        odd = [device_name(r["dev"]) for r in targets
               if (r["dev"].product and board and not guess_board(r["dev"].product, [board]))
               or not role_matches(r["dev"].is_receiver)]
        if odd:
            if not ask_yes_no(
                    T("Passt die Firmware?", "Does the firmware fit?"),
                    T(f"Die Datei ist für „{board.replace('_', ' ')}“ "
                    f"({'Dongle' if st['role'] == 'dongle' else 'Tracker'}), aber diese Geräte melden sich anders:\n", f"The file is for “{board.replace('_', ' ')}” ({'dongle' if st['role'] == 'dongle' else 'tracker'}"
                        "), but these devices report differently:\n")
                    + "\n".join(f"– {n}" for n in odd) + T("\n\nTrotzdem flashen?", "\n\nFlash anyway?"), default="no", parent=win):
                flash_ctl["info"].configure(text=T("Abgebrochen – Firmware passt evtl. nicht zum Gerät.", "Cancelled – the firmware may not fit the device."), text_color="orange")
                return
        cmds, err = collect_settings()
        if err:
            flash_ctl["info"].configure(text=T(f"Einstellungen: {err}", f"Settings: {err}"), text_color="red")
            return
        remember_choice()
        st["busy"] = True
        for b in (flash_ctl["start"], flash_ctl["back"], b_add, b_all, b_conn):
            b.configure(state="disabled")
        threading.Thread(target=flash_worker, args=(targets, dict(st["asset"]), clear_var.get(), cmds, pre),
                         daemon=True).start()

    # Schreibt die Einstellungen und zaehlt die Bestaetigungen ("Updated config")
    def apply_settings(r, cmds):
        dev = r["dev"]
        deadline = time.time() + 15
        while not dev.connected and time.time() < deadline:
            time.sleep(0.5)
        if not dev.connected:
            ui(lambda: set_status(r, T("fertig ✅, Einstellungen nicht übertragen (nicht verbunden)", "done ✅, settings not transferred (not connected)"), "orange"))
            return
        replies = []
        dev.listeners.append(replies.append)
        try:
            for cmd in cmds:
                ui(lambda c=cmd: send_command(c, dev))
                time.sleep(0.2)
            time.sleep(2)
        finally:
            dev.listeners.remove(replies.append)
        ok = sum(1 for line in replies if "Updated config" in line)
        writes = sum(1 for c in cmds if c.startswith("write_config"))
        if any("Unknown command" in line for line in replies):
            ui(lambda: set_status(r, T("fertig ✅, Firmware kennt keine Einstellungen", "done ✅, firmware does not support settings"), "orange"))
        elif ok >= writes:
            ui(lambda: set_status(r, T(f"fertig ✅, {writes} Einstellung(en) übernommen", f"done ✅, {writes} setting(s) applied"), "green"))
        else:
            ui(lambda: set_status(r, T(f"fertig ✅, nur {ok} von {writes} Einstellungen bestätigt", f"done ✅, only {ok} of {writes} settings confirmed"), "orange"))

    def flash_worker(targets, asset, clear, cmds, pre=()):
        info = flash_ctl["info"]
        try:
            fw_path = asset.get("path")
            if not fw_path:
                ui(lambda: info.configure(text=T("Lade Firmware…", "Downloading firmware…")))
                fw_path = os.path.join(tempfile.gettempdir(), asset["name"])
                response = requests.get(asset["url"], stream=True, timeout=30)
                response.raise_for_status()
                with open(fw_path, "wb") as f:
                    shutil.copyfileobj(response.raw, f)

            def enter_bootloader(r):
                dev = r["dev"]
                dev.paused = True
                replies = []
                dev.listeners.append(replies.append)
                try:
                    with ser_lock:
                        if clear and not dev.is_receiver:  # beim Dongle wuerde clear alle Kopplungen loeschen
                            dev.ser.write(b"clear\n")
                            time.sleep(0.5)
                        dev.ser.write(b"dfu\n")
                        dev.ser.flush()
                    ui(lambda: set_status(r, "Bootloader…"))
                    time.sleep(1.0)   # Antwort abwarten: Firmware ohne UF2-Unterstuetzung kennt dfu nicht
                except Exception as e:
                    ui(lambda e=e: set_status(r, T(f"dfu fehlgeschlagen: {e}", f"dfu failed: {e}"), "red"))
                finally:
                    if replies.append in dev.listeners:
                        dev.listeners.remove(replies.append)
                if any("Unknown command" in line for line in replies):
                    r["manual"] = True
                    ui(lambda: set_status(r, T("Firmware kennt „dfu“ nicht – bitte jetzt viermal schnell Reset drücken", "Firmware does not know “dfu” – please press reset four times quickly now"), "orange"))
                disconnect_device(dev)
                ui(refresh_sidebar)
                ui(sync_active)

            def copy_one(r, mount):
                try:
                    dest = os.path.join(mount, os.path.basename(fw_path))
                    with open(fw_path, "rb") as s, open(dest, "wb") as d:
                        shutil.copyfileobj(s, d)
                        d.flush()
                        os.fsync(d.fileno())
                except OSError:
                    pass  # Der Bootloader startet oft schon waehrend des Schliessens neu
                ui(lambda: set_status(r, T("geschrieben, startet neu…", "written, restarting…")))

            # Schluessel je Geraet: Seriennummer (gibt es auch unter Windows), sonst Steckplatz
            keys = {id(r): r["dev"].serial_number or r["dev"].location or f"#{i}" for i, r in enumerate(targets)}
            found = {}

            # .hex: ueber den Nordic-Bootloader (Seriell-DFU) uebertragen
            def fix_permissions_and_wait():
                result, ready = {}, threading.Event()

                def ask():
                    result["ok"] = fix_serial_permissions(win)
                    ready.set()
                ui(ask)
                ready.wait()
                time.sleep(1.0)   # udev setzt die Freigabe kurz danach
                return result.get("ok", False)

            def flash_nordic(r, port, retried=False):
                for d in devices:
                    if d.port == port:
                        d.paused = True
                        disconnect_device(d)

                def prog(done, total):
                    ui(lambda: set_status(r, T(f"überträgt … {done * 100 // total} %", f"transferring … {done * 100 // total} %")))
                try:
                    nordic_flash_hex(port, fw_path, prog)
                    ui(lambda: set_status(r, T("geschrieben, startet neu…", "written, restarting…")))
                    return True
                except Exception as e:
                    if not retried and is_permission_error(e):
                        ui(lambda: set_status(r, T("kein Zugriff auf den Bootloader – Freigabe wird eingerichtet…", "no access to the bootloader – setting up permission…"), "orange"))
                        if fix_permissions_and_wait():
                            return flash_nordic(r, port, retried=True)
                    ui(lambda e=e: set_status(r, T(f"Übertragung fehlgeschlagen: {e}", f"Transfer failed: {e}"), "red"))
                    return False

            def nordic_target(r):
                before = {p.device for p in nordic_bootloader_ports()}
                if "holyiot" in (r["dev"].product or "").lower():
                    # Der Holyiot kommt nur per Magnet in den Bootloader - kein dfu schicken, nur Anschluss freigeben
                    r["dev"].paused = True
                    disconnect_device(r["dev"])
                    ui(refresh_sidebar)
                    r["manual"] = True
                    hint = T("Bitte jetzt den mitgelieferten Magneten an die LED halten (die LED pulsiert dann)", "Please hold the included magnet to the LED now (the LED will pulse)")
                else:
                    enter_bootloader(r)
                    hint = (T("Bitte Bootloader von Hand starten: eByte – rechter Knopf, Nordic-Dongle – seitlicher Knopf, "
                            "HolyIOT – Magnet an die LED", "Please start the bootloader by hand: eByte – right button, Nordic dongle – side button,"
                        " HolyIOT – magnet to the LED"))
                asked, port, start = False, None, time.time()
                while port is None and time.time() < start + 90:
                    port = next((p.device for p in nordic_bootloader_ports() if p.device not in before), None)
                    if port is None and not asked and (r.get("manual") or time.time() > start + 5):
                        asked = True
                        ui(lambda: set_status(r, hint, "orange"))
                    time.sleep(0.5)
                if port is None:
                    ui(lambda: set_status(r, T("kein Nordic-Bootloader gefunden", "no Nordic bootloader found"), "red"))
                    return False
                time.sleep(1.0)   # Anschluss bereit werden lassen
                return flash_nordic(r, port)

            # Geraete, die schon im Bootloader stecken: Datei direkt aufs Laufwerk bzw. per Nordic-DFU
            confirmed = set()
            serials_before = {q.serial_number for q in serial.tools.list_ports.comports()}
            for i, r in enumerate(pre):
                key = r["drive"]["serial"] or r["drive"]["location"] or f"boot{i}"
                if r.get("nordic"):
                    if flash_nordic(r, r["nordic"]):
                        found[key] = r
                        confirmed.add(key)
                        ui(lambda rr=r: set_status(rr, T("fertig ✅ (vom Bootloader geprüft)", "done ✅ (verified by bootloader)"), "green"))
                        # Der Bootloader hat eine andere Seriennummer als die Firmware: den Stand unter der
                        # Seriennummer merken, mit der das Geraet gleich neu auftaucht
                        new_serial, until = None, time.time() + 20
                        while new_serial is None and time.time() < until:
                            new_serial = next((q.serial_number for q in serial.tools.list_ports.comports()
                                               if q.vid == 0x1209 and q.serial_number
                                               and q.serial_number not in serials_before), None)
                            time.sleep(1)
                        ui(lambda k=new_serial: remember_flash(k, asset, st["role"]))
                else:
                    found[key] = r
                    copy_one(r, r["drive"]["root"])

            if asset.get("ext") == "hex":
                for n, r in enumerate(targets, 1):
                    ui(lambda n=n: info.configure(text=T(f"Gerät {n} von {len(targets)}…", f"Device {n} of {len(targets)}…")))
                    if nordic_target(r):
                        found[keys[id(r)]] = r
            elif sys.platform.startswith("linux") and all(r["dev"].location for r in targets):
                # Linux: alle gleichzeitig, Laufwerk und Tracker ueber den USB-Steckplatz zuordnen
                before = set(find_usb_drives())
                for r in targets:
                    enter_bootloader(r)
                ui(lambda: info.configure(text=T("Warte auf die UF2-Laufwerke…", "Waiting for the UF2 drives…")))
                by_loc = {r["dev"].location: r for r in targets}
                mounts = {}
                deadline = time.time() + (60 if any(r.get("manual") for r in targets) else 30)
                while time.time() < deadline and len(mounts) < len(by_loc):
                    for name, d in find_usb_drives().items():
                        if name in before or d["location"] in mounts or d["location"] not in by_loc:
                            continue
                        mount = mount_drive(d)
                        if mount and os.path.isfile(os.path.join(mount, "INFO_UF2.TXT")):
                            mounts[d["location"]] = mount
                    time.sleep(1)
                ui(lambda: info.configure(text=T("Schreibe Firmware…", "Writing firmware…")))
                copies = []
                seen = {d["location"]: d for d in find_usb_drives().values()}
                for loc, r in by_loc.items():
                    if loc in mounts:
                        found[keys[id(r)]] = r
                        t = threading.Thread(target=copy_one, args=(r, mounts[loc]), daemon=True)
                        t.start()
                        copies.append(t)
                    elif loc in seen:
                        err = next((mount_errors[d] for d in seen[loc]["devs"] if d in mount_errors), "")
                        ui(lambda rr=r, err=err: set_status(rr, T(f"UF2-Laufwerk da, aber Einhängen nicht erlaubt ({err})", f"UF2 drive present, but mounting not allowed ({err})"), "red"))
                    else:
                        ui(lambda rr=r: set_status(rr, T("kein UF2-Laufwerk gefunden", "no UF2 drive found"), "red"))
                for t in copies:
                    t.join()
            else:
                # Windows/macOS (oder Steckplatz unbekannt): einer nach dem anderen,
                # das jeweils neu auftauchende UF2-Laufwerk gehoert zum gerade gestarteten Tracker
                for n, r in enumerate(targets, 1):
                    ui(lambda n=n: info.configure(text=T(f"Tracker {n} von {len(targets)}…", f"Tracker {n} of {len(targets)}…")))
                    before = set(uf2_drive_roots())
                    enter_bootloader(r)
                    root, deadline = None, time.time() + (60 if r.get("manual") else 30)
                    while root is None and time.time() < deadline:
                        root = next((d for d in uf2_drive_roots() if d not in before), None)
                        time.sleep(0.5)
                    if root is None:
                        ui(lambda rr=r: set_status(rr, T("kein UF2-Laufwerk gefunden", "no UF2 drive found"), "red"))
                        continue
                    found[keys[id(r)]] = r
                    copy_one(r, root)
                    # warten, bis das Laufwerk weg ist, sonst haelt der naechste Tracker es fuer seins
                    deadline = time.time() + 15
                    while root in uf2_drive_roots() and time.time() < deadline:
                        time.sleep(0.5)

            # Erfolg = das Geraet meldet sich mit neuer Firmware wieder als Port
            waiting = {k: r for k, r in found.items() if k not in confirmed}
            deadline = time.time() + 30
            while waiting and time.time() < deadline:
                for p in serial.tools.list_ports.comports():
                    if p.vid == 0x239A or (p.vid, p.pid) == NORDIC_DFU_ID:
                        continue   # noch im Bootloader
                    for key in (p.serial_number, (p.location or "").split(":")[0]):
                        r = waiting.pop(key, None) if key else None
                        if r:
                            ui(lambda rr=r: set_status(rr, T("fertig ✅", "done ✅"), "green"))
                            stored = (r["dev"].key if r.get("dev") else "") or p.serial_number
                            ui(lambda k=stored: remember_flash(k, asset, st["role"]))
                time.sleep(1)
            for r in waiting.values():
                ui(lambda rr=r: set_status(rr, T("geschrieben, aber nicht zurückgemeldet", "written, but did not report back"), "orange"))

            if cmds:
                done_rows = [r for key, r in found.items() if key not in waiting and r.get("dev")]
                for r in done_rows:
                    r["dev"].paused = False  # damit watch_devices sie wieder verbindet
                ui(lambda: info.configure(text=T("Übertrage Einstellungen…", "Transferring settings…")))
                workers = [threading.Thread(target=apply_settings, args=(r, cmds), daemon=True) for r in done_rows]
                for t in workers:
                    t.start()
                for t in workers:
                    t.join()

            total = len(targets) + len(pre)
            ok = len(found) - len(waiting)
            ui(lambda: info.configure(text=T(f"{ok} von {total} fertig.", f"{ok} of {total} done."),
                                      text_color="green" if ok == total else "orange"))
            ui(lambda: append_text(T(f"Firmware-Tool: {ok} von {total} Geräten mit {asset['name']} geflasht.\n", f"Firmware tool: {ok} of {total} devices flashed with {asset['name']}.\n"), "success"))
        except Exception as e:
            ui(lambda e=e: info.configure(text=T(f"Fehler: {e}", f"Error: {e}"), text_color="red"))
        finally:
            for r in targets:
                r["dev"].paused = False  # watch_devices verbindet sie wieder
            st["busy"] = False

            def done():
                for b in (flash_ctl["back"], b_add, b_all, b_conn):
                    b.configure(state="normal")
                flash_ctl["start"].configure(state="normal", text=T("Nochmal flashen", "Flash again"))
            ui(done)

    def go(i):
        cur["i"] = i
        for j, s in enumerate(steps):
            if j == i:
                s["circle"].configure(text=str(j + 1), fg_color=FW_PURPLE)
                s["sub"].grid(row=1, column=1, sticky="w")
                s["frame"].grid(row=2, column=1, sticky="ew", pady=(8, 4), padx=(0, 10))
            else:
                s["circle"].configure(text="✓" if j < i else str(j + 1), fg_color=FW_GREEN if j < i else FW_SLATE)
                s["sub"].grid_forget()
                s["frame"].grid_forget()
        enter = [None, enter_config, enter_devices, enter_method, enter_flash][i]
        if enter:
            enter()

    def on_close():
        if st["busy"]:
            return
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)
    go(0)
    if role:
        set_role(role)
    src_id = settings.get("fw_last", {}).get(st["role"], {}).get("source", "main")
    select_source(next((s for s in fw_sources() if s["id"] == src_id and s["id"] != "all"), fw_sources()[0]))

# ---------- Nordic Serial DFU ("Open DFU Bootloader", z.B. Holyiot-/eByte-/Nordic-Dongle) ----------
# Nachgebaut nach Nordics pc-nrfutil (BSD-Lizenz): nordicsemi/dfu/dfu_transport_serial.py, package.py,
# nrfhex.py und dfu-cc.proto. Reines Python, damit es ohne nRF Connect/nrfutil unter Linux und Windows laeuft.
NORDIC_DFU_ID = (0x1915, 0x521F)   # USB-Kennung des Nordic-Bootloaders

class NordicDfuError(Exception):
    pass

NORDIC_RES = {0x00: "InvalidCode", 0x02: "NotSupported", 0x03: "InvalidParameter", 0x04: "InsufficientResources",
              0x05: "InvalidObject", 0x06: "InvalidSignature", 0x07: "UnsupportedType",
              0x08: "OperationNotPermitted", 0x0A: "OperationFailed"}
NORDIC_EXT = {0x05: T("Firmware-Version zu niedrig", "Firmware version too low"), 0x06: T("Hardware-Version passt nicht", "Hardware version does not match"),
              0x07: T("SoftDevice-Anforderung passt nicht", "SoftDevice requirement does not match"), 0x08: T("Signatur erforderlich", "Signature required"),
              0x0C: T("Prüfsumme der Firmware passt nicht", "Firmware checksum does not match"), 0x0D: T("zu wenig Platz", "not enough space")}

# Intel-HEX -> Binaerdaten wie nrfhex: ohne MBR (< 0x1000) und UICR (>= 0x10000000), Luecken 0xFF,
# Laenge auf ganze 4-Byte-Woerter aufgerundet
def hex_to_app_bin(path):
    data, base = {}, 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line.startswith(":"):
                continue
            raw = bytes.fromhex(line[1:])
            addr, rtype, payload = int.from_bytes(raw[1:3], "big"), raw[3], raw[4:4 + raw[0]]
            if rtype == 0x00:
                for i, b in enumerate(payload):
                    data[base + addr + i] = b
            elif rtype == 0x02:
                base = int.from_bytes(payload, "big") << 4
            elif rtype == 0x04:
                base = int.from_bytes(payload, "big") << 16
            elif rtype == 0x01:
                break
    data = {a: b for a, b in data.items() if 0x1000 <= a < 0x10000000}
    if not data:
        raise NordicDfuError(T("Die .hex-Datei enthält keine Anwendung", "The .hex file contains no application"))
    lo, hi = min(data), max(data)
    size = ((hi - lo + 1) + 3) // 4 * 4
    out = bytearray(b"\xff" * size)
    for a, b in data.items():
        out[a - lo] = b
    return bytes(out)

def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)

def _field(num, wire, payload):
    tag = _varint((num << 3) | wire)
    return tag + (_varint(payload) if wire == 0 else _varint(len(payload)) + payload)

# Init-Paket (dfu-cc.proto): Packet{command{op_code=INIT, init{...}}}, unsigniert wie fuer den offenen Bootloader
def nordic_init_packet(app_bin, fw_version=1, hw_version=52, sd_req=(0x00,)):
    digest = hashlib.sha256(app_bin).digest()[::-1]   # nrfutil legt den Hash byteweise umgedreht ab
    hash_msg = _field(1, 0, 3) + _field(2, 2, digest)  # SHA256
    init = (_field(1, 0, fw_version) + _field(2, 0, hw_version)
            + _field(3, 2, b"".join(_varint(x) for x in sd_req))
            + _field(4, 0, 0)            # APPLICATION
            + _field(5, 0, 0) + _field(6, 0, 0) + _field(7, 0, len(app_bin))
            + _field(8, 2, hash_msg) + _field(9, 0, 0))
    command = _field(1, 0, 1) + _field(2, 2, init)   # op_code INIT
    return _field(1, 2, command)

def _slip(data):
    out = bytearray()
    for b in data:
        out += b"\xdb\xdc" if b == 0xC0 else b"\xdb\xdd" if b == 0xDB else bytes([b])
    return bytes(out + b"\xc0")

class NordicDfu:
    def __init__(self, port, progress=None):
        self.ser = serial.Serial(port, 115200, rtscts=True, timeout=1.0)
        self.progress = progress or (lambda done, total: None)
        self.mtu = 0

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    def _read(self, timeout=5.0):
        buf, esc, deadline = bytearray(), False, time.time() + timeout
        while time.time() < deadline:
            b = self.ser.read(1)
            if not b:
                continue
            c = b[0]
            if c == 0xC0:
                if buf:
                    return bytes(buf)
                continue
            if esc:
                buf.append(0xC0 if c == 0xDC else 0xDB)
                esc = False
            elif c == 0xDB:
                esc = True
            else:
                buf.append(c)
        return None

    def _cmd(self, payload, timeout=5.0, size=None):
        self.ser.write(_slip(payload))
        resp = self._read(timeout)
        if size is not None and resp and resp[2:3] == b"\x01" and len(resp) - 3 != size:
            raise NordicDfuError(T(f"unerwartete Antwort auf Befehl 0x{payload[0]:02X} – liest ein anderes Programm "
                                 "am Anschluss mit?", f"unexpected reply to command 0x{payload[0]:02X} – is another program reading the port?"))
        if not resp or resp[0] != 0x60 or resp[1] != payload[0]:
            raise NordicDfuError(T(f"keine passende Antwort auf Befehl 0x{payload[0]:02X}", f"no matching reply to command 0x{payload[0]:02X}"))
        if resp[2] == 0x0B:
            raise NordicDfuError(NORDIC_EXT.get(resp[3], T(f"erweiterter Fehler 0x{resp[3]:02X}", f"extended error 0x{resp[3]:02X}")), resp[3])
        if resp[2] != 0x01:
            raise NordicDfuError(NORDIC_RES.get(resp[2], T(f"Fehler 0x{resp[2]:02X}", f"error 0x{resp[2]:02X}")))
        return resp[3:]

    # Wie nrfutil "dfu usb-serial": 3 s warten, kein Ping (aeltere Nordic-Bootloader kennen ihn nicht),
    # dann Bestaetigungen aus und MTU erfragen
    def connect(self):
        time.sleep(3.0)
        self.ser.reset_input_buffer()
        self._cmd(bytes([0x02]) + struct.pack("<H", 0))            # PRN aus
        self.mtu = struct.unpack("<H", self._cmd(bytes([0x07]), size=2))[0]

    def _stream(self, data, crc, offset):
        chunk = (self.mtu - 1) // 2 - 1
        for i in range(0, len(data), chunk):
            part = data[i:i + chunk]
            self.ser.write(_slip(bytes([0x08]) + part))
            crc = binascii.crc32(part, crc) & 0xFFFFFFFF
            offset += len(part)
        got_offset, got_crc = struct.unpack("<II", self._cmd(bytes([0x03]), size=8))
        if got_offset != offset or got_crc != crc:
            raise NordicDfuError(T("Prüfsumme der Übertragung stimmt nicht", "Transfer checksum does not match"))
        return crc, offset

    def send(self, init_packet, app_bin):
        max_size = struct.unpack("<III", self._cmd(bytes([0x06, 0x01]), size=12))[0]
        if len(init_packet) > max_size:
            raise NordicDfuError(T("Init-Paket zu groß", "Init packet too large"))
        self._cmd(bytes([0x01, 0x01]) + struct.pack("<L", len(init_packet)))
        self._stream(init_packet, 0, 0)
        self._cmd(bytes([0x04]))                                       # Init-Paket pruefen lassen
        max_size = struct.unpack("<III", self._cmd(bytes([0x06, 0x02]), size=12))[0]
        crc = 0
        for i in range(0, len(app_bin), max_size):
            obj = app_bin[i:i + max_size]
            self._cmd(bytes([0x01, 0x02]) + struct.pack("<L", len(obj)))
            crc, _ = self._stream(obj, crc, i)
            self._cmd(bytes([0x04]), timeout=15.0)                     # Block ins Flash schreiben
            self.progress(i + len(obj), len(app_bin))

# Ganze Uebertragung: .hex -> Init-Paket + Daten -> Bootloader. Ist die Version zu niedrig (der Bootloader
# verbietet Rueckschritte), einmal mit der hoechsten Version wiederholen.
def nordic_flash_hex(port, hex_path, progress=None):
    app_bin = hex_to_app_bin(hex_path)
    for fw_version in (1, 0xFFFFFFFF):
        dfu = NordicDfu(port, progress)
        try:
            dfu.connect()
            dfu.send(nordic_init_packet(app_bin, fw_version=fw_version), app_bin)
            return
        except NordicDfuError as e:
            if len(e.args) > 1 and e.args[1] == 0x05 and fw_version == 1:
                continue
            raise
        finally:
            dfu.close()

def nordic_bootloader_ports():
    return [p for p in serial.tools.list_ports.comports() if (p.vid, p.pid) == NORDIC_DFU_ID]

# Firmware-Stand je Geraet: was die App zuletzt draufgeflasht hat. Grundlage fuer "Update verfuegbar".
def de_date(iso):   # deutsch TT.MM.JJJJ, englisch JJJJ-MM-TT
    if len(iso) < 10:
        return iso or "?"
    return T(f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}", iso[:10])

def remember_flash(key, asset, role):
    if not key or not asset.get("src") or not asset["src"].get("repo"):
        return   # eigene Datei: keine Quelle, die man spaeter wieder fragen koennte
    settings.setdefault("flashed", {})[key] = {
        "source": asset["src"]["id"], "repo": asset["src"]["repo"], "board": asset.get("board", ""),
        "options": sorted(asset.get("options", ())), "name": asset["name"], "date": asset.get("date", ""),
        "tag": asset.get("tag", ""), "role": role, "when": time.strftime("%Y-%m-%d %H:%M"),
    }
    save_settings()

# ---------- Geraeteverwaltung ----------
# Uebersicht ueber alle bekannten Geraete. Firmware, Board, Sensor, Akku und Kopplung
# kommen aus der Antwort auf "info"; Einstellungen werden per read_config/write_config
# gelesen und geschrieben, ohne neu zu flashen.
dev_win = None
dev_details = {}   # dev.key -> {"fw", "board", "imu", "battery", "paired"}
dev_updates = {}   # dev.key -> ("aktuell"|"update"|"weg"|"fehler", neues Datum)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Schickt Befehle und sammelt die Antwortzeilen. Nur aus einem Hintergrund-Thread aufrufen.
def query_device(dev, cmds, wait=1.5):
    lines = []
    dev.listeners.append(lines.append)
    try:
        for c in cmds:
            app.after(0, lambda c=c: send_command(c, dev))
            time.sleep(0.2)
        time.sleep(wait)
    finally:
        dev.listeners.remove(lines.append)
    return [ANSI_RE.sub("", line).strip() for line in lines]

def parse_info(lines):
    d = {}
    for line in lines:
        m = re.match(r"^(SlimeVR-\S+)\s+(\S+)", line)
        if m:
            d["fw"] = f"{m.group(1)} {m.group(2)}"
        for key, label in (("board", "Board"), ("imu", "IMU"), (T("gekoppelt", "paired"), "Tracker ID")):
            if line.startswith(label + ": "):
                d[key] = line[len(label) + 2:]
        m = re.match(r"^Battery: ([\d.]+)%", line)
        if m:
            d["battery"] = f"{float(m.group(1)):.0f} %"
    return d

def open_device_manager():
    global dev_win
    if dev_win is not None and dev_win.winfo_exists():
        dev_win.focus()
        return
    win = ctk.CTkToplevel(app, fg_color=FW_BG)
    dev_win = win
    win.title(T("Geräteverwaltung", "Device Manager"))
    win.geometry("1000x660")
    win.transient(app)

    head = ctk.CTkFrame(win, fg_color="transparent")
    head.pack(fill="x", padx=20, pady=(16, 4))
    ctk.CTkLabel(head, text=T("Geräteverwaltung", "Device Manager"), font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
    ctk.CTkLabel(head, text=T("Alle Dongles und Tracker auf einen Blick", "All dongles and trackers at a glance"), text_color=FW_DIM).pack(anchor="w")

    bar = ctk.CTkFrame(win, fg_color="transparent")
    bar.pack(fill="x", padx=16, pady=(8, 4))
    listbox = ctk.CTkScrollableFrame(win, fg_color="transparent")
    listbox.pack(fill="both", expand=True, padx=10, pady=4)
    status = ctk.CTkLabel(win, text="", anchor="w", text_color=FW_DIM)
    status.pack(fill="x", padx=20, pady=(0, 10))
    state = {"sig": None}

    def say(text, color=None):
        status.configure(text=text, text_color=color or FW_DIM)

    def connect_plugged():
        asked = False
        n = 0
        for p in serial.tools.list_ports.comports():
            if p.vid != 0x1209:   # pid.codes: SlimeNRF-Dongles und -Tracker
                continue
            dev = get_or_add_device(p)
            dev.manual_off = False
            if dev.connected or connect_device(dev, ask=not asked, parent=win):
                n += 1
            elif dev.last_error is not None and is_permission_error(dev.last_error):
                asked = True
        say(T(f"{n} Gerät(e) verbunden.", f"{n} device(s) connected.") if n else T("Keine SlimeNRF-Geräte angesteckt.", "No SlimeNRF devices plugged in."))
        render(force=True)

    def fetch_info(targets=None):
        targets = [d for d in (targets or devices) if d.connected]
        if not targets:
            say(T("Kein Gerät verbunden.", "No device connected."), "orange")
            return
        say(T("Frage Info und Akku ab…", "Querying info and battery…"))

        def work(dev):
            dev_details.setdefault(dev.key, {}).update(parse_info(query_device(dev, ["info"])))
        threads = [threading.Thread(target=work, args=(d,), daemon=True) for d in targets]
        for t in threads:
            t.start()

        def wait():
            for t in threads:
                t.join()
            app.after(0, lambda: (say(T(f"Info von {len(targets)} Gerät(en) aktualisiert.", f"Info of {len(targets)} device(s) updated.")), render(force=True)))
        threading.Thread(target=wait, daemon=True).start()

    def show_paired():
        dongle = next((d for d in devices if d.is_dongle and d.connected), None) \
            or next((d for d in devices if d.is_receiver and d.connected), None)
        if not dongle:
            say(T("Kein Dongle verbunden.", "No dongle connected."), "orange")
            return
        say(T("Frage den Dongle nach gekoppelten Trackern…", "Asking the dongle for paired trackers…"))

        def work():
            lines = [l for l in query_device(dongle, ["list"]) if l and not l.startswith(">>>") and not l.startswith("[")]
            app.after(0, lambda: show_lines(T("Gekoppelte Tracker", "Paired trackers"), lines or [T("Keine Antwort vom Dongle.", "No reply from the dongle.")]))
        threading.Thread(target=work, daemon=True).start()

    def show_lines(title, lines):
        say("")
        pop = ctk.CTkToplevel(win, fg_color=FW_BG)
        pop.title(title)
        pop.geometry("520x380")
        pop.transient(win)
        box = ctk.CTkTextbox(pop)
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("end", "\n".join(lines))
        box.configure(state="disabled")

    for text, cmd, tip in (
        (T("Alle angesteckten verbinden", "Connect all plugged in"), connect_plugged, T("Verbindet alle angesteckten SlimeNRF-Geräte", "Connects all plugged-in SlimeNRF devices")),
        (T("Info + Akku abrufen", "Get info + battery"), lambda: fetch_info(), T("Fragt bei allen verbundenen Geräten „info“ ab", "Sends “info” to all connected devices")),
        (T("Gekoppelte Tracker", "Paired trackers"), show_paired, T("Fragt den Dongle mit „list“, welche Tracker er kennt", "Asks the dongle with “list” which trackers it knows")),
    ):
        b = ctk.CTkButton(bar, text=text, command=cmd)
        b.pack(side="left", padx=4)
        ToolTip(b, tip)
    b = ctk.CTkButton(bar, text=T("🔗 Alle koppeln", "🔗 Pair all"), command=pair_all, fg_color=FW_PURPLE, hover_color=FW_PURPLE_H,
                      text_color="white")
    b.pack(side="right", padx=4)
    ToolTip(b, T("Dongle und alle verbundenen Tracker gleichzeitig in den Kopplungsmodus", "Put the dongle and all connected trackers into pairing mode at once"))

    def render(force=False):
        sig = tuple((d.key, d.connected, device_name(d), d.is_dongle, d.port) for d in devices) + \
            tuple((k, tuple(sorted(v.items()))) for k, v in sorted(dev_details.items()))
        if sig == state["sig"] and not force:
            return
        state["sig"] = sig
        for w in listbox.winfo_children():
            w.destroy()
        if not devices:
            ctk.CTkLabel(listbox, text=T("Noch keine Geräte. Stecke Dongle oder Tracker an und drücke "
                                       "„Alle angesteckten verbinden“.", "No devices yet. Plug in a dongle or tracker and press “Connect all plugged in”."), text_color=FW_DIM).pack(pady=30)
            return
        for dev in sorted(devices, key=lambda d: (not d.is_dongle, not d.is_receiver, d.number)):
            card = ctk.CTkFrame(listbox, fg_color=FW_CARD, corner_radius=10)
            card.pack(fill="x", padx=6, pady=4)
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(10, 0))
            ctk.CTkLabel(top, text=device_name(dev), font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
            kind = "Dongle" if dev.is_receiver else "Tracker"
            ctk.CTkLabel(top, text=f" {kind} ", corner_radius=6, height=20, text_color="white",
                         fg_color=FW_PURPLE if dev.is_receiver else FW_SLATE,
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=8)
            ctk.CTkLabel(top, text=T("● verbunden", "● connected") if dev.connected else T("○ getrennt", "○ disconnected"),
                         text_color="green" if dev.connected else "gray55").pack(side="left", padx=4)

            d = dev_details.get(dev.key, {})
            facts = [f"Port: {dev.port}", T(f"Seriennummer: {dev.serial_number or '–'}", f"Serial number: {dev.serial_number or '–'}")]
            for key, label in (("fw", "Firmware"), ("board", "Board"), ("imu", "Sensor"), ("battery", T("Akku", "Battery"))):
                if d.get(key):
                    facts.append(f"{label}: {d[key]}")
            if T("gekoppelt", "paired") in d and not dev.is_receiver:
                facts.append(T("gekoppelt", "paired") if d[T("gekoppelt", "paired")] != "None" else T("nicht gekoppelt", "not paired"))
            ctk.CTkLabel(card, text="   ·   ".join(facts), text_color=FW_DIM, anchor="w", justify="left",
                         wraplength=900).pack(fill="x", padx=12, pady=(2, 6))

            # Firmware-Stand aus dem letzten Flashen ueber die App
            fl = settings.get("flashed", {}).get(dev.key)
            stand = ctk.CTkFrame(card, fg_color="transparent")
            stand.pack(fill="x", padx=12, pady=(0, 6))
            if not fl:
                ctk.CTkLabel(stand, text=T("Firmware-Stand unbekannt – nach dem ersten Flashen über das DIY "
                                         "Firmware-Tool merkt sich die App ihn", "Firmware state unknown – the app remembers it after the first flash with the DIY Firmware"
                    " Tool"), text_color=FW_DIM).pack(side="left")
            else:
                ctk.CTkLabel(stand, text=T(f"Geflasht: {fl['name']} vom {de_date(fl['date'])} "
                                         f"({fl['source']}, {fl['tag']})", f"Flashed: {fl['name']} from {de_date(fl['date'])} ({fl['source']}, {fl['tag']})"), text_color=FW_DIM).pack(side="left")
                upd, newdate = dev_updates.get(dev.key, ("", ""))
                text, color = {"aktuell": (T("✓ aktuell", "✓ up to date"), "green"),
                               "update": (T(f"⬆ Update verfügbar (neu vom {de_date(newdate)})", f"⬆ Update available (new from {de_date(newdate)})"), "orange"),
                               "weg": (T("Datei gibt es in der Quelle nicht mehr", "File no longer exists in the source"), "orange"),
                               "fehler": (T("Update-Prüfung fehlgeschlagen", "Update check failed"), "red")}.get(upd, (T("prüfe …", "checking …"), None))
                ctk.CTkLabel(stand, text=f"   {text}", text_color=color or FW_DIM).pack(side="left")
                if upd == "update":
                    ctk.CTkButton(stand, text="Update…", width=90, fg_color=FW_PURPLE, hover_color=FW_PURPLE_H,
                                  text_color="white", command=lambda f=fl: open_update(f)).pack(side="left", padx=8)

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=(0, 10))

            def toggle(dev=dev):
                if dev.connected:
                    dev.manual_off = True
                    device_lost(dev, T("Getrennt.\n", "Disconnected.\n"))
                else:
                    dev.manual_off = False
                    connect_device(dev, parent=win)
                render(force=True)
            buttons = [
                (T("Trennen", "Disconnect") if dev.connected else T("Verbinden", "Connect"), toggle),
                (T("Umbenennen", "Rename"), lambda dev=dev: rename_device(dev)),
            ]
            if dev.is_dongle:
                buttons.append((T("Dongle aufheben", "Unset dongle"), lambda: set_dongle(None)))
            elif dev.serial_number and dev.is_receiver:
                buttons.append((T("Als Dongle festlegen", "Set as dongle"), lambda dev=dev: set_dongle(dev)))
            if dev.connected:
                buttons.append((T("Info abrufen", "Get info"), lambda dev=dev: fetch_info([dev])))
                if not dev.is_receiver:
                    buttons.append((T("Einstellungen", "Settings"), lambda dev=dev: open_device_settings(dev, win)))
            buttons.append((T("Entfernen", "Remove"), lambda dev=dev: (remove_device(dev), render(force=True))))
            for text, cmd in buttons:
                ctk.CTkButton(row, text=text, width=110, command=cmd).pack(side="left", padx=4)

    # Gespeicherte Staende mit der jeweiligen Quelle vergleichen (gleiche Datei, neueres Datum?)
    def check_updates():
        def work():
            for key, fl in list(settings.get("flashed", {}).items()):
                try:
                    rels = fetch_releases(fl["repo"])
                    rel = next((r for r in rels if r.get("stable")), rels[0] if rels else None)
                    if rel is not None and rel["assets"] is None:
                        rel["assets"] = fetch_release_assets(fl["repo"], rel["tag"])
                    match = next((a for a in (rel["assets"] if rel else []) if a["name"] == fl["name"]), None)
                    if match is None:
                        dev_updates[key] = ("weg", "")
                    elif match.get("date", "") > fl.get("date", ""):
                        dev_updates[key] = ("update", match["date"])
                    else:
                        dev_updates[key] = ("aktuell", match.get("date", ""))
                except Exception:
                    dev_updates[key] = ("fehler", "")
            app.after(0, lambda: render(force=True) if win.winfo_exists() else None)
        threading.Thread(target=work, daemon=True).start()

    def open_update(fl):
        if multi_win is not None and multi_win.winfo_exists():
            multi_win.destroy()   # mit der Auswahl dieses Geraets neu oeffnen
        settings.setdefault("fw_last", {})[fl["role"]] = {"source": fl["source"], "board": fl["board"],
                                                        "options": fl["options"]}
        open_multiflash_window(role=fl["role"])

    def tick():
        if not win.winfo_exists():
            return
        render()
        win.after(1500, tick)

    tick()
    check_updates()

# Einstellungen eines Trackers lesen und aendern, ohne neu zu flashen
def open_device_settings(dev, parent):
    w = ctk.CTkToplevel(parent, fg_color=FW_BG)
    w.title(T(f"Einstellungen – {device_name(dev)}", f"Settings – {device_name(dev)}"))
    w.geometry("860x700")
    w.transient(parent)
    head = ctk.CTkFrame(w, fg_color="transparent")
    head.pack(fill="x", padx=20, pady=(16, 4))
    ctk.CTkLabel(head, text=T(f"Einstellungen – {device_name(dev)}", f"Settings – {device_name(dev)}"), font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
    ctk.CTkLabel(head, text=T("Direkt im Tracker gespeichert, ohne neu zu flashen", "Saved directly in the tracker, without reflashing"), text_color=FW_DIM).pack(anchor="w")
    body = ctk.CTkScrollableFrame(w, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=10, pady=4)
    status = ctk.CTkLabel(w, text=T("Lese Einstellungen…", "Reading settings…"), anchor="w", text_color=FW_DIM)
    status.pack(fill="x", padx=20)
    bar = ctk.CTkFrame(w, fg_color="transparent")
    bar.pack(fill="x", padx=16, pady=(4, 12))
    widgets = {}
    current = {}

    def read(done_msg=None):
        for c in body.winfo_children():
            c.destroy()
        status.configure(text=T("Lese Einstellungen…", "Reading settings…"), text_color=FW_DIM)

        def work():
            values = {}
            for line in query_device(dev, ["info", "read_config all"], wait=2.0):
                m = re.match(r"^Read config: (\w+)=(-?\d+)", line)
                if m:
                    values[m.group(1)] = int(m.group(2))
                elif line.startswith("Target: "):
                    current["__target__"] = line[len("Target: "):]
            app.after(0, lambda: build(values, done_msg))
        threading.Thread(target=work, daemon=True).start()

    def build(values, done_msg=None):
        target = current.get("__target__", "")
        current.clear()
        current.update(values)
        rgb = target_has_rgb(target) if target else None
        widgets.clear()
        if not values:
            status.configure(text=T("Keine Antwort auf „read_config“ – diese Firmware kennt keine Einstellungen "
                                  "oder der Tracker ist nicht verbunden.", "No reply to “read_config” – this firmware does not support settings or the tracker is not"
                " connected."), text_color="orange")
            return
        holder = ctk.CTkFrame(body, fg_color=FW_CARD, corner_radius=10)
        holder.pack(fill="x", padx=6, pady=4)
        row = 0
        for group, items in FW_SETTINGS:
            if not any(n in values or (k == "color" and "led_default_color_r" in values and rgb is not False)
                       for n, _, k, *_ in items):
                continue  # Gruppe, die diese Firmware nicht kennt, gar nicht erst anzeigen
            ctk.CTkLabel(holder, text=group, font=ctk.CTkFont(size=14, weight="bold"), anchor="w").grid(
                row=row, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 2))
            row += 1
            for name, label, kind, default, unit, factor, help_text in items:
                if kind == "color":
                    # Farbe nur bei Boards mit Farb-LED (Stacked Smol/Normal haben nur die einfarbige)
                    if not all(f"led_default_color_{c}" in values for c in "rgb") or rgb is False:
                        continue
                elif name not in values:
                    continue
                label_with_help(holder, row, label, help_text, padx=24).grid(
                    row=row, column=0, sticky="w", padx=(24, 8), pady=(4, 0))
                cell = ctk.CTkFrame(holder, fg_color="transparent")
                cell.grid(row=row, column=1, sticky="w", pady=(4, 0))
                if kind == "bool":
                    wdg = ctk.CTkSegmentedButton(cell, values=[T("An", "On"), T("Aus", "Off")])
                    wdg.set(T("An", "On") if values[name] else T("Aus", "Off"))
                    wdg.pack(side="left")
                elif kind == "enum":
                    wdg = ctk.CTkSegmentedButton(cell, values=list(factor.values()))
                    wdg.set(factor.get(values[name], list(factor.values())[0]))
                    wdg.pack(side="left")
                elif kind == "int":
                    wdg = ctk.CTkEntry(cell, width=100)
                    shown = values[name] / factor
                    wdg.insert(0, str(int(shown)) if float(shown).is_integer() else f"{shown:.2f}")
                    wdg.pack(side="left")
                    ctk.CTkLabel(cell, text=unit, text_color=FW_DIM).pack(side="left", padx=6)
                else:
                    rgb = [round(values[f"led_default_color_{c}"] * 255 / 10000) for c in "rgb"]
                    wdg = {"rgb": rgb}
                    hexc = "#%02x%02x%02x" % tuple(rgb)
                    sw = ctk.CTkButton(cell, text=hexc, width=130, fg_color=hexc)

                    def pick(wdg=wdg, sw=sw):
                        from tkinter import colorchooser
                        c = colorchooser.askcolor(parent=w, title=T("LED-Farbe", "LED color"))
                        if c and c[0]:
                            wdg["rgb"] = [int(v) for v in c[0]]
                            sw.configure(fg_color=c[1], text=c[1])
                    sw.configure(command=pick)
                    sw.pack(side="left")
                    if rgb is None:
                        ctk.CTkLabel(cell, text=LED_UNKNOWN_NOTE, text_color=FW_DIM).pack(side="left", padx=6)
                widgets[name] = (kind, wdg, factor)
                row += 2
        ctk.CTkLabel(holder, text="").grid(row=row, column=0, pady=2)
        if done_msg:
            status.configure(text=done_msg[0], text_color=done_msg[1])
        else:
            status.configure(text=T(f"{len(values)} Einstellungen gelesen.", f"{len(values)} settings read."), text_color=FW_DIM)

    def apply():
        cmds = []
        for name, (kind, wdg, factor) in widgets.items():
            if kind == "bool":
                v = 1 if wdg.get() == T("An", "On") else 0
                if v != current.get(name):
                    cmds.append(f"write_config {name} {v}")
            elif kind == "enum":
                inv = {lbl: key for key, lbl in factor.items()}
                v = inv.get(wdg.get())
                if v is not None and v != current.get(name):
                    cmds.append(f"write_config {name} {v}")
            elif kind == "int":
                text = wdg.get().strip().replace(",", ".")
                try:
                    v = int(round(float(text) * factor))
                except ValueError:
                    status.configure(text=T(f"„{text}“ ist keine Zahl.", f"“{text}” is not a number."), text_color="red")
                    return
                if v != current.get(name):
                    cmds.append(f"write_config {name} {v}")
            else:
                for ch, val in zip("rgb", wdg["rgb"]):
                    v = round(val * 10000 / 255)
                    if v != current.get(f"led_default_color_{ch}"):
                        cmds.append(f"write_config led_default_color_{ch} {v}")
        if not cmds:
            status.configure(text=T("Nichts geändert.", "Nothing changed."), text_color=FW_DIM)
            return
        status.configure(text=T(f"Schreibe {len(cmds)} Einstellung(en)…", f"Writing {len(cmds)} setting(s)…"), text_color=FW_DIM)

        def work():
            lines = query_device(dev, cmds, wait=1.5)
            ok = sum(1 for l in lines if "Updated config" in l)
            color = "green" if ok == len(cmds) else "orange"
            app.after(0, lambda: read((T(f"{ok} von {len(cmds)} Einstellung(en) übernommen.", f"{ok} of {len(cmds)} setting(s) applied."), color)))
        threading.Thread(target=work, daemon=True).start()

    def reset_all():
        if not ask_yes_no(T("Zurücksetzen", "Reset"), T("Alle Einstellungen dieses Trackers auf Standard zurücksetzen?", "Reset all settings of this tracker to default?"), parent=w):
            return

        def work():
            query_device(dev, ["reset_config all"], wait=1.0)
            app.after(0, read)
        threading.Thread(target=work, daemon=True).start()

    ctk.CTkButton(bar, text=T("Neu einlesen", "Reload"), command=read).pack(side="left", padx=4)
    ctk.CTkButton(bar, text=T("Alle auf Standard", "All to default"), command=reset_all).pack(side="left", padx=4)
    ctk.CTkButton(bar, text=T("Übernehmen", "Apply"), width=160, fg_color=FW_PURPLE, hover_color=FW_PURPLE_H,
                  text_color="white", command=apply).pack(side="right", padx=4)
    if dev.connected:
        read()
    else:
        status.configure(text=T("Tracker ist nicht verbunden.", "Tracker is not connected."), text_color="orange")

# Buttons!
def start_firmware_download():
    threading.Thread(target=download_firmware, daemon=True).start()

btn_download_fw = ctk.CTkButton(top_frame, text="⬇ Firmware", width=80, command=start_firmware_download)
btn_download_fw.pack(side="left", padx=5)
ToolTip(btn_download_fw, "Upgrade your firmware!")

btn_multi_fw = ctk.CTkButton(header_buttons, text=T("DIY Firmware-Tool", "DIY Firmware Tool"), width=80, command=open_multiflash_window,
                             fg_color=SV_PURPLE, hover_color=SV_PURPLE_H, text_color="white")
btn_multi_fw.pack(side="left", padx=5)
ToolTip(btn_multi_fw, T("Tracker konfigurieren und auf einmal flashen", "Configure trackers and flash them all at once"))

btn_devmgr = ctk.CTkButton(header_buttons, text=T("Geräteverwaltung", "Device Manager"), width=80, command=open_device_manager)
btn_devmgr.pack(side="left", padx=(5, 0))
ToolTip(btn_devmgr, T("Alle Geräte, Akku, Firmware und Einstellungen", "All devices, battery, firmware and settings"))

status_label = ctk.CTkLabel(top_frame, text=T("Nicht verbunden", "Not connected"), text_color="red")
status_label.pack(side="left", padx=10)

def on_tab_change():
    # In den Einstellungen braucht es kein Terminal: die Einstellungen bekommen den ganzen Platz
    if tab_view.get() == TAB_SETTINGS:
        console_row.pack_forget()
        entry_frame.pack_forget()
        tab_view.pack_configure(fill="both", expand=True)
    else:
        tab_view.pack_configure(fill="x", expand=False)
        entry_frame.pack(side="bottom", pady=5, padx=10, fill="x")
        console_row.pack(pady=(0, 5), padx=10, fill="both", expand=True)

TAB_SETTINGS = T("Einstellungen", "Settings")
tab_view = ctk.CTkTabview(app, width=580, height=130, corner_radius=10, anchor="w", command=on_tab_change)
tab_view.pack(pady=10, padx=10, fill="x")



# Make the repetitive stuff less messy
def ui_btn(parent, text, command, tooltip):
    btn = ctk.CTkButton(
        parent,
        text=text,
        command=command,
        width=110,
        height=30,
        anchor="center"
    )
    ToolTip(btn, tooltip)
    return btn


# Tracker tab
tracker_tab = tab_view.add("Tracker")
tracker_btn_frame = ctk.CTkFrame(tracker_tab)
tracker_btn_frame.pack(pady=10, padx=10)

ui_btn(tracker_btn_frame, "Info", lambda: send_command("info"), T("Geräteinformationen abrufen", "Get device information")).grid(row=0, column=0, padx=5, pady=5)
ui_btn(tracker_btn_frame, T("Neustart", "Reboot"), lambda: send_command("reboot"), T("Gerät neu starten", "Soft reset the device")).grid(row=0, column=1, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Scan", lambda: send_command("scan"), T("Sensor neu suchen", "Restart sensor scan")).grid(row=0, column=2, padx=5, pady=5)
ui_btn(tracker_btn_frame, T("Kalibrieren", "Calibrate"), lambda: send_command("calibrate"), T("Sensor kalibrieren (ZRO)", "Calibrate sensor ZRO")).grid(row=0, column=3, padx=5, pady=5)
ui_btn(tracker_btn_frame, T("6 Seiten kalibrieren", "Calibrate 6 Sides"), lambda: send_command("6-side"), T("Beschleunigungssensor auf 6 Seiten kalibrieren", "Calibrate 6-side accelerometer")).grid(row=0, column=4, padx=5, pady=5)
ui_btn(tracker_btn_frame, T("Mag löschen", "Mag Clear"), lambda: send_command("mag"), T("Magnetometer-Kalibrierung löschen", "Clear magnetometer calibration")).grid(row=0, column=5, padx=5, pady=5)
ui_btn(tracker_btn_frame, T("Akku", "Battery"), lambda: send_command("battery"), T("Akku-Informationen abrufen", "Get battery information")).grid(row=0, column=6, padx=5, pady=5)

ui_btn(tracker_btn_frame, T("Kopplungsmodus", "Pairing Mode"), lambda: send_command("pair"), T("Kopplungsmodus starten", "Enter pairing mode")).grid(row=1, column=0, padx=5, pady=5)
ui_btn(tracker_btn_frame, T("Kopplung löschen", "Clear Con. Data"), lambda: send_command("clear"), T("Kopplungsdaten löschen", "Clear pairing data")).grid(row=1, column=1, padx=5, pady=5)
ui_btn(tracker_btn_frame, "DFU", lambda: send_command("dfu"), T("DFU-Bootloader starten (falls vorhanden)", "Enter DFU bootloader (if available)")).grid(row=1, column=2, padx=5, pady=5)
ui_btn(tracker_btn_frame, T("Laufzeit", "Uptime"), lambda: send_command("uptime"), T("Laufzeit des Geräts abrufen", "Get device uptime")).grid(row=1, column=3, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Debug", lambda: send_command("debug"), T("Debug-Protokoll ausgeben", "Print debug log")).grid(row=1, column=4, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Meow!", lambda: send_command("meow"), "Meow!").grid(row=1, column=5, padx=5, pady=5)

# Receiver tab
receiver_tab = tab_view.add(T("Empfänger", "Receiver"))
receiver_btn_frame = ctk.CTkFrame(receiver_tab)
receiver_btn_frame.pack(pady=10, padx=10)

ui_btn(receiver_btn_frame, "Info", lambda: send_command("info"), T("Geräteinformationen abrufen", "Get device information")).grid(row=0, column=0, padx=5, pady=5)
ui_btn(receiver_btn_frame, T("Liste", "List"), lambda: send_command("list"), T("Gekoppelte Geräte abrufen", "Get paired devices")).grid(row=0, column=1, padx=5, pady=5)
ui_btn(receiver_btn_frame, T("Neustart", "Reboot"), lambda: send_command("reboot"), T("Gerät neu starten", "Soft reset the device")).grid(row=0, column=2, padx=5, pady=5)
ui_btn(receiver_btn_frame, T("Entfernen", "Remove"), lambda: send_command("remove"), T("Zuletzt gekoppeltes Gerät entfernen", "Remove last paired device")).grid(row=0, column=3, padx=5, pady=5)
ui_btn(receiver_btn_frame, T("Kopplungsmodus", "Pairing Mode"), lambda: send_command("pair"), T("Kopplungsmodus starten", "Enter pairing mode")).grid(row=0, column=4, padx=5, pady=5)

ui_btn(receiver_btn_frame, T("✖ Gespeicherte Geräte", "✖ Saved Devices"), lambda: send_command("clear"), T("Gespeicherte Geräte löschen", "Clear stored devices")).grid(row=1, column=0, padx=5, pady=5)
ui_btn(receiver_btn_frame, "DFU", lambda: send_command("dfu"), T("DFU-Bootloader starten (falls vorhanden)", "Enter DFU bootloader (if available)")).grid(row=1, column=1, padx=5, pady=5)
ui_btn(receiver_btn_frame, T("Laufzeit", "Uptime"), lambda: send_command("uptime"), T("Laufzeit des Geräts abrufen", "Get device uptime")).grid(row=1, column=2, padx=5, pady=5)
ui_btn(receiver_btn_frame, "Meow!", lambda: send_command("meow"), "Meow!").grid(row=1, column=3, padx=5, pady=5)
ui_btn(receiver_btn_frame, T("⎋ Kopplungsmodus", "⎋ Pairing Mode"), lambda: send_command("exit"), T("Kopplungsmodus beenden", "Exit pairing mode")).grid(row=1, column=4, padx=5, pady=5)

# Settings tab
settings_tab = tab_view.add(TAB_SETTINGS)
settings_frame = ctk.CTkFrame(settings_tab)
settings_frame.pack(padx=10, pady=10, fill="both", expand=True)
settings_frame.grid_columnconfigure(0, weight=1)
settings_frame.grid_columnconfigure(1, weight=1)

# Platform name ting ting
platform_name = platform.system()
if platform_name == "Darwin":
    platform_name = "macOS"
elif platform_name == "Windows":
    platform_name = "Windows"
elif platform_name == "Linux":
    platform_name = "Linux"

version_label = ctk.CTkLabel(
    settings_frame,
    text=T(f"SmolSlimeConfigurator Version 9 · Fassung v{APP_VERSION} ({platform_name})", f"SmolSlimeConfigurator Version 9 · build v{APP_VERSION} ({platform_name})"),
    text_color="gray"
)
version_label.pack(anchor="ne", padx=10, pady=5)

firmware_frame = ctk.CTkFrame(settings_frame)
firmware_frame.pack(pady=10, fill="x")

ctk.CTkLabel(
    firmware_frame,
    text=T("Firmware-Quelle:", "Firmware Source:"),
    font=ctk.CTkFont(weight="bold")
).pack(anchor="w", padx=5, pady=(0, 5))

# Firmware repo select

firmware_source_var = tk.StringVar(value=settings.get("firmware_source", "main"))

def on_firmware_source_change():
    settings["firmware_source"] = firmware_source_var.get()
    save_settings()
    populate_firmware_menu()

rb_main = ctk.CTkRadioButton(
    firmware_frame,
    text="Main (Shine-Bright-Meow)",
    variable=firmware_source_var,
    value="main",
    command=on_firmware_source_change
)
rb_main.pack(anchor="w", padx=10)
ToolTip(rb_main, T("Haupt-Firmware-Quelle", "Main firmware repo"))

rb_kouno = ctk.CTkRadioButton(
    firmware_frame,
    text="Kounocom (Backup)",
    variable=firmware_source_var,
    value="kounocom",
    command=on_firmware_source_change
)
rb_kouno.pack(anchor="w", padx=10)
ToolTip(rb_kouno, T("Ausweich-Firmware-Quelle", "Backup firmware option"))

rb_custom = ctk.CTkRadioButton(
    firmware_frame,
    text=T("Eigene Quelle", "Custom Repo"),
    variable=firmware_source_var,
    value="custom",
    command=on_firmware_source_change
)
rb_custom.pack(anchor="w", padx=10)
ToolTip(rb_custom, T("Eigene Firmware-Quelle", "Custom firmware repo"))

custom_repo_entry = ctk.CTkEntry(
    firmware_frame,
    placeholder_text="https://api.github.com/repos/user/repo/releases/latest"
)
custom_repo_entry.pack(fill="x", padx=20, pady=(5, 0))
custom_repo_entry.insert(0, settings.get("custom_firmware_repo", ""))

def save_custom_repo(*args):
    settings["custom_firmware_repo"] = custom_repo_entry.get().strip()
    save_settings()

custom_repo_entry.bind("<FocusOut>", save_custom_repo)
ToolTip(custom_repo_entry, T("Eigene Firmware-Quelle", "Custom firmware repo"))

def toggle_theme(choice):
    settings["theme"] = choice
    ctk.set_appearance_mode(choice)

    if sys.platform.startswith("linux"):
        set_linux_scaling()

    save_settings()

def change_language(choice):
    lang = "de" if choice == "Deutsch" else "en"
    if lang == LANG:
        return
    settings["lang"] = lang
    save_settings()
    if ask_yes_no(T("Sprache", "Language"),
                           "Restart now to switch the language?\nJetzt neu starten, um die Sprache umzustellen?"):
        restart_app()
    else:
        lang_menu.set("Deutsch" if LANG == "de" else "English")
        settings["lang"] = LANG
        save_settings()

def toggle_tooltips():
    global TOOLTIPS_ENABLED
    settings["tooltips"] = not settings["tooltips"]
    TOOLTIPS_ENABLED = settings["tooltips"]
    save_settings()
    append_text(T(f"Tooltips {'an' if TOOLTIPS_ENABLED else 'aus'}.\n", f"Tooltips {'enabled' if TOOLTIPS_ENABLED else 'disabled'}.\n"), "success")

def open_repo():
    webbrowser.open("https://github.com/ICantMakeThings/SmolSlimeConfigurator")

appearance_frame = ctk.CTkFrame(settings_frame)
appearance_frame.pack(pady=10, fill="x")

ctk.CTkLabel(appearance_frame, text=T("Darstellung:", "Appearance Mode:")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
theme_menu = ctk.CTkOptionMenu(appearance_frame, values=["light", "dark"], command=toggle_theme)
theme_menu.set(settings["theme"])
theme_menu.grid(row=0, column=1, padx=5, pady=5, sticky="w")

ctk.CTkLabel(appearance_frame, text=T("Sprache:", "Language:")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
lang_menu = ctk.CTkOptionMenu(appearance_frame, values=["English", "Deutsch"], command=change_language)
lang_menu.set("Deutsch" if LANG == "de" else "English")
lang_menu.grid(row=1, column=1, padx=5, pady=5, sticky="w")
ToolTip(lang_menu, T("Die App startet dafür neu", "The app restarts to apply it"))

# Buttonssss
button_row = ctk.CTkFrame(settings_frame)
button_row.pack(pady=15)

tooltips_button = ctk.CTkButton(button_row, text=T("Tooltips an/aus", "Toggle Tooltips"), command=toggle_tooltips)
tooltips_button.pack(side="left", padx=10)
ToolTip(tooltips_button, T("Du weißt, was jeder Knopf macht? Tooltips ausschalten!", "Yk what each button does? Turn off tooltips!"))


repo_button = ctk.CTkButton(button_row, text=T("GitHub-Repo öffnen", "Open GitHub Repo"), command=open_repo)
repo_button.pack(side="left", padx=10)

ToolTip(repo_button, "github.com/ICantMakeThings/SmolSlimeConfigurator")

# Updater: sucht beim Start das neueste Release von UPDATE_REPO. Unter Linux
# (gebaute Einzeldatei) wird die Programmdatei ersetzt und neu gestartet,
# sonst nur die Release-Seite geoeffnet.
update_info = {}

# Reste eines Windows-Updates (die umbenannte alte .exe) wegraeumen
if getattr(sys, "frozen", False):
    try:
        os.remove(sys.executable + ".alt")
    except OSError:
        pass

def ver_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])

def show_check_result(text):
    update_button.configure(text=text)
    app.after(4000, lambda: update_button.configure(text=T("Nach Updates suchen", "Check for updates"), state="normal"))

def check_for_update(manual=False):
    if manual:
        update_button.configure(text=T("Suche…", "Checking…"), state="disabled")

    def work():
        try:
            # Die Release-Seite leitet auf den neuesten Tag weiter. Anders als die API hat sie
            # kein Limit von 60 Abfragen pro Stunde, an dem die Pruefung sonst scheitern kann.
            response = requests.get(f"https://github.com/{UPDATE_REPO}/releases/latest",
                                    allow_redirects=False, timeout=10)
            tag = response.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]
            if response.status_code not in (301, 302) or not ver_tuple(tag):
                raise RuntimeError(T(f"keine Antwort von GitHub (HTTP {response.status_code})", f"no answer from GitHub (HTTP {response.status_code})"))
            asset = {"browser_download_url": f"https://github.com/{UPDATE_REPO}/releases/download/{tag}/{UPDATE_ASSET}"}
            if ver_tuple(tag) > ver_tuple(APP_VERSION):
                notes = ""
                try:  # Aenderungsliste nur, wenn die API gerade antwortet
                    api = requests.get(f"https://api.github.com/repos/{UPDATE_REPO}/releases/tags/{tag}", timeout=10)
                    if api.ok:
                        notes = api.json().get("body") or ""
                except Exception:
                    pass
                app.after(0, lambda: offer_update(tag, asset, notes))
                if manual:
                    app.after(0, lambda: show_check_result(T(f"Neu: {tag}", f"New: {tag}")))
            elif manual:
                app.after(0, lambda: show_check_result(T(f"✓ v{APP_VERSION} ist aktuell", f"✓ v{APP_VERSION} is up to date")))
        except Exception as e:
            if manual:
                app.after(0, lambda e=e: (append_text(T(f"Update-Prüfung fehlgeschlagen: {e}\n", f"Update check failed: {e}\n"), "error"),
                                          show_check_result(T("Prüfung fehlgeschlagen", "Check failed"))))
    threading.Thread(target=work, daemon=True).start()

def offer_update(tag, asset, notes):
    update_info.update(tag=tag, asset=asset, notes=notes)
    btn_update.configure(text=f"⬆ Update {tag}", state="normal")
    btn_update.pack(side="left", padx=5, before=btn_multi_fw)
    append_text(T(f"Update verfügbar: {tag} (installiert: v{APP_VERSION}).\n", f"Update available: {tag} (installed: v{APP_VERSION}).\n"), "success")

def install_update():
    tag, asset = update_info.get("tag"), update_info.get("asset")
    if not (getattr(sys, "frozen", False) and sys.platform.startswith(("linux", "win")) and asset):
        webbrowser.open(f"https://github.com/{UPDATE_REPO}/releases/latest")
        return
    notes = update_info.get("notes", "").strip()
    if not ask_yes_no("Update", T(f"Auf {tag} aktualisieren?\n\n{notes[:800]}\n\nDas Programm startet danach neu.", f"Update to {tag}?\n\n{notes[:800]}\n\nThe program restarts afterwards."),
                               parent=app):
        return
    btn_update.configure(state="disabled", text=T("Lade Update…", "Downloading update…"))
    exe = sys.executable

    def work():
        try:
            new = exe + ".neu"
            response = requests.get(asset["browser_download_url"], stream=True, timeout=60)
            response.raise_for_status()
            with open(new, "wb") as f:
                shutil.copyfileobj(response.raw, f)
            expected = int(response.headers.get("Content-Length") or 0)
            if os.path.getsize(new) < 1_000_000 or (expected and os.path.getsize(new) != expected):
                raise RuntimeError(T("Download unvollständig", "Download incomplete"))
            os.chmod(new, 0o755)
            if sys.platform.startswith("win"):
                # Windows sperrt die laufende .exe gegen Ueberschreiben, Umbenennen geht aber
                old = exe + ".alt"
                if os.path.exists(old):
                    os.remove(old)
                os.rename(exe, old)
            os.replace(new, exe)  # Linux erlaubt das Ersetzen der laufenden Datei direkt
        except Exception as e:
            app.after(0, lambda e=e: (append_text(T(f"Update fehlgeschlagen: {e}\n", f"Update failed: {e}\n"), "error"),
                                      btn_update.configure(state="normal", text=f"⬆ Update {tag}")))
            return
        app.after(0, restart_app)
    threading.Thread(target=work, daemon=True).start()

def restart_app():
    for dev in devices:
        disconnect_device(dev)
    # Die neue Einzeldatei soll sich frisch entpacken und nicht die Umgebung
    # (Entpack-Ordner, LD_LIBRARY_PATH) dieser Instanz uebernehmen.
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    env.pop("_MEIPASS2", None)
    if "LD_LIBRARY_PATH_ORIG" in env:
        env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
    else:
        env.pop("LD_LIBRARY_PATH", None)
    if getattr(sys, "frozen", False):
        subprocess.Popen([sys.executable], cwd=os.path.dirname(sys.executable), env=env, start_new_session=True)
    else:   # als Skript gestartet: Python mit demselben Skript neu
        subprocess.Popen([sys.executable] + sys.argv, start_new_session=True)
    app.destroy()
    os._exit(0)

btn_update = ctk.CTkButton(header_buttons, text="⬆ Update", width=80, fg_color="green", hover_color="#006400",
                           command=install_update)
ToolTip(btn_update, T("Neue Fassung herunterladen und neu starten", "Download the new build and restart"))

update_button = ctk.CTkButton(button_row, text=T("Nach Updates suchen", "Check for updates"), command=lambda: check_for_update(manual=True))
update_button.pack(side="left", padx=10)
ToolTip(update_button, T(f"Installiert: v{APP_VERSION}", f"Installed: v{APP_VERSION}"))
app.after(3000, check_for_update)


# CLI, links daneben die Geraete zum Umschalten
console_row = ctk.CTkFrame(app, fg_color="transparent")

sidebar = ctk.CTkFrame(console_row, width=130)
sidebar.pack(side="left", fill="y", padx=(0, 5))
btn_pair_all = ctk.CTkButton(sidebar, text=T("🔗 Koppeln", "🔗 Pair"), width=110, command=pair_all,
                             fg_color=SV_PURPLE, hover_color=SV_PURPLE_H, text_color="white")
btn_pair_all.pack(side="bottom", fill="x", padx=5, pady=5)
device_list = ctk.CTkScrollableFrame(sidebar, width=110, fg_color="transparent")
device_list.pack(fill="both", expand=True, padx=2, pady=(2, 0))
ToolTip(btn_pair_all, T("Dongle und alle verbundenen Tracker gleichzeitig in den Kopplungsmodus", "Put the dongle and all connected trackers into pairing mode at once"))

console_area = ctk.CTkFrame(console_row, fg_color="transparent")
console_area.pack(side="left", fill="both", expand=True)

console = make_console()
base_console = console
console.pack(fill="both", expand=True)

def send_custom_command():
    cmd = command_entry.get().strip()
    if cmd:
        send_command(cmd)
        command_entry.delete(0, "end")

entry_frame = ctk.CTkFrame(app)
entry_frame.pack(side="bottom", pady=5, padx=10, fill="x")

command_entry = ctk.CTkEntry(entry_frame, placeholder_text=T("Eigenen Befehl eingeben...", "Enter custom command..."))
command_entry.pack(side="left", fill="x", expand=True, padx=(0, 5), pady=5)

btn_send = ctk.CTkButton(entry_frame, text=T("Senden", "Send"), width=80, command=send_custom_command)
btn_send.pack(side="left", pady=5)

btn_clear = ctk.CTkButton(entry_frame, text="X", width=30, command=lambda: console.configure(state="normal") or console.delete("1.0", "end") or console.configure(state="disabled"))
btn_clear.pack(side="left", padx=(5,0), pady=5)

# Erst nach der Eingabezeile packen, damit die nicht abgeschnitten wird
console_row.pack(pady=(0, 5), padx=10, fill="both", expand=True)
ToolTip(btn_clear, T("Leeren", "Clear"))

command_entry.bind("<Return>", lambda event: send_custom_command())

# MY GUY THE ICON IS THE MOST IMPORTANT TING
def resource_path(relative_path):
    """gapfpione."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if sys.platform.startswith("win"):
    try:
        app.iconbitmap(resource_path("icon.ico"))
    except Exception as e:
        print(f"boohoo.. error: {e}")
elif sys.platform.startswith("linux") or sys.platform.startswith("darwin"):
    img_path = resource_path("icon.png")
    try:
        img = tk.PhotoImage(file=img_path)
        app.iconphoto(True, img)
    except Exception as e:
        print(f"boohoo.. error: {e}")



def flush_serial_queue():
    while not serial_queue.empty():
        dev, line, lost = serial_queue.get()
        if line is not None:
            append_text(line, None, dev)
            for listener in list(dev.listeners):
                listener(line)
        else:
            device_lost(dev, lost)
    app.after(50, flush_serial_queue)

app.after(50, flush_serial_queue)
app.after(500, watch_devices)

if os.environ.get("SMOLSLIME_SELFTEST"):
    app.after(2000, open_multiflash_window)
    app.after(6000, lambda: (print("selftest ok", flush=True), os._exit(0)))
# The MOST PORTAN' PART!!!
app.mainloop()
