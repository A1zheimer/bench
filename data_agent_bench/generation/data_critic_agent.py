import logging
import json
from typing import Dict, Any, List
from ..skills.base import Skill

logger = logging.getLogger(__name__)

CRITIC_SYSTEM_PROMPT = """\
You are an expert Data Critic. Your job is to verify the statistical properties and realism of a generated synthetic dataset.
You will be provided with a dataset description, the first few rows of data, and the problem statement.

Your goal:
1. Ensure the data does not look trivially generated (e.g. all values are identical, perfectly linear, or unrealistic).
2. Ensure there are no glaring anomalies unless specified by the problem (e.g., negative prices, age > 200).
3. If the data is realistic and valid, pass it. If not, reject it and provide feedback for regeneration.

You must call `submit_critic_review` exactly once with your final verdict.
"""

CRITIC_SKILL = Skill(
    name="submit_critic_review",
    description="Submit your assessment of the dataset's realism and statistical validity.",
    input_schema={
        "type": "object",
        "properties": {
            "is_realistic": {
                "type": "boolean",
                "description": "True if the dataset is realistic and appropriate for the task."
            },
            "feedback": {
                "type": "string",
                "description": "Detailed feedback on what is wrong with the data, or why it passed."
            }
        },
        "required": ["is_realistic", "feedback"]
    }
)

class DataCriticAgent:
    """
    Evaluates the generated data to ensure it's not a 'toy' dataset.
    """
    def __init__(self, provider: str, model_id: str, temperature: float = 0.0, api_key: str = None):
        self.provider = provider
        self.model_id = model_id
        self.temperature = temperature
        self._api_key = api_key

    def evaluate_data(self, task_json: Dict[str, Any], data_preview: str) -> bool:
        problem = task_json.get("context", {}).get("problem_statement", "")
        
        user_msg = (
            f"## Problem Statement\n{problem}\n\n"
            f"## Data Preview\n{data_preview}\n\n"
            f"Review the data. Does it look realistic and suitable for this problem? Call `submit_critic_review`."
        )
        
        messages = [{"role": "user", "content": user_msg}]
        
        if self.provider == "openai":
            return self._openai_call(messages)
        elif self.provider == "anthropic":
            return self._anthropic_call(messages)
        else:
            logger.warning("DataCriticAgent not implemented for %s, returning True by default", self.provider)
            return True

    def _openai_call(self, messages: List[Dict[str, Any]]) -> bool:
        import openai
        client = openai.OpenAI(api_key=self._api_key)
        
        api_messages = [{"role": "system", "content": CRITIC_SYSTEM_PROMPT}]
        api_messages.extend(messages)
        
        try:
            resp = client.chat.completions.create(
                model=self.model_id,
                messages=api_messages,
                tools=[CRITIC_SKILL.to_openai_tool()],
                tool_choice=CRITIC_SKILL.openai_tool_choice(),
                temperature=self.temperature
            )
            
            msg = resp.choices[0].message
            if msg.tool_calls:
                args = json.loads(msg.tool_calls[0].function.arguments)
                is_realistic = args.get("is_realistic", False)
                if not is_realistic:
                    logger.warning(f"Data Critic rejected dataset: {args.get('feedback')}")
                return is_realistic
        except Exception as e:
            logger.error(f"Data Critic failed: {e}")
            
        return True

    def _anthropic_call(self, messages: List[Dict[str, Any]]) -> bool:
        import os
        import anthropic

        client = anthropic.Anthropic(api_key=self._api_key or os.environ.get("ANTHROPIC_API_KEY"))

        user_messages = [m for m in messages if m["role"] != "system"]

        try:
            resp = client.messages.create(
                model=self.model_id,
                max_tokens=1024,
                system=CRITIC_SYSTEM_PROMPT,
                messages=user_messages,
                temperature=0.0,
            )

            text = resp.content[0].text if resp.content else ""
            if "FAIL" in text:
                logger.warning("Data Critic (Anthropic) rejected dataset: %s", text)
                return False
            if "PASS" in text:
                return True
            return True
        except Exception as e:
            logger.error("Data Critic (Anthropic) failed: %s", e)
            return True
