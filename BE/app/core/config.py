from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    PROJECT_NAME: str = "English Object Recognition Learning System"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    #Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    #YOLO
    YOLO_MODEL_PATH: str = "bestt.pt"
    CONFIDENCE_THRESHOLD: float = 0.3
    IMGSZ: int = 640
    YOLO_MAX_DET: int = 3
    #Person filter
    PERSON_CONFIDENCE_THRESHOLD: float = 0.73
    PERSON_MIN_AREA_RATIO: float = 0.12
    PERSON_MIN_WIDTH_RATIO: float = 0.15
    PERSON_MIN_HEIGHT_RATIO: float = 0.30
    IGNORE_PERSON_WHEN_OTHER_OBJECTS_EXIST: bool = True

    #TTS (Text To Speech)
    TTS_RATE: int = 170
    TTS_VOLUME: float = 1.0
    # TTS_VOICE: str = "english"
    TTS_VOICE_ID:int = 1
    TTS_VOICE_KEYWORD:str = "zira"

    #Paths
    AUDIO_DIR: str ="app/static/audio"
    DB_PATH: str ="learning.db"

    #Token
    SECRET_KEY: str = "Taidzquaditroioilatroi11072005"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:int = 60*24*7

    class Config:
        env_file = ".env"
settings = Settings()