from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Dict, Optional, Type, get_type_hints

logger = logging.getLogger(__name__)

class Tool:
    """
    Standardized Tool class for DataAgentBench.
    Inspired by smolagents but designed for academic transparency and 0-dependency.
    """
    def __init__(
        self,
        name: str,
        func: Callable,
        description: Optional[str] = None,
        inputs: Optional[Dict[str, Dict[str, Any]]] = None,
        output_type: str = "string",
    ):
        self.name = name
        self.func = func
        self.description = description or func.__doc__ or "No description provided."
        self.inputs = inputs or self._infer_inputs(func)
        self.output_type = output_type

    def _infer_inputs(self, func: Callable) -> Dict[str, Dict[str, Any]]:
        """Infer input schema from function signature and type hints."""
        signature = inspect.signature(func)
        type_hints = get_type_hints(func)
        inputs = {}
        
        for name, param in signature.parameters.items():
            if name == "self" or name == "kwargs":
                continue
            
            param_type = type_hints.get(name, Any)
            inputs[name] = {
                "type": str(param_type.__name__) if hasattr(param_type, "__name__") else "any",
                "description": f"Input parameter '{name}'",
                "required": param.default is inspect.Parameter.empty,
            }
        return inputs

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    def to_schema(self) -> Dict[str, Any]:
        """Return a JSON-serializable schema for LLM prompting."""
        return {
            "name": self.name,
            "description": self.description,
            "inputs": self.inputs,
            "output_type": self.output_type,
        }

def tool(name: Optional[str] = None, description: Optional[str] = None):
    """Decorator to easily create a Tool from a function."""
    def decorator(func: Callable) -> Tool:
        tool_name = name or func.__name__
        return Tool(name=tool_name, func=func, description=description)
    return decorator

class ToolRegistry:
    """Registry for managing available tools in an environment."""
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [t.to_schema() for t in self._tools.values()]
