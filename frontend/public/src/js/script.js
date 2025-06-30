const startBtn = document.getElementById('start');
const stopBtn = document.getElementById('stop');
let recorder;
let socket;
let audioChunks = [];

startBtn.addEventListener('click', async () => {
    console.log('[Client] Iniciando gravação e conexão WebSocket');

    socket = new WebSocket('ws://localhost:8000/ws/voice');

    socket.onerror = error => console.error('[Client] WebSocket error:', error);

    socket.onmessage = async event => {
        console.log('[Client] Áudio recebido, reproduzindo...');
        const blob = event.data;
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        try {
            await audio.play();
        } catch (e) {
            console.error('[Client] Erro ao reproduzir áudio:', e);
        }
    };

    await new Promise(resolve => {
        socket.onopen = () => {
            console.log('[Client] WebSocket aberto');
            resolve();
        };
    });

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

    recorder.ondataavailable = e => {
        audioChunks.push(e.data);
    };

    recorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        audioChunks = [];

        if (socket.readyState === WebSocket.OPEN) {
            console.log('[Client] Gravação finalizada. Enviando áudio completo, tamanho:', audioBlob.size);
            socket.send(audioBlob);
        } else {
            console.error('[Client] WebSocket não está aberto para enviar áudio final.');
        }
    };

    recorder.start();
    console.log('[Client] Gravação iniciada');

    startBtn.disabled = true;
    stopBtn.disabled = false;
});

stopBtn.addEventListener('click', () => {
    console.log('[Client] Parando gravação e aguardando envio do áudio');
    recorder.stop();

    startBtn.disabled = false;
    stopBtn.disabled = true;
});