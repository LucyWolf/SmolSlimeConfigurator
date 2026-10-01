# Geraeteverwaltung zeigt den gemerkten Firmware-Stand und ob die Quelle Neueres hat (ohne Netz: Abruf nachgebaut)
exec(open("/src/tools/tests/fake_devices.py").read())

def fake_releases(repo):
    assets = []
    for name, date in (("SlimeNRF_StackedSmol_SPI.uf2", "2026-09-30"), ("SlimeNRF_Receiver_ProMicro.uf2", "2026-08-01")):
        a = parse_fw_name(name)
        assert a, name
        assets.append(dict(a, date=date, url="http://x/" + name))
    return [{"tag": "latest", "stable": True, "assets": assets}]
fetch_releases = fake_releases

def setup():
    for info in (FAKE_DONGLE, FAKE_TRACKER):
        dev = get_or_add_device(info)
        connect_device(dev, ask=False)
    set_dongle(next(d for d in devices if d.is_receiver))
    tracker = next(d for d in devices if not d.is_receiver)
    dongle = next(d for d in devices if d.is_receiver)
    src = FW_SOURCES[0]
    old = {a["name"]: dict(a, date="2026-09-01", tag="latest", src=src) for a in fake_releases("")[0]["assets"]}
    old["SlimeNRF_Receiver_ProMicro.uf2"]["date"] = "2026-08-01"
    remember_flash(tracker.key, old["SlimeNRF_StackedSmol_SPI.uf2"], "tracker")
    remember_flash(dongle.key, old["SlimeNRF_Receiver_ProMicro.uf2"], "dongle")
    print("GEMERKT:", settings["flashed"][tracker.key])
    remember_flash("EIGENE", {"name": "x.uf2", "src": FW_SOURCES[-1]}, "tracker")   # eigene Datei: nicht merken
    assert "EIGENE" not in settings["flashed"]
    open_device_manager()

def check():
    texts = [c.cget("text") for w in _windows() for c in _walk(w) if isinstance(c, ctk.CTkLabel)]
    joined = "\n".join(texts)
    print("UPDATE:", "⬆ Update verfügbar (neu vom 30.09.2026)" in joined)
    print("AKTUELL:", "✓ aktuell" in joined)
    print("GEFLASHT:", "vom 01.09.2026" in joined)
    shot("1_stand")
    click("Update…")
at(1500, setup)
at(5000, check)
def after():
    print("TOOL_OFFEN:", multi_win is not None and multi_win.winfo_exists())
    click("Nächster Schritt")
    shot("2_tool")
at(9000, after)
at(11000, lambda: shot("3_konfig"))
at(11500, done)
