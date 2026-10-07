# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 117 manuals succeeded, 0 failed · wall time 1409 s with 4 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 44.468 | 35.1 | 79.6 | 5203 |
| Input tokens | 26130 | 20468 | 48409 | 3057257 |
| Output tokens | 6750 | 5191 | 12368 | 789771 |
| Cost (USD) | 0.122 | 0.1051 | 0.225 | 14.29 |

Estimated cost for 100 manuals at this rate: **$12.21**.

### Accuracy

**48 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 27 / 48 (56%) |
| Mean net precision | 0.721 |
| Mean net recall | 0.697 |
| Parts list correct (V1) | 29 / 48 |

**69 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 0.958.

**First-time part creation:** 3 drafted types could be checked against verified cards: polarity right 3/3, symmetry right 3/3, port count right 0/3.

### Check and repair loop

Build → check → repair → final check. **22/117** manuals had check failures after the first build; **20** of those were fully fixed by the repair. Issues in total: 67 → 2.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 117 | 39.183 | 0.104 | 0.003 |
| repair1 | 22 | 25.695 | 0.091 | 0.002 |
| repair2 | 3 | 17.667 | 0.048 | 0.003 |

**Accuracy before → after repair** (5 tutorials with an answer key that were repaired): all nets correct 1 → 2; mean net recall 0.38 → 0.53.

### Spec rules and structure

- Manuals with **no rule problems**: 117/117 (100%).
- Problems by rule: none (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 6/117; overrides used in 6.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 25 | 0 | 0 |
| 50 | 1 | 4 |
| 75 | 0 | 41 |
| 117 | 1 | 86 |

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| analog-read-serial | 23.0 | 0.0469 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| adxl3xx | 26.3 | 0.0814 | 9 | 36 | 0 | 0 | nets 3/5  |
| analog-input | 32.8 | 0.1022 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| analog-in-out-serial | 34.4 | 0.0861 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| arduino-isp | 46.2 | 0.1088 | 22 | 76 | 0 | 0 | nets 0/15  |
| blink | 15.7 | 0.0574 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| arrays | 59.4 | 0.1386 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| analog-write-mega | 77.5 | 0.2118 | 51 | 196 | 0 | 0 | nets 25/25 ✅ |
| arduino-to-breadboard | 69.3 | 0.1402 | 19 | 120 | 0 | 0 | nets 1/7  |
| blink-without-delay | 16.9 | 0.0526 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| button | 37.9 | 0.0591 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| calibration | 41.2 | 0.0952 | 13 | 44 | 0 | 0 | nets 2/7  |
| debounce | 35.1 | 0.0836 | 9 | 32 | 0 | 0 | nets 2/5  |
| dimmer | 15.9 | 0.0618 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| fade | 19.0 | 0.0575 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| button-mouse-control | 72.0 | 0.1577 | 24 | 108 | 0 | 0 | nets 7/7 ✅ |
| digital-read-serial | 40.7 | 0.0613 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| fading | 19.7 | 0.0563 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| graph | 20.7 | 0.0597 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| if-statement | 33.2 | 0.0975 | 6 | 18 | 0 | 0 | nets 2/5  |
| input-pullup-serial | 36.8 | 0.0653 | 5 | 16 | 0 | 0 | nets 1/4  |
| joystick-mouse-control | 24.9 | 0.0387 | 8 | 21 | 0 | 0 | nets 0/8  |
| for-loop | 59.1 | 0.1341 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| keyboard-logout | 19.8 | 0.0586 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| knock | 18.2 | 0.0579 | 6 | 16 | 0 | 0 | nets 1/4  |
| keyboard-message | 33.2 | 0.0488 | 8 | 28 | 0 | 0 | nets 3/3 ✅ |
| keyboard-reprogram | 32.8 | 0.0965 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| keyboard-mouse-control | 62.6 | 0.1242 | 24 | 108 | 0 | 0 | nets 7/7 ✅ |
| midi | 28.0 | 0.0744 | 8 | 26 | 0 | 0 | nets 3/4  |
| memsic2125 | 34.5 | 0.0861 | 9 | 36 | 0 | 0 | nets 4/4 ✅ |
| physical-pixel | 17.9 | 0.0701 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| ping | 19.5 | 0.0582 | 6 | 18 | 0 | 0 | nets 0/3  |
| led-bar-graph | 66.1 | 0.1221 | 37 | 142 | 0 | 0 | nets 2/23  |
| pitch-follower | 30.8 | 0.0797 | 10 | 32 | 1 | 0 | nets 2/4  |
| read-analog-voltage | 23.3 | 0.0632 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| read-ascii-string | 28.1 | 0.0863 | 10 | 36 | 0 | 0 | nets 7/7 ✅ |
| smoothing | 21.4 | 0.0594 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| row-column-scanning | 62.2 | 0.1 | 37 | 124 | 0 | 0 | nets 19/28  |
| serial-call-response | 68.0 | 0.1751 | 17 | 64 | 0 | 0 | nets 1/5  |
| serial-call-response-ascii | 62.9 | 0.1516 | 17 | 64 | 0 | 0 | nets 1/5  |
| state-change-detection | 32.7 | 0.0808 | 9 | 32 | 0 | 0 | nets 2/5  |
| switch-case-sensor | 17.2 | 0.059 | 9 | 28 | 0 | 0 | nets 3/3 ✅ |
| tone-melody | 13.3 | 0.0525 | 5 | 12 | 0 | 0 | nets 2/2 ✅ |
| tone-multiple | 51.8 | 0.1707 | 12 | 40 | 0 | 0 | nets 0/4  |
| while-loop | 66.6 | 0.1335 | 18 | 68 | 0 | 0 | nets 5/8  |
| virtual-color-mixer | 128.1 | 0.1459 | 15 | 52 | 0 | 0 | nets 0/5  |
| docs-nano-33-ble-sense-i2c | 32.1 | 0.0881 | 13 | 34 | 1 | 0 | listed parts 1.0 |
| docs-nano-33-ble-i2c | 30.9 | 0.0937 | 13 | 36 | 0 | 0 | listed parts 1.0 |
| docs-nano-33-iot-i2c | 33.7 | 0.0988 | 13 | 34 | 1 | 0 | listed parts 1.0 |
| docs-nano-every-i2c | 33.1 | 0.0969 | 13 | 34 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-03-matter-fan | 50.6 | 0.21 | 8 | 23 | 3 | 0 | listed parts 1.0 |
| docs-nano-matter-05-matter-rgb-light | 35.9 | 0.1149 | 8 | 25 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-06-matter-temp-sensor | 52.8 | 0.1432 | 12 | 53 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-04-matter-relay-lightbulb | 71.5 | 0.2063 | 10 | 29 | 4 | 0 | listed parts None |
| docs-nano-rp2040-connect-rp2040-ble-device-to-device | 36.6 | 0.1176 | 9 | 24 | 1 | 0 | listed parts 1.0 |
| docs-uno-r4-minima-dac | 41.1 | 0.1051 | 11 | 38 | 0 | 0 | listed parts 1.0 |
| docs-uno-rev3-matlab-pwm-blink | 27.8 | 0.108 | 13 | 36 | 1 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-hosting-a-webserver | 26.5 | 0.1022 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-web-server-ap-mode | 24.3 | 0.0817 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-uno-r4-wifi-dac | 41.5 | 0.1065 | 11 | 38 | 0 | 0 | listed parts 1.0 |
| docs-yun-rev2-shell-commands | 27.5 | 0.0565 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-yun-rev2-temperature-web-panel | 25.7 | 0.0632 | 6 | 18 | 1 | 0 | listed parts 1.0 |
| docs-uno-msr3-controlling-dc-motor | 60.5 | 0.199 | 10 | 36 | 2 | 0 | listed parts 1.0 |
| docs-uno-barometric-pressure-web-server | 93.0 | 0.2675 | 10 | 42 | 2 | 0 | listed parts 1.0 |
| docs-due-due-motor-shield-dc | 54.6 | 0.1541 | 6 | 23 | 3 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-hosting-a-webserver | 22.5 | 0.103 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-due-simple-waveform-generator | 62.3 | 0.1588 | 18 | 74 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-web-server-ap-mode | 17.9 | 0.0992 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-zero-simple-audio-frequency-meter | 113.6 | 0.225 | 21 | 82 | 4 | 0 | listed parts 1.0 |
| docs-mkr-vidor-hosting-a-webserver | 25.5 | 0.077 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-mkr-arduino-mkr-gsm-1400-and-dtmf | 49.2 | 0.1262 | 18 | 58 | 5 | 0 | listed parts 0.5 (missing led) |
| docs-mkr-enabling-ble | 24.3 | 0.1192 | 7 | 17 | 1 | 0 | listed parts 1.0 |
| docs-mkr-lora-button-press-995 | 37.7 | 0.1357 | 13 | 30 | 2 | 0 | listed parts 1.0 |
| docs-mkr-lora-button-press-649 | 67.9 | 0.2249 | 15 | 34 | 2 | 0 | listed parts 1.0 |
| docs-mkr-hosting-a-webserver | 19.7 | 0.1113 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-analog-to-midi | 134.3 | 0.2579 | 23 | 94 | 2 | 0 | listed parts 1.0 |
| docs-mkr-web-server-ap-mode | 22.8 | 0.1133 | 7 | 17 | 0 | 0 | listed parts 1.0 |
| docs-mkr-powering-with-batteries | 51.3 | 0.2697 | 6 | 18 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-zero-weather-data-logger | 68.0 | 0.2032 | 14 | 40 | 1 | 0 | listed parts 0.667 (missing sensor) |
| docs-mkr-mkr-relay-shield-basic | 80.9 | 0.3104 | 12 | 46 | 1 | 0 | listed parts 1.0 |
| docs-mkr-mkr-zero-garden-automation | 110.7 | 0.3131 | 24 | 61 | 7 | 0 | listed parts 1.0 |
| docs-mkr-smart-garden-project | 79.6 | 0.1591 | 10 | 28 | 6 | 0 | listed parts 1.0 |
| docs-opta-10-opta-modbus-tcp-plc-ide | 25.2 | 0.128 | 8 | 16 | 3 | 0 | listed parts 1.0 |
| docs-communication-barometricpressuresensor | 18.8 | 0.0863 | 9 | 28 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-motor-carrier-battery | 60.4 | 0.1703 | 5 | 25 | 2 | 0 | listed parts 1.0 |
| docs-generic-basic-servo-control | 10.6 | 0.0894 | 5 | 12 | 0 | 0 | listed parts 1.0 |
| docs-generic-digital-input-pullup | 16.3 | 0.0394 | 5 | 16 | 0 | 0 | listed parts 1.0 |
| docs-communication-digitalpotcontrol | 101.7 | 0.2508 | 43 | 208 | 1 | 0 | listed parts 1.0 |
| docs-generic-midi-device | 88.7 | 0.2481 | 30 | 136 | 0 | 0 | listed parts 1.0 |
| docs-projects-arduino-iot-cloud-amazon-alexa-integration | 84.3 | 0.2782 | 16 | 66 | 1 | 0 | listed parts 1.0 |
| docs-projects-gnome-forecaster | 35.5 | 0.1759 | 15 | 44 | 3 | 0 | listed parts 0.5 (missing sensor) |
| pi-python-quick-reaction-game | 53.1 | 0.1516 | 12 | 48 | 1 | 0 | listed parts None |
| pi-push-button-stop-motion | 34.1 | 0.1186 | 7 | 20 | 2 | 0 | listed parts 1.0 |
| docs-projects-make-it-rain-clap-machine | 86.6 | 0.2406 | 36 | 137 | 2 | 0 | listed parts 1.0 |
| docs-projects-full-control-of-your-tv-using-alexa-and-arduino-iot-cloud | 181.1 | 0.3881 | 12 | 50 | 0 | 0 | listed parts 1.0 |
| pi-balloon-pi-tay-popper | 55.8 | 0.1622 | 15 | 54 | 2 | 0 | listed parts 1.0 |
| pi-gpio-music-box | 72.2 | 0.2416 | 16 | 69 | 0 | 0 | listed parts 1.0 |
| pi-laser-tripwire | 41.3 | 0.1364 | 10 | 32 | 0 | 0 | listed parts 1.0 |
| pi-pir-motion-sensors | 11.8 | 0.0662 | 5 | 12 | 0 | 0 | listed parts None |
| pi-physical-computing | 34.9 | 0.1683 | 7 | 20 | 0 | 0 | listed parts None |
| pi-camjam-kit-1 | 59.7 | 0.1222 | 17 | 64 | 0 | 0 | listed parts 1.0 |
| pi-rpi-gpio-wiring-a-button | 34.4 | 0.0665 | 9 | 36 | 0 | 0 | listed parts None |
| pi-rpi-python-piezoelectric-buzzer | 14.8 | 0.0331 | 5 | 12 | 0 | 0 | listed parts None |
| pi-rpi-gpio-connect-pir | 17.1 | 0.0315 | 5 | 12 | 0 | 0 | listed parts None |
| pi-rpi-physical-connect-led | 20.6 | 0.0569 | 6 | 16 | 0 | 0 | listed parts None |
| pi-ultrasonic-theremin | 73.5 | 0.1294 | 15 | 52 | 0 | 0 | listed parts 1.0 |
| pi-build-a-robot | 6.8 | 0.0201 | 0 | 0 | 0 | 0 | listed parts None |
| pi-build-a-buggy | 41.6 | 0.1018 | 19 | 41 | 7 | 0 | listed parts 1.0 |
| pi-traffic-lights-python | 15.3 | 0.0405 | 2 | 8 | 1 | 0 | listed parts 0.0 (missing led, resistor) |
| pi-generic-electronics-connect-ultrasonic-distance-sensor | 42.0 | 0.0812 | 12 | 44 | 0 | 0 | listed parts None |
| pi-rpi-physical-connect-motor-controller | 50.1 | 0.1402 | 5 | 22 | 1 | 0 | listed parts None |
| pi-rpi-connect-led | 18.4 | 0.0817 | 6 | 16 | 0 | 0 | listed parts None |
| pi-rpi-connect-buzzer | 16.9 | 0.0397 | 5 | 12 | 0 | 0 | listed parts None |
| pi-reaction | 25.0 | 0.1712 | 2 | 2 | 1 | 0 | listed parts None |
| pi-interactive-traffic-lights-python | 54.9 | 0.1572 | 17 | 64 | 0 | 0 | listed parts 1.0 |
| switch-case-serial | 55.7 | 0.1264 | 23 | 84 | 0 | 0 | nets 11/11 ✅ |
| tone-keyboard | 58.9 | 0.1176 | 18 | 64 | 1 | 0 | nets 4/6  |
