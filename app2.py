# ================================
# LangChain: Summarize URL (YT + Web)
# ================================

import re
import os
import json
import tempfile
import subprocess
import requests

import api_key_prod
import validators
import streamlit as st

from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain.chains.summarize import load_summarize_chain
from langchain_groq import ChatGroq

from langchain_community.document_loaders import (
    UnstructuredURLLoader,
    PyPDFLoader,
    UnstructuredFileLoader,
)

# ---------------- STREAMLIT UI ----------------
st.set_page_config(
    page_title="LangChain: Summarize Text From YT or Website",
    page_icon="🦜"
)

st.title("🦜 LangChain: Summarize Text From YT or Website")
st.subheader("Summarize URL")

generic_url = st.text_input("URL", label_visibility="collapsed")

# ---------------- LLM ----------------
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    streaming=False,
    temperature=0.2,
)

# ---------------- PROMPT ----------------
prompt_template = """
Provide a concise summary of the following content in under 300 words.

Content:
{text}
"""

prompt = PromptTemplate(
    template=prompt_template,
    input_variables=["text"],
)

# ---------------- YOUTUBE TRANSCRIPT (CLOUD SAFE) ----------------
def load_youtube_transcript(url: str):
    """
    Works locally and on Streamlit Cloud.
    Uses youtube_transcript_api first, falls back to yt-dlp if blocked.
    """

    match = re.search(r"(?:v=|youtu\.be/)([^&?/]+)", url)
    if not match:
        raise ValueError("Invalid YouTube URL")

    video_id = match.group(1)

    # ----- Method 1: youtube_transcript_api (local IPs) -----
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        transcript_data = YouTubeTranscriptApi().list(video_id)

        try:
            transcript = transcript_data.find_manually_created_transcript(["en"])
        except:
            transcript = transcript_data.find_generated_transcript(["en"])

        transcript = transcript.fetch()
        text = " ".join(chunk.text for chunk in transcript)

        if text.strip():
            return [Document(page_content=text)]

    except Exception:
        pass  # Cloud IP blocked → fallback

    # ----- Method 2: yt-dlp fallback (cloud safe) -----
    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = os.path.join(tmpdir, "%(id)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--sub-format", "json3",
            "-o", output_template,
            url,
        ]

        subprocess.run(cmd, check=True, capture_output=True)

        files = os.listdir(tmpdir)
        sub_files = [f for f in files if f.endswith(".json3")]

        if not sub_files:
            raise RuntimeError("No subtitles available for this video.")

        sub_path = os.path.join(tmpdir, sub_files[0])

        with open(sub_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        events = data.get("events", [])
        text = " ".join(
            seg["utf8"]
            for event in events
            for seg in event.get("segs", [])
        )

        if not text.strip():
            raise RuntimeError("Transcript is empty.")

        return [Document(page_content=text)]

# ---------------- GOOGLE DOCS / DRIVE ----------------
def load_google_drive_file(url: str):
    session = requests.Session()

    # Google Docs
    if "docs.google.com/document" in url:
        file_id = re.search(r"/d/([^/]+)", url)
        if not file_id:
            raise ValueError("Invalid Google Docs URL")

        file_id = file_id.group(1)
        export_url = f"https://docs.google.com/document/d/{file_id}/export?format=txt"

        resp = session.get(export_url, timeout=15)

        if resp.status_code != 200 or "DOCTYPE html" in resp.text:
            raise PermissionError(
                "Cannot access Google Doc. Share as: Anyone with link → Viewer."
            )

        text = resp.text.strip()
        if not text:
            raise ValueError("Google Doc is empty.")

        return [Document(page_content=text)]

    # Google Drive files
    if "drive.google.com/file" in url:
        file_id = re.search(r"/d/([^/]+)", url)
        if not file_id:
            raise ValueError("Invalid Google Drive file URL")

        file_id = file_id.group(1)
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

        resp = session.get(download_url, timeout=20)

        if resp.status_code != 200:
            raise PermissionError("Cannot access Google Drive file.")

        content_type = resp.headers.get("Content-Type", "").lower()

        suffix = ".pdf" if "application/pdf" in content_type else ".docx"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(resp.content)
            temp_path = f.name

        try:
            if suffix == ".pdf":
                loader = PyPDFLoader(temp_path)
            else:
                loader = UnstructuredFileLoader(temp_path)

            docs = loader.load()

            if not docs or not docs[0].page_content.strip():
                raise ValueError("File contains no readable text.")

            return docs

        finally:
            os.unlink(temp_path)

    raise ValueError("Unsupported Google Drive URL")

# ---------------- BUTTON ----------------
if st.button("Summarize the Content from YT or Website"):

    if not validators.url(generic_url):
        st.error("Please enter a valid URL")
        st.stop()

    try:
        with st.spinner("Loading content..."):

            # -------- LOAD CONTENT --------
            if "youtube.com" in generic_url or "youtu.be" in generic_url:
                docs = load_youtube_transcript(generic_url)

            elif "docs.google.com/document" in generic_url or "drive.google.com/file" in generic_url:
                docs = load_google_drive_file(generic_url)

            elif generic_url.lower().endswith(".pdf"):
                loader = PyPDFLoader(generic_url)
                docs = loader.load()

            else:
                loader = UnstructuredURLLoader(
                    urls=[generic_url],
                    ssl_verify=False,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    },
                )
                docs = loader.load()

            if not docs or not docs[0].page_content.strip():
                st.error("No readable text found at this URL.")
                st.stop()

            # -------- SUMMARIZE --------
            chain = load_summarize_chain(
                llm=llm,
                chain_type="stuff",
                prompt=prompt,
            )

            result = chain.invoke(
                {"input_documents": docs},
                return_only_outputs=True,
            )

            st.success(result["output_text"])

    except Exception as e:
        st.exception(e)