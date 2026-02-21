import time
import os
import base64
import tempfile
import sys
import re
import json
import threading
import queue
from typing import Dict, List, Optional, Callable, Any

# Add project root to path for core access, then bridge dir for local modules
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_bridge_dir = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _bridge_dir not in sys.path:
    sys.path.insert(0, _bridge_dir)  # highest priority: local modules first

from whatsapp_web import WhatsAppWeb

# Import admin_server explicitly from bridge dir (avoids collision with project-root admin_server)
import importlib.util
_admin_spec = importlib.util.spec_from_file_location("admin_server", os.path.join(_bridge_dir, "admin_server.py"))
_admin_mod = importlib.util.module_from_spec(_admin_spec)
_admin_spec.loader.exec_module(_admin_mod)
start_server = _admin_mod.start_server
from core.base_bridge import AbstractBridge
from core.models import Message, MessageRole, MessageType, ChatChannel
from core.ai_manager import AIManager
from core.command_processor import CommandProcessor
from core.session_manager import SessionManager
from core.orchestrator import BridgeOrchestrator, RestartException
from core.config import ADMIN_CHAT, SHOW_BROWSER, BROWSER_TYPE


class LoginFailedException(Exception):
    pass


class WhatsAppBridge(AbstractBridge):
    """WhatsApp Bridge — platform I/O with clean lifecycle API.
    
    Usage:
        bridge = WhatsAppBridge(sessions=sessions, ai_manager=ai_manager)
        bridge.register_chat("Admin Chat")
        bridge.run()
    """

    def __init__(self, sessions: SessionManager, ai_manager: AIManager):
        self.sessions = sessions
        self.ai_manager = ai_manager
        self.registered_chats: List[str] = []
        self.events: List[dict] = []
        self.history_log = os.path.abspath(os.path.join(os.path.dirname(__file__), "chat_history.log"))
        self.whatsapp: Optional[WhatsAppWeb] = None
        self.orchestrator: Optional[BridgeOrchestrator] = None

    # --- AbstractBridge Implementation (Delegation) ---

    def login(self, timeout: int = 90) -> bool:
        """Initializes the browser and handles login."""
        self.whatsapp = WhatsAppWeb(headless=not SHOW_BROWSER, browser=BROWSER_TYPE)
        return self.whatsapp.login(timeout=timeout)

    def is_connected(self) -> bool:
        return self.whatsapp.is_connected() if self.whatsapp else False

    def get_history(self, chat_name: str, limit: int = 10) -> List[Message]:
        return self.whatsapp.get_history(chat_name, limit=limit) if self.whatsapp else []

    def send_message(self, chat_name: str, message: str):
        if self.whatsapp:
            self.whatsapp.send_message(chat_name, message)

    def download_media(self, chat_name: str, message_index: int = -1, media_type: Any = None) -> List[str]:
        return self.whatsapp.download_media(chat_name, message_index, media_type) if self.whatsapp else []

    def get_unread_chats(self) -> List[ChatChannel]:
        return self.whatsapp.get_unread_chats() if self.whatsapp else []

    def get_all_chats(self) -> List[ChatChannel]:
        return self.whatsapp.get_all_chats() if self.whatsapp else []

    def close(self):
        if self.whatsapp:
            self.whatsapp.close()

    # --- Public API ---

    def register_chat(self, chat_name: str, folder_path: Optional[str] = None, **kwargs):
        """Register a chat for monitoring. Can be called at startup or while running."""
        if chat_name and chat_name not in self.registered_chats:
            self.registered_chats.append(chat_name)
        
        # Activate session if not already active
        if not self.sessions.is_active(chat_name):
            print(f">>> Activating session for: {chat_name}")
            self.sessions.activate(chat_name, folder_path=folder_path)
            
        # If the bridge is already running, seed the chat history to avoid re-processing old messages
        if self.orchestrator:
            self.orchestrator.seed_chats([chat_name])

    def unregister_chat(self, chat_name: str):
        """Unregister a chat and deactivate its session."""
        print(f">>> Unregistering chat: {chat_name}")
        if chat_name in self.registered_chats:
            self.registered_chats.remove(chat_name)
        self.sessions.deactivate(chat_name)

    def reset_chat(self, chat_name: str):
        """Deactivate a chat session (Alias for unregister_chat)."""
        self.unregister_chat(chat_name)

    def run(self):
        """Login to WhatsApp and start the main polling loop. Blocks until stopped."""
        # Build internal components
        command_processor = CommandProcessor(
            self.sessions, ADMIN_CHAT, 
            lambda chat, instruction: self._run_repair_agent(manual_instruction=instruction)
        )

        # WhatsApp I/O
        if not self.login(timeout=90):
            print(">>> Login failed.")
            self.close()
            raise LoginFailedException("WhatsApp login failed after 90s timeout.")

        # Admin UI
        try:
            start_server(self.sessions, whatsapp_instance=self.whatsapp, events_list=self.events)
        except Exception as e:
            print(f">>> Admin UI Error: {e}")

        # Wire orchestrator
        self.orchestrator = BridgeOrchestrator(
            bridge=self,
            ai_manager=self.ai_manager,
            command_processor=command_processor,
            session_manager=self.sessions,
            admin_chat=ADMIN_CHAT,
            log_interaction_cb=self._log_interaction,
            log_event_cb=self._log_event,
            normalize_name_cb=self._normalize_name
        )

        # Seed: registered chats + already-active sessions + admin
        chats_to_seed = list(set(
            self.registered_chats + 
            list(self.sessions.active_sessions.keys()) +
            ([ADMIN_CHAT] if ADMIN_CHAT else [])
        ))
        self.orchestrator.seed_chats(chats_to_seed)

        # Run
        try:
            self.orchestrator.run(self._process_media_wrapper)
        except Exception as e:
            self.close()
            raise e

    def stop(self):
        """Graceful shutdown."""
        if self.orchestrator:
            self.orchestrator.stop()
        if self.whatsapp:
            self.whatsapp.close()

    # --- Internal Helpers ---

    def _normalize_name(self, name):
        if not name: return ""
        return re.sub(r'[^a-zA-Z0-9]', '', name).lower()

    def _log_event(self, chat_name, event_type):
        self.events.append({
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'chat': chat_name,
            'event': event_type
        })
        if len(self.events) > 50:
            self.events.pop(0)

    def _log_interaction(self, chat_name, sender, content):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{chat_name}] {sender}: {content}\n"
        try:
            with open(self.history_log, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            print(f">>> Error writing to chat_history.log: {e}")

    def _process_media(self, msg, target_chat):
        try:
            media_blobs = self.whatsapp.download_media(target_chat, message_index=-1, media_type=msg.type)
            if not media_blobs:
                return None
            blob = media_blobs[0]
            header, encoded = blob.split(",", 1)
            mime = header.split(":")[1].split(";")[0]
            ext_map = {"image/jpeg": "jpg", "image/png": "png", "audio/mpeg": "mp3", "video/mp4": "mp4", "audio/ogg": "ogg"}
            ext = ext_map.get(mime, "bin")
            data = base64.b64decode(encoded)
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as f:
                f.write(data)
                return f.name
        except Exception as e:
            print(f">>> Error processing media: {e}")
            return None

    def _process_media_wrapper(self, bridge, msg, target_chat):
        if msg.type in [MessageType.IMAGE, MessageType.AUDIO, MessageType.VIDEO]:
            return self._process_media(msg, target_chat)
        return None

    def _dump_state(self):
        state = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": {"admin_chat": ADMIN_CHAT, "browser_type": BROWSER_TYPE},
            "active_sessions": dict(self.sessions.active_sessions),
            "session_models": dict(self.sessions.session_models),
            "active_tasks": self.ai_manager.active_tasks,
            "pending_responses": self.ai_manager.response_queue.qsize(),
            "recent_events": self.events[-20:],
            "recent_history_log": [],
        }
        try:
            if os.path.exists(self.history_log):
                with open(self.history_log, "r", encoding="utf-8") as f:
                    state["recent_history_log"] = [l.strip() for l in f.readlines()[-20:]]
        except Exception:
            pass
        
        state_path = os.path.join(os.path.dirname(__file__), "bridge_state.json")
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)

    def _run_repair_agent(self, error_exception=None, manual_instruction=None):
        import traceback
        if manual_instruction:
            prompt = f"MANUAL REPAIR REQUEST: {manual_instruction}\n\nPlease analyze the code..."
        else:
            prompt = f"CRITICAL SYSTEM CRASH REPORT:\n\nError: {error_exception}\n\nTraceback:\n{traceback.format_exc()}"
        
        print(f"\n>>> Calling Repair Agent...")
        repair_system = os.path.join(os.path.dirname(__file__), ".gemini", "repair_system.md")
        result = self.ai_manager.run_gemini(prompt, os.getcwd(), "RepairAgent", model="auto", system_md=repair_system)
        print(f">>> Repair Agent Result: {result}\n")
        return result
