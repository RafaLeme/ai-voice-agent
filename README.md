# 🤖 AI Voice Agent para SDR (Sales Development Representative)

Um AI Voice Agent completo e inteligente, incialmente focado em otimizar a prospecção de clientes para SDRs (Sales Development Representatives). Desenvolvido com Python (FastAPI) no backend e um frontend simples em HTML, CSS e JavaScript, este agente é capaz de interagir por voz, transcrever a fala, consultar uma base de conhecimento contextual (RAG) e gerar respostas faladas, adaptando-se ao seu negócio.

## ✨ Funcionalidades Principais (MVP)

* **Interação por Voz**: Captação de áudio diretamente do navegador.
* **Speech-to-Text (STT)**: Transcrição da fala do usuário para texto utilizando a API Whisper da OpenAI.
* **Retrieval-Augmented Generation (RAG)**: Geração de respostas contextuais e relevantes utilizando a base de conhecimento da empresa (catálogo de produtos, FAQs, etc.) com Langchain e um índice FAISS.
* **Large Language Model (LLM)**: Utiliza o `gpt-4o-mini` da OpenAI para gerar respostas inteligentes e com persona de SDR.
* **Text-to-Speech (TTS)**: Conversão da resposta do agente para áudio utilizando `gTTS`.
* **Comunicação Bidirecional**: Interação em tempo real via WebSockets entre frontend e backend.

## 🚀 Como Rodar o Projeto

Siga os passos abaixo para configurar e executar o projeto localmente.

### Pré-requisitos

Antes de começar, certifique-se de ter instalado:

* **Python 3.9+**: [Download Python](https://www.python.org/downloads/)
* **Git**: [Download Git](https://git-scm.com/downloads)
* **FFmpeg**: Essencial para a conversão de áudio no backend.
    * **Windows**: Baixe a versão `gpl` ou `lgpl` do [site oficial (Windows builds)](https://ffmpeg.org/download.html). Extraia o conteúdo e adicione o caminho da pasta `bin` do FFmpeg às variáveis de ambiente do sistema (`Path`).
    * **Linux (Debian/Ubuntu)**: `sudo apt update && sudo apt install ffmpeg`
    * **macOS (com Homebrew)**: `brew install ffmpeg`
    * **Verificação**: Abra um novo terminal e digite `ffmpeg -version`. Deve exibir informações da versão.

### Configuração e Execução

1.  **Clone o Repositório:**
    ```bash
    git clone <URL_DO_SEU_REPOSITORIO>
    cd ai-voice-sdr-agent # Ou o nome da sua pasta raiz
    ```

2.  **Crie e Ative o Ambiente Virtual:**
    É altamente recomendado usar um ambiente virtual para isolar as dependências do projeto.
    ```bash
    python -m venv venv
    ```
    * **Windows:**
        ```bash
        .\venv\Scripts\activate
        ```
    * **Linux/macOS:**
        ```bash
        source venv/bin/activate
        ```
    (Você verá `(venv)` no início da sua linha de comando, indicando que o ambiente está ativo.)

3.  **Instale as Dependências do Backend:**
    Certifique-se de que seu ambiente virtual esteja ativo antes de executar este comando.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure suas Variáveis de Ambiente:**
    * No diretório `backend/`, crie um arquivo chamado `.env`.
    * Dentro deste arquivo `.env`, adicione sua chave da API da OpenAI. **Substitua `sua_chave_aqui` pela sua chave real.**
        ```
        OPENAI_KEY="sk-sua_chave_aqui"
        ```
    * **Mantenha este arquivo `.env` fora do controle de versão do Git (ele já está no `.gitignore`).**

5.  **Prepare a Base de Conhecimento (RAG):**
    * No diretório `backend/data/`, adicione arquivos com conteudos para o RAG em  `.txt` preferencialmente, com o conteúdo que você deseja que o agente utilize para suas respostas (informações sobre produtos, serviços, FAQs, etc.). Quanto mais detalhado e relevante, melhor.
    * Com o ambiente virtual ativo, construa o índice FAISS a partir do seu `CatalogoProdutos.txt`. Este índice será usado para o RAG.
        ```bash
        cd backend
        python -c "from rag import build_index; build_index()"
        cd .. # Volte para a raiz do projeto
        ```
        Você verá a mensagem `[RAG] Índice salvo em: faiss_index` no console.

6.  **Inicie o Servidor Backend (FastAPI):**
    Abra um terminal, ative seu ambiente virtual e execute o Uvicorn na raiz do projeto:
    ```bash
    (venv) python -m uvicorn backend.main:tapp --reload --host 0.0.0.0 --port 8000
    ```
    Mantenha este terminal aberto. O servidor estará disponível em `http://localhost:8000`.

7.  **Inicie o Servidor Frontend:**
    Abra um **segundo terminal**, e **NÃO ative o ambiente virtual neste terminal**, pois o servidor HTTP Python é um utilitário de sistema. Navegue até a pasta `frontend/public`:
    ```bash
    cd frontend/public
    ```
    Então, inicie o servidor HTTP simples:
    ```bash
    python -m http.server 3000
    ```
    Mantenha este terminal aberto. O frontend estará disponível em `http://localhost:3000`.

8.  **Acesse a Aplicação:**
    Abra seu navegador web e acesse:
    ```
    http://localhost:3000
    ```

## 🎤 Como Usar (MVP)

1.  Com a página aberta em `http://localhost:3000`, clique no botão **"Iniciar"**.
2.  Se o navegador solicitar permissão para usar o microfone, **conceda a permissão**.
3.  Fale claramente no microfone, fazendo uma pergunta relacionada ao conteúdo que você inseriu no `CatalogoProdutos.txt`.
4.  Clique no botão **"Parar"**.
5.  O agente processará seu áudio e, após alguns segundos, você ouvirá a resposta sintetizada pelo agente diretamente no navegador.

## 🛠️ Tecnologias Utilizadas

* **Backend**: Python 3.x, FastAPI, Uvicorn
* **Frontend**: HTML, CSS, JavaScript (Vanilla JS para o core)
* **STT (Speech-to-Text)**: OpenAI Whisper API
* **LLM (Large Language Model)**: OpenAI GPT-4o-mini
* **RAG (Retrieval-Augmented Generation)**: Langchain, FAISS (para índice vetorial)
* **TTS (Text-to-Speech)**: gTTS
* **Manipulação de Áudio**: `pydub` (requer FFmpeg)
* **Variáveis de Ambiente**: `python-dotenv`
* **Comunicação**: WebSockets

## 🛣️ Próximos Passos e Melhorias Futuras

* **Integração com VOIP e Asterisk**: Conectar a solução a um número VOIP real através do Asterisk hospedado em Docker.
* **Streaming de Áudio Contínuo**: Implementar gravação e processamento de áudio em tempo real para uma conversação mais fluida, sem a necessidade de clicar "Iniciar/Parar" para cada turno.
* **Gerenciamento de Contexto da Conversa**: Adicionar memória à interação para que o agente possa manter o contexto em diálogos mais longos.
* **Feedback Visual no Frontend**: Melhorar a experiência do usuário com indicadores visuais de gravação, processamento e reprodução.
* **Modularização do RAG**: Refinar a estrutura de dados e as estratégias de recuperação para RAG.
* **Testes Abrangentes**: Expandir a suíte de testes para cobrir mais cenários e componentes da aplicação.

## 🤝 Contribuição

Contribuições são bem-vindas! Se você tiver ideias, melhorias ou encontrar bugs, sinta-se à vontade para abrir uma issue ou enviar um Pull Request.

---