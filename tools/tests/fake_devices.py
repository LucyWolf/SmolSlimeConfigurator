# Nachgebaute SlimeNRF-Geraete an virtuellen seriellen Anschluessen (pty). Sie antworten
# im Format der offiziellen Firmware auf info, read_config all, write_config und list.
import pty
import types

def fake_device(product, serial_no, info_lines, cfg=None):
    master, slave = pty.openpty()
    cfg = dict(cfg or {})

    def loop():
        buf = b""
        while True:
            buf += os.read(master, 1024)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                cmd = line.decode(errors="ignore").strip()
                out = []
                if cmd == "info":
                    out = info_lines
                elif cmd == "read_config all":
                    out = [f"Read config: {k}={v}" for k, v in cfg.items()]
                elif cmd.startswith("write_config"):
                    _, k, v = cmd.split()
                    cfg[k] = int(v)
                    out = [f"Updated config: {k}={v}"]
                elif cmd == "list":
                    out = ["Stored devices: 2", "0: ED722F24DECA30F1", "1: FBB8E4EE16CFC112"]
                elif cmd:
                    out = [cmd, "Unknown command"]   # wie Firmware ohne UF2-Unterstuetzung bei "dfu"
                for o in out:
                    os.write(master, (o + "\r\n").encode())
    threading.Thread(target=loop, daemon=True).start()
    # Die App nimmt unter Linux nur Anschluesse namens ttyACM*; daher ein passender Verweis
    link = f"/tmp/ttyACM{len(glob.glob('/tmp/ttyACM*'))}"
    os.symlink(os.ttyname(slave), link)
    return types.SimpleNamespace(device=link, serial_number=serial_no, location="", product=product,
                                 description=product, vid=0x1209, pid=0x7692 if "Tracker" in product else 0x7690)

FAKE_DONGLE = fake_device("SlimeNRF Receiver Holyiot-21017", "C7F52BB73A4A4882",
                          ["Holyiot SlimeNRF Receiver Holyiot-21017", "SlimeVR-Tracker-nRF-Receiver 0.6.9+0 (Commit 97f8877)",
                           "Board: holyiot_21017"])
FAKE_TRACKER = fake_device("SlimeNRF Tracker ProMicro", "ED722F24DECA30F1",
                           ["SlimeVR SlimeNRF Tracker ProMicro", "SlimeVR-Tracker-nRF 0.7.2+3 (Commit abc1234)",
                            "Board: promicro_uf2", "Target: promicro_uf2/nrf52840/stackedspi", "IMU: ICM-45686", "Interface: SPI", "Tracker ID: 1",
                            "Battery: 87% (Read 0h 2min ago)"],
                           {"sensor_use_mag": 1, "use_sensor_clock": 1, "use_imu_timeout": 1, "imu_timeout_ramp_min": 5000,
                            "imu_timeout_ramp_max": 15000, "sensor_accel_odr": 100, "active_timeout_mode": 0,
                            "active_timeout_delay": 900000, "led_default_color_r": 4000, "led_default_color_g": 0,
                            "led_default_color_b": 10000, "radio_tx_power": 8})
