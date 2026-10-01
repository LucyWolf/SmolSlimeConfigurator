
# --- Hilfen fuer tools/gui_test.sh (werden nur im Test angehaengt) ---
def _walk(w):
    for c in w.winfo_children():
        yield c
        yield from _walk(c)

def _windows():
    return [app] + [w for w in _walk(app) if isinstance(w, ctk.CTkToplevel)]

def click(text, n=0):
    hits = [c for win in _windows() for c in _walk(win)
            if isinstance(c, ctk.CTkButton) and c.cget("text") == text and c.winfo_ismapped()]
    print(f"klick {text!r}: {'ok' if len(hits) > n else 'nicht gefunden'}", flush=True)
    if len(hits) > n:
        hits[n].invoke()

def scroll(fraction):
    for win in _windows():
        for c in _walk(win):
            if isinstance(c, ctk.CTkScrollableFrame) and c.winfo_ismapped():
                c._parent_canvas.yview_moveto(fraction)
                return

def shot(name):
    app.update()
    subprocess.run(["import", "-window", "root", f"/out/{name}.png"])
    print("bild", name, flush=True)

def at(ms, fn):
    app.after(ms, fn)

def done():
    app.destroy()
