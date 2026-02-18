"""WebSocket route: streams AgentEvents as JSON to clients."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from retrai.server.run_manager import run_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/api/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    await websocket.accept()

    entry = run_manager.get(run_id)
    if not entry:
        await websocket.send_json({"error": f"Run not found: {run_id}"})
        await websocket.close()
        return

    bus = entry.bus
    q = await bus.subscribe()

    try:
        async for event in bus.iter_events(q):
            await websocket.send_json(event.to_dict())
            if event.kind == "run_end":
                break
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await bus.unsubscribe(q)
        except ValueError:
            pass
        await websocket.close()
