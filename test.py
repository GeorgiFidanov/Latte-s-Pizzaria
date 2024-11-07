import requests

url = "http://localhost:5000/admin"  
data = {"status": "ready"}

try:
    response = requests.post(url, json=data)
    if response.status_code == 200:
        print("POST request to /notify_ready successful. Flask response:", response.text)
    else:
        print("POST request failed with status code:", response.status_code)
except Exception as e:
    print("Error during POST request:", e)

#test for arduino endpoint