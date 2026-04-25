"""
Voice Command API Routes

Implements GROK RECOMMENDATION #9: Voice Commands with Whisper API

Endpoints:
- POST /api/voice/transcribe - Transcribe audio to text
- POST /api/voice/command - Process full voice command (audio + execution)
- POST /api/voice/command/text - Process text command without audio
- POST /api/voice/speak - Generate speech from text (TTS)

Features:
- Audio transcription via OpenAI Whisper
- Command interpretation via Claude AI
- Text-to-speech responses
- User context integration (revenue, orders, pending actions)

SECURITY:
- All endpoints require JWT authentication
- File uploads validated for size, format, and content type
"""

import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone

from ospra_os.database import get_db, User
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.voice.voice_processor import VoiceProcessor, TextToSpeech

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

# ============================================================
# Security Constants for File Upload Validation
# ============================================================

# Maximum file size: 25MB (Whisper API limit)
MAX_AUDIO_FILE_SIZE = 25 * 1024 * 1024  # 25MB in bytes

# Allowed audio formats with their MIME types
ALLOWED_AUDIO_FORMATS = {
    "webm": ["audio/webm", "video/webm"],
    "mp3": ["audio/mpeg", "audio/mp3"],
    "wav": ["audio/wav", "audio/x-wav", "audio/wave"],
    "m4a": ["audio/m4a", "audio/x-m4a", "audio/mp4"],
    "ogg": ["audio/ogg", "application/ogg"],
}

# Magic bytes for audio format detection
AUDIO_MAGIC_BYTES = {
    "mp3": [b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\x49\x44\x33"],  # MP3 frame sync + ID3 tag
    "wav": [b"RIFF"],
    "ogg": [b"OggS"],
    "webm": [b"\x1a\x45\xdf\xa3"],  # EBML header
    "m4a": [b"\x00\x00\x00", b"ftyp"],  # ftyp box (may have variable offset)
}


async def validate_audio_upload(audio: UploadFile) -> tuple[bytes, str]:
    """
    Validate uploaded audio file for security.

    Checks:
    1. File size within limits
    2. File extension is allowed
    3. MIME type matches expected format
    4. Basic magic byte verification

    Returns:
        (audio_data, file_extension)

    Raises:
        HTTPException if validation fails
    """
    # Extract file extension
    filename = audio.filename or "audio.webm"
    file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"

    # Check file extension is allowed
    if file_ext not in ALLOWED_AUDIO_FORMATS:
        logger.warning(f"[SECURITY] Rejected audio upload with invalid extension: {file_ext}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format: {file_ext}. Allowed formats: {', '.join(ALLOWED_AUDIO_FORMATS.keys())}"
        )

    # Validate MIME type if provided
    if audio.content_type:
        expected_mimes = ALLOWED_AUDIO_FORMATS[file_ext]
        # Allow application/octet-stream as browsers sometimes send this
        if audio.content_type not in expected_mimes and audio.content_type != "application/octet-stream":
            logger.warning(
                f"[SECURITY] MIME type mismatch: got {audio.content_type}, "
                f"expected one of {expected_mimes} for .{file_ext}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Content type {audio.content_type} does not match file extension .{file_ext}"
            )

    # Read file data with size limit check
    audio_data = b""
    chunk_size = 1024 * 1024  # Read 1MB at a time

    try:
        while True:
            chunk = await audio.read(chunk_size)
            if not chunk:
                break
            audio_data += chunk

            # Check size limit during read to fail fast
            if len(audio_data) > MAX_AUDIO_FILE_SIZE:
                logger.warning(f"[SECURITY] Rejected oversized audio upload: >{MAX_AUDIO_FILE_SIZE} bytes")
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Audio file too large. Maximum size: {MAX_AUDIO_FILE_SIZE // (1024*1024)}MB"
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SECURITY] Error reading uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded file"
        )

    # Check for empty file
    if len(audio_data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is empty"
        )

    # Basic magic byte verification (non-blocking warning)
    # Some formats have variable headers, so we just log suspicious files
    magic_patterns = AUDIO_MAGIC_BYTES.get(file_ext, [])
    if magic_patterns:
        header = audio_data[:12]  # Check first 12 bytes
        matches_any = any(
            header.startswith(pattern) or pattern in header[:12]
            for pattern in magic_patterns
        )
        if not matches_any and file_ext not in ["m4a"]:  # m4a has variable offset
            logger.warning(
                f"[SECURITY] Audio file header doesn't match expected format .{file_ext}. "
                f"Header bytes: {header[:8].hex()}"
            )
            # Don't reject - let Whisper API handle format validation
            # This is just a warning for monitoring

    return audio_data, file_ext

# ============================================================
# Request/Response Models
# ============================================================

class TranscribeResponse(BaseModel):
    """Response for audio transcription"""
    transcript: str = Field(..., description="Transcribed text from audio")
    duration_ms: int = Field(..., description="Processing time in milliseconds")

class TextCommandRequest(BaseModel):
    """Request for text-based command (no audio)"""
    text: str = Field(..., description="Command text to process")

class CommandResponse(BaseModel):
    """Response for command processing"""
    command_type: str = Field(..., description="Type of command (query/action/navigation/setting)")
    transcript: str = Field(..., description="Original command text")
    response: str = Field(..., description="Text response to display/speak")
    action: Optional[str] = Field(None, description="Action to execute")
    navigate_to: Optional[str] = Field(None, description="Page to navigate to")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data")
    duration_ms: int = Field(..., description="Processing time in milliseconds")

class SpeakRequest(BaseModel):
    """Request for text-to-speech generation"""
    text: str = Field(..., description="Text to convert to speech")
    voice: str = Field("nova", description="Voice to use (alloy, echo, fable, onyx, nova, shimmer)")

# ============================================================
# Helper Functions
# ============================================================

def _get_user_context(db: Session, user_id: int) -> Dict[str, Any]:
    """
    Gather user context for command processing

    Returns:
    - pending_actions: Number of pending actions
    - today_revenue: Revenue for today
    - today_orders: Number of orders today
    - auto_pilot: Whether auto-pilot is enabled
    """
    from ospra_os.database import (
        Action,
        AIActionStatus,
        UserSettings
    )

    # Count pending actions
    pending_actions = db.query(Action).filter(
        Action.user_id == user_id,
        Action.status == AIActionStatus.PENDING
    ).count()

    # Get today's revenue and orders
    # Note: This would connect to your Shopify/order tracking system
    # For now, using placeholder values
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    today_revenue = 0.0  # TODO: Query from Shopify API or orders table
    today_orders = 0     # TODO: Query from orders table

    # Get auto-pilot status
    settings = db.query(UserSettings).filter(
        UserSettings.user_id == user_id
    ).first()

    auto_pilot = settings.auto_pilot_enabled if settings else False

    return {
        "pending_actions": pending_actions,
        "today_revenue": today_revenue,
        "today_orders": today_orders,
        "auto_pilot": auto_pilot,
        "user_id": user_id
    }

# ============================================================
# API Endpoints
# ============================================================

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file to transcribe (webm, mp3, wav, m4a, ogg). Max 25MB."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Transcribe audio to text using Whisper API

    Accepts audio formats: webm, mp3, wav, m4a, ogg
    Maximum file size: 25MB
    Returns the transcribed text without processing as a command.

    SECURITY: File uploads are validated for size, format, and MIME type.
    """
    start_time = datetime.now(timezone.utc)

    try:
        # SECURITY: Validate uploaded file (size, format, MIME type, magic bytes)
        audio_data, file_ext = await validate_audio_upload(audio)

        # Transcribe
        processor = VoiceProcessor()
        transcript = await processor.transcribe_audio(audio_data, format=file_ext)

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        return TranscribeResponse(
            transcript=transcript,
            duration_ms=duration_ms
        )

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voice processor initialization failed. Please try again."
        )
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed. Please try again."
        )

@router.post("/command", response_model=CommandResponse)
async def process_voice_command(
    audio: UploadFile = File(..., description="Audio file with voice command (webm, mp3, wav, m4a, ogg). Max 25MB."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Process full voice command: transcribe + interpret + execute

    Steps:
    1. Transcribe audio to text using Whisper
    2. Interpret command using pattern matching or Claude AI
    3. Execute command (query data, navigate, change settings)
    4. Return response with action to take

    Maximum file size: 25MB

    Supported commands:
    - "What's my revenue today?"
    - "Show pending actions"
    - "Enable auto-pilot"
    - "Approve all high-confidence actions"
    - "Go to dashboard"

    SECURITY: File uploads are validated for size, format, and MIME type.
    """
    start_time = datetime.now(timezone.utc)

    try:
        # SECURITY: Validate uploaded file (size, format, MIME type, magic bytes)
        audio_data, file_ext = await validate_audio_upload(audio)

        # Transcribe
        processor = VoiceProcessor()
        transcript = await processor.transcribe_audio(audio_data, format=file_ext)

        # Get user context
        user_context = _get_user_context(db, current_user.id)

        # Process command
        result = await processor.process_command(transcript, user_context)

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        return CommandResponse(
            command_type=result.get("type", "unknown"),
            transcript=transcript,
            response=result.get("response", "I didn't understand that command."),
            action=result.get("action"),
            navigate_to=result.get("navigate_to"),
            data=result.get("data"),
            duration_ms=duration_ms
        )

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voice processor initialization failed. Please try again."
        )
    except Exception as e:
        logger.error(f"Command processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Command processing failed. Please try again."
        )

@router.post("/command/text", response_model=CommandResponse)
async def process_text_command(
    request: TextCommandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Process text command without audio transcription

    Useful for:
    - Testing commands without audio recording
    - Text-based command input
    - Debugging command interpretation

    Example commands:
    - "What's my revenue?"
    - "Show me pending actions"
    - "Enable auto-pilot mode"
    """
    start_time = datetime.now(timezone.utc)

    try:
        processor = VoiceProcessor()

        # Get user context
        user_context = _get_user_context(db, current_user.id)

        # Process command
        result = await processor.process_command(request.text, user_context)

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        return CommandResponse(
            command_type=result.get("type", "unknown"),
            transcript=request.text,
            response=result.get("response", "I didn't understand that command."),
            action=result.get("action"),
            navigate_to=result.get("navigate_to"),
            data=result.get("data"),
            duration_ms=duration_ms
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voice processor initialization failed. Please try again."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Command processing failed. Please try again."
        )

@router.post("/speak")
async def generate_speech(
    request: SpeakRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate speech audio from text using OpenAI TTS

    Returns audio/mpeg (MP3) file that can be played directly.

    Available voices:
    - alloy: Neutral and balanced
    - echo: Slightly deeper, more formal
    - fable: British accent, expressive
    - onyx: Deep and authoritative
    - nova: Warm and upbeat (default)
    - shimmer: Soft and pleasant
    """
    try:
        tts = TextToSpeech()
        audio_data = await tts.generate_speech(request.text, voice=request.voice)

        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=speech.mp3"
            }
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TTS initialization failed. Please try again."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech generation failed. Please try again."
        )

@router.get("/health")
async def voice_health_check():
    """
    Health check endpoint for voice commands system

    Returns status of OpenAI API key and available features.
    """
    import os

    has_openai_key = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic_key = bool(os.getenv("ANTHROPIC_API_KEY"))

    return {
        "status": "healthy" if has_openai_key else "degraded",
        "features": {
            "whisper_transcription": has_openai_key,
            "text_to_speech": has_openai_key,
            "claude_interpretation": has_anthropic_key,
            "basic_interpretation": True
        },
        "message": "Voice commands ready" if has_openai_key else "OpenAI API key required for voice features"
    }
