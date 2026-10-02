# Hauptfenster: Startansicht, Reiter Receiver und Settings, dazu das Firmware-Tool
at(4000, lambda: shot("1_haupt"))
at(4500, lambda: tab_view.set(TAB_SETTINGS))
at(5500, lambda: shot("2_settings"))
at(6000, open_multiflash_window)
at(14000, lambda: shot("3_firmware_tool"))
at(14500, done)
