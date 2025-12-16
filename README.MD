# IoT Project 3: Smart Classroom

This project implements a small IoT-based **smart classroom** prototype.
The system monitors environmental conditions on a laptop and sends lightweight
control commands to an embedded device via MQTT.

The overall design follows a **split-responsibility architecture**:

- The **laptop** performs sensing, signal processing, and decision-making.
- The **microcontroller (Particle Photon 2)** only handles simple actuator control.

---

## System Overview

### Laptop-side Sensing and Processing

The laptop runs Python programs that continuously monitor the classroom environment.

**Brightness sensing**
- Webcam frames are captured using OpenCV.
- Frames are converted to grayscale.
- The mean pixel intensity (0–255) is used as an estimate of room brightness.

**Sound level sensing**
- Audio samples are recorded from the microphone.
- Root Mean Square (RMS) is computed for each audio window.
- RMS values are converted to decibels (dB) to estimate sound volume.

---

### Control Logic

A central control loop runs on the laptop:

- Brightness and volume are sampled at regular intervals (approximately once per second).
- A moving average window is applied to smooth noisy sensor readings.
- Smoothed values are compared against predefined thresholds.
- When thresholds are crossed, the system determines whether an
  **increase (UP)** or **decrease (DOWN)** action is required.

To avoid excessive network traffic and actuator oscillation:
- MQTT commands are **rate-limited**, ensuring a minimum time gap between
  consecutive messages on the same topic.

---

### MQTT Communication

The laptop publishes control commands via MQTT:

| Topic                         | Payload | Meaning |
|------------------------------|---------|--------|
| `smartclassroom/light_cmd`   | `UP`    | Increase light output (room too dark) |
| `smartclassroom/light_cmd`   | `DOWN`  | Decrease light output (room too bright) |
| `smartclassroom/speaker_cmd` | `UP`    | Increase speaker volume (room too quiet) |
| `smartclassroom/speaker_cmd` | `DOWN`  | Decrease speaker volume (room too loud) |

---

### Device-side Actuation (Photon 2)

The Particle Photon 2 (not included in this repository):

- Subscribes to the MQTT topics listed above.
- Adjusts LEDs and speakers based on received commands.
- Does not perform heavy computation or signal processing.

This keeps the embedded device simple and responsive, while leveraging the
laptop’s higher computational power.

---

## Project Structure

```text
PROJECT3/
  app/
    camera_processor.py   # Webcam brightness reader (grayscale mean)
    mic_processor.py      # Microphone volume reader (RMS -> dB)
    main.py               # Control loop, smoothing, and MQTT publishing
  .gitignore
  README.md
  requirements.txt
'''
---
## How to Run / Compile

This project runs entirely on the laptop using Python.
No compilation is required for the laptop-side code.

### Prerequisites

- Python 3.8 or later
- A webcam and a microphone
- An MQTT broker (local or remote)
- Required Python packages listed in `requirements.txt`

### Install Dependencies

From the project root directory, run:

```bash
pip install -r requirements.txt
