# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 117 manuals succeeded, 0 failed · wall time 741 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 67.491 | 53.1 | 141.1 | 7896 |
| Input tokens | 89096 | 61261 | 173624 | 10424222 |
| Output tokens | 9894 | 7116 | 20381 | 1157631 |
| Cost (USD) | 0.182 | 0.15 | 0.3322 | 21.26 |

Estimated cost for 100 manuals at this rate: **$18.17**.

### Accuracy

**48 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 28 / 48 (58%) |
| Mean net precision | 0.733 |
| Mean net recall | 0.711 |
| Parts list correct (V1) | 29 / 48 |

**69 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 0.968.

**First-time part creation:** 2 drafted types could be checked against verified cards: polarity right 1/2, symmetry right 1/2, port count right 1/2.

### Check and repair loop

Build → check → repair → final check. **33/117** manuals had check failures after the first build; **20** of those were fully fixed by the repair. Issues in total: 152 → 19.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 117 | 36.98 | 0.073 | 0.007 |
| parts | 117 | 17.725 | 0.071 | 0.0 |
| repair1 | 33 | 29.642 | 0.091 | 0.007 |
| repair2 | 17 | 30.459 | 0.084 | 0.005 |

**Accuracy before → after repair** (48 tutorials with an answer key that were repaired): all nets correct 27 → 28; mean net recall 0.704 → 0.711.

### Spec rules and structure

- Manuals with **no rule problems**: 114/117 (97%).
- Problems by rule: V4 ×4, V2 ×2 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/117; overrides used in 0.

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
| 117 | 0 | 34 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| analog-input | 39.3 | 0.1811 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| analog-in-out-serial | 44.4 | 0.1872 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| adxl3xx | 32.0 | 0.1743 | 9 | 36 | 0 | 0 | nets 3/5  |
| analog-read-serial | 20.3 | 0.0547 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| analog-write-mega | 102.0 | 0.2571 | 51 | 196 | 0 | 0 | nets 25/25 ✅ |
| arduino-isp | 76.9 | 0.1862 | 22 | 73 | 0 | 0 | nets 1/15  |
| arduino-to-breadboard | 109.7 | 0.2156 | 23 | 136 | 0 | 0 | nets 3/7  |
| arrays | 61.1 | 0.1602 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| blink | 21.3 | 0.0743 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| blink-without-delay | 25.5 | 0.0737 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| button-mouse-control | 85.3 | 0.1939 | 24 | 108 | 0 | 0 | nets 7/7 ✅ |
| button | 44.9 | 0.1072 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| calibration | 49.3 | 0.1173 | 13 | 44 | 0 | 0 | nets 2/7  |
| digital-read-serial | 53.7 | 0.1205 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| debounce | 45.1 | 0.1071 | 9 | 32 | 0 | 0 | nets 2/5  |
| dimmer | 22.0 | 0.0801 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| fade | 22.9 | 0.0733 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| fading | 25.6 | 0.0732 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| for-loop | 64.1 | 0.1669 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| graph | 31.9 | 0.0837 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| if-statement | 24.3 | 0.0726 | 6 | 18 | 0 | 0 | nets 2/5  |
| input-pullup-serial | 29.4 | 0.0824 | 6 | 17 | 0 | 0 | nets 1/4  |
| joystick-mouse-control | 42.3 | 0.1157 | 12 | 46 | 0 | 0 | nets 2/8  |
| keyboard-logout | 23.9 | 0.0748 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| keyboard-message | 48.0 | 0.1096 | 8 | 28 | 0 | 0 | nets 3/3 ✅ |
| keyboard-mouse-control | 85.5 | 0.1914 | 24 | 108 | 0 | 0 | nets 7/7 ✅ |
| keyboard-reprogram | 25.6 | 0.0799 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| knock | 28.2 | 0.0848 | 6 | 16 | 0 | 0 | nets 1/4  |
| led-bar-graph | 89.5 | 0.2002 | 37 | 142 | 0 | 0 | nets 2/23  |
| memsic2125 | 53.1 | 0.1161 | 9 | 36 | 0 | 0 | nets 4/4 ✅ |
| midi | 33.9 | 0.0902 | 8 | 30 | 0 | 0 | nets 3/4  |
| ping | 26.6 | 0.0837 | 6 | 18 | 0 | 0 | nets 0/3  |
| physical-pixel | 24.4 | 0.0877 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| pitch-follower | 35.8 | 0.0994 | 10 | 32 | 0 | 0 | nets 2/4  |
| read-ascii-string | 34.8 | 0.1088 | 10 | 36 | 0 | 0 | nets 7/7 ✅ |
| read-analog-voltage | 34.2 | 0.0837 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| row-column-scanning | 151.1 | 0.412 | 37 | 124 | 0 | 0 | nets 28/28 ✅ |
| serial-call-response | 74.5 | 0.1857 | 17 | 64 | 0 | 0 | nets 1/5  |
| serial-call-response-ascii | 97.4 | 0.2634 | 17 | 64 | 0 | 0 | nets 1/5  |
| smoothing | 24.4 | 0.0731 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| switch-case-sensor | 34.7 | 0.095 | 9 | 28 | 0 | 0 | nets 3/3 ✅ |
| state-change-detection | 48.2 | 0.1116 | 9 | 32 | 0 | 0 | nets 2/5  |
| switch-case-serial | 65.1 | 0.1517 | 23 | 84 | 0 | 0 | nets 11/11 ✅ |
| tone-melody | 20.1 | 0.0727 | 5 | 12 | 0 | 0 | nets 2/2 ✅ |
| tone-keyboard | 69.0 | 0.1638 | 24 | 76 | 0 | 0 | nets 4/6  |
| tone-multiple | 40.1 | 0.1052 | 12 | 40 | 0 | 0 | nets 0/4  |
| virtual-color-mixer | 54.1 | 0.1368 | 15 | 52 | 0 | 0 | nets 0/5  |
| while-loop | 76.0 | 0.1705 | 18 | 68 | 0 | 0 | nets 3/8  |
| docs-nano-33-ble-sense-i2c | 51.3 | 0.132 | 13 | 34 | 0 | 0 | listed parts 1.0 |
| docs-nano-33-ble-i2c | 52.2 | 0.1448 | 18 | 50 | 0 | 0 | listed parts 1.0 |
| docs-nano-33-iot-i2c | 106.8 | 0.3245 | 18 | 52 | 0 | 0 | listed parts 1.0 |
| docs-nano-every-i2c | 52.9 | 0.1462 | 18 | 50 | 0 | 0 | listed parts 1.0 |
| docs-nano-matter-03-matter-fan | 145.4 | 0.289 | 8 | 24 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-04-matter-relay-lightbulb | 184.3 | 0.3661 | 11 | 30 | 5 | 1 | listed parts None |
| docs-nano-matter-05-matter-rgb-light | 75.3 | 0.129 | 8 | 26 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-06-matter-temp-sensor | 68.0 | 0.1951 | 12 | 45 | 0 | 0 | listed parts 1.0 |
| docs-nano-rp2040-connect-rp2040-ble-device-to-device | 34.5 | 0.1694 | 9 | 22 | 0 | 0 | listed parts 1.0 |
| docs-uno-r4-minima-dac | 99.3 | 0.331 | 11 | 38 | 0 | 0 | listed parts 1.0 |
| docs-uno-r4-wifi-dac | 96.8 | 0.322 | 11 | 38 | 0 | 0 | listed parts 1.0 |
| docs-uno-rev3-matlab-pwm-blink | 38.5 | 0.1744 | 12 | 35 | 0 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-hosting-a-webserver | 51.4 | 0.1127 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-web-server-ap-mode | 58.2 | 0.1221 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-uno-barometric-pressure-web-server | 167.5 | 0.3554 | 11 | 43 | 2 | 0 | listed parts 1.0 |
| docs-uno-msr3-controlling-dc-motor | 80.8 | 0.2358 | 7 | 28 | 0 | 0 | listed parts 1.0 |
| docs-yun-rev2-shell-commands | 27.8 | 0.1318 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-yun-rev2-temperature-web-panel | 28.7 | 0.0766 | 7 | 19 | 0 | 0 | listed parts 1.0 |
| docs-zero-simple-audio-frequency-meter | 175.2 | 0.2939 | 23 | 94 | 2 | 0 | listed parts 1.0 |
| docs-due-due-motor-shield-dc | 65.3 | 0.165 | 5 | 15 | 0 | 0 | listed parts 1.0 |
| docs-due-simple-waveform-generator | 140.5 | 0.3915 | 18 | 74 | 0 | 0 | listed parts 1.0 |
| docs-mkr-analog-to-midi | 240.6 | 0.5903 | 23 | 94 | 2 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-web-server-ap-mode | 44.5 | 0.1476 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-hosting-a-webserver | 37.9 | 0.1744 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-arduino-mkr-gsm-1400-and-dtmf | 95.3 | 0.2011 | 14 | 41 | 0 | 0 | listed parts 1.0 |
| docs-mkr-vidor-hosting-a-webserver | 32.6 | 0.0883 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-lora-button-press-649 | 99.0 | 0.2543 | 15 | 36 | 1 | 0 | listed parts 1.0 |
| docs-mkr-lora-button-press-995 | 91.8 | 0.2539 | 15 | 38 | 1 | 0 | listed parts 1.0 |
| docs-mkr-enabling-ble | 32.5 | 0.1698 | 7 | 17 | 0 | 0 | listed parts 1.0 |
| docs-mkr-hosting-a-webserver | 26.3 | 0.0995 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-powering-with-batteries | 56.8 | 0.2564 | 6 | 18 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-zero-garden-automation | 213.5 | 0.5062 | 23 | 76 | 1 | 0 | listed parts 1.0 |
| docs-mkr-web-server-ap-mode | 29.5 | 0.1718 | 7 | 17 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-zero-weather-data-logger | 54.8 | 0.1083 | 10 | 31 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-relay-shield-basic | 66.8 | 0.1909 | 10 | 29 | 0 | 0 | listed parts 1.0 |
| docs-mkr-smart-garden-project | 137.9 | 0.3322 | 8 | 24 | 3 | 0 | listed parts 1.0 |
| docs-mkr-mkr-motor-carrier-battery | 54.3 | 0.1512 | 5 | 12 | 1 | 0 | listed parts 1.0 |
| docs-opta-10-opta-modbus-tcp-plc-ide | 79.5 | 0.2974 | 8 | 16 | 2 | 0 | listed parts 1.0 |
| docs-communication-barometricpressuresensor | 27.2 | 0.0757 | 9 | 28 | 0 | 0 | listed parts 1.0 |
| docs-communication-digitalpotcontrol | 141.1 | 0.3308 | 36 | 180 | 1 | 0 | listed parts 1.0 |
| docs-generic-basic-servo-control | 23.5 | 0.1463 | 5 | 12 | 0 | 0 | listed parts 1.0 |
| docs-generic-digital-input-pullup | 23.1 | 0.0565 | 5 | 16 | 0 | 0 | listed parts 1.0 |
| docs-generic-midi-device | 91.3 | 0.2361 | 30 | 136 | 0 | 0 | listed parts 1.0 |
| docs-projects-arduino-iot-cloud-amazon-alexa-integration | 112.7 | 0.2633 | 13 | 45 | 1 | 0 | listed parts 1.0 |
| docs-projects-gnome-forecaster | 166.8 | 0.4534 | 15 | 44 | 2 | 0 | listed parts 1.0 |
| docs-projects-make-it-rain-clap-machine | 215.0 | 0.6271 | 24 | 102 | 1 | 0 | listed parts 1.0 |
| docs-projects-full-control-of-your-tv-using-alexa-and-arduino-iot-cloud | 247.4 | 0.6543 | 12 | 50 | 0 | 0 | listed parts 1.0 |
| pi-push-button-stop-motion | 58.8 | 0.2214 | 7 | 20 | 0 | 0 | listed parts 1.0 |
| pi-gpio-music-box | 56.5 | 0.1312 | 15 | 68 | 0 | 0 | listed parts 0.5 (missing buzzer) |
| pi-python-quick-reaction-game | 118.0 | 0.4033 | 12 | 48 | 0 | 0 | listed parts None |
| pi-laser-tripwire | 53.5 | 0.125 | 10 | 32 | 0 | 0 | listed parts 1.0 |
| pi-pir-motion-sensors | 19.9 | 0.0451 | 5 | 12 | 0 | 0 | listed parts None |
| pi-camjam-kit-1 | 70.0 | 0.15 | 17 | 64 | 0 | 0 | listed parts 1.0 |
| pi-physical-computing | 41.3 | 0.1574 | 7 | 20 | 0 | 0 | listed parts None |
| pi-ultrasonic-theremin | 77.3 | 0.1616 | 15 | 52 | 0 | 0 | listed parts 1.0 |
| pi-rpi-gpio-connect-pir | 19.0 | 0.0481 | 5 | 12 | 0 | 0 | listed parts None |
| pi-balloon-pi-tay-popper | 165.1 | 0.3893 | 14 | 51 | 1 | 0 | listed parts 0.75 (missing buzzer) |
| pi-rpi-gpio-wiring-a-button | 45.0 | 0.0934 | 9 | 36 | 0 | 0 | listed parts None |
| pi-rpi-python-piezoelectric-buzzer | 25.5 | 0.059 | 5 | 12 | 0 | 0 | listed parts None |
| pi-rpi-physical-connect-led | 76.6 | 0.2002 | 6 | 16 | 1 | 0 | listed parts None |
| pi-rpi-physical-connect-motor-controller | 78.0 | 0.1486 | 5 | 14 | 1 | 0 | listed parts None |
| pi-build-a-robot | 9.9 | 0.1065 | 0 | 0 | 0 | 0 | listed parts None |
| pi-generic-electronics-connect-ultrasonic-distance-sensor | 55.9 | 0.188 | 12 | 44 | 0 | 0 | listed parts None |
| pi-build-a-buggy | 127.6 | 0.211 | 15 | 35 | 2 | 0 | listed parts 1.0 |
| pi-rpi-connect-led | 22.9 | 0.1321 | 6 | 16 | 0 | 4 | listed parts None |
| pi-traffic-lights-python | 44.4 | 0.0987 | 2 | 8 | 1 | 0 | listed parts 0.0 (missing led, resistor) |
| pi-rpi-connect-buzzer | 23.2 | 0.0579 | 5 | 12 | 0 | 0 | listed parts None |
| pi-reaction | 18.8 | 0.1397 | 1 | 0 | 0 | 1 | listed parts None |
| pi-interactive-traffic-lights-python | 75.4 | 0.2327 | 17 | 64 | 0 | 0 | listed parts 1.0 |
