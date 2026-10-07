# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 116 manuals succeeded, 1 failed · wall time 2315 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 40.758 | 34.9 | 79.3 | 4728 |
| Input tokens | 19742 | 18187 | 24119 | 2290086 |
| Output tokens | 5886 | 4989 | 11046 | 682770 |
| Cost (USD) | 0.104 | 0.1007 | 0.1596 | 12.12 |

Estimated cost for 100 manuals at this rate: **$10.45**.

### Accuracy

**47 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 23 / 47 (49%) |
| Mean net precision | 0.648 |
| Mean net recall | 0.62 |
| Parts list correct (V1) | 29 / 47 |

**69 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 0.967.

**First-time part creation:** 3 drafted types could be checked against verified cards: polarity right 3/3, symmetry right 3/3, port count right 0/3.

### Spec rules and structure

- Manuals with **no rule problems**: 86/116 (74%).
- Problems by rule: V4 ×178, V3 ×30, V2 ×2 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 3/116; overrides used in 3.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 25 | 0 | 0 |
| 50 | 1 | 3 |
| 75 | 1 | 44 |
| 116 | 0 | 82 |

### Failures

- `tone-keyboard`: RuntimeError: claude -p failed: API Error: Sonnet 5.5's safeguards flagged this message (https://www.anthropic.com/legal/aup). This sometimes happens with safe, normal conversations. Claude Code can't

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| adxl3xx | 31.0 | 0.0953 | 9 | 36 | 0 | 0 | nets 3/5  |
| analog-in-out-serial | 34.9 | 0.0534 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| analog-input | 35.1 | 0.054 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| analog-read-serial | 18.0 | 0.0412 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| arduino-isp | 46.2 | 0.1014 | 21 | 69 | 0 | 0 | nets 0/15  |
| analog-write-mega | 71.9 | 0.1444 | 51 | 196 | 0 | 26 | nets 25/25 ✅ |
| blink | 20.3 | 0.0522 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| arrays | 59.8 | 0.1356 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| arduino-to-breadboard | 76.3 | 0.1481 | 21 | 128 | 0 | 0 | nets 1/7  |
| blink-without-delay | 17.6 | 0.0562 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| button | 36.3 | 0.0817 | 9 | 32 | 0 | 0 | nets 1/3  |
| button-mouse-control | 55.1 | 0.1154 | 25 | 109 | 0 | 14 | nets 7/7 ✅ |
| digital-read-serial | 37.4 | 0.0879 | 10 | 33 | 0 | 0 | nets 1/3  |
| calibration | 39.8 | 0.094 | 13 | 44 | 0 | 0 | nets 2/7  |
| debounce | 40.4 | 0.0874 | 9 | 32 | 0 | 0 | nets 2/5  |
| dimmer | 17.5 | 0.0614 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| fade | 19.1 | 0.0581 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| fading | 20.5 | 0.0549 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| graph | 23.5 | 0.0627 | 6 | 18 | 0 | 1 | nets 3/3 ✅ |
| if-statement | 27.0 | 0.0658 | 6 | 18 | 0 | 0 | nets 2/5  |
| for-loop | 57.7 | 0.1331 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| input-pullup-serial | 14.3 | 0.0516 | 5 | 16 | 0 | 0 | nets 0/4  |
| keyboard-logout | 18.5 | 0.0596 | 5 | 16 | 0 | 4 | nets 2/2 ✅ |
| joystick-mouse-control | 38.1 | 0.0919 | 12 | 46 | 0 | 14 | nets 2/8  |
| keyboard-reprogram | 15.6 | 0.0557 | 5 | 16 | 0 | 4 | nets 2/2 ✅ |
| keyboard-message | 44.4 | 0.0877 | 8 | 28 | 0 | 6 | nets 1/3  |
| keyboard-mouse-control | 77.4 | 0.1546 | 24 | 98 | 0 | 14 | nets 7/7 ✅ |
| knock | 21.5 | 0.059 | 6 | 16 | 0 | 0 | nets 1/4  |
| memsic2125 | 39.3 | 0.0914 | 9 | 36 | 0 | 0 | nets 4/4 ✅ |
| led-bar-graph | 64.0 | 0.1163 | 37 | 142 | 0 | 0 | nets 2/23  |
| physical-pixel | 15.3 | 0.0641 | 7 | 17 | 0 | 0 | nets 3/3 ✅ |
| ping | 20.7 | 0.058 | 6 | 18 | 0 | 0 | nets 0/3  |
| midi | 31.9 | 0.0784 | 10 | 29 | 0 | 0 | nets 3/4  |
| read-analog-voltage | 25.5 | 0.0666 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| read-ascii-string | 27.8 | 0.086 | 10 | 36 | 0 | 0 | nets 7/7 ✅ |
| pitch-follower | 33.4 | 0.0803 | 10 | 32 | 0 | 0 | nets 2/4  |
| serial-call-response-ascii | 99.3 | 0.1378 | 17 | 64 | 0 | 0 | nets 0/5  |
| row-column-scanning | 103.4 | 0.1682 | 37 | 124 | 0 | 0 | nets 19/28  |
| serial-call-response | 105.0 | 0.1712 | 17 | 64 | 0 | 0 | nets 0/5  |
| smoothing | 19.4 | 0.0566 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| switch-case-sensor | 31.6 | 0.0739 | 9 | 28 | 0 | 0 | nets 3/3 ✅ |
| state-change-detection | 45.2 | 0.0952 | 9 | 32 | 0 | 0 | nets 2/5  |
| tone-melody | 14.6 | 0.052 | 5 | 12 | 0 | 0 | nets 0/2  |
| switch-case-serial | 113.9 | 0.1553 | 23 | 84 | 0 | 0 | nets 11/11 ✅ |
| tone-multiple | 34.6 | 0.0854 | 12 | 40 | 1 | 0 | nets 0/4  |
| virtual-color-mixer | 42.5 | 0.1092 | 15 | 52 | 0 | 0 | nets 0/5  |
| while-loop | 70.2 | 0.14 | 18 | 68 | 0 | 0 | nets 3/8  |
| docs-nano-33-ble-i2c | 29.6 | 0.1064 | 13 | 34 | 1 | 0 | listed parts 1.0 |
| docs-nano-33-ble-sense-i2c | 29.9 | 0.0993 | 10 | 24 | 0 | 0 | listed parts 1.0 |
| docs-nano-33-iot-i2c | 35.0 | 0.1116 | 13 | 34 | 1 | 0 | listed parts 1.0 |
| docs-nano-every-i2c | 30.9 | 0.1076 | 14 | 38 | 0 | 0 | listed parts 1.0 |
| docs-nano-matter-03-matter-fan | 49.4 | 0.1254 | 10 | 45 | 5 | 0 | listed parts 1.0 |
| docs-nano-matter-04-matter-relay-lightbulb | 49.9 | 0.1232 | 12 | 33 | 6 | 2 | listed parts None |
| docs-nano-rp2040-connect-rp2040-ble-device-to-device | 30.9 | 0.1045 | 9 | 22 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-06-matter-temp-sensor | 37.7 | 0.1146 | 12 | 43 | 1 | 12 | listed parts 1.0 |
| docs-nano-matter-05-matter-rgb-light | 37.5 | 0.0998 | 10 | 41 | 1 | 4 | listed parts 1.0 |
| docs-uno-rev3-matlab-pwm-blink | 29.9 | 0.1062 | 13 | 38 | 1 | 0 | listed parts 1.0 |
| docs-uno-r4-minima-dac | 40.1 | 0.1038 | 11 | 38 | 1 | 0 | listed parts 1.0 |
| docs-uno-r4-wifi-dac | 46.3 | 0.1132 | 11 | 38 | 1 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-hosting-a-webserver | 25.2 | 0.0761 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-web-server-ap-mode | 25.2 | 0.1014 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-uno-barometric-pressure-web-server | 33.9 | 0.0827 | 10 | 42 | 2 | 0 | listed parts 1.0 |
| docs-yun-rev2-temperature-web-panel | 26.3 | 0.084 | 6 | 18 | 2 | 0 | listed parts 1.0 |
| docs-yun-rev2-shell-commands | 28.3 | 0.0772 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-uno-msr3-controlling-dc-motor | 40.8 | 0.1173 | 10 | 42 | 2 | 0 | listed parts 1.0 |
| docs-due-due-motor-shield-dc | 27.5 | 0.077 | 6 | 32 | 2 | 2 | listed parts 1.0 |
| docs-due-simple-waveform-generator | 79.3 | 0.1687 | 18 | 74 | 0 | 2 | listed parts 1.0 |
| docs-zero-simple-audio-frequency-meter | 124.1 | 0.2129 | 23 | 94 | 4 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-web-server-ap-mode | 22.4 | 0.1013 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-hosting-a-webserver | 24.4 | 0.1007 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-analog-to-midi | 117.9 | 0.2291 | 23 | 94 | 1 | 0 | listed parts 1.0 |
| docs-mkr-vidor-hosting-a-webserver | 23.9 | 0.0773 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-mkr-lora-button-press-649 | 42.7 | 0.112 | 15 | 32 | 2 | 0 | listed parts 1.0 |
| docs-mkr-arduino-mkr-gsm-1400-and-dtmf | 45.9 | 0.1097 | 18 | 53 | 5 | 9 | listed parts 0.5 (missing led) |
| docs-mkr-hosting-a-webserver | 22.4 | 0.1113 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-mkr-enabling-ble | 25.1 | 0.1113 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-lora-button-press-995 | 39.8 | 0.1344 | 13 | 32 | 1 | 0 | listed parts 1.0 |
| docs-mkr-powering-with-batteries | 14.4 | 0.0908 | 6 | 13 | 0 | 3 | listed parts 1.0 |
| docs-mkr-web-server-ap-mode | 26.0 | 0.1091 | 7 | 17 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-zero-garden-automation | 94.4 | 0.2158 | 25 | 96 | 7 | 0 | listed parts 1.0 |
| docs-mkr-mkr-zero-weather-data-logger | 42.4 | 0.1066 | 14 | 37 | 0 | 9 | listed parts 0.667 (missing sensor) |
| docs-mkr-smart-garden-project | 42.4 | 0.1334 | 10 | 35 | 6 | 5 | listed parts 1.0 |
| docs-mkr-mkr-relay-shield-basic | 46.8 | 0.1434 | 12 | 50 | 1 | 0 | listed parts 1.0 |
| docs-communication-barometricpressuresensor | 23.0 | 0.0851 | 9 | 28 | 0 | 0 | listed parts 1.0 |
| docs-opta-10-opta-modbus-tcp-plc-ide | 25.3 | 0.1198 | 8 | 12 | 3 | 0 | listed parts 1.0 |
| docs-mkr-mkr-motor-carrier-battery | 27.4 | 0.1112 | 5 | 23 | 2 | 4 | listed parts 1.0 |
| docs-generic-basic-servo-control | 15.3 | 0.0552 | 5 | 12 | 0 | 6 | listed parts 1.0 |
| docs-generic-digital-input-pullup | 18.7 | 0.0737 | 5 | 16 | 0 | 0 | listed parts 1.0 |
| docs-communication-digitalpotcontrol | 106.1 | 0.2484 | 41 | 200 | 1 | 0 | listed parts 1.0 |
| docs-projects-arduino-iot-cloud-amazon-alexa-integration | 43.8 | 0.1376 | 16 | 66 | 1 | 5 | listed parts 1.0 |
| docs-generic-midi-device | 85.2 | 0.2347 | 30 | 136 | 0 | 14 | listed parts 1.0 |
| docs-projects-full-control-of-your-tv-using-alexa-and-arduino-iot-cloud | 104.5 | 0.1903 | 12 | 50 | 0 | 10 | listed parts 1.0 |
| docs-projects-gnome-forecaster | 38.2 | 0.1747 | 16 | 45 | 4 | 0 | listed parts 1.0 |
| pi-python-quick-reaction-game | 56.7 | 0.1596 | 12 | 48 | 1 | 0 | listed parts None |
| docs-projects-make-it-rain-clap-machine | 81.5 | 0.1835 | 29 | 112 | 2 | 12 | listed parts 1.0 |
| pi-push-button-stop-motion | 36.0 | 0.1087 | 7 | 20 | 2 | 0 | listed parts 1.0 |
| pi-gpio-music-box | 44.1 | 0.1325 | 16 | 68 | 0 | 1 | listed parts 1.0 |
| pi-balloon-pi-tay-popper | 54.5 | 0.1519 | 15 | 50 | 2 | 0 | listed parts 1.0 |
| pi-pir-motion-sensors | 15.5 | 0.0649 | 5 | 12 | 0 | 0 | listed parts None |
| pi-laser-tripwire | 37.6 | 0.1252 | 10 | 32 | 0 | 0 | listed parts 1.0 |
| pi-camjam-kit-1 | 60.7 | 0.1575 | 17 | 64 | 0 | 0 | listed parts 1.0 |
| pi-rpi-gpio-wiring-a-button | 31.2 | 0.0609 | 9 | 36 | 0 | 0 | listed parts None |
| pi-physical-computing | 36.3 | 0.1261 | 7 | 20 | 0 | 0 | listed parts None |
| pi-ultrasonic-theremin | 58.9 | 0.1184 | 15 | 52 | 0 | 8 | listed parts 1.0 |
| pi-rpi-gpio-connect-pir | 15.3 | 0.0303 | 5 | 12 | 0 | 0 | listed parts None |
| pi-rpi-python-piezoelectric-buzzer | 21.7 | 0.0423 | 5 | 12 | 0 | 0 | listed parts None |
| pi-rpi-physical-connect-led | 25.4 | 0.0618 | 6 | 16 | 0 | 0 | listed parts None |
| pi-build-a-buggy | 26.1 | 0.0729 | 5 | 20 | 2 | 4 | listed parts 1.0 |
| pi-rpi-physical-connect-motor-controller | 29.1 | 0.0816 | 5 | 22 | 1 | 4 | listed parts None |
| pi-generic-electronics-connect-ultrasonic-distance-sensor | 37.5 | 0.075 | 12 | 44 | 0 | 8 | listed parts None |
| pi-build-a-robot | 6.9 | 0.0561 | 0 | 0 | 0 | 0 | listed parts None |
| pi-traffic-lights-python | 19.1 | 0.0793 | 2 | 8 | 1 | 0 | listed parts 0.0 (missing led, resistor) |
| pi-interactive-traffic-lights-python | 56.0 | 0.1485 | 17 | 60 | 0 | 2 | listed parts 1.0 |
| pi-reaction | 13.8 | 0.0712 | 1 | 0 | 1 | 1 | listed parts None |
| pi-rpi-connect-led | 16.8 | 0.0737 | 6 | 16 | 0 | 0 | listed parts None |
| pi-rpi-connect-buzzer | 18.3 | 0.0795 | 5 | 12 | 0 | 0 | listed parts None |
