import subprocess
import time
import sys

if len(sys.argv) < 2 or not sys.argv[1].strip():
    print('Usage: python main.py "your story idea" ["3-5"]')
    sys.exit(1)

user_idea = sys.argv[1]
chapter_length = sys.argv[2].strip() if len(sys.argv) > 2 and sys.argv[2].strip() else "3-5"

print("=== Welcome to the AI Audiobook Builder ===\n")

# 1. Run the Architect
print("[1/3] Architect is designing the story bible...")
architect_process = subprocess.run([sys.executable, "architect.py", user_idea, chapter_length])
if architect_process.returncode != 0:
    print("Architect encountered an error. Stopping pipeline.")
    sys.exit(1)
time.sleep(1) # Brief pause to ensure the file system saves the JSON

# 2. Run the Ghostwriter
print("\n[2/3] Ghostwriter is writing Chapter 1...")
ghostwriter_process = subprocess.run([sys.executable, "ghostwriter.py"])
if ghostwriter_process.returncode != 0:
    print("Ghostwriter encountered an error. Stopping pipeline.")
    sys.exit(1)
time.sleep(1) # Brief pause to ensure the text file is saved

# 3. Run the Audio Director
print("\n[3/3] Audio Director is generating the voiceover...")
audio_process = subprocess.run([sys.executable, "audio_director.py"])
if audio_process.returncode != 0:
    print("Audio Director encountered an error. Stopping pipeline.")
    sys.exit(1)

print("\n=== All Done! Open chapter_1.mp3 to listen to your audiobook! ===")