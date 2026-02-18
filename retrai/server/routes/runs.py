"""REST routes for run management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from retrai.config import RunConfig
from retrai.server.run_manager import run_manager

router = APIRouter(prefix="/api/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    goal: str
    cwd: str = "."
    model_name: str = "claude-sonnet-4-6"
    max_iterations: int = 20
    hitl_enabled: bool = False


class ResumeRunRequest(BaseModel):
    decision: str = "approve"  # "approve" | "abort"


@router.post("")
async def create_run(req: CreateRunRequest):
    cfg = RunConfig(
        goal=req.goal,
        cwd=req.cwd,
        model_name=req.model_name,
        max_iterations=req.max_iterations,
        hitl_enabled=req.hitl_enabled,
    )
    entry = run_manager.create(cfg)
    await run_manager.start_run(entry.run_id)
    return {"run_id": entry.run_id, "status": entry.status}


@router.get("")
async def list_runs():
    runs = run_manager.list_runs()
    return [
        {
            "run_id": r.run_id,
            "goal": r.config.goal,
            "status": r.status,
            "model_name": r.config.model_name,
            "max_iterations": r.config.max_iterations,
            "cwd": r.config.cwd,
        }
        for r in runs
    ]


@router.get("/{run_id}")
async def get_run(run_id: str):
    entry = run_manager.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": entry.run_id,
        "goal": entry.config.goal,
        "status": entry.status,
        "model_name": entry.config.model_name,
        "max_iterations": entry.config.max_iterations,
        "hitl_enabled": entry.config.hitl_enabled,
        "cwd": entry.config.cwd,
        "error": entry.error,
        "final_state": (
            {
                "iteration": entry.final_state.get("iteration"),
                "goal_achieved": entry.final_state.get("goal_achieved"),
                "goal_reason": entry.final_state.get("goal_reason"),
            }
            if entry.final_state
            else None
        ),
    }


@router.post("/{run_id}/resume")
async def resume_run(run_id: str, req: ResumeRunRequest):
    entry = run_manager.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        await run_manager.resume_run(run_id, req.decision)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"run_id": run_id, "resumed_with": req.decision}


@router.post("/{run_id}/abort")
async def abort_run(run_id: str):
    entry = run_manager.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        await run_manager.abort_run(run_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"run_id": run_id, "status": "aborted"}


class PatchConfigRequest(BaseModel):
    max_iterations: int | None = None
    model_name: str | None = None
    hitl_enabled: bool | None = None


@router.patch("/{run_id}/config")
async def patch_config(run_id: str, req: PatchConfigRequest):
    entry = run_manager.get(run_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        run_manager.update_config(
            run_id,
            max_iterations=req.max_iterations,
            model_name=req.model_name,
            hitl_enabled=req.hitl_enabled,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "run_id": run_id,
        "max_iterations": entry.config.max_iterations,
        "model_name": entry.config.model_name,
        "hitl_enabled": entry.config.hitl_enabled,
    }
