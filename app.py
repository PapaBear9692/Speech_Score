import os
import json
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from google import genai
from google.genai import types
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# Latest google-genai SDK — client is auto-configured from GEMINI_API_KEY env var
client = genai.Client()

MODEL = "gemini-2.5-flash"  # Use gemini-2.5-flash (stable). Switch to
                             # "gemini-3-flash-preview" if you have preview access.

ANALYSIS_PROMPT = """You are an expert speech coach and product presentation trainer.
Analyze this audio recording of an employee practicing a product sales/presentation speech.

Evaluate the following dimensions and return a JSON object ONLY (no markdown, no backticks):

{
  "overall_score": <0-100>,
  "transcript": "<exact words spoken>",
  "dimensions": {
    "clarity": {
      "score": <0-100>,
      "feedback": "<specific feedback>",
      "examples": ["<example from speech>"]
    },
    "tone_confidence": {
      "score": <0-100>,
      "feedback": "<specific feedback>",
      "examples": ["<example from speech>"]
    },
    "pacing": {
      "score": <0-100>,
      "feedback": "<specific feedback>",
      "examples": ["<example from speech>"]
    },
    "product_knowledge": {
      "score": <0-100>,
      "feedback": "<specific feedback>",
      "examples": ["<example from speech>"]
    },
    "persuasiveness": {
      "score": <0-100>,
      "feedback": "<specific feedback>",
      "examples": ["<example from speech>"]
    },
    "vocabulary": {
      "score": <0-100>,
      "feedback": "<specific feedback>",
      "examples": ["<example from speech>"]
    }
  },
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "improvements": [
    {
      "issue": "<issue title>",
      "detail": "<detailed explanation>",
      "suggestion": "<actionable suggestion>"
    }
  ],
  "filler_words": {
    "count": <number>,
    "words": ["<each filler word occurrence>"],
    "feedback": "<advice on reducing filler words>"
  },
  "energy_level": "<low|medium|high>",
  "overall_impression": "<2-3 sentence summary of the speech performance>",
  "next_practice_focus": "<single most important thing to practice next>"
}

Be specific, constructive, and encouraging. Reference actual moments from the speech."""


@app.route("/")
def index():
    return render_template('app.html')


@app.route("/analyze", methods=["POST"])
def analyze_speech():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    product_context = request.form.get("product_context", "").strip()

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

        # Build prompt, optionally injecting product context
        prompt = ANALYSIS_PROMPT
        if product_context:
            prompt += f"\n\nProduct context provided by trainer:\n{product_context}"

        # ── Generate analysis ─────────────────────────────────────────────────
        response = client.models.generate_content(
            model=MODEL,
            contents=[prompt, uploaded],
        )

        raw = response.text.strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.lower().startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        # Clean up uploaded file from Google's servers
        client.files.delete(name=uploaded.name)

        return jsonify({"success": True, "analysis": result})

    except json.JSONDecodeError as e:
        return jsonify({"error": f"Could not parse AI response: {e}", "raw": response.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Always clean up local temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        print("⚠️  GEMINI_API_KEY not set — set it before starting.")
    print("🎙️  Speech Score running → http://localhost:5000")
    app.run(debug=True, port=5000)