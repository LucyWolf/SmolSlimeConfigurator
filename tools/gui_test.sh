#!/usr/bin/env bash
# Startet die App auf einem virtuellen Bildschirm (Xvfb) im Container und fuehrt
# ein Schritt-Skript aus. Laeuft komplett auf werkbank, nicht auf dem PC.
#   tools/gui_test.sh tools/tests/firmware_tool.py /pfad/zu/ausgabe
# Im Schritt-Skript stehen click(text, n), shot(name), scroll(anteil), done(),
# Zeiten mit at(ms, funktion). Screenshots landen als <name>.png im Ausgabeordner.
set -euo pipefail
cd "$(dirname "$0")/.."
STEPS=$1; OUT=$(realpath -m "$2"); mkdir -p "$OUT"
docker image inspect smolslime-test >/dev/null 2>&1 || docker build -q -t smolslime-test -f tools/test.Dockerfile tools
docker run --rm -v "$PWD":/src:ro -v "$OUT":/out -v "$(realpath "$STEPS")":/steps.py:ro smolslime-test bash -c '
  mkdir -p /w /tmp/cfg && cp /src/icon.png /w/ && cp -r /src/assets /w/
  { sed "/^app.mainloop()/d" /src/SmolSlimeConfiguratorV9.py; cat /src/tools/gui_helpers.py /steps.py; echo "app.mainloop()"; } > /w/run.py
  cd /w && XDG_CONFIG_HOME=/tmp/cfg timeout 120 xvfb-run -a -s "-screen 0 1400x1000x24" python run.py 2>&1 | grep -v Fontconfig || true
  chown -R '"$(id -u):$(id -g)"' /out'
ls "$OUT"
