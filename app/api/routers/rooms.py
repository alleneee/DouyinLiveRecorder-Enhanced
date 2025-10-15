"""房间管理 API。"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_recording_context, get_uow
from app.schemas.rooms import RoomCreate, RoomList, RoomRead, RoomUpdate
from app.services.room_service import RoomService
from app.core.recording.models import Room, RoomStatus


router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=RoomList)
def list_rooms(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    uow=Depends(get_uow),
):
    service = RoomService(uow.session)
    return service.list_rooms(limit=limit, offset=offset)


@router.post("", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
def create_room(payload: RoomCreate, uow=Depends(get_uow), context=Depends(get_recording_context)):
    service = RoomService(uow.session)
    try:
        domain_room = Room(
            url=payload.url,
            quality=payload.quality,
            nickname=payload.nickname,
            status=RoomStatus(payload.status),
            comment=payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        context.service.add_room(domain_room)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    uow.session.expire_all()
    return service.get_room_by_url(domain_room.url)


@router.get("/{room_id}", response_model=RoomRead)
def get_room(room_id: int, uow=Depends(get_uow)):
    service = RoomService(uow.session)
    try:
        return service.get_room(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{room_id}", response_model=RoomRead)
def update_room(room_id: int, payload: RoomUpdate, uow=Depends(get_uow), context=Depends(get_recording_context)):
    service = RoomService(uow.session)
    try:
        orm = service.get_room_orm(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes:
        try:
            RoomStatus(changes["status"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid status value") from exc

    try:
        context.service.update_room(orm.url, **changes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    uow.session.expire_all()
    return service.get_room(room_id)


@router.post("/{room_id}/disable", response_model=RoomRead)
def disable_room(room_id: int, uow=Depends(get_uow), context=Depends(get_recording_context)):
    return _disable_room(room_id, uow, context)


@router.post("/{room_id}/enable", response_model=RoomRead)
def enable_room(room_id: int, uow=Depends(get_uow), context=Depends(get_recording_context)):
    service = RoomService(uow.session)
    try:
        orm = service.get_room_orm(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    updated = context.service.enable_room(orm.url)
    if not updated:
        raise HTTPException(status_code=404, detail="Room not found")

    uow.session.expire_all()
    return service.get_room(room_id)


@router.delete("/{room_id}", response_model=RoomRead)
def delete_room(room_id: int, uow=Depends(get_uow), context=Depends(get_recording_context)):
    return _disable_room(room_id, uow, context)


def _disable_room(room_id: int, uow, context) -> RoomRead:
    service = RoomService(uow.session)
    try:
        orm = service.get_room_orm(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    updated = context.service.disable_room(orm.url)
    if not updated:
        raise HTTPException(status_code=404, detail="Room not found")

    uow.session.expire_all()
    return service.get_room(room_id)

__all__ = ["router"]
