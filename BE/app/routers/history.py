from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.history import (
    HistoryCreateRequest,
    HistoryDeleteResponse,
    HistoryItem,
    HistoryListResponse,
    HistorySummaryResponse,
    SessionType,
)
from app.services.history_service import history_service

router = APIRouter(prefix="/api/v1", tags=["History"])


@router.get("/history", response_model=HistoryListResponse, summary="Lấy danh sách lịch sử học tập")
async def get_learning_history(
    db: Session = Depends(get_db),
    user_id: int = Query(1, description="ID người dùng"),
    limit: int = Query(50, ge=1, le=200, description="Số bản ghi tối đa"),
    skip: int = Query(0, ge=0, description="Bỏ qua n bản ghi đầu"),
    session_type: Optional[SessionType] = Query(None, description="Loại phiên học"),
    object_name_en: Optional[str] = Query(None, description="Lọc theo tên vật (tiếng Anh)"),
    from_date: Optional[datetime] = Query(None, description="Từ ngày"),
    to_date: Optional[datetime] = Query(None, description="Đến ngày"),
):
    history_list = history_service.get_history(
        db=db,
        user_id=user_id,
        limit=limit,
        skip=skip,
        session_type=session_type,
        object_name_en=object_name_en,
        from_date=from_date,
        to_date=to_date,
    )
    total = history_service.get_total_count(db, user_id)
    return HistoryListResponse(
        success=True,
        history=history_list,
        total_count=total,
        skip=skip,
        limit=limit,
    )


# QUAN TRỌNG: /history/summary phải đặt TRƯỚC /history/{history_id}
# Nếu đặt sau, FastAPI sẽ hiểu "summary" là history_id (int) và báo lỗi
@router.get("/history/summary", response_model=HistorySummaryResponse, summary="Thống kê tổng hợp lịch sử học tập")
async def get_history_summary(
    db: Session = Depends(get_db),
    user_id: int = Query(1, description="ID người dùng"),
):
    summary = history_service.get_summary(db=db, user_id=user_id)
    return HistorySummaryResponse(success=True, summary=summary)


@router.get("/history/{history_id}", response_model=HistoryItem, summary="Chi tiết 1 bản ghi lịch sử")
async def get_history_item(
    history_id: int,
    db: Session = Depends(get_db),
    user_id: int = Query(1),
):
    record = history_service.get_history_by_id(db=db, history_id=history_id, user_id=user_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bản ghi #{history_id}",
        )
    return history_service._to_item(record)


@router.post("/history", response_model=HistoryItem, status_code=status.HTTP_201_CREATED, summary="Tạo bản ghi lịch sử thủ công")
async def create_history_manually(
    body: HistoryCreateRequest,
    db: Session = Depends(get_db),
):
    record = history_service.create_or_update_history(
        db=db,
        user_id=body.user_id,
        object_name_en=body.object_name_en,
        object_name_vn=body.object_name_vn or body.object_name_en,
        confidence=body.confidence or 0.0,
        session_type=body.session_type,
        duration_seconds=body.duration_seconds,
    )
    return history_service._to_item(record)


@router.delete("/history/{history_id}", response_model=HistoryDeleteResponse, summary="Xoá 1 bản ghi lịch sử")
async def delete_history_item(
    history_id: int,
    db: Session = Depends(get_db),
    user_id: int = Query(1),
):
    deleted = history_service.delete_history(db=db, history_id=history_id, user_id=user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bản ghi #{history_id}",
        )
    return HistoryDeleteResponse(
        success=True,
        deleted_count=1,
        message=f"Đã xoá bản ghi #{history_id}",
    )


@router.delete("/history", response_model=HistoryDeleteResponse, summary="Xoá toàn bộ lịch sử")
async def delete_all_history(
    db: Session = Depends(get_db),
    user_id: int = Query(1),
):
    count = history_service.delete_all_history(db=db, user_id=user_id)
    return HistoryDeleteResponse(
        success=True,
        deleted_count=count,
        message=f"Đã xoá {count} bản ghi của user {user_id}",
    )