"""
Announcement endpoints for the High School Management System API
"""

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementUpsert(BaseModel):
    """Payload for creating/updating announcements."""

    message: str = Field(..., min_length=5, max_length=300)
    expires_on: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    starts_on: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


def parse_iso_date(date_text: str, field_name: str) -> date:
    """Parse date in ISO format and return a date object."""
    try:
        return date.fromisoformat(date_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be a valid date in YYYY-MM-DD format"
        ) from exc


def ensure_teacher_authenticated(teacher_username: Optional[str]) -> Dict[str, Any]:
    """Validate teacher identity by username."""
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


def serialize_announcement(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB document to API response schema."""
    return {
        "id": doc["_id"],
        "message": doc["message"],
        "starts_on": doc.get("starts_on"),
        "expires_on": doc["expires_on"]
    }


@router.get("", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get only currently active announcements for public display."""
    today = date.today().isoformat()
    query = {
        "$and": [
            {"expires_on": {"$gte": today}},
            {
                "$or": [
                    {"starts_on": None},
                    {"starts_on": {"$lte": today}}
                ]
            }
        ]
    }

    docs = announcements_collection.find(query).sort("expires_on", 1)
    return [serialize_announcement(doc) for doc in docs]


@router.get("/manage", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Get all announcements for management. Authentication required."""
    ensure_teacher_authenticated(teacher_username)
    docs = announcements_collection.find({}).sort("expires_on", 1)
    return [serialize_announcement(doc) for doc in docs]


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    payload: AnnouncementUpsert,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Create a new announcement. Authentication required."""
    ensure_teacher_authenticated(teacher_username)

    starts_on_date = parse_iso_date(payload.starts_on, "starts_on") if payload.starts_on else None
    expires_on_date = parse_iso_date(payload.expires_on, "expires_on")

    if starts_on_date and starts_on_date > expires_on_date:
        raise HTTPException(status_code=400, detail="starts_on cannot be after expires_on")

    doc_id = str(uuid4())
    announcements_collection.insert_one(
        {
            "_id": doc_id,
            "message": payload.message.strip(),
            "starts_on": payload.starts_on,
            "expires_on": payload.expires_on
        }
    )

    return {
        "message": "Announcement created successfully",
        "announcement": {
            "id": doc_id,
            "message": payload.message.strip(),
            "starts_on": payload.starts_on,
            "expires_on": payload.expires_on
        }
    }


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    payload: AnnouncementUpsert,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Update an announcement. Authentication required."""
    ensure_teacher_authenticated(teacher_username)

    starts_on_date = parse_iso_date(payload.starts_on, "starts_on") if payload.starts_on else None
    expires_on_date = parse_iso_date(payload.expires_on, "expires_on")

    if starts_on_date and starts_on_date > expires_on_date:
        raise HTTPException(status_code=400, detail="starts_on cannot be after expires_on")

    result = announcements_collection.update_one(
        {"_id": announcement_id},
        {
            "$set": {
                "message": payload.message.strip(),
                "starts_on": payload.starts_on,
                "expires_on": payload.expires_on
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {
        "message": "Announcement updated successfully",
        "announcement": {
            "id": announcement_id,
            "message": payload.message.strip(),
            "starts_on": payload.starts_on,
            "expires_on": payload.expires_on
        }
    }


@router.delete("/{announcement_id}", response_model=Dict[str, Any])
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Delete an announcement. Authentication required."""
    ensure_teacher_authenticated(teacher_username)

    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
