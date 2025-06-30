const startBtn = document.getElementById('start');
const stopBtn = document.getElementById('stop');
const statusMessage = document.getElementById('status-message');
const transcriptionDisplay = document.getElementById('transcription-display');
const responseDisplay = document.getElementById('response-display');

let recorder;
let socket;
let audioChunks = [];

function updateStatus(message, type = 'info') {
    statusMessage.textContent = message;
    statusMessage.className = type === 'error' ? 'error' : 'info'; // Você pode adicionar mais classes para outros tipos
}

function clearDisplays() {
    transcriptionDisplay.textContent = '';
    responseDisplay.textContent = '';
}

startBtn.addEventListener('click', async () => {
    const usernameInput = document.getElementById('username');
    const username = usernameInput.value.trim();
    console.log(`Usuário: ${username}`);

    console.log('[Client] Iniciando gravação e conexão WebSocket');
    clearDisplays(); // Limpa exibições anteriores
    updateStatus('Iniciando gravação...');
    startBtn.disabled = true;
    stopBtn.disabled = true; // Desabilita o stop momentaneamente para evitar cliques duplos

    socket = new WebSocket('ws://localhost:8000/ws/voice?username=' + encodeURIComponent(username));

    socket.onerror = error => {
        console.error('[Client] WebSocket error:', error);
        updateStatus('Erro na conexão. Verifique o console.', 'error');
        startBtn.disabled = false;
        stopBtn.disabled = true;
    };

    socket.onmessage = async event => {
        console.log('[Client] Áudio recebido, reproduzindo...');
        updateStatus('Reproduzindo resposta...');
        const blob = event.data;
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        
        audio.onended = () => {
            console.log('[Client] Reprodução finalizada.');
            updateStatus('Pronto para uma nova gravação.');
            startBtn.disabled = false;
            stopBtn.disabled = true;
            socket.close(); // Fecha o socket após a reprodução
        };

        try {
            await audio.play();
        } catch (e) {
            console.error('[Client] Erro ao reproduzir áudio:', e);
            updateStatus('Erro ao reproduzir áudio.', 'error');
            startBtn.disabled = false;
            stopBtn.disabled = true;
            socket.close();
        }
    };

    await new Promise((resolve, reject) => {
        socket.onopen = () => {
            console.log('[Client] WebSocket aberto');
            updateStatus('Conexão estabelecida. Preparando microfone...');
            resolve();
        };
        socket.onclose = () => {
            console.log('[Client] WebSocket fechado.');
            // A mensagem de status final é definida pelo onmessage. Se fechar antes, é um erro.
            if (statusMessage.textContent.includes('Reproduzindo') || statusMessage.textContent.includes('Erro')) {
                // Já tratado
            } else {
                updateStatus('Conexão fechada inesperadamente.', 'error');
            }
        };
        // Timeout para a conexão, caso algo dê errado
        setTimeout(() => reject(new Error('Conexão WebSocket demorou demais.')), 10000);
    }).catch(e => {
        console.error('[Client] Erro ao abrir WebSocket:', e);
        updateStatus('Falha ao conectar. Verifique o console.', 'error');
        startBtn.disabled = false;
        stopBtn.disabled = true;
        socket.close();
        return; // Sai da função se houver erro
    });

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

        recorder.ondataavailable = e => {
            audioChunks.push(e.data);
        };

        recorder.onstop = () => {
            updateStatus('Gravando finalizada. Enviando para processamento...');
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            audioChunks = [];

            if (socket.readyState === WebSocket.OPEN) {
                console.log('[Client] Gravação finalizada. Enviando áudio completo, tamanho:', audioBlob.size);
                socket.send(audioBlob);
            } else {
                console.error('[Client] WebSocket não está aberto para enviar áudio final.');
                updateStatus('Erro: Conexão com o servidor não está ativa.', 'error');
                startBtn.disabled = false;
                stopBtn.disabled = true;
            }
        };

        recorder.start();
        console.log('[Client] Gravação iniciada');
        updateStatus('Gravando sua voz... Fale agora!');
        stopBtn.disabled = false;
    } catch (e) {
        console.error('[Client] Erro ao acessar microfone:', e);
        updateStatus('Erro ao acessar microfone. Permita o acesso.', 'error');
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
});

stopBtn.addEventListener('click', () => {
    if (recorder && recorder.state !== 'inactive') {
        console.log('[Client] Parando gravação e aguardando envio do áudio');
        updateStatus('Processando áudio...');
        recorder.stop();
        startBtn.disabled = true; // Desabilita start até a resposta chegar
        stopBtn.disabled = true; // Desabilita stop após parar a gravação
    }
});