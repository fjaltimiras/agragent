import logging
from fastapi import APIRouter, HTTPException
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{user_id}")
async def list_conversations(user_id: str):
    """
    List all conversations for a user, ordered by most recently updated.
    Returns id, title, created_at, updated_at, and last message preview.
    """
    db = get_db()
    try:
        result = (
            db.table("conversations")
            .select("id, title, created_at, updated_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        conversations = result.data

        # Fetch last message for each conversation for preview
        enriched = []
        for conv in conversations:
            conv_id = conv["id"]
            try:
                msg_result = (
                    db.table("messages")
                    .select("content, role, created_at")
                    .eq("conversation_id", conv_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                last_msg = msg_result.data[0] if msg_result.data else None
                conv["last_message"] = (
                    last_msg["content"][:100] + "..." if last_msg and last_msg.get("content") and len(last_msg["content"]) > 100
                    else last_msg["content"] if last_msg else None
                )
                conv["last_message_role"] = last_msg["role"] if last_msg else None
            except Exception:
                conv["last_message"] = None
                conv["last_message_role"] = None
            enriched.append(conv)

        return {"conversations": enriched, "total": len(enriched)}

    except Exception as e:
        logger.error(f"Error listing conversations for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener conversaciones: {str(e)}")


@router.get("/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    """
    Get all messages for a given conversation, ordered chronologically.
    """
    db = get_db()
    try:
        # Verify conversation exists
        conv_result = (
            db.table("conversations")
            .select("id, title, user_id, created_at, updated_at")
            .eq("id", conversation_id)
            .execute()
        )
        if not conv_result.data:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        conversation = conv_result.data[0]

        # Get messages
        msg_result = (
            db.table("messages")
            .select("id, role, content, tool_calls, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )
        messages = msg_result.data

        return {
            "conversation": conversation,
            "messages": messages,
            "total_messages": len(messages),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages for conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener mensajes: {str(e)}")


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete a conversation and all its messages (cascade).
    """
    db = get_db()
    try:
        # Verify it exists
        conv_result = db.table("conversations").select("id").eq("id", conversation_id).execute()
        if not conv_result.data:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")

        # Delete (messages cascade via FK)
        db.table("conversations").delete().eq("id", conversation_id).execute()
        return {"success": True, "message": "Conversación eliminada correctamente"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar conversación: {str(e)}")


@router.patch("/{conversation_id}")
async def update_conversation(conversation_id: str, body: dict):
    """
    Update conversation title.
    Body: {title: str}
    """
    db = get_db()
    title = body.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="El campo 'title' es requerido")

    try:
        result = (
            db.table("conversations")
            .update({"title": title, "updated_at": "now()"})
            .eq("id", conversation_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        return {"success": True, "conversation": result.data[0]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar conversación: {str(e)}")
