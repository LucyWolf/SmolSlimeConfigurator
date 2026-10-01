# Firmware-Tool ohne GitHub-API: latest laden, dann auf einen Tages-Build wechseln (laedt nach)
settings["fw_last"] = {"tracker": {"source": "main", "board": "ProMicro",
                                   "options": ["StackedSmol", "I2C", "SW0", "CLK"]}}

def pick_daily():
    menus = [c for win in _windows() for c in _walk(win) if isinstance(c, ctk.CTkOptionMenu) and c.winfo_ismapped()]
    ver = next(m for m in menus if "stabil" in m.get())
    daily = next(v for v in ver.cget("values") if v.startswith("daily"))
    ver.set(daily)
    ver._command(daily)

at(1500, open_multiflash_window)
at(9000, lambda: shot("1_latest"))
at(9500, pick_daily)
at(15000, lambda: shot("2_daily"))
at(15500, lambda: click("Nächster Schritt"))
at(17000, lambda: (scroll(0.2), shot("3_bauweise")))
at(17500, done)
