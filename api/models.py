from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer
from geoalchemy2 import Geometry

from api import db

Base = declarative_base()


class StartPoint(Base):
    __tablename__ = 'start_point'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    point = Column(Geometry('POINT'))

    def __init__(self, url, result_all, result_no_stop_words):
        self.user_id = user_id
        self.point = point

    def __repr__(self):
        return f'<id {self.id}>'
