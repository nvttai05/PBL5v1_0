from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models.learning_history import LearningHistory, LearningSessionType
from app.models.object_dictionary import ObjectDictionary
from app.schemas.history import (
    HistoryItem,
    HistoryFilterRequest,
    LearningSummary,
    ObjectStatItem,
    SessionType,
)


class HistoryService:

    def create_or_update_history(
        self,
        db: Session,
        user_id: int,
        object_name_en: str,
        object_name_vn: str,
        confidence: float,
        session_type: str = "detection",
        duration_seconds: Optional[float] = None,
        merge_window_seconds: int = 120,
    ) -> LearningHistory:
        object_name_en = object_name_en.strip().lower()

        # 1. Đảm bảo object tồn tại trong từ điển
        obj = self._ensure_object_exists(db, object_name_en, object_name_vn)

        # 2. Kiểm tra bản ghi gần đây trong merge window
        cutoff = datetime.utcnow() - timedelta(seconds=merge_window_seconds)
        existing = (
            db.query(LearningHistory)
            .filter(
                LearningHistory.user_id == user_id,
                LearningHistory.object_name_en == object_name_en,
                LearningHistory.session_type == session_type,
                LearningHistory.timestamp >= cutoff,
            )
            .order_by(desc(LearningHistory.timestamp))
            .first()
        )

        if existing:
            # cập nhật
            existing.repeat_count += 1
            existing.last_seen_at = datetime.utcnow()
            if confidence is not None:
                n = existing.repeat_count
                existing.confidence = round(
                    (existing.confidence * (n - 1) + confidence) / n, 4
                )
            if duration_seconds:
                existing.duration_seconds = (existing.duration_seconds or 0) + duration_seconds
            db.commit()
            db.refresh(existing)
            return existing

        history = LearningHistory(
            user_id=user_id,
            object_id=obj.object_id if obj else None,
            object_name_en=object_name_en,
            object_name_vn=object_name_vn,
            confidence=round(confidence, 4) if confidence else None,
            session_type=session_type,
            duration_seconds=duration_seconds,
            repeat_count=1,
            timestamp=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        return history

    def create_history(
        self,
        db: Session,
        user_id: int,
        object_name_en: str,
        object_name_vn: str,
        confidence: float,
        duration_seconds: Optional[float] = None,
    ) -> LearningHistory:

        return self.create_or_update_history(
            db=db,
            user_id=user_id,
            object_name_en=object_name_en,
            object_name_vn=object_name_vn,
            confidence=confidence,
            session_type=LearningSessionType.detection,
            duration_seconds=duration_seconds,
        )


    def get_history(
        self,
        db: Session,
        user_id: int,
        limit: int = 50,
        skip: int = 0,
        session_type: Optional[str] = None,
        object_name_en: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[HistoryItem]:
        query = (
            db.query(LearningHistory)
            .filter(LearningHistory.user_id == user_id)
        )

        if session_type:
            query = query.filter(LearningHistory.session_type == session_type)
        if object_name_en:
            query = query.filter(
                LearningHistory.object_name_en.ilike(f"%{object_name_en.lower()}%")
            )
        if from_date:
            query = query.filter(LearningHistory.timestamp >= from_date)
        if to_date:
            query = query.filter(LearningHistory.timestamp <= to_date)

        records = (
            query.order_by(desc(LearningHistory.timestamp))
            .offset(skip)
            .limit(limit)
            .all()
        )

        return [self._to_item(h) for h in records]

    def get_history_by_filter(
        self,
        db: Session,
        req: HistoryFilterRequest,
    ) -> List[HistoryItem]:
        return self.get_history(
            db=db,
            user_id=req.user_id,
            limit=req.limit,
            skip=req.skip,
            session_type=req.session_type,
            object_name_en=req.object_name_en,
            from_date=req.from_date,
            to_date=req.to_date,
        )

    def get_total_count(self, db: Session, user_id: int) -> int:
        return (
            db.query(LearningHistory)
            .filter(LearningHistory.user_id == user_id)
            .count()
        )

    def get_history_by_id(
        self, db: Session, history_id: int, user_id: int
    ) -> Optional[LearningHistory]:
        return (
            db.query(LearningHistory)
            .filter(
                LearningHistory.history_id == history_id,
                LearningHistory.user_id == user_id,
            )
            .first()
        )


    def get_summary(self, db: Session, user_id: int) -> LearningSummary:
        total_sessions = self.get_total_count(db, user_id)

        unique_objects = (
            db.query(func.count(func.distinct(LearningHistory.object_name_en)))
            .filter(LearningHistory.user_id == user_id)
            .scalar()
            or 0
        )

        total_seconds = (
            db.query(func.sum(LearningHistory.duration_seconds))
            .filter(LearningHistory.user_id == user_id)
            .scalar()
            or 0
        )
        total_duration_minutes = round(total_seconds / 60, 2)

        top_rows = (
            db.query(
                LearningHistory.object_name_en,
                LearningHistory.object_name_vn,
                func.sum(LearningHistory.repeat_count).label("total_encounters"),
                func.avg(LearningHistory.confidence).label("avg_confidence"),
                func.min(LearningHistory.timestamp).label("first_seen"),
                func.max(LearningHistory.last_seen_at).label("last_seen"),
            )
            .filter(LearningHistory.user_id == user_id)
            .group_by(LearningHistory.object_name_en, LearningHistory.object_name_vn)
            .order_by(desc("total_encounters"))
            .limit(5)
            .all()
        )

        most_seen_objects = [
            ObjectStatItem(
                object_name_en=row.object_name_en,
                object_name_vn=row.object_name_vn or row.object_name_en,
                total_encounters=row.total_encounters or 0,
                avg_confidence=round(row.avg_confidence or 0.0, 3),
                first_seen=row.first_seen,
                last_seen=row.last_seen or row.first_seen,
            )
            for row in top_rows
        ]

        recent_objects = self.get_history(db=db, user_id=user_id, limit=5, skip=0)

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        sessions_today = (
            db.query(LearningHistory)
            .filter(
                LearningHistory.user_id == user_id,
                LearningHistory.timestamp >= today_start,
            )
            .count()
        )

        return LearningSummary(
            user_id=user_id,
            total_sessions=total_sessions,
            unique_objects=unique_objects,
            total_duration_minutes=total_duration_minutes,
            most_seen_objects=most_seen_objects,
            recent_objects=recent_objects,
            sessions_today=sessions_today,
        )


    def increase_repeat_count(self, db: Session, history_id: int) -> bool:
        record = db.query(LearningHistory).filter(
            LearningHistory.history_id == history_id
        ).first()
        if record:
            record.repeat_count += 1
            record.last_seen_at = datetime.utcnow()
            db.commit()
            return True
        return False

    def delete_history(
        self, db: Session, history_id: int, user_id: int
    ) -> bool:
        record = (
            db.query(LearningHistory)
            .filter(
                LearningHistory.history_id == history_id,
                LearningHistory.user_id == user_id,
            )
            .first()
        )
        if record:
            db.delete(record)
            db.commit()
            return True
        return False

    def delete_all_history(self, db: Session, user_id: int) -> int:
        count = (
            db.query(LearningHistory)
            .filter(LearningHistory.user_id == user_id)
            .count()
        )
        db.query(LearningHistory).filter(
            LearningHistory.user_id == user_id
        ).delete()
        db.commit()
        return count


    def _ensure_object_exists(
        self,
        db: Session,
        object_name_en: str,
        object_name_vn: str,
    ) -> Optional[ObjectDictionary]:
        obj = (
            db.query(ObjectDictionary)
            .filter(ObjectDictionary.class_name_en == object_name_en)
            .first()
        )
        if not obj:
            obj = ObjectDictionary(
                class_name_en=object_name_en,
                class_name_vn=object_name_vn or object_name_en,
                example_sentence_en=f"This is a {object_name_en}.",
            )
            db.add(obj)
            db.commit()
            db.refresh(obj)
        return obj

    def _to_item(self, h: LearningHistory) -> HistoryItem:
        return HistoryItem(
            history_id=h.history_id,
            object_name_en=h.object_name_en,
            object_name_vn=h.object_name_vn or h.object_name_en,
            confidence=round(h.confidence or 0.0, 3),
            session_type=SessionType(h.session_type) if h.session_type else SessionType.detection,
            repeat_count=h.repeat_count or 1,
            duration_seconds=h.duration_seconds,
            timestamp=h.timestamp,
            last_seen_at=h.last_seen_at,
        )

history_service = HistoryService()