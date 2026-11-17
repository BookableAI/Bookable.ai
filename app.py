import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import streamlit as st

folder = Path(__file__).parent

st.set_page_config(page_title="Bookable.ai", page_icon="📖")
st.title("Bookable.ai")
st.write("Type a story idea and generate a narrated audiobook.")

prompt = st.text_area(
    "Story prompt",
    placeholder="A disgraced spy in Napoleonic Paris is pulled back into a conspiracy...",
    height=160,
)

chapter_count = st.selectbox(
    "Select chapter count",
    ["3-5", "6-8", "9-11", "12-15"],
)

def secret_value(name):
    try:
        value = st.secrets[name]
    except Exception:
        value = ""
    if value:
        return str(value).strip()
    return os.environ.get(name, "").strip()

if st.button("Generate Audiobook", type="primary"):
    if not prompt.strip():
        st.warning("Enter a story prompt first.")
    else:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        for name in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY"):
            value = secret_value(name)
            if value:
                env[name] = value

        if not env.get("ANTHROPIC_API_KEY"):
            st.error(
                "ANTHROPIC_API_KEY is missing. In the Streamlit app settings, "
                "open Secrets and add ANTHROPIC_API_KEY and ELEVENLABS_API_KEY."
            )
        else:
            steps = [
                ("Architect", [sys.executable, "architect.py", prompt.strip(), chapter_count]),
                ("Ghostwriter", [sys.executable, "ghostwriter.py"]),
                ("Audio Director", [sys.executable, "audio_director.py"]),
            ]

            status = st.status("Building your audiobook...", expanded=True)
            title_slot = st.empty()
            seen_audio = set()
            started = time.time()

            def publish_ready_audio():
                bible_path = folder / "story_bible.json"
                chapters_by_number = {}
                if bible_path.exists() and bible_path.stat().st_mtime >= started - 1:
                    try:
                        story = json.loads(bible_path.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        story = None
                    if story:
                        chapters_by_number = {
                            chapter["chapter_number"]: chapter["title"]
                            for chapter in story.get("chapters", [])
                        }
                        with title_slot.container():
                            st.subheader(story["title"])
                            st.caption(story.get("tone", ""))

                for audio_path in sorted(folder.glob("chapter_*.mp3")):
                    if audio_path.name in seen_audio:
                        continue
                    if audio_path.stat().st_mtime < started - 1 or audio_path.stat().st_size == 0:
                        continue
                    seen_audio.add(audio_path.name)
                    number = audio_path.stem.split("_", 1)[-1]
                    title = chapters_by_number.get(int(number), "")
                    label = f"Chapter {number}: {title}" if title else f"Chapter {number}"
                    st.markdown(f"**{label}**")
                    st.audio(audio_path.read_bytes(), format="audio/mp3")

            failed = False
            for label, command in steps:
                status.write(f"Running {label}...")
                process = subprocess.Popen(
                    command,
                    cwd=folder,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                )
                output = []

                def drain_output(stream, sink):
                    for line in stream:
                        sink.append(line)

                reader = threading.Thread(
                    target=drain_output,
                    args=(process.stdout, output),
                    daemon=True,
                )
                reader.start()

                while process.poll() is None:
                    publish_ready_audio()
                    time.sleep(1)

                reader.join(timeout=5)
                publish_ready_audio()

                if process.returncode != 0:
                    status.update(label=f"{label} failed", state="error")
                    detail = "".join(output).strip()
                    st.error(detail or f"{label} exited with code {process.returncode}.")
                    failed = True
                    break
                status.write(f"{label} finished.")

            if not failed:
                status.update(label="Audiobook ready", state="complete")
