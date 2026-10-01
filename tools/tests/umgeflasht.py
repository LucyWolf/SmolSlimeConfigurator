# Geraet kommt nach dem Umflashen mit gleicher Seriennummer als Dongle zurueck -> Name/Typ aktualisiert
exec(open("/src/tools/tests/fake_devices.py").read())
import types as _types
def check():
    dev = get_or_add_device(FAKE_TRACKER)
    before = (device_name(dev), dev.is_receiver)
    as_dongle = _types.SimpleNamespace(**dict(vars(FAKE_TRACKER), product="SlimeNRF Receiver ProMicro",
                                              description="SlimeNRF Receiver ProMicro", pid=0x7690))
    get_or_add_device(as_dongle)
    print("vorher:", before, "| nachher:", (device_name(dev), dev.is_receiver), "| Geraete:", len(devices), flush=True)
    done()
at(1500, check)
