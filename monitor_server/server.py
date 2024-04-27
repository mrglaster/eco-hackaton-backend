import os
import bcrypt
import uvicorn
import random
import string
from fastapi import FastAPI, Request, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from monitor_server.modules.models.db_entities import Base, db_engine, Owner, Record

app = FastAPI()


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


def main():
    Base.metadata.create_all(db_engine)
    uvicorn.run(f"{os.path.basename(__file__)[:-3]}:app", log_level="info")


if __name__ == '__main__':
    main()
