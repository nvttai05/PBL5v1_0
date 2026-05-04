from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class QuizType(str, Enum):
    en_to_vn = "en_to_vn"
    vn_to_en = "vn_to_en"
    pronunciation = "pronunciation"

class QuizQuestion(BaseModel):
    question_index : int
    question_text : str
    options : List[str]
    correct_answer : str
    object_name_en : str
    object_name_vn : str
    pronunciation : Optional[str] = None
    audio_url : Optional[str] = None
    example_en : Optional[str] = None

class QuizGenerateRequest(BaseModel):
    user_id : int = 1
    quiz_type : QuizType = QuizType.en_to_vn
    limit : int = Field(5, ge=1, le=20, description="Số câu hỏi")
    objects : Optional[List[str]]= None  #ds cac vat lam quiz
    from_history : bool = True

class QuizSessionResponse(BaseModel):
    success: bool = True
    session_id : str
    quiz_type : QuizType
    questions: List[QuizQuestion]
    total: int
    generated_at: datetime

#submit
class AnswerItem(BaseModel):
    question_index : int
    user_answer: str
    time_taken_seconds: Optional[float] = None

class QuizSubmitRequest(BaseModel):
    user_id : int
    session_id : str
    quiz_type : QuizType = QuizType.en_to_vn
    answers: List[AnswerItem]
    total_time_seconds: Optional[float] = None

#result
class AnswerResultItem(BaseModel):
    question_index : int
    object_name_en : str
    object_name_vn : str
    pronunciation : Optional[str] = None
    question_text : str
    correct_answer : str
    user_answer : str
    is_correct : bool

class QuizResultResponse(BaseModel):
    success: bool = True
    quiz_id: int
    score: int
    total_questions: int
    score_percent: float
    passed: bool
    time_seconds: Optional[float]
    answers: List[AnswerResultItem]
    message: str
    
#history
class QuizHistoryItem(BaseModel):
    quiz_id: int
    quiz_type: QuizType
    score: int
    total_questions: int
    score_percent: float
    passed: bool
    timestamp: datetime
 
    model_config = {"from_attributes": True}

class QuizHistoryResponse(BaseModel):
    success: bool = True
    results: List[QuizHistoryItem]
    total_count: int

#dashboard
class QuizStatsResponse(BaseModel):
    success: bool = True
    user_id: int
    total_quizzes: int
    avg_score_percent: float
    best_score_percent: float
    total_answered: int
    total_correct: int
    accuracy_percent: float
    most_missed_objects: List[str]
