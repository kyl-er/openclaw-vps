import os, tempfile, glob as glob_mod
from flask import Flask, request, render_template_string
import yt_dlp, whisper

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


def _fetch_subtitles(url, tmp):
    """Try to pull auto-generated or manual captions via yt-dlp. Returns text or None."""
    ydl_opts = {
        "skip_download": True,
        "writeautomaticsub": True,
        "writesubtitles": True,
        "subtitleslangs": ["en", "en-US", "en-GB"],
        "subtitlesformat": "vtt",
        "outtmpl": f"{tmp}/sub",
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    vtt_files = glob_mod.glob(f"{tmp}/*.vtt")
    if not vtt_files:
        return None

    lines, prev = [], ""
    for line in open(vtt_files[0], encoding="utf-8"):
        line = line.strip()
        if (not line or line.startswith("WEBVTT") or line.startswith("NOTE")
                or "-->" in line or line[0].isdigit()):
            continue
        if line != prev:
            lines.append(line)
            prev = line
    return " ".join(lines) if lines else None


def _transcribe_audio(url, tmp):
    """Download audio and run local Whisper. Returns (text, duration_s)."""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{tmp}/audio.%(ext)s",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "96"}],
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        duration = info.get("duration", 0)

    model = whisper.load_model("base")
    result = model.transcribe(f"{tmp}/audio.mp3")
    return result["text"].strip(), duration


@app.route("/", methods=["GET", "POST"])
def index():
    transcript = error = src = None
    if request.method == "POST":
        url = request.form["url"].strip()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                text = _fetch_subtitles(url, tmp)
                if text:
                    src = "auto-generated captions"
                    transcript = text
                else:
                    text, _ = _transcribe_audio(url, tmp)
                    src = "Whisper (local)"
                    transcript = text
        except Exception as e:
            error = str(e)

    return render_template_string(PAGE, transcript=transcript, error=error, src=src)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
