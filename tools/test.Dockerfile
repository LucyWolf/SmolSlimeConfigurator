# Test- und Bauumgebung fuer werkbank: Python 3.10 wie im Original, dazu ein
# virtueller Bildschirm (Xvfb), damit die Oberflaeche ohne echten PC laeuft.
FROM python:3.10-bookworm
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends xvfb xauth imagemagick fonts-dejavu fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*
RUN pip install -q --no-cache-dir pyinstaller customtkinter pyserial requests pyflakes
