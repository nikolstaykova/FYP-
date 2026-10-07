# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 117 manuals succeeded, 0 failed · wall time 824 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 99.521 | 59.4 | 261.7 | 11644 |
| Input tokens | 48620 | 26101 | 122119 | 5688559 |
| Output tokens | 8508 | 6512 | 17522 | 995476 |
| Cost (USD) | 0.186 | 0.1375 | 0.4035 | 21.81 |

Estimated cost for 100 manuals at this rate: **$18.64**.

### Accuracy

**48 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 26 / 48 (54%) |
| Mean net precision | 0.702 |
| Mean net recall | 0.675 |
| Parts list correct (V1) | 30 / 48 |

**69 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 0.985.

**First-time part creation:** 2 drafted types could be checked against verified cards: polarity right 1/2, symmetry right 1/2, port count right 0/2.

### Check and repair loop

Build → check → repair → final check. **39/117** manuals had check failures after the first build; **2** of those were fully fixed by the repair. Issues in total: 246 → 251.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 117 | 40.062 | 0.099 | 0.004 |
| parts | 117 | 54.068 | 0.073 | 0.0 |
| repair1 | 12 | 34.417 | 0.096 | 0.005 |
| repair2 | 9 | 24.178 | 0.068 | 0.004 |

**Accuracy before → after repair** (48 tutorials with an answer key that were repaired): all nets correct 26 → 26; mean net recall 0.675 → 0.675.

### Spec rules and structure

- Manuals with **no rule problems**: 81/117 (69%).
- Problems by rule: V4 ×201, V3 ×59, V2 ×7 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 5/117; overrides used in 5.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 25 | 0 | 0 |
| 50 | 0 | 0 |
| 75 | 1 | 15 |
| 117 | 2 | 40 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| adxl3xx | 35.8 | 0.1076 | 9 | 36 | 0 | 0 | nets 3/5  |
| analog-in-out-serial | 40.1 | 0.1114 | 11 | 35 | 0 | 0 | nets 5/5 ✅ |
| analog-input | 48.6 | 0.1148 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| analog-write-mega | 54.2 | 0.1349 | 51 | 196 | 0 | 13 | nets 25/25 ✅ |
| analog-read-serial | 24.2 | 0.0644 | 7 | 19 | 0 | 0 | nets 3/3 ✅ |
| arduino-isp | 49.9 | 0.1374 | 21 | 69 | 0 | 0 | nets 0/15  |
| arduino-to-breadboard | 77.4 | 0.1669 | 19 | 120 | 0 | 0 | nets 1/7  |
| arrays | 66.5 | 0.1592 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| blink | 26.4 | 0.0665 | 7 | 17 | 0 | 0 | nets 3/3 ✅ |
| button | 42.2 | 0.0613 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| blink-without-delay | 21.2 | 0.0694 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| button-mouse-control | 64.9 | 0.1474 | 25 | 109 | 0 | 0 | nets 7/7 ✅ |
| calibration | 47.2 | 0.1151 | 13 | 44 | 0 | 0 | nets 2/7  |
| debounce | 39.5 | 0.0928 | 9 | 32 | 0 | 0 | nets 2/5  |
| digital-read-serial | 39.0 | 0.1074 | 10 | 33 | 0 | 0 | nets 3/3 ✅ |
| dimmer | 25.7 | 0.0914 | 7 | 17 | 0 | 0 | nets 3/3 ✅ |
| fade | 24.7 | 0.071 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| fading | 22.1 | 0.0761 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| graph | 28.1 | 0.0758 | 7 | 19 | 0 | 0 | nets 3/3 ✅ |
| for-loop | 51.8 | 0.1138 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| if-statement | 31.4 | 0.0782 | 7 | 19 | 0 | 0 | nets 2/5  |
| joystick-mouse-control | 44.9 | 0.1135 | 13 | 47 | 0 | 0 | nets 2/8  |
| input-pullup-serial | 29.1 | 0.0785 | 5 | 16 | 0 | 0 | nets 1/4  |
| keyboard-logout | 27.6 | 0.0854 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| keyboard-mouse-control | 79.6 | 0.1749 | 24 | 108 | 0 | 0 | nets 7/7 ✅ |
| keyboard-message | 35.6 | 0.0913 | 9 | 29 | 0 | 0 | nets 3/3 ✅ |
| keyboard-reprogram | 26.2 | 0.0795 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| led-bar-graph | 87.5 | 0.1762 | 28 | 142 | 0 | 0 | nets 2/23  |
| knock | 24.3 | 0.075 | 7 | 17 | 0 | 0 | nets 1/4  |
| memsic2125 | 37.0 | 0.1056 | 10 | 37 | 0 | 0 | nets 4/4 ✅ |
| midi | 38.2 | 0.0929 | 8 | 26 | 0 | 0 | nets 3/4  |
| physical-pixel | 24.9 | 0.0935 | 7 | 17 | 0 | 0 | nets 3/3 ✅ |
| ping | 56.7 | 0.1474 | 6 | 18 | 0 | 0 | nets 0/3  |
| pitch-follower | 70.8 | 0.1169 | 10 | 32 | 0 | 0 | nets 2/4  |
| read-analog-voltage | 28.7 | 0.0839 | 7 | 19 | 0 | 0 | nets 3/3 ✅ |
| read-ascii-string | 34.7 | 0.1233 | 10 | 36 | 0 | 0 | nets 7/7 ✅ |
| row-column-scanning | 83.0 | 0.1937 | 37 | 124 | 0 | 0 | nets 19/28  |
| serial-call-response | 75.5 | 0.2018 | 17 | 64 | 0 | 0 | nets 2/5  |
| serial-call-response-ascii | 68.8 | 0.1481 | 17 | 64 | 0 | 0 | nets 1/5  |
| smoothing | 28.7 | 0.0749 | 7 | 19 | 0 | 0 | nets 3/3 ✅ |
| state-change-detection | 50.2 | 0.118 | 9 | 32 | 0 | 0 | nets 2/5  |
| switch-case-sensor | 34.2 | 0.0889 | 9 | 28 | 0 | 0 | nets 3/3 ✅ |
| switch-case-serial | 54.0 | 0.1314 | 24 | 85 | 0 | 0 | nets 11/11 ✅ |
| tone-keyboard | 59.4 | 0.1453 | 18 | 64 | 0 | 0 | nets 0/6  |
| tone-melody | 20.8 | 0.0805 | 5 | 12 | 0 | 0 | nets 0/2  |
| tone-multiple | 41.8 | 0.1046 | 12 | 40 | 0 | 0 | nets 0/4  |
| virtual-color-mixer | 49.6 | 0.1375 | 15 | 52 | 0 | 0 | nets 1/5  |
| while-loop | 69.8 | 0.1545 | 18 | 68 | 0 | 0 | nets 5/8  |
| docs-nano-33-ble-i2c | 66.4 | 0.1611 | 12 | 40 | 0 | 0 | listed parts 1.0 |
| docs-nano-33-ble-sense-i2c | 68.5 | 0.1524 | 14 | 36 | 0 | 1 | listed parts 1.0 |
| docs-nano-33-iot-i2c | 55.6 | 0.1602 | 15 | 38 | 0 | 0 | listed parts 1.0 |
| docs-nano-every-i2c | 141.2 | 0.258 | 11 | 144 | 0 | 0 | listed parts 1.0 |
| docs-nano-matter-03-matter-fan | 204.1 | 0.3735 | 10 | 28 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-04-matter-relay-lightbulb | 443.2 | 0.5733 | 11 | 85 | 3 | 14 | listed parts None |
| docs-nano-matter-05-matter-rgb-light | 313.5 | 0.3581 | 9 | 26 | 0 | 3 | listed parts 1.0 |
| docs-nano-matter-06-matter-temp-sensor | 348.1 | 0.3059 | 15 | 62 | 1 | 5 | listed parts 1.0 |
| docs-nano-rp2040-connect-rp2040-ble-device-to-device | 55.3 | 0.1426 | 7 | 20 | 0 | 1 | listed parts 1.0 |
| docs-uno-r4-minima-dac | 77.8 | 0.1375 | 11 | 38 | 0 | 0 | listed parts 1.0 |
| docs-uno-r4-wifi-dac | 68.1 | 0.1351 | 11 | 38 | 0 | 0 | listed parts 1.0 |
| docs-uno-rev3-matlab-pwm-blink | 33.5 | 0.1157 | 12 | 35 | 0 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-hosting-a-webserver | 78.8 | 0.2065 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-web-server-ap-mode | 90.0 | 0.1284 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-uno-barometric-pressure-web-server | 261.7 | 0.4035 | 12 | 31 | 0 | 10 | listed parts 1.0 |
| docs-yun-rev2-shell-commands | 97.7 | 0.1702 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-uno-msr3-controlling-dc-motor | 167.0 | 0.1785 | 6 | 70 | 0 | 3 | listed parts 1.0 |
| docs-yun-rev2-temperature-web-panel | 158.6 | 0.3195 | 7 | 19 | 2 | 0 | listed parts 1.0 |
| docs-zero-simple-audio-frequency-meter | 369.2 | 0.4354 | 23 | 94 | 2 | 0 | listed parts 1.0 |
| docs-due-due-motor-shield-dc | 226.6 | 0.3303 | 5 | 32 | 1 | 0 | listed parts 1.0 |
| docs-due-simple-waveform-generator | 199.1 | 0.4581 | 18 | 74 | 0 | 2 | listed parts 1.0 |
| docs-mkr-analog-to-midi | 266.5 | 0.4467 | 23 | 91 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-hosting-a-webserver | 67.9 | 0.1705 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-web-server-ap-mode | 28.5 | 0.1159 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-arduino-mkr-gsm-1400-and-dtmf | 344.5 | 0.4196 | 16 | 44 | 2 | 6 | listed parts 1.0 |
| docs-mkr-vidor-hosting-a-webserver | 55.1 | 0.1473 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-lora-button-press-649 | 190.8 | 0.3063 | 15 | 32 | 1 | 0 | listed parts 1.0 |
| docs-mkr-lora-button-press-995 | 207.9 | 0.2035 | 15 | 32 | 0 | 2 | listed parts 1.0 |
| docs-mkr-enabling-ble | 116.4 | 0.1881 | 7 | 17 | 0 | 0 | listed parts 1.0 |
| docs-mkr-hosting-a-webserver | 29.2 | 0.1325 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-powering-with-batteries | 67.3 | 0.2111 | 7 | 18 | 0 | 2 | listed parts 1.0 |
| docs-mkr-web-server-ap-mode | 27.8 | 0.1058 | 7 | 17 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-zero-garden-automation | 379.9 | 0.5886 | 14 | 70 | 1 | 14 | listed parts 1.0 |
| docs-mkr-mkr-zero-weather-data-logger | 176.9 | 0.1246 | 11 | 33 | 0 | 0 | listed parts 0.667 (missing sensor) |
| docs-mkr-mkr-relay-shield-basic | 229.7 | 0.5482 | 14 | 98 | 0 | 29 | listed parts 1.0 |
| docs-mkr-smart-garden-project | 325.4 | 0.4746 | 10 | 28 | 4 | 0 | listed parts 1.0 |
| docs-opta-10-opta-modbus-tcp-plc-ide | 174.4 | 0.2296 | 8 | 10 | 2 | 0 | listed parts 1.0 |
| docs-mkr-mkr-motor-carrier-battery | 174.6 | 0.3427 | 5 | 22 | 1 | 0 | listed parts 1.0 |
| docs-communication-barometricpressuresensor | 38.3 | 0.0981 | 9 | 28 | 1 | 0 | listed parts 1.0 |
| docs-communication-digitalpotcontrol | 164.5 | 0.2947 | 37 | 184 | 1 | 0 | listed parts 1.0 |
| docs-generic-basic-servo-control | 22.0 | 0.0774 | 5 | 12 | 0 | 0 | listed parts 1.0 |
| docs-generic-digital-input-pullup | 23.0 | 0.0514 | 5 | 16 | 0 | 0 | listed parts 1.0 |
| docs-generic-midi-device | 89.0 | 0.2418 | 31 | 137 | 0 | 0 | listed parts 1.0 |
| docs-projects-arduino-iot-cloud-amazon-alexa-integration | 88.4 | 0.2115 | 16 | 64 | 1 | 4 | listed parts 1.0 |
| docs-projects-full-control-of-your-tv-using-alexa-and-arduino-iot-cloud | 252.5 | 0.5311 | 12 | 102 | 0 | 0 | listed parts 1.0 |
| docs-projects-gnome-forecaster | 103.5 | 0.2966 | 17 | 46 | 0 | 6 | listed parts 0.5 (missing sensor) |
| pi-python-quick-reaction-game | 91.4 | 0.1746 | 12 | 48 | 0 | 0 | listed parts None |
| pi-push-button-stop-motion | 67.6 | 0.1959 | 7 | 20 | 1 | 5 | listed parts 1.0 |
| pi-gpio-music-box | 90.8 | 0.2293 | 16 | 70 | 0 | 11 | listed parts 1.0 |
| pi-laser-tripwire | 238.4 | 0.3053 | 12 | 33 | 2 | 11 | listed parts 1.0 |
| docs-projects-make-it-rain-clap-machine | 372.9 | 0.5001 | 31 | 119 | 5 | 5 | listed parts 1.0 |
| pi-balloon-pi-tay-popper | 314.6 | 0.3593 | 25 | 94 | 3 | 8 | listed parts 1.0 |
| pi-pir-motion-sensors | 21.3 | 0.0525 | 5 | 12 | 0 | 6 | listed parts None |
| pi-camjam-kit-1 | 84.7 | 0.1797 | 17 | 64 | 0 | 12 | listed parts 1.0 |
| pi-rpi-gpio-wiring-a-button | 27.9 | 0.0604 | 5 | 16 | 0 | 4 | listed parts None |
| pi-rpi-gpio-connect-pir | 46.3 | 0.0484 | 5 | 12 | 0 | 6 | listed parts None |
| pi-rpi-python-piezoelectric-buzzer | 21.2 | 0.0627 | 5 | 12 | 0 | 6 | listed parts None |
| pi-ultrasonic-theremin | 141.1 | 0.3445 | 15 | 52 | 0 | 12 | listed parts 1.0 |
| pi-physical-computing | 135.1 | 0.4013 | 7 | 20 | 0 | 7 | listed parts None |
| pi-rpi-physical-connect-led | 26.5 | 0.0865 | 6 | 16 | 0 | 4 | listed parts None |
| pi-generic-electronics-connect-ultrasonic-distance-sensor | 47.7 | 0.1011 | 12 | 44 | 0 | 8 | listed parts None |
| pi-build-a-robot | 11.2 | 0.0393 | 0 | 0 | 0 | 0 | listed parts None |
| pi-rpi-physical-connect-motor-controller | 99.6 | 0.1607 | 5 | 14 | 0 | 10 | listed parts None |
| pi-traffic-lights-python | 47.8 | 0.1018 | 12 | 40 | 0 | 8 | listed parts 1.0 |
| pi-rpi-connect-led | 22.3 | 0.0505 | 6 | 16 | 0 | 4 | listed parts None |
| pi-interactive-traffic-lights-python | 62.1 | 0.1457 | 17 | 64 | 0 | 12 | listed parts 1.0 |
| pi-rpi-connect-buzzer | 35.2 | 0.0701 | 5 | 12 | 1 | 0 | listed parts None |
| pi-reaction | 31.8 | 0.0838 | 1 | 0 | 0 | 1 | listed parts None |
| pi-build-a-buggy | 295.9 | 0.6169 | 20 | 40 | 2 | 12 | listed parts 1.0 |
