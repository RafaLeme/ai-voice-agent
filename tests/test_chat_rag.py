import pytest
import asyncio
from backend.main import chat_rag
import backend.main as main_module

class DummyDoc:
    page_content = "conteúdo de teste"

@pytest.fixture(autouse=True)
def mock_query_and_client(monkeypatch):
    # Mocka a função query_index usada em backend.main
    monkeypatch.setattr(main_module, "query_index", lambda text: [DummyDoc()])
    # Mocka o cliente OpenAI presente em backend.main
    class DummyClient:
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    class Resp:
                        def __init__(self):
                            self.choices = [type("C", (), {"message": type("M", (), {"content": "resposta teste"})})()]
                    return Resp()
    monkeypatch.setattr(main_module, "client", DummyClient())

@pytest.mark.asyncio
async def test_chat_rag_returns_mock():
    # Executa a função chat_rag com dados mockados
    result = await chat_rag("pergunta qualquer")
    assert "resposta teste" in result, f"Esperado 'resposta teste', mas obteve: {result}"
