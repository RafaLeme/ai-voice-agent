import os
from pathlib import Path
from dotenv import load_dotenv

dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

import asyncio
import json
from io import BytesIO
import time
import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
from fastapi.websockets import WebSocketState
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from backend.rag import query_index
from pydub import AudioSegment

# --- ElevenLabs Imports e Configuração ---
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
        print("ERROR: Cliente ElevenLabs não inicializado ou API Key ausente.")
        return b""
    try:
        audio_generator = elevenlabs_client.text_to_speech.convert(
            voice_id="21m00Tcm4TlvDq8ikWAM",
            output_format="mp3_44100_128",
            text=text,
            model_id="eleven_multilingual_v2",
        )
        all_audio_bytes = b""
        async for chunk in audio_generator:
            all_audio_bytes += chunk
        return all_audio_bytes
    except Exception as e:
        print(f"ERROR: Erro ao gerar áudio com ElevenLabs: {e}. Detalhes: {e.response.text if hasattr(e, 'response') and hasattr(e.response, 'text') else 'N/A'}")
        return b""

tapp = FastAPI()

tapp.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAI_KEY = os.getenv("OPENAI_KEY")
if not OPENAI_KEY:
    raise ValueError("Defina OPENAI_KEY no .env antes de iniciar o servidor")
client = OpenAI(api_key=OPENAI_KEY)

# Função para converter PCM RAW para WAV
def convert_pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    try:
        current_time_ms = int(time.time() * 1000)
        output_raw_filename = f"received_audio_raw_{current_time_ms}.bin"
        with open(output_raw_filename, "wb") as f:
            f.write(pcm_bytes)
        print(f"INFO DEBUG: Áudio PCM RAW recebido salvo como {output_raw_filename}")
    except Exception as e:
        print(f"WARN DEBUG: Não foi possível salvar received_audio_raw.bin: {e}")
    try:
        audio = AudioSegment(
            data=pcm_bytes,
            sample_width=sample_width,
            frame_rate=sample_rate,
            channels=channels
        )
        wav_io = BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)
        
        output_wav_filename = f"converted_audio_{current_time_ms}.wav"
        with open(output_wav_filename, "wb") as f:
            f.write(wav_io.getvalue())
        print(f"INFO DEBUG: Áudio WAV convertido salvo como {output_wav_filename}")
        
        return wav_io.read()
    except Exception as e:
        print(f"ERROR: Erro ao converter PCM RAW para WAV: {e}")
        print("INFO DEBUG: Por favor, verifique 'received_audio_raw_*.bin' e tente reproduzir como RAW 16kHz mono.")
        raise

async def transcribe_bytes(data: bytes) -> str:
    try:
        wav_bytes = await asyncio.to_thread(convert_pcm_to_wav, data)
        
        audio_file = BytesIO(wav_bytes)
        audio_file.name = "audio.wav"
        
        response = await asyncio.to_thread(
            client.audio.transcriptions.create,
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )
        return response
    except Exception as e:
        print(f"ERROR: Erro na transcrição com Whisper: {e}")
        raise

async def chat_rag(username: str, messages: list) -> str:
    user_query = messages[-1]["content"]

    docs = query_index(user_query)
    context = "\n\n".join(d.page_content for d in docs)

    system_message_content = f"""Você é um agente SDR (Sales Development Representative) especialista em prospecção de clientes.
Sua tarefa é engajar o cliente **{username}** de forma útil, respondendo suas perguntas e direcionando a conversa para a apresentação de produtos/serviços, com base nas informações fornecidas.
Seja conciso, profissional e persuasivo. Mantenha a coerência com o histórico da conversa.
Se a pergunta do cliente não estiver diretamente relacionada ao contexto, tente guiá-lo de volta para o assunto principal ou para uma oportunidade de vendas.
"""

    openai_messages = [{"role": "system", "content": system_message_content}]

    if context:
        openai_messages.append({"role": "system", "content": f"Informações relevantes para esta consulta (contexto RAG):\n{context}\n\nUse estas informações para complementar sua resposta no contexto da conversa atual."})

    openai_messages.extend(messages)

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o-mini",
        messages=openai_messages
    )
    return response.choices[-1].message.content


# --- FUNÇÃO DE LÓGICA DE TURNO (GLOBAL) ---
async def handle_user_turn_logic(audio_buffer_ref: bytearray, user_id_ref: str, conversation_history_ref: list, ws_ref: WebSocket, set_is_processing_flag_callback):
    
    MIN_AUDIO_BUFFER_FOR_PROCESSING = 16000 # 1 segundo de áudio (16kHz * 1 canal * 2 bytes/sample)
    
    if ws_ref.client_state != WebSocketState.CONNECTED:
        print(f"INFO: handle_user_turn_logic chamado, mas WS para {user_id_ref} não está conectado. Abortando.")
        set_is_processing_flag_callback(False)
        return

    current_turn_audio = bytes(audio_buffer_ref)
    audio_buffer_ref.clear() 

    if not current_turn_audio or len(current_turn_audio) < MIN_AUDIO_BUFFER_FOR_PROCESSING:
        print(f"INFO: Nenhuma fala significativa ou buffer muito pequeno para {user_id_ref}. Ignorando.")
        if ws_ref.client_state == WebSocketState.CONNECTED:
            try:
                await ws_ref.send_text("Agente: Desculpe, não consegui te ouvir. Pode repetir?")
            except RuntimeError as send_error:
                print(f"ERROR: Erro ao enviar mensagem de erro para {user_id_ref}: {send_error}")
        set_is_processing_flag_callback(False)
        return

    print(f"INFO: Processando {len(current_turn_audio)} bytes de áudio de {user_id_ref}.")
    try:
        user_text = await transcribe_bytes(current_turn_audio)
        
        if user_text.strip():
            print(f"INFO: Transcrição: {user_text}")
            if ws_ref.client_state == WebSocketState.CONNECTED:
                try:
                    await ws_ref.send_text(f"Você: {user_id_ref}: {user_text}")
                except RuntimeError as send_error:
                    print(f"ERROR: Erro ao enviar transcrição para {user_id_ref}: {send_error}")
            
            conversation_history_ref.append({"role": "user", "content": user_text})

            reply = await chat_rag(user_id_ref, conversation_history_ref)
            print(f"INFO: Agente: {reply}")
            if ws_ref.client_state == WebSocketState.CONNECTED:
                try:
                    await ws_ref.send_text(f"Agente: {reply}")
                except RuntimeError as send_error:
                    print(f"ERROR: Erro ao enviar resposta de texto para {user_id_ref}: {send_error}")
            
            conversation_history_ref.append({"role": "assistant", "content": reply})

            audio = await synthesize_tts(reply)
            if ws_ref.client_state == WebSocketState.CONNECTED:
                try:
                    await ws_ref.send_bytes(audio)
                except RuntimeError as send_error:
                    print(f"ERROR: Erro ao enviar áudio de resposta para {user_id_ref}: {send_error}")
            print(f"INFO: Áudio de resposta enviado para {user_id_ref}.")
            
        else: # Transcrição vazia, mas buffer não era pequeno
            print(f"INFO: Fala detectada, mas transcrição vazia para {user_id_ref}. Pode ser ruído.")
            if ws_ref.client_state == WebSocketState.CONNECTED:
                try:
                    await ws_ref.send_text("Agente: Não entendi. Você pode repetir, por favor?")
                except RuntimeError as send_error:
                    print(f"ERROR: Erro ao enviar mensagem de repetição para {user_id_ref}: {send_error}")
                
    except Exception as e:
        print(f"ERROR: Erro durante processamento da fala: {e}")
        traceback.print_exc()
        if ws_ref.client_state == WebSocketState.CONNECTED:
            try:
                await ws_ref.send_text("Agente: Desculpe, tive um problema ao processar sua solicitação. Por favor, tente novamente.")
            except RuntimeError as send_error:
                print(f"ERROR: Erro ao enviar mensagem de erro de processamento para {user_id_ref}: {send_error}")
    finally:
        set_is_processing_flag_callback(False)
        print(f"INFO: Processamento do turno de {user_id_ref} concluído/finalizado. 'is_processing_turn' resetado para False.")


@tapp.websocket("/ws/voice")
async def ws_voice(ws: WebSocket, username: str = Query(None)):
    await ws.accept()
    user_id = username or "Desconhecido"
    print(f"INFO: WS aberto por {user_id}")

    conversation_history = []
    audio_buffer = bytearray()
    
    is_processing_turn = False 
    
    def set_processing_flag(value: bool):
        nonlocal is_processing_turn
        is_processing_turn = value

    RECEIVE_TIMEOUT_SECONDS = 0.1 

    try:
        while True: # Loop contínuo para a sessão WebSocket
            try:
                message = await asyncio.wait_for(ws.receive(), timeout=RECEIVE_TIMEOUT_SECONDS)
                
                if "bytes" in message:
                    chunk = message["bytes"]
                    if not is_processing_turn:
                        audio_buffer.extend(chunk)
                    else:
                        pass
                        
                elif "text" in message:
                    try:
                        parsed_text = json.loads(message["text"])
                        
                        if parsed_text.get("type") == "end_of_speech" or parsed_text.get("type") == "end_of_speech_button":
                            print(f"INFO: Sinal de fim de fala ('{parsed_text.get('type')}') recebido para {user_id}.")
                            
                            if not is_processing_turn:
                                is_processing_turn = True
                                asyncio.create_task(
                                    handle_user_turn_logic(
                                        audio_buffer, user_id, conversation_history, ws, set_processing_flag
                                    )
                                )
                                audio_buffer = bytearray() 
                            else:
                                print(f"INFO: Sinal de fim de fala ignorado para {user_id}, pois já estamos processando um turno.")
                            
                        elif parsed_text.get("type") == "end_of_session":
                            print(f"INFO: Sinal de fim de sessão recebido para {user_id}. Encerrando loop.")
                            break 
                                    
                        else:
                            print(f"INFO: Mensagem de texto JSON desconhecida recebida para {user_id}: {parsed_text}")
                            if ws.client_state == WebSocketState.CONNECTED:
                                await ws.send_text(f"Servidor: {message['text']}")

                    except json.JSONDecodeError:
                        print(f"INFO: Mensagem de texto não JSON (malformada) recebida para {user_id}: {message['text']}")
                        if ws.client_state == WebSocketState.CONNECTED:
                            await ws.send_text(f"Servidor: {message['text']}")
                else: # Se o tipo de mensagem não for bytes nem texto
                    print(f"DEBUG BACKEND: Mensagem de tipo inesperado ou de controle recebida: {message.get('type')}")
                
            except asyncio.TimeoutError:
                pass 
                
            except WebSocketDisconnect:
                print(f"INFO: WS desconectado por {user_id}")
                break 
            except Exception as e:
                print(f"ERROR: Erro inesperado no loop do WebSocket para {user_id}: {e}")
                if ws.client_state == WebSocketState.CONNECTED:
                    try:
                        await ws.send_text("Agente: Desculpe, um erro inesperado ocorreu. Por favor, reinicie a conversa.")
                    except RuntimeError as send_error:
                        print(f"ERROR: Erro ao enviar mensagem de erro final para {user_id}: {send_error}")
                break 

    finally:
        # Processa áudio restante ao finalizar a conexão (se não estiver processando)
        if audio_buffer and not is_processing_turn:
            print(f"INFO: Processando áudio restante no buffer ao fechar conexão para {user_id}.")
            await handle_user_turn_logic(audio_buffer, user_id, conversation_history, ws, set_processing_flag)
        
        print(f"INFO: Conexão WebSocket para {user_id} finalizada.")
        if ws.client_state == WebSocketState.CONNECTED:
            try:
                await ws.close()
            except RuntimeError as close_error:
                print(f"ERROR: Erro ao fechar WebSocket para {user_id}: {close_error}")