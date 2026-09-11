from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Content, ContentStatus
from app.schemas import ContentCreate, ContentResponse, ContentUpdate

router = APIRouter(prefix="/api/contents", tags=["contents"])


@router.get("/", response_model=list[ContentResponse])
async def list_contents(status: str | None = None, db: AsyncSession = Depends(get_db)):
    q = select(Content)
    if status:
        q = q.where(Content.status == status)
    q = q.order_by(Content.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(content_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return content


@router.post("/", response_model=ContentResponse, status_code=201)
async def create_content(data: ContentCreate, db: AsyncSession = Depends(get_db)):
    content = Content(**data.model_dump())
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


@router.patch("/{content_id}", response_model=ContentResponse)
async def update_content(
    content_id: int, data: ContentUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(content, field, value)

    await db.commit()
    await db.refresh(content)
    return content


@router.post("/{content_id}/approve", response_model=ContentResponse)
async def approve_content(content_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    if content.status != ContentStatus.REVIEW:
        raise HTTPException(status_code=400, detail="Only review content can be approved")

    content.status = ContentStatus.SCHEDULED
    await db.commit()
    await db.refresh(content)
    return content


@router.post("/{content_id}/reject", response_model=ContentResponse)
async def reject_content(content_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    content.status = ContentStatus.REJECTED
    await db.commit()
    await db.refresh(content)
    return content


@router.post("/{content_id}/publish")
async def publish_now(content_id: int):
    from app.services.publisher import publish_content

    result = await publish_content(content_id, force=False)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Publish failed"))
    return result
