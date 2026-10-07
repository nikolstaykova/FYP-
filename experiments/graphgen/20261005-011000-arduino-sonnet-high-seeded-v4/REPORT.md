# Graph generation: arduino

**Model:** `sonnet` · effort `high` · catalogue `seeded` · 94 manuals succeeded, 4 failed · wall time 3285 s with 3 in parallel

### Time and cost

| | Mean | Median | 90th pct | Total |
|---|---:|---:|---:|---:|
| Seconds per manual | 84.0 | 63.4 | 183.9 | 7896 |
| Input tokens | 41386 | 28771 | 82918 | 3890251 |
| Output tokens | 7991 | 6869 | 15169 | 751132 |
| Cost (USD) | 0.157 | 0.1292 | 0.2929 | 14.79 |

Estimated cost for 100 manuals at this rate: **$15.74**.

### Accuracy

**47 tutorials with an answer key** (CircuitQuest's verified circuit):

| Measure | Result |
|---|---:|
| All electrical connections correct | 24 / 47 (51%) |
| Mean net precision | 0.696 |
| Mean net recall | 0.674 |
| Parts list correct (V1) | 28 / 47 |

**47 tutorials without an answer key** (scored on the parts the tutorial lists): mean share of listed part families present = 0.975.

**First-time part creation:** 2 drafted types could be checked against verified cards: polarity right 2/2, symmetry right 2/2, port count right 0/2.

### Check and repair loop

Build → check → repair → final check. **18/94** manuals had check failures after the first build; **15** of those were fully fixed by the repair. Issues in total: 86 → 12.

| Phase | Runs | Mean seconds | Mean cost | Mean check seconds |
|---|---:|---:|---:|---:|
| build | 94 | 41.741 | 0.109 | 0.001 |
| parts | 94 | 36.09 | 0.03 | 0.0 |
| repair1 | 18 | 26.717 | 0.077 | 0.002 |
| repair2 | 5 | 19.78 | 0.054 | 0.0 |

**Accuracy before → after repair** (2 tutorials with an answer key that were repaired): all nets correct 0 → 0; mean net recall 0.25 → 0.5.

### Spec rules and structure

- Manuals with **no rule problems**: 92/94 (98%).
- Problems by rule: V4 ×4, V3 ×1 (V2 unused part, V3 incompatible ports, V4 missing/over-used port, refs unknown part).
- Manuals using **repeats**: 6/94; overrides used in 6.

### Store on demand (catalogue growth)

| After manual | New types in that manual | Catalogue additions so far |
|---:|---:|---:|
| 1 | 0 | 0 |
| 2 | 0 | 0 |
| 5 | 0 | 0 |
| 10 | 0 | 0 |
| 25 | 0 | 0 |
| 50 | 1 | 2 |
| 75 | 1 | 27 |
| 94 | 3 | 50 |

### Failures

- `physical-pixel`: URLError: <urlopen error _ssl.c:1011: The handshake operation timed out>
- `pi-push-button-stop-motion`: RuntimeError: claude -p failed: You've hit your session limit · resets 6am (Europe/Dublin)
- `pi-python-quick-reaction-game`: RuntimeError: claude -p failed: You've hit your session limit · resets 6am (Europe/Dublin)
- `pi-gpio-music-box`: RuntimeError: claude -p failed: You've hit your session limit · resets 6am (Europe/Dublin)

### Per manual

| Manual | Seconds | Cost | Parts | Edges | New types | Problems | Score |
|---|---:|---:|---:|---:|---:|---:|---|
| adxl3xx | 73.1 | 0.1268 | 9 | 36 | 0 | 0 | nets 3/5  |
| analog-in-out-serial | 78.0 | 0.0854 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| analog-read-serial | 21.4 | 0.0407 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| analog-input | 102.9 | 0.2028 | 10 | 34 | 0 | 0 | nets 5/5 ✅ |
| analog-write-mega | 53.3 | 0.1226 | 51 | 196 | 0 | 0 | nets 25/25 ✅ |
| arduino-isp | 46.2 | 0.0843 | 23 | 80 | 0 | 0 | nets 6/15  |
| blink | 16.9 | 0.059 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| arduino-to-breadboard | 61.6 | 0.1224 | 19 | 102 | 0 | 0 | nets 1/7  |
| blink-without-delay | 16.2 | 0.0542 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| arrays | 61.3 | 0.1377 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| button | 34.7 | 0.0539 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| debounce | 41.8 | 0.0858 | 9 | 32 | 0 | 0 | nets 2/5  |
| calibration | 48.7 | 0.0911 | 13 | 44 | 0 | 0 | nets 2/7  |
| dimmer | 16.6 | 0.0599 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| button-mouse-control | 87.3 | 0.1849 | 24 | 108 | 0 | 0 | nets 7/7 ✅ |
| digital-read-serial | 32.2 | 0.08 | 9 | 32 | 0 | 0 | nets 3/3 ✅ |
| fade | 19.6 | 0.0582 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| fading | 20.1 | 0.0554 | 6 | 16 | 0 | 0 | nets 3/3 ✅ |
| graph | 20.0 | 0.0589 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| if-statement | 20.4 | 0.0608 | 6 | 18 | 0 | 0 | nets 2/5  |
| input-pullup-serial | 23.0 | 0.0622 | 5 | 16 | 0 | 0 | nets 1/4  |
| for-loop | 55.8 | 0.1292 | 27 | 100 | 0 | 0 | nets 13/13 ✅ |
| keyboard-logout | 69.2 | 0.0875 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| keyboard-message | 74.5 | 0.0928 | 8 | 28 | 0 | 0 | nets 3/3 ✅ |
| joystick-mouse-control | 130.3 | 0.2495 | 12 | 46 | 0 | 0 | nets 2/8  |
| keyboard-reprogram | 46.5 | 0.08 | 5 | 16 | 0 | 0 | nets 2/2 ✅ |
| knock | 37.3 | 0.0907 | 6 | 16 | 0 | 0 | nets 0/4  |
| keyboard-mouse-control | 103.9 | 0.1606 | 24 | 108 | 0 | 0 | nets 7/7 ✅ |
| memsic2125 | 39.8 | 0.0893 | 9 | 36 | 0 | 0 | nets 4/4 ✅ |
| ping | 45.7 | 0.06 | 6 | 18 | 0 | 0 | nets 0/3  |
| led-bar-graph | 201.7 | 0.1434 | 37 | 142 | 0 | 0 | nets 2/23  |
| midi | 88.9 | 0.1678 | 8 | 26 | 0 | 0 | nets 3/4  |
| pitch-follower | 36.4 | 0.1145 | 10 | 32 | 0 | 0 | nets 2/4  |
| read-analog-voltage | 21.3 | 0.0603 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| read-ascii-string | 60.1 | 0.1493 | 10 | 36 | 0 | 0 | nets 6/7  |
| row-column-scanning | 84.3 | 0.1819 | 37 | 124 | 0 | 0 | nets 19/28  |
| serial-call-response | 87.6 | 0.1664 | 17 | 64 | 0 | 0 | nets 1/5  |
| smoothing | 26.1 | 0.0661 | 6 | 18 | 0 | 0 | nets 3/3 ✅ |
| serial-call-response-ascii | 63.4 | 0.1339 | 21 | 72 | 0 | 0 | nets 1/5  |
| state-change-detection | 42.4 | 0.0872 | 9 | 32 | 0 | 0 | nets 2/5  |
| switch-case-sensor | 31.0 | 0.0776 | 9 | 28 | 0 | 0 | nets 3/3 ✅ |
| tone-melody | 16.6 | 0.0567 | 5 | 12 | 0 | 0 | nets 0/2  |
| switch-case-serial | 48.9 | 0.12 | 23 | 84 | 0 | 0 | nets 11/11 ✅ |
| tone-multiple | 33.7 | 0.0815 | 12 | 40 | 1 | 0 | nets 0/4  |
| tone-keyboard | 71.7 | 0.1482 | 24 | 76 | 0 | 0 | nets 4/6  |
| virtual-color-mixer | 55.5 | 0.1527 | 15 | 52 | 0 | 0 | nets 0/5  |
| docs-nano-33-ble-sense-i2c | 37.2 | 0.1341 | 13 | 34 | 0 | 0 | listed parts 1.0 |
| while-loop | 67.9 | 0.1537 | 18 | 68 | 0 | 0 | nets 5/8  |
| docs-nano-33-iot-i2c | 30.4 | 0.0934 | 13 | 34 | 0 | 0 | listed parts 1.0 |
| docs-nano-33-ble-i2c | 59.8 | 0.199 | 15 | 38 | 1 | 0 | listed parts 1.0 |
| docs-nano-every-i2c | 125.1 | 0.2304 | 16 | 42 | 0 | 0 | listed parts 1.0 |
| docs-nano-matter-03-matter-fan | 187.3 | 0.357 | 8 | 24 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-05-matter-rgb-light | 70.5 | 0.2001 | 8 | 25 | 1 | 0 | listed parts 1.0 |
| docs-nano-matter-04-matter-relay-lightbulb | 183.9 | 0.319 | 12 | 32 | 4 | 0 | listed parts None |
| docs-nano-rp2040-connect-rp2040-ble-device-to-device | 131.6 | 0.1385 | 9 | 24 | 0 | 0 | listed parts 1.0 |
| docs-nano-matter-06-matter-temp-sensor | 178.6 | 0.1928 | 12 | 53 | 0 | 0 | listed parts 1.0 |
| docs-uno-r4-minima-dac | 58.1 | 0.1387 | 11 | 38 | 0 | 0 | listed parts 1.0 |
| docs-uno-r4-wifi-dac | 41.8 | 0.1126 | 11 | 38 | 0 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-hosting-a-webserver | 23.3 | 0.0785 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-uno-rev3-matlab-pwm-blink | 43.0 | 0.1247 | 13 | 36 | 1 | 0 | listed parts 1.0 |
| docs-uno-wifi-rev2-uno-wifi-r2-web-server-ap-mode | 25.7 | 0.0824 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-yun-rev2-shell-commands | 147.5 | 0.14 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-uno-barometric-pressure-web-server | 195.3 | 0.326 | 10 | 42 | 2 | 0 | listed parts 1.0 |
| docs-uno-msr3-controlling-dc-motor | 195.4 | 0.324 | 6 | 28 | 2 | 0 | listed parts 1.0 |
| docs-yun-rev2-temperature-web-panel | 118.9 | 0.1624 | 6 | 18 | 2 | 0 | listed parts 1.0 |
| docs-due-due-motor-shield-dc | 107.6 | 0.2404 | 6 | 20 | 2 | 0 | listed parts 1.0 |
| docs-due-simple-waveform-generator | 71.2 | 0.167 | 18 | 74 | 1 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-hosting-a-webserver | 25.4 | 0.1063 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-mkr-mkr-1000-web-server-ap-mode | 17.7 | 0.098 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-analog-to-midi | 141.3 | 0.2763 | 23 | 94 | 3 | 0 | listed parts 1.0 |
| docs-zero-simple-audio-frequency-meter | 273.7 | 0.488 | 23 | 94 | 2 | 0 | listed parts 1.0 |
| docs-mkr-vidor-hosting-a-webserver | 84.6 | 0.1286 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-arduino-mkr-gsm-1400-and-dtmf | 193.1 | 0.3423 | 12 | 39 | 1 | 0 | listed parts 1.0 |
| docs-mkr-lora-button-press-649 | 102.8 | 0.261 | 13 | 32 | 0 | 0 | listed parts 1.0 |
| docs-mkr-enabling-ble | 31.8 | 0.1148 | 6 | 16 | 1 | 0 | listed parts 1.0 |
| docs-mkr-hosting-a-webserver | 23.9 | 0.0882 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-lora-button-press-995 | 71.6 | 0.1725 | 13 | 30 | 1 | 0 | listed parts 1.0 |
| docs-mkr-web-server-ap-mode | 44.0 | 0.1058 | 6 | 16 | 0 | 0 | listed parts 1.0 |
| docs-mkr-powering-with-batteries | 98.3 | 0.2572 | 6 | 14 | 1 | 4 | listed parts 1.0 |
| docs-mkr-mkr-zero-weather-data-logger | 145.1 | 0.115 | 14 | 40 | 2 | 0 | listed parts 0.667 (missing sensor) |
| docs-mkr-mkr-relay-shield-basic | 155.8 | 0.1868 | 12 | 38 | 0 | 0 | listed parts 1.0 |
| docs-mkr-mkr-zero-garden-automation | 289.3 | 0.5891 | 23 | 44 | 1 | 0 | listed parts 1.0 |
| docs-mkr-mkr-motor-carrier-battery | 137.8 | 0.2062 | 5 | 24 | 1 | 0 | listed parts 1.0 |
| docs-opta-10-opta-modbus-tcp-plc-ide | 87.1 | 0.2845 | 8 | 12 | 2 | 0 | listed parts 1.0 |
| docs-communication-barometricpressuresensor | 99.1 | 0.1207 | 9 | 28 | 0 | 0 | listed parts 1.0 |
| docs-mkr-smart-garden-project | 141.4 | 0.2944 | 10 | 19 | 6 | 1 | listed parts 1.0 |
| docs-generic-basic-servo-control | 46.6 | 0.0873 | 5 | 12 | 0 | 0 | listed parts 1.0 |
| docs-generic-digital-input-pullup | 36.2 | 0.0728 | 5 | 16 | 0 | 0 | listed parts 1.0 |
| docs-projects-arduino-iot-cloud-amazon-alexa-integration | 81.2 | 0.1904 | 16 | 57 | 1 | 0 | listed parts 1.0 |
| docs-generic-midi-device | 97.1 | 0.2239 | 30 | 136 | 0 | 0 | listed parts 1.0 |
| docs-communication-digitalpotcontrol | 165.5 | 0.2761 | 41 | 200 | 1 | 0 | listed parts 0.667 (missing pot) |
| docs-projects-gnome-forecaster | 147.7 | 0.2929 | 15 | 44 | 3 | 0 | listed parts 0.5 (missing sensor) |
| docs-projects-full-control-of-your-tv-using-alexa-and-arduino-iot-cloud | 239.6 | 0.2873 | 12 | 50 | 1 | 0 | listed parts 1.0 |
| docs-projects-make-it-rain-clap-machine | 350.3 | 0.3789 | 34 | 139 | 3 | 0 | listed parts 1.0 |
