import { useState, useCallback } from 'react';
import { voiceService } from '../../services/voice';

interface UseVoiceReturn {
  isRecording: boolean;
  isSupported: boolean;
  transcript: string;
  startRecording: () => void;
  stopRecording: () => void;
  error: string | null;
}

export function useVoice(onFinalTranscript?: (text: string) => void): UseVoiceReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);

  const startRecording = useCallback(() => {
    setError(null);
    setTranscript('');

    const started = voiceService.start(
      (text, isFinal) => {
        setTranscript(text);
        if (isFinal && onFinalTranscript) {
          onFinalTranscript(text);
        }
      },
      () => {
        setIsRecording(false);
      },
      (err) => {
        setError(err);
        setIsRecording(false);
      }
    );

    if (started) {
      setIsRecording(true);
    }
  }, [onFinalTranscript]);

  const stopRecording = useCallback(() => {
    voiceService.stop();
    setIsRecording(false);
  }, []);

  return {
    isRecording,
    isSupported: voiceService.isSupported(),
    transcript,
    startRecording,
    stopRecording,
    error,
  };
}
