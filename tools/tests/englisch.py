# Mit TEST_LANG=en: alle sichtbaren Texte einsammeln und deutsche melden (Hauptfenster, Einstellungen,
# Firmware-Tool Schritt 1+2, Geraeteverwaltung, Einstellungsfenster). Mit TEST_LANG=de: Sprachwahl steht auf Deutsch.
exec(open("/src/tools/tests/fake_devices.py").read())
import re as _re
GERMAN = _re.compile(r"[äöüÄÖÜß]|\b(und|oder|nicht|der|die|das|mit|wird|kein|keine|Gerät|Geräte|Datei|bitte|"
                     r"Einstellungen|verbunden|getrennt|Quelle|Schritt|Zurück|Übernehmen|Akku|fertig)\b")
found = set()
def collect(where):
    for w in _windows():
        for c in _walk(w):
            try:
                if not c.winfo_ismapped():
                    continue
                t = c.cget("text") if hasattr(c, "cget") else ""
            except Exception:
                continue
            if isinstance(t, str) and GERMAN.search(t):
                found.add((where, t.replace("\n", " ")[:110]))
    for w in _windows():
        for c in _walk(w):
            if isinstance(c, ctk.CTkOptionMenu) and c.winfo_ismapped() and GERMAN.search(c.get() or ""):
                found.add((where, "Menü: " + c.get()))

def setup():
    print("LANG:", LANG, "| Sprachmenü:", lang_menu.get())
    for info in (FAKE_DONGLE, FAKE_TRACKER):
        connect_device(get_or_add_device(info), ask=False)
    set_dongle(next(d for d in devices if d.is_receiver))
at(1500, setup)
at(2500, lambda: collect("Hauptfenster"))
at(3000, lambda: (tab_view.set(TAB_SETTINGS), on_tab_change()))
at(3500, lambda: (collect("Einstellungen-Tab"), shot("1_settings"),
                  print("Terminal sichtbar im Settings-Tab:", console_row.winfo_ismapped())))
at(4000, lambda: (tab_view.set("Tracker"), on_tab_change()))
at(4500, lambda: (print("Terminal wieder da:", console_row.winfo_ismapped()), open_multiflash_window()))
at(11000, lambda: (collect("Firmware-Tool 1"), shot("2_tool")))
at(11500, lambda: click(T("Nächster Schritt", "Next step")))
at(13000, lambda: (collect("Firmware-Tool 2"), shot("3_konfig")))
at(13500, lambda: (multi_win.destroy(), open_device_manager()))
at(15000, lambda: (collect("Geräteverwaltung"), shot("4_geraete")))
at(15500, lambda: click(T("Einstellungen", "Settings")))
at(20000, lambda: (collect("Tracker-Einstellungen"), shot("5_tracker_einst")))
def report():
    for where, t in sorted(found):
        print("DEUTSCH:", where, "|", t)
    print("Anzahl:", len(found))
    done()
at(20500, report)
