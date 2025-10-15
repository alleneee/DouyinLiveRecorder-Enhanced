"""录制控制 API。"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_recording_context, get_uow
from app.schemas.recordings import RecordingRead, RecordingStart, RecordingStop
from app.services.recording_service import RecordingService
from app.services.room_service import RoomService
from src.recording.models import RoomStatus


router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.get("/{room_id}", response_model=list[RecordingRead])
def get_recordings(room_id: int, uow=Depends(get_uow)):
    service = RecordingService(uow.session)
    return service.list_by_room(room_id)


@router.post("/{room_id}/start", response_model=RecordingRead, status_code=status.HTTP_202_ACCEPTED)
def start_recording(
    room_id: int,
    payload: RecordingStart,
    uow=Depends(get_uow),
    context=Depends(get_recording_context),
):
    room_service = RoomService(uow.session)
    try:
        orm = room_service.get_room_orm(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    recording_service = RecordingService(uow.session)
    active = recording_service.get_active_entry(room_id)
    if active and not payload.force:
        return active

    if active and payload.force:
        recording_service.mark_stopped(active.id, error_message="Force restart")
        context.service.update_room(orm.url, status=RoomStatus.DISABLED.value)

    context.service.update_room(orm.url, status=RoomStatus.RECORDING.value)
    entry = recording_service.mark_started(room_id)
    return entry


@router.post("/{room_id}/stop", response_model=RecordingRead)
def stop_recording(
    room_id: int,
    payload: RecordingStop,
    uow=Depends(get_uow),
    context=Depends(get_recording_context),
):
    room_service = RoomService(uow.session)
    try:
        orm = room_service.get_room_orm(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    recording_service = RecordingService(uow.session)
    active = recording_service.get_active_entry(room_id)
    if not active:
        raise HTTPException(status_code=404, detail="Active recording not found")

    entry = recording_service.mark_stopped(active.id, error_message=payload.reason)
    context.service.update_room(orm.url, status=RoomStatus.DISABLED.value)
    return entry


__all__ = ["router"]
