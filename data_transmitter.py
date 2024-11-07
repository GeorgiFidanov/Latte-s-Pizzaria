import serial
import requests
import json
import time

ser = serial.Serial("COM5", baudrate=9600, timeout=1)
url = "http://localhost:5000/admin"  # Endpoint for Flask server

while True:
    if ser.in_waiting > 0:
        data = ser.readline().decode().strip()
        print(f"Received data from Arduino: {data}")  # Debugging received data

        try:
            sensor_data = json.loads(data)
            if sensor_data.get("message") == "pizza":
                print("Preparing to send ready notification to server...")
                response = requests.post(url, json=sensor_data)
                if response.status_code == 200:
                    print("Ready notification sent successfully.")
                else:
                    print("Failed to send notification:", response.text)
            else:
                print("Received data is not a 'pizza' status.")

        except json.JSONDecodeError:
            print("Error decoding JSON:", data)

    time.sleep(1)
