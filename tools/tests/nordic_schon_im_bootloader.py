# Wie nordic_dongle, aber der Dongle steckt schon im Bootloader: Magnet-Hinweis, Bootloader taucht auf, Uebertragung,
# Dongle meldet sich wieder -> "fertig". Der Bootloader ist nachgebaut (prueft CRC wie das Original).
exec(open("/src/tools/tests/fake_devices.py").read())
import pty as _pty, tty as _tty, types as _types

phase = {"n": 2}
blm, bls = _pty.openpty(); _tty.setraw(blm)
os.symlink(os.ttyname(bls), "/tmp/ttyACM_nordic")
BL_PORT = _types.SimpleNamespace(device="/tmp/ttyACM_nordic", serial_number="F1A2B3C4D5E6", location="",
                                 product="Open DFU Bootloader", description="Open DFU Bootloader", vid=0x1915, pid=0x521F)
fw = bytearray(); expected = {"size": None}

def _rx():
    buf, esc = bytearray(), False
    while True:
        c = os.read(blm, 1)[0]
        if c == 0xC0:
            if buf: return bytes(buf)
            continue
        if esc: buf.append(0xC0 if c == 0xDC else 0xDB); esc = False
        elif c == 0xDB: esc = True
        else: buf.append(c)

def _tx(op, payload=b""):
    os.write(blm, _slip(bytes([0x60, op, 1]) + payload))

def bootloader():
    cur, objbuf = None, bytearray()
    while True:
        m = _rx(); op = m[0]
        if op == 0x09: _tx(0x09, m[1:2])
        elif op == 0x02: _tx(0x02)
        elif op == 0x07: _tx(0x07, struct.pack("<H", 131))
        elif op == 0x06: _tx(0x06, struct.pack("<III", 512 if m[1] == 1 else 4096, 0, 0))
        elif op == 0x01: cur, objbuf = m[1], bytearray(); _tx(0x01)
        elif op == 0x08:
            objbuf += m[1:]
            if cur == 2: fw.extend(m[1:])
        elif op == 0x03:
            data = fw if cur == 2 else objbuf
            _tx(0x03, struct.pack("<II", len(data), binascii.crc32(data) & 0xFFFFFFFF))
        elif op == 0x04:
            _tx(0x04)
            if cur == 2 and len(fw) >= expected["size"]:
                phase["n"] = 3            # fertig: Bootloader weg, Dongle mit neuer Firmware zurueck
threading.Thread(target=bootloader, daemon=True).start()

def ports():
    return {1: [FAKE_DONGLE], 2: [BL_PORT], 3: [FAKE_DONGLE]}[phase["n"]]
serial.tools.list_ports.comports = ports
settings["fw_last"] = {"tracker": {"source": "main"}}

def to_dongle():
    seg = next(c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkSegmentedButton) and c.winfo_ismapped())
    seg.set("Dongle"); seg._command("Dongle")

def status():
    return [c.cget("text") for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkLabel)
            and any(k in c.cget("text") for k in ("Magnet", "überträgt", "fertig", "fehlgeschlagen", "geschrieben", "von 1"))]

def magnet():
    expected["size"] = len(hex_to_app_bin("/tmp/claude-fw.hex")) if os.path.exists("/tmp/claude-fw.hex") else expected["size"]
    phase["n"] = 2

# echte Holyiot-Firmware statt Download (die App laedt sonst von GitHub)
import shutil as _sh
HEX = "/tmp/holyiot.hex"   # echte Holyiot-Firmware einmal laden (liegt nicht im Repo)
if not os.path.exists(HEX):
    with open(HEX, "wb") as _f:
        _f.write(requests.get("https://github.com/Shine-Bright-Meow/SlimeNRF-Firmware-CI/releases/download/latest/"
                              "SlimeNRF_Holyiot_Dongle_Receiver.hex", timeout=60).content)
expected["size"] = len(hex_to_app_bin(HEX))
_orig_get = requests.get
def fake_get(url, *a, **k):
    if url.endswith("SlimeNRF_Holyiot_Dongle_Receiver.hex"):
        r = _types.SimpleNamespace(raw=open(HEX, "rb"), raise_for_status=lambda: None)
        return r
    return _orig_get(url, *a, **k)
requests.get = fake_get

at(1500, open_multiflash_window)
def pick_board(name):
    menu = next(c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkOptionMenu) and c.winfo_ismapped()
                and name in c.cget("values"))
    menu.set(name); menu._command(name)

at(20000, to_dongle)
at(20500, lambda: pick_board("Holyiot Dongle"))
at(21000, lambda: click("Nächster Schritt"))
at(22000, lambda: click("Nächster Schritt"))
at(23000, lambda: click("Alle verbinden"))
at(23500, lambda: print("Schritt 3:", [c.cget("text") for win in _windows() for c in _walk(win)
                                     if isinstance(c, ctk.CTkLabel) and "im Bootloader" in c.cget("text")],
                        "| Auswahl ohne Bootloader:", [v for m in _walk(multi_win) if isinstance(m, ctk.CTkOptionMenu)
                                                       for v in m.cget("values") if "nordic" in v.lower()], flush=True))
at(24000, lambda: click("Nächster Schritt"))
at(25000, lambda: click("Weiter zum Flashen"))
at(26000, lambda: click("⬇ Flashen starten"))
at(34000, lambda: print("waehrend:", status()[-2:], flush=True))
at(60000, lambda: print("Ende:", status()[-3:], "| empfangen:", len(fw), "/", expected["size"], flush=True))
at(60500, done)
