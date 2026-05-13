#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# solva_server_signalk.py
#
# Reads sensor data from MCP3208 ADC (starter battery voltage, 
# two water tank levels) and pushes the
# values to a local SignalK server via WebSocket delta messages.
#
# Based on solva_server.py - BMP085 support removed, Flask REST 
# service replaced with SignalK delta push.

import time
import json
import statistics
import random
import sys
import os
import signal
import logging
import websocket

# Only import GPIO when not in testing mode
TESTING = 0

if not TESTING:
    import RPi.GPIO as GPIO

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

print("-" * 40)
print("Solva Server (SignalK) started")
print("-" * 40)

# --- SignalK Configuration ---
SK_SERVER = "127.0.0.1"
SK_PORT = 3000
SK_WS_URL = f"ws://{SK_SERVER}:{SK_PORT}/signalk/v1/stream?subscribe=none"

# Update interval in seconds
UPDATE_INTERVAL = 10

# Duration in seconds to collect ADC samples before computing median
SAMPLE_DURATION = 5

# --- GPIO / Hardware Constants ---
HIGH = True   # 3.3V level (high)
LOW  = False  # 0V level (low)

# GPIO pins for echo sensors (kept for GPIO setup)
gpioTrigger1 = 23
gpioEcho1    = 18
gpioTrigger2 = 25
gpioEcho2    = 24

# GPIO pins for MCP3208 AD converter
CLK  = 6   # Clock
DOUT = 13  # Digital out
DIN  = 19  # Digital in
CS   = 26  # Chip-Select

# --- Water Tank Constants ---
waterMax1 = 2
waterMin1 = 20
waterMax2 = 2
waterMin2 = 33


# =============================================================================
# Sensor Reading Functions (preserved from solva_server.py)
# =============================================================================

def ConvertVolts(data, places, type):
    """Convert raw ADC data to voltage or water level percentage. 
    The MCP3208 ADC is connected to the Raspberry Pi's SPI interface.
    The reference voltage is 3.3V.
    """
    volts = (data * 3.3) / float(4095)  # convert to volt
    
    # Type 1: Voltage divider calculation for battery voltage
    if type == 1:
        volts = volts * (1800 + 470) / 470
        volts = round(volts, places)
    """Type 2: Resistance-based water level calculation. 
        R2 is the sensor, 180 Ohm is in series with the sensor. 
        The total resistance is R1+R2 = 180+R2.
        The voltage divider is connected to a 5V source. 
        The output voltage is Vout = 5V * R2 / (180+R2).
        The ADC is connected to the output voltage. 
        The senser delivers 0 - 190 Ohm, but 170 Ohm showed already as full in our tests
    """
    else:
        waterlevel = 0
        r2 = 180 * volts / (5 - volts)
        level = (r2 / 170) * 100
        
        if level >= 90:
            waterlevel = 100
        elif level >= 80:
            waterlevel = 90
        elif level >= 70:
            waterlevel = 80
        elif level >= 60:
            waterlevel = 70
        elif level >= 50:
            waterlevel = 60
        elif level >= 40:
            waterlevel = 50
        elif level >= 30:
            waterlevel = 40
        elif level >= 20:
            waterlevel = 30
        elif level >= 10:
            waterlevel = 20
        elif level >= 5:
            waterlevel = 10
        else:
            waterlevel = 0
        
        volts = waterlevel
    
    volts = round(volts, places)
    return volts


def getAnalogData(adCh, CLKPin, DINPin, DOUTPin, CSPin, type):
    """Read analog data from MCP3208 ADC on a given channel."""
    GPIO.output(CSPin, HIGH)
    GPIO.output(CSPin, LOW)
    GPIO.output(CLKPin, LOW)

    cmd = adCh
    cmd |= 0b00011000  # Command to read analog value from channel adCh

    # Send bit sequence
    for i in range(5):
        if cmd & 0x10:
            GPIO.output(DINPin, HIGH)
        else:
            GPIO.output(DINPin, LOW)
        GPIO.output(CLKPin, HIGH)
        GPIO.output(CLKPin, LOW)
        cmd <<= 1  # Shift bit sequence one position left

    # Read data
    adchvalue = 0
    for i in range(13):
        GPIO.output(CLKPin, HIGH)
        GPIO.output(CLKPin, LOW)
        adchvalue <<= 1
        if GPIO.input(DOUTPin):
            adchvalue |= 0x01

    time.sleep(0.5)
    adchvalue = ConvertVolts(adchvalue, 2, type)
    return adchvalue


def collect_samples(duration_seconds):
    """
    Collect ADC samples from all active channels over the given duration.
    Returns a dict with lists of samples per channel:
      { 'voltage1': [...], 'water1': [...], 'water2': [...] }
    """
    samples = {
        'voltage1': [],
        'water1': [],
        'water2': []
    }

    if TESTING:
        # In testing mode, generate random samples
        count = max(1, int(duration_seconds / 0.5))  # simulate ~0.5s per reading
        for _ in range(count):
            samples['voltage1'].append(random.uniform(11, 14))
            samples['water1'].append(random.uniform(0, 100))
            samples['water2'].append(random.uniform(0, 100))
        return samples

    end_time = time.time() + duration_seconds
    log.debug("Collecting samples for %d seconds...", duration_seconds)

    while time.time() < end_time:
        # Read each channel once per loop iteration
        # Starter Battery (ADC channel 5, type 1 = voltage)
        samples['voltage1'].append(
            getAnalogData(5, CLK, DIN, DOUT, CS, 1)
        )
        # Water Tank 1 (ADC channel 7, type 2 = water level)
        samples['water1'].append(
            getAnalogData(7, CLK, DIN, DOUT, CS, 2)
        )
        # Water Tank 2 (ADC channel 6, type 2 = water level)
        samples['water2'].append(
            getAnalogData(6, CLK, DIN, DOUT, CS, 2)
        )

    log.debug("Collected %d samples per channel", len(samples['voltage1']))
    return samples


# =============================================================================
# SignalK Delta Push
# =============================================================================

def build_signalk_delta(voltage1, water_level1, water_level2):
    """
    Build a SignalK delta message with battery and tank data.
    
    SignalK paths used:
      - electrical.batteries.starter.voltage      (Volts)
      - tanks.freshWater.0.currentLevel            (ratio 0.0 - 1.0)
      - tanks.freshWater.1.currentLevel            (ratio 0.0 - 1.0)
    """
    # Convert water level percentage (0-100) to ratio (0.0-1.0) for SignalK
    water_ratio1 = round(water_level1 / 100.0, 3)
    water_ratio2 = round(water_level2 / 100.0, 3)

    delta = {
        "updates": [
            {
                "source": {
                    "label": "solva-server",
                    "type": "solva.mcp3208"
                },
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime()),
                "values": [
                    {
                        "path": "electrical.batteries.starter.voltage",
                        "value": round(voltage1, 2)
                    },
                    {
                        "path": "tanks.freshWater.0.currentLevel",
                        "value": water_ratio1
                    },
                    {
                        "path": "tanks.freshWater.1.currentLevel",
                        "value": water_ratio2
                    }
                ]
            }
        ]
    }
    return delta


def read_and_push(ws):
    """Collect ADC samples over SAMPLE_DURATION seconds, compute medians, and push to SignalK."""
    log.info("Sampling sensors for %d seconds...", SAMPLE_DURATION)
    samples = collect_samples(SAMPLE_DURATION)

    # Compute median for each value
    voltage1 = statistics.median(samples['voltage1'])
    water1 = statistics.median(samples['water1'])
    water2 = statistics.median(samples['water2'])

    log.info(
        "Median values — Starter: %.2fV | Tank1: %.0f%% | Tank2: %.0f%% (from %d samples)",
        voltage1, water1, water2, len(samples['voltage1'])
    )

    delta = build_signalk_delta(voltage1, water1, water2)
    ws.send(json.dumps(delta))
    log.debug("Delta sent to SignalK")


# =============================================================================
# WebSocket Callbacks
# =============================================================================

def on_open(ws):
    """Called when WebSocket connection is established."""
    log.info("Connected to SignalK at %s", SK_WS_URL)
    log.info("Pushing updates every %d seconds", UPDATE_INTERVAL)


def on_message(ws, message):
    """Called when a message is received from SignalK (e.g. hello message)."""
    try:
        data = json.loads(message)
        if "name" in data:
            log.info("SignalK server: %s (v%s)", data.get("name"), data.get("version"))
    except json.JSONDecodeError:
        pass


def on_error(ws, error):
    """Called on WebSocket error."""
    log.error("WebSocket error: %s", error)


def on_close(ws, close_status, msg):
    """Called when WebSocket connection is closed."""
    log.warning("WebSocket connection closed (status=%s, msg=%s)", close_status, msg)


# =============================================================================
# Main
# =============================================================================

def setup_gpio():
    """Initialize GPIO pins for the MCP3208 and echo sensors."""
    GPIO.setmode(GPIO.BCM)

    # Echo sensor pins
    GPIO.setup(gpioTrigger1, GPIO.OUT)
    GPIO.setup(gpioEcho1, GPIO.IN)
    GPIO.setup(gpioTrigger2, GPIO.OUT)
    GPIO.setup(gpioEcho2, GPIO.IN)

    # MCP3208 ADC pins
    GPIO.setup(CLK, GPIO.OUT)
    GPIO.setup(DIN, GPIO.OUT)
    GPIO.setup(DOUT, GPIO.IN)
    GPIO.setup(CS, GPIO.OUT)

    # Set trigger to false
    GPIO.output(gpioTrigger1, False)

    log.info("GPIO initialized")


def cleanup_and_exit(signum=None, frame=None):
    """Clean up GPIO and exit gracefully."""
    log.info("Shutting down...")
    if not TESTING:
        GPIO.cleanup()
        log.info("GPIO cleaned up")
    sys.exit(0)


if __name__ == '__main__':
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)

    if not TESTING:
        setup_gpio()

    # Main loop with reconnection logic
    while True:
        try:
            log.info("Connecting to SignalK at %s ...", SK_WS_URL)
            ws = websocket.WebSocketApp(
                SK_WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )

            # We need to run the sensor loop in parallel with the WebSocket.
            # Use a simple approach: connect, then loop sending deltas.
            ws_connection = websocket.create_connection(SK_WS_URL)

            # Read and log the hello message
            hello = ws_connection.recv()
            hello_data = json.loads(hello)
            if "name" in hello_data:
                log.info("SignalK server: %s (v%s)", 
                         hello_data.get("name"), hello_data.get("version"))

            log.info("Connected! Pushing updates every %d seconds", UPDATE_INTERVAL)

            # Continuous sensor reading and push loop
            while True:
                read_and_push(ws_connection)
                time.sleep(UPDATE_INTERVAL)

        except (websocket.WebSocketException, ConnectionRefusedError, OSError) as e:
            log.error("Connection failed: %s", e)
            log.info("Retrying in 10 seconds...")
            time.sleep(10)

        except KeyboardInterrupt:
            cleanup_and_exit()
