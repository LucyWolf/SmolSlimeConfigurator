# Kopfzeile ohne alte Leiste, mit Geraeten und angebotenem Update
exec(open("/src/tools/tests/fake_devices.py").read())
serial.tools.list_ports.comports = lambda: [FAKE_DONGLE, FAKE_TRACKER]
at(3500, lambda: shot("ohne_update"))
at(4000, lambda: offer_update("v9.9.9", {"browser_download_url": ""}, ""))
at(4500, lambda: shot("kopfzeile"))
at(5000, lambda: (tab_view.set(TAB_SETTINGS), click("Nach Updates suchen")))
at(9000, lambda: shot("settings"))
at(9500, done)
