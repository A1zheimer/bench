"""
Skill base class: provider-agnostic structured output via tool_use.

A Skill defines a tool schema that can be forced via tool_choice,
guaranteeing the LLM's response conforms to the schema. No regex parsing.

Usage:
    skill = Skill(name="submit_verdict", description="...", input_schema={...})

    # Anthropic
    tools = [skill.to_anthropic_tool()]
    tool_choice = skill.anthropic_tool_choice()

    # OpenAI
    tools = [skill.to_openai_tool()]
    tool_choice = skill.openai_tool_choice()
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class Skill:
    """
    A structured output schema enforced via forced tool_choice.

    Attributes:
        name: Tool name (e.g. "submit_verdict", "submit_task").
        description: Human-readable description shown to the LLM.
        input_schema: JSON Schema defining the expected output structure.
    """

    name: str
    description: str
    input_schema: Dict[str, Any]

    # ----- Provider adapters -----

    def to_anthropic_tool(self) -> Dict[str, Any]:
        """Anthropic Messages API tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def to_openai_tool(self) -> Dict[str, Any]:
        """OpenAI Chat Completions function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def anthropic_tool_choice(self) -> Dict[str, Any]:
        """Force Anthropic to call this specific tool."""
        return {"type": "tool", "name": self.name}

    def openai_tool_choice(self) -> Dict[str, Any]:
        """Force OpenAI to call this specific function."""
        return {"type": "function", "function": {"name": self.name}}

    # ----- Validation -----

    def validate_output(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate tool output against the schema.

        Returns a list of error strings (empty = valid).
        Performs lightweight checks without a full JSON Schema library.
        """
        errors: List[str] = []
        props = self.input_schema.get("properties", {})
        required = set(self.input_schema.get("required", []))

        # Check required fields
        for field in required:
            if field not in data:
                errors.append(f"Missing required field: '{field}'")

        # Check types and ranges for present fields
        for field, value in data.items():
            if field not in props:
                continue
            spec = props[field]
            field_type = spec.get("type")

            # Type check (simple)
            if field_type == "number" and not isinstance(value, (int, float)):
                if value is not None:
                    errors.append(f"'{field}' must be numeric, got {type(value).__name__}")
            elif field_type == "string" and not isinstance(value, str):
                errors.append(f"'{field}' must be string, got {type(value).__name__}")
            elif field_type == "boolean" and not isinstance(value, bool):
                errors.append(f"'{field}' must be boolean, got {type(value).__name__}")
            elif field_type == "integer" and not isinstance(value, int):
                errors.append(f"'{field}' must be integer, got {type(value).__name__}")
            elif field_type == "object" and not isinstance(value, dict):
                errors.append(f"'{field}' must be object, got {type(value).__name__}")
            elif field_type == "array" and not isinstance(value, list):
                errors.append(f"'{field}' must be array, got {type(value).__name__}")

            # Range check
            if isinstance(value, (int, float)):
                if "minimum" in spec and value < spec["minimum"]:
                    errors.append(
                        f"'{field}' = {value} below minimum {spec['minimum']}"
                    )
                if "maximum" in spec and value > spec["maximum"]:
                    errors.append(
                        f"'{field}' = {value} above maximum {spec['maximum']}"
                    )

        return errors
