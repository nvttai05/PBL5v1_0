import json
from datetime import datetime
from sqlalchemy import Column, Integer, Float, Text, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from app.models.base import Base


class QuizResult(Base):
    __tablename__ = "quiz_results"

    quiz_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    history_id = Column(Integer, ForeignKey("learning_history.history_id", ondelete="SET NULL"), nullable=True)

    quiz_type = Column(String(20), default="en_to_vn", nullable=False)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False, default=0)
    score_percent = Column(Float, nullable=True)
    time_seconds = Column(Float, nullable=True)
    passed = Column(Boolean, default=False, nullable=False)
    answers_json = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    history = relationship("LearningHistory", back_populates="quiz_results", foreign_keys=[history_id])
    user = relationship("User", foreign_keys=[user_id])

    def set_answers(self, answers: list):
        self.answers_json = json.dumps(answers, ensure_ascii=False)

    def get_answers(self) -> list:
        if self.answers_json:
            try:
                return json.loads(self.answers_json)
            except Exception:
                return []
        return []

    def __repr__(self):
        return f"<QuizResult #{self.quiz_id} user={self.user_id} type={self.quiz_type} score={self.score_percent}%>"
