import { useState, useRef } from 'react';
import axios from 'axios';

// Detect if running under dev server (port 5173) or production FastAPI (port 8000)
const API_BASE = window.location.port === '5173' ? 'http://localhost:8000' : '';

export interface KIRAState {
  loading: boolean;
  transcription: string;
  response: string;
  intent: string;
  geminiSuggested: boolean;
  error: string | null;
}

export const useKIRA = () => {
  const [kiraState, setKiraState] = useState<KIRAState>({
    loading: false,
    transcription: '',
    response: '',
    intent: 'general',
    geminiSuggested: false,
    error: null,
  });

  const sessionRef = useRef<string>(`session-${Math.random().toString(36).substr(2, 9)}`);

  // Web Speech API for TTS
  const speakText = (text: string) => {
    if ('speechSynthesis' in window) {
      // Cancel any ongoing speech
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      
      // Try to select a nice sounding female/assistant voice
      const voices = window.speechSynthesis.getVoices();
      const assistantVoice = voices.find(
        (voice) => 
          (voice.name.includes('Google') || voice.name.includes('Natural') || voice.name.includes('Zira') || voice.name.includes('Samantha')) && 
          voice.lang.startsWith('en')
      );
      
      if (assistantVoice) {
        utterance.voice = assistantVoice;
      }
      
      utterance.pitch = 1.05; // Slightly higher pitch for KIRA
      utterance.rate = 1.0;
      
      window.speechSynthesis.speak(utterance);
    } else {
      console.warn('Speech synthesis not supported in this browser.');
    }
  };

  const sendVoice = async (audioBlob: Blob, extension: string = 'webm') => {
    setKiraState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const formData = new FormData();
      // Server expects "audio" file parameter
      formData.append('audio', audioBlob, `voice.${extension}`);
      formData.append('session_id', sessionRef.current);

      const resp = await axios.post(`${API_BASE}/voice`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const { transcription, response, intent, gemini_suggested } = resp.data;

      setKiraState({
        loading: false,
        transcription: transcription || '',
        response,
        intent: intent || 'general',
        geminiSuggested: !!gemini_suggested,
        error: null,
      });

      // Playback response text
      speakText(response);
      
      // Phase 3 requirement: Log the intent to console
      console.log(`[KIRA Phase 3] Response Intent Classified: "${intent}"`);

      return resp.data;
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Error uploading voice';
      setKiraState((prev) => ({ ...prev, loading: false, error: errMsg }));
      console.error('KIRA voice request error:', err);
    }
  };

  const sendText = async (text: string) => {
    setKiraState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const resp = await axios.post(`${API_BASE}/chat`, {
        message: text,
        session_id: sessionRef.current,
      });

      const { response, intent, gemini_suggested } = resp.data;

      setKiraState({
        loading: false,
        transcription: text,
        response,
        intent: intent || 'general',
        geminiSuggested: !!gemini_suggested,
        error: null,
      });

      speakText(response);
      console.log(`[KIRA Phase 3] Response Intent Classified: "${intent}"`);

      return resp.data;
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Error sending message';
      setKiraState((prev) => ({ ...prev, loading: false, error: errMsg }));
      console.error('KIRA text request error:', err);
    }
  };

  const approveGemini = async (prompt: string) => {
    setKiraState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const resp = await axios.post(`${API_BASE}/gemini`, {
        prompt,
        session_id: sessionRef.current,
      });

      const { response } = resp.data;

      setKiraState((prev) => ({
        ...prev,
        loading: false,
        response,
        intent: 'gemini',
        geminiSuggested: false,
        error: null,
      }));

      speakText(response);
      return resp.data;
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Error querying Gemini';
      setKiraState((prev) => ({ ...prev, loading: false, error: errMsg }));
    }
  };

  return {
    kiraState,
    sendVoice,
    sendText,
    approveGemini,
    session_id: sessionRef.current,
  };
};
