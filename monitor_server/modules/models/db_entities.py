from sqlalchemy import create_engine, Column, Integer, String, Float, TIMESTAMP, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

db_engine = create_engine('sqlite:///service.db', echo=False)
Base = declarative_base()


class Owner(Base):
    __tablename__ = 'owners'

    id = Column(Integer, primary_key=True, autoincrement=True)
    login = Column(String(255), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    name = Column(String(255))
    last_name = Column(String(255))
    token = Column(String(255), nullable=False, unique=True)
    devices = relationship("Device", back_populates="owner")
    has_device = Column(Boolean, default=False)


class Device(Base):
    __tablename__ = 'devices'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    owner_id = Column(Integer, ForeignKey('owners.id'))

    owner = relationship("Owner", back_populates="devices")
    records = relationship("Record", back_populates="device")


class Record(Base):
    __tablename__ = 'records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey('devices.id'), nullable=False)
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    radioactivity = Column(Float, nullable=False)
    pm25 = Column(Float, nullable=False)
    pm10 = Column(Float, nullable=False)
    noisiness = Column(Float, nullable=False)
    time = Column(TIMESTAMP, nullable=False)

    device = relationship("Device", back_populates="records")
