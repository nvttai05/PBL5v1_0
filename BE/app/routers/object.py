from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.object_dictionary import ObjectDictionary
from app.schemas.object_detail import ObjectDetailResponse
from app.services.yolo_service import yolo_service

router = APIRouter(prefix="/api/v1", tags=["Object Detail"])

@router.get("/objects/{class_name_en}", response_model=ObjectDetailResponse)
async def get_object_detail(class_name_en: str, db: Session = Depends(get_db)):
    obj = db.query(ObjectDictionary).filter(ObjectDictionary.class_name_en == class_name_en).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    return ObjectDetailResponse(
        success=True,
        class_name_en=obj.class_name_en,
        class_name_vn=obj.class_name_vn,
        example_sentence_en=obj.example_sentence_en,
        pronunciation_en=obj.pronunciation_ipa,
        audio_url=obj.audio_file_path,
    )

