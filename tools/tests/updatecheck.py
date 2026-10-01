# Knopf "Nach Updates suchen" in der Kopfzeile: vorher, waehrend der Suche, Ergebnis
at(3000, lambda: shot("1_kopf"))
at(3500, lambda: click("Nach Updates suchen"))
at(3700, lambda: shot("2_suche"))
at(7000, lambda: shot("3_ergebnis"))
at(7500, done)
