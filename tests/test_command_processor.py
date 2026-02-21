import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import pytest
from unittest.mock import MagicMock
from core.command_processor import CommandProcessor
from core.session_manager import SessionManager

@pytest.fixture
def mock_session_manager():
    manager = MagicMock(spec=SessionManager)
    manager.is_active.return_value = True
    manager.get_model.return_value = "default"
    manager.get_system_prompt.return_value = ""
    return manager

@pytest.fixture
def command_processor(mock_session_manager):
    return CommandProcessor(mock_session_manager, "+4912345678", lambda c, i: "Repairing...")

def test_system_command_view(command_processor, mock_session_manager):
    mock_session_manager.get_system_prompt.return_value = "Custom Prompt"
    resp = command_processor.process("+4912345678", "/system", True, None)
    assert "current custom system prompt is 'Custom Prompt'" in resp

def test_system_command_set(command_processor, mock_session_manager):
    resp = command_processor.process("+4912345678", "/system New Prompt", True, None)
    mock_session_manager.set_system_prompt.assert_called_once_with("+4912345678", "New Prompt")
    assert "custom system prompt updated" in resp

def test_system_command_reset(command_processor, mock_session_manager):
    resp = command_processor.process("+4912345678", "/system reset", True, None)
    mock_session_manager.set_system_prompt.assert_called_once_with("+4912345678", "")
    assert "reset to default" in resp
