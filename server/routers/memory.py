"""Memory management API."""

from fastapi import APIRouter, HTTPException, Query

from server.memory.long_term import LongTermMemory

router = APIRouter()


@router.get("/memory/long-term/candidates")
def list_long_term_candidates(
    kb_id: int | None = None,
    status: str = "pending",
    limit: int = Query(default=50, ge=1, le=200),
):
    return LongTermMemory().list_candidates(kb_id=kb_id, status=status, limit=limit)


@router.post("/memory/long-term/candidates/{candidate_id}/approve")
def approve_long_term_candidate(candidate_id: int):
    try:
        return LongTermMemory().approve_candidate(candidate_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="memory candidate not found")


@router.post("/memory/long-term/candidates/{candidate_id}/reject")
def reject_long_term_candidate(candidate_id: int):
    try:
        return LongTermMemory().reject_candidate(candidate_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="memory candidate not found")


@router.get("/memory/long-term/items")
def list_long_term_items(
    kb_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    return LongTermMemory().list_items(kb_id=kb_id, limit=limit)


@router.get("/memory/long-term/usage")
def list_long_term_usage(
    kb_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    return LongTermMemory().list_usage(kb_id=kb_id, limit=limit)
