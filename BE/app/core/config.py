from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    PROJECT_NAME: str = "English Object Recognition Learning System"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    #Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    #YOLO
    YOLO_MODEL_PATH: str = "yolo11m.pt"
    CONFIDENCE_THRESHOLD: float = 0.5
    IMGSZ: int = 640

    #TTS (Text To Speech)
    TTS_RATE: int = 170
    TTS_VOLUME: float = 0.9
    TTS_VOICE: str = "english"

    #Paths
    AUDIO_DIR: str ="app/static/audio"
    DB_PATH: str ="learning.db"

    class Config:
        env_file = ".env"
settings = Settings()