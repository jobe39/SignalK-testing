#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, request
from flask_restful import Resource, Api
from json import dumps
#from flask.ext.jsonpify import jsonify

# import required modules
import time
import csv
import RPi.GPIO as GPIO
import random
import sys
import os
import re
import socket
from Adafruit_BMP085 import BMP085

#redirect print to file
#f = open('/var/log/solva_server.log', 'w')
#sys.stdout = f
#sys.stderr = f
print("-" * 25)
print("Solva Server started")
print("-" * 25)

#Suppress flask http logging
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
api = Api(app)

HIGH = True  # 3,3V Pegel (high)
LOW  = False # 0V Pegel (low)

TESTING = 0
#TESTING = 0

# define file names
tSensorPath = "/sys/bus/w1/devices/10-000802b3c6af/w1_slave"

#define constants for watertanks
waterMax1=2
waterMin1=20
waterMax2=2
waterMin2=33

# define GPIO pins for echo sensors
gpioTrigger1 = 23
gpioEcho1    = 18
gpioTrigger2 = 25
gpioEcho2    = 24

#UDP Definitions
UDP_IP = "127.0.0.1"
UDP_PORT = 5005


# define GPIO pins for AD converter
CLK     = 6 # Clock
DOUT    = 13  # Digital out
DIN     = 19 # Digital in
CS      = 26  # Chip-Select

class Data(Resource):
    def get(self):
      if TESTING:
        bmp = "TEST"
      else:
        bmp = BMP085(0x77)

      waterData1 = self.measureWaterLevel(7, CLK, DIN, DOUT, CS,2)
      #print ("waterData1: %s" % waterData1)

      waterData2 = self.measureWaterLevel(6, CLK, DIN, DOUT, CS,2) 
      #print ("waterData2: %s" % waterData2)

      # Batterie 1
      voltageData1 = self.measureVoltage(5, CLK, DIN, DOUT, CS,1)
      #print ("voltageData1: %s" % voltageData1)
      # Batterie 2
      voltageData2 = self.measureVoltage(4, CLK, DIN, DOUT, CS,1)
      #print ("voltageData2: %s" % voltageData2)
      # Temperatur
      temperatureData = self.measureTemperature(bmp)
      #print ("temperatureData: %s" % temperatureData)
      # Luftdruck
      pressureData = self.measureBarometricPressure(bmp)
      #print ("pressureData: %s" % pressureData)

      return {'waterData1': waterData1, 'waterData2':waterData2, 'voltageData1':voltageData1, 'voltageData2':voltageData2, 'temperature':temperatureData, 'pressure':pressureData} 

    def getCurrentHour():
      os.environ['TZ'] = 'Europe/Vienna'
      time.tzset()  
      return time.strftime('%H') + ':00:00'

    def getCurrentDay():
      os.environ['TZ'] = 'Europe/Vienna'
      time.tzset()
      return time.strftime('%d/%m/%Y')

    def ConvertVolts(self,data,places,type):
      volts = (data * 3.3) / float(4095) #convert to volt
      # now lets calculate the real voltage based on the voltage divider
      if(type==1):
        volts = volts*(1800+470)/470
        volts = round(volts,places)
      else:
        waterlevel = 0;
        r2 = 180 * volts/(5-volts)
        #print ("R2 = %s" % r2)
        level = (r2/170) * 100
        # return level
        if (level >=90):
          waterlevel = 100
        elif (level >= 80):
          # Value between 2.25 and 1.9
          # Note: remove constant
          waterlevel = 90
        elif (level >= 70):
          # Value between 2.25 and 1.9
          # Note: remove constant
          waterlevel = 80
        elif (level >= 60):
          # Value between 2.25 and 1.9
          # Note: remove constant
          waterlevel = 70
        elif (level >= 50):
          # Value between 2.25 and 1.9
          # Note: remove constant
          waterlevel = 60
        elif (level >= 40):
          # Value between 2.25 and 1.9
          # Note: remove constant
          waterlevel = 50
        elif (level >= 30):
          # Value between 2.25 and 1.9
          # Note: remove constant
          waterlevel = 40
        elif (level >= 20):
          # Value between 2.25 and 1.9
          # Note: remove constant
          waterlevel = 30
        elif (level >= 10):
          # Value between 2.25 and 1.9
          # Note: remove constant
          waterlevel = 20
        elif (level >= 5):
          # Value between 2.25 and 1.9
          # Note: remove constant
          waterlevel = 10
        else:
          # Value between 2.25 and 1.9
          # Note: remove constant
          waterlevel = 0
        volts = waterlevel
        #print(waterlevel)
      volts = round(volts,places)
      return volts 


    def getAnalogData(self,adCh, CLKPin, DINPin, DOUTPin, CSPin,type):
      # Pegel definieren
      GPIO.output(CSPin,   HIGH)    
      GPIO.output(CSPin,   LOW)
      GPIO.output(CLKPin, LOW)
      
      cmd = adCh
      cmd |= 0b00011000 # Kommando zum Abruf der Analogwerte des Datenkanals adCh
  
      # Bitfolge senden
      for i in range(5):
        if (cmd & 0x10): # 4. Bit prnd mit 0 anfangen
          GPIO.output(DINPin, HIGH)
        else:
          GPIO.output(DINPin, LOW)
          # Clocksignal negative Flanke erzeugen   
        GPIO.output(CLKPin, HIGH)
        GPIO.output(CLKPin, LOW)
        cmd <<= 1 # Bitfolge eine Position nach links verschieben
    
      # Datenabruf
      adchvalue = 0 # Wert auf 0 zurzen
      for i in range(13):
        GPIO.output(CLKPin, HIGH)
        GPIO.output(CLKPin, LOW)
        adchvalue <<= 1 # 1 Postition nach links schieben
        if(GPIO.input(DOUTPin)):
          adchvalue |= 0x01
      time.sleep(0.5)
      adchvalue=self.ConvertVolts(adchvalue,2,type)
      #print ("Measured Voltage: %s" %adchvalue)
      return adchvalue

    # function: read and parse sensor data file
    def measureTemperature(self,bmp):
      if TESTING:
        value = random.uniform(20,33)
      else:
        value = bmp.readTemperature()
      return value

	
    # function: read and parse sensor data file
    def measureBarometricPressure(self,bmp):
      value = 0.0
      if TESTING:
        value = random.uniform(990,1100)
      else:
        value = bmp.readPressure()
        #print ("Pressure: value from BMP180 is: %s" % value)
        if value > 0:
          value = value / 100.0
          #print("Calc val: %s" % value)
        else:
          print ("ERROR: Could not read barometric pressure")
      return value

    def measureWaterLevel(self, adCh, clkPin, dinPin, doutPin, csPin,type):
      level = 0
      if TESTING:
        level = random.uniform(0,100)
      else:
        for i in range(3):
          level = level + self.getAnalogData(adCh, clkPin, dinPin, doutPin, csPin,type)
          #print(level)
        level = level / 3
      return level

    def measureVoltage(self,adCh, clkPin, dinPin, doutPin, csPin,type):
      level = 0
      if TESTING:
        level = random.uniform(11,14)
      else:
        for i in range(3):
          level = level + self.getAnalogData(adCh, clkPin, dinPin, doutPin, csPin,type)
        level = level / 3
      return level
  


api.add_resource(Data, '/data') # Route_1


      
if __name__ == '__main__':
  if not TESTING:
    
      # use GPIO pin numbering convention
      GPIO.setmode(GPIO.BCM)
      
      # set up GPIO pins
      GPIO.setup(gpioTrigger1, GPIO.OUT)
      GPIO.setup(gpioEcho1, GPIO.IN)
      GPIO.setup(gpioTrigger2, GPIO.OUT)
      GPIO.setup(gpioEcho2, GPIO.IN)
      GPIO.setup(CLK, GPIO.OUT)
      GPIO.setup(DIN, GPIO.OUT)
      GPIO.setup(DOUT, GPIO.IN)
      GPIO.setup(CS,   GPIO.OUT)
          
          
      # set trigger to false
      GPIO.output(gpioTrigger1, False)
          
  app.run(port=5002, threaded=True)
  # reset GPIO settings if user pressed Ctrl+C
  print("Execution stopped by user")
  if not TESTING:
      GPIO.cleanup()
