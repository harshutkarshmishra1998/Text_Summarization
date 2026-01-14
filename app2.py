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

from youtube_transcript_api import YouTubeTranscriptApi

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