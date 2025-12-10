"""
Voice Command System for Ospra OS

Implements GROK RECOMMENDATION #9: Voice Commands with Whisper API

Features:
- Voice transcription via OpenAI Whisper
- Command interpretation via Claude AI
- Text-to-Speech responses
- Quick pattern matching for common commands
"""

from ospra_os.voice.voice_processor import VoiceProcessor, TextToSpeech, VoiceCommandType

__all__ = ['VoiceProcessor', 'TextToSpeech', 'VoiceCommandType']
