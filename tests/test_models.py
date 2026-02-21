import os
import sys
# Add project root to sys.path so we can import from whatsapp_bridge
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest
from whatsapp_bridge.whatsapp_web.models import Message, ChatChannel

def test_message_model():
    msg = Message(role="incoming", content="Hello", type="text")
    assert msg.role == "incoming"
    assert msg.content == "Hello"
    assert msg.type == "text"
    assert msg.media_base64 is None

def test_message_with_media():
    blobs = ["data:image/jpeg;base64,123", "data:image/jpeg;base64,456"]
    msg = Message(role="outgoing", content="[Image]", type="image", media_base64=blobs)
    assert msg.type == "image"
    assert len(msg.media_base64) == 2
    assert msg.media_base64[0] == "data:image/jpeg;base64,123"

def test_chatchannel_model():
    chat = ChatChannel(name="Test Group", unread_count=5, is_group=True)
    assert chat.name == "Test Group"
    assert chat.unread_count == 5
    assert chat.is_group is True

def test_message_validation_error():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        # Invalid role
        Message(role="invalid", content="test")
