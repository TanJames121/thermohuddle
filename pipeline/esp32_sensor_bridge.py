#!/usr/bin/env python3
"""ESP32 USB-serial sensor bridge (DHT22 + MQ-137/ADS1115 + fan relay) for Raspberry Pi 5."""
import glob
import json
import logging
import math
import os
import threading
import time
from typing import Optional

VALID_STATUSES = ("ok", "degraded", "error")


def _finite_number(value, low: float, high: float) -> Optional[float]:
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    val = float(value)
    if not (low <= val <= high):
        return None
    return val


def parse_esp32_line(line: str, *, now: float) -> Optional[dict]:
    """Parse and validate one single-line JSON telemetry packet from ThermohaddleDht22Mq_nov13a.ino."""
    if not isinstance(line, str) or type(now) not in (int, float) or not math.isfinite(now) or now <= 0:
        return None
    raw_text = line.strip()
    if not raw_text.startswith("{") or not raw_text.endswith("}"):
        return None
    try:
        data = json.loads(raw_text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(data, dict):
        return None

    status = data.get("status")
    if status not in VALID_STATUSES:
        return None

    ambient_raw = data.get("ambient_temp_c")
    if ambient_raw is None:
        ambient_temp_c = None
    else:
        ambient_temp_c = _finite_number(ambient_raw, -40.0, 85.0)
        if ambient_temp_c is None:
            return None

    humidity_raw = data.get("humidity_pct")
    if humidity_raw is None:
        humidity_pct = None
    else:
        humidity_pct = _finite_number(humidity_raw, 0.0, 100.0)
        if humidity_pct is None:
            return None

    if status == "error":
        mq137_raw = data.get("mq137_raw", 0)
        mq137_volts = data.get("mq137_volts", 0.0)
        nh3_rel_ppm = data.get("nh3_rel_ppm", 0.0)
        mq137_do_alert = data.get("mq137_do_alert", False)
        fan_on = data.get("fan_on", False)
    else:
        mq137_raw = data.get("mq137_raw")
        mq137_volts = data.get("mq137_volts")
        nh3_rel_ppm = data.get("nh3_rel_ppm")
        mq137_do_alert = data.get("mq137_do_alert")
        fan_on = data.get("fan_on")

    if type(mq137_raw) is not int or not (-32768 <= mq137_raw <= 32767):
        return None
    mq_volts_f = _finite_number(mq137_volts, -6.2, 6.2)
    nh3_ppm_f = _finite_number(nh3_rel_ppm, 0.0, 10000.0)
    if mq_volts_f is None or nh3_ppm_f is None:
        return None
    if type(mq137_do_alert) is not bool or type(fan_on) is not bool:
        return None

    return {
        "available": status in ("ok", "degraded"),
        "status": status,
        "ts": round(float(now), 3),
        "ambient_temp_c": round(ambient_temp_c, 2) if ambient_temp_c is not None else None,
        "humidity_pct": round(humidity_pct, 2) if humidity_pct is not None else None,
        "mq137_raw": int(mq137_raw),
        "mq137_volts": round(mq_volts_f, 4),
        "nh3_rel_ppm": round(nh3_ppm_f, 2),
        "mq137_do_alert": mq137_do_alert,
        "fan_on": fan_on,
    }


def format_fan_command(turn_on: bool) -> bytes:
    """Format the serial fan command understood by ThermohaddleDht22Mq_nov13a.ino."""
    return b"FAN:1\n" if turn_on else b"FAN:0\n"


def discover_serial_ports() -> list[str]:
    """Return candidate USB-UART serial device paths for an attached ESP32."""
    env_port = os.environ.get("ESP32_SERIAL_PORT", "").strip()
    candidates = []
    if env_port:
        candidates.append(env_port)
    for pattern in ("/dev/serial/by-id/*", "/dev/ttyUSB*", "/dev/ttyACM*"):
        candidates.extend(sorted(glob.glob(pattern)))
    seen = set()
    unique = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


class ESP32SerialReader:
    """Background serial reader that continuously buffers the latest valid ESP32 sensor reading."""

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200,
                 reconnect_s: float = 2.0, max_age_s: float = 15.0, start: bool = True):
        self.port = port
        self.baudrate = baudrate
        self.reconnect_s = reconnect_s
        self.max_age_s = max_age_s
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._stop = threading.Event()
        self._latest: Optional[dict] = None
        self._ser = None
        self.active_port: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        if start:
            self._thread = threading.Thread(target=self._run, name="esp32-serial", daemon=True)
            self._thread.start()

    def _open_serial(self):
        import serial  # type: ignore

        ports = [self.port] if self.port else discover_serial_ports()
        for dev in ports:
            if not dev:
                continue
            try:
                ser = serial.Serial(dev, self.baudrate, timeout=1.0)
                self.active_port = dev
                logging.info("ESP32 serial connected on %s @ %d", dev, self.baudrate)
                return ser
            except Exception:
                continue
        return None

    def _close_serial(self):
        with self._write_lock:
            ser = self._ser
            self._ser = None
            self.active_port = None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    def _run(self):
        while not self._stop.is_set():
            if self._ser is None:
                ser = self._open_serial()
                if ser is None:
                    self._stop.wait(self.reconnect_s)
                    continue
                with self._write_lock:
                    self._ser = ser
            try:
                raw = self._ser.readline()
                if not raw:
                    continue
                text = raw.decode("utf-8", errors="ignore")
                parsed = parse_esp32_line(text, now=time.time())
                if parsed is not None:
                    with self._lock:
                        self._latest = parsed
            except Exception as exc:
                logging.warning("ESP32 serial read error (%s); reconnecting", exc)
                self._close_serial()
                self._stop.wait(self.reconnect_s)

    def latest(self, *, now: Optional[float] = None, max_age_s: Optional[float] = None) -> Optional[dict]:
        """Return the latest sensor packet if fresh within max_age_s, else None."""
        check_now = time.time() if now is None else float(now)
        limit = self.max_age_s if max_age_s is None else float(max_age_s)
        with self._lock:
            if self._latest is None:
                return None
            sample = dict(self._latest)
        age = check_now - sample["ts"]
        if 0.0 <= age <= limit:
            return sample
        return None

    def send_fan_command(self, turn_on: bool) -> bool:
        """Send FAN:1 or FAN:0 over USB serial to the ESP32."""
        payload = format_fan_command(turn_on)
        with self._write_lock:
            if self._ser is None:
                return False
            try:
                self._ser.write(payload)
                self._ser.flush()
                return True
            except Exception:
                return False

    def close(self):
        self._stop.set()
        self._close_serial()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)


def main() -> int:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=None, help="Explicit serial device (e.g. /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    reader = ESP32SerialReader(port=args.port, baudrate=args.baud)

    client = None
    try:
        import paho.mqtt.client as mqtt  # type: ignore

        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        except (AttributeError, TypeError):
            client = mqtt.Client()

        def on_message(_client, _userdata, msg):
            if msg.topic == "thermohuddle/cmd/fan":
                text = msg.payload.decode("utf-8", errors="ignore").strip()
                if text in ("1", "true", "FAN:1", '{"fan":true}'):
                    reader.send_fan_command(True)
                elif text in ("0", "false", "FAN:0", '{"fan":false}'):
                    reader.send_fan_command(False)

        client.on_message = on_message
        client.connect(args.mqtt_host, args.mqtt_port, 30)
        client.subscribe("thermohuddle/cmd/fan")
        client.loop_start()
    except Exception as exc:
        logging.warning("MQTT bridge unavailable (%s); logging ESP32 readings only", exc)
        client = None

    last_ts = 0.0
    try:
        while True:
            sample = reader.latest()
            if sample is not None and sample["ts"] > last_ts:
                last_ts = sample["ts"]
                logging.info("esp32=%s", json.dumps(sample))
                if client is not None:
                    client.publish("thermohuddle/telemetry/env", json.dumps(sample))
            time.sleep(max(0.2, args.interval))
    except KeyboardInterrupt:
        pass
    finally:
        reader.close()
        if client is not None:
            client.loop_stop()
            client.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
