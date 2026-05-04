from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum



class SessionType(str, Enum):
    detection = "detection"
    quiz = "quiz"
    manual = "manual"



class HistoryCreateRequest(BaseModel):
    user_id: int
    object_name_en: str = Field(..., min_length=1, max_length=100)
    object_name_vn: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    session_type: SessionType = SessionType.detection
    duration_seconds: Optional[float] = Field(None, ge=0)

    @field_validator("object_name_en")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip().lower()


class HistoryFilterRequest(BaseModel):
    user_id: int
    limit: int = Field(50, ge=1, le=200)
    skip: int = Field(0, ge=0)
    session_type: Optional[SessionType] = None
    object_name_en: Optional[str] = None   # lọc theo vật thể
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None

class HistoryItem(BaseModel):
    history_id: int
    object_name_en: str
    object_name_vn: str
    confidence: float
    session_type: SessionType
    repeat_count: int
    duration_seconds: Optional[float]
    timestamp: datetime
    last_seen_at: Optional[datetime]

    model_config = {"from_attributes": True}

class HistoryListResponse(BaseModel):
    success: bool = True
    history: List[HistoryItem]
    total_count: int
    skip: int
    limit: int

class ObjectStatItem(BaseModel):
    object_name_en: str
    object_name_vn: str
    total_encounters: int      # tổng số lần gặp
    avg_confidence: float      # confidence trung bình
    first_seen: datetime
    last_seen: datetime


class LearningSummary(BaseModel):
    user_id: int
    total_sessions: int          # tổng số bản ghi lịch sử
    unique_objects: int          # số loại vật thể khác nhau đã học
    total_duration_minutes: float
    most_seen_objects: List[ObjectStatItem]    # top 5 vật hay gặp nhất
    recent_objects: List[HistoryItem]          # 5 vật học gần nhất
    sessions_today: int


class HistorySummaryResponse(BaseModel):
    success: bool = True
    summary: LearningSummary



class HistoryDeleteResponse(BaseModel):
    success: bool = True
    deleted_count: int
    message: str