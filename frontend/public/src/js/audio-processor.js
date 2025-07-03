class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
      super();
      this.sampleRate = 48000;
      this.volumeThreshold = 0.09; // Limiar de volume para detectar voz (0.0 a 1.0)
      
      // O worklet apenas reporta atividade/inatividade. A temporização é no main thread.
      this.isTalking = false;
      this.silenceFrameCount = 0;
      this.silenceFrameThreshold = 5;
  
      this.port.onmessage = (event) => {
        if (event.data.type === 'init') {
          this.sampleRate = event.data.sampleRate;
          console.log(`AudioProcessor: Initialized with sampleRate: ${this.sampleRate}`);
        } else if (event.data.type === 'start_recording') {
          this.isTalking = false;
          this.silenceFrameCount = 0;
          this.port.postMessage({ type: 'vad_status', status: 'ready' });
          console.log(`AudioProcessor: Starting recording, ready for VAD.`);
        } else if (event.data.type === 'stop_recording') {
          this.isTalking = false;
          this.silenceFrameCount = 0;
          this.port.postMessage({ type: 'vad_status', status: 'stopped' });
          console.log(`AudioProcessor: Stopping recording.`);
        }
      };
    }
  
    process(inputs, outputs, parameters) {
      const input = inputs[0];
      const channelData = input[0];
  
      if (!channelData) {
        return true;
      }
  
      let sum = 0;
      for (let i = 0; i < channelData.length; i++) {
        sum += Math.abs(channelData[i]);
      }
      let averageVolume = sum / channelData.length;
      this.port.postMessage({ type: 'volume', volume: averageVolume });
  
      // Lógica de Detecção de Atividade de Voz (VAD)
      const hasVoiceActivity = averageVolume > this.volumeThreshold;
  
      if (hasVoiceActivity) {
        this.silenceFrameCount = 0;
        if (!this.isTalking) {
          this.isTalking = true;
          this.port.postMessage({ type: 'vad_status', status: 'voice_activity' }); // Manda 'voice_activity' (início de fala)
        }
      } else {
        this.silenceFrameCount++;
        if (this.isTalking && this.silenceFrameCount >= this.silenceFrameThreshold) {
          // Se estava falando e atingiu o limite de frames de silêncio
          this.isTalking = false;
          this.silenceFrameCount = 0;
          this.port.postMessage({ type: 'vad_status', status: 'no_voice_activity' }); // Manda 'no_voice_activity' (fim de fala)
        }
      }
  
      // Envia os Dados PCM (Float32) para o main thread
      this.port.postMessage({ type: 'audio', audioData: channelData.buffer }, [channelData.buffer]);
  
      return true;
    }
  }
  
  registerProcessor('audio-processor', AudioProcessor);