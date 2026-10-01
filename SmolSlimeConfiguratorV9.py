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
APP_VERSION = "1.0.2"
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
    "custom_firmware_repo": ""
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
apply_accent(settings["accent"])

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
        msg = ("SmolSlime Configurator braucht XWayland (die X11-Ebene von Wayland).\n"
               "Bitte XWayland installieren bzw. in der Sitzung aktivieren.")
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
        port_option.configure(values=["No ports found"])
        port_option.set("No ports found")

# Linux sperrt /dev/ttyACM* fuer normale Benutzer (Arch: Gruppe uucp). Statt
# "Permission denied" einmal per Passwortfenster eine udev-Regel setzen, die
# dem angemeldeten Benutzer SlimeNRF-Geraete (USB-Hersteller 1209) freigibt.
UDEV_RULE_PATH = "/etc/udev/rules.d/70-smolslime.rules"

def is_permission_error(e):
    return getattr(e, "errno", None) == 13 or "Permission denied" in str(e)

def fix_serial_permissions(parent=None):
    if not sys.platform.startswith("linux") or not shutil.which("pkexec"):
        return False
    from tkinter import messagebox
    if not messagebox.askyesno(
        "Keine Berechtigung",
        "Linux erlaubt den Zugriff auf den USB-Anschluss nicht.\n\n"
        "Jetzt einmalig einrichten? Danach fragt ein Fenster nach deinem Passwort.",
        parent=parent or app,
    ):
        return False
    rule = 'SUBSYSTEM=="tty", ATTRS{idVendor}=="1209", TAG+="uaccess"'
    script = (
        f"printf '%s\\n' '{rule}' > {UDEV_RULE_PATH}"
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
    append_text("USB-Rechte eingerichtet.\n" if ok else "USB-Rechte nicht eingerichtet.\n", "success" if ok else "error")
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
        return "Empfänger"
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
            dev.port = info.device
            return dev
    dev = Device(info)
    dev.number = 1 + sum(1 for d in devices if not d.is_receiver)
    dev.console = make_console()
    dev.button = ctk.CTkButton(device_list, text=device_name(dev), width=110,
                               command=lambda d=dev: select_device(d))
    dev.button.bind("<Button-3>", lambda e, d=dev: open_device_menu(d, e))
    ToolTip(dev.button, "Rechtsklick: trennen, umbenennen, als Dongle festlegen")
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
        status_label.configure(text="Not connected", text_color="red")
    elif connected:
        status_label.configure(text=f"{device_name(dev)}: Connected to {dev.port}", text_color="green")
    else:
        status_label.configure(text=f"{device_name(dev)}: getrennt", text_color="orange")

def select_device(dev):
    global active_device, console
    active_device = dev
    console.pack_forget()
    console = dev.console if dev else base_console
    console.pack(fill="both", expand=True)
    if dev and tab_view.get() != "Settings":
        tab_view.set("Receiver" if dev.is_receiver else "Tracker")
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
            append_text(f"Failed to connect: {e}\n", "error", dev)
        refresh_sidebar()
        sync_active()
        return False
    dev.stop = threading.Event()
    threading.Thread(target=read_serial, args=(dev,), daemon=True).start()
    append_text(f"Connected to {dev.port}\n", "success", dev)
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

def remove_device(dev):
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
        menu.add_command(label="Trennen", command=lambda: (setattr(dev, "manual_off", True), device_lost(dev, "Getrennt.\n")))
    else:
        menu.add_command(label="Verbinden", command=lambda: (setattr(dev, "manual_off", False), connect_device(dev)))
    if dev.is_dongle:
        menu.add_command(label="Dongle-Festlegung aufheben", command=lambda: set_dongle(None))
    elif dev.serial_number:
        menu.add_command(label="Als Dongle festlegen", command=lambda: set_dongle(dev))
    menu.add_command(label="Umbenennen…", command=lambda: rename_device(dev))
    menu.add_separator()
    menu.add_command(label="Entfernen", command=lambda: remove_device(dev))
    menu.tk_popup(event.x_root, event.y_root)

def set_dongle(dev):
    settings["dongle_serial"] = dev.serial_number if dev else ""
    save_settings()
    refresh_sidebar()
    sync_active()
    if dev:
        append_text("Als Dongle festgelegt. Er verbindet sich ab jetzt von selbst.\n", "success", dev)

def rename_device(dev):
    name = ctk.CTkInputDialog(text="Neuer Name (leer = Standard):", title="Umbenennen").get_input()
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
def watch_devices():
    try:
        ports = serial.tools.list_ports.comports()
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
                dev.port = info.device
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
        append_text("Kein Dongle verbunden.\n", "error")
        return
    if not trackers:
        append_text("Kein Tracker verbunden.\n", "error")
        return
    send_command("pair", dongle)
    for d in trackers:
        send_command("pair", d)
    append_text(f"Kopplungsmodus: Dongle + {len(trackers)} Tracker.\n", "success")

# El button to connect your Smol Slimes to El program
def connect_to_port():
    port = port_option.get()
    if not port or "No ports" in port:
        append_text("No valid port selected.\n", "error")
        return
    info = next((p for p in serial.tools.list_ports.comports() if p.device == port), None)
    if info is None:
        append_text(f"{port} ist nicht mehr da.\n", "error")
        refresh_ports()
        return
    dev = get_or_add_device(info)
    dev.manual_off = False
    if not dev.connected and not connect_device(dev):
        status_label.configure(text="Connection failed", text_color="red")
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
            device_lost(dev, f"[Error] Serial write failed: {e}\n")
    else:
        append_text("Not connected.\n", "error", dev)

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
                serial_queue.put((dev, None, f"Device disconnected: {e}\n"))
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
        path = filedialog.askopenfilename(title="Select firmware (.uf2 or .hex)", filetypes=[("Firmware files", "*.uf2 *.hex"), ("UF2 files", "*.uf2"), ("HEX files", "*.hex")])
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
ctk.CTkLabel(header_text, text=f"Tracker und Dongle verbinden, einstellen und flashen · v{APP_VERSION}",
             text_color=("gray35", "gray65")).pack(anchor="w")
btn_check_update = ctk.CTkButton(header, text="Nach Updates suchen", width=170,
                                 command=lambda: check_for_update(manual=True))
btn_check_update.pack(side="right", anchor="n", pady=(4, 0))

top_frame = ctk.CTkFrame(app)
top_frame.pack(pady=5, padx=10, fill="x")

initial_ports = list_serial_ports()
if not initial_ports:
    initial_ports = ["No ports found"]

port_option = ctk.CTkOptionMenu(top_frame, values=initial_ports)
port_option.set(initial_ports[0])
port_option.pack(side="left", padx=5)
ToolTip(port_option, "Select the port for your device")

btn_refresh = ctk.CTkButton(top_frame, text="↻", width=10, command=refresh_ports)
btn_refresh.pack(side="left", padx=5)
ToolTip(btn_refresh, "Refresh serial port")

btn_connect = ctk.CTkButton(top_frame, text="Connect", command=connect_to_port,
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


app.after(100, populate_firmware_menu)

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
        file_path = filedialog.askopenfilename(filetypes=[("Firmware files", "*.uf2 *.hex"), ("UF2 files", "*.uf2"), ("HEX files", "*.hex")])
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
        drives[name] = {"devs": devs, "location": locs[-1] if locs else "", "mount": mount}
    return drives

def mount_drive(drive):
    if drive["mount"]:
        return drive["mount"]
    for dev in reversed(drive["devs"]):
        subprocess.run(["udisksctl", "mount", "-b", dev, "--no-user-interaction"],
                       capture_output=True, timeout=15)
        mount = read_mounts().get(dev)
        if mount:
            return mount
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
    {"id": "main", "name": "SlimeNRF-Firmware-CI", "owner": "Shine-Bright-Meow", "badge": "Offiziell",
     "repo": "Shine-Bright-Meow/SlimeNRF-Firmware-CI"},
    {"id": "kounocom", "name": "SlimeNRF-Firmware-CI", "owner": "kounocom", "badge": "Drittanbieter",
     "repo": "kounocom/SlimeNRF-Firmware-CI"},
    {"id": "jitingcn", "name": "SlimeVR-Tracker-nRF", "owner": "jitingcn", "badge": "Drittanbieter",
     "repo": "jitingcn/SlimeVR-Tracker-nRF"},
    {"id": "all", "name": "Alle Quellen", "owner": "jeweils neueste", "badge": "Alle", "repo": "*"},
    {"id": "file", "name": "Eigene Datei", "owner": ".uf2 vom Rechner", "badge": "Datei", "repo": None},
]

FW_OPTION_GROUPS = [
    ("variant", "Bauform", ["StackedSmol", "Chrysalis", "Bao"]),
    ("bus", "Sensor-Anschluss", ["SPI", "I2C", "smSPI"]),
    ("mag", "Magnetometer", ["Mag"]),
    ("clk", "Externer Sensor-Takt", ["CLK", "NoCLK"]),
    ("sleep", "Schlafmodus aus", ["NoSleep"]),
    ("sw0", "Taster an SW0", ["SW0"]),
    ("tdma", "Funkmodus TDMA", ["TDMA"]),
    ("data", "Datensammlung (CDC)", ["DataCollect"]),
]
FW_OPTION_TOKENS = {t for _, _, toks in FW_OPTION_GROUPS for t in toks}

# Erklaerungen fuer Leute ohne Vorwissen. Grundlage: Kconfig der offiziellen
# Firmware und das Build-Skript der CI (was jede Option beim Bauen umschaltet).
FW_OPTION_HELP = {
    "variant": "Wie der Tracker um den Controller herum aufgebaut ist. „Stacked Smol“: der Sensor sitzt huckepack "
               "direkt auf dem ProMicro. Chrysalis und Bao sind fertige Tracker-Platinen. Hast du einen ProMicro "
               "selbst mit Kabeln verdrahtet: „Platinen-Standard“.",
    "bus": "Wie der Bewegungssensor mit dem Controller verbunden ist. SPI ist schneller und weniger störanfällig "
           "und wird deshalb empfohlen. I2C braucht weniger Drähte und funktioniert auch. Wichtig: Die Wahl muss "
           "zu deiner Verdrahtung passen, sonst wird der Sensor nicht gefunden. „SPI (Smol-Belegung)“ ist SPI mit "
           "anderer Pin-Belegung – nur wählen, wenn dein Schaltplan das so vorgibt.",
    "mag": "Ein Magnetometer ist ein Kompass-Sensor. Er verhindert, dass sich die Drehung des Trackers mit der Zeit "
           "langsam verschiebt (Drift). Nur einschalten, wenn wirklich einer verbaut ist. In der Nähe von Metall, "
           "Magneten oder Lautsprechern kann er stören.",
    "clk": "Manche Sensoren bekommen vom Controller einen eigenen Takt über eine extra Leitung. Das macht die "
           "Zeitmessung genauer und spart etwas Strom. Nur einschalten, wenn diese Leitung (CLK) bei dir "
           "angeschlossen ist. „Aus“ schaltet sie ausdrücklich ab, „Platinen-Standard“ lässt es so, wie die Platine "
           "es vorsieht.",
    "sleep": "Normalerweise legt sich der Tracker schlafen, wenn er still liegt, und wacht bei Bewegung wieder auf. "
             "Das spart viel Akku. Mit „Schlafmodus aus“ bleibt er immer wach: Er reagiert sofort, aber der Akku "
             "hält deutlich kürzer. Sinnvoll, wenn dein Sensor das Aufwecken durch Bewegung nicht kann.",
    "sw0": "Nur wählen, wenn an Pin SW0 ein Taster angeschlossen ist. Damit kannst du z. B. koppeln "
           "(5 Sekunden halten) oder den Tracker ausschalten.",
    "tdma": "Neuerer Funkmodus mit festen Zeitfenstern pro Tracker – kann bei vielen Trackern stabiler sein. "
            "Achtung: Der Dongle braucht dann ebenfalls TDMA-Firmware, sonst verbinden sie sich nicht.",
    "data": "Gibt zusätzlich Rohdaten über USB aus. Nur für Fehlersuche oder Entwicklung.",
}

FW_CHOICE_LABELS = {
    "bus": {"SPI": "SPI (empfohlen)", "I2C": "I2C", "smSPI": "SPI (Smol-Belegung)", None: "Platinen-Standard"},
    "variant": {"StackedSmol": "Stacked Smol", None: "Platinen-Standard"},
    "clk": {"CLK": "An", "NoCLK": "Aus", None: "Platinen-Standard"},
}

# Laufzeit-Einstellungen der offiziellen Firmware (write_config <name> <wert>).
# (name, Beschriftung, Art, Standard in Anzeige-Einheit, Einheit, Faktor zur Firmware-Einheit, Erklaerung)
FW_SETTINGS = [
    ("Sensor", [
        ("sensor_use_mag", "Magnetometer benutzen", "bool", True, "", 1,
         "Schaltet den Kompass-Sensor ein oder aus, falls einer verbaut ist."),
        ("use_sensor_clock", "Externen Sensor-Takt benutzen", "bool", True, "", 1,
         "Nutzt die extra Taktleitung zum Sensor, falls angeschlossen."),
        ("sensor_use_6_side_calibration", "6-Seiten-Kalibrierung", "bool", True, "", 1,
         "Genauere Kalibrierung des Beschleunigungssensors. Wird in der Konsole mit „6-side“ durchgeführt."),
        ("sensor_accel_odr", "Messrate Beschleunigung", "int", 100, "Hz", 1,
         "Wie oft pro Sekunde gemessen wird. Höher = genauer, aber mehr Rechenzeit und Stromverbrauch."),
        ("sensor_gyro_odr", "Messrate Gyroskop", "int", 200, "Hz", 1,
         "Wie oft pro Sekunde die Drehung gemessen wird. Bei rauschenden Sensoren (BMI270, LSM6DS3TR-C) "
         "ist ein niedrigerer Wert besser."),
        ("sensor_accel_fs", "Messbereich Beschleunigung", "int", 4, "g", 1,
         "Kleiner = feiner und rauschärmer, aber schnelle Bewegungen können „überlaufen“."),
        ("sensor_gyro_fs", "Messbereich Gyroskop", "int", 1000, "°/s", 1,
         "Kleiner = feiner, aber sehr schnelle Drehungen können „überlaufen“."),
    ]),
    ("Energie und Schlaf", [
        ("use_imu_timeout", "Bei Stillstand schlafen", "bool", True, "", 1,
         "Liegt der Tracker still, geht der Sensor in einen Schlafzustand. Spart viel Akku."),
        ("imu_timeout_ramp_min", "Schlafen frühestens nach", "int", 5, "s", 1000,
         "So lange muss der Tracker mindestens stillliegen, bevor er schläft."),
        ("imu_timeout_ramp_max", "Schlafen spätestens nach", "int", 15, "s", 1000,
         "Längste Wartezeit bei Stillstand, bevor er schläft."),
        ("use_imu_wake_up", "Aufwecken durch Bewegung", "bool", True, "", 1,
         "Der Sensor weckt den Tracker auf, sobald er bewegt wird."),
        ("sensor_lp_timeout", "Stromsparmodus nach", "int", 500, "ms", 1,
         "Nach so vielen Millisekunden ohne Bewegung misst der Sensor sparsamer."),
        ("sensor_use_low_power_2", "Zusätzliche Sparmodi", "bool", False, "", 1,
         "Noch sparsamer bei Stillstand, reagiert dafür minimal verzögert."),
        ("delay_sleep_on_status", "Nicht schlafen bei Statusmeldung", "bool", True, "", 1,
         "Verschiebt den Schlaf, solange eine Meldung anliegt oder gekoppelt wird."),
    ]),
    ("Zeitlimit bei Nichtbenutzung", [
        ("use_active_timeout", "Zeitlimit benutzen", "bool", True, "", 1,
         "Liegt der Tracker lange Zeit unbewegt herum (z. B. vergessen), legt er sich nach dem Zeitlimit "
         "schlafen oder schaltet sich ganz aus."),
        ("active_timeout_mode", "Danach", "enum", 0, "", {0: "Schlafen", 1: "Ausschalten"},
         "Schlafen: wacht bei Bewegung wieder auf (braucht „Aufwecken durch Bewegung“). Ausschalten: muss "
         "per Taster wieder eingeschaltet werden (braucht „Ausschalten per Taster“)."),
        ("active_timeout_delay", "Zeitlimit", "int", 15, "min", 60000,
         "Nach so vielen Minuten ohne Bewegung greift das Zeitlimit."),
        ("active_timeout_threshold", "Schwelle", "int", 15, "s", 1000,
         "Nach so vielen Sekunden Stillstand beginnt das Zeitlimit zu zählen."),
    ]),
    ("Taster", [
        ("user_extra_actions", "Mehrfachdruck-Aktionen", "bool", False, "", 1,
         "Mehrmals drücken zum Kalibrieren, Koppeln oder für den Bootloader."),
        ("ignore_reset", "Reset-Taster ignorieren", "bool", True, "", 1,
         "Der Reset-Taster löst keine Zusatzaktionen aus."),
        ("user_shutdown", "Ausschalten per Taster", "bool", True, "", 1,
         "Der Tracker lässt sich per Taster bzw. Reset ausschalten."),
    ]),
    ("LED", [
        ("led_default_color", "Farbe im Normalbetrieb", "color", None, "", 1,
         "Farbe der Status-LED, falls der Tracker eine RGB-LED hat."),
    ]),
    ("Funk und Akku", [
        ("radio_tx_power", "Sendeleistung", "int", 8, "dBm", 1,
         "Weniger = etwas weniger Reichweite, dafür längere Akkulaufzeit. Höchstwert meist 8."),
        ("connection_timeout_delay", "Abschalten ohne Dongle nach", "int", 5, "min", 60000,
         "Findet der Tracker keinen Dongle, schaltet er sich nach dieser Zeit ab."),
        ("connection_over_hid", "Daten per USB-HID ausgeben", "bool", False, "", 1,
         "Nur für Sonderfälle: Daten per USB statt nur per Funk."),
        ("battery_low_runtime_threshold", "Akku-Warnung unter", "int", 3, "h", 3600000,
         "Warnt, wenn die geschätzte Restlaufzeit darunter fällt."),
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

fw_release_cache = {}

# Zwei Namensschemata: SlimeNRF_Tracker_SPI_Mag_ProMicro (CI) und
# SlimeNRF_ProMicro_StackedSmol_Tracker_I2C bzw. Aero_Tracker_Pro (jitingcn).
# Bekannte Optionen werden herausgezogen, der Rest ist das Board.
FW_TOKEN_ALIASES = {t.lower(): t for t in FW_OPTION_TOKENS}

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
    return {
        "role": role,
        "board": "_".join(t for t in rest if t.lower() not in FW_TOKEN_ALIASES and t.lower() != "nosleepclk"
                          and not t.startswith("StackedSmol_"))
                 or ("ProMicro" if any(t.lower().startswith("stackedsmol") for t in rest) else "Standard"),
        "options": frozenset(FW_TOKEN_ALIASES[t.lower()] for t in rest if t.lower() in FW_TOKEN_ALIASES)
                   | frozenset(t for t in rest if t.startswith("StackedSmol_"))
                   | (frozenset({"NoSleep", "CLK"}) if any(t.lower() == "nosleepclk" for t in rest) else frozenset()),
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

def fetch_releases(repo):
    if repo in fw_release_cache:
        return fw_release_cache[repo]
    response = requests.get(f"https://api.github.com/repos/{repo}/releases?per_page=20", timeout=15)
    response.raise_for_status()
    releases = []
    for rel in response.json():
        assets = []
        for a in rel.get("assets", []):
            info = parse_fw_name(a.get("name", ""))
            if info:
                info["url"] = a.get("browser_download_url")
                assets.append(info)
        if assets:
            releases.append({"tag": rel.get("tag_name", "?"), "assets": assets})
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

def open_multiflash_window():
    global multi_win
    if multi_win is not None and multi_win.winfo_exists():
        multi_win.focus()
        return

    win = ctk.CTkToplevel(app, fg_color=FW_BG)
    multi_win = win
    win.title("DIY Firmware-Tool")
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
    ctk.CTkLabel(head, text="DIY Firmware-Tool", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
    ctk.CTkLabel(head, text="Erlaubt dir das Konfigurieren und Flashen von DIY-Trackern", text_color=FW_DIM).pack(anchor="w")

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

    def nav(frame, row, next_cmd=None, next_text="Nächster Schritt", back=True):
        bar = ctk.CTkFrame(frame, fg_color="transparent")
        bar.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        if back:
            ctk.CTkButton(bar, text="Zurück", width=100, fg_color="transparent", border_width=1,
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
    f1 = make_step(0, "Wähle die Firmware zum Flashen aus", "Quelle, Board und Version")
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

    col_src = column(0, "Firmware-Quelle")
    col_board = column(1, "Boardtyp")
    col_ver = column(2, "Firmware-Version")

    src_cards = {}
    for src in fw_sources():
        card = ctk.CTkFrame(col_src, fg_color=FW_CARD2, corner_radius=8, border_width=2, border_color=FW_CARD2)
        card.pack(fill="x", padx=8, pady=4)
        t = ctk.CTkLabel(card, text=src["name"], anchor="w", font=ctk.CTkFont(weight="bold"))
        t.pack(fill="x", padx=10, pady=(6, 0))
        line = ctk.CTkFrame(card, fg_color="transparent")
        line.pack(fill="x", padx=10, pady=(0, 6))
        o = ctk.CTkLabel(line, text=src["owner"], anchor="w", text_color=FW_DIM)
        o.pack(side="left")
        badge = ctk.CTkLabel(line, text=f" {src['badge']} ", corner_radius=6, height=18,
                             fg_color=FW_PURPLE if src["badge"] == "Offiziell" else FW_SLATE,
                             text_color="white", font=ctk.CTkFont(size=11))
        badge.pack(side="right")
        for w in (card, t, line, o, badge):
            w.bind("<Button-1>", lambda e, s=src: select_source(s))
        src_cards[src["id"]] = card

    board_menu = ctk.CTkOptionMenu(col_board, values=["Keine Quelle ausgewählt"], state="disabled",
                                   command=lambda v: set_board(board_map.get(v)))
    board_menu.set("Keine Quelle ausgewählt")
    board_menu.pack(fill="x", padx=10, pady=12)

    def pick_file():
        path = filedialog.askopenfilename(parent=win, title="UF2-Datei wählen", filetypes=[("UF2 files", "*.uf2")])
        if path:
            st["file"] = path
            file_btn.configure(text=os.path.basename(path))
            update_next1()

    file_btn = ctk.CTkButton(col_board, text="Datei wählen…", command=pick_file)

    ver_menu = ctk.CTkOptionMenu(col_ver, values=["Keine Quelle ausgewählt"], state="disabled",
                                 command=lambda v: select_version(v))
    ver_menu.set("Keine Quelle ausgewählt")
    ver_menu.pack(fill="x", padx=10, pady=12)
    ctk.CTkLabel(col_ver, text="Der Dongle muss dieselbe\nVersion haben.", text_color=FW_DIM,
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
            ver_menu.configure(values=["Eigene Datei"], state="disabled")
            ver_menu.set("Eigene Datei")
            update_next1()
            return
        st["file"] = None
        file_btn.pack_forget()
        board_menu.pack(fill="x", padx=10, pady=12)
        for m in (board_menu, ver_menu):
            m.configure(state="disabled")
            m.set("Lade…")
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
                rels = [{"tag": "neueste je Quelle", "assets": merged}] if merged else []
                err = None if merged else err
            else:
                try:
                    rels, err = fetch_releases(src["repo"]), None
                    rels = [dict(rel, assets=[dict(a, src=src, tag=rel["tag"]) for a in rel["assets"]]) for rel in rels]
                except Exception as e:
                    rels, err = [], e
            ui(lambda: releases_loaded(src, rels, err))
        threading.Thread(target=work, daemon=True).start()

    def releases_loaded(src, rels, err):
        if st["source"] is not src:
            return
        st["releases"] = rels
        if err or not rels:
            ver_menu.set("Fehler beim Laden" if err else "Keine Firmware gefunden")
            board_menu.set("–")
            if err:
                append_text(f"[Firmware-Tool] {src['repo']}: {err}\n", "error")
            update_next1()
            return
        ver_map.clear()
        for k, rel in enumerate(rels):
            ver_map[rel["tag"] + ("  (neueste)" if k == 0 and src["repo"] != "*" else "")] = rel
        labels = list(ver_map)
        ver_menu.configure(values=labels, state="normal")
        ver_menu.set(labels[0])
        select_version(labels[0])

    def select_version(label):
        st["release"] = ver_map.get(label)
        refresh_boards()

    def set_board(board):
        st["board"] = board
        update_next1()

    def refresh_boards():
        boards = sorted({a["board"] for a in st["release"]["assets"] if a["role"] == st["role"]}) if st["release"] else []
        board_map.clear()
        board_map.update({b.replace("_", " "): b for b in boards})
        if not boards:
            board_menu.configure(values=["Keine für diesen Gerätetyp"], state="disabled")
            board_menu.set("Keine für diesen Gerätetyp")
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

    # Erklaerungen stehen hinter einem ?-Knopf, damit die Seite uebersichtlich bleibt
    def label_with_help(parent, row, text, help_text, bold=False, padx=12):
        head = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(head, text=text, anchor="w",
                     font=ctk.CTkFont(weight="bold") if bold else None).pack(side="left")
        help_l = ctk.CTkLabel(parent, text=help_text, anchor="w", justify="left", wraplength=640, text_color=FW_DIM)
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

    # ---------- 2: Board konfigurieren ----------
    f2 = make_step(1, "Konfiguriere dein Board", "Bauweise deines Trackers")
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
            min(sets, key=lambda o: (len(o) + 10 * any(t in ("Chrysalis", "Bao") or t.startswith("StackedSmol") for t in o),
                                     sorted(o)))
        fixed = frozenset.intersection(*sets)
        choice_vars = {}

        box = ctk.CTkFrame(f2, fg_color=FW_CARD, corner_radius=10)
        box.grid(row=0, column=0, sticky="ew", padx=6)
        box.grid_columnconfigure(1, weight=1)
        result = ctk.CTkLabel(f2, text="", anchor="w", justify="left")
        result.grid(row=1, column=0, sticky="ew", padx=6, pady=(8, 0))
        adv = ctk.CTkFrame(f2, fg_color="transparent")
        adv.grid(row=2, column=0, sticky="ew", padx=6, pady=(10, 0))
        nxt = nav(f2, 3, next_cmd=lambda: go(2))

        def update_result():
            chosen = set(fixed)
            for var, tok in choice_vars.values():
                if tok and var.get():
                    chosen.add(tok)
                elif not tok and var.get():
                    chosen.add(var.get())
            order = [s["id"] for s in fw_sources()]
            match = sorted((a for a in assets if a["options"] == chosen),
                           key=lambda a: (a["ext"] != "uf2", order.index(a["src"]["id"]) if a["src"]["id"] in order else 99))
            st["asset"] = match[0] if match else None
            if match:
                a = match[0]
                result.configure(text=f"✅  {a['name']}\n      Quelle: {a['src']['owner']} / {a['src']['name']} · {a['tag']}",
                                 text_color=("green", "lime"))
                nxt.configure(state="normal")
            else:
                tip = "" if st["source"]["id"] == "all" else "\n      Tipp: Unter „Alle Quellen“ gibt es mehr Kombinationen."
                result.configure(text="❌  Diese Kombination gibt es in dieser Version nicht." + tip, text_color="red")
                nxt.configure(state="disabled")

        r = 0
        for key, label, toks in FW_OPTION_GROUPS:
            if key == "variant":
                toks = toks + sorted({t for o in sets for t in o if t.startswith("StackedSmol_")})
            present = [t for t in toks if any(t in s for s in sets)]
            has_none = any(not (s & set(toks)) for s in sets)
            choices = present + ([None] if has_none else [])
            if len(choices) < 2 and not (key == "bus" and present):
                continue
            current = next((t for t in base if t in toks), None)
            names = FW_CHOICE_LABELS.get(key, {})
            label_with_help(box, r, label, FW_OPTION_HELP.get(key, ""), bold=True).grid(
                row=r, column=0, sticky="nw", padx=12, pady=(10, 0))
            if len(toks) == 1:
                var = tk.BooleanVar(value=current is not None)
                ctk.CTkCheckBox(box, text="An", variable=var, command=update_result).grid(
                    row=r, column=1, sticky="w", pady=(10, 0))
                choice_vars[key] = (var, toks[0])
            else:
                var = tk.StringVar(value=current or "")
                fr = ctk.CTkFrame(box, fg_color="transparent")
                fr.grid(row=r, column=1, sticky="w", pady=(10, 0))
                # Beim Sensor-Anschluss auch zeigen, was diese Quelle nicht hat, damit die Wahl sichtbar bleibt
                shown = choices + ([t for t in toks if t not in present and t != "smSPI"] if key == "bus" else [])
                for i, t in enumerate(shown):
                    available = t in choices
                    text = names.get(t) or (f"Stacked Smol ({t[12:]})" if t and t.startswith("StackedSmol_") else t)
                    text += "" if available else " – nicht in dieser Quelle"
                    ctk.CTkRadioButton(fr, text=text, variable=var, value=t or "", command=update_result,
                                       state="normal" if available else "disabled").grid(
                        row=i // 3, column=i % 3, sticky="w", padx=(0, 14), pady=2)
                choice_vars[key] = (var, None)
            r += 2
        if r == 0:
            ctk.CTkLabel(box, text="Für dieses Board gibt es nur eine Bauweise.", text_color=FW_DIM).grid(
                row=0, column=0, sticky="w", padx=12, pady=10)
        update_result()
        build_settings(adv)

    # Laufzeit-Einstellungen: "Standard" = nichts schreiben. Werte stehen in
    # der Anzeige-Einheit (s, min, h); beim Schreiben wird umgerechnet.
    setting_widgets = {}

    def build_settings(parent):
        setting_widgets.clear()
        saved = settings.get("fw_settings", {})
        parent.grid_columnconfigure(0, weight=1)
        holder = ctk.CTkFrame(parent, fg_color=FW_CARD, corner_radius=10)
        toggle = ctk.CTkButton(parent, text="▸ Firmware-Einstellungen (optional)", anchor="w", fg_color="transparent",
                               hover_color=FW_CARD2, font=ctk.CTkFont(weight="bold"))
        toggle.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(parent, text="Werden nach dem Flashen in jeden Tracker geschrieben. „Standard“ lässt den Wert "
                                  "unverändert. Geht nur mit Firmware, die Einstellungen kennt (offizielle Firmware).",
                     text_color=FW_DIM, anchor="w", justify="left", wraplength=700).grid(row=1, column=0, sticky="w", padx=4)

        def flip():
            if holder.winfo_ismapped():
                holder.grid_forget()
                toggle.configure(text="▸ Firmware-Einstellungen (optional)")
            else:
                holder.grid(row=2, column=0, sticky="ew", pady=(6, 0))
                toggle.configure(text="▾ Firmware-Einstellungen (optional)")
        toggle.configure(command=flip)
        if saved:
            flip()

        reset_var = tk.BooleanVar(value=bool(settings.get("fw_settings_reset", False)))
        ctk.CTkCheckBox(holder, text="Vorher alle Einstellungen im Tracker auf Standard zurücksetzen",
                        variable=reset_var).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 4))
        setting_widgets["__reset__"] = reset_var
        row = 1
        for group, items in FW_SETTINGS:
            ctk.CTkLabel(holder, text=group, font=ctk.CTkFont(size=14, weight="bold"), anchor="w").grid(
                row=row, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 2))
            row += 1
            for name, label, kind, default, unit, factor, help_text in items:
                label_with_help(holder, row, label, help_text, padx=24).grid(
                    row=row, column=0, sticky="w", padx=(24, 8), pady=(4, 0))
                cell = ctk.CTkFrame(holder, fg_color="transparent")
                cell.grid(row=row, column=1, sticky="w", pady=(4, 0))
                if kind == "bool":
                    std = "Standard"
                    w = ctk.CTkSegmentedButton(cell, values=[std, "An", "Aus"])
                    w.set({True: "An", False: "Aus"}.get(saved.get(name), std))
                    w.pack(side="left")
                elif kind == "enum":
                    std = "Standard"
                    w = ctk.CTkSegmentedButton(cell, values=[std] + list(factor.values()))
                    w.set(factor.get(saved.get(name), std))
                    w.pack(side="left")
                elif kind == "int":
                    w = ctk.CTkEntry(cell, width=90, placeholder_text=f"{default}")
                    if name in saved:
                        w.insert(0, str(saved[name]))
                    w.pack(side="left")
                    ctk.CTkLabel(cell, text=f"{unit}   (leer = Standard, meist {default} {unit})", text_color=FW_DIM).pack(side="left", padx=6)
                else:  # color
                    w = {"rgb": saved.get(name)}
                    swatch = ctk.CTkButton(cell, text="Farbe wählen…", width=130)

                    def pick(w=w, swatch=swatch):
                        from tkinter import colorchooser
                        c = colorchooser.askcolor(parent=win, title="LED-Farbe")
                        if c and c[0]:
                            w["rgb"] = [int(v) for v in c[0]]
                            swatch.configure(fg_color=c[1], text=c[1])

                    def clear(w=w, swatch=swatch):
                        w["rgb"] = None
                        swatch.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"], text="Farbe wählen…")
                    swatch.configure(command=pick)
                    swatch.pack(side="left")
                    ctk.CTkButton(cell, text="Standard", width=80, fg_color="transparent", border_width=1,
                                  border_color=FW_SLATE, command=clear).pack(side="left", padx=6)
                    if w["rgb"]:
                        hexc = "#%02x%02x%02x" % tuple(w["rgb"])
                        swatch.configure(fg_color=hexc, text=hexc)
                setting_widgets[name] = (kind, w, factor)
                row += 2
        ctk.CTkLabel(holder, text="").grid(row=row, column=0, pady=2)

    # -> (Befehle, Fehlertext). Speichert die Auswahl fuer das naechste Mal.
    def collect_settings():
        if not setting_widgets:
            return [], None
        values, cmds = {}, []
        reset = setting_widgets["__reset__"].get()
        if reset:
            cmds.append("reset_config all")
        for name, (kind, w, factor) in setting_widgets.items():
            if name == "__reset__":
                continue
            if kind == "bool":
                v = w.get()
                if v in ("An", "Aus"):
                    values[name] = v == "An"
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
                        return None, f"„{text}“ ist keine Zahl."
                    values[name] = int(num) if num.is_integer() else num
                    cmds.append(f"write_config {name} {int(round(num * factor))}")
            elif kind == "color" and w["rgb"]:
                values[name] = w["rgb"]
                for ch, v in zip("rgb", w["rgb"]):
                    cmds.append(f"write_config led_default_color_{ch} {round(v * 10000 / 255)}")
        settings["fw_settings"] = values
        settings["fw_settings_reset"] = reset
        save_settings()
        return cmds, None

    # ---------- 3: Geraete waehlen ----------
    f3 = make_step(2, "Geräte auswählen", "Welche angesteckten Geräte die Firmware bekommen")
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
        values = list(label_to_port.keys()) or ["Keine Ports gefunden"]
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
            label = free[0] if free else "Kein passendes Gerät gefunden"
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
                set_status(r, "kein Port", "red")
                continue
            dev = get_or_add_device(info)
            dev.manual_off = False
            r["dev"] = dev
            if not role_matches(dev.is_receiver):
                set_status(r, "passt nicht zum Gerätetyp", "orange")
                continue
            if dev.connected or connect_device(dev, ask=not asked, parent=win):
                set_status(r, f"verbunden ({device_name(dev)})", "green")
                continue
            e = dev.last_error
            if e is not None and is_permission_error(e):
                asked = True
            set_status(r, "keine Berechtigung" if e is not None and is_permission_error(e) else f"Fehler: {e}", "red")
        update_next3()

    def valid_targets():
        return [r for r in rows if r["dev"] and r["dev"].connected and role_matches(r["dev"].is_receiver)]

    b_add = ctk.CTkButton(dev_bar, text="+ Gerät", width=90, command=add_row)
    b_add.pack(side="left", padx=(0, 5))
    b_all = ctk.CTkButton(dev_bar, text="Alle erkannten", width=120, command=add_all_detected)
    b_all.pack(side="left", padx=5)
    b_conn = ctk.CTkButton(dev_bar, text="Alle verbinden", width=120, command=connect_all)
    b_conn.pack(side="left", padx=5)
    ToolTip(b_add, "Weiteres Gerät hinzufügen")
    ToolTip(b_all, "Alle angesteckten Geräte dieses Typs übernehmen")
    next3_btn = nav(f3, 2, next_cmd=lambda: go(3))

    def update_next3():
        next3_btn.configure(state="normal" if valid_targets() else "disabled")

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
    f4 = make_step(3, "Flash-Methode", "Wie die Firmware auf das Gerät kommt")
    f4.grid_columnconfigure(0, weight=1)

    def enter_method():
        for w in f4.winfo_children():
            w.destroy()
        is_uf2 = st["asset"]["ext"] == "uf2"
        box = ctk.CTkFrame(f4, fg_color=FW_CARD, corner_radius=10)
        box.grid(row=0, column=0, sticky="ew", padx=6)
        method = tk.StringVar(value="uf2" if is_uf2 else "")
        ctk.CTkRadioButton(box, text="UF2-Laufwerk – Gerät startet in den Bootloader, die Datei wird kopiert",
                           variable=method, value="uf2", state="normal" if is_uf2 else "disabled").pack(anchor="w", padx=12, pady=(10, 4))
        ctk.CTkRadioButton(box, text="Seriell (nrfutil) – für .hex-Dateien, noch nicht verfügbar",
                           variable=method, value="serial", state="disabled").pack(anchor="w", padx=12, pady=(4, 10))
        if st["role"] == "tracker":
            ctk.CTkCheckBox(box, text="Kopplungsdaten vorher löschen (danach neu koppeln)",
                            variable=clear_var).pack(anchor="w", padx=12, pady=(0, 10))
        nxt = nav(f4, 2, next_cmd=lambda: go(4), next_text="Weiter zum Flashen")
        if is_uf2:
            nxt.configure(state="normal")
        else:
            ctk.CTkLabel(f4, text=f"{st['asset']['name']} ist eine .hex-Datei. Dafür gibt es noch keine "
                                  "funktionierende Flash-Methode.", text_color="red", anchor="w",
                         justify="left", wraplength=700).grid(row=1, column=0, sticky="ew", padx=6, pady=(8, 0))

    # ---------- 5: Flashen ----------
    f5 = make_step(4, "Flashen", "Firmware aufspielen")
    f5.grid_columnconfigure(0, weight=1)
    flash_ctl = {}

    def enter_flash():
        for w in f5.winfo_children():
            w.destroy()
        targets = valid_targets()
        src = st["asset"].get("src") or st["source"]
        version = st["asset"].get("tag") or "eigene Datei"
        cmds, _ = collect_settings()
        extra = f"\nEinstellungen:  {len(cmds or [])} Befehl(e) nach dem Flashen" if cmds else ""
        box = ctk.CTkFrame(f5, fg_color=FW_CARD, corner_radius=10)
        box.grid(row=0, column=0, sticky="ew", padx=6)
        ctk.CTkLabel(box, text=f"Firmware:  {st['asset']['name']}\nQuelle:  {src['owner']} / {src['name']}  ·  {version}{extra}",
                     anchor="w", justify="left").pack(anchor="w", padx=12, pady=(10, 6))
        for r in targets:
            r["status2"] = ctk.CTkLabel(box, text=f"{device_name(r['dev'])}: bereit", anchor="w")
            r["status2"].pack(anchor="w", padx=24)
        info = ctk.CTkLabel(f5, text="", anchor="w", text_color=FW_DIM)
        info.grid(row=1, column=0, sticky="ew", padx=6, pady=(8, 0))
        bar = ctk.CTkFrame(f5, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        back = ctk.CTkButton(bar, text="Zurück", width=100, fg_color="transparent", border_width=1,
                             border_color=FW_SLATE, command=go_back)
        back.pack(side="left")
        start = ctk.CTkButton(bar, text="⬇ Flashen starten", width=180, fg_color="green", hover_color="#006400",
                              command=lambda: flash_start(targets))
        start.pack(side="right")
        flash_ctl.update(info=info, start=start, back=back)

    def remember_choice():
        if st["source"]["repo"] is None:
            return
        settings.setdefault("fw_last", {})[st["role"]] = {
            "source": st["source"]["id"], "board": st["board"], "options": sorted(st["asset"]["options"]),
        }
        save_settings()

    def flash_start(targets):
        if st["busy"] or not targets:
            return
        cmds, err = collect_settings()
        if err:
            flash_ctl["info"].configure(text=f"Einstellungen: {err}", text_color="red")
            return
        remember_choice()
        st["busy"] = True
        for b in (flash_ctl["start"], flash_ctl["back"], b_add, b_all, b_conn):
            b.configure(state="disabled")
        threading.Thread(target=flash_worker, args=(targets, dict(st["asset"]), clear_var.get(), cmds), daemon=True).start()

    # Schreibt die Einstellungen und zaehlt die Bestaetigungen ("Updated config")
    def apply_settings(r, cmds):
        dev = r["dev"]
        deadline = time.time() + 15
        while not dev.connected and time.time() < deadline:
            time.sleep(0.5)
        if not dev.connected:
            ui(lambda: set_status(r, "fertig ✅, Einstellungen nicht übertragen (nicht verbunden)", "orange"))
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
            ui(lambda: set_status(r, "fertig ✅, Firmware kennt keine Einstellungen", "orange"))
        elif ok >= writes:
            ui(lambda: set_status(r, f"fertig ✅, {writes} Einstellung(en) übernommen", "green"))
        else:
            ui(lambda: set_status(r, f"fertig ✅, nur {ok} von {writes} Einstellungen bestätigt", "orange"))

    def flash_worker(targets, asset, clear, cmds):
        info = flash_ctl["info"]
        try:
            fw_path = asset.get("path")
            if not fw_path:
                ui(lambda: info.configure(text="Lade Firmware…"))
                fw_path = os.path.join(tempfile.gettempdir(), asset["name"])
                response = requests.get(asset["url"], stream=True, timeout=30)
                response.raise_for_status()
                with open(fw_path, "wb") as f:
                    shutil.copyfileobj(response.raw, f)

            def enter_bootloader(r):
                dev = r["dev"]
                dev.paused = True
                try:
                    with ser_lock:
                        if clear and not dev.is_receiver:  # beim Dongle wuerde clear alle Kopplungen loeschen
                            dev.ser.write(b"clear\n")
                            time.sleep(0.5)
                        dev.ser.write(b"dfu\n")
                        dev.ser.flush()
                    ui(lambda: set_status(r, "Bootloader…"))
                except Exception as e:
                    ui(lambda e=e: set_status(r, f"dfu fehlgeschlagen: {e}", "red"))
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
                ui(lambda: set_status(r, "geschrieben, startet neu…"))

            # Schluessel je Geraet: Seriennummer (gibt es auch unter Windows), sonst Steckplatz
            keys = {id(r): r["dev"].serial_number or r["dev"].location or f"#{i}" for i, r in enumerate(targets)}
            found = {}

            if sys.platform.startswith("linux") and all(r["dev"].location for r in targets):
                # Linux: alle gleichzeitig, Laufwerk und Tracker ueber den USB-Steckplatz zuordnen
                before = set(find_usb_drives())
                for r in targets:
                    enter_bootloader(r)
                ui(lambda: info.configure(text="Warte auf die UF2-Laufwerke…"))
                by_loc = {r["dev"].location: r for r in targets}
                mounts = {}
                deadline = time.time() + 30
                while time.time() < deadline and len(mounts) < len(by_loc):
                    for name, d in find_usb_drives().items():
                        if name in before or d["location"] in mounts or d["location"] not in by_loc:
                            continue
                        mount = mount_drive(d)
                        if mount and os.path.isfile(os.path.join(mount, "INFO_UF2.TXT")):
                            mounts[d["location"]] = mount
                    time.sleep(1)
                ui(lambda: info.configure(text="Schreibe Firmware…"))
                copies = []
                for loc, r in by_loc.items():
                    if loc in mounts:
                        found[keys[id(r)]] = r
                        t = threading.Thread(target=copy_one, args=(r, mounts[loc]), daemon=True)
                        t.start()
                        copies.append(t)
                    else:
                        ui(lambda rr=r: set_status(rr, "kein UF2-Laufwerk gefunden", "red"))
                for t in copies:
                    t.join()
            else:
                # Windows/macOS (oder Steckplatz unbekannt): einer nach dem anderen,
                # das jeweils neu auftauchende UF2-Laufwerk gehoert zum gerade gestarteten Tracker
                for n, r in enumerate(targets, 1):
                    ui(lambda n=n: info.configure(text=f"Tracker {n} von {len(targets)}…"))
                    before = set(uf2_drive_roots())
                    enter_bootloader(r)
                    root, deadline = None, time.time() + 30
                    while root is None and time.time() < deadline:
                        root = next((d for d in uf2_drive_roots() if d not in before), None)
                        time.sleep(0.5)
                    if root is None:
                        ui(lambda rr=r: set_status(rr, "kein UF2-Laufwerk gefunden", "red"))
                        continue
                    found[keys[id(r)]] = r
                    copy_one(r, root)
                    # warten, bis das Laufwerk weg ist, sonst haelt der naechste Tracker es fuer seins
                    deadline = time.time() + 15
                    while root in uf2_drive_roots() and time.time() < deadline:
                        time.sleep(0.5)

            # Erfolg = das Geraet meldet sich mit neuer Firmware wieder als Port
            waiting = dict(found)
            deadline = time.time() + 30
            while waiting and time.time() < deadline:
                for p in serial.tools.list_ports.comports():
                    for key in (p.serial_number, (p.location or "").split(":")[0]):
                        r = waiting.pop(key, None) if key else None
                        if r:
                            ui(lambda rr=r: set_status(rr, "fertig ✅", "green"))
                time.sleep(1)
            for r in waiting.values():
                ui(lambda rr=r: set_status(rr, "geschrieben, aber nicht zurückgemeldet", "orange"))

            if cmds:
                done_rows = [r for key, r in found.items() if key not in waiting]
                for r in done_rows:
                    r["dev"].paused = False  # damit watch_devices sie wieder verbindet
                ui(lambda: info.configure(text="Übertrage Einstellungen…"))
                workers = [threading.Thread(target=apply_settings, args=(r, cmds), daemon=True) for r in done_rows]
                for t in workers:
                    t.start()
                for t in workers:
                    t.join()

            ok = len(found) - len(waiting)
            ui(lambda: info.configure(text=f"{ok} von {len(targets)} fertig.",
                                      text_color="green" if ok == len(targets) else "orange"))
            ui(lambda: append_text(f"Firmware-Tool: {ok} von {len(targets)} Geräten mit {asset['name']} geflasht.\n", "success"))
        except Exception as e:
            ui(lambda e=e: info.configure(text=f"Fehler: {e}", text_color="red"))
        finally:
            for r in targets:
                r["dev"].paused = False  # watch_devices verbindet sie wieder
            st["busy"] = False

            def done():
                for b in (flash_ctl["back"], b_add, b_all, b_conn):
                    b.configure(state="normal")
                flash_ctl["start"].configure(state="normal", text="Nochmal flashen")
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
    src_id = settings.get("fw_last", {}).get("tracker", {}).get("source", "main")
    select_source(next((s for s in fw_sources() if s["id"] == src_id), fw_sources()[0]))

# Buttons!
def start_firmware_download():
    threading.Thread(target=download_firmware, daemon=True).start()

btn_download_fw = ctk.CTkButton(top_frame, text="⬇ Firmware", width=80, command=start_firmware_download)
btn_download_fw.pack(side="left", padx=5)
ToolTip(btn_download_fw, "Upgrade your firmware!")

btn_multi_fw = ctk.CTkButton(top_frame, text="DIY Firmware-Tool", width=80, command=open_multiflash_window,
                             fg_color=SV_PURPLE, hover_color=SV_PURPLE_H, text_color="white")
btn_multi_fw.pack(side="left", padx=5)
ToolTip(btn_multi_fw, "Tracker konfigurieren und auf einmal flashen")

status_label = ctk.CTkLabel(top_frame, text="Not connected", text_color="red")
status_label.pack(side="left", padx=10)

tab_view = ctk.CTkTabview(app, width=580, height=130, corner_radius=10, anchor="w")
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

ui_btn(tracker_btn_frame, "Info", lambda: send_command("info"), "Get device information").grid(row=0, column=0, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Reboot", lambda: send_command("reboot"), "Soft reset the device").grid(row=0, column=1, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Scan", lambda: send_command("scan"), "Restart sensor scan").grid(row=0, column=2, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Calibrate", lambda: send_command("calibrate"), "Calibrate sensor ZRO").grid(row=0, column=3, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Calibrate 6 Sides", lambda: send_command("6-side"), "Calibrate 6-side accelerometer").grid(row=0, column=4, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Mag Clear", lambda: send_command("mag"), "Clear magnetometer calibration").grid(row=0, column=5, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Battery", lambda: send_command("battery"), "Get battery information").grid(row=0, column=6, padx=5, pady=5)

ui_btn(tracker_btn_frame, "Pairing Mode", lambda: send_command("pair"), "Enter pairing mode").grid(row=1, column=0, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Clear Con. Data", lambda: send_command("clear"), "Clear pairing data").grid(row=1, column=1, padx=5, pady=5)
ui_btn(tracker_btn_frame, "DFU", lambda: send_command("dfu"), "Enter DFU bootloader (if available)").grid(row=1, column=2, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Uptime", lambda: send_command("uptime"), "Get device uptime").grid(row=1, column=3, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Debug", lambda: send_command("debug"), "Print debug log").grid(row=1, column=4, padx=5, pady=5)
ui_btn(tracker_btn_frame, "Meow!", lambda: send_command("meow"), "Meow!").grid(row=1, column=5, padx=5, pady=5)

# Receiver tab
receiver_tab = tab_view.add("Receiver")
receiver_btn_frame = ctk.CTkFrame(receiver_tab)
receiver_btn_frame.pack(pady=10, padx=10)

ui_btn(receiver_btn_frame, "Info", lambda: send_command("info"), "Get device information").grid(row=0, column=0, padx=5, pady=5)
ui_btn(receiver_btn_frame, "List", lambda: send_command("list"), "Get paired devices").grid(row=0, column=1, padx=5, pady=5)
ui_btn(receiver_btn_frame, "Reboot", lambda: send_command("reboot"), "Soft reset the device").grid(row=0, column=2, padx=5, pady=5)
ui_btn(receiver_btn_frame, "Remove", lambda: send_command("remove"), "Remove last paired device").grid(row=0, column=3, padx=5, pady=5)
ui_btn(receiver_btn_frame, "Pairing Mode", lambda: send_command("pair"), "Enter pairing mode").grid(row=0, column=4, padx=5, pady=5)

ui_btn(receiver_btn_frame, "✖ Saved Devices", lambda: send_command("clear"), "Clear stored devices").grid(row=1, column=0, padx=5, pady=5)
ui_btn(receiver_btn_frame, "DFU", lambda: send_command("dfu"), "Enter DFU bootloader (if available)").grid(row=1, column=1, padx=5, pady=5)
ui_btn(receiver_btn_frame, "Uptime", lambda: send_command("uptime"), "Get device uptime").grid(row=1, column=2, padx=5, pady=5)
ui_btn(receiver_btn_frame, "Meow!", lambda: send_command("meow"), "Meow!").grid(row=1, column=3, padx=5, pady=5)
ui_btn(receiver_btn_frame, "⎋ Pairing Mode", lambda: send_command("exit"), "Exit pairing mode").grid(row=1, column=4, padx=5, pady=5)

# Settings tab
settings_tab = tab_view.add("Settings")
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
    text=f"SmolSlimeConfigurator Version 9 · Fassung v{APP_VERSION} ({platform_name})",
    text_color="gray"
)
version_label.pack(anchor="ne", padx=10, pady=5)

firmware_frame = ctk.CTkFrame(settings_frame)
firmware_frame.pack(pady=10, fill="x")

ctk.CTkLabel(
    firmware_frame,
    text="Firmware Source:",
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
ToolTip(rb_main, "Main firmware repo")

rb_kouno = ctk.CTkRadioButton(
    firmware_frame,
    text="Kounocom (Backup)",
    variable=firmware_source_var,
    value="kounocom",
    command=on_firmware_source_change
)
rb_kouno.pack(anchor="w", padx=10)
ToolTip(rb_kouno, "Backup firmware option")

rb_custom = ctk.CTkRadioButton(
    firmware_frame,
    text="Custom Repo",
    variable=firmware_source_var,
    value="custom",
    command=on_firmware_source_change
)
rb_custom.pack(anchor="w", padx=10)
ToolTip(rb_custom, "Custom firmware repo")

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
ToolTip(custom_repo_entry, "Custom firmware repo")

def toggle_theme(choice):
    settings["theme"] = choice
    ctk.set_appearance_mode(choice)

    if sys.platform.startswith("linux"):
        set_linux_scaling()

    save_settings()

def toggle_accent(choice):
    settings["accent"] = choice
    apply_accent(choice)
    save_settings()

def toggle_tooltips():
    global TOOLTIPS_ENABLED
    settings["tooltips"] = not settings["tooltips"]
    TOOLTIPS_ENABLED = settings["tooltips"]
    save_settings()
    append_text(f"Tooltips {'enabled' if TOOLTIPS_ENABLED else 'disabled'}.\n", "success")

def open_repo():
    webbrowser.open("https://github.com/ICantMakeThings/SmolSlimeConfigurator")

appearance_frame = ctk.CTkFrame(settings_frame)
appearance_frame.pack(pady=10, fill="x")

ctk.CTkLabel(appearance_frame, text="Appearance Mode:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
theme_menu = ctk.CTkOptionMenu(appearance_frame, values=["light", "dark"], command=toggle_theme)
theme_menu.set(settings["theme"])
theme_menu.grid(row=0, column=1, padx=5, pady=5, sticky="w")

ctk.CTkLabel(appearance_frame, text="Accent Colour:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
accent_menu = ctk.CTkOptionMenu(appearance_frame, values=["slimevr", "blue", "green", "dark-blue"], command=toggle_accent)
accent_menu.set(settings["accent"])
accent_menu.grid(row=1, column=1, padx=5, pady=5, sticky="w")
ToolTip(accent_menu, "Requires app restart")

# Buttonssss
button_row = ctk.CTkFrame(settings_frame)
button_row.pack(pady=15)

tooltips_button = ctk.CTkButton(button_row, text="Toggle Tooltips", command=toggle_tooltips)
tooltips_button.pack(side="left", padx=10)
ToolTip(tooltips_button, "Yk what each button does? Turn off tooltips!")


repo_button = ctk.CTkButton(button_row, text="Open GitHub Repo", command=open_repo)
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
    for b in (btn_check_update, update_button):
        b.configure(text=text)
    app.after(4000, lambda: [b.configure(text="Nach Updates suchen", state="normal")
                             for b in (btn_check_update, update_button)])

def check_for_update(manual=False):
    if manual:
        for b in (btn_check_update, update_button):
            b.configure(text="Suche…", state="disabled")

    def work():
        try:
            # Die Release-Seite leitet auf den neuesten Tag weiter. Anders als die API hat sie
            # kein Limit von 60 Abfragen pro Stunde, an dem die Pruefung sonst scheitern kann.
            response = requests.get(f"https://github.com/{UPDATE_REPO}/releases/latest",
                                    allow_redirects=False, timeout=10)
            tag = response.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]
            if response.status_code not in (301, 302) or not ver_tuple(tag):
                raise RuntimeError(f"keine Antwort von GitHub (HTTP {response.status_code})")
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
                    app.after(0, lambda: show_check_result(f"Neu: {tag}"))
            elif manual:
                app.after(0, lambda: show_check_result(f"✓ v{APP_VERSION} ist aktuell"))
        except Exception as e:
            if manual:
                app.after(0, lambda e=e: (append_text(f"Update-Prüfung fehlgeschlagen: {e}\n", "error"),
                                          show_check_result("Prüfung fehlgeschlagen")))
    threading.Thread(target=work, daemon=True).start()

def offer_update(tag, asset, notes):
    update_info.update(tag=tag, asset=asset, notes=notes)
    btn_update.configure(text=f"⬆ Update {tag}", state="normal")
    btn_update.pack(side="left", padx=5, before=status_label)
    append_text(f"Update verfügbar: {tag} (installiert: v{APP_VERSION}).\n", "success")

def install_update():
    from tkinter import messagebox
    tag, asset = update_info.get("tag"), update_info.get("asset")
    if not (getattr(sys, "frozen", False) and sys.platform.startswith(("linux", "win")) and asset):
        webbrowser.open(f"https://github.com/{UPDATE_REPO}/releases/latest")
        return
    notes = update_info.get("notes", "").strip()
    if not messagebox.askyesno("Update", f"Auf {tag} aktualisieren?\n\n{notes[:800]}\n\nDas Programm startet danach neu.",
                               parent=app):
        return
    btn_update.configure(state="disabled", text="Lade Update…")
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
                raise RuntimeError("Download unvollständig")
            os.chmod(new, 0o755)
            if sys.platform.startswith("win"):
                # Windows sperrt die laufende .exe gegen Ueberschreiben, Umbenennen geht aber
                old = exe + ".alt"
                if os.path.exists(old):
                    os.remove(old)
                os.rename(exe, old)
            os.replace(new, exe)  # Linux erlaubt das Ersetzen der laufenden Datei direkt
        except Exception as e:
            app.after(0, lambda e=e: (append_text(f"Update fehlgeschlagen: {e}\n", "error"),
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
    subprocess.Popen([sys.executable], cwd=os.path.dirname(sys.executable), env=env, start_new_session=True)
    app.destroy()
    os._exit(0)

btn_update = ctk.CTkButton(top_frame, text="⬆ Update", width=80, fg_color="green", hover_color="#006400",
                           command=install_update)
ToolTip(btn_update, "Neue Fassung herunterladen und neu starten")

update_button = ctk.CTkButton(button_row, text="Nach Updates suchen", command=lambda: check_for_update(manual=True))
update_button.pack(side="left", padx=10)
ToolTip(update_button, f"Installiert: v{APP_VERSION}")
app.after(3000, check_for_update)


# CLI, links daneben die Geraete zum Umschalten
console_row = ctk.CTkFrame(app, fg_color="transparent")

sidebar = ctk.CTkFrame(console_row, width=130)
sidebar.pack(side="left", fill="y", padx=(0, 5))
btn_pair_all = ctk.CTkButton(sidebar, text="🔗 Koppeln", width=110, command=pair_all,
                             fg_color=SV_PURPLE, hover_color=SV_PURPLE_H, text_color="white")
btn_pair_all.pack(side="bottom", fill="x", padx=5, pady=5)
device_list = ctk.CTkScrollableFrame(sidebar, width=110, fg_color="transparent")
device_list.pack(fill="both", expand=True, padx=2, pady=(2, 0))
ToolTip(btn_pair_all, "Dongle und alle verbundenen Tracker gleichzeitig in den Kopplungsmodus")

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

command_entry = ctk.CTkEntry(entry_frame, placeholder_text="Enter custom command...")
command_entry.pack(side="left", fill="x", expand=True, padx=(0, 5), pady=5)

btn_send = ctk.CTkButton(entry_frame, text="Send", width=80, command=send_custom_command)
btn_send.pack(side="left", pady=5)

btn_clear = ctk.CTkButton(entry_frame, text="X", width=30, command=lambda: console.configure(state="normal") or console.delete("1.0", "end") or console.configure(state="disabled"))
btn_clear.pack(side="left", padx=(5,0), pady=5)

# Erst nach der Eingabezeile packen, damit die nicht abgeschnitten wird
console_row.pack(pady=(0, 5), padx=10, fill="both", expand=True)
ToolTip(btn_clear, "Clear")

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
