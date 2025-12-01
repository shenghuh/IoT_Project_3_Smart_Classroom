"""
rssi_subscriber.py

Reusable MQTT RSSI subscriber for the smart classroom project.

Usage from main.py:
    from .rssi_subscriber import RssiSubscriber

    rssi_sub = RssiSubscriber(
        broker_host=MQTT_BROKER_HOST,
        broker_port=MQTT_BROKER_PORT,
        topic="smartclassroom/rssi",
    )
    rssi_sub.start()
    ...
    rssi_sub.stop()
"""
import json
import logging
from typing import Optional

import paho.mqtt.client as mqtt

# 跟 Node-RED mqtt out 的 Topic 一樣
MQTT_TOPIC_RSSI = "RSSI"


class RssiSubscriber:
    """
    簡單的 MQTT Subscriber：訂閱 RSSI topic，並記住「最近一次」的 RSSI。
    預期 Node-RED payload 範例：
        { "rssi": -70, "timestamp": "2025-12-01T10:04:45.372Z" }
    """

    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        topic: str = MQTT_TOPIC_RSSI,
        keepalive: int = 60,
    ) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.keepalive = keepalive

        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        # 給 main.py 讀的「最新 RSSI 資訊」
        self.latest_rssi: Optional[float] = None
        self.latest_timestamp: Optional[str] = None
        self.last_raw_payload: Optional[str] = None

        self._started = False

    # ───── MQTT callbacks ─────

    def _on_connect(self, client: mqtt.Client, userdata, flags, rc):
        if rc == 0:
            logging.info(
                "RSSI subscriber connected to %s:%s, subscribing to %s",
                self.broker_host,
                self.broker_port,
                self.topic,
            )
            client.subscribe(self.topic, qos=0)
        else:
            logging.error("RSSI subscriber connect failed, rc=%s", rc)

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
        payload_str = msg.payload.decode("utf-8", errors="ignore")
        self.last_raw_payload = payload_str
        logging.debug("Raw RSSI message on %s: %s", msg.topic, payload_str)

        rssi: Optional[float] = None
        timestamp: Optional[str] = None

        try:
            data = json.loads(payload_str)
            rssi = float(data.get("rssi"))
            timestamp = str(data.get("timestamp"))
        except Exception as e:
            logging.warning("Failed to parse RSSI payload: %s", e)

        # 記住最近一次資料，給 main loop 用
        if rssi is not None:
            self.latest_rssi = rssi
            self.latest_timestamp = timestamp
            if timestamp:
                logging.info("RSSI = %6.1f dBm at %s", rssi, timestamp)
            else:
                logging.info("RSSI = %6.1f dBm", rssi)
        else:
            logging.info("Received RSSI message (unparsed): %s", payload_str)

    # ───── lifecycle control ─────

    def start(self) -> None:
        if self._started:
            return
        self.client.connect(self.broker_host, self.broker_port, self.keepalive)
        self.client.loop_start()
        self._started = True
        logging.info("RSSI subscriber started.")

    def stop(self) -> None:
        if not self._started:
            return
        self.client.loop_stop()
        self.client.disconnect()
        self._started = False
        logging.info("RSSI subscriber stopped.")
