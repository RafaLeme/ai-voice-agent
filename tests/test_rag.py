from backend.rag import build_index, query_index
import os
import shutil

DATA_DIR = "backend/data"
INDEX_DIR = "backend/faiss_index"

def test_build_and_query_index(tmp_path):
    # Copia alguns arquivos de 'data' para tmp_path
    src = os.path.join(DATA_DIR, "CatalogoProdutos.txt")
    dst = tmp_path / "CatalogoProdutos.txt"
    shutil.copy(src, dst)

    # Constrói índice em pasta temporária
    build_index(data_dir=str(tmp_path), index_path=str(tmp_path / "idx"))
    # Deve retornar pelo menos um documento
    results = query_index("linhas de implantes", k=1)
    assert len(results) == 1
    assert "Linha Zero" in results[0].page_content

def teardown_module(module):
    # Limpeza opcional
    if os.path.isdir(INDEX_DIR):
        shutil.rmtree(INDEX_DIR)
