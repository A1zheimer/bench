"""Open Interpreter HTTP server for DataAgentBench."""
import json
import os
import traceback
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Open Interpreter Agent")


class TaskRequest(BaseModel):
    task_id: str
    problem_statement: str
    dataset_preview: str = ""
    expert_knowledge: str = ""
    data_path: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    status: str
    final_answer: str = ""
    steps: list = []
    error: str = ""


@app.get("/health")
def health():
    return {"status": "ok", "agent": "open-interpreter"}


@app.post("/run_task", response_model=TaskResponse)
def run_task(req: TaskRequest):
    try:
        from interpreter import interpreter

        # 配置
        interpreter.llm.model = os.environ.get("OI_MODEL", "gpt-4o")
        interpreter.auto_run = True
        interpreter.llm.max_tokens = 4096
        interpreter.max_output = 10000

        # 如果设置了 API base
        api_base = os.environ.get("OPENAI_BASE_URL")
        if api_base:
            interpreter.llm.api_base = api_base

        # 构建 prompt
        prompt_parts = [req.problem_statement]
        if req.dataset_preview:
            prompt_parts.append(f"\n## Dataset Preview\n{req.dataset_preview}")
        if req.expert_knowledge:
            prompt_parts.append(f"\n## Expert Knowledge\n{req.expert_knowledge}")
        if req.data_path:
            prompt_parts.append(f"\n## Data File\nThe dataset is located at: {req.data_path}")

        prompt = "\n".join(prompt_parts)

        # 执行
        messages = interpreter.chat(prompt, display=False)

        # 提取步骤和最终答案
        steps = []
        final_answer = ""
        for msg in messages:
            role = msg.get("role", "unknown")
            msg_type = msg.get("type", "message")
            content = str(msg.get("content", ""))[:500]
            steps.append({"role": role, "type": msg_type, "content": content})

            if role == "assistant" and msg_type == "message":
                final_answer = str(msg.get("content", ""))

        # 清理状态
        interpreter.messages = []

        return TaskResponse(
            task_id=req.task_id,
            status="success",
            final_answer=final_answer[:5000],
            steps=steps,
        )

    except Exception as e:
        return TaskResponse(
            task_id=req.task_id,
            status="error",
            error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()[-500:]}",
        )
