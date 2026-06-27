import json
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_schemas import ConfidentialEntryIn, ConfidentialEntryOut, PublicEntryIn, PublicEntryOut
from core.auth import get_current_user
from core.database import get_db
from core.guardrail_service import evaluate_text
from core.models import ConfidentialEntry, ImportJob, PublicEntry, User
from core.vector_store import vectorize_user_facts, debounce_vectorize, _get_embedding_client

router = APIRouter(prefix="/libraries", tags=["libraries"])


async def _get_user_facts(db: AsyncSession, user_id: str) -> list[dict]:
    """Get all confidential facts for a user."""
    items = list(await db.scalars(select(ConfidentialEntry).where(ConfidentialEntry.user_id == user_id, ConfidentialEntry.enabled.is_(True))))
    return [
        {
            "fact_id": item.id,
            "fact_type": item.category,
            "confidential_level": item.confidential_level or "high",
            "fact_text": item.text,
            "fact_summary": item.summary or "",
            "paraphrases": item.paraphrases or [],
            "negative_samples": item.negative_samples or [],
            "keywords": item.keywords or [],
        }
        for item in items
    ]


async def _owned(model, item_id: str, user_id: str, db: AsyncSession):
    item = await db.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
    if not item:
        raise HTTPException(status_code=404, detail="条目不存在")
    return item


@router.get("/confidential", response_model=list[ConfidentialEntryOut])
async def confidential_list(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return list(await db.scalars(select(ConfidentialEntry).where(ConfidentialEntry.user_id == user.id).order_by(ConfidentialEntry.created_at.desc())))


@router.post("/confidential", response_model=ConfidentialEntryOut, status_code=201)
async def confidential_create(data: ConfidentialEntryIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    duplicate = await db.scalar(select(ConfidentialEntry).where(ConfidentialEntry.user_id == user.id, ConfidentialEntry.text == data.text))
    if duplicate:
        raise HTTPException(status_code=409, detail="该保密条目已存在")
    item = ConfidentialEntry(user_id=user.id, **data.model_dump())
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="该保密条目已存在")
    await db.refresh(item)
    # Trigger debounced vectorization
    facts = await _get_user_facts(db, user.id)
    embedding_client = _get_embedding_client()
    import asyncio
    asyncio.create_task(debounce_vectorize(user.id, facts, embedding_client))
    return item


@router.put("/confidential/{item_id}", response_model=ConfidentialEntryOut)
async def confidential_update(item_id: str, data: ConfidentialEntryIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(ConfidentialEntry, item_id, user.id, db)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    await db.commit(); await db.refresh(item)
    return item


@router.delete("/confidential/{item_id}", status_code=204)
async def confidential_delete(item_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.delete(await _owned(ConfidentialEntry, item_id, user.id, db)); await db.commit()
    # Re-vectorize after deletion
    facts = await _get_user_facts(db, user.id)
    embedding_client = _get_embedding_client()
    await vectorize_user_facts(user.id, facts, embedding_client)


@router.get("/public", response_model=list[PublicEntryOut])
async def public_list(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return list(await db.scalars(select(PublicEntry).where(PublicEntry.user_id == user.id).order_by(PublicEntry.created_at.desc())))


@router.post("/public", response_model=PublicEntryOut, status_code=201)
async def public_create(data: PublicEntryIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = PublicEntry(user_id=user.id, **data.model_dump()); db.add(item)
    try: await db.commit()
    except IntegrityError:
        await db.rollback(); raise HTTPException(status_code=409, detail="该公开条目已存在")
    await db.refresh(item); return item


@router.put("/public/{item_id}", response_model=PublicEntryOut)
async def public_update(item_id: str, data: PublicEntryIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(PublicEntry, item_id, user.id, db)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    await db.commit(); await db.refresh(item); return item


@router.delete("/public/{item_id}", status_code=204)
async def public_delete(item_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.delete(await _owned(PublicEntry, item_id, user.id, db)); await db.commit()


@router.post("/{library_type}/import")
async def import_jsonl(
    library_type: Literal["confidential", "public"],
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 5MB")
    imported = errors = 0
    for line in raw.decode("utf-8-sig").splitlines():
        if not line.strip(): continue
        try:
            async with db.begin_nested():
                data = json.loads(line)
                if library_type == "confidential":
                    text = data.get("text") or data.get("fact_text")
                    if not text:
                        raise ValueError("missing text")
                    duplicate = await db.scalar(select(ConfidentialEntry.id).where(ConfidentialEntry.user_id == user.id, ConfidentialEntry.text == text))
                    if duplicate:
                        raise ValueError("duplicate text")
                    db.add(ConfidentialEntry(
                        user_id=user.id, text=text,
                        category=data.get("category") or data.get("fact_type", "confidential"),
                        confidential_level=data.get("confidential_level", "high"),
                        summary=data.get("summary") or data.get("fact_summary"),
                        paraphrases=data.get("paraphrases", []),
                        negative_samples=data.get("negative_samples", []),
                        keywords=data.get("keywords", []),
                    ))
                else:
                    parsed = PublicEntryIn(entity_type=data["type"], value=str(data["value"]), label=data.get("label", ""))
                    db.add(PublicEntry(user_id=user.id, **parsed.model_dump()))
                await db.flush()
            imported += 1
        except Exception:
            errors += 1
    job = ImportJob(user_id=user.id, library_type=library_type, imported_count=imported, error_count=errors)
    db.add(job); await db.commit()
    # Immediate vectorization for confidential imports
    if library_type == "confidential" and imported > 0:
        facts = await _get_user_facts(db, user.id)
        embedding_client = _get_embedding_client()
        await vectorize_user_facts(user.id, facts, embedding_client)
    return {"job_id": job.id, "imported_count": imported, "error_count": errors}


class TestDetectionIn(BaseModel):
    text: str


@router.post("/confidential/test")
async def test_confidential_detection(
    data: TestDetectionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result, traces = await evaluate_text(user.id, data.text, db)
    return {
        "action": result.action,
        "risk_score": result.risk_score,
        "risk_types": result.risk_types,
        "message": result.message,
        "safe_input": result.safe_input,
        "traces": traces,
    }
