import os
from pathlib import Path
from dotenv import load_dotenv

dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

from elevenlabs.client import AsyncElevenLabs
from elevenlabs.types import Voice, VoiceSettings

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

elevenlabs_client = None
if ELEVENLABS_API_KEY:
    try:
        elevenlabs_client = AsyncElevenLabs(api_key=ELEVENLABS_API_KEY)
        print("DEBUG TTS: Cliente AsyncElevenLabs inicializado com sucesso.")
    except Exception as e:
        print(f"ERROR: Erro ao inicializar cliente AsyncElevenLabs: {e}")
else:
    print("AVISO: ELEVENLABS_API_KEY não definida. O TTS ElevenLabs não funcionará.")

async def synthesize_tts(text: str) -> bytes:
    if not elevenlabs_client:
        print("ERROR: Cliente ElevenLabs não inicializado. Verifique a API Key.")
        return b""
    
    try:
        audio_bytes = elevenlabs_client.text_to_speech.convert(
            voice_id="GnDrTQvdzZ7wqAKfLzVQ",
            output_format="mp3_44100_128",
            text=text,
            model_id="eleven_multilingual_v2",
        )
        all_audio_bytes = b""
        async for chunk in audio_bytes:
            all_audio_bytes += chunk
            
        return all_audio_bytes
    except Exception as e:
        print(f"ERROR: Erro ao gerar áudio com ElevenLabs: {e}")
        return b""
