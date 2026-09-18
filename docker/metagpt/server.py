"""MetaGPT DataInterpreter HTTP server for DataAgentBench."""
import asyncio
import json
import os
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="MetaGPT DataInterpreter Agent")


class TaskRequest(BaseModel):
    task_id: str
    problem_statement: str
    dataset_preview: str = ""
    expert_knowledge: str = ""
    data_path: Optional[str] = None  # 容器内数据路径


class TaskResponse(BaseModel):
    task_id: str
    status: str  # "success" | "error"
    final_answer: str = ""
    steps: list = []
    error: str = ""


@app.get("/health")
def health():
    return {"status": "ok", "agent": "metagpt-data-interpreter"}


@app.post("/run_task", response_model=TaskResponse)
async def run_task(req: TaskRequest):
    try:
        from metagpt.roles.di.data_interpreter import DataInterpreter

        # 构建 prompt
        prompt_parts = [req.problem_statement]
        if req.dataset_preview:
            prompt_parts.append(f"\n## Dataset Preview\n{req.dataset_preview}")
        if req.expert_knowledge:
            prompt_parts.append(f"\n## Expert Knowledge\n{req.expert_knowledge}")
        if req.data_path:
            prompt_parts.append(f"\n## Data File\nThe dataset is located at: {req.data_path}")

        prompt = "\n".join(prompt_parts)

        di = DataInterpreter()
        result = await di.run(prompt)

        # 提取步骤
        steps = []
        if hasattr(di, "working_memory") and hasattr(di.working_memory, "history"):
            for msg in di.working_memory.history:
                steps.append({
                    "role": getattr(msg, "role", "unknown"),
                    "content": str(getattr(msg, "content", ""))[:500],
                })

        return TaskResponse(
            task_id=req.task_id,
            status="success",
            final_answer=str(result)[:5000],
            steps=steps,
        )

    except Exception as e:
        return TaskResponse(
            task_id=req.task_id,
            status="error",
            error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()[-500:]}",
        )
