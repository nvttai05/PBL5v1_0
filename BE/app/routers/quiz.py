from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
 
from app.core.database import get_db
from app.schemas.quiz import (
    QuizGenerateRequest, QuizSessionResponse,
    QuizSubmitRequest, QuizResultResponse,
    QuizHistoryResponse, QuizStatsResponse, QuizType,
)
from app.services.quiz_service import quiz_service

router = APIRouter(prefix="/api/v1/quiz", tags=["Quiz"])

@router.post(
    "/generate",
    response_model=QuizSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo bộ câu hỏi quiz",
    description="",
)
async def generate_quiz(
    body: QuizGenerateRequest,
    db: Session = Depends(get_db)):
    try:
        return quiz_service.generate_quiz(db=db, data=body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post(
    "/submit",
    response_model=QuizResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Nộp kết quả quiz",
    description="",
)
async def submit_quiz(
    body: QuizSubmitRequest,
    db: Session = Depends(get_db)):
    try:
        return quiz_service.submit_quiz(db=db, data=body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/history",
    response_model=QuizHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Lấy lịch sử quiz",
    description="",
)
async def get_quiz_history(
    db: Session = Depends(get_db),
    user_id: int = Query(...),
    limit: int = Query(20),
    skip: int = Query(0),
    quiz_type: Optional[str] = Query(None)
):
    try:
        return quiz_service.get_history(
            db=db,
            user_id=user_id,
            limit=limit,
            skip=skip,
            quiz_type=quiz_type
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get(
    "/history/{quiz_id}",
    response_model=QuizResultResponse,
    summary="Lấy chi tiết kết quả quiz",
    description="",
)
async def get_quiz_detail(
    quiz_id: int,
    db: Session = Depends(get_db),
    user_id: int = Query(1),
):
    result = quiz_service.get_result_detail(db=db, quiz_id=quiz_id, user_id=user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Quiz result not found")
    return result

@router.get(
    "/stats",
    response_model=QuizStatsResponse,
    summary="Thống kê kết quả quiz",
    description="",
)
async def get_quiz_stats(
    db : Session = Depends(get_db),
    user_id: int = Query(1),
):
    return quiz_service.get_stats(db=db, user_id=user_id)

@router.delete(
    "/history/{quiz_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa kết quả quiz",
    description="",
)
async def delete_quiz_result(
    quiz_id: int,
    db: Session = Depends(get_db),
    user_id: int = Query(1),
):
    from app.models.quiz_result import QuizResult as QuizResultModel
    row = (
        db.query(QuizResultModel)
        .filter(
            QuizResultModel.quiz_id == quiz_id,
            QuizResultModel.user_id == user_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy quiz #{quiz_id}")
    db.delete(row)
    db.commit()