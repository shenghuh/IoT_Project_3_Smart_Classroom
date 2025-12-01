# IoT Project 3: Smart Classroom

This project is a small IoT prototype for a **smart classroom**:

- The **laptop** reads:
  - Webcam frames -> estimates room brightness.
  - Microphone input -> estimates sound volume.
- The laptop applies simple thresholds and smoothing.
- When the room is too dark / bright or too quiet / loud, it sends
  **commands via MQTT** to a Particle Photon 2:
  - Topic `smartclassroom/light_cmd`: payload `UP` / `DOWN`
  - Topic `smartclassroom/speaker_cmd`: payload `UP` / `DOWN`
- The Photon 2 (not included in this repo) subscribes to those topics
  and adjusts LEDs / speakers accordingly.

The heavy processing stays on the laptop; the Photon only handles actuator
control.

---

## Project Structure

```text
PROJECT3/
  app/
    camera_processor.py   # webcam brightness reader
    mic_processor.py      # microphone volume reader
    main.py               # main control loop + MQTT publisher
  .gitignore
  README.md
  requirements.txt
