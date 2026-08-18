# Video Transcript App — Agent Rebuild Spec

## What this app does

A minimal Flask web app that accepts a video URL and returns a plain-text transcript. Supports YouTube and Facebook Reels (and any platform yt-dlp handles).

## Transcription strategy (platform-aware)

| Platform | Method | Why |
|---|---|---|
| YouTube | `youtube-transcript-api` | Fetches YouTube's own captions — instant, no audio download |
| Facebook Reels / everything else | `yt-dlp` + local `openai-whisper` | No caption API exists; download audio and run Whisper `base` model locally |

YouTube URLs are detected by regex before any network call is made. Non-YouTube falls through to Whisper.

## Network requirements

Both platforms require outbound HTTPS. In a proxied/restricted environment (e.g. Claude Code cloud container on "Trusted" network), facebook.com and youtube.com are blocked at the CONNECT tunnel level. Set network access to **Full** (or add the domains below to a Custom allowlist) before deploying:

```
facebook.com
*.facebook.com
*.fbcdn.net
*.facebook.net
youtube.com
*.youtube.com
*.googlevideo.com
```

## Runtime requirements

- Python 3.11+
- ffmpeg (system package — required by yt-dlp for audio extraction)
- Whisper `base` model downloads ~145 MB on first transcription (cached at `~/.cache/whisper/`)

## Dependencies (`requirements.txt`)

```
flask
yt-dlp
openai-whisper
youtube-transcript-api
```

Install:
```bash
pip install -r requirements.txt
```

## Complete source (`app.py`)

```python
import os, re, tempfile
from flask import Flask, request, render_template_string
import yt_dlp, whisper
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__)

PAGE = """<!doctype html><html><head><style>
body{font-family:monospace;max-width:700px;margin:40px auto;padding:0 16px}
input{width:100%;box-sizing:border-box;padding:6px;margin:6px 0}
pre{white-space:pre-wrap;background:#f4f4f4;padding:12px}
.err{color:red}
.meta{color:#888;font-size:.85em;margin-bottom:4px}
</style></head><body>
<h2>Video → Transcript</h2>
<p class=meta>Supports YouTube, Facebook Reels, and most video platforms.</p>
<form method=post>
  <input name=url placeholder="https://youtu.be/... or https://www.facebook.com/reel/..." required>
  <button>Transcribe</button>
</form>
{% if src %}<p class=meta>Source: {{ src }}</p>{% endif %}
{% if transcript %}<pre>{{ transcript }}</pre>{% endif %}
{% if error %}<p class=err>{{ error }}</p>{% endif %}
</body></html>"""

YT_RE = re.compile(r'(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})')


def _youtube_transcript(video_id):
    api = YouTubeTranscriptApi()
    segments = api.fetch(video_id)
    return " ".join(seg.text for seg in segments)


def _whisper_transcribe(url, tmp):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{tmp}/audio.%(ext)s",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "96"}],
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    model = whisper.load_model("base")
    result = model.transcribe(f"{tmp}/audio.mp3")
    return result["text"].strip()


@app.route("/", methods=["GET", "POST"])
def index():
    transcript = error = src = None
    if request.method == "POST":
        url = request.form["url"].strip()
        try:
            yt_match = YT_RE.search(url)
            if yt_match:
                transcript = _youtube_transcript(yt_match.group(1))
                src = "YouTube transcript API"
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    transcript = _whisper_transcribe(url, tmp)
                src = "Whisper (local)"
        except Exception as e:
            error = str(e)

    return render_template_string(PAGE, transcript=transcript, error=error, src=src)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
```

## Run

```bash
# Dev
python app.py

# Production (Gunicorn — needs long timeout for Whisper inference)
gunicorn -w 1 -b 0.0.0.0:5000 --timeout 300 app:app
```

## Known issues / next steps

- **Whisper load time**: `whisper.load_model("base")` is called on every request. Cache the model at module level for a persistent server.
- **Concurrency**: `openai-whisper` uses CPU by default; run with `-w 1` to avoid contention. Use `faster-whisper` for 2–4× speed improvement.
- **Facebook auth**: Public Reels work without cookies. Private or age-gated content requires passing a `cookiefile` to yt-dlp.
- **YouTube auth**: `youtube-transcript-api` works without credentials for videos with public captions. Videos with disabled captions will raise `TranscriptsDisabled`.
