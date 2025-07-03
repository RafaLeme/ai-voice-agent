const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const usernameInput = document.getElementById('username');
const messagesDiv = document.getElementById('messages');
const statusDiv = document.getElementById('statusDiv');
const audioVisualizer = document.getElementById('audioVisualizer');

let socket = null; 
let audioContext = null;
let audioWorkletNode = null;
let microphoneStream = null;
let audioInputNode = null;

let isRecordingActive = false;
let isAgentSpeaking = false;
let isUserTalking = false;

let silenceTimeoutId = null;
const SILENCE_DURATION_MS = 1000;

let audioQueue = [];
let isPlayingQueue = false;

const SAMPLE_RATE_TARGET = 16000; // Taxa de amostragem alvo para o backend (Whisper)

// Função para adicionar mensagens ao chat
function addMessage(sender, text) {
  const el = document.createElement('div');
  el.className = `message ${sender}`;
  el.textContent = text;
  messagesDiv.appendChild(el);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Funções do Visualizador de Áudio
function startAudioVisualizerAnimation() {
  audioVisualizer.classList.add('active');
}

function stopAudioVisualizerAnimation() {
  audioVisualizer.classList.remove('active');
  audioVisualizer.style.transform = 'scale(1)';
  audioVisualizer.style.opacity = '0.7';
}

function updateVisualizerVolume(volume) {
  const scale = 1 + volume * 0.5;
  const opacity = 0.7 + volume * 0.3;
  audioVisualizer.style.transform = `scale(${Math.min(scale, 1.5)})`;
  audioVisualizer.style.opacity = Math.min(opacity, 1);
}

// Funções de Processamento de Áudio
function float32ToInt16(buffer) {
  const l = buffer.length;
  const result = new Int16Array(l);
  for (let i = 0; i < l; i++) {
    result[i] = Math.min(1, buffer[i]) * 0x7FFF;
  }
  return result;
}

function resampleAudio(buffer, originalRate, targetRate) {
  if (originalRate === targetRate) return buffer;
  const ratio = originalRate / targetRate;
  const newLen = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLen);
  for (let i = 0; i < newLen; i++) {
    const idx = i * ratio;
    const low = Math.floor(idx);
    const high = Math.min(buffer.length - 1, Math.ceil(idx));
    const frac = idx - low;
    result[i] = buffer[low] + frac * (buffer[high] - buffer[low]);
  }
  return result;
}

// Função para tocar áudio da fila
async function playNextAudio() {
  if (audioQueue.length > 0 && !isPlayingQueue) {
    isPlayingQueue = true;
    isAgentSpeaking = true;
    statusDiv.textContent = 'Status: Agente falando...';
    
    const blob = audioQueue.shift();
    const arrayBuffer = await blob.arrayBuffer();
    
    if (!audioContext || audioContext.state === 'closed') {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    
    try {
      const buffer = await audioContext.decodeAudioData(arrayBuffer);
      const source = audioContext.createBufferSource();
      source.buffer = buffer;
      source.connect(audioContext.destination);
      source.start(0);
      
      source.onended = () => {
        isPlayingQueue = false;
        
        // Se há mais áudios na fila, toca o próximo
        if (audioQueue.length > 0) {
          playNextAudio();
        } else {
          // Acabou de falar, volta a gravar (se o socket ainda estiver aberto)
          isAgentSpeaking = false;
          if (socket && socket.readyState === WebSocket.OPEN) {
              statusDiv.textContent = 'Status: Pronto para nova fala.';
              // Se o usuário já estiver falando (isUserTalking true do VAD), continua enviando. Caso contrário, prepara para receber a próxima fala.
              if (!isUserTalking) {
                  isRecordingActive = true;
                  startAudioVisualizerAnimation();
                  console.log('DEBUG JS: Agente terminou de falar, microfone reativado.');
              } else {
                  console.log("DEBUG JS: Agente terminou de falar, usuário já estava falando. Mantendo gravação ativa.");
                  isRecordingActive = true; // Continua o envio.
              }
          } else {
              // Socket pode ter sido fechado durante a fala do agente
              console.log('DEBUG JS: Agente terminou de falar, mas socket não está OPEN. Sessão encerrada.');
              resetFrontendState(false);
          }
        }
      };
    } catch (e) {
      console.error('Error decoding audio (from agent):', e);
      isPlayingQueue = false;
      isAgentSpeaking = false;
      statusDiv.textContent = 'Status: Erro na reprodução do áudio do agente.';
      
      if (audioQueue.length > 0) {
        playNextAudio();
      } else {
          // Se não há mais áudios e ocorreu erro, tenta reabilitar microfone
          if (socket && socket.readyState === WebSocket.OPEN && !isUserTalking) {
              statusDiv.textContent = 'Status: Erro na reprodução. Pronto para nova fala.';
              isRecordingActive = true;
              startAudioVisualizerAnimation();
          }
      }
    }
  }
}

// Função para resetar o estado do frontend completamente
function resetFrontendState(closeSocketExplicitly = true) {
    startBtn.disabled = false;
    stopBtn.disabled = true;
    usernameInput.disabled = false;
    statusDiv.textContent = 'Status: Aguardando.';
    messagesDiv.innerHTML = '';
    
    if (microphoneStream) {
      microphoneStream.getTracks().forEach(track => track.stop());
      microphoneStream = null;
    }
    if (audioInputNode) {
      audioInputNode.disconnect();
      audioInputNode = null;
    }
    if (audioWorkletNode) {
      audioWorkletNode.port.postMessage({ type: 'stop_recording' });
      audioWorkletNode.disconnect();
      audioWorkletNode = null;
    }
    
    // Fecha AudioContext de forma assíncrona ou com delay para evitar problemas de timing
    if (audioContext && audioContext.state !== 'closed') {
        console.log("DEBUG JS: Tentando fechar AudioContext.");
        setTimeout(() => {
          if (audioContext && audioContext.state !== 'closed') {
              audioContext.close().then(() => {
                  console.log("DEBUG JS: AudioContext fechado com sucesso.");
                  audioContext = null;
              }).catch(e => console.error("ERROR JS: Falha ao fechar AudioContext:", e));
          }
        }, 50);
    }
    
    stopAudioVisualizerAnimation();
    
    isRecordingActive = false;
    isAgentSpeaking = false;
    isUserTalking = false;
    audioQueue = [];
    isPlayingQueue = false;
    
    if (silenceTimeoutId !== null) {
      clearTimeout(silenceTimeoutId);
      silenceTimeoutId = null;
    }
    
    if (closeSocketExplicitly && socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      socket.close();
    }
    socket = null;
  }

startBtn.addEventListener('click', async () => {
  resetFrontendState(false); 
  
  startBtn.disabled = true;
  stopBtn.disabled = true;
  usernameInput.disabled = true;

  statusDiv.textContent = 'Status: Conectando...';
  addMessage('system', 'Conectando ao agente...');

  const username = usernameInput.value.trim();
  if (!username) {
    addMessage('system', 'Por favor, digite seu nome para iniciar a conversa.');
    resetFrontendState();
    return;
  }

  // Inicializa o socket
  socket = new WebSocket(`ws://localhost:8000/ws/voice?username=${encodeURIComponent(username)}`);

  socket.onopen = async () => {
    console.log('WebSocket conectado');
    statusDiv.textContent = 'Status: Conectado. Preparando microfone...';
    addMessage('system', 'Conexão estabelecida.');

    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      await audioContext.audioWorklet.addModule('src/js/audio-processor.js'); 
      
      microphoneStream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: audioContext.sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      
      audioInputNode = audioContext.createMediaStreamSource(microphoneStream);
      audioWorkletNode = new AudioWorkletNode(audioContext, 'audio-processor');
      
      // Envia a taxa de amostragem original para o worklet
      audioWorkletNode.port.postMessage({ type: 'init', sampleRate: audioContext.sampleRate });

      audioWorkletNode.port.onmessage = event => {
        if (event.data.type === 'volume') {
          updateVisualizerVolume(event.data.volume);
        } else if (event.data.type === 'audio') {
          const floatData = new Float32Array(event.data.audioData);
          let resampled = floatData;
          
          // Reamostragem no main thread
          if (audioContext.sampleRate !== SAMPLE_RATE_TARGET) {
            resampled = resampleAudio(floatData, audioContext.sampleRate, SAMPLE_RATE_TARGET);
          }
          
          const pcm16 = float32ToInt16(resampled);
          
          // isRecordingActive controla se o áudio do mic é enviado
          if (isRecordingActive && !isAgentSpeaking && socket.readyState === WebSocket.OPEN) {
            socket.send(pcm16.buffer); // Envia ArrayBuffer
          }
          
        } else if (event.data.type === 'vad_status') {
          console.log('DEBUG JS: VAD status ->', event.data.status);
          
          if (event.data.status === 'voice_activity') {
            console.log('DEBUG JS: Voz detectada');
            isUserTalking = true;
            startAudioVisualizerAnimation();
            
            // Cancelar timeout de silêncio se existir
            if (silenceTimeoutId !== null) { // NOVO: Usar !== null
              clearTimeout(silenceTimeoutId);
              silenceTimeoutId = null;
              console.log('DEBUG JS: Timeout de silêncio cancelado');
            }
            
            // Ativar gravação se agente não estiver respondendo
            if (!isAgentSpeaking) {
              isRecordingActive = true;
              statusDiv.textContent = 'Status: Ouvindo...';
            } else {
                console.log("DEBUG JS: Voz detectada, mas agente está falando. Microfone pausado temporariamente.");
                isRecordingActive = false;
            }
            
          } else if (event.data.status === 'no_voice_activity') {
            console.log('DEBUG JS: Silêncio detectado');
            
            // Se o usuário estava falando E não há timer de silêncio ativo E agente não está falando
            if (isUserTalking && silenceTimeoutId === null && !isAgentSpeaking) {
                console.log('DEBUG JS: Agendando end_of_speech');
                
                silenceTimeoutId = setTimeout(() => {
                  console.log('DEBUG JS: Enviando end_of_speech');
                  console.log('socket = ', socket);
                  console.log('socket.readyState = ', socket.readyState);
                  console.log('WebSocket.OPEN = ', WebSocket.OPEN);
                  
                  if (socket && socket.readyState === WebSocket.OPEN) {
                    console.log('DEBUG JS: readyState é OPEN. Enviando sinal...');
                    socket.send(JSON.stringify({ type: 'end_of_speech' }));
                    statusDiv.textContent = 'Status: Processando...';
                  } else {
                    console.log('DEBUG JS: NÃO foi possível enviar end_of_speech. Socket estado:', 
                                socket ? socket.readyState : 'NULL', 
                                'Esperado OPEN:', WebSocket.OPEN);
                  }
                  
                  isUserTalking = false;
                  isRecordingActive = false;
                  stopAudioVisualizerAnimation();
                  silenceTimeoutId = null;
                  
                }, SILENCE_DURATION_MS);
              } else if (!isUserTalking) {
                   stopAudioVisualizerAnimation();
              }
          } else if (event.data.status === 'ready') {
               console.log('DEBUG JS: VAD - Worklet pronto para detectar fala.');
               // Só ativa a gravação se o agente não estiver falando
               if (!isAgentSpeaking) {
                  isRecordingActive = true;
                  startAudioVisualizerAnimation();
                  statusDiv.textContent = 'Status: Pronto para falar.';
               }
          } else if (event.data.status === 'stopped') {
              console.log('DEBUG JS: VAD - Worklet parou a detecção/gravação.');
              isRecordingActive = false;
              isUserTalking = false;
              stopAudioVisualizerAnimation();
          }
        }
      };
      
      audioInputNode.connect(audioWorkletNode);
      audioWorkletNode.connect(audioContext.destination);

    } catch (error) {
      console.error('Erro ao configurar áudio:', error);
      statusDiv.textContent = 'Status: Erro ao acessar microfone.';
      addMessage('system', 'Erro ao acessar seu microfone. Por favor, verifique as permissões.');
      resetFrontendState();
    }
  };

  socket.onmessage = async event => {
    if (event.data instanceof Blob) {
      console.log('DEBUG JS: Áudio recebido do agente');
      isAgentSpeaking = true;
      audioQueue.push(event.data);
      
      if (!isPlayingQueue) {
        playNextAudio();
      }
      
      isRecordingActive = false;
      stopAudioVisualizerAnimation();
      statusDiv.textContent = 'Status: Agente falando...';
      
    } else {
      const text = event.data;
      console.log('DEBUG JS: Texto recebido:', text);
      
      if (text.startsWith('Você:')) {
        addMessage('user', text.substring(5));
      } else if (text.startsWith('Agente:')) {
        addMessage('assistant', text.substring(7));
      } else {
        addMessage('system', text);
      }
    }
  };

  socket.onerror = e => {
    console.error('WebSocket error:', e);
    statusDiv.textContent = 'Status: Erro na conexão.';
    addMessage('system', 'Erro na conexão. Tente novamente.');
    resetFrontendState();
  };

  socket.onclose = event => {
    console.log('WebSocket fechado:', event.code, event.reason);
    statusDiv.textContent = 'Status: Desconectado.';
    addMessage('system', 'Conexão encerrada.');
    resetFrontendState();
  };
});

stopBtn.addEventListener('click', () => {
  console.log('Botão parar clicado');
  
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'end_of_session' }));
  }
  
  resetFrontendState();
});