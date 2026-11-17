import json
import os
import subprocess
import sys
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

if st.button("Generate Audiobook", type="primary"):
    if not prompt.strip():
        st.warning("Enter a story prompt first.")
    else:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        steps = [
            ("Architect", [sys.executable, "architect.py", prompt.strip()]),
            ("Ghostwriter", [sys.executable, "ghostwriter.py"]),
            ("Audio Director", [sys.executable, "audio_director.py"]),
        ]

        failed = False
        with st.status("Building your audiobook...", expanded=True) as status:
            for label, command in steps:
                status.write(f"Running {label}...")
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
                    status.update(label=f"{label} failed", state="error")
                    detail = (result.stderr or result.stdout or "").strip()
                    st.error(detail or f"{label} exited with code {result.returncode}.")
                    failed = True
                    break
                status.write(f"{label} finished.")

            if not failed:
                status.update(label="Audiobook ready", state="complete")

        if not failed:
            story = json.loads((folder / "story_bible.json").read_text(encoding="utf-8"))
            st.subheader(story["title"])
            st.caption(story["tone"])

            for chapter in story["chapters"]:
                number = chapter["chapter_number"]
                audio_path = folder / f"chapter_{number}.mp3"
                st.markdown(f"**Chapter {number}: {chapter['title']}**")
                if audio_path.exists():
                    st.audio(audio_path.read_bytes(), format="audio/mp3")
                else:
                    st.warning(f"Missing {audio_path.name}")
