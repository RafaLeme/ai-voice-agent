import os
from pathlib import Path
from dotenv import load_dotenv

dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

# LangChain imports
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# Carrega variáveis de ambiente do arquivo .env
OPENAI_KEY = os.getenv("OPENAI_KEY")
if not OPENAI_KEY:
    raise ValueError("Defina OPENAI_KEY no arquivo .env antes de usar o RAG")

# Inicializa embeddings com a chave válida
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_KEY)

# Caminho padrão do índice FAISS
INDEX_PATH = Path(__file__).parent / "faiss_index"


def build_index(data_dir="data", index_path: Path = None): # Mude o tipo para Path
    """
    Lê todos os arquivos .txt em `data_dir`, indexa em FAISS e salva em `index_path`.
    Se `index_path` for None, usa o INDEX_PATH global.
    """
    # Garante que data_dir também seja um caminho absoluto se necessário
    abs_data_dir = Path(__file__).parent / data_dir

    # O index_path aqui já deve ser absoluto ou se tornará o INDEX_PATH global
    final_index_path = index_path if index_path else INDEX_PATH

    docs = []
    for txt_file in abs_data_dir.rglob("*.txt"):
        text = txt_file.read_text(encoding="utf-8", errors="ignore")
        docs.append(Document(page_content=text, metadata={"source": str(txt_file)}))

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_documents(docs)

    store = FAISS.from_documents(chunks, embeddings)
    store.save_local(str(final_index_path)) # Salva usando o caminho absoluto
    print(f"[RAG] Índice salvo em: {final_index_path}")


def load_index(index_path: Path = None): # Mude o tipo para Path
    """
    Carrega o índice FAISS de `index_path` (ou do INDEX_PATH se None), permitindo deserialização perigosa.
    """
    # O caminho de carga também deve ser absoluto
    path_to_load = index_path if index_path else INDEX_PATH
    return FAISS.load_local(
        str(path_to_load), # Passa o caminho absoluto como string
        embeddings,
        allow_dangerous_deserialization=True
    )


def query_index(text: str, k: int = 3, index_path: Path = None): # Mude o tipo para Path
    """
    Retorna os k documentos mais similares ao `text`, usando o índice especificado.
    """
    store = load_index(index_path)
    return store.similarity_search(text, k=k)
