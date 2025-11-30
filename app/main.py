"""
main.py

High-level loop for the "smart classroom" prototype.

- Reads brightness from the laptop camera
- Reads volume level from the laptop microphone
- Applies simple thresholds + smoothing
- Publishes UP/DOWN commands over MQTT for:
    - smartclassroom/light_cmd
    - smartclassroom/speaker_cmd

Run from project root as:
    python -m app.main
"""

import argparse
import logging
import time
from collections import deque
from typing import Deque, Optional

import paho.mqtt.client as mqtt

from .camera_processor import CameraProcessor
from .mic_processor import MicrophoneProcessor

# MQTT configuration
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_KEEPALIVE = 60

MQTT_TOPIC_LIGHT = "smartclassroom/light_cmd"
MQTT_TOPIC_SPEAKER = "smartclassroom/speaker_cmd"

# Sampling + decision parameters
LOOP_INTERVAL_SEC = 1.0  # main loop period

# Brightness thresholds (0–255, tune for your room)
BRIGHTNESS_LOW = 80.0    # below this, try to brighten
BRIGHTNESS_HIGH = 180.0  # above this, try to dim

# Volume thresholds (dB, negative values; closer to 0 = louder)
VOLUME_HIGH_DB = -20.0   # above this (less negative) = too loud
VOLUME_LOW_DB = -40.0    # below this (more negative) = too quiet

# Rate limiting so we don't spam commands
MIN_CMD_INTERVAL_SEC = 5.0

# Moving-average history length
HISTORY_LENGTH = 10


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client()
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_KEEPALIVE)
    client.loop_start()  # background network loop
    logging.info("Connected to MQTT broker at %s:%s", MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    return client


def moving_average(history: Deque[float]) -> Optional[float]:
    if not history:
        return None
    return sum(history) / len(history)


def maybe_publish(
    client: mqtt.Client,
    topic: str,
    payload: str,
    last_sent_time: dict,
) -> None:
    """
    Publish a command if enough time has passed since the last one on this topic.
    """
    now = time.time()
    last = last_sent_time.get(topic, 0.0)
    if now - last < MIN_CMD_INTERVAL_SEC:
        return

    result = client.publish(topic, payload=payload, qos=0, retain=False)
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        logging.info("MQTT publish: %s -> %s", topic, payload)
        last_sent_time[topic] = now
    else:
        logging.warning("Failed to publish MQTT message: rc=%s", result.rc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Classroom controller")
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam index")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    # Initialize components
    camera = CameraProcessor(camera_index=args.camera_index)
    mic = MicrophoneProcessor()
    client = create_mqtt_client()

    brightness_history: Deque[float] = deque(maxlen=HISTORY_LENGTH)
    volume_history: Deque[float] = deque(maxlen=HISTORY_LENGTH)

    last_cmd_time: dict = {}

    logging.info("Starting main loop. Press Ctrl+C to stop.")

    try:
        while True:
            loop_start = time.time()

            # 1) Measure brightness
            try:
                brightness = camera.read_brightness()
                brightness_history.append(brightness)
                avg_brightness = moving_average(brightness_history)
            except Exception as e:
                logging.error("Error reading camera brightness: %s", e)
                avg_brightness = None

            # 2) Measure volume
            try:
                volume_db = mic.measure_volume_db()
                volume_history.append(volume_db)
                avg_volume_db = moving_average(volume_history)
            except Exception as e:
                logging.error("Error measuring microphone volume: %s", e)
                avg_volume_db = None

            logging.info(
                "Brightness: current=%.1f avg=%s | Volume: current=%.1f dB avg=%s",
                brightness if avg_brightness is not None else float("nan"),
                f"{avg_brightness:.1f}" if avg_brightness is not None else "N/A",
                volume_db if avg_volume_db is not None else float("nan"),
                f"{avg_volume_db:.1f}" if avg_volume_db is not None else "N/A",
            )

            # 3) Decision logic → MQTT commands
            if avg_brightness is not None:
                if avg_brightness < BRIGHTNESS_LOW:
                    maybe_publish(client, MQTT_TOPIC_LIGHT, "UP", last_cmd_time)
                elif avg_brightness > BRIGHTNESS_HIGH:
                    maybe_publish(client, MQTT_TOPIC_LIGHT, "DOWN", last_cmd_time)

            if avg_volume_db is not None:
                if avg_volume_db > VOLUME_HIGH_DB:  # too loud (less negative)
                    maybe_publish(client, MQTT_TOPIC_SPEAKER, "DOWN", last_cmd_time)
                elif avg_volume_db < VOLUME_LOW_DB:  # too quiet
                    maybe_publish(client, MQTT_TOPIC_SPEAKER, "UP", last_cmd_time)

            # 4) Sleep to keep a roughly fixed loop interval
            elapsed = time.time() - loop_start
            to_sleep = max(0.0, LOOP_INTERVAL_SEC - elapsed)
            time.sleep(to_sleep)

    except KeyboardInterrupt:
        logging.info("Stopping...")

    finally:
        camera.release()
        client.loop_stop()
        client.disconnect()
        logging.info("Shutdown complete.")


if __name__ == "__main__":
    main()
