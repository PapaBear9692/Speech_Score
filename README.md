# 🎙️ SpeakPro — AI Speech Delivery Coach (v2)

Uses the **latest `google-genai` SDK** (`from google import genai`) with the
`client.files.upload()` Files API pattern — exactly as shown in Google's
current documentation.

## Install & Run

```bash
pip install -r requirements.txt

export GEMINI_API_KEY="your-key-here"   # from https://aistudio.google.com

python app.py
# → http://localhost:5000
```

## SDK Pattern Used

```python
from google import genai
from google.genai import types

client = genai.Client()           # picks up GEMINI_API_KEY automatically

# 1. Upload audio via Files API
uploaded = client.files.upload(
    file="path/to/audio.mp3",
    config=types.UploadFileConfig(mime_type="audio/mp3"),
)

# 2. Pass file object directly into generate_content
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=["Analyse this speech", uploaded],
)

print(response.text)

# 3. Clean up
client.files.delete(name=uploaded.name)
```

> **Want gemini-3-flash-preview?**  
> Change `MODEL = "gemini-2.5-flash"` → `MODEL = "gemini-3-flash-preview"` in
> `app.py` if you have preview access in AI Studio.

## Supported Audio Formats
mp3 · wav · webm · m4a · ogg · flac · aac

## What Gets Analysed
| Dimension | What Gemini evaluates |
|---|---|
| Clarity | Articulation, diction, pronunciation |
| Tone & Confidence | Authority, energy, conviction |
| Pacing | Speed, natural pauses, rhythm |
| Product Knowledge | Accuracy and depth |
| Persuasiveness | CTA, benefit-focused language |
| Vocabulary | Word choice, jargon use |

Plus: full transcript, filler word detection, top strengths, actionable
improvement suggestions, energy level, and a single "next focus" tip.