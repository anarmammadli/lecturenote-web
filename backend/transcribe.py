# UTF-8 safety for Windows console/subprocess output.
# Fixes: UnicodeEncodeError: 'charmap' codec can't encode character ...
import sys
import os

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import subprocess
import tempfile
import re
from faster_whisper import WhisperModel


SUPPORTED_MODELS = {"base", "small", "medium", "large-v3"}


def progress(message):
    print(message, file=sys.stderr, flush=True)


def emit(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)


def format_time(seconds):
    seconds = int(seconds)
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def check_ffmpeg():
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return True
    except Exception:
        return False


def extract_audio_to_wav(input_path):
    temp_dir = tempfile.mkdtemp(prefix="lecturenote_studio_")
    wav_path = os.path.join(temp_dir, "audio_16khz.wav")

    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-f", "wav",
        wav_path
    ]

    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=True
    )

    return wav_path


def transcribe_file(input_path, model_name="base"):
    """
    Used by FastAPI backend on Railway.

    input_path: uploaded audio/video file path
    model_name: base, small, medium, or large-v3

    Returns JSON-compatible dictionary.
    """

    if model_name not in SUPPORTED_MODELS:
        model_name = "base"

    if not os.path.exists(input_path):
        raise Exception(f"File not found: {input_path}")

    if not check_ffmpeg():
        raise Exception("FFmpeg is not installed or not available in PATH.")

    wav_path = None

    try:
        wav_path = extract_audio_to_wav(input_path)

        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8"
        )

        segments_iter, info = model.transcribe(
            wav_path,
            beam_size=5,
            vad_filter=True,
            task="transcribe",
            word_timestamps=False
        )

        segments = []

        for segment in segments_iter:
            text = clean_text(segment.text)

            if text:
                segments.append({
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "time": format_time(segment.start),
                    "text": text
                })

        return {
            "ok": True,
            "engine": "faster-whisper",
            "model": model_name,
            "language": getattr(info, "language", "unknown"),
            "duration": getattr(info, "duration", None),
            "segments": segments
        }

    except subprocess.CalledProcessError:
        return {
            "ok": False,
            "error": "FFmpeg failed to read this file. Try another audio/video file."
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }

    finally:
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass


def main():
    """
    Local command-line mode.

    Example:
    python transcribe.py lecture.mp4 base
    """

    try:
        if len(sys.argv) < 2:
            raise Exception("No media file provided.")

        input_path = sys.argv[1]
        model_name = sys.argv[2] if len(sys.argv) >= 3 else "base"

        progress("STEP:CONVERT")
        progress("STEP:LOAD_MODEL")
        progress("STEP:TRANSCRIBE")

        result = transcribe_file(input_path, model_name)

        progress("STEP:RENDER")
        emit(result)

    except KeyboardInterrupt:
        emit({
            "ok": False,
            "error": "Transcription stopped."
        })

    except Exception as e:
        emit({
            "ok": False,
            "error": str(e)
        })


if __name__ == "__main__":
    main()