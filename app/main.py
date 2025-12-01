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
from datetime import datetime
from threading import Thread
from typing import Deque, Optional

import paho.mqtt.client as mqtt

from .camera_processor import CameraProcessor
from .mic_processor import MicrophoneProcessor
from .rssi_subscriber import RssiSubscriber, MQTT_TOPIC_RSSI
from .web_server import app as web_app, set_log  # <-- 這裡同時拿到 Flask app 跟 set_log

# MQTT broker 設定
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_KEEPALIVE = 60

# 控制用 topic
MQTT_TOPIC_LIGHT = "smartclassroom/light_cmd"
MQTT_TOPIC_SPEAKER = "smartclassroom/speaker_cmd"

# 主迴圈週期（秒）：每 2 秒一筆 log
LOOP_INTERVAL_SEC = 2.0

# 亮度門檻 (0–255，依你環境可微調)
BRIGHTNESS_LOW = 80.0     # 太暗 → 亮一點
BRIGHTNESS_HIGH = 180.0   # 太亮 → 暗一點

# 音量門檻 (dB，越靠近 0 越大聲)
VOLUME_HIGH_DB = -20.0    # 太吵 → 降音量
VOLUME_LOW_DB = -40.0     # 太小聲 → 加音量

# MQTT 控制節流（同一 topic 至少隔這麼久才再發一筆）
MIN_CMD_INTERVAL_SEC = 5.0

# 移動平均窗口長度
HISTORY_LENGTH = 10


def iso_timestamp() -> str:
    """回傳類似 2025-12-01T10:47:06.241Z 的 UTC 字串"""
    return datetime.utcnow().isoformat(timespec="milliseconds") + "Z"


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
    client.loop_start()
    logging.info(
        "Connected to MQTT broker at %s:%s",
        MQTT_BROKER_HOST,
        MQTT_BROKER_PORT,
    )
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
    如果距離上一次在同一個 topic 發訊已經過了 MIN_CMD_INTERVAL_SEC，
    就 publish 一次，避免狂發消息。
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


def start_web_server() -> None:
    """在背景 thread 裡啟動 Flask Web Server."""
    def run():
        # 不要開 debug，避免多開一個 reloader process
        web_app.run(port=5000, debug=False, threaded=True)

    t = Thread(target=run, daemon=True)
    t.start()
    logging.info("Started web server thread on http://127.0.0.1:5000")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Classroom controller")
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam index")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--listen-rssi",
        action="store_true",
        help="Subscribe to RSSI MQTT topic",
    )
    parser.add_argument(
        "--rssi-topic",
        type=str,
        default=MQTT_TOPIC_RSSI,
        help=f"RSSI MQTT topic (default: {MQTT_TOPIC_RSSI})",
    )
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    # ⭐ 在這裡啟動 Web Server（背景 thread）
    start_web_server()

    # 初始化感測器與 MQTT
    camera = CameraProcessor(camera_index=args.camera_index)
    mic = MicrophoneProcessor()
    client = create_mqtt_client()

    # RSSI subscriber（可選）
    rssi_sub: Optional[RssiSubscriber] = None
    if args.listen_rssi:
        rssi_sub = RssiSubscriber(
            broker_host=MQTT_BROKER_HOST,
            broker_port=MQTT_BROKER_PORT,
            topic=args.rssi_topic,
        )
        rssi_sub.start()

    # 歷史資料用來算 moving average
    brightness_history: Deque[float] = deque(maxlen=HISTORY_LENGTH)
    volume_history: Deque[float] = deque(maxlen=HISTORY_LENGTH)

    last_cmd_time: dict = {}

    logging.info("Starting main loop. Press Ctrl+C to stop.")

    try:
        while True:
            loop_start = time.time()

            # 1) 讀亮度
            try:
                brightness = camera.read_brightness()
                brightness_history.append(brightness)
                avg_brightness = moving_average(brightness_history)
            except Exception as e:
                logging.error("Error reading camera brightness: %s", e)
                brightness = float("nan")
                avg_brightness = None

            # 2) 讀音量
            try:
                volume_db = mic.measure_volume_db()
                volume_history.append(volume_db)
                avg_volume_db = moving_average(volume_history)
            except Exception as e:
                logging.error("Error measuring microphone volume: %s", e)
                volume_db = float("nan")
                avg_volume_db = None

            # 3) 讀最近一次 RSSI
            current_rssi = None
            rssi_ts = None
            if rssi_sub is not None:
                current_rssi = rssi_sub.latest_rssi
                rssi_ts = rssi_sub.latest_timestamp

            # 組合 timestamped log message
            timestamp = iso_timestamp()
            brightness_avg_str = (
                f"{avg_brightness:.1f}" if avg_brightness is not None else "N/A"
            )
            volume_avg_str = (
                f"{avg_volume_db:.1f}" if avg_volume_db is not None else "N/A"
            )
            rssi_str = (
                f"{current_rssi:.1f} dBm" if current_rssi is not None else "N/A"
            )
            rssi_ts_str = rssi_ts if rssi_ts is not None else "N/A"

            msg = (
                f"{timestamp} | "
                f"Brightness: current={brightness:.1f} avg={brightness_avg_str} | "
                f"Volume: current={volume_db:.1f} dB avg={volume_avg_str} | "
                f"RSSI: {rssi_str} (ts={rssi_ts_str})"
            )

            # 4) 印到 console + 丟給 web server
            logging.info(msg)
            set_log(msg)

            # 5) 根據亮度 / 音量做簡單控制
            if avg_brightness is not None:
                if avg_brightness < BRIGHTNESS_LOW:
                    maybe_publish(client, MQTT_TOPIC_LIGHT, "UP", last_cmd_time)
                elif avg_brightness > BRIGHTNESS_HIGH:
                    maybe_publish(client, MQTT_TOPIC_LIGHT, "DOWN", last_cmd_time)

            if avg_volume_db is not None:
                if avg_volume_db > VOLUME_HIGH_DB:  # 太吵
                    maybe_publish(client, MQTT_TOPIC_SPEAKER, "DOWN", last_cmd_time)
                elif avg_volume_db < VOLUME_LOW_DB:  # 太小聲
                    maybe_publish(client, MQTT_TOPIC_SPEAKER, "UP", last_cmd_time)

            # 6) 保持固定週期
            elapsed = time.time() - loop_start
            to_sleep = max(0.0, LOOP_INTERVAL_SEC - elapsed)
            time.sleep(to_sleep)

    except KeyboardInterrupt:
        logging.info("Stopping...")

    finally:
        camera.release()
        client.loop_stop()
        client.disconnect()

        if rssi_sub is not None:
            rssi_sub.stop()

        logging.info("Shutdown complete.")


if __name__ == "__main__":
    main()
