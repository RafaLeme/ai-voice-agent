from backend.tts import synthesize_tts

def test_synthesize_tts_returns_valid_mp3():
    mp3 = synthesize_tts("Olá, teste")
    # Header MP3 padrão: 'ID3' ou bytes de frame 0xFFFB
    assert isinstance(mp3, (bytes, bytearray))
    assert len(mp3) > 1000
    assert mp3.startswith(b"ID3") or mp3[0] == 0xFF
