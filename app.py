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

chapter_count = st.selectbox(
    "Select chapter count",
    ["3-5", "6-8", "9-12", "13-15"],
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
