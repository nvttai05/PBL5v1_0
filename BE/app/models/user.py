from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.models.base import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="student")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    learning_histories = relationship("LearningHistory", back_populates="user", foreign_keys="LearningHistory.user_id")

    def __repr__(self):
        return f"<User {self.username}>"