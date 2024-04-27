import json
import random
from datetime import datetime

import requests

import paho.mqtt.publish as publish


#
# publish.single("ecohack_kt315/register", "register", hostname="broker.emqx.io")
# publish.single("ecohack_kt315/data/", "DATA", hostname="broker.emqx.io")
# publish.single("ecohack_kt315/register", "register", hostname="broker.emqx.io")
# publish.single("ecohack_kt315/data/", "DATA", hostname="broker.emqx.io")


def create_user(server_ip, server_port):
    login = f"user-{random.randint(0, 10000)}"
    password = "password"
    name = "Ivan"
    last_name = "Ivanov"
    request_json = {
        "login": login,
        "password": password,
        "name": name,
        "last_name": last_name
    }
    url = f"http://{server_ip}:{server_port}/user/register"
    response = requests.post(url, json=request_json)
    if response.status_code == 200:
        json_response = response.json()
        return json_response["token"]
    return None


def register_device(token):
    lat = random.uniform(10.5, 75.5)
    lon = random.uniform(10.5, 75.5)
    device_name = f"device-iot-test-{random.randint(1, 10000)}"
    request_json = {
        "owner_token": token,
        "device_name": device_name,
        "device_geo": [lon, lat]
    }
    publish.single("ecohack_kt315/register", payload=json.dumps(request_json), hostname="broker.emqx.io")
    return device_name


def send_data(device_name):
    temperature = round(random.uniform(0, 50), 2)  # Random temperature between 0 and 50
    humidity = round(random.uniform(0, 100), 2)  # Random humidity between 0 and 100
    radioactivity = round(random.uniform(0, 1000), 2)  # Random radioactivity between 0 and 1000
    pm25 = round(random.uniform(0, 100), 2)  # Random PM2.5 between 0 and 100
    pm10 = round(random.uniform(0, 100), 2)  # Random PM10 between 0 and 100
    noisiness = round(random.uniform(0, 100), 2)  # Random noisiness between 0 and 100
    timestamp = datetime.now().isoformat()
    payload = {
        "device_name": device_name,
        "temperature": temperature,
        "humidity": humidity,
        "radioactivity": radioactivity,
        "pm25": pm25,
        "pm10": pm10,
        "noisiness": noisiness,
        "timestamp": timestamp
    }
    publish.single("ecohack_kt315/data", payload=json.dumps(payload), hostname="broker.emqx.io")


def main():
    token = create_user('127.0.0.1', 8000)
    name_a = register_device(token)
    name_b = register_device(token)
    name_c = register_device(token)
    send_data(name_a)
    send_data(name_b)
    send_data(name_c)
    send_data(name_a)


if __name__ == '__main__':
    main()
