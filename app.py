from datetime import datetime
import os
import json
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_file
from google import genai
from google.genai import types
from dotenv import load_dotenv
from weasyprint import HTML, CSS
import io
from llama_config import initialize_index
from prompt import ANALYSIS_PROMPT
from werkzeug.middleware.proxy_fix import ProxyFix  # ✅ added


app = Flask(__name__)

app.config['APPLICATION_ROOT'] = '/speech'  # ✅ added
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_prefix=1)  # ✅ added

load_dotenv()


# ─── LlamaIndex/Pinecone RAG Setup ──────────────────────────────────────────
vector_index = initialize_index()
# ─────────────────────────────────────────────────────────────────────────────


# Latest google-genai SDK — client is auto-configured from GEMINI_API_KEY env var
client = genai.Client()

MODEL = "gemini-3-flash-preview" #"gemini-2.5-flash"




@app.route("/")
def index():
    return render_template('app.html')


@app.route("/analyze", methods=["POST"])
def analyze_speech():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    product_context = request.form.get("product_context", "").strip()

    # ─── RAG Retrieval Step ────────────────────────────────────────────────
    retrieved_context = ""
    if product_context:
        try:
            # Use LlamaIndex retriever to get relevant chunks
            retriever = vector_index.as_retriever(similarity_top_k=5)
            nodes = retriever.retrieve(product_context)
            retrieved_context = product_context + "\n\n" + "\n\n".join([n.get_content() for n in nodes])
        except Exception as e:
            # Fail gracefully, proceed without retrieved context
            retrieved_context = "Error: Could not retrieve context from vector store."


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


        # ── Generate analysis ─────────────────────────────────────────────────
        response = client.models.generate_content(
            model=MODEL,
            contents=[final_prompt, uploaded],
        )

        raw = response.text.strip() # type: ignore

        # Strip accidental markdown fences
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.lower().startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        # ───────────────────────────────────────────────────────────────────

        # Clean up uploaded file from Google's servers
        client.files.delete(name=uploaded.name) # type: ignore
        return jsonify({"success": True, "analysis": result})

    except json.JSONDecodeError as e:
        return jsonify({"error": f"Could not parse AI response: {e}", "raw": response.text}), 500 # type: ignore
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Always clean up local temp file
        try:
            os.unlink(tmp_path)
        except Exception as e:
            pass


@app.route("/download_report", methods=["POST"])
def download_report():
    analysis_data = request.json
    if not analysis_data:
        return jsonify({"error": "No analysis data provided"}), 400

    try:
        # Add generation date and create dynamic filename
        now = datetime.now()
        analysis_data['generated_date'] = now.strftime("%B %d, %Y at %I:%M %p")
        download_name = now.strftime("%B_%d_%H_%M_Speech_Score_Analysis.pdf")
        
        # Render the HTML template with the analysis data
        html_string = render_template('report.html', analysis=analysis_data)
        
        # Define the path to the CSS file
        css_path = os.path.join(os.path.dirname(__file__), 'static', 'css', 'report.css')
        
        # Generate PDF using WeasyPrint
        pdf_bytes = HTML(string=html_string, base_url=request.url_root).write_pdf(stylesheets=[CSS(css_path)])  # ✅ updated
        
        # Return the PDF as a downloadable file
        return send_file(
            io.BytesIO(pdf_bytes), # type: ignore
            as_attachment=True,
            download_name=download_name,
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({"error": "Failed to generate PDF report"}), 500


if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        print("⚠️  GEMINI_API_KEY not set — set it before starting.")
    print("🎙️  Speech Score running → http://localhost:8000")
    app.run(host="0.0.0.0", debug=True, port=8000)  # ✅ updated