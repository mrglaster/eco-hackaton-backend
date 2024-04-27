import asyncio
import json
import logging
import os
import time
import bcrypt
import uvicorn
import random
import string
import threading
from fastapi import FastAPI, Request, HTTPException
from fastapi_mqtt import MQTTConfig, FastMQTT
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from monitor_server.modules.models.db_entities import Base, db_engine, Owner, Record, Device
from datetime import datetime, timedelta

app = FastAPI()
mqtt_config = MQTTConfig(
    host="broker.emqx.io",
)
fast_mqtt = FastMQTT(config=mqtt_config)
fast_mqtt.init_app(app)


@fast_mqtt.subscribe("ecohack_kt315/register/#")
async def register_device(client, topic, payload, qos, properties):
    payload_json = json.loads(payload.decode())
    try:
        owner_token = payload_json["owner_token"]
        device_name = payload_json["device_name"]
        device_geo = payload_json["device_geo"]
        with sessionmaker(bind=db_engine)() as session:
            owner = session.query(Owner).filter(Owner.token == owner_token).first()
            if owner is not None and device_name and len(device_geo) == 2:
                owner.has_device = True
                new_device = Device(name=device_name, latitude=device_geo[1], longitude=device_geo[0],
                                    owner_id=owner.id)
                session.add(new_device)
                session.commit()
                logging.info(f"[Register] New device has been added {time.time()}")
            else:
                logging.warning(f"[Register] Invalid register request! {time.time()}")
    except:
        logging.warning(f"[Register] Invalid register request! {time.time()}")


@fast_mqtt.subscribe("ecohack_kt315/data/#")
async def collect_data(client, topic, payload, qos, properties):
    device_name = ""
    try:
        payload_json = json.loads(payload.decode())
        device_name = payload_json["device_name"]
        temperature = payload_json["temperature"]
        humidity = payload_json["humidity"]
        radioactivity = payload_json["radioactivity"]
        pm25 = payload_json["pm25"]
        pm10 = payload_json["pm10"]
        noisiness = payload_json["noisiness"]
        timestamp = payload_json["timestamp"]
        with sessionmaker(bind=db_engine)() as session:
            device = session.query(Device).filter(Device.name == device_name).first()
            if device is not None:
                record = Record(device_id=device.id, temperature=temperature, humidity=humidity,
                                radioactivity=radioactivity, pm25=pm25, pm10=pm10, noisiness=noisiness,
                                time=datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f"))
                session.add(record)
                device.is_active = True
                session.commit()
    except:
        logging.error(f"[Data] invalid data from {device_name}")


@app.post("/user/register")
async def register_user(info: Request):
    request_json = await info.json()
    try:
        login = request_json["login"]
        password = request_json["password"]
        name = request_json["name"]
        last_name = request_json["last_name"]
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        with sessionmaker(bind=db_engine)() as session:
            if session.query(Owner).filter(Owner.login == login).first():
                raise HTTPException(status_code=400, detail="There is a user with such nickname!")
            token = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(50))
            new_owner = Owner(login=login, password=hashed_password, name=name, last_name=last_name, token=token)
            session.add(new_owner)
            session.commit()
            return {"token": token}
    except KeyError:
        raise HTTPException(status_code=400, detail="Not all required fields were found!")


@app.post("/user/login")
async def login_user(info: Request):
    request_json = await info.json()
    try:
        login = request_json["login"]
        password = request_json["password"]
        with sessionmaker(bind=db_engine)() as session:
            potential_user = session.query(Owner).filter(Owner.login == login).first()
            if potential_user is not None and bcrypt.checkpw(password.encode('utf-8'), potential_user.password):
                token = potential_user.token
                return {"token": token}
            raise HTTPException(status_code=400, detail="Invalid credentials")
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid credentials")


@app.post("/stations/data")
async def get_data(info: Request):
    request_json = await info.json()
    try:
        token = request_json["token"]
        with sessionmaker(bind=db_engine)() as session:
            potential_user = session.query(Owner).filter(Owner.token == token).first()
            if potential_user is None:
                raise HTTPException(status_code=400, detail="Invalid token!")
            if not potential_user.has_device:
                raise HTTPException(status_code=403, detail="Register device first do get access to the map")
            latest_records = session.query(Record.device_id,
                                           func.max(Record.time).label('max_time')). \
                group_by(Record.device_id).subquery()

            query = session.query(Record). \
                join(latest_records,
                     (Record.device_id == latest_records.c.device_id) &
                     (Record.time == latest_records.c.max_time)). \
                order_by(Record.device_id).all()
            json_results = []
            for record in query:
                json_result = {
                    "lon": record.device.longitude,
                    "lat": record.device.latitude,
                    "temperature": record.temperature,
                    "humidity": record.humidity,
                    "radioactivity": record.radioactivity,
                    "pm25": record.pm25,
                    "pm10": record.pm10,
                    "noisiness": record.noisiness
                }
                json_results.append(json_result)
            return {"data": json_results}
    except:
        raise HTTPException(status_code=400, detail="Invalid token")


@asyncio.coroutine
def check_device_status():
    while True:
        with sessionmaker(bind=db_engine)() as session:
            devices = session.query(Device).filter_by(is_active=True).all()
            for device in devices:
                last_record = session.query(Record).filter_by(device_id=device.id).order_by(Record.time.desc()).first()
                if last_record:
                    time_difference = datetime.now() - last_record.time
                    if time_difference > timedelta(seconds=300):
                        print(f"[Activity check] Device {device.name} is still inactive after 5min of waiting!")
                        device.is_active = False
            session.commit()
        yield from asyncio.sleep(300)


def loop_in_thread(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_device_status())


@app.post("/user/devices")
async def get_user_stations(info: Request):
    request_json = await info.json()
    try:
        token = request_json["token"]
        with sessionmaker(bind=db_engine)() as session:
            potential_user = session.query(Owner).filter(Owner.token == token).first()
            if potential_user is not None:
                if potential_user.has_device:
                    devices = potential_user.devices
                    devices_array = []
                    for device in devices:
                        devices_array.append({"name": device.name, "longitude": device.longitude,
                                              "latitude": device.latitude, "is_active": device.is_active})
                    return {"devices": devices_array}
                return {"devices": []}
            raise HTTPException(status_code=400, detail="Invalid token")
    except:
        raise HTTPException(status_code=400, detail="Invalid token")


def main():
    Base.metadata.create_all(db_engine)
    loop = asyncio.get_event_loop()
    t = threading.Thread(target=loop_in_thread, args=(loop,))
    t.start()
    uvicorn.run(f"{os.path.basename(__file__)[:-3]}:app", log_level="info")

if __name__ == '__main__':
    main()
