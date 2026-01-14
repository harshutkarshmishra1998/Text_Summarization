# ================================
# LangChain: Summarize URL (YT + Web)
# ================================

import re
import api_keys
import validators
import streamlit as st

from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain.chains.summarize import load_summarize_chain
from langchain.schema import Document
from langchain_community.document_loaders import UnstructuredURLLoader
from langchain_community.document_loaders import PyPDFLoader, UnstructuredFileLoader
from youtube_transcript_api import YouTubeTranscriptApi

import requests
import tempfile
import os

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
    streaming=False,   # 🔑 REQUIRED
    temperature=0.2
)

# ---------------- PROMPT ----------------
prompt_template = """
Provide a concise summary of the following content in under 300 words.

Content:
{text}
"""

prompt = PromptTemplate(
    template=prompt_template,
    input_variables=["text"]
)

# ---------------- YOUTUBE TRANSCRIPT ----------------
def load_youtube_transcript(url: str):
    match = re.search(r"(?:v=|youtu\.be/)([^&?/]+)", url)
    if not match:
        raise ValueError("Invalid YouTube URL")

    video_id = match.group(1)

    transcript_data = YouTubeTranscriptApi().list(video_id)

    try:
        transcript = transcript_data.find_manually_created_transcript(["en"])
    except:
        transcript = transcript_data.find_generated_transcript(["en"])

    transcript = transcript.fetch()
    text = " ".join(chunk.text for chunk in transcript)

    return [Document(page_content=text)]

def load_google_drive_file(url: str):
    """
    Loads publicly shared Google Docs or Google Drive PDFs.
    Raises clear error if permission is denied.
    """
    session = requests.Session()

    # -------- Google Docs (text export) --------
    if "docs.google.com/document" in url:
        file_id = re.search(r"/d/([^/]+)", url)
        if not file_id:
            raise ValueError("Invalid Google Docs URL")

        file_id = file_id.group(1)
        export_url = f"https://docs.google.com/document/d/{file_id}/export?format=txt"

        resp = session.get(export_url, timeout=15)

        if resp.status_code != 200 or "DOCTYPE html" in resp.text:
            raise PermissionError(
                "Cannot access Google Doc. "
                "Make sure it is shared as: Anyone with the link → Viewer."
            )

        text = resp.text.strip()
        if not text:
            raise ValueError("Google Doc is empty or unreadable.")

        return [Document(page_content=text)]

    # -------- Google Drive file (PDF etc.) --------
    if "drive.google.com/file" in url:
        file_id = re.search(r"/d/([^/]+)", url)
        if not file_id:
            raise ValueError("Invalid Google Drive file URL")

        file_id = file_id.group(1)
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

        resp = session.get(download_url, timeout=20)

        if resp.status_code != 200 or "DOCTYPE html" in resp.text[:200]:
            raise PermissionError(
                "Cannot access Google Drive file. "
                "Ensure it is shared publicly (Viewer access)."
            )

        # Save temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(resp.content)
            temp_path = f.name

        loader = PyPDFLoader(temp_path)
        docs = loader.load()


from langchain_community.document_loaders import PyPDFLoader, UnstructuredFileLoader
import requests, tempfile, os, re

import requests, tempfile, os, re
from langchain_community.document_loaders import PyPDFLoader, UnstructuredFileLoader
from langchain.schema import Document

def load_google_drive_shared_file(url: str):
    match = re.search(r"/d/([^/]+)", url)
    if not match:
        raise ValueError("Invalid Google Drive file URL")

    file_id = match.group(1)
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    response = requests.get(download_url, timeout=20)
    content_type = response.headers.get("Content-Type", "").lower()

    # Permission / login HTML
    if response.status_code != 200 or "text/html" in content_type:
        raise PermissionError(
            "Cannot access Google Drive file. "
            "Set sharing to: Anyone with the link → Viewer."
        )

    # 🔑 EXTENSION DECISION (STRICT)
    if "application/pdf" in content_type:
        suffix = ".pdf"
        is_pdf = True
    else:
        suffix = ".docx"
        is_pdf = False

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(response.content)
        temp_path = f.name

    try:
        # 🔥 THIS LINE IS THE ENTIRE FIX
        if is_pdf:
            loader = PyPDFLoader(temp_path)              # ✅ SAFE
        else:
            loader = UnstructuredFileLoader(temp_path)  # DOC/DOCX ONLY

        docs = loader.load()

        if not docs or not docs[0].page_content.strip():
            raise ValueError("Downloaded file has no readable text.")

        return docs

    finally:
        os.unlink(temp_path)

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

            # elif "drive.google.com/file" in generic_url:
            #     docs = load_google_drive_shared_file(generic_url)

            elif "docs.google.com/document" in generic_url:
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
                    }
                )
                docs = loader.load()

            if not docs or not docs[0].page_content.strip():
                st.error("No readable text found at this URL.")
                st.stop()

            # -------- SUMMARIZE --------
            chain = load_summarize_chain(
                llm=llm,
                chain_type="stuff",
                prompt=prompt
            )

            result = chain.invoke(
                {"input_documents": docs},
                return_only_outputs=True
            )

            st.success(result["output_text"])

    except Exception as e:
        st.exception(e)