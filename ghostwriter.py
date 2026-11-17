import json
import os
from anthropic import Anthropic

# Same connection setup and model as architect.py
client = Anthropic()

with open("story_bible.json", "r", encoding="utf-8") as file:
    story_bible = json.load(file)

chapters = story_bible["chapters"]

for chapter in chapters:
    chapter_number = chapter["chapter_number"]
    chapter_title = chapter["title"]
    chapter_summary = chapter["summary"]
    output_path = f"chapter_{chapter_number}.txt"

    print(f"Writing Chapter {chapter_number}: {chapter_title}... please wait.\n")

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

    prose = response.content[0].text

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(prose)

    print(f"✅ Finished Chapter {chapter_number}. Saved to {output_path}\n")

print("✅ Success! All chapters have been written.")
