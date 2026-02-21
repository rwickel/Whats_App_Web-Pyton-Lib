import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import pytest
from unittest.mock import MagicMock, patch
from core.ai_manager import AIManager

@pytest.fixture
def ai_manager():
    return AIManager(gemini_bin=["echo"])

def test_worker_calls_run_gemini_in_two_phases(ai_manager):
    captured_calls = []
    
    def mock_run_gemini(prompt, *args, **kwargs):
        captured_calls.append(prompt)
        return f"Response for {prompt[:10]}"

    with patch.object(ai_manager, 'run_gemini', side_effect=mock_run_gemini) as mock_run:
        ai_manager.worker("MyPrompt", "/ws", "Chat1", "model1", "System Prompt", None)
        
        # Verify two phases were called
        assert len(captured_calls) == 2
        assert "PHASE 1: PLANNING" in captured_calls[0]
        assert "MyPrompt" in captured_calls[0]
        assert "PHASE 2: EXECUTION" in captured_calls[1]
        assert "MyPrompt" in captured_calls[1]
        
        # Verify response queue contains two items
        assert ai_manager.response_queue.qsize() == 2
        
        chat1, resp1 = ai_manager.response_queue.get()
        assert chat1 == "Chat1"
        assert "📋 **PLAN**" in resp1
        
        chat2, resp2 = ai_manager.response_queue.get()
        assert chat2 == "Chat1"
        assert "Response for PHASE 2: E" in resp2

def test_worker_cleanup_temp_files(ai_manager, tmp_path):
    # Create a dummy temp file to be cleaned up
    temp_media = tmp_path / "media.jpg"
    temp_media.write_text("data")
    
    with patch.object(ai_manager, 'run_gemini') as mock_run:
        mock_run.return_value = "Done"
        
        ai_manager.worker("P", str(tmp_path), "C", "m", "System", str(temp_media))
        
        # Verify temp_media is gone
        assert not os.path.exists(str(temp_media))
        
        # Verify system_md temp file is also gone (from try-finally)
        _, kwargs = mock_run.call_args
        system_md_path = kwargs.get('system_md')
        if system_md_path:
            assert not os.path.exists(system_md_path)
