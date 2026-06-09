import os
import threading
from datetime import datetime
import pyttsx3
from app.core.config import settings
from pydub import AudioSegment, effects

DURATION_MAP = {
    "person": 1.3,
    "bicycle": 1.0,
    "car": 0.9,
    "motorcycle": 1.1,
    "airplane": 1.1,
    "bus": 0.9,
    "train": 0.9,
    "truck": 0.9,
    "boat": 0.9,
    "traffic light": 1.3,
    "fire hydrant": 1.3,
    "stop sign": 1.2,
    "parking meter": 1.4,
    "bench": 0.9,
    "bird": 0.9,
    "cat": 0.9,
    "dog": 0.9,
    "horse": 0.9,
    "sheep": 0.9,
    "cow": 0.9,
    "elephant": 1.1,
    "bear": 0.9,
    "zebra": 0.9,
    "giraffe": 1.1,
    "backpack": 1.2,
    "umbrella": 1.1,
    "handbag": 1.1,
    "tie": 0.9,
    "suitcase": 1.1,
    "frisbee": 1.0,
    "skis": 0.9,
    "snowboard": 1.1,
    "sports ball": 1.2,
    "kite": 0.9,
    "baseball bat": 1.3,
    "baseball glove": 1.4,
    "skateboard": 1.1,
    "surfboard": 1.1,
    "tennis racket": 1.3,
    "bottle": 0.9,
    "wine glass": 1.2,
    "cup": 0.9,
    "fork": 0.9,
    "knife": 0.9,
    "spoon": 0.9,
    "bowl": 0.9,
    "banana": 0.9,
    "apple": 0.9,
    "sandwich": 1.1,
    "orange": 0.9,
    "broccoli": 1.1,
    "carrot": 0.9,
    "hot dog": 1.1,
    "pizza": 0.9,
    "donut": 0.9,
    "cake": 0.9,
    "chair": 0.9,
    "couch": 0.9,
    "potted plant": 1.3,
    "bed": 0.9,
    "dining table": 1.3,
    "toilet": 0.9,
    "tv": 0.9,
    "laptop": 1.0,
    "mouse": 0.9,
    "remote": 1.0,
    "keyboard": 1.1,
    "cell phone": 1.2,
    "microwave": 1.1,
    "oven": 0.9,
    "toaster": 1.0,
    "sink": 0.9,
    "refrigerator": 1.3,
    "book": 0.9,
    "clock": 0.9,
    "vase": 0.9,
    "scissors": 1.0,
    "teddy bear": 1.2,
    "hair drier": 1.2,
    "toothbrush": 1.0,
}

class TTSService:
    def __init__(self):
        self.engine = None
        self.audio_dir = settings.AUDIO_DIR
        self._init_engine()
        self._ensure_audio_dir()
        self._lock=threading.Lock()

    def _init_engine(self):
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', settings.TTS_RATE)
            self.engine.setProperty('volume', settings.TTS_VOLUME)
            self._set_voice()
            print("TS Service initialized successfully (WAV output)")

        except Exception as e:
            print(f"Failed to initialize TTS engine: {e}")
            self.engine = None

    def _set_voice(self):
        if not self.engine:
            return

        voices = self.engine.getProperty("voices")

        if not voices:
            print("No TTS voices found on this system")
            return

        print("Available TTS voices:")
        for index, voice in enumerate(voices):
            print(f"[{index}] id={voice.id} | name={getattr(voice, 'name', '')}")

        keyword = settings.TTS_VOICE_KEYWORD.lower().strip()

        selected_voice = None

        for voice in voices:
            voice_id = str(voice.id).lower()
            voice_name = str(getattr(voice, "name", "")).lower()

            if keyword and (keyword in voice_id or keyword in voice_name):
                selected_voice = voice
                break

        if selected_voice is None:
            voice_index = settings.TTS_VOICE_ID

            if 0 <= voice_index < len(voices):
                selected_voice = voices[voice_index]
            else:
                selected_voice = voices[0]

        self.engine.setProperty("voice", selected_voice.id)

        print(
            "Selected TTS voice:",
            getattr(selected_voice, "name", selected_voice.id)
        )

    def _ensure_audio_dir(self):
        os.makedirs(self.audio_dir, exist_ok=True)

    def _safe_name(self,text:str) -> str:
        return text.strip().lower().replace(" ", "_")

    def get_audio_filename(self, text: str) -> str:
        return f"{self._safe_name(text)}.wav"

    def get_audio_path(self, text: str) -> str:
        return os.path.join(self.audio_dir, self.get_audio_filename(text))

    def get_audio_url(self, text: str) -> str:
        return f"/static/audio/{self.get_audio_filename(text)}"

    def audio_exists(self, text: str) -> bool:
        return os.path.exists(self.get_audio_path(text))

    def _boost_wav_volume(self, filepath: str, gain_db: float = 8.0):
        audio = AudioSegment.from_wav(filepath)

        # Chuẩn hóa peak để âm lượng đều hơn, tránh file quá nhỏ
        audio = effects.normalize(audio)

        # Tăng thêm gain
        louder = audio + gain_db

        # Xuất lại file WAV
        louder.export(filepath, format="wav")

    def generate_audio(self, text: str, accent: str = "en-uk") -> dict:

        if not self.engine:
            raise Exception("TTS engine is not initialized")
        class_name = text.strip().lower()
        duration = DURATION_MAP.get(class_name,1.0)
        filename=self.get_audio_filename(class_name)
        filepath = self.get_audio_path(class_name)
        audio_url = self.get_audio_url(class_name)

        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"used cache audio for: {class_name}")
            return {
                "audio_url": audio_url,
                "duration_seconds": duration,
                "filename": filename,
                "full_path": filepath
            }

        try:
            with self._lock:
                self.engine.save_to_file(text, filepath)
                self.engine.runAndWait()

            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                raise Exception("Generated WAV file is missing or empty")
            self._boost_wav_volume(filepath, gain_db=6.0)

            print(f"Generated audio: {filename} | Duration {duration:.2f}s")

            return {
                "audio_url": audio_url,
                "duration_seconds": duration,
                "filename": filename,
                "full_path": filepath
            }

        except Exception as e:
            raise Exception(f"TTS generation failed: {str(e)}")

    def speak(self, text: str, accent: str = "en-uk"):
        if self.engine:
            self.engine.say(text)
            self.engine.runAndWait()
        else:
            print("TTS engine is not available")

tts_service = TTSService()