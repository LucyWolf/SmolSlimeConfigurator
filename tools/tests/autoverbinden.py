# Automatisch erkennen: nachgebaute Geraete "stecken" (erscheinen in comports), ohne Klick.
# Dann Tracker entfernen (bleibt weg, solange er steckt), abstecken und wieder anstecken.
exec(open("/src/tools/tests/fake_devices.py").read())
plugged = [FAKE_DONGLE, FAKE_TRACKER]
serial.tools.list_ports.comports = lambda: list(plugged)

def names():
    return [f"{device_name(d)}:{'an' if d.connected else 'aus'}" for d in devices]

at(4000, lambda: (print("nach Einstecken:", names(), flush=True), shot("1_automatisch")))
at(4500, lambda: remove_device(next(d for d in devices if not d.is_receiver)))
at(9000, lambda: print("entfernt, steckt noch:", names(), flush=True))
at(9500, lambda: plugged.remove(FAKE_TRACKER))
at(12500, lambda: plugged.append(FAKE_TRACKER))
at(16000, lambda: (print("wieder eingesteckt:", names(), flush=True), shot("2_wieder")))
at(16500, done)
