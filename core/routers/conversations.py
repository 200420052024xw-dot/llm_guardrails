from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_schemas import ConversationCreate, ConversationOut, ConversationUpdate, MessageOut
from core.auth import get_current_user
from core.database import get_db
from core.models import Conversation, Message, User, utcnow

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def owned_conversation(conversation_id: str, user_id: str, db: AsyncSession) -> Conversation:
    item = await db.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    if not item:
        raise HTTPException(status_code=404, detail="对话不存在")
    return item


@router.get("", response_model=list[ConversationOut])
async def list_conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    )
    return list(rows)


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(data: ConversationCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = Conversation(user_id=user.id, title=data.title.strip() or "新对话")
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(conversation_id: str, data: ConversationUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await owned_conversation(conversation_id, user.id, db)
    item.title = data.title.strip()
    item.updated_at = utcnow()
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await owned_conversation(conversation_id, user.id, db)
    await db.delete(item)
    await db.commit()


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(conversation_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await owned_conversation(conversation_id, user.id, db)
    rows = await db.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at, Message.id)
    )
    return list(rows)
