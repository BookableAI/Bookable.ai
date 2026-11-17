import os
import sys
import instructor
from anthropic import Anthropic
from pydantic import BaseModel

# 1. Setup your connection
api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
if not api_key:
    print("ANTHROPIC_API_KEY is not set. Add it in the app's Streamlit secrets.")
    sys.exit(1)

client = instructor.from_anthropic(Anthropic(api_key=api_key))

# 2. Define the exact shape of the data
class Character(BaseModel):
    name: str
    role: str
    voice_style: str

class Chapter(BaseModel):
    chapter_number: int
    title: str
    summary: str

class StoryBible(BaseModel):
    title: str
    tone: str
    characters: list[Character]
    chapters: list[Chapter]

# 3. Read the story idea and chapter length from the command line
if len(sys.argv) < 3 or not sys.argv[1].strip() or not sys.argv[2].strip():
    print('Usage: python architect.py "your story idea" "3-5"')
    sys.exit(1)

user_idea = sys.argv[1]
chapter_length = sys.argv[2]
print("Thinking of a story... please wait.\n")

# 4. Generate the story bible.
# claude-3-5-sonnet-20241022 is retired and returns 404.
# instructor passes this model id through unchanged.
story = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8000,
    system=(
        "You are a master storyteller. Expand the user's premise into a "
        f"{chapter_length} chapter story bible."
    ),
    messages=[
        {"role": "user", "content": user_idea}
    ],
    response_model=StoryBible,
)

# 5. Print the data and save it to a file
print(f"BOOK TITLE: {story.title.upper()}")
for chapter in story.chapters:
    print(f"Chapter {chapter.chapter_number}: {chapter.title}")

with open("story_bible.json", "w", encoding="utf-8") as file:
    file.write(story.model_dump_json(indent=4))

print("\n✅ Success! Saved to story_bible.json")
