**Language / Sprache:** [🇬🇧 English](#smolslime-configurator) | [🇩🇪 Deutsch](#smolslime-configurator-1)

---

<img src="icon.png" width="48" height="48" alt="Icon">

# SmolSlime Configurator

Unofficial desktop app to connect, configure and flash **SlimeVR Smol Slime (SlimeNRF)** trackers and dongles.

This is a fork of the [SmolSlime Configurator by ICantMakeThings](https://github.com/ICantMakeThings/SmolSlimeConfigurator). It keeps the original buttons and terminal and adds a firmware wizard, a device manager, multi-device support and installers for Linux and Windows.

The interface is in **English** by default and can be switched to **German** under *Settings → Language*.

![DIY Firmware Tool](docs/firmware-tool.png)

## Installation

All files are on the [Releases](https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest) page.

### Windows

Download [`SmolSlimeConfigurator-setup.exe`](https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest/download/SmolSlimeConfigurator-setup.exe) and double-click it.

- Installs for your user only, no admin rights needed
- Adds a Start menu entry (desktop shortcut optional)
- Can be uninstalled under *Settings → Apps*
- No drivers needed on Windows 10/11

If you don't want to install anything, you can run `SmolSlimeConfigurator-Windows.exe` directly.

### Linux

Download the installer for your distribution and double-click it. The first time, your file manager asks whether it may run the file.

| Distribution | Installer |
|---|---|
| Arch / CachyOS / Manjaro | [`SmolSlimeConfigurator-arch-installer.desktop`](https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest/download/SmolSlimeConfigurator-arch-installer.desktop) |
| Debian / Ubuntu | [`SmolSlimeConfigurator-deb-installer.desktop`](https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest/download/SmolSlimeConfigurator-deb-installer.desktop) |
| Everything else (Fedora, openSUSE, …) | [`SmolSlimeConfigurator-installer.desktop`](https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest/download/SmolSlimeConfigurator-installer.desktop) |

The installer:

- downloads the latest version
- installs missing packages (udisks2, XWayland)
- sets up USB access for the trackers (asks for your password once)
- adds a menu entry

Running it again offers **Update** or **Uninstall**. On Wayland the app runs through XWayland.

<details>
<summary>Prefer the terminal?</summary>

```bash
curl -fsSL -o SmolSlimeConfigurator-installieren.sh https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest/download/SmolSlimeConfigurator-installieren.sh
bash SmolSlimeConfigurator-installieren.sh
```
</details>

### Updates

The app checks for a new version on start. If there is one, click **⬆ Update** in the top bar.

## Features

### DIY Firmware Tool
A step-by-step wizard modeled on the SlimeVR Server: source → board → version → build → devices → flash method → flash.

- Firmware sources: **Shine-Bright-Meow** (official), **kounocom**, **jitingcn**, or your own `.uf2` file
- Pick the build options (form factor, sensor bus, magnetometer, sensor clock, sleep mode, button, …); every option has a **?** with an explanation
- If a combination doesn't exist, the tool suggests the closest ones or searches all sources
- Flashes **several trackers at once** (one after another on Windows)
- **UF2 bootloader** for trackers and ProMicro dongles, **Nordic serial bootloader** for `.hex` dongles (Holyiot, eByte, Nordic), without nRF Connect
- Can reflash a ProMicro from tracker to dongle and back
- Warns before flashing if the firmware doesn't match the connected device
- Optional: write firmware settings into the trackers right after flashing

### Device Manager
![Device Manager](docs/device-manager.png)

- All dongles and trackers at a glance, with port and serial number
- Firmware, board, sensor and battery via **Get info + battery**
- List of trackers paired to the dongle
- **Settings** stored directly in a tracker (sleep, sensor, button, radio, …) without reflashing
- Remembers which firmware the app flashed onto each device and shows whether an **update** is available

### Main window
- Several devices connected at the same time, each with its own terminal; switch on the left
- SlimeNRF devices connect automatically; set one as **dongle** and it reconnects by itself
- **🔗 Pair** puts the dongle and all connected trackers into pairing mode at once
- The original buttons: Info, Reboot, Scan, Calibrate, Calibrate 6 Sides, Mag Clear, Battery, Pairing Mode, Clear Con. Data, DFU, Uptime, Debug
- On Linux, a missing USB permission ("Permission denied") can be fixed with one password prompt

## Usage

### Flashing
1. Plug in the trackers (or the dongle) via USB.
2. Open **DIY Firmware Tool**, choose source, *Tracker* or *Dongle*, board and version.
3. Pick the build options, select the devices and start flashing.

The app sends the devices into the bootloader by itself. For firmware without the `dfu` command, it asks you to press reset four times quickly. Holyiot dongles enter the bootloader by holding the included magnet to the LED; the app tells you when.

A brand-new ProMicro without SlimeNRF firmware has to be put into the bootloader by hand once: bridge **RST** and **GND** twice quickly.

**Trackers and dongle need the same firmware version**, otherwise they won't pair.

### Pairing
Connect the dongle and the trackers, then press **🔗 Pair** (main window) or **🔗 Pair all** (Device Manager). When all trackers show up, end pairing mode on the *Receiver* tab.

If a tracker has old pairing data, it won't connect: plug it in and press **Clear Con. Data**.

### Calibration
Press **Calibrate 6 Sides** and follow the terminal. Then press **Calibrate** and leave the tracker still on a desk for about 5 seconds. Double-tapping the tracker's button works instead of **Calibrate**.

More in the official [SmolSlime docs](https://docs.slimevr.dev/smol-slimes/).

## Building from source

Python **3.10**:

```bash
pip install pyinstaller customtkinter pyserial requests
pyinstaller --onefile --windowed --add-data "icon.png:." --add-data "assets:assets" SmolSlimeConfiguratorV9.py
```

On Windows use `;` instead of `:` in `--add-data` and add `--icon=icon.ico`.

**Releases (maintainers):** raise `APP_VERSION` in `SmolSlimeConfiguratorV9.py` (the last digit counts up to 99), push, run `tools/release.sh`. GitHub Actions builds and tests Linux and Windows (including the setup) and then publishes.

## Credits

- Original app: [ICantMakeThings/SmolSlimeConfigurator](https://github.com/ICantMakeThings/SmolSlimeConfigurator) (MIT). macOS and Android builds are available there.
- Schematic images: [SlimeVR docs](https://github.com/SlimeVR/SlimeVR-Docs-Site) (MIT), see `assets/bauform/QUELLEN.md`.
- Nordic serial DFU rebuilt in Python after Nordic's [pc-nrfutil](https://github.com/NordicSemiconductor/pc-nrfutil) (BSD).
- Web version of the original: [SmolSlimeWebConfigurator](https://github.com/jitingcn/SmolSlimeWebConfigurator) by jitingcn.

License: MIT, see [LICENSE](LICENSE).

## A note on this project

This code was created with Claude AI – and I know many people turn up their noses at those words. Still, this project stands for a simple idea: to be there for everyone, without exception. An AI is not a miracle cure that solves every problem by itself – it is a tool that only unfolds its power through the hands that guide it. All files are open, freely accessible and free to use.

I want to be honest here: this is AI-generated, and I do not claim to have written it myself. That honor isn't mine. The 3D printer once gave rise to hobby engineers who solved everyday problems they previously lacked the knowledge or means for. That is exactly what AI can – and should – be: not a miracle cure, but a tool that makes our lives easier. A tool that lets people without a computer science background tackle the small, annoying problems we all run into. Not out of a claim to genius, but out of the simple wish to make something better.

---

# SmolSlime Configurator

Inoffizielle Desktop-App zum Verbinden, Einstellen und Flashen von **SlimeVR Smol Slime (SlimeNRF)**-Trackern und -Dongles.

Dies ist ein Fork des [SmolSlime Configurators von ICantMakeThings](https://github.com/ICantMakeThings/SmolSlimeConfigurator). Die ursprünglichen Knöpfe und das Terminal bleiben, dazu kommen ein Firmware-Assistent, eine Geräteverwaltung, mehrere Geräte gleichzeitig und Installer für Linux und Windows.

Die Oberfläche ist standardmäßig **Englisch** und lässt sich unter *Settings → Language* auf **Deutsch** umstellen.

![DIY Firmware-Tool](docs/firmware-tool.png)

## Installation

Alle Dateien liegen auf der [Releases](https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest)-Seite.

### Windows

[`SmolSlimeConfigurator-setup.exe`](https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest/download/SmolSlimeConfigurator-setup.exe) herunterladen und doppelklicken.

- Installiert nur für deinen Benutzer, ohne Admin-Rechte
- Legt einen Startmenü-Eintrag an (Desktop-Verknüpfung auf Wunsch)
- Deinstallierbar unter *Einstellungen → Apps*
- Unter Windows 10/11 sind keine Treiber nötig

Ohne Installation lässt sich `SmolSlimeConfigurator-Windows.exe` direkt starten.

### Linux

Den Installer für deine Distribution herunterladen und doppelklicken. Beim ersten Mal fragt der Dateimanager, ob er die Datei ausführen darf.

| Distribution | Installer |
|---|---|
| Arch / CachyOS / Manjaro | [`SmolSlimeConfigurator-arch-installer.desktop`](https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest/download/SmolSlimeConfigurator-arch-installer.desktop) |
| Debian / Ubuntu | [`SmolSlimeConfigurator-deb-installer.desktop`](https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest/download/SmolSlimeConfigurator-deb-installer.desktop) |
| Alle anderen (Fedora, openSUSE, …) | [`SmolSlimeConfigurator-installer.desktop`](https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest/download/SmolSlimeConfigurator-installer.desktop) |

Der Installer:

- lädt die neueste Version herunter
- installiert fehlende Pakete (udisks2, XWayland)
- richtet den USB-Zugriff auf die Tracker ein (fragt einmal nach deinem Passwort)
- legt einen Menüeintrag an

Erneut gestartet bietet er **Aktualisieren** oder **Deinstallieren** an. Unter Wayland läuft die App über XWayland.

<details>
<summary>Lieber per Terminal?</summary>

```bash
curl -fsSL -o SmolSlimeConfigurator-installieren.sh https://github.com/LucyWolf/SmolSlimeConfigurator/releases/latest/download/SmolSlimeConfigurator-installieren.sh
bash SmolSlimeConfigurator-installieren.sh
```
</details>

### Updates

Die App sucht beim Start nach einer neuen Version. Gibt es eine, oben auf **⬆ Update** klicken.

## Funktionen

### DIY Firmware-Tool
Ein Assistent Schritt für Schritt wie im SlimeVR-Server: Quelle → Board → Version → Bauweise → Geräte → Flash-Methode → Flashen.

- Firmware-Quellen: **Shine-Bright-Meow** (offiziell), **kounocom**, **jitingcn** oder eine eigene `.uf2`-Datei
- Bauweise wählen (Bauform, Sensor-Anschluss, Magnetometer, Sensor-Takt, Schlafmodus, Taster, …); hinter jeder Option steht ein **?** mit Erklärung
- Gibt es eine Kombination nicht, schlägt das Tool die nächstliegenden vor oder sucht in allen Quellen
- Flasht **mehrere Tracker auf einmal** (unter Windows nacheinander)
- **UF2-Bootloader** für Tracker und ProMicro-Dongles, **Nordic-Seriell-Bootloader** für `.hex`-Dongles (Holyiot, eByte, Nordic), ohne nRF Connect
- Kann einen ProMicro vom Tracker zum Dongle umflashen und zurück
- Warnt vor dem Flashen, wenn die Firmware nicht zum angesteckten Gerät passt
- Auf Wunsch: Firmware-Einstellungen direkt nach dem Flashen in die Tracker schreiben

### Geräteverwaltung
![Geräteverwaltung](docs/device-manager.png)

- Alle Dongles und Tracker auf einen Blick, mit Port und Seriennummer
- Firmware, Board, Sensor und Akku über **Info + Akku abrufen**
- Liste der Tracker, die mit dem Dongle gekoppelt sind
- **Einstellungen** direkt im Tracker speichern (Schlaf, Sensor, Taster, Funk, …), ohne neu zu flashen
- Merkt sich, welche Firmware die App auf jedes Gerät geflasht hat, und zeigt, ob es ein **Update** gibt

### Hauptfenster
- Mehrere Geräte gleichzeitig verbunden, jedes mit eigenem Terminal; links umschalten
- SlimeNRF-Geräte verbinden sich von selbst; ein als **Dongle** festgelegtes Gerät verbindet sich immer wieder
- **🔗 Koppeln** schickt Dongle und alle verbundenen Tracker gleichzeitig in den Kopplungsmodus
- Die ursprünglichen Knöpfe: Info, Neustart, Scan, Kalibrieren, 6 Seiten kalibrieren, Mag löschen, Akku, Kopplungsmodus, Kopplung löschen, DFU, Laufzeit, Debug
- Unter Linux lässt sich fehlender USB-Zugriff („Permission denied“) mit einer Passwortabfrage beheben

## Bedienung

### Flashen
1. Tracker (oder Dongle) per USB anstecken.
2. **DIY Firmware-Tool** öffnen, Quelle, *Tracker* oder *Dongle*, Board und Version wählen.
3. Bauweise wählen, Geräte auswählen und Flashen starten.

Die App schickt die Geräte selbst in den Bootloader. Bei Firmware ohne den Befehl `dfu` bittet sie dich, viermal schnell Reset zu drücken. Holyiot-Dongles kommen in den Bootloader, wenn man den mitgelieferten Magneten an die LED hält; die App sagt Bescheid, wann.

Ein neuer ProMicro ohne SlimeNRF-Firmware muss einmal von Hand in den Bootloader: **RST** und **GND** zweimal schnell verbinden.

**Tracker und Dongle brauchen dieselbe Firmware-Version**, sonst koppeln sie nicht.

### Koppeln
Dongle und Tracker verbinden, dann **🔗 Koppeln** (Hauptfenster) oder **🔗 Alle koppeln** (Geräteverwaltung) drücken. Sobald alle Tracker auftauchen, den Kopplungsmodus im Reiter *Empfänger* beenden.

Hat ein Tracker alte Kopplungsdaten, verbindet er sich nicht: anstecken und **Kopplung löschen** drücken.

### Kalibrieren
**6 Seiten kalibrieren** drücken und den Anweisungen im Terminal folgen. Danach **Kalibrieren** drücken und den Tracker etwa 5 Sekunden ruhig auf den Tisch legen. Statt **Kalibrieren** geht auch doppeltes Tippen auf den Knopf des Trackers.

Mehr in der offiziellen [SmolSlime-Doku](https://docs.slimevr.dev/smol-slimes/).

## Aus dem Quellcode bauen

Python **3.10**:

```bash
pip install pyinstaller customtkinter pyserial requests
pyinstaller --onefile --windowed --add-data "icon.png:." --add-data "assets:assets" SmolSlimeConfiguratorV9.py
```

Unter Windows in `--add-data` `;` statt `:` verwenden und `--icon=icon.ico` ergänzen.

**Releases (für Betreuer):** `APP_VERSION` in `SmolSlimeConfiguratorV9.py` erhöhen (die letzte Stelle zählt bis 99), pushen, `tools/release.sh` ausführen. GitHub Actions baut und testet Linux und Windows (samt Setup) und veröffentlicht dann.

## Danksagung

- Ursprüngliche App: [ICantMakeThings/SmolSlimeConfigurator](https://github.com/ICantMakeThings/SmolSlimeConfigurator) (MIT). Dort gibt es auch Fassungen für macOS und Android.
- Schaltplan-Bilder: [SlimeVR-Doku](https://github.com/SlimeVR/SlimeVR-Docs-Site) (MIT), siehe `assets/bauform/QUELLEN.md`.
- Nordic-Seriell-DFU in Python nachgebaut nach Nordics [pc-nrfutil](https://github.com/NordicSemiconductor/pc-nrfutil) (BSD).
- Web-Fassung des Originals: [SmolSlimeWebConfigurator](https://github.com/jitingcn/SmolSlimeWebConfigurator) von jitingcn.

Lizenz: MIT, siehe [LICENSE](LICENSE).

## Eine Anmerkung zu diesem Projekt

Dieser Code wurde mit Claude AI erschaffen – und ich weiß, viele rümpfen bei diesen Worten die Nase. Trotzdem steht dieses Projekt für einen einfachen Gedanken: für alle da zu sein, ohne Ausnahme. Eine KI ist kein Wundermittel, das jedes Problem von selbst löst – sie ist ein Werkzeug, das seine Kraft erst durch die Hände entfaltet, die es führen. Alle Dateien liegen offen, für jeden frei zugänglich und frei verwendbar.

Ich will an dieser Stelle ehrlich sein: Das hier ist KI-generiert, und ich beanspruche nicht, es selbst geschrieben zu haben. Diese Ehre gebührt mir nicht. Der 3D-Drucker hat einst Hobby-Ingenieure entstehen lassen, die damit Probleme des Alltags lösten, für die ihnen früher Wissen oder Mittel fehlten. Genau das kann – und sollte – auch KI sein: kein Wundermittel, sondern ein Werkzeug, das unser Leben einfacher macht. Ein Werkzeug, mit dem auch Menschen ohne Informatik-Hintergrund die kleinen, nervigen Probleme angehen können, die uns allen begegnen. Nicht aus Anspruch auf Genialität, sondern aus dem einfachen Wunsch, etwas besser zu machen.
