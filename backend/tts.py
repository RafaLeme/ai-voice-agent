from gtts import gTTS
from io import BytesIO

def synthesize_tts(text: str) -> bytes:
    buf = BytesIO()
    tts = gTTS(text=text, lang="pt")
    tts.write_to_fp(buf)
    return buf.getvalue()
