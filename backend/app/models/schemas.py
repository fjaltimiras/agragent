from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from uuid import UUID
from datetime import datetime


class MessageCreate(BaseModel):
    conversation_id: UUID
    content: str


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: Optional[str] = None
    tool_calls: Optional[Any] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: Optional[str] = "Nueva consulta"
    field_id: Optional[UUID] = None


class ConversationResponse(BaseModel):
    id: UUID
    user_id: str
    field_id: Optional[UUID] = None
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationWithMessages(ConversationResponse):
    messages: List[MessageResponse] = []


class ChatRequest(BaseModel):
    conversation_id: Optional[UUID] = None
    message: str
    user_id: str
    language: Optional[str] = None  # "en", "es", "pt"


class ChatResponse(BaseModel):
    message: str
    conversation_id: UUID
    tool_calls_made: List[str] = []


class UploadResponse(BaseModel):
    analysis_id: UUID
    type: str
    parsed_data: Dict[str, Any]


class FieldCreate(BaseModel):
    name: str
    crop_type: Optional[str] = None
    area_ha: Optional[float] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class FieldResponse(BaseModel):
    id: UUID
    user_id: str
    name: str
    crop_type: Optional[str] = None
    area_ha: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationUpdate(BaseModel):
    title: str


class ConversationListItem(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None
