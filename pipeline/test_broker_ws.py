"""Local MQTT-over-WebSocket test broker for ThermoHuddle (amqtt).

Simulates the Pi pipeline: publishes a telemetry payload every 2 s on
thermohuddle/telemetry. Run alongside the HTTP server, then click
"⚡ Connect MQTT" in the app.

Usage:  python test_broker_ws.py [ws_port]  (default 9001)
"""
import asyncio
import json
import math
import random
import sys
import time

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_1

WS_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9001

broker = None


async def main():
    global broker
    broker = Broker(
        {
            "listeners": {
                # amqtt requires a 'default' TCP listener to exist
                "default": {"type": "tcp", "bind": "0.0.0.0:1883", "max_connections": 10},
                "ws": {"type": "ws", "bind": f"0.0.0.0:{WS_PORT}", "max_connections": 10},
            },
            "auth": {"allow-anonymous": True},
        }
    )
    # Simulated flock: 45 chicks loosely roaming; periodic cold-huddle events
    chicks = [[random.uniform(10, 90), random.uniform(10, 90)] for _ in range(45)]
    client = MQTTClient(client_id="thermohuddle-pub")
    await broker.start()
    print(f"[broker] WS listening on :{WS_PORT}, publishing telemetry every 2 s", flush=True)
    await client.connect(f"ws://127.0.0.1:{WS_PORT}/")
    floor_t = 32.5
    i = 0
    while True:
        i += 1
        for c in chicks:
            c[0] = min(95, max(5, c[0] + random.uniform(-4, 4)))
            c[1] = min(95, max(5, c[1] + random.uniform(-4, 4)))
        # every 15 messages, inject a cold huddle event (floor temp drops)
        phase = (i // 15) % 3
        if phase == 1:
            floor_t = max(26.0, floor_t - 0.4)
            for c in chicks:
                c[0] += (50 - c[0]) * 0.25
                c[1] += (50 - c[1]) * 0.25
        else:
            floor_t = min(33.0, floor_t + 0.2)
        payload = {
            "ts": round(time.time(), 1),
            "chicks": [[round(x, 1), round(z, 1)] for x, z in chicks],
            "count": len(chicks),
            "floorT": round(floor_t, 1),
            "setpoint": 33.0,
            "pwm": 180,
            "nh3": 6 + 2 * math.sin(i / 20),
            "state": "COMFY",
        }
        msg = json.dumps(payload).encode()
        await client.publish("thermohuddle/telemetry", msg, qos=QOS_1)
        await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[broker] stopped")
