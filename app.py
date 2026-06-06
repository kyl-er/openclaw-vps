import os, tempfile
from flask import Flask, request, render_template_string
import yt_dlp, whisper

app = Flask(__name__)

PAGE = """<!doctype html><html><head><style>
body{font-family:monospace;max-width:700px;margin:40px auto;padding:0 16px}
input{width:100%;box-sizing:border-box;padding:6px;margin:6px 0}
pre{white-space:pre-wrap;background:#f4f4f4;padding:12px}
.err{color:red}
</style></head><body>
<h2>Facebook Reels → Transcript</h2>
<form method=post>
  <input name=url placeholder="https://www.facebook.com/reel/..." required>
  <button>Transcribe</button>
</form>
{% if transcript %}<pre>{{ transcript }}</pre>{% endif %}
{% if error %}<p class=err>{{ error }}</p>{% endif %}
</body></html>"""

@app.route("/", methods=["GET", "POST"])
def index():
    transcript = error = None
    if request.method == "POST":
        url = request.form["url"].strip()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": f"{tmp}/audio.%(ext)s",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "96",
                    }],
                    "quiet": True,
                    "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                audio_path = f"{tmp}/audio.mp3"
                model = whisper.load_model("base")
                result = model.transcribe(audio_path)

            transcript = f"## Transcript\n\n{result['text'].strip()}"
        except Exception as e:
            error = str(e)

    return render_template_string(PAGE, transcript=transcript, error=error)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
