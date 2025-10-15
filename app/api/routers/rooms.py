"""房间管理 API。"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_recording_context, get_uow
from app.schemas.rooms import RoomCreate, RoomRead, RoomUpdate
from app.services.room_service import RoomService
from src.recording.models import Room, RoomStatus


router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomRead])
def list_rooms(uow=Depends(get_uow)):
    service = RoomService(uow.session)
    return service.list_rooms()


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


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(room_id: int, uow=Depends(get_uow), context=Depends(get_recording_context)):
    service = RoomService(uow.session)
    try:
        orm = service.get_room_orm(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        context.service.remove_room(orm.url)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

__all__ = ["router"]
