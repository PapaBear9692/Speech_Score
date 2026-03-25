import os
import json
import tempfile
import logging
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from google import genai
from google.genai import types
from dotenv import load_dotenv
from llama_config import initialize_index
from prompt import ANALYSIS_PROMPT

import re

app = Flask(__name__)
load_dotenv()

# ─── Logging Setup ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_text(text):
    """
    A more aggressive sanitizer for LLM output.
    - Removes leading non-alphanumeric characters.
    - Collapses multiple whitespace characters.
    - Fixes text where letters are separated by spaces (e.g., 'H e l l o').
    """
    if not isinstance(text, str):
        return text

    # Remove leading junk characters but keep legitimate sentence starters
    sanitized = re.sub(r"^[^\w'\"(]+", "", text.strip())

    # Heuristic: If the text has an unusually high ratio of spaces to characters,
    # it's likely spaced out.
    char_count = len(sanitized.replace(" ", ""))
    space_count = sanitized.count(" ")

    # If more than half the string is spaces, and it's not just a few chars,
    # assume it's an artifact and remove all spaces.
    if char_count > 5 and space_count > char_count * 0.8:
        sanitized = "".join(sanitized.split())
    else:
        # Otherwise, just collapse multiple spaces into one
        sanitized = re.sub(r"\s+", " ", sanitized)

    return sanitized.strip()

def sanitize_analysis_result(result):
    """Recursively sanitizes all string values in the analysis result."""
    if isinstance(result, dict):
        return {k: sanitize_analysis_result(v) for k, v in result.items()}
    elif isinstance(result, list):
        return [sanitize_analysis_result(item) for item in result]
    elif isinstance(result, str):
        return sanitize_text(result)
    return result


# ─── LlamaIndex/Pinecone RAG Setup ──────────────────────────────────────────
vector_index = initialize_index()
# ─────────────────────────────────────────────────────────────────────────────


# Latest google-genai SDK — client is auto-configured from GEMINI_API_KEY env var
client = genai.Client()

MODEL = "gemini-2.5-flash"




@app.route("/")
def index():
    return render_template('app.html')


@app.route("/analyze", methods=["POST"])
def analyze_speech():
    logging.info("Received request to /analyze")
    if "audio" not in request.files:
        logging.warning("No audio file provided in the request.")
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    product_context = request.form.get("product_context", "").strip()
    logging.info(f"Received product context: '{product_context[:100]}...'")

    # ─── RAG Retrieval Step ────────────────────────────────────────────────
    retrieved_context = ""
    if product_context:
        logging.info("Product context provided. Starting RAG retrieval...")
        try:
            # Use LlamaIndex retriever to get relevant chunks
            retriever = vector_index.as_retriever(similarity_top_k=5)
            nodes = retriever.retrieve(product_context)
            retrieved_context = "\n\n".join([n.get_content() for n in nodes])
            logging.info(f"Retrieved {len(nodes)} chunks from vector store.")
            # ─── Log Retrieved Chunks for Debugging ────────────────────────
            logging.info("────────────────── RETRIEVED CHUNKS ──────────────────")
            logging.info(retrieved_context)
            logging.info("──────────────────────────────────────────────────────")
            # ───────────────────────────────────────────────────────────────
        except Exception as e:
            logging.error(f"Error during RAG retrieval: {e}", exc_info=True)
            # Fail gracefully, proceed without retrieved context
            retrieved_context = "Error: Could not retrieve context from vector store."
    else:
        logging.info("No product context provided. Skipping RAG retrieval.")


    # Determine mime type from filename
    filename = audio_file.filename or "audio.webm"
    ext_to_mime = {
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".flac": "audio/flac",
        ".webm": "audio/webm",
    }
    ext = Path(filename).suffix.lower()
    mime_type = ext_to_mime.get(ext, "audio/webm")

    # Save to temp file — client.files.upload() accepts a file path
    with tempfile.NamedTemporaryFile(suffix=ext or ".webm", delete=False) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # ── Upload audio via Files API (latest SDK pattern) ──────────────────
        uploaded = client.files.upload(
            file=tmp_path,
            config=types.UploadFileConfig(mime_type=mime_type),
        )

        # Build prompt, injecting both user-provided and retrieved context
        final_prompt = ANALYSIS_PROMPT.format(retrieved_context=retrieved_context)
        if product_context:
            final_prompt += f"\n\nOriginal user-provided context:\n{product_context}"
        logging.info("Prompt constructed. Sending to Gemini for analysis.")


        # ── Generate analysis ─────────────────────────────────────────────────
        response = client.models.generate_content(
            model=MODEL,
            contents=[final_prompt, uploaded],
        )

        raw = response.text.strip() # type: ignore
        logging.info("Received response from Gemini.")
        logging.debug(f"Raw Gemini response: {raw}")

        # Strip accidental markdown fences
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.lower().startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        # ─── Sanitize AI Response to Prevent Artifacts ──────────────────────
        logging.info("Sanitizing AI response...")
        sanitized_result = sanitize_analysis_result(result)
        logging.info("Sanitization complete.")
        # ───────────────────────────────────────────────────────────────────

        # Clean up uploaded file from Google's servers
        client.files.delete(name=uploaded.name) # type: ignore
        logging.info("Analysis complete. Returning JSON response.")
        return jsonify({"success": True, "analysis": sanitized_result})

    except json.JSONDecodeError as e:
        logging.error(f"JSONDecodeError: Could not parse AI response. Raw text: {response.text}", exc_info=True)
        return jsonify({"error": f"Could not parse AI response: {e}", "raw": response.text}), 500 # type: ignore
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        # Always clean up local temp file
        try:
            os.unlink(tmp_path)
            logging.info(f"Successfully deleted temp file: {tmp_path}")
        except Exception as e:
            logging.error(f"Failed to delete temp file: {tmp_path}", exc_info=True)
            pass


if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        print("⚠️  GEMINI_API_KEY not set — set it before starting.")
    print("🎙️  Speech Score running → http://localhost:5000")
    app.run(debug=True, port=5000)
