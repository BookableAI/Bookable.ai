import json
from pathlib import Path

from elevenlabs.client import ElevenLabs
from elevenlabs.play import save

folder = Path(__file__).parent

with open(folder / "story_bible.json", "r", encoding="utf-8") as file:
    story_bible = json.load(file)

chapters = story_bible["chapters"]

import os
# Find your elevenlabs client setup and change the key to this:
api_key = os.environ.get("ELEVENLABS_API_KEY")

for chapter in chapters:
    chapter_number = chapter["chapter_number"]
    chapter_title = chapter["title"]
    text_path = folder / f"chapter_{chapter_number}.txt"
    output_path = folder / f"chapter_{chapter_number}.mp3"

    print(f"Recording Chapter {chapter_number}: {chapter_title}... please wait.\n")

    chapter_text = text_path.read_text(encoding="utf-8")

    audio = client.text_to_speech.convert(
        text=chapter_text,
        voice_id="pNInz6obpgDQGcFmaJgB",  # Adam
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )

    save(audio, str(output_path))
    print(f"✅ Finished Chapter {chapter_number}. Saved audio to {output_path}\n")

print("✅ Success! All chapter audio files have been recorded.")
