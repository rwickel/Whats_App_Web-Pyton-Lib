from pydantic import BaseModel
from typing import Optional, Literal

class Message(BaseModel):
    role: Literal["incoming", "outgoing"]
    content: str
    type: Literal["text", "audio", "video", "image", "other", "contact"] = "text"
    timestamp: Optional[str] = None
    media_base64: Optional[list[str]] = None

class ChatChannel(BaseModel):
    name: str
    unread_count: int = 0
    is_group: bool = False
