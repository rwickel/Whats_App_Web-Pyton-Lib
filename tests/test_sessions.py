import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import shutil
import json
import pytest
from core.session_manager import SessionManager

@pytest.fixture
def temp_session_manager(tmp_path):
    persistence_file = tmp_path / "sessions.json"
    manager = SessionManager(persistence_file=str(persistence_file))
    return manager

def test_session_activation(temp_session_manager):
    chat_name = "Test Chat"
    temp_session_manager.activate(chat_name)
    
    assert chat_name in temp_session_manager.active_sessions
    assert os.path.exists(temp_session_manager.active_sessions[chat_name])
    assert temp_session_manager.is_active(chat_name)

def test_session_deactivation(temp_session_manager):
    chat_name = "Test Chat"
    temp_session_manager.activate(chat_name)
    temp_session_manager.deactivate(chat_name)
    
    assert chat_name not in temp_session_manager.active_sessions
    assert not temp_session_manager.is_active(chat_name)

def test_workspace_initialization(temp_session_manager):
    chat_name = "Project X"
    path = temp_session_manager.get_workspace(chat_name)
    
    assert os.path.exists(os.path.join(path, "TODO.md"))
    assert os.path.exists(os.path.join(path, "OBJECTIVE.md"))
    assert os.path.exists(os.path.join(path, "GEMINI.md"))
    
    with open(os.path.join(path, "TODO.md"), "r") as f:
        content = f.read()
        assert chat_name in content

def test_persistence(tmp_path):
    persistence_file = tmp_path / "sessions.json"
    manager1 = SessionManager(persistence_file=str(persistence_file))
    manager1.activate("Persistent Chat")
    
    # New manager instance with same file
    manager2 = SessionManager(persistence_file=str(persistence_file))
    assert "Persistent Chat" in manager2.active_sessions

def test_model_and_prompt_persistence(tmp_path):
    persistence_file = tmp_path / "sessions.json"
    manager1 = SessionManager(persistence_file=str(persistence_file))
    
    chat_name = "AI Chat"
    manager1.activate(chat_name)
    manager1.set_model(chat_name, "gemini-2.0-pro")
    manager1.set_system_prompt(chat_name, "You are a helpful assistant.")
    
    # Reload from persistence
    manager2 = SessionManager(persistence_file=str(persistence_file))
    assert manager2.get_model(chat_name) == "gemini-2.0-pro"
    assert manager2.get_system_prompt(chat_name) == "You are a helpful assistant."
