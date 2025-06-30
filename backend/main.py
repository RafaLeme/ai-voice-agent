import os
from pathlib import Path
from dotenv import load_dotenv

dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

import asyncio
from io import BytesIO
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from backend.rag import query_index
from backend.tts import synthesize_tts

from pydub import AudioSegment

# Inicializa app FastAPI
tapp = FastAPI()
tapp.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializa cliente OpenAI
OPENAI_KEY = os.getenv("OPENAI_KEY")
if not OPENAI_KEY:
    raise ValueError("Defina OPENAI_KEY no .env antes de iniciar o servidor")
client = OpenAI(api_key=OPENAI_KEY)

def convert_webm_to_wav(webm_bytes: bytes) -> bytes:
    """
    Converte um stream de áudio WebM para um stream de áudio WAV.
    Usa pydub, que depende de ffmpeg.
    Garanti que o WAV resultante seja mono, 16kHz.
    """
    # --- DEBUG: Salvar o áudio WebM recebido ---
    try:
        with open("received_audio.webm", "wb") as f:
            f.write(webm_bytes)
        print("INFO DEBUG: Áudio WebM recebido salvo como received_audio.webm")
    except Exception as e:
        print(f"WARN DEBUG: Não foi possível salvar received_audio.webm: {e}")
    # --- FIM DEBUG ---

    try:
        audio = AudioSegment.from_file(BytesIO(webm_bytes), format="webm")
        
        # PADRONIZAR O ÁUDIO PARA WHISPER: mono e 16kHz
        if audio.channels > 1:
            audio = audio.set_channels(1) # Converter para mono
            print("INFO DEBUG: Áudio convertido para mono.")
        if audio.frame_rate != 16000:
            audio = audio.set_frame_rate(16000) # Converter para 16kHz
            print("INFO DEBUG: Áudio convertido para 16kHz.")

        wav_buffer = BytesIO()
        audio.export(wav_buffer, format="wav")
        
        # --- DEBUG: Salvar o áudio WAV convertido ---
        with open("converted_audio.wav", "wb") as f:
            f.write(wav_buffer.getvalue())
        print("INFO DEBUG: Áudio WAV convertido salvo como converted_audio.wav")
        # --- FIM DEBUG ---

        return wav_buffer.getvalue()
    except Exception as e:
        print(f"ERROR: Erro ao converter WebM para WAV: {e}")
        print("INFO DEBUG: Por favor, verifique 'received_audio.webm' para ver se está corrompido ou formato inválido para FFmpeg.")
        raise

async def transcribe_bytes(data: bytes) -> str:
    """
    Envia áudio para Whisper (nova interface) e retorna transcrição de texto.
    """
    wav_data = await asyncio.to_thread(convert_webm_to_wav, data)
    
    # Criar BytesIO e adicionar atributo 'name'
    audio_file_like_object = BytesIO(wav_data)
    audio_file_like_object.name = "audio.wav" # <-- Adicionar este atributo para que a API o trate como um arquivo

    result = await asyncio.to_thread(
        client.audio.transcriptions.create,
        model="whisper-1",
        file=audio_file_like_object # <--- Passar o objeto com 'name'
    )
    return result.text

async def chat_rag(user_text: str) -> str:
    """
    Consulta o índice FAISS, monta prompt com contexto e chama ChatCompletions (nova interface).
    """
    docs = query_index(user_text)
    context = "\n\n".join(d.page_content for d in docs)
    prompt = f"""Você é um agente SDR (Sales Development Representative) especialista em prospecção de clientes.
Sua tarefa é engajar o cliente de forma útil, respondendo suas perguntas e direcionando a conversa para a apresentação de produtos/serviços, com base no contexto fornecido.
Seja conciso, profissional e persuasivo. Se a pergunta do cliente não estiver diretamente relacionada ao contexto, tente guiá-lo de volta para o assunto principal ou para uma oportunidade de vendas.

Contexto da Empresa/Produtos:
{context}

Interação Atual:
Cliente: {user_text}
Agente:"""


    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Você é um SDR expert com RAG, focado em vendas."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

@tapp.websocket("/ws/voice")
async def ws_voice(ws: WebSocket):
    await ws.accept()
    audio_buffer = bytearray()
    try:
        while True:
            full_audio_blob = await ws.receive_bytes()
            audio_buffer.extend(full_audio_blob)
            break 

    except WebSocketDisconnect:
        print("INFO: WebSocket disconnected.")
    except Exception as e:
        print(f"ERROR: Erro no WebSocket: {e}")
    finally:
        if audio_buffer:
            try:
                print(f"INFO: Recebido {len(audio_buffer)} bytes de áudio para transcrição.")
                text = await transcribe_bytes(bytes(audio_buffer))
                print(f"INFO: Transcrição: {text}")
                reply = await chat_rag(text)
                print(f"INFO: Resposta do Agente: {reply}")
                audio = synthesize_tts(reply)
                await ws.send_bytes(audio)
                print("INFO: Áudio de resposta enviado.")
            except Exception as e:
                print(f"ERROR: Erro durante processamento ou envio da resposta: {e}")
                # Enviar uma mensagem de erro de volta ao cliente, se possível
                try:
                    await ws.send_text("Desculpe, tive um problema ao processar seu áudio. Por favor, tente novamente.")
                except:
                    pass # Evita loop de erros se o socket já estiver fechado
            finally:
                await ws.close()
        else:
            print("INFO: Nenhum dado de áudio recebido antes da desconexão.")