/**
 * VoiceCommand Component
 *
 * Implements GROK RECOMMENDATION #9: Voice Commands with Whisper API
 *
 * Features:
 * - Mic button with animated recording indicator
 * - Real-time voice transcription using OpenAI Whisper
 * - Command interpretation via Claude AI
 * - Text-to-speech responses
 * - Keyboard shortcut (Cmd/Ctrl + M)
 * - Modal interface with status indicators
 *
 * Supported commands:
 * - "What's my revenue today?"
 * - "Show pending actions"
 * - "Enable auto-pilot"
 * - "Approve all high-confidence actions"
 * - "Go to dashboard"
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Loader2, Volume2, X, Check, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface VoiceCommandProps {
  className?: string;
  onCommandExecuted?: (result: CommandResult) => void;
}

interface CommandResult {
  command_type: 'query' | 'action' | 'navigation' | 'setting' | 'clarification' | 'unknown';
  transcript: string;
  response: string;
  action?: string;
  navigate_to?: string;
  data?: Record<string, any>;
  duration_ms: number;
}

type RecordingState = 'idle' | 'recording' | 'processing' | 'speaking' | 'error';

export function VoiceCommand({ className = '', onCommandExecuted }: VoiceCommandProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [state, setState] = useState<RecordingState>('idle');
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [error, setError] = useState('');
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [audioChunks, setAudioChunks] = useState<Blob[]>([]);

  const navigate = useNavigate();

  // Keyboard shortcut: Cmd/Ctrl + M
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'm') {
        e.preventDefault();
        toggleModal();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const toggleModal = useCallback(() => {
    setIsOpen(!isOpen);
    if (isOpen) {
      // Closing modal - reset state
      stopRecording();
      setState('idle');
      setTranscript('');
      setResponse('');
      setError('');
    }
  }, [isOpen]);

  const startRecording = async () => {
    try {
      setError('');
      setTranscript('');
      setResponse('');

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });

      const chunks: Blob[] = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunks.push(e.data);
        }
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());

        const audioBlob = new Blob(chunks, { type: 'audio/webm' });

        if (audioBlob.size > 0) {
          await processVoiceCommand(audioBlob);
        } else {
          setError('No audio recorded');
          setState('error');
        }
      };

      recorder.start();
      setMediaRecorder(recorder);
      setState('recording');
      setAudioChunks([]);

    } catch (err) {
      console.error('Error starting recording:', err);
      setError('Microphone access denied. Please allow microphone access.');
      setState('error');
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
      setMediaRecorder(null);
    }
  };

  const processVoiceCommand = async (audioBlob: Blob) => {
    setState('processing');

    try {
      // Get auth token
      const token = localStorage.getItem('auth_token');
      if (!token) {
        setError('Not authenticated. Please log in.');
        setState('error');
        return;
      }

      // Create form data with audio
      const formData = new FormData();
      formData.append('audio', audioBlob, 'command.webm');

      // Send to backend
      const response = await fetch('http://localhost:8001/api/voice/command', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result: CommandResult = await response.json();

      // Display result
      setTranscript(result.transcript);
      setResponse(result.response);

      // Execute action if needed
      if (result.navigate_to) {
        // Navigate after showing response
        setTimeout(() => {
          navigate(result.navigate_to!);
          toggleModal();
        }, 2000);
      }

      // Speak response
      await speakResponse(result.response);

      // Call callback
      if (onCommandExecuted) {
        onCommandExecuted(result);
      }

      setState('idle');

    } catch (err) {
      console.error('Error processing voice command:', err);
      setError(err instanceof Error ? err.message : 'Failed to process command');
      setState('error');
    }
  };

  const speakResponse = async (text: string) => {
    setState('speaking');

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return;

      const response = await fetch('http://localhost:8001/api/voice/speak', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text, voice: 'nova' })
      });

      if (!response.ok) {
        console.error('TTS failed:', response.status);
        return;
      }

      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);

      await audio.play();

      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
      };

    } catch (err) {
      console.error('Error speaking response:', err);
      // Don't show error to user - TTS is optional
    }
  };

  const handleMicClick = () => {
    if (state === 'idle') {
      startRecording();
    } else if (state === 'recording') {
      stopRecording();
    }
  };

  const getStatusIcon = () => {
    switch (state) {
      case 'recording':
        return <Mic className="w-5 h-5 text-red-500 animate-pulse" />;
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'speaking':
        return <Volume2 className="w-5 h-5 text-green-500 animate-pulse" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Mic className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusText = () => {
    switch (state) {
      case 'recording':
        return 'Listening...';
      case 'processing':
        return 'Processing command...';
      case 'speaking':
        return 'Speaking response...';
      case 'error':
        return 'Error';
      default:
        return 'Ready to listen';
    }
  };

  return (
    <>
      {/* Mic Button (Header) */}
      <motion.button
        onClick={toggleModal}
        className={`relative p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors ${className}`}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        title="Voice Commands (Cmd+M)"
      >
        {getStatusIcon()}

        {state === 'recording' && (
          <motion.span
            className="absolute inset-0 rounded-full bg-red-500/20"
            animate={{
              scale: [1, 1.5, 1],
              opacity: [0.5, 0, 0.5]
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          />
        )}
      </motion.button>

      {/* Voice Command Modal */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={toggleModal}
            />

            {/* Modal */}
            <motion.div
              className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] max-w-[90vw] bg-white dark:bg-gray-900 rounded-2xl shadow-2xl z-50 overflow-hidden"
              initial={{ opacity: 0, scale: 0.9, y: -50 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: -50 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
            >
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  {getStatusIcon()}
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                      Voice Commands
                    </h2>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {getStatusText()}
                    </p>
                  </div>
                </div>
                <button
                  onClick={toggleModal}
                  className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>

              {/* Content */}
              <div className="p-6 space-y-4">
                {/* Transcript */}
                {transcript && (
                  <motion.div
                    className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg"
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <div className="flex items-start gap-2">
                      <Check className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                          You said:
                        </p>
                        <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                          "{transcript}"
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Response */}
                {response && (
                  <motion.div
                    className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg"
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <div className="flex items-start gap-2">
                      <Volume2 className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-green-900 dark:text-green-100">
                          Ospra says:
                        </p>
                        <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                          {response}
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Error */}
                {error && (
                  <motion.div
                    className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg"
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <div className="flex items-start gap-2">
                      <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-red-900 dark:text-red-100">
                          Error:
                        </p>
                        <p className="text-sm text-red-700 dark:text-red-300 mt-1">
                          {error}
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Mic Button */}
                <div className="flex justify-center pt-4">
                  <motion.button
                    onClick={handleMicClick}
                    disabled={state === 'processing' || state === 'speaking'}
                    className={`relative w-20 h-20 rounded-full flex items-center justify-center transition-all ${
                      state === 'recording'
                        ? 'bg-red-500 hover:bg-red-600'
                        : state === 'processing' || state === 'speaking'
                        ? 'bg-gray-300 dark:bg-gray-700 cursor-not-allowed'
                        : 'bg-blue-500 hover:bg-blue-600'
                    }`}
                    whileHover={{ scale: state === 'idle' ? 1.05 : 1 }}
                    whileTap={{ scale: state === 'idle' ? 0.95 : 1 }}
                  >
                    {state === 'recording' ? (
                      <MicOff className="w-8 h-8 text-white" />
                    ) : state === 'processing' || state === 'speaking' ? (
                      <Loader2 className="w-8 h-8 text-white animate-spin" />
                    ) : (
                      <Mic className="w-8 h-8 text-white" />
                    )}

                    {state === 'recording' && (
                      <motion.span
                        className="absolute inset-0 rounded-full bg-red-400"
                        animate={{
                          scale: [1, 1.3, 1],
                          opacity: [0.5, 0, 0.5]
                        }}
                        transition={{
                          duration: 1.5,
                          repeat: Infinity,
                          ease: "easeInOut"
                        }}
                      />
                    )}
                  </motion.button>
                </div>

                {/* Instructions */}
                {state === 'idle' && !transcript && (
                  <div className="text-center text-sm text-gray-500 dark:text-gray-400 pt-2">
                    <p>Click the microphone and try saying:</p>
                    <ul className="mt-2 space-y-1">
                      <li>"What's my revenue today?"</li>
                      <li>"Show pending actions"</li>
                      <li>"Enable auto-pilot"</li>
                    </ul>
                  </div>
                )}
              </div>

              {/* Keyboard hint */}
              <div className="px-6 pb-4 text-center text-xs text-gray-400 dark:text-gray-500">
                Press <kbd className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded">Cmd+M</kbd> to toggle
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
