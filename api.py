import json
import os
import subprocess
import sys
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

folder = Path(__file__).parent
generate_lock = Lock()

app = FastAPI(title="Bookable.ai")


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    chapters: int = Field(ge=1, le=15)


def run_script(command):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        command,
        cwd=folder,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise HTTPException(
            status_code=500,
            detail=detail or f"{command[1]} exited with code {result.returncode}.",
        )


def clear_previous_chapters():
    for pattern in ("chapter_*.txt", "chapter_*.mp3", "chapter_*.txt.part", "chapter_*.mp3.part"):
        for path in folder.glob(pattern):
            path.unlink(missing_ok=True)


@app.post("/generate")
def generate(body: GenerateRequest):
    if not generate_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A generation is already running.")

    try:
        prompt = body.prompt.strip()
        if not prompt:
            raise HTTPException(status_code=422, detail="prompt is required.")

        clear_previous_chapters()
        run_script([sys.executable, "architect.py", prompt, str(body.chapters)])
        run_script([sys.executable, "ghostwriter.py"])
        run_script([sys.executable, "audio_director.py"])

        story = json.loads((folder / "story_bible.json").read_text(encoding="utf-8"))
        chapters = []
        for chapter in story["chapters"]:
            number = chapter["chapter_number"]
            audio_path = folder / f"chapter_{number}.mp3"
            if not audio_path.exists():
                raise HTTPException(
                    status_code=500,
                    detail=f"Missing audio file {audio_path.name}.",
                )
            chapters.append(
                {
                    "chapter_number": number,
                    "title": chapter["title"],
                    "path": str(audio_path),
                    "url": f"/audio/{audio_path.name}",
                }
            )

        return {
            "title": story["title"],
            "tone": story.get("tone", ""),
            "chapters": chapters,
        }
    finally:
        generate_lock.release()


@app.get("/audio/{filename}")
def audio(filename: str):
    if not filename.startswith("chapter_") or not filename.endswith(".mp3"):
        raise HTTPException(status_code=404, detail="Audio file not found.")
    audio_path = folder / filename
    if not audio_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(audio_path, media_type="audio/mpeg", filename=filename)
