import re
import logging
from typing import Any, Dict, List

from .client_adapters import get_llm_client
from ..agent_interface import AgentInterface, AgentAction
from ...models.task import TaskInput
from ...models.trace import ActionType, TraceStep

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Data Scientist.
Your task is to analyze data and provide a final answer based on the provided problem statement.

## Environment
You have access to a **stateful** Python REPL. This means that any variables defined or libraries imported in one step will be available in subsequent steps.

To use the REPL, you must write Python code in a Markdown code block like this:
```python
# your code here
import pandas as pd
df = pd.read_csv(DATA_PATH)
print(df.head())
```
The system will execute your code and return the output (stdout, stderr, and the value of the last expression) as an "Observation".

## Guidelines
1. **Stateful Analysis**: Leverage the persistent environment. Don't re-import libraries or re-load data unnecessarily.
2. **Step-by-Step**: Perform complex analyses in small, verifiable steps.
3. **Error Handling**: If you encounter an error, analyze the Traceback provided in the Observation and try to fix your code in the next step.
4. **Final Answer Format**: Once you have the answer, provide a JSON object after FINAL ANSWER with both numerical results and a declared typed trace:
   FINAL ANSWER: {"key_values": {"key1": value1}, "declared_trace": [{"step_id":"s1","subject":"agent","predicate":"LOADS","object":"dataset.csv","intent":"load_data","operation":"read_csv","inputs":["DATA_PATH"],"outputs":["df"],"depends_on":[],"evidence_step":1,"status":"success"}]}
   The declared_trace must summarize your actual process. Each evidence_step should point to the observed tool/code step that supports the claim.

## Data Science Best Practices
- Always check for missing values and data types.
- Use appropriate statistical tests for the task.
- Ensure numerical results are clearly labeled.
"""

class NativeCodeAgent(AgentInterface):
    def __init__(self, model_id: str, temperature: float = 0.0):
        self.model_id = model_id
        self.temperature = temperature
        self.client = get_llm_client(model_id)
        self.messages: List[Dict[str, str]] = []
        self._done = False

    def reset(self, task: TaskInput) -> None:
        prompt = SYSTEM_PROMPT + f"""

## Task
{task.context.problem_statement}

## Data Preview
{task.context.dataset_preview or "(none)"}

## Expert Knowledge
{task.context.expert_knowledge or "None provided."}

## Data Paths
- `DATA_PATH`: Path to the primary dataset.
- `DATA_DIR`: Directory containing task-related data files.
"""
        self.messages = [
            {"role": "system", "content": prompt}
        ]
        self._done = False

    def act(
        self,
        step_number: int,
        observation: str,
        trace_so_far: List[TraceStep],
    ) -> AgentAction:
        if self._done:
            return AgentAction(
                action_type=ActionType.FINAL_ANSWER,
                action="Task complete",
            )

        # Append observation to history
        if step_number == 1:
            # First step: the observation contains the initial task context
            self.messages.append({"role": "user", "content": f"Context and initial observation:\n{observation}"})
        elif observation:
            self.messages.append({"role": "user", "content": f"Observation:\n{observation}"})

        # Call LLM
        try:
            response = self.client.generate(self.messages, temperature=self.temperature)
            reply_text = response.text
            self.messages.append({"role": "assistant", "content": reply_text})
        except Exception as e:
            logger.error("LLM Error: %s", e)
            return AgentAction(
                action_type=ActionType.ERROR,
                action="LLM API Error",
                thought=f"Error calling LLM: {str(e)}",
            )

        # Parse reply
        code_blocks = re.findall(r"```python\n(.*?)\n```", reply_text, re.DOTALL)
        # Handle cases where agent doesn't put newline after ```python
        if not code_blocks:
            code_blocks = re.findall(r"```python(.*?)\n```", reply_text, re.DOTALL)
        
        is_final = "FINAL ANSWER" in reply_text.upper() or "TASK MARKED AS COMPLETE" in reply_text.upper()
        
        # Priority 1: Execute Code (if code exists, execute it)
        if code_blocks:
            if is_final:
                self._done = True  # Mark as done so executor stops AFTER this code step
            
            # We take the first block found
            code = code_blocks[0].strip()
            return AgentAction(
                action_type=ActionType.CODE_EXEC,
                action="Execute Code",
                thought=reply_text,
                tool_name="python_repl",
                tool_args={"code": code},
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
            )

        # Priority 2: Final Answer
        if is_final:
            self._done = True
            return AgentAction(
                action_type=ActionType.FINAL_ANSWER,
                action="Final Answer",
                thought=reply_text,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
            )
        
        # Priority 3: Just thinking
        return AgentAction(
            action_type=ActionType.THINK,
            action="Think",
            thought=reply_text,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
        )

    def is_done(self) -> bool:
        return self._done
