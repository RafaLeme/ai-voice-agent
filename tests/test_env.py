import os
from pathlib import Path
from dotenv import load_dotenv

print(f"Diretório de trabalho atual: {os.getcwd()}")
dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)
print(f"Valor de OPENAI_KEY após load_dotenv: {os.getenv('OPENAI_KEY')}")