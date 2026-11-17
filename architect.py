import os
import instructor
from anthropic import Anthropic
from pydantic import BaseModel
# 1. Setup your connection
# PASTE YOUR BRAND NEW ANTHROPIC KEY BELOW
client = instructor.from_anthropic(Anthropic())
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
# 3. Ask the user for their idea
user_idea = input("\nWhat is your story idea? -> ")
print("Thinking of a story... please wait.\n")
# 4. Generate the story bible using the new unlocked model
# 4. Generate the story bible.
# claude-3-5-sonnet-20241022 is retired and returns 404.
# instructor passes this model id through unchanged.
story = client.messages.create(
    model="claude-3-5-sonnet-20241022", 
    model="claude-sonnet-4-6", 
    max_tokens=1500,
    system="You are a master storyteller. Expand the user's premise into a 3-chapter story bible.",
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