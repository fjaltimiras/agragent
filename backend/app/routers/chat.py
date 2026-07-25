import json
import logging
import uuid
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest, ChatResponse, ConversationCreate, ConversationResponse
from app.agent.claude import AgroAgent
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# Singleton agent instance
_agent: AgroAgent = None


def get_agent() -> AgroAgent:
    global _agent
    if _agent is None:
        _agent = AgroAgent()
    return _agent


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Accepts a message and optional conversation_id.
    Creates a new conversation if conversation_id is not provided.
    Returns the assistant's response and any tool calls made.
    """
    db = get_db()
    agent = get_agent()

    conversation_id = str(request.conversation_id) if request.conversation_id else None

    # If no conversation_id, create a new conversation
    if not conversation_id:
        # Derive a short title from the first message
        title = request.message[:60] + ("..." if len(request.message) > 60 else "")
        try:
            result = db.table("conversations").insert({
                "user_id": request.user_id,
                "title": title,
            }).execute()
            conversation_id = result.data[0]["id"]
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error al crear conversación: {str(e)}")

    # Verify conversation exists (and optionally belongs to user)
    try:
        conv_result = db.table("conversations").select("id").eq("id", conversation_id).execute()
        if not conv_result.data:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al verificar conversación: {str(e)}")

    # Run the agent
    try:
        result = await agent.chat(
            message=request.message,
            conversation_id=conversation_id,
            user_id=request.user_id,
            db=db,
            language=request.language,
        )
    except Exception as e:
        logger.error(f"Agent chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en el agente: {str(e)}")

    return ChatResponse(
        message=result["response"],
        conversation_id=uuid.UUID(conversation_id),
        tool_calls_made=result.get("tools_used", []),
    )


@router.post("/new", response_model=dict)
async def new_conversation(body: dict):
    """
    Start a new conversation. Sends a welcome message from the assistant.
    Body: {user_id: str, title: str (optional), field_id: str (optional)}
    Returns: {conversation: ConversationResponse, welcome_message: str}
    """
    db = get_db()
    agent = get_agent()

    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id es requerido")

    title = body.get("title", "Nueva consulta")
    field_id = body.get("field_id")

    # Create conversation
    try:
        insert_data = {"user_id": user_id, "title": title}
        if field_id:
            insert_data["field_id"] = field_id
        result = db.table("conversations").insert(insert_data).execute()
        conversation = result.data[0]
        conversation_id = conversation["id"]
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al crear conversación: {str(e)}")

    # Generate welcome message
    welcome_text = (
        "¡Hola! Soy **agragent**, tu asistente agrónomo experto. "
        "Estoy aquí para ayudarte con análisis de suelo y foliar, "
        "planificación de riego y fertilización, interpretación de datos climáticos y satelitales, "
        "y cualquier consulta agronómica que necesites.\n\n"
        "Para darte las mejores recomendaciones, cuéntame:\n"
        "- ¿Qué cultivo tienes o vas a sembrar?\n"
        "- ¿En qué zona o región estás ubicado?\n"
        "- ¿Cuál es tu consulta principal hoy?\n\n"
        "Si tienes un análisis de suelo o foliar, puedes subirlo directamente con el botón 📎 "
        "y lo interpretaré en detalle. ¡Comencemos!"
    )

    # Save welcome message to DB
    try:
        db.table("messages").insert({
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": welcome_text,
        }).execute()
    except Exception as e:
        logger.warning(f"Error saving welcome message: {str(e)}")

    return {
        "conversation": {
            "id": conversation["id"],
            "user_id": conversation["user_id"],
            "field_id": conversation.get("field_id"),
            "title": conversation["title"],
            "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"],
        },
        "welcome_message": welcome_text,
    }


# ── STREAMING ENDPOINT ────────────────────────────────────────────
@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint via Server-Sent Events (SSE).
    Events: tool_start | text | done | error
    """
    db = get_db()
    agent = get_agent()

    conversation_id = str(request.conversation_id) if request.conversation_id else None

    if not conversation_id:
        title = request.message[:60] + ("..." if len(request.message) > 60 else "")
        try:
            result = db.table("conversations").insert({
                "user_id": request.user_id,
                "title":   title,
            }).execute()
            conversation_id = result.data[0]["id"]
        except Exception as e:
            async def err():
                yield f"data: {json.dumps({'type':'error','content':str(e)})}\n\n"
            return StreamingResponse(err(), media_type="text/event-stream")

    async def event_stream():
        try:
            async for event in agent.chat_stream(
                message=request.message,
                conversation_id=conversation_id,
                user_id=request.user_id,
                db=db,
                language=request.language,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','content':str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
