from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String

from .database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(
        Integer, default=lambda: int(datetime.now(timezone.utc).timestamp())
    )
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    interaction_count = Column(Integer, default=0)
    configuration_json = Column(String, default="")
    api_key = Column(String, default="")
    is_self_managed = Column(Boolean, default=False)
