import pytest
import asyncio

def test_websocket_voice_response(client):
    """
    Conecta ao endpoint /ws/voice via TestClient,
    envia bytes vazios e espera bytes de áudio de volta.
    """
    with client.websocket_connect("/ws/voice") as ws:
        ws.send_bytes(b"")
        data = ws.receive_bytes()
    assert isinstance(data, (bytes, bytearray))
    assert len(data) > 0