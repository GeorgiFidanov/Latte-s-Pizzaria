import serial
import requests
import json
import time


ser = serial.Serial("COM8", baudrate=9600, timeout=1)
url = ""

while True:
    # Check how many characters are in the serial buffer
    if ser.in_waiting > 0:
        # Read the byte array, decode it to a string, and remove newline characters
        data = ser.readline().decode().strip()

        try:
            # Parse the JSON-like data string
            sensor_data = json.loads(data)

            # Send the data to the Flask server
            response = requests.post(url, json=sensor_data)

            # Check response status
            if response.status_code == 200:
                print("Data sent successfully:", sensor_data)
            else:
                print("Failed to send data:", response.text)

        except json.JSONDecodeError:
            print("Error decoding JSON:", data)

    time.sleep(1)  # Sleep briefly to avoid overwhelming the serial buffer



# This file will be changed