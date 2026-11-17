import json
import os
from pathlib import Path

from elevenlabs.client import ElevenLabs

# ElevenLabs rejects any single request over 10,000 characters.
MAX_CHARS = 9500

folder = Path(__file__).parent

def split_for_speech(text, limit=MAX_CHARS):
    text = text.strip()
    if len(text) <= limit:
        return [text]

    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    if len(blocks) == 1:
        sentences = []
        for sentence in text.replace("\n", " ").split(". "):
            sentence = sentence.strip()
            if not sentence:
                continue
            if not sentence.endswith((".", "!", "?")):
                sentence += "."
            sentences.append(sentence)
        blocks = sentences or [text]

    pieces = []
    current = ""

    def add(block):
        nonlocal current
        block = block.strip()
        if not block:
            return
        if len(block) > limit:
            if current:
                pieces.append(current)
                current = ""
            start = 0
            while start < len(block):
                chunk = block[start:start + limit].strip()
                if chunk:
                    pieces.append(chunk)
                start += limit
            return

        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) <= limit:
            current = candidate
        else:
            pieces.append(current)
            current = block

    for block in blocks:
        add(block)
    if current:
        pieces.append(current)
    return pieces

with open(folder / "story_bible.json", "r", encoding="utf-8") as file:
    story_bible = json.load(file)

chapters = story_bible["chapters"]

api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
if not api_key:
    print("ELEVENLABS_API_KEY is not set. Add it in the app's Streamlit secrets.")
    raise SystemExit(1)

client = ElevenLabs(api_key=api_key)

for chapter in chapters:
    chapter_number = chapter["chapter_number"]
    chapter_title = chapter["title"]
    text_path = folder / f"chapter_{chapter_number}.txt"
    output_path = folder / f"chapter_{chapter_number}.mp3"

    print(f"Recording Chapter {chapter_number}: {chapter_title}... please wait.\n")

    chapter_text = text_path.read_text(encoding="utf-8")
    pieces = split_for_speech(chapter_text)
    print(f"Chapter {chapter_number} is {len(chapter_text)} characters, split into {len(pieces)} parts.")

    audio_bytes = bytearray()
    for index, piece in enumerate(pieces, start=1):
        print(f"Recording part {index} of {len(pieces)} ({len(piece)} characters)...")
        audio = client.text_to_speech.convert(
            text=piece,
            voice_id="pNInz6obpgDQGcFmaJgB",  # Adam
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        audio_bytes.extend(b"".join(audio))

    output_path.write_bytes(audio_bytes)
    print(f"✅ Finished Chapter {chapter_number}. Saved audio to {output_path}\n")

print("✅ Success! All chapter audio files have been recorded.")
