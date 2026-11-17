from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import json
import re
import shutil
import threading
import uuid
import uvicorn
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

import accounts

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
code_root = Path(__file__).parent
data_root = Path(os.environ.get("DATA_DIR", code_root))
data_root.mkdir(parents=True, exist_ok=True)
library_dir = data_root / "library"
jobs = {}
jobs_lock = threading.Lock()
generation_lock = threading.Lock()

class StoryRequest(BaseModel):
    prompt: str
    chapters: str
    voice: str = "pNInz6obpgDQGcFmaJgB"

FREE_VOICES = {
    "pNInz6obpgDQGcFmaJgB",
    "21m00Tcm4TlvDq8ikWAM",
    "onwK4e9ZLuTAKqWW03F9",
    "ThT5KcBeYPX3keUQqHPh",
}
PLUS_VOICES = {
    "EXAVITQu4vr4xnSDxMaL",
    "TxGEqnHWrfWFTfGW9XjX",
    "VR6AewLTigWG4xSOukaG",
    "MF3mGyEYCl7XYWbV9V6O",
    "CYw3kZ02Hs0563khs1Fj",
    "D38z5RcWu1voky8WS1ja",
    "IKne3meq5aSn9XLyUdCD",
    "ZQe5CZNOzWyzPSCn5a3c",
    "oWAxZDx7w5VEj9dCyTzz",
    "zcAOhNBS3c14rBihAFp1",
}
VOICES = FREE_VOICES | PLUS_VOICES

class AuthRequest(BaseModel):
    email: str
    password: str

@app.get("/")
async def health():
    return {"status": "ok"}

def bearer_user(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Log in from the Account tab.")
    user = accounts.user_from_token(authorization.removeprefix("Bearer ").strip())
    if user is None:
        raise HTTPException(status_code=401, detail="Log in from the Account tab.")
    return user

@app.post("/auth/register")
async def register(request: AuthRequest):
    try:
        return accounts.register(request.email, request.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

@app.post("/auth/login")
async def login(request: AuthRequest):
    try:
        return accounts.login(request.email, request.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

@app.post("/auth/logout")
async def logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        accounts.logout(authorization.removeprefix("Bearer ").strip())
    return {"status": "success"}

@app.get("/account")
async def account(authorization: str | None = Header(default=None)):
    user = bearer_user(authorization)
    return accounts.account_summary(user["id"])

@app.post("/account/subscribe")
async def subscribe(authorization: str | None = Header(default=None)):
    bearer_user(authorization)
    raise HTTPException(
        status_code=402,
        detail="Plus costs £9.99 a month. The plan stays on Free until that payment is completed.",
    )

@app.post("/generate")
async def generate_audiobook(request: StoryRequest, authorization: str | None = Header(default=None)):
    print(f"\n=== NEW REQUEST FROM PHONE ===")
    print(f"Idea: {request.prompt} | Chapters: {request.chapters}")
    user = None
    if authorization and authorization.startswith("Bearer "):
        user = accounts.user_from_token(authorization.removeprefix("Bearer ").strip())
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Log in from the Account tab. Free accounts can generate 1 audiobook and up to 8 chapters a month.",
        )
    if request.voice not in VOICES:
        raise HTTPException(status_code=400, detail="Choose a narrator from the list.")
    if request.voice in PLUS_VOICES and not accounts.account_summary(user["id"])["subscription_active"]:
        raise HTTPException(
            status_code=402,
            detail="That accent is part of Plus. Free accounts include 2 American and 2 British voices.",
        )
    try:
        chapter_count = accounts.check_can_generate(user, request.chapters)
    except PermissionError as error:
        raise HTTPException(status_code=402, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if not generation_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="An audiobook is already being generated. Try again when it finishes.",
        )

    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {"status": "running", "user_id": user["id"]}
    threading.Thread(
        target=run_generation,
        args=(job_id, user["id"], request.prompt, chapter_count, request.voice),
        daemon=True,
    ).start()
    return JSONResponse({"status": "running", "job_id": job_id}, status_code=202)

def run_generation(job_id: str, user_id: int, prompt: str, chapter_count: str, voice: str):
    work = data_root / "work" / job_id
    work.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["DATA_DIR"] = str(work)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        print("[1/3] Architect is designing the story bible...")
        subprocess.run(
            [sys.executable, str(code_root / "architect.py"), prompt, chapter_count],
            cwd=work,
            env=env,
            check=True,
        )
        print("\n[2/3] Ghostwriter is writing the chapters...")
        subprocess.run([sys.executable, str(code_root / "ghostwriter.py")], cwd=work, env=env, check=True)
        print("\n[3/3] Audio Director is generating the voiceover...")
        subprocess.run(
            [sys.executable, str(code_root / "audio_director.py"), voice],
            cwd=work,
            env=env,
            check=True,
        )
        book = archive_book(prompt, work)
        accounts.record_usage(user_id, book["id"], len(book["chapters"]))
        print("\n=== All Done! ===")
        result = {
            "status": "success",
            "user_id": user_id,
            "message": "Audiobook generated!",
            "book": book,
            "account": accounts.account_summary(user_id),
        }
    except subprocess.CalledProcessError:
        result = {
            "status": "error",
            "user_id": user_id,
            "message": "Generation failed. Check the Render logs.",
        }
    except FileNotFoundError as error:
        result = {"status": "error", "user_id": user_id, "message": str(error)}
    except Exception as error:
        result = {"status": "error", "user_id": user_id, "message": str(error)}
    finally:
        with jobs_lock:
            jobs[job_id] = result
        generation_lock.release()

@app.get("/jobs/{job_id}")
async def job_status(job_id: str, authorization: str | None = Header(default=None)):
    user = bearer_user(authorization)
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None or job["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="That generation was not found.")
    return {key: value for key, value in job.items() if key != "user_id"}

def archive_book(prompt: str, work: Path):
    story = json.loads((work / "story_bible.json").read_text(encoding="utf-8"))
    book_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    book_dir = library_dir / book_id
    book_dir.mkdir(parents=True, exist_ok=True)

    chapters = []
    for chapter in sorted(story["chapters"], key=lambda item: item["chapter_number"]):
        number = chapter["chapter_number"]
        source = work / f"chapter_{number}.mp3"
        if not source.is_file():
            raise FileNotFoundError(f"Missing chapter_{number}.mp3")
        shutil.copy2(source, book_dir / source.name)
        chapters.append({
            "chapter_number": number,
            "title": chapter["title"],
            "url": f"/audio/{book_id}/{source.name}",
        })

    book = {
        "id": book_id,
        "prompt": prompt,
        "title": story["title"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chapters": chapters,
    }
    (book_dir / "meta.json").write_text(json.dumps(book), encoding="utf-8")
    return book

def list_books():
    books = []
    if not library_dir.exists():
        return books
    for book_dir in library_dir.iterdir():
        if not book_dir.is_dir():
            continue
        meta_path = book_dir / "meta.json"
        if meta_path.is_file():
            books.append(json.loads(meta_path.read_text(encoding="utf-8")))
            continue
        chapters = []
        for audio_path in sorted(book_dir.glob("chapter_*.mp3")):
            number = int(audio_path.stem.split("_", 1)[1])
            chapters.append({
                "chapter_number": number,
                "title": f"Chapter {number}",
                "url": f"/audio/{book_dir.name}/{audio_path.name}",
            })
        if not chapters:
            continue
        book = {
            "id": book_dir.name,
            "prompt": "",
            "title": "Audiobook",
            "created_at": datetime.fromtimestamp(book_dir.stat().st_mtime, timezone.utc).isoformat(),
            "chapters": chapters,
        }
        meta_path.write_text(json.dumps(book), encoding="utf-8")
        books.append(book)
    books.sort(key=lambda item: item["created_at"], reverse=True)
    return books

@app.get("/library")
async def library():
    if not list_books() and (data_root / "story_bible.json").is_file() and (data_root / "chapter_1.mp3").is_file():
        story = json.loads((data_root / "story_bible.json").read_text(encoding="utf-8"))
        archive_book(story.get("title", "Audiobook"), data_root)
    return {"books": list_books()}

@app.get("/audio/{book_id}/{filename}")
async def get_book_audio(book_id: str, filename: str):
    if not re.fullmatch(r"\d{20}", book_id) or not re.fullmatch(r"chapter_\d+\.mp3", filename):
        raise HTTPException(status_code=404, detail="Audio file not found.")
    file_path = library_dir / book_id / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(file_path, media_type="audio/mpeg", filename=filename)

@app.get("/audio")
async def get_audio():
    # Make sure this matches the exact filename audio_director.py saves!
    file_path = data_root / "chapter_1.mp3"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/mpeg")
    return {"status": "error", "message": "Audio file not found on PC."}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))