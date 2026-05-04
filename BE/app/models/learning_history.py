from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.models.base import Base
import enum


class LearningSessionType(str, enum.Enum):
    detection = "detection"
    quiz = "quiz"
    manual = "manual"


class LearningHistory(Base):
    __tablename__ = "learning_history"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    object_id = Column(Integer, ForeignKey("object_dictionary.object_id", ondelete="SET NULL"), nullable=True)

    # Snapshot tên tại thời điểm học
    object_name_en = Column(String(100), nullable=False)
    object_name_vn = Column(String(100), nullable=True)

    # Conf
    confidence = Column(Float, nullable=True)

    # Thông tin phiên học
    session_type = Column(Enum(LearningSessionType), default=LearningSessionType.detection, nullable=False)
    repeat_count = Column(Integer, default=1, nullable=False)
    duration_seconds = Column(Float, nullable=True)

    # Time
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="learning_histories", foreign_keys=[user_id])
    object_dict = relationship("ObjectDictionary", back_populates="learning_histories", foreign_keys=[object_id])
    quiz_results = relationship("QuizResult", back_populates="history", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LearningHistory #{self.history_id} user={self.user_id} obj={self.object_name_en} conf={self.confidence}>"