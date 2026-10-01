# Geraeteverwaltung mit nachgebautem Dongle und Tracker: Uebersicht, Info + Akku, Einstellungen
exec(open("/src/tools/tests/fake_devices.py").read())

def setup():
    for info in (FAKE_DONGLE, FAKE_TRACKER):
        dev = get_or_add_device(info)
        connect_device(dev, ask=False)
    set_dongle(next(d for d in devices if d.is_receiver))
    open_device_manager()

at(1500, setup)
at(4000, lambda: shot("1_uebersicht"))
at(4500, lambda: click("Info + Akku abrufen"))
at(8000, lambda: shot("2_info"))
at(8500, lambda: click("Einstellungen"))
at(13000, lambda: shot("3_einstellungen"))

# Schreiben: "Schlafen fruehestens nach" von 5 auf 8 s, dann Uebernehmen
def change_value():
    entries = [c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkEntry) and c.winfo_ismapped()]
    e = next(x for x in entries if x.get() == "5")
    e.delete(0, "end")
    e.insert(0, "8")
    click("Übernehmen")
at(13600, change_value)
at(19000, lambda: shot("4_geschrieben"))
at(19500, done)
