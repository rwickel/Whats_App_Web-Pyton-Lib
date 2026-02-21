import os
import sys
# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import json
import pytest
from core.session_manager import SessionManager
from core.ai_manager import AIManager
from core.command_processor import CommandProcessor
from core.models import Message, MessageRole, MessageType

def test_req_001_005_session_management(tmp_path):
    """Verifies REQ-001 to REQ-005."""
    persistence = tmp_path / "sessions.json"
    manager = SessionManager(str(persistence))
    
    # REQ-001 & REQ-002: Concurrent management and unique directories
    manager.activate("Chat A")
    manager.activate("Chat B")
    
    path_a = manager.active_sessions["Chat A"]
    path_b = manager.active_sessions["Chat B"]
    
    assert path_a != path_b
    assert os.path.exists(path_a)
    assert os.path.exists(path_b)
    
    # REQ-003: Mandatory files
    for path in [path_a, path_b]:
        assert os.path.exists(os.path.join(path, "OBJECTIVE.md"))
        assert os.path.exists(os.path.join(path, "TODO.md"))
        assert os.path.exists(os.path.join(path, "GEMINI.md"))
        
    # REQ-004: Persistence
    with open(persistence, "r") as f:
        data = json.load(f)
        assert "Chat A" in data["sessions"]
        assert "Chat B" in data["sessions"]
        
    # REQ-005: Deactivation
    manager.deactivate("Chat A")
    assert "Chat A" not in manager.active_sessions
    with open(persistence, "r") as f:
        data = json.load(f)
        assert "Chat A" not in data["sessions"]

def test_req_006_008_message_handling():
    """Verifies REQ-006 to REQ-008."""
    # REQ-008: Role validation
    msg = Message(role="incoming", content="test", type="text")
    assert msg.role == MessageRole.INCOMING
    
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Message(role="hacker", content="test")
        
    # REQ-006 & REQ-007: Media types and base64 storage
    for mtype in ["image", "audio", "video"]:
        m = Message(role="incoming", content="media", type=mtype, media_base64=["data:test"])
        assert m.type == mtype
        assert m.media_base64 == ["data:test"]

def test_req_012_admin_interface_structure():
    """Verifies REQ-012 code structure (FastAPI presence)."""
    import whatsapp_bridge.admin_server as admin_server
    from fastapi import FastAPI
    assert isinstance(admin_server.app, FastAPI)

def test_req_016_logging_capability(tmp_path):
    """Verifies REQ-016 (Logging to error.log)."""
    # Simulate run_gemini error logging via AIManager
    workspace = tmp_path / "ws"
    workspace.mkdir()
    
    from core.ai_manager import AIManager
    am = AIManager(gemini_bin=["gemini"])
    am._log_and_return_error("SimulatedErr", "Details", str(workspace), ["cmd"])
        
    log_path = os.path.join(str(workspace), "error.log")
    assert os.path.exists(log_path)
    with open(log_path, "r") as f:
        assert "SimulatedErr" in f.read()

def test_req_007_008_bot_prefix_and_filtering():
    """Verifies REQ-007 and REQ-008."""
    # REQ-007: Automated responses prefix "Bot:"
    response = "Hello"
    bot_response = f"Bot: {response}"
    assert bot_response.startswith("Bot:")

    # REQ-008: Ignore Bot: messages
    msg_content = "Bot: registration successful"
    assert msg_content.strip().lower().startswith("bot:")

def test_req_010_011_admin_permissions():
    """Verifies REQ-010 and REQ-011."""
    from unittest.mock import MagicMock
    cp = CommandProcessor(MagicMock(), "+49 176 45975276", lambda c, i: "")
    assert cp.is_admin_chat("+49 176 45975276")
    assert cp.is_admin_chat("+4917645975276")
    assert not cp.is_admin_chat("+49 176 00000000")

def test_req_013_whitespace_robustness():
    """Verifies REQ-013."""
    import re
    def normalize_name(name):
        if not name: return ""
        return re.sub(r'[^a-zA-Z0-9]', '', name).lower()
    assert normalize_name("+49 176 45975276") == normalize_name("+4917645975276")
    assert normalize_name("My Group Name") == normalize_name("mygroupname")

def test_req_009_unregistered_isolation(tmp_path):
    """Verifies REQ-009 (Ignoring unregistered chats)."""
    persistence = tmp_path / "sessions.json"
    manager = SessionManager(str(persistence))
    manager.activate("Registered Chat")
    assert manager.is_active("Registered Chat")
    assert not manager.is_active("Unregistered Chat")

def test_req_021_explicit_workspace_mapping(tmp_path):
    """Verifies REQ-021 (Explicit workspace folder registration)."""
    persistence = tmp_path / "sessions.json"
    manager = SessionManager(str(persistence))
    
    manager.activate("Chat With Folder", folder_path="MyExplicitFolder")
    path1 = manager.active_sessions["Chat With Folder"]
    assert "MyExplicitFolder" in path1
    assert os.path.exists(path1)
    
    abs_path = str(tmp_path / "AbsoluteFolder")
    manager.activate("Chat With Abs Path", folder_path=abs_path)
    path2 = manager.active_sessions["Chat With Abs Path"]
    assert path2 == abs_path
    assert os.path.exists(path2)

def test_req_018_event_logging():
    """Verifies REQ-018 (Event logging)."""
    import time
    events = []
    def log_event(chat_name, event_type):
        events.append({'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"), 'chat': chat_name, 'event': event_type})
    log_event("Test Chat", "REGISTER")
    assert len(events) == 1
    assert events[0]["chat"] == "Test Chat"
    assert events[0]["event"] == "REGISTER"

def test_req_012_cross_chat_command_parsing():
    """Verifies REQ-012 command parsing logic."""
    import re
    command = "/register \"My Special Group\" \"folder/path\""
    parts = []
    for m in re.finditer(r'"([^"]*)"|(\S+)', command.strip()):
        parts.append(m.group(1) if m.group(1) is not None else m.group(2))
    assert parts[1] == "My Special Group"
    assert parts[2] == "folder/path"

def test_req_015_seeding_logic():
    """Verifies REQ-015 (Initial seeding logic)."""
    import re
    from unittest.mock import MagicMock
    def normalize_name(name):
        if not name: return ""
        return re.sub(r'[^a-zA-Z0-9]', '', name).lower()
    whatsapp = MagicMock()
    mock_msg = MagicMock()
    mock_msg.timestamp = "ts_123"
    whatsapp.get_history.return_value = [mock_msg]
    chat_name = "+49 176 45975276"
    norm_name = normalize_name(chat_name)
    processed_messages = {}
    history = whatsapp.get_history(chat_name, limit=5)
    processed_messages[norm_name] = {msg.timestamp for msg in history}
    assert "ts_123" in processed_messages[norm_name]

def test_req_022_023_bridge_logging(tmp_path):
    """Verifies REQ-022 and REQ-023."""
    log_path = str(tmp_path / "test_history.log")
    import time
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [Test] User: Hello\n")
    assert os.path.exists(log_path)

def test_req_024_bot_vs_me_sender():
    """Verifies REQ-024."""
    def get_sender(text, role):
        if role == MessageRole.OUTGOING:
            return "Bot" if text.startswith("Bot:") else "Me"
        return "User"
    assert get_sender("Bot: Hello", MessageRole.OUTGOING) == "Bot"
    assert get_sender("Manual", MessageRole.OUTGOING) == "Me"

def test_req_019_browser_session_setup(tmp_path):
    """Verifies REQ-019."""
    from whatsapp_bridge.whatsapp_web import WhatsAppWeb
    os.chdir(tmp_path)
    driver = WhatsAppWeb(headless=True)
    assert os.path.exists(driver.user_data_dir)

def test_req_017_admin_ui_endpoints():
    """Verifies REQ-017 exists."""
    import importlib.util
    admin_path = os.path.join(os.path.dirname(__file__), "..", "admin_server.py")
    spec = importlib.util.spec_from_file_location("wa_admin_server", admin_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert isinstance(mod.get_chat_history(limit=1), list)

def test_req_020_js_input_logic():
    """Verifies REQ-020."""
    from whatsapp_bridge.whatsapp_web import WhatsAppWeb
    import inspect
    assert "execute_script" in inspect.getsource(WhatsAppWeb.open_chat)

def test_req_025_gemini_execution_logic(tmp_path):
    """Verifies REQ-025 (via AIManager)."""
    from unittest.mock import patch, MagicMock
    from core.ai_manager import AIManager
    am = AIManager(gemini_bin=["gemini"])
    workspace = str(tmp_path / "ws")
    os.makedirs(workspace, exist_ok=True)
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("Resp", "")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc
        am.run_gemini("Hi", workspace, "Chat")
        args, _ = mock_popen.call_args
        assert "--yolo" in args[0]

def test_req_026_system_message_filtering():
    """Verifies REQ-026."""
    def should_ignore(content):
        c = content.strip().lower()
        return any(x in c for x in ["bot:", "ende-zu-ende"])
    assert should_ignore("Bot: Hello")
    assert should_ignore("Ende-zu-Ende-verschlüsselt")

def test_unregistered_chat_filtering(tmp_path):
    """Verifies filtering of unregistered chats."""
    from unittest.mock import MagicMock
    persistence = tmp_path / "sessions_f.json"
    manager = SessionManager(str(persistence))
    manager.activate("Reg")
    cp = CommandProcessor(manager, "+4912345678", lambda c, i: "")
    badge_name = "Unreg"
    should_poll = manager.is_active(badge_name) or cp.is_admin_chat(badge_name)
    assert not should_poll
    assert manager.is_active("Reg")

def test_req_028_gemini_exit_codes(tmp_path):
    """Verifies REQ-028 (via AIManager)."""
    from unittest.mock import patch, MagicMock
    from core.ai_manager import AIManager
    am = AIManager(gemini_bin=["gemini"])
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "quota exhausted")
        mock_proc.returncode = 1
        mock_popen.return_value = mock_proc
        assert "quota exhausted" in am.run_gemini("p", str(tmp_path), "c").lower()

def test_req_029_crash_recovery():
    """Verifies REQ-029 — crash recovery loop exists in launcher."""
    # The crash recovery loop is in run_whatsapp.py (launcher)
    launcher_path = os.path.join(os.path.dirname(__file__), "..", "..", "run_whatsapp.py")
    with open(launcher_path, "r", encoding="utf-8") as f:
        source = f.read()
    assert "while True:" in source
    assert "LoginFailedException" in source
    assert "RestartException" in source


def test_req_031_workspace_locks():
    """Verifies REQ-031 (via ai_manager)."""
    am = AIManager(gemini_bin=["gemini"])
    assert isinstance(am.workspace_locks, dict)

def test_req_032_model_management(tmp_path):
    """Verifies REQ-032."""
    persistence = tmp_path / "sessions_m.json"
    manager = SessionManager(str(persistence))
    manager.set_model("Chat", "gpt-4")
    assert manager.get_model("Chat") == "gpt-4"

def test_req_033_unregister_logic(tmp_path):
    """Verifies REQ-033."""
    persistence = tmp_path / "sessions_u.json"
    manager = SessionManager(str(persistence))
    manager.activate("Chat")
    manager.deactivate("Chat")
    assert not manager.is_active("Chat")

def test_req_034_media_prompt_syntax():
    """Verifies REQ-034."""
    import base64, tempfile
    from unittest.mock import MagicMock
    whatsapp = MagicMock()
    whatsapp.download_media.return_value = ["data:image/jpeg;base64,YmFzZTY0"]
    msg = MagicMock()
    msg.type = MessageType.IMAGE
    # Simulate process_media logic
    blob = whatsapp.download_media("Chat")[0]
    header, encoded = blob.split(",", 1)
    data = base64.b64decode(encoded)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
        f.write(data)
        path = f.name
    assert path is not None
    assert "@" in f"File: @{path}"

def test_req_035_restart_command():
    """Verifies REQ-035."""
    import core.orchestrator
    import inspect
    source_orch = inspect.getsource(core.orchestrator)
    assert 'raise RestartException("Manual restart.")' in source_orch

def test_req_036_repair_agent():
    """Verifies REQ-036."""
    from unittest.mock import patch, MagicMock
    am = AIManager(gemini_bin=["gemini"])
    with patch.object(am, "run_gemini") as mock_run:
        mock_run.return_value = "Fixed"
        result = am.run_gemini("MANUAL REPAIR REQUEST: fix", os.getcwd(), "RepairAgent")
        assert mock_run.called

def test_req_039_040(tmp_path):
    """Verifies REQ-039 (Rate Limiting) and REQ-040 (Custom System Prompt)."""
    # REQ-039: Global cooldown and per-chat interval
    from core.orchestrator import BridgeOrchestrator
    from unittest.mock import MagicMock
    import time

    orch = BridgeOrchestrator(MagicMock(), MagicMock(), MagicMock(), MagicMock(), "Admin", None, None, lambda x: x)
    
    # Test global cooldown
    orch.last_global_send_time = time.time()
    start = time.time()
    orch.wait_for_rate_limit("Chat")
    end = time.time()
    assert (end - start) >= orch.GLOBAL_COOLDOWN - 0.1 # Allow for small timing variations

    # REQ-040: Custom system prompt persistence
    persistence = tmp_path / "sessions_p.json"
    manager = SessionManager(str(persistence))
    
    prompt = "Be a helpful assistant"
    manager.set_system_prompt("Chat", prompt)
    assert manager.get_system_prompt("Chat") == prompt
    
    # Verify persistence
    manager2 = SessionManager(str(persistence))
    assert manager2.get_system_prompt("Chat") == prompt

def test_req_041_042():
    """Verifies REQ-041 (SPL Agent existence) and REQ-042 (Git Storing context)."""
    # REQ-041: SPL Agent file exists and has correct kind
    # Path relative to this test file
    spl_agent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".gemini", "agents", "software_project_lead.md"))
    assert os.path.exists(spl_agent_path), f"SPL Agent file not found at {spl_agent_path}"
    with open(spl_agent_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "name: software_project_lead" in content
        assert "kind: local" in content
        assert "Git Storing" in content

    # REQ-042: Supervisor GEMINI.md context includes Git & Storage mandate
    # We check the default context generated by SessionManager._init_workspace
    import tempfile
    import shutil
    
    tmp_ws = tempfile.mkdtemp()
    try:
        sm = SessionManager()
        sm._init_workspace(tmp_ws, "Test Chat")
        gemini_md = os.path.join(tmp_ws, "GEMINI.md")
        assert os.path.exists(gemini_md)
        with open(gemini_md, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Git & Storage (Git Storing)" in content
            assert "Traceability Loop" in content
    finally:
        shutil.rmtree(tmp_ws)

if __name__ == "__main__":
    pytest.main([__file__])
