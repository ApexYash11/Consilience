from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from database.connection import init_db
from database.connection import _engine
from database.schema import Base

class User(Base):
      __tablename__ = "users"
      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      email = Column(String, unique=True, nullable=False)
      hashed_password = Column(String, nullable=False)
      subscription_tier = Column(String, default="free")
      is_active = Column(Boolean, default=True)
      created_at = Column(TIMESTAMP, server_default=func.now())