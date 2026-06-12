import { useRef, useState, useEffect } from 'react';

export const useMic = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioExtension, setAudioExtension] = useState<string>('webm');
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  
  // Real-time voice amplitude volume (0 to 1)
  const [amplitude, setAmplitude] = useState(0);

  // Helper to get browser-supported audio mime type and matching file extension
  const getSupportedAudioConfig = () => {
    if (typeof MediaRecorder === 'undefined') {
      return { mimeType: 'audio/webm', extension: 'webm' };
    }

    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      return { mimeType: 'audio/webm;codecs=opus', extension: 'webm' };
    }
    if (MediaRecorder.isTypeSupported('audio/webm')) {
      return { mimeType: 'audio/webm', extension: 'webm' };
    }
    if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
      return { mimeType: 'audio/ogg;codecs=opus', extension: 'ogg' };
    }
    if (MediaRecorder.isTypeSupported('audio/mp4')) {
      return { mimeType: 'audio/mp4', extension: 'mp4' };
    }
    if (MediaRecorder.isTypeSupported('audio/aac')) {
      return { mimeType: 'audio/aac', extension: 'aac' };
    }
    
    return { mimeType: '', extension: 'wav' }; // Fallback
  };

  const startRecording = async () => {
    try {
      setAudioBlob(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const config = getSupportedAudioConfig();
      setAudioExtension(config.extension);

      // 1. Set up MediaRecorder with the supported MIME type
      const options = config.mimeType ? { mimeType: config.mimeType } : undefined;
      const mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mediaRecorder;
      
      const audioChunks: Blob[] = [];
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        // Save Blob using the actual MIME type of the recorded chunks
        const mimeType = mediaRecorder.mimeType || config.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunks, { type: mimeType });
        setAudioBlob(audioBlob);
      };

      // 2. Set up Web Audio API Analyser for visual feedback rings
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const audioContext = new AudioContextClass();
      audioContextRef.current = audioContext;

      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;

      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      mediaRecorder.start(100); // Collect data every 100ms
      setIsRecording(true);

      // Track amplitude in a loop
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      
      const updateAmplitude = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
        }
        
        const avg = sum / bufferLength;
        setAmplitude(Math.min(1.0, avg / 120));
        
        animationFrameRef.current = requestAnimationFrame(updateAmplitude);
      };

      updateAmplitude();
    } catch (err) {
      console.error('Error accessing microphone:', err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
    }
    
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
    }

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    setIsRecording(false);
    setAmplitude(0);
  };

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  return {
    isRecording,
    amplitude,
    audioBlob,
    audioExtension,
    startRecording,
    stopRecording,
  };
};
