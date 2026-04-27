from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os

from transcribe import transcribe_file

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Later replace with your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "ok": True,
        "message": "LectureNote backend is running"
    }


@app.get("/health")
def health():
    return {
        "ok": True
    }


@app.post("/transcribe")
async def transcribe_endpoint(
    file: UploadFile = File(...),
    model: str = Form("base")
):
    input_path = None

    try:
        suffix = os.path.splitext(file.filename or "")[1] or ".webm"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            input_path = tmp.name

        result = transcribe_file(input_path, model)
        return result

    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }

    finally:
        if input_path and os.path.exists(input_path):
            try:
                os.remove(input_path)
            except Exception:
                pass