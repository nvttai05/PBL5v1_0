import json
import random
import uuid
from datetime import datetime
from typing import List, Optional, Dict

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models.learning_history import LearningHistory
from app.models.object_dictionary import ObjectDictionary
from app.models.quiz_result import QuizResult
from app.schemas.quiz import (
    QuizGenerateRequest, QuizSessionResponse, QuizQuestion,
    QuizSubmitRequest, QuizResultResponse, AnswerResultItem,
    QuizHistoryItem, QuizHistoryResponse, QuizStatsResponse,
    QuizType,
)

PASS_THRESHOLD = 60.0

# Lưu câu hỏi tạm giữa generate và submit
_session_store: Dict[str, List[QuizQuestion]] = {}

FALLBACK_OBJECTS = [
    "cat", "dog", "book", "chair", "bottle",
    "cup", "laptop", "clock", "apple", "banana",
    "car", "bird", "backpack", "keyboard", "cell phone"
]


class QuizService:

    def generate_quiz(self, db: Session, data: QuizGenerateRequest) -> QuizSessionResponse:
        pool = self._build_pool(db, data)

        # Bổ sung fallback nếu pool < 4
        if len(pool) < 4:
            extra_names = [n for n in FALLBACK_OBJECTS
                           if n not in [o.class_name_en for o in pool]]
            for name in extra_names:
                obj = db.query(ObjectDictionary).filter(
                    ObjectDictionary.class_name_en == name
                ).first()
                if obj:
                    pool.append(obj)
                if len(pool) >= 4:
                    break

        if not pool:
            raise ValueError("Không đủ dữ liệu để tạo quiz. Hãy học thêm các từ mới!")

        selected = random.sample(pool, min(data.limit, len(pool)))
        questions: List[QuizQuestion] = []
        for idx, obj in enumerate(selected):
            q = self._make_question(idx=idx, obj=obj, pool=pool, quiz_type=data.quiz_type)
            questions.append(q)

        session_id = str(uuid.uuid4())
        _session_store[session_id] = questions

        return QuizSessionResponse(
            success=True,
            session_id=session_id,
            quiz_type=data.quiz_type,
            questions=questions,
            total=len(questions),
            generated_at=datetime.utcnow(),
        )

    def submit_quiz(self, db: Session, data: QuizSubmitRequest) -> QuizResultResponse:
        questions = _session_store.pop(data.session_id, None)
        if not questions:
            raise ValueError("Session không hợp lệ hoặc đã hết hạn. Hãy tạo quiz mới.")

        answer_map = {a.question_index: a.user_answer.strip() for a in data.answers}
        score = 0
        answer_results: List[AnswerResultItem] = []

        for q in questions:
            user_ans = answer_map.get(q.question_index, "")
            is_correct = user_ans.strip().lower() == q.correct_answer.strip().lower()
            if is_correct:
                score += 1

            answer_results.append(AnswerResultItem(
                question_index=q.question_index,  
                object_name_en=q.object_name_en,
                object_name_vn=q.object_name_vn,
                pronunciation=q.pronunciation,
                question_text=q.question_text,
                correct_answer=q.correct_answer,
                user_answer=user_ans,
                is_correct=is_correct,
            ))

        total   = len(questions)
        percent = round((score / total) * 100, 2) if total > 0 else 0.0
        passed  = percent >= PASS_THRESHOLD

        quiz_result = QuizResult(
            user_id=data.user_id,
            quiz_type=data.quiz_type.value,
            total_questions=total,
            correct_answers=score,
            score_percent=percent,
            time_seconds=data.total_time_seconds,
            passed=passed,
            timestamp=datetime.utcnow(),
        )
        quiz_result.set_answers([ar.model_dump() for ar in answer_results])
        db.add(quiz_result)

        # Cập nhật repeat_count trong lịch sử học
        for q in questions:
            record = (
                db.query(LearningHistory)
                .filter(
                    LearningHistory.user_id == data.user_id,
                    LearningHistory.object_name_en == q.object_name_en,
                )
                .order_by(desc(LearningHistory.timestamp))
                .first()
            )
            if record:
                record.repeat_count += 1
                record.last_seen_at = datetime.utcnow()

        db.commit()
        db.refresh(quiz_result)

        return QuizResultResponse(
            success=True,
            quiz_id=quiz_result.quiz_id,
            score=score,
            total_questions=total,
            score_percent=percent,
            passed=passed,
            time_seconds=data.total_time_seconds,
            answers=answer_results,
            message=self._feedback(percent),
        )

    def get_history(
        self, db: Session, user_id: int,
        limit: int = 20, skip: int = 0,
        quiz_type: Optional[str] = None,
    ) -> QuizHistoryResponse:
        query = db.query(QuizResult).filter(QuizResult.user_id == user_id)
        if quiz_type:
            qt = quiz_type.value if hasattr(quiz_type, "value") else quiz_type
            query = query.filter(QuizResult.quiz_type == qt)
        total = query.count()
        rows = query.order_by(desc(QuizResult.timestamp)).offset(skip).limit(limit).all()
        items = [
            QuizHistoryItem(
                quiz_id=r.quiz_id,
                quiz_type=r.quiz_type,
                score=r.correct_answers,
                total_questions=r.total_questions,
                score_percent=r.score_percent or 0.0,
                passed=r.passed,
                timestamp=r.timestamp,
            )
            for r in rows
        ]
        return QuizHistoryResponse(success=True, results=items, total_count=total)

    def get_result_detail(
        self, db: Session, quiz_id: int, user_id: int
    ) -> Optional[QuizResultResponse]:
        row = (
            db.query(QuizResult)
            .filter(QuizResult.quiz_id == quiz_id, QuizResult.user_id == user_id)
            .first()
        )
        if not row:
            return None
        answers = [AnswerResultItem(**a) for a in row.get_answers()]
        return QuizResultResponse(
            success=True,
            quiz_id=row.quiz_id,
            score=row.correct_answers,
            total_questions=row.total_questions,
            score_percent=row.score_percent or 0.0,
            passed=row.passed,
            time_seconds=row.time_seconds,
            answers=answers,
            message=self._feedback(row.score_percent or 0.0),
        )

    def get_stats(self, db: Session, user_id: int) -> QuizStatsResponse:
        total_quizzes = db.query(QuizResult).filter(QuizResult.user_id == user_id).count()
        agg = (
            db.query(
                func.avg(QuizResult.score_percent).label("avg_score"),
                func.max(QuizResult.score_percent).label("max_score"),
                func.sum(QuizResult.correct_answers).label("total_correct"),
                func.sum(QuizResult.total_questions).label("total_questions"),
            )
            .filter(QuizResult.user_id == user_id)
            .first()
        )
        total_answers = int(agg.total_questions or 0)
        total_correct = int(agg.total_correct or 0)
        accuracy = round((total_correct / total_answers) * 100, 1) if total_answers > 0 else 0.0

        wrong_count: Dict[str, int] = {}
        for r in db.query(QuizResult).filter(QuizResult.user_id == user_id).all():
            for ans in r.get_answers():
                if not ans.get("is_correct", True):
                    obj = ans.get("object_name_en", "unknown")
                    wrong_count[obj] = wrong_count.get(obj, 0) + 1
        most_missed = sorted(wrong_count, key=wrong_count.get, reverse=True)[:5]

        return QuizStatsResponse(
            success=True,
            user_id=user_id,
            total_quizzes=total_quizzes,
            avg_score_percent=round(float(agg.avg_score or 0), 1),
            best_score_percent=round(float(agg.max_score or 0), 1),
            total_answered=total_answers,
            total_correct=total_correct,
            accuracy_percent=accuracy,
            most_missed_objects=most_missed,
        )

    def _build_pool(self, db: Session, data: QuizGenerateRequest) -> List[ObjectDictionary]:
        if data.objects:
            result = []
            for name in data.objects:
                obj = db.query(ObjectDictionary).filter(
                    ObjectDictionary.class_name_en == name.lower().strip()
                ).first()
                if obj:
                    result.append(obj)
            return result

        if data.from_history:
            rows = (
                db.query(
                    LearningHistory.object_name_en,
                    func.sum(LearningHistory.repeat_count).label("total_repeats"),
                )
                .filter(LearningHistory.user_id == data.user_id)
                .group_by(LearningHistory.object_name_en)
                .order_by(desc("total_repeats"))
                .limit(20)
                .all()
            )
            if rows:
                names = [r[0] for r in rows]
                objects = (
                    db.query(ObjectDictionary)
                    .filter(ObjectDictionary.class_name_en.in_(names))
                    .all()
                )
                if objects:
                    return objects

        return db.query(ObjectDictionary).limit(60).all()

    def _make_question(
        self, idx: int, obj: ObjectDictionary,
        pool: List[ObjectDictionary], quiz_type: str,
    ) -> QuizQuestion:
        distractors = [o for o in pool if o.class_name_en != obj.class_name_en]
        if len(distractors) < 3:
            distractors = distractors * 3
        wrong = random.sample(distractors, 3)

        if quiz_type == QuizType.en_to_vn:
            question_text  = f"Từ '{obj.class_name_en}' trong tiếng Việt là gì?"
            correct_answer = obj.class_name_vn
            options = [w.class_name_vn for w in wrong] + [correct_answer]

        elif quiz_type == QuizType.vn_to_en:
            question_text  = f"Từ '{obj.class_name_vn}' trong tiếng Anh là gì?"
            correct_answer = obj.class_name_en
            options = [w.class_name_en for w in wrong] + [correct_answer]

        elif quiz_type == QuizType.pronunciation:
            ipa = obj.pronunciation_ipa or f"/{obj.class_name_en}/"  # ✅ đúng tên field
            question_text  = f"Cách phát âm của '{obj.class_name_en}' là gì?"
            correct_answer = ipa
            options = [
                w.pronunciation_ipa if w.pronunciation_ipa else f"/{w.class_name_en}/"  # ✅
                for w in wrong
            ] + [correct_answer]

        else:
            question_text  = f'"{obj.class_name_en.capitalize()}" nghĩa là gì?'
            correct_answer = obj.class_name_vn
            options = [w.class_name_vn for w in wrong] + [correct_answer]

        random.shuffle(options)

        return QuizQuestion(
            question_index=idx,
            question_text=question_text,
            options=options,
            correct_answer=correct_answer,
            object_name_en=obj.class_name_en,
            object_name_vn=obj.class_name_vn,
            pronunciation=obj.pronunciation_ipa,        # ✅ sửa obj.pronunciation → pronunciation_ipa
            audio_url=obj.audio_file_path,              # ✅ sửa obj.audio_url → audio_file_path
            example_en=obj.example_sentence_en,         # ✅ sửa obj.example_en → example_sentence_en
        )

    @staticmethod
    def _feedback(pct: float) -> str:
        if pct == 100:
            return "🎉 Xuất sắc! Bạn trả lời đúng tất cả câu hỏi!"
        elif pct >= 80:
            return "👏 Rất tốt! Hãy tiếp tục phát huy nhé!"
        elif pct >= 60:
            return "👍 Khá tốt! Ôn lại các từ sai để cải thiện hơn."
        elif pct >= 40:
            return "📚 Cần cố gắng thêm! Xem lại lịch sử học nhé."
        else:
            return "💪 Đừng nản lòng! Học lại từ đầu và thử lại nhé."


quiz_service = QuizService()