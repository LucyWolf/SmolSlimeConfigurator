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
    "accent": "dark-blue",
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

load_settings()
ctk.set_appearance_mode(settings["theme"])
ctk.set_default_color_theme(settings["accent"])

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
app = ctk.CTk()
app.title("SmolSlime Configurator")
app.geometry("1010x500")

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
        self.ser = None
        self.stop = threading.Event()
        self.paused = False      # waehrend des Flashens nicht neu verbinden
        self.manual_off = False  # vom Benutzer getrennt
        self.last_error = None
        self.number = 0
        self.console = None
        self.button = None

    @property
    def key(self):
        return self.serial_number or self.location or self.port

    @property
    def is_dongle(self):
        return bool(self.serial_number) and self.serial_number == settings.get("dongle_serial")

    @property
    def is_receiver(self):
        return self.is_dongle or "receiver" in self.product.lower()

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
            fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"] if active else ("gray75", "gray25"),
            text_color=ctk.ThemeManager.theme["CTkButton"]["text_color"] if dev.connected else "gray50",
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

btn_connect = ctk.CTkButton(top_frame, text="Connect", command=connect_to_port)
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
    
def open_firmware_popup():
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
        selected_firmware.set(fw)
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
            "receiver": "receiver" in name.lower()
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

multi_win = None

def open_multiflash_window():
    global multi_win
    if not sys.platform.startswith("linux"):
        append_text("Mehrere Tracker flashen gibt es nur unter Linux.\n", "error")
        return
    if multi_win is not None and multi_win.winfo_exists():
        multi_win.focus()
        return

    win = ctk.CTkToplevel(app)
    multi_win = win
    win.title("Mehrere Tracker flashen")
    win.geometry("700x600")
    win.transient(app)

    rows = []
    label_to_port = {}
    fw_mode = tk.StringVar(value="list")
    custom_uf2 = {"path": None}
    clear_var = tk.BooleanVar(value=False)
    busy = {"on": False}

    def ui(fn):
        app.after(0, fn)

    # Firmware
    fw_frame = ctk.CTkFrame(win)
    fw_frame.pack(fill="x", padx=10, pady=(10, 5))
    ctk.CTkLabel(fw_frame, text="Firmware", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=5, pady=(5, 0))
    ctk.CTkRadioButton(fw_frame, text="Aus der Liste:", variable=fw_mode, value="list").grid(row=1, column=0, sticky="w", padx=5, pady=3)
    ctk.CTkButton(fw_frame, textvariable=selected_firmware, command=open_firmware_popup, width=320).grid(row=1, column=1, sticky="w", padx=5, pady=3)
    ctk.CTkRadioButton(fw_frame, text="Eigene .uf2:", variable=fw_mode, value="custom").grid(row=2, column=0, sticky="w", padx=5, pady=3)

    def pick_uf2():
        path = filedialog.askopenfilename(parent=win, title="UF2-Datei wählen", filetypes=[("UF2 files", "*.uf2")])
        if path:
            custom_uf2["path"] = path
            fw_mode.set("custom")
            custom_btn.configure(text=os.path.basename(path))

    custom_btn = ctk.CTkButton(fw_frame, text="Datei wählen…", command=pick_uf2, width=320)
    custom_btn.grid(row=2, column=1, sticky="w", padx=5, pady=3)
    ctk.CTkCheckBox(fw_frame, text="Kopplungsdaten vorher löschen (danach neu koppeln)", variable=clear_var).grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=(3, 8))

    # Trackerliste
    list_frame = ctk.CTkScrollableFrame(win, height=280)
    list_frame.pack(fill="both", expand=True, padx=10, pady=5)

    def refresh_choices():
        label_to_port.clear()
        for p in list_tracker_ports():
            lbl = port_label(p) + ("  (Empfänger)" if p["receiver"] else "")
            label_to_port[lbl] = p
        values = list(label_to_port.keys()) or ["Keine Ports gefunden"]
        for r in rows:
            r["menu"].configure(values=values)
        return values

    def set_status(r, text, color=None):
        r["status"].configure(text=text, text_color=color or ctk.ThemeManager.theme["CTkLabel"]["text_color"])

    def row_port(r):
        return label_to_port.get(r["var"].get())

    def remove_row(r):
        if busy["on"]:
            return
        r["frame"].destroy()
        rows.remove(r)

    def add_row(label=None):
        values = refresh_choices()
        if label is None:
            used = {r["var"].get() for r in rows}
            free = [v for v in values if v not in used and v in label_to_port and not label_to_port[v]["receiver"]]
            label = free[0] if free else "Kein Tracker gefunden"
        frame = ctk.CTkFrame(list_frame)
        frame.pack(fill="x", pady=2)
        r = {"frame": frame, "var": tk.StringVar(value=label), "dev": None}
        ctk.CTkLabel(frame, text=f"#{len(rows) + 1}", width=30).pack(side="left", padx=(5, 0))
        r["menu"] = ctk.CTkOptionMenu(frame, values=values, variable=r["var"], width=330,
                                      command=lambda _v, rr=r: (rr.update(dev=None), set_status(rr, "")))
        r["menu"].pack(side="left", padx=5, pady=4)
        r["status"] = ctk.CTkLabel(frame, text="", anchor="w")
        r["status"].pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(frame, text="−", width=28, command=lambda rr=r: remove_row(rr)).pack(side="right", padx=5)
        rows.append(r)

    def add_all_detected():
        refresh_choices()
        used = {r["var"].get() for r in rows}
        for lbl, p in list(label_to_port.items()):
            if not p["receiver"] and lbl not in used:
                add_row(lbl)

    def connect_all():
        if busy["on"]:
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
            if dev.connected or connect_device(dev, ask=not asked, parent=win):
                set_status(r, f"verbunden ({device_name(dev)})", "green")
                continue
            e = dev.last_error
            if e is not None and is_permission_error(e):
                asked = True
            set_status(r, "keine Berechtigung" if e is not None and is_permission_error(e) else f"Fehler: {e}", "red")

    def flash_all():
        if busy["on"]:
            return
        targets = [r for r in rows if r["dev"] and r["dev"].connected and not r["dev"].is_dongle]
        if not targets:
            info_label.configure(text="Erst „Alle verbinden“ drücken.", text_color="red")
            return
        if fw_mode.get() == "custom":
            src = custom_uf2["path"]
            if not src:
                info_label.configure(text="Keine .uf2-Datei gewählt.", text_color="red")
                return
            is_url = False
        else:
            src = firmware_urls.get(selected_firmware.get())
            if not src:
                info_label.configure(text="Erst eine Firmware aus der Liste wählen.", text_color="red")
                return
            is_url = True
        if not src.lower().endswith(".uf2"):
            info_label.configure(text="Mehrfach-Flashen geht nur mit .uf2-Dateien.", text_color="red")
            return
        busy["on"] = True
        for b in action_buttons:
            b.configure(state="disabled")
        threading.Thread(target=flash_worker, args=(targets, src, is_url, clear_var.get()), daemon=True).start()

    def flash_worker(targets, src, is_url, clear):
        try:
            fw_path = src
            if is_url:
                ui(lambda: info_label.configure(text="Lade Firmware…", text_color="gray"))
                fw_path = os.path.join(tempfile.gettempdir(), os.path.basename(src))
                response = requests.get(src, stream=True, timeout=30)
                response.raise_for_status()
                with open(fw_path, "wb") as f:
                    shutil.copyfileobj(response.raw, f)

            before = set(find_usb_drives())
            for r in targets:
                dev = r["dev"]
                dev.paused = True
                r["location"] = dev.location
                try:
                    with ser_lock:
                        if clear:
                            dev.ser.write(b"clear\n")
                            time.sleep(0.5)
                        dev.ser.write(b"dfu\n")
                        dev.ser.flush()
                    ui(lambda rr=r: set_status(rr, "Bootloader…"))
                except Exception as e:
                    ui(lambda rr=r, e=e: set_status(rr, f"dfu fehlgeschlagen: {e}", "red"))
                disconnect_device(dev)
                ui(refresh_sidebar)
                ui(sync_active)

            ui(lambda: info_label.configure(text="Warte auf die UF2-Laufwerke…", text_color="gray"))
            pending = {r["location"]: r for r in targets if r["location"]}
            found = {}
            deadline = time.time() + 30
            while time.time() < deadline and len(found) < len(pending):
                for name, d in find_usb_drives().items():
                    if name in before or d["location"] in found or d["location"] not in pending:
                        continue
                    mount = mount_drive(d)
                    if mount and os.path.isfile(os.path.join(mount, "INFO_UF2.TXT")):
                        found[d["location"]] = mount
                time.sleep(1)

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

            ui(lambda: info_label.configure(text="Schreibe Firmware…", text_color="gray"))
            copies = []
            for loc, r in pending.items():
                if loc in found:
                    t = threading.Thread(target=copy_one, args=(r, found[loc]), daemon=True)
                    t.start()
                    copies.append(t)
                else:
                    ui(lambda rr=r: set_status(rr, "kein UF2-Laufwerk gefunden", "red"))
            for r in targets:
                if not r["location"]:
                    ui(lambda rr=r: set_status(rr, "USB-Steckplatz unbekannt", "red"))
            for t in copies:
                t.join()

            # Erfolg = der Tracker meldet sich mit neuer Firmware wieder als Port
            waiting = {loc: r for loc, r in pending.items() if loc in found}
            deadline = time.time() + 30
            while waiting and time.time() < deadline:
                for p in list_tracker_ports():
                    r = waiting.pop(p["location"], None)
                    if r:
                        ui(lambda rr=r, pp=p: (refresh_choices(), rr["var"].set(next((l for l, q in label_to_port.items() if q["device"] == pp["device"]), rr["var"].get())), set_status(rr, "fertig ✅", "green")))
                time.sleep(1)
            for r in waiting.values():
                ui(lambda rr=r: set_status(rr, "geschrieben, aber nicht zurückgemeldet", "orange"))

            ok = len(found) - len(waiting)
            ui(lambda: info_label.configure(text=f"{ok} von {len(targets)} fertig.", text_color="green" if ok == len(targets) else "orange"))
            ui(lambda: append_text(f"Mehrfach-Flash: {ok} von {len(targets)} Trackern mit {os.path.basename(fw_path)} geflasht.\n", "success"))
        except Exception as e:
            ui(lambda e=e: info_label.configure(text=f"Fehler: {e}", text_color="red"))
        finally:
            for r in targets:
                r["dev"].paused = False  # watch_devices verbindet sie wieder
            busy["on"] = False
            ui(lambda: [b.configure(state="normal") for b in action_buttons])

    # Knoepfe
    btn_frame = ctk.CTkFrame(win)
    btn_frame.pack(fill="x", padx=10, pady=5)
    b_add = ctk.CTkButton(btn_frame, text="+ Tracker", width=100, command=add_row)
    b_add.pack(side="left", padx=5, pady=5)
    b_all = ctk.CTkButton(btn_frame, text="Alle erkannten hinzufügen", command=add_all_detected)
    b_all.pack(side="left", padx=5, pady=5)
    b_flash = ctk.CTkButton(btn_frame, text="⬇ Alle flashen", command=flash_all, fg_color="green", hover_color="#006400")
    b_flash.pack(side="right", padx=5, pady=5)
    b_conn = ctk.CTkButton(btn_frame, text="Alle verbinden", command=connect_all)
    b_conn.pack(side="right", padx=5, pady=5)
    action_buttons = [b_add, b_all, b_flash, b_conn]
    ToolTip(b_add, "Weiteren Tracker hinzufügen")
    ToolTip(b_all, "Alle angesteckten Tracker übernehmen (ohne Empfänger)")
    ToolTip(b_conn, "Alle Tracker in der Liste verbinden")
    ToolTip(b_flash, "Alle verbundenen Tracker in den Bootloader schicken und die Firmware aufspielen")

    info_label = ctk.CTkLabel(win, text="Tracker per USB anstecken, mit + hinzufügen, verbinden, flashen.", text_color="gray")
    info_label.pack(fill="x", padx=10, pady=(0, 10))

    def on_close():
        if busy["on"]:
            return
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)
    add_row()

# Buttons!
def start_firmware_download():
    threading.Thread(target=download_firmware, daemon=True).start()

btn_download_fw = ctk.CTkButton(top_frame, text="⬇ Firmware", width=80, command=start_firmware_download)
btn_download_fw.pack(side="left", padx=5)
ToolTip(btn_download_fw, "Upgrade your firmware!")

btn_multi_fw = ctk.CTkButton(top_frame, text="⧉ Mehrere", width=80, command=open_multiflash_window)
btn_multi_fw.pack(side="left", padx=5)
ToolTip(btn_multi_fw, "Mehrere Tracker auf einmal flashen")

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
    text=f"SmolSlimeConfigurator Version 9 ({platform_name})",
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
    ctk.set_default_color_theme(choice)
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
accent_menu = ctk.CTkOptionMenu(appearance_frame, values=["blue", "green", "dark-blue"], command=toggle_accent)
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


# CLI, links daneben die Geraete zum Umschalten
console_row = ctk.CTkFrame(app, fg_color="transparent")

sidebar = ctk.CTkFrame(console_row, width=130)
sidebar.pack(side="left", fill="y", padx=(0, 5))
btn_pair_all = ctk.CTkButton(sidebar, text="🔗 Koppeln", width=110, command=pair_all)
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
    app.iconbitmap(resource_path("icon.ico"))
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
        else:
            device_lost(dev, lost)
    app.after(50, flush_serial_queue)

app.after(50, flush_serial_queue)
app.after(500, watch_devices)
# The MOST PORTAN' PART!!!
app.mainloop()
