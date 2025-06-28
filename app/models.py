from abc import ABC
import sqlalchemy
from sqlalchemy import create_engine

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import List, Optional
from sqlalchemy import String, ForeignKey, DateTime, DECIMAL, Integer, BigInteger, LargeBinary
from decimal import Decimal
from datetime import datetime
import os
import redis
from constants import UTC


engine = create_engine(f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@{os.environ['POSTGRES_HOST']}/{os.environ['POSTGRES_DB']}")
my_redis = redis.Redis(host='redis', port=6379, db=0)


class Base(DeclarativeBase):
    pass

class GuideEntry(Base):
    __tablename__ = 'guide_entries'
    # def __init__(self, start: datetime.datetime, end: datetime.datetime, name: str, description=None, picture=None):
    #     """
    #     Initializes a GuideEntry with start and end times, name, description, and picture.
        
    #     :param start: The start time of the entry.
    #     :param end: The end time of the entry.
    #     :param name: The name of the entry.
    #     :param description: Optional description of the entry.
    #     :param picture: Optional picture URL for the entry.
    #     """
    #     self.start = start
    #     self.end = end
    #     self.name = name
    #     self.description = description
    #     self.picture = picture
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(), nullable=False)
    start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    name: Mapped[str] = mapped_column(String(), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(), nullable=True)
    picture: Mapped[Optional[str]] = mapped_column(String(), nullable=True)
    updated: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    __indexes__ = (
        sqlalchemy.Index('idx_channel'), 'channel'
    )
    __constraints__ = (
        sqlalchemy.CheckConstraint(
            'start <= end',
            name='check_start_before_end'
        ),
    )

Base.metadata.create_all(engine)