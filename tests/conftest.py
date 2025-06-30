import os
import pytest
from fastapi.testclient import TestClient
from backend.main import tapp

@pytest.fixture(scope="session")
def client():
    os.environ["OPENAI_KEY"] = "sk-test"  # se você fizer mocks
    return TestClient(tapp)
