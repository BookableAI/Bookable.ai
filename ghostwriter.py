import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from anthropic import Anthropic

api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
if not api_key:
    print("ANTHROPIC_API_KEY is not set. Add it as an environment variable.")
    raise SystemExit(1)

client = Anthropic(api_key=api_key)

with open("story_bible.json", "r", encoding="utf-8") as file:
    story_bible = json.load(file)

chapters = story_bible["chapters"]
print_lock = threading.Lock()

def log(message):
    with print_lock:
        print(message, flush=True)

def save_text(path, text):
    """Write to a temporary file, then replace the chapter file in one step."""
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)

def write_chapter(chapter):
    chapter_number = chapter["chapter_number"]
    chapter_title = chapter["title"]
    chapter_summary = chapter["summary"]
    output_path = Path(f"chapter_{chapter_number}.txt")

    log(f"Writing Chapter {chapter_number}: {chapter_title}... please wait.\n")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": (
                    "You are an expert Ghostwriter. Write a rich, engaging 1,500-word "
                    f"prose chapter for Chapter {chapter_number}: {chapter_title}. "
                    f"Here is the summary to follow: {chapter_summary}. "
                    "Do not include conversational filler."
                ),
            }
        ],
    )

    save_text(output_path, response.content[0].text)
    log(f"✅ Finished Chapter {chapter_number}. Saved to {output_path}\n")

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(write_chapter, chapter) for chapter in chapters]
    try:
        for future in as_completed(futures):
            future.result()
    except Exception:
        for future in futures:
            future.cancel()
        raise

print("✅ Success! All chapters have been written.")
