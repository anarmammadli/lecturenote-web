import os
import tempfile
import traceback
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel

app = FastAPI(title="LectureNote Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_model_cache = {}

ALLOWED_MODELS = {"tiny", "base", "small", "medium", "large-v3"}


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds or 0))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_model(model_name: str) -> WhisperModel:
    model_name = (model_name or "base").strip()
    if model_name not in ALLOWED_MODELS:
        model_name = "base"

    if model_name not in _model_cache:
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        _model_cache[model_name] = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )
    return _model_cache[model_name]


@app.get("/")
def home():
    return {"ok": True, "message": "LectureNote backend is running"}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), model: str = Form("base")):
    suffix = Path(file.filename or "lecture.webm").suffix or ".webm"
    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)

        whisper = get_model(model)
        segments_iter, info = whisper.transcribe(
            tmp_path,
            beam_size=5,
            vad_filter=True,
        )

        segments = []
        plain_parts = []
        for i, seg in enumerate(segments_iter, start=1):
            text = (seg.text or "").strip()
            item = {
                "id": i,
                "start": float(seg.start or 0),
                "end": float(seg.end or 0),
                "time": format_time(seg.start),
                "text": text,
            }
            segments.append(item)
            plain_parts.append(f"[{item['time']}] {text}")

        return {
            "ok": True,
            "model": model,
            "language": getattr(info, "language", None),
            "duration": getattr(info, "duration", None),
            "segments": segments,
            "text": "\n".join(plain_parts),
        }

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)},
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
