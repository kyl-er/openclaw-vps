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
