from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from app.models.base import Base

class ObjectDictionary(Base):
    __tablename__ = 'object_dictionary'
    object_id = Column(Integer, primary_key=True, autoincrement=True)
    class_name_en = Column(String, nullable=False, unique=True)
    class_name_vn = Column(String, nullable=False)
    example_sentence_en = Column(Text)
    pronunciation_ipa = Column(String)
    audio_file_path = Column(String, nullable=True)

    # Relationships
    learning_histories = relationship("LearningHistory", back_populates="object_dict", foreign_keys="LearningHistory.object_id")