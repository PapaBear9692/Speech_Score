import os
import json
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string
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
    return render_template_string(HTML_TEMPLATE)


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


# ─── Frontend ──────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SpeakPro — Speech Delivery Coach</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:        #07070e;
    --surface:   #0f0f1a;
    --surface2:  #171726;
    --border:    #252538;
    --accent:    #7c6eff;
    --accent2:   #ff6b8a;
    --green:     #3ee8a0;
    --yellow:    #fbbf24;
    --text:      #ddddf5;
    --muted:     #6868a0;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* Subtle dot-grid background */
  body::before {
    content: '';
    position: fixed; inset: 0;
    background-image: radial-gradient(circle, rgba(124,110,255,.12) 1px, transparent 1px);
    background-size: 32px 32px;
    pointer-events: none; z-index: 0;
  }

  .wrap { max-width: 980px; margin: 0 auto; padding: 0 24px; position: relative; z-index: 1; }

  /* ── Header ── */
  header { padding: 48px 0 36px; display: flex; align-items: center; gap: 16px; }
  .logo {
    width: 52px; height: 52px; border-radius: 16px;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    display: flex; align-items: center; justify-content: center; font-size: 24px;
    box-shadow: 0 0 32px rgba(124,110,255,.35);
  }
  .brand h1 { font-family: 'Syne', sans-serif; font-size: 26px; font-weight: 800; letter-spacing: -.5px; }
  .brand p  { font-size: 13px; color: var(--muted); }

  .pill {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 500;
    background: rgba(124,110,255,.12); border: 1px solid rgba(124,110,255,.25);
    color: var(--accent); margin-left: auto;
  }

  /* ── Notice ── */
  .notice {
    background: rgba(124,110,255,.07); border: 1px solid rgba(124,110,255,.2);
    border-radius: 12px; padding: 13px 18px; font-size: 13px; color: var(--muted);
    margin-bottom: 28px; display: flex; align-items: center; gap: 10px;
  }

  /* ── Card ── */
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 20px; padding: 32px; margin-bottom: 20px;
  }
  .card h2 { font-family: 'Syne', sans-serif; font-size: 18px; font-weight: 700; margin-bottom: 6px; }
  .card .sub { font-size: 14px; color: var(--muted); margin-bottom: 26px; line-height: 1.6; }
  .card h3 {
    font-family: 'Syne', sans-serif; font-size: 12px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1.2px; color: var(--muted); margin-bottom: 16px;
  }

  /* ── Context field ── */
  .field { margin-bottom: 26px; }
  .field label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 7px; font-weight: 500; }
  .field textarea {
    width: 100%; background: var(--surface2); border: 1px solid var(--border);
    border-radius: 10px; padding: 12px 16px; color: var(--text);
    font-family: 'DM Sans', sans-serif; font-size: 14px;
    resize: vertical; min-height: 72px; outline: none; transition: border-color .2s;
  }
  .field textarea:focus { border-color: var(--accent); }

  /* ── Buttons ── */
  .btn {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 11px 22px; border-radius: 10px; font-family: 'DM Sans', sans-serif;
    font-size: 14px; font-weight: 500; cursor: pointer; border: none; transition: all .2s;
  }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-primary:hover:not(:disabled) { background: #6a5ee0; transform: translateY(-1px); box-shadow: 0 8px 24px rgba(124,110,255,.3); }
  .btn-danger  { background: var(--accent2); color: #fff; }
  .btn-danger:hover:not(:disabled) { background: #e05572; }
  .btn-ghost   { background: transparent; border: 1px solid var(--border); color: var(--text); }
  .btn-ghost:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .btn:disabled { opacity: .38; cursor: not-allowed; transform: none !important; }

  /* ── Controls row ── */
  .controls { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }

  .rec-ind { display: none; align-items: center; gap: 8px; font-size: 13px; color: var(--accent2); font-weight: 500; }
  .rec-ind.on { display: flex; }
  .rec-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent2); animation: blink 1s infinite; }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }

  /* ── Waveform ── */
  .wave-wrap { margin-top: 20px; display: none; }
  .wave-wrap.on { display: block; }
  #waveform { width: 100%; height: 64px; border-radius: 10px; border: 1px solid var(--border); background: var(--surface2); display: block; }

  /* ── Drop zone ── */
  .dropzone {
    margin-top: 20px; border: 2px dashed var(--border); border-radius: 12px;
    padding: 22px; text-align: center; cursor: pointer; transition: all .2s;
  }
  .dropzone:hover, .dropzone.over { border-color: var(--accent); background: rgba(124,110,255,.05); }
  .dropzone p { font-size: 13px; color: var(--muted); }
  #fileInput { display: none; }

  /* ── Loader ── */
  .loader { display: none; flex-direction: column; align-items: center; gap: 14px; padding: 56px; }
  .loader.on { display: flex; }
  .spinner { width: 40px; height: 40px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin .75s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loader p { font-size: 14px; color: var(--muted); }

  /* ── Error ── */
  .err { display: none; background: rgba(255,107,138,.08); border: 1px solid rgba(255,107,138,.3); border-radius: 12px; padding: 14px 18px; font-size: 13px; color: var(--accent2); margin-bottom: 16px; }
  .err.on { display: block; }

  /* ── Results ── */
  #results { display: none; }

  /* Score hero */
  .score-hero {
    display: flex; align-items: center; gap: 40px; flex-wrap: wrap;
    padding: 40px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 20px; margin-bottom: 20px;
  }
  .ring { position: relative; width: 140px; height: 140px; flex-shrink: 0; }
  .ring svg { transform: rotate(-90deg); }
  .ring circle { fill: none; stroke-width: 10; }
  .ring .track { stroke: var(--surface2); }
  .ring .fill { stroke: var(--accent); stroke-linecap: round; transition: stroke-dashoffset 1.2s cubic-bezier(.4,0,.2,1); }
  .ring-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
  .ring-num { font-family: 'Syne', sans-serif; font-size: 40px; font-weight: 800; line-height: 1; }
  .ring-lbl { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }
  .score-info { flex: 1; min-width: 200px; }
  .score-info h2 { font-family: 'Syne', sans-serif; font-size: 22px; font-weight: 700; margin-bottom: 10px; }
  .score-info .imp { font-size: 14px; color: var(--muted); line-height: 1.75; margin-bottom: 16px; }
  .badge { display: inline-flex; align-items: center; gap: 6px; padding: 5px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }
  .badge-high   { background: rgba(62,232,160,.12); color: var(--green); }
  .badge-medium { background: rgba(251,191,36,.12);  color: var(--yellow); }
  .badge-low    { background: rgba(255,107,138,.12); color: var(--accent2); }

  /* Focus strip */
  .focus {
    display: flex; align-items: center; gap: 16px;
    padding: 22px 28px; border-radius: 16px; margin-bottom: 20px;
    background: linear-gradient(135deg,rgba(124,110,255,.12),rgba(255,107,138,.06));
    border: 1px solid rgba(124,110,255,.25);
  }
  .focus-ico { width: 44px; height: 44px; border-radius: 12px; background: var(--accent); display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
  .focus-txt h3 { font-family: 'Syne', sans-serif; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; color: var(--accent); margin-bottom: 4px; }
  .focus-txt p { font-size: 14px; line-height: 1.6; }

  /* Grid */
  .g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
  @media(max-width:640px) { .g2 { grid-template-columns: 1fr; } .score-hero { flex-direction: column; } }

  /* Dimension bars */
  .dim { margin-bottom: 15px; }
  .dim-row { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 5px; }
  .dim-name { font-weight: 500; }
  .dim-sc { font-family: 'Syne', sans-serif; font-weight: 700; }
  .bar { height: 5px; background: var(--surface2); border-radius: 3px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 3px; transition: width 1s cubic-bezier(.4,0,.2,1); }

  /* Transcript */
  .transcript { background: var(--surface2); border-radius: 10px; padding: 16px; font-size: 14px; line-height: 1.8; max-height: 170px; overflow-y: auto; font-style: italic; color: #bbbbd5; }

  /* Tags */
  .tags { display: flex; flex-wrap: wrap; gap: 8px; }
  .tag { padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; }
  .tag-g { background: rgba(62,232,160,.1);   color: var(--green);   border: 1px solid rgba(62,232,160,.2); }
  .tag-y { background: rgba(251,191,36,.1);    color: var(--yellow);  border: 1px solid rgba(251,191,36,.2); font-family: monospace; font-size: 11px; }

  /* Improvements */
  .imp-item { border-left: 3px solid var(--accent2); padding: 12px 16px; background: var(--surface2); border-radius: 0 10px 10px 0; margin-bottom: 12px; }
  .imp-item h4 { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
  .imp-item p { font-size: 13px; color: var(--muted); line-height: 1.65; margin-bottom: 6px; }
  .imp-item .sug { font-size: 12px; color: var(--accent); font-weight: 500; }

  .footer { text-align: center; padding: 32px 0 52px; }
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="logo">🎙️</div>
    <div class="brand">
      <h1>SpeakPro</h1>
      <p>AI-Powered Speech Delivery Coach</p>
    </div>
    <span class="pill">⚡ Gemini 2.5 Flash</span>
  </header>

  <div class="notice">
    ⚙️ Requires <strong>GEMINI_API_KEY</strong> environment variable · Uses <code>google-genai</code> SDK with <code>client.files.upload()</code>
  </div>

  <!-- ── Record section ── -->
  <div id="recSection">
    <div class="card">
      <h2>Practice Your Pitch</h2>
      <p class="sub">Record live or upload an audio file. Gemini analyzes the raw audio natively — words, tone, pacing, confidence and more — no separate speech-to-text needed.</p>

      <div class="field">
        <label>Product / Context (optional)</label>
        <textarea id="ctx" placeholder="e.g. 2-minute elevator pitch for our SaaS analytics platform targeting mid-market finance teams…"></textarea>
      </div>

      <div class="controls">
        <button class="btn btn-primary" id="startBtn" onclick="startRec()">⏺ Start Recording</button>
        <button class="btn btn-danger"  id="stopBtn"  onclick="stopRec()" disabled>⏹ Stop</button>
        <div class="rec-ind" id="recInd"><div class="rec-dot"></div><span id="recTime">0:00</span></div>
      </div>

      <div class="wave-wrap" id="waveWrap"><canvas id="waveform" width="900" height="64"></canvas></div>

      <div class="dropzone" id="dropzone"
        onclick="document.getElementById('fileInput').click()"
        ondragover="event.preventDefault(); this.classList.add('over')"
        ondragleave="this.classList.remove('over')"
        ondrop="onDrop(event)">
        <input type="file" id="fileInput" accept="audio/*" onchange="onFile(event)">
        <p>📁 Or drag & drop / click to upload an audio file (mp3, wav, webm, m4a, ogg, flac)</p>
      </div>
    </div>

    <div class="err" id="errBox"></div>
    <div class="loader" id="loader">
      <div class="spinner"></div>
      <p>Uploading & analysing with Gemini 2.5 Flash…</p>
    </div>
  </div>

  <!-- ── Results ── -->
  <div id="results">

    <div class="score-hero">
      <div class="ring">
        <svg width="140" height="140" viewBox="0 0 140 140">
          <circle class="track" cx="70" cy="70" r="60"/>
          <circle class="fill" id="ringFill" cx="70" cy="70" r="60" stroke-dasharray="377" stroke-dashoffset="377"/>
        </svg>
        <div class="ring-center">
          <div class="ring-num" id="ringNum">—</div>
          <div class="ring-lbl">/ 100</div>
        </div>
      </div>
      <div class="score-info">
        <h2>Analysis Complete</h2>
        <p class="imp" id="impression">—</p>
        <span class="badge" id="energyBadge">—</span>
      </div>
    </div>

    <div class="focus">
      <div class="focus-ico">🎯</div>
      <div class="focus-txt">
        <h3>Next Practice Focus</h3>
        <p id="nextFocus">—</p>
      </div>
    </div>

    <div class="g2">
      <div class="card">
        <h3>Performance Dimensions</h3>
        <div id="dims"></div>
      </div>
      <div class="card">
        <h3>Transcript</h3>
        <div class="transcript" id="transcript">—</div>
      </div>
    </div>

    <div class="g2">
      <div class="card">
        <h3>✅ Strengths</h3>
        <div class="tags" id="strengths"></div>
      </div>
      <div class="card">
        <h3>🔤 Filler Words</h3>
        <p style="font-size:13px;color:var(--muted);margin-bottom:10px" id="fillerNote">—</p>
        <div class="tags" id="fillerTags"></div>
      </div>
    </div>

    <div class="card">
      <h3>💡 Suggestions for Improvement</h3>
      <div id="improvements"></div>
    </div>

    <div class="footer">
      <button class="btn btn-ghost" onclick="reset()">🔄 Practice Again</button>
    </div>
  </div>

</div><!-- /wrap -->

<script>
let recorder, stream, analyser, animId, timer, recSecs = 0, chunks = [];

async function startRec() {
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { return showErr("Microphone access denied."); }

  // Visualiser
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  analyser = ctx.createAnalyser(); analyser.fftSize = 256;
  src.connect(analyser);
  document.getElementById('waveWrap').classList.add('on');
  drawWave();

  recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
  chunks = [];
  recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
  recorder.onstop = () => submit(new Blob(chunks, { type: 'audio/webm' }), 'recording.webm');
  recorder.start(100);

  document.getElementById('startBtn').disabled = true;
  document.getElementById('stopBtn').disabled  = false;
  document.getElementById('recInd').classList.add('on');
  recSecs = 0;
  timer = setInterval(() => {
    recSecs++;
    document.getElementById('recTime').textContent =
      Math.floor(recSecs/60) + ':' + String(recSecs%60).padStart(2,'0');
  }, 1000);
}

function stopRec() {
  recorder?.stop();
  stream?.getTracks().forEach(t => t.stop());
  clearInterval(timer);
  cancelAnimationFrame(animId);
  document.getElementById('recInd').classList.remove('on');
  document.getElementById('startBtn').disabled = false;
  document.getElementById('stopBtn').disabled  = true;
}

function drawWave() {
  const canvas = document.getElementById('waveform');
  const c = canvas.getContext('2d');
  const buf = new Uint8Array(analyser.frequencyBinCount);
  (function loop() {
    animId = requestAnimationFrame(loop);
    analyser.getByteTimeDomainData(buf);
    c.fillStyle = '#171726'; c.fillRect(0,0,canvas.width,canvas.height);
    c.strokeStyle = '#7c6eff'; c.lineWidth = 2; c.beginPath();
    const step = canvas.width / buf.length;
    buf.forEach((v, i) => {
      const y = (v/128) * canvas.height / 2;
      i ? c.lineTo(i*step, y) : c.moveTo(0, y);
    });
    c.stroke();
  })();
}

function onFile(e)  { const f = e.target.files[0]; if (f) submit(f, f.name); }
function onDrop(e)  {
  e.preventDefault(); document.getElementById('dropzone').classList.remove('over');
  const f = e.dataTransfer.files[0];
  if (f && f.type.startsWith('audio/')) submit(f, f.name);
}

async function submit(blob, name) {
  clearErr();
  document.getElementById('loader').classList.add('on');
  document.getElementById('dropzone').style.display = 'none';

  const fd = new FormData();
  fd.append('audio', blob, name);
  fd.append('product_context', document.getElementById('ctx').value);

  try {
    const res  = await fetch('/analyze', { method: 'POST', body: fd });
    const data = await res.json();
    document.getElementById('loader').classList.remove('on');
    if (data.error) { showErr(data.error); document.getElementById('dropzone').style.display=''; return; }
    render(data.analysis);
  } catch(e) {
    document.getElementById('loader').classList.remove('on');
    showErr('Network error: ' + e.message);
    document.getElementById('dropzone').style.display = '';
  }
}

function render(a) {
  document.getElementById('recSection').style.display = 'none';
  document.getElementById('results').style.display = 'block';

  // Score ring
  const score = a.overall_score ?? 0;
  const circ  = 377;
  const col   = score >= 75 ? '#3ee8a0' : score >= 50 ? '#fbbf24' : '#ff6b8a';
  const fill  = document.getElementById('ringFill');
  setTimeout(() => { fill.style.strokeDashoffset = circ - (score/100)*circ; }, 80);
  fill.style.stroke = col;
  document.getElementById('ringNum').textContent = score;
  document.getElementById('ringNum').style.color = col;

  document.getElementById('impression').textContent = a.overall_impression ?? '';

  const en = (a.energy_level ?? 'medium').toLowerCase();
  const eb = document.getElementById('energyBadge');
  eb.textContent = '⚡ ' + en.charAt(0).toUpperCase() + en.slice(1) + ' Energy';
  eb.className = 'badge badge-' + en;

  document.getElementById('nextFocus').textContent = a.next_practice_focus ?? '';

  // Dimensions
  const dimLabels = {
    clarity:          'Clarity',
    tone_confidence:  'Tone & Confidence',
    pacing:           'Pacing',
    product_knowledge:'Product Knowledge',
    persuasiveness:   'Persuasiveness',
    vocabulary:       'Vocabulary',
  };
  const dims = document.getElementById('dims');
  dims.innerHTML = '';
  for (const [k, label] of Object.entries(dimLabels)) {
    const d  = (a.dimensions ?? {})[k] ?? {};
    const sc = d.score ?? 0;
    const c  = sc >= 75 ? '#3ee8a0' : sc >= 50 ? '#fbbf24' : '#ff6b8a';
    dims.innerHTML += `
      <div class="dim" title="${d.feedback ?? ''}">
        <div class="dim-row">
          <span class="dim-name">${label}</span>
          <span class="dim-sc" style="color:${c}">${sc}</span>
        </div>
        <div class="bar"><div class="bar-fill" style="width:0%;background:${c}" data-w="${sc}%"></div></div>
      </div>`;
  }
  setTimeout(() => { document.querySelectorAll('.bar-fill').forEach(el => el.style.width = el.dataset.w); }, 150);

  document.getElementById('transcript').textContent = a.transcript ?? 'No transcript available.';

  document.getElementById('strengths').innerHTML =
    (a.strengths ?? []).map(s => `<span class="tag tag-g">✓ ${s}</span>`).join('');

  const fw = a.filler_words ?? {};
  document.getElementById('fillerNote').textContent =
    `Detected ${fw.count ?? 0} filler occurrence(s). ${fw.feedback ?? ''}`;
  document.getElementById('fillerTags').innerHTML =
    (fw.words ?? []).slice(0, 15).map(w => `<span class="tag tag-y">${w}</span>`).join('');

  document.getElementById('improvements').innerHTML =
    (a.improvements ?? []).map(i => `
      <div class="imp-item">
        <h4>${i.issue}</h4>
        <p>${i.detail}</p>
        <div class="sug">💡 ${i.suggestion}</div>
      </div>`).join('');
}

function reset() {
  document.getElementById('results').style.display    = 'none';
  document.getElementById('recSection').style.display = 'block';
  document.getElementById('dropzone').style.display   = '';
  document.getElementById('fileInput').value          = '';
  document.getElementById('waveWrap').classList.remove('on');
  chunks = [];
}

function showErr(msg) { const e = document.getElementById('errBox'); e.textContent = msg; e.classList.add('on'); }
function clearErr()   { document.getElementById('errBox').classList.remove('on'); }
</script>
</body>
</html>
"""

if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        print("⚠️  GEMINI_API_KEY not set — set it before starting.")
    print("🎙️  SpeakPro running → http://localhost:5000")
    app.run(debug=True, port=5000)