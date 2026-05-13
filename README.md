The solva_server_signalk.py reads analog data via an mcp3208.
The data read is:
-**Starter Battery Voltage** - the measured voltage from the starter battery (house battery is done via BMS)
-**Watertank Levels** - We use a 0-190 Ohm mechanic sensor. In our case the sensor shows a full tank on 170Ohm (see src code and adopt for your case)

### Key Connections

**MCP3208 SPI (bit-banged) → Raspberry Pi:**
| Signal | GPIO (BCM) | MCP3208 Pin |
|--------|-----------|-------------|
| CLK | 6 | Pin 13 |
| DOUT | 13 | Pin 12 |
| DIN | 19 | Pin 11 |
| CS | 26 | Pin 10 |
|VDD,Vref (3,3V) | 1 | Pin 15,16 |
|5V for resistive sensor | 2 ||

**ADC Channels in use:**
- **CH5** — Starter battery voltage via a **1800Ω / 470Ω voltage divider** (measures up to ~16V)
- **CH6** — Water Tank 2 via a **resistive sensor** (180Ω series, 5V supply)
- **CH7** — Water Tank 1 via a **resistive sensor** (180Ω series, 5V supply)

The diagram also documents the **echo sensor GPIOs** (23, 18, 25, 24) which are initialized but not actively used in the SignalK version.

Check out the full diagram artifact — it includes the MCP3208 DIP pinout, voltage divider and water sensor schematics, and a complete GPIO summary table. Let me know if anything needs correction!
