# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 93 manuals succeeded, 3 failed · wall time 2576 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 67.954 | 55.9 | 111.6 | 6320 |
| Input tokens | 61956 | 45090 | 107496 | 5761894 |
| Output tokens | 9051 | 7153 | 17479 | 841731 |
| Cost (USD) | 0.15 | 0.1354 | 0.2433 | 13.98 |

Estimated cost for 100 manuals at this rate: **$15.03**.

### Accuracy

**48 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 27 / 48 (56%) |
| Mean net precision | 0.736 |
| Mean net recall | 0.712 |
| Parts list correct (V1) | 29 / 48 |

**45 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 0.981.

**First-time part creation:** 1 drafted types could be checked against verified cards: polarity right 1/1, symmetry right 1/1, port count right 0/1.

### Check and repair loop

Build → check → repair → final check. **15/93** manuals had check failures after the first build; **10** of those were fully fixed by the repair. Issues in total: 40 → 16.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 93 | 37.212 | 0.07 | 0.004 |
| parts | 93 | 23.809 | 0.062 | 0.0 |
| repair-after-upkeep | 2 | 31.3 | 0.09 | 0.0 |
| repair1 | 15 | 28.767 | 0.071 | 0.002 |
| repair2 | 6 | 25.117 | 0.068 | 0.005 |

**Accuracy before → after repair** (1 tutorials with an answer key that were repaired): all nets correct 0 → 0; mean net recall 0.679 → 0.679.

### Spec rules and structure

- Manuals with **no rule problems**: 85/93 (91%).
- Problems by rule: V4 ×24, V2 ×1 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 0/93; overrides used in 0.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 25 | 0 | 0 |
| 50 | 0 | 0 |
| 75 | 1 | 18 |
| 93 | 2 | 32 |

### Failures

- `docs-projects-make-it-rain-clap-machine`: RuntimeError: claude -p failed: API Error: This request would exceed your account's rate limit. Please try again later.
- `pi-python-quick-reaction-game`: RuntimeError: claude -p failed: You've hit your session limit · resets 4:20pm (Europe/Dublin)
- `docs-projects-full-control-of-your-tv-using-alexa-and-arduino-iot-cloud`: RuntimeError: claude -p failed: API Error: This request would exceed your account's rate limit. Please try again later.

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| adxl3xx | 36.5 | 0.0997 | 9 | 36 | 0 | 0 | nets 3/5  |
| analog-in-out-serial | 40.4 | 0.1003 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| analog-input | 44.3 | 0.1067 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| analog-read-serial | 27.6 | 0.0582 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| arduino-isp | 55.9 | 0.1317 | 21 | 72 | 0 | 0 | nets 7/15  |
| analog-write-mega | 107.8 | 0.2587 | 51 | 196 | 0 | 0 | nets 25/25 ✅ |
| arduino-to-breadboard | 103.1 | 0.1962 | 21 | 128 | 0 | 0 | nets 3/7  |
| arrays | 70.2 | 0.1665 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| blink | 23.7 | 0.0683 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| blink-without-delay | 22.4 | 0.0698 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| button | 44.3 | 0.0998 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| calibration | 53.1 | 0.1146 | 13 | 44 | 0 | 0 | nets 2/7  |
| button-mouse-control | 81.2 | 0.1816 | 24 | 108 | 0 | 0 | nets 7/7 ✅ |
| debounce | 50.5 | 0.1108 | 9 | 32 | 0 | 0 | nets 2/5  |
| dimmer | 22.6 | 0.0757 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| fade | 22.5 | 0.0677 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| digital-read-serial | 49.4 | 0.108 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| fading | 22.4 | 0.0674 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| graph | 25.7 | 0.0713 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| if-statement | 26.7 | 0.0737 | 6 | 18 | 0 | 0 | nets 2/5  |
| input-pullup-serial | 27.1 | 0.0745 | 5 | 16 | 0 | 0 | nets 1/4  |
| for-loop | 69.3 | 0.1664 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| joystick-mouse-control | 45.9 | 0.1112 | 12 | 46 | 0 | 0 | nets 2/8  |
| keyboard-logout | 32.5 | 0.0759 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| keyboard-message | 38.8 | 0.0924 | 8 | 28 | 0 | 0 | nets 3/3 ✅ |
| keyboard-reprogram | 27.7 | 0.0781 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| knock | 25.3 | 0.0727 | 6 | 16 | 0 | 0 | nets 1/4  |
| keyboard-mouse-control | 89.6 | 0.1895 | 24 | 108 | 0 | 0 | nets 7/7 ✅ |
| memsic2125 | 55.7 | 0.1218 | 9 | 36 | 0 | 0 | nets 4/4 ✅ |
| led-bar-graph | 93.5 | 0.1989 | 37 | 142 | 0 | 0 | nets 2/23  |
| midi | 42.1 | 0.0915 | 8 | 24 | 0 | 0 | nets 3/4  |
| physical-pixel | 28.9 | 0.0858 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| ping | 26.5 | 0.0737 | 6 | 18 | 0 | 0 | nets 0/3  |
| read-analog-voltage | 30.1 | 0.079 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| pitch-follower | 37.4 | 0.0964 | 10 | 32 | 0 | 0 | nets 2/4  |
| read-ascii-string | 40.1 | 0.1075 | 10 | 36 | 0 | 0 | nets 7/7 ✅ |
| serial-call-response | 83.8 | 0.1881 | 17 | 64 | 0 | 0 | nets 1/5  |
| serial-call-response-ascii | 82.6 | 0.1581 | 17 | 64 | 0 | 0 | nets 1/5  |
| smoothing | 30.1 | 0.0773 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| row-column-scanning | 149.2 | 0.3444 | 37 | 124 | 0 | 0 | nets 19/28  |
| switch-case-sensor | 41.6 | 0.0966 | 9 | 28 | 0 | 0 | nets 3/3 ✅ |
| state-change-detection | 55.1 | 0.1123 | 9 | 32 | 0 | 0 | nets 2/5  |
| tone-melody | 21.4 | 0.0385 | 5 | 12 | 0 | 0 | nets 2/2 ✅ |
| switch-case-serial | 64.7 | 0.1511 | 23 | 84 | 0 | 0 | nets 11/11 ✅ |
| tone-multiple | 40.8 | 0.1009 | 12 | 40 | 0 | 0 | nets 0/4  |
| tone-keyboard | 76.5 | 0.1672 | 24 | 76 | 0 | 0 | nets 4/6  |
| virtual-color-mixer | 59.4 | 0.1379 | 15 | 52 | 0 | 0 | nets 0/5  |
| docs-nano-33-ble-sense-i2c | 71.8 | 0.1897 | 14 | 36 | 0 | 0 | listed parts 1.0 |
| while-loop | 76.9 | 0.1585 | 18 | 68 | 0 | 0 | nets 3/8  |
| docs-nano-33-ble-i2c | 70.2 | 0.1534 | 14 | 50 | 0 | 0 | listed parts 1.0 |
| docs-nano-every-i2c | 48.0 | 0.1258 | 13 | 34 | 0 | 0 | listed parts 1.0 |
| docs-nano-33-iot-i2c | 93.2 | 0.2433 | 15 | 40 | 0 | 0 | listed parts 1.0 |
| docs-nano-matter-03-matter-fan | 84.4 | 0.1122 | 8 | 19 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-05-matter-rgb-light | 81.3 | 0.1232 | 8 | 25 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-06-matter-temp-sensor | 74.5 | 0.1633 | 12 | 45 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-04-matter-relay-lightbulb | 165.3 | 0.2926 | 11 | 27 | 3 | 1 | listed parts None |
| docs-uno-r4-minima-dac | 62.6 | 0.1475 | 11 | 38 | 0 | 0 | listed parts 1.0 |
| docs-nano-rp2040-connect-rp2040-ble-device-to-device | 64.6 | 0.1573 | 9 | 22 | 1 | 0 | listed parts 1.0 |
| docs-uno-rev3-matlab-pwm-blink | 36.8 | 0.105 | 12 | 35 | 0 | 0 | listed parts 1.0 |
| docs-uno-r4-wifi-dac | 111.6 | 0.2324 | 11 | 38 | 1 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-hosting-a-webserver | 55.1 | 0.1431 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-web-server-ap-mode | 53.4 | 0.148 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-yun-rev2-shell-commands | 49.4 | 0.0684 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-uno-msr3-controlling-dc-motor | 75.8 | 0.1354 | 5 | 29 | 0 | 0 | listed parts 1.0 |
| docs-uno-barometric-pressure-web-server | 93.1 | 0.1235 | 10 | 36 | 2 | 0 | listed parts 1.0 |
| docs-due-due-motor-shield-dc | 93.8 | 0.1743 | 5 | 14 | 0 | 0 | listed parts 1.0 |
| docs-yun-rev2-temperature-web-panel | 76.4 | 0.1857 | 7 | 19 | 1 | 0 | listed parts 1.0 |
| docs-zero-simple-audio-frequency-meter | 184.3 | 0.3274 | 23 | 94 | 2 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-hosting-a-webserver | 78.3 | 0.1834 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-due-simple-waveform-generator | 155.2 | 0.4282 | 18 | 74 | 1 | 0 | listed parts 1.0 |
| docs-mkr-analog-to-midi | 197.7 | 0.3307 | 23 | 94 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-web-server-ap-mode | 46.8 | 0.1854 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-mkr-vidor-hosting-a-webserver | 39.4 | 0.1363 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-arduino-mkr-gsm-1400-and-dtmf | 88.1 | 0.1157 | 13 | 47 | 1 | 0 | listed parts 0.5 (missing led) |
| docs-mkr-lora-button-press-649 | 88.8 | 0.1871 | 15 | 32 | 1 | 0 | listed parts 1.0 |
| docs-mkr-enabling-ble | 33.8 | 0.1455 | 7 | 17 | 0 | 2 | listed parts 1.0 |
| docs-mkr-lora-button-press-995 | 73.6 | 0.1514 | 15 | 34 | 1 | 4 | listed parts 1.0 |
| docs-mkr-hosting-a-webserver | 26.4 | 0.0969 | 6 | 16 | 0 | 2 | listed parts 1.0 |
| docs-mkr-web-server-ap-mode | 26.4 | 0.1395 | 7 | 17 | 0 | 2 | listed parts 1.0 |
| docs-mkr-powering-with-batteries | 59.9 | 0.174 | 6 | 17 | 0 | 2 | listed parts 1.0 |
| docs-mkr-mkr-zero-weather-data-logger | 77.8 | 0.1725 | 10 | 33 | 1 | 0 | listed parts 0.667 (missing sensor) |
| docs-mkr-mkr-relay-shield-basic | 60.4 | 0.1069 | 10 | 29 | 0 | 4 | listed parts 1.0 |
| docs-mkr-mkr-motor-carrier-battery | 84.3 | 0.1472 | 5 | 12 | 1 | 0 | listed parts 1.0 |
| docs-mkr-smart-garden-project | 146.5 | 0.2053 | 10 | 28 | 5 | 0 | listed parts 1.0 |
| docs-opta-10-opta-modbus-tcp-plc-ide | 91.8 | 0.1744 | 8 | 16 | 2 | 0 | listed parts 1.0 |
| docs-mkr-mkr-zero-garden-automation | 347.4 | 0.4625 | 23 | 77 | 0 | 0 | listed parts 1.0 |
| docs-generic-basic-servo-control | 18.3 | 0.0668 | 5 | 12 | 0 | 0 | listed parts 1.0 |
| docs-communication-barometricpressuresensor | 27.3 | 0.1235 | 9 | 28 | 0 | 0 | listed parts 1.0 |
| docs-generic-digital-input-pullup | 25.8 | 0.0549 | 5 | 16 | 0 | 0 | listed parts 1.0 |
| docs-generic-midi-device | 99.7 | 0.2419 | 30 | 136 | 0 | 0 | listed parts 1.0 |
| docs-projects-arduino-iot-cloud-amazon-alexa-integration | 84.5 | 0.2095 | 11 | 37 | 1 | 8 | listed parts 1.0 |
| docs-communication-digitalpotcontrol | 138.2 | 0.3136 | 41 | 200 | 1 | 0 | listed parts 1.0 |
| docs-projects-gnome-forecaster | 134.8 | 0.4001 | 16 | 45 | 2 | 0 | listed parts 1.0 |
