"""
Voice Command Processor

Implements GROK RECOMMENDATION #9: Voice Commands with Whisper API

Features:
- Speech-to-text via OpenAI Whisper
- Command interpretation via Claude AI
- Quick pattern matching for common commands
- Text-to-speech responses
- Context-aware command execution
"""

import os
import tempfile
from typing import Optional, Dict, Any, Tuple
from enum import Enum
import json

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️  OpenAI not available. Voice commands will be disabled.")


class VoiceCommandType(str, Enum):
    QUERY = "query"           # Asking for information
    ACTION = "action"         # Execute something
    NAVIGATION = "navigation" # Go to a page
    SETTING = "setting"       # Change a setting
    CLARIFICATION = "clarification"  # Need more info
    UNKNOWN = "unknown"


class VoiceProcessor:
    """Process voice commands using Whisper and Claude"""

    def __init__(self):
        if not OPENAI_AVAILABLE:
            raise RuntimeError("OpenAI SDK not installed. Run: uv pip install openai")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found in environment variables")

        self.openai_client = openai.OpenAI(api_key=api_key)

        # Import Claude client if available
        try:
            from ospra_os.integrations.claude_client import ClaudeClient
            self.claude = ClaudeClient()
            self.claude_available = True
        except:
            self.claude = None
            self.claude_available = False
            print("⚠️  Claude client not available. Using basic command interpretation.")

        # Command patterns for quick matching (before hitting Claude)
        self.quick_patterns = {
            "approve all": ("action", "approve_all_high_confidence"),
            "show pending": ("navigation", "/actions"),
            "show actions": ("navigation", "/actions"),
            "show dashboard": ("navigation", "/"),
            "show home": ("navigation", "/"),
            "show learnings": ("navigation", "/learnings"),
            "show products": ("navigation", "/products"),
            "show intelligence": ("navigation", "/intelligence"),
            "show trends": ("navigation", "/trends"),
            "show inventory": ("navigation", "/inventory"),
            "show ads": ("navigation", "/ads"),
            "show settings": ("navigation", "/settings"),
            "enable auto pilot": ("setting", "auto_pilot_on"),
            "disable auto pilot": ("setting", "auto_pilot_off"),
            "turn on auto pilot": ("setting", "auto_pilot_on"),
            "turn off auto pilot": ("setting", "auto_pilot_off"),
            "what's my revenue": ("query", "revenue_today"),
            "how many orders": ("query", "orders_today"),
            "show revenue": ("query", "revenue_today"),
            "show orders": ("query", "orders_today"),
        }

    async def transcribe_audio(self, audio_data: bytes, format: str = "webm") -> str:
        """Transcribe audio using Whisper"""

        # Save to temp file (Whisper API needs a file)
        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"
                )
            return transcript.text
        finally:
            os.unlink(temp_path)

    async def process_command(
        self,
        transcript: str,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process transcribed command and determine action"""

        transcript_lower = transcript.lower().strip()

        # Try quick pattern matching first
        for pattern, (cmd_type, cmd_value) in self.quick_patterns.items():
            if pattern in transcript_lower:
                return await self._execute_quick_command(cmd_type, cmd_value, user_context)

        # Fall back to Claude for complex interpretation (if available)
        if self.claude_available:
            return await self._interpret_with_claude(transcript, user_context)
        else:
            return await self._interpret_basic(transcript, user_context)

    async def _execute_quick_command(
        self,
        cmd_type: str,
        cmd_value: str,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a quick-matched command"""

        if cmd_type == "navigation":
            page_name = cmd_value.replace('/', '').replace('-', ' ').title()
            if not page_name:
                page_name = "Home"

            return {
                "type": "navigation",
                "action": "navigate",
                "navigate_to": cmd_value,
                "response": f"Opening {page_name}"
            }

        elif cmd_type == "action":
            if cmd_value == "approve_all_high_confidence":
                # Would call your actions API here
                pending_count = user_context.get('pending_actions', 0)
                return {
                    "type": "action",
                    "action": "approve_all",
                    "response": f"Approving all high-confidence actions. You have {pending_count} pending actions.",
                    "data": {"pending_count": pending_count}
                }

        elif cmd_type == "setting":
            if cmd_value == "auto_pilot_on":
                return {
                    "type": "setting",
                    "action": "auto_pilot",
                    "value": True,
                    "response": "Auto-pilot enabled. I'll handle high-confidence decisions automatically."
                }
            elif cmd_value == "auto_pilot_off":
                return {
                    "type": "setting",
                    "action": "auto_pilot",
                    "value": False,
                    "response": "Auto-pilot disabled. All actions will require your approval."
                }

        elif cmd_type == "query":
            return await self._handle_query(cmd_value, user_context)

        return {"type": "unknown", "response": "I didn't understand that command. Try saying 'show dashboard' or 'what's my revenue'."}

    async def _interpret_basic(
        self,
        transcript: str,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Basic interpretation without Claude"""

        transcript_lower = transcript.lower()

        # Check for revenue queries
        if any(word in transcript_lower for word in ['revenue', 'sales', 'earnings']):
            return await self._handle_query("revenue_today", user_context)

        # Check for order queries
        if any(word in transcript_lower for word in ['orders', 'purchases']):
            return await self._handle_query("orders_today", user_context)

        # Check for navigation
        pages = {
            'dashboard': '/',
            'home': '/',
            'products': '/products',
            'actions': '/actions',
            'intelligence': '/intelligence',
            'trends': '/trends',
            'settings': '/settings',
        }

        for page, path in pages.items():
            if page in transcript_lower:
                return {
                    "type": "navigation",
                    "navigate_to": path,
                    "response": f"Opening {page.title()}"
                }

        return {
            "type": "clarification",
            "response": "I'm not sure what you want. Try 'show dashboard', 'what's my revenue', or 'show actions'."
        }

    async def _interpret_with_claude(
        self,
        transcript: str,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use Claude to interpret complex commands"""

        prompt = f"""You are Ospra, an AI e-commerce assistant. Interpret this voice command and respond with a JSON action.

User's command: "{transcript}"

User context:
- Pending actions: {user_context.get('pending_actions', 0)}
- Today's revenue: ${user_context.get('today_revenue', 0):.2f}
- Today's orders: {user_context.get('today_orders', 0)}
- Auto-pilot: {'enabled' if user_context.get('auto_pilot') else 'disabled'}

Respond with JSON only in this format:
{{
  "type": "query|action|navigation|setting|clarification",
  "action": "specific_action_name",
  "params": {{}},
  "response": "Natural language response to speak back",
  "navigate_to": "/path"
}}

Action types:
- approve_action: params.action_id
- approve_all: params.threshold (default 85)
- get_revenue: params.period (today/week/month)
- get_orders: params.period
- toggle_auto_pilot: params.enabled
- navigate: params.path

If you need clarification, use type "clarification" and ask in the response."""

        try:
            response = await self.claude.chat(prompt, max_tokens=300)

            # Parse JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                json_str = response

            result = json.loads(json_str.strip())

            # Execute the interpreted action
            return await self._execute_interpreted_action(result, user_context)

        except Exception as e:
            print(f"Claude interpretation failed: {e}")
            return {
                "type": "error",
                "response": "I had trouble understanding that. Could you try again?",
                "error": str(e)
            }

    async def _execute_interpreted_action(
        self,
        interpretation: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an action interpreted by Claude"""

        action_type = interpretation.get("type")
        action = interpretation.get("action")
        params = interpretation.get("params", {})

        if action_type == "query":
            # Handle data queries
            if action == "get_revenue":
                period = params.get("period", "today")
                data = await self._get_revenue(period, user_context)
                interpretation["data"] = data
            elif action == "get_orders":
                period = params.get("period", "today")
                data = await self._get_orders(period, user_context)
                interpretation["data"] = data

        return interpretation

    async def _handle_query(self, query_type: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data queries"""

        if query_type == "revenue_today":
            revenue = user_context.get("today_revenue", 0)
            return {
                "type": "query",
                "action": "get_revenue",
                "data": {"revenue": revenue, "period": "today"},
                "response": f"Today's revenue is ${revenue:,.2f}"
            }

        elif query_type == "orders_today":
            orders = user_context.get("today_orders", 0)
            return {
                "type": "query",
                "action": "get_orders",
                "data": {"orders": orders, "period": "today"},
                "response": f"You have {orders} order{'s' if orders != 1 else ''} today"
            }

        return {"type": "query", "response": "I couldn't find that information."}

    async def _get_revenue(self, period: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Get revenue data"""
        return {"revenue": user_context.get("today_revenue", 0), "period": period}

    async def _get_orders(self, period: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Get orders data"""
        return {"orders": user_context.get("today_orders", 0), "period": period}


class TextToSpeech:
    """Generate speech responses using OpenAI TTS"""

    def __init__(self):
        if not OPENAI_AVAILABLE:
            raise RuntimeError("OpenAI SDK not installed")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found")

        self.openai_client = openai.OpenAI(api_key=api_key)

    async def generate_speech(
        self,
        text: str,
        voice: str = "nova"  # Options: alloy, echo, fable, onyx, nova, shimmer
    ) -> bytes:
        """Generate speech audio from text"""

        response = self.openai_client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )

        return response.content
