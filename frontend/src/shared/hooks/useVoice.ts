interface UseVoiceReturn {
  isRecording: boolean;
  isSupported: boolean;
  transcript: string;
  startRecording: () => void;
  stopRecording: () => void;
  error: string | null;
}

export function useVoice(_onFinalTranscript?: (text: string) => void): UseVoiceReturn {
  return {
    isRecording: false,
    isSupported: false,
    transcript: '',
    startRecording: () => {},
    stopRecording: () => {},
    error: null,
  };
}
