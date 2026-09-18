from __future__ import annotations

import re
from typing import Any, Dict, List

from ..models.constants import VALID_ACCURACY_COMPONENTS, VALID_TASK_TYPES


class SchemaValidationError(ValueError):
    pass


class SchemaValidator:
    REQUIRED_TOP_LEVEL = {"instance_id", "task_metadata", "context", "environment_config"}
    REQUIRED_METADATA = {"domain", "difficulty"}
    REQUIRED_CONTEXT = {"problem_statement", "dataset_preview"}
    REQUIRED_ENV = {"image", "max_steps", "budget"}

    VALID_DOMAINS = {
        "Biomedical", "Finance", "ECommerce", "Geospatial", "Generic",
        "SQL", "Scientific", "NLP_Text", "Climate", "HR_Analytics", "Manufacturing",
    }
    VALID_DIFFICULTIES = {"Easy", "Medium", "Hard"}
    INSTANCE_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*_\d+$")

    @classmethod
    def validate_task_input(cls, d: Dict[str, Any]) -> None:
        errors: List[str] = []

        # Top-level keys
        missing = cls.REQUIRED_TOP_LEVEL - set(d.keys())
        if missing:
            errors.append(f"Missing top-level keys: {missing}")

        if errors:
            raise SchemaValidationError("; ".join(errors))

        # instance_id format
        iid = d.get("instance_id", "")
        if not isinstance(iid, str) or not cls.INSTANCE_ID_PATTERN.match(iid):
            errors.append(
                f"instance_id '{iid}' must match pattern [A-Z][A-Z0-9_]*_<digits> "
                f"(e.g. DS_TASK_001)"
            )

        # task_metadata
        meta = d.get("task_metadata", {})
        if not isinstance(meta, dict):
            errors.append("task_metadata must be a dict")
        else:
            missing_meta = cls.REQUIRED_METADATA - set(meta.keys())
            if missing_meta:
                errors.append(f"task_metadata missing keys: {missing_meta}")
            if meta.get("domain") not in cls.VALID_DOMAINS:
                errors.append(f"domain must be one of {cls.VALID_DOMAINS}")
            if meta.get("difficulty") not in cls.VALID_DIFFICULTIES:
                errors.append(f"difficulty must be one of {cls.VALID_DIFFICULTIES}")
            primary_type = meta.get("primary_task_type")
            if primary_type is not None and primary_type not in VALID_TASK_TYPES:
                errors.append(
                    f"primary_task_type must be one of {sorted(VALID_TASK_TYPES)}"
                )
            secondary_types = meta.get("secondary_task_types", [])
            if not isinstance(secondary_types, list):
                errors.append("secondary_task_types must be a list if provided")
            else:
                invalid_secondary = [
                    t for t in secondary_types if t not in VALID_TASK_TYPES
                ]
                if invalid_secondary:
                    errors.append(
                        "secondary_task_types contains invalid values: "
                        f"{invalid_secondary}"
                    )
            challenge_dims = meta.get("challenge_dimensions", [])
            if not isinstance(challenge_dims, list):
                errors.append("challenge_dimensions must be a list if provided")
            elif not all(isinstance(v, str) for v in challenge_dims):
                errors.append("challenge_dimensions must contain only strings")

        # context
        ctx = d.get("context", {})
        if not isinstance(ctx, dict):
            errors.append("context must be a dict")
        else:
            missing_ctx = cls.REQUIRED_CONTEXT - set(ctx.keys())
            if missing_ctx:
                errors.append(f"context missing keys: {missing_ctx}")
            # Path traversal prevention
            preview = ctx.get("dataset_preview", "")
            if ".." in str(preview):
                errors.append("dataset_preview must not contain '..' (path traversal)")

        # environment_config
        env = d.get("environment_config", {})
        if not isinstance(env, dict):
            errors.append("environment_config must be a dict")
        else:
            missing_env = cls.REQUIRED_ENV - set(env.keys())
            if missing_env:
                errors.append(f"environment_config missing keys: {missing_env}")
            max_steps = env.get("max_steps", 0)
            if not isinstance(max_steps, int) or not (1 <= max_steps <= 100):
                errors.append(f"max_steps must be int in [1, 100], got {max_steps!r}")
            budget = env.get("budget", 0)
            if not isinstance(budget, (int, float)) or budget <= 0:
                errors.append(f"budget must be positive number, got {budget!r}")

        if errors:
            raise SchemaValidationError(f"Validation failed: {'; '.join(errors)}")

    @classmethod
    def validate_ground_truth(cls, d: Dict[str, Any]) -> None:
        """Validate expected_output.json structure."""
        errors: List[str] = []

        if "execution_result" not in d:
            errors.append("Missing 'execution_result'")
        elif not isinstance(d["execution_result"], str):
            errors.append("'execution_result' must be a string")

        if "key_values" not in d:
            errors.append("Missing 'key_values'")
        elif not isinstance(d["key_values"], dict):
            errors.append("'key_values' must be a dict")
        else:
            for k, v in d["key_values"].items():
                if not isinstance(v, (int, float, str, bool)):
                    errors.append(
                        f"key_values['{k}'] must be scalar, got {type(v).__name__}"
                    )

        if "required_keywords" in d:
            if not isinstance(d["required_keywords"], list):
                errors.append("'required_keywords' must be a list")

        if "components" in d:
            components = d["components"]
            if not isinstance(components, dict):
                errors.append("'components' must be a dict")
            else:
                for name, spec in components.items():
                    if name not in VALID_ACCURACY_COMPONENTS:
                        errors.append(
                            f"components['{name}'] must be one of "
                            f"{sorted(VALID_ACCURACY_COMPONENTS)}"
                        )
                        continue
                    if not isinstance(spec, dict):
                        errors.append(f"components['{name}'] must be a dict")
                        continue
                    weight = spec.get("score_weight", spec.get("weight"))
                    if weight is not None:
                        if not isinstance(weight, (int, float)) or weight < 0:
                            errors.append(
                                f"components['{name}'].score_weight must be "
                                "a non-negative number"
                            )
                    tolerance = spec.get("tolerance")
                    if tolerance is not None:
                        if not isinstance(tolerance, (int, float)) or tolerance <= 0:
                            errors.append(
                                f"components['{name}'].tolerance must be "
                                "a positive number"
                            )
                    key_values = spec.get("key_values")
                    if key_values is not None:
                        if not isinstance(key_values, dict):
                            errors.append(
                                f"components['{name}'].key_values must be a dict"
                            )
                        else:
                            for k, v in key_values.items():
                                if not isinstance(v, (int, float)):
                                    errors.append(
                                        f"components['{name}'].key_values['{k}'] "
                                        "must be numeric"
                                    )
                    for list_key in (
                        "target_columns",
                        "required_keywords",
                        "method_keywords",
                    ):
                        values = spec.get(list_key)
                        if values is not None:
                            if not isinstance(values, list) or not all(
                                isinstance(v, str) for v in values
                            ):
                                errors.append(
                                    f"components['{name}'].{list_key} must be "
                                    "a list of strings"
                                )

        if errors:
            raise SchemaValidationError(
                f"Ground truth validation failed: {'; '.join(errors)}"
            )

    @classmethod
    def validate_generated_task(
        cls, task_dict: Dict[str, Any], ground_truth: Dict[str, Any]
    ) -> None:
        """
        Full validation for a generated task: task.json + ground_truth
        + cross-checks specific to generated content.
        """
        cls.validate_task_input(task_dict)
        cls.validate_ground_truth(ground_truth)

        # Generated tasks must include a canary_value
        canary = task_dict.get("task_metadata", {}).get("canary_value")
        if canary is None:
            raise SchemaValidationError(
                "Generated tasks must include a canary_value in task_metadata"
            )

        # Ground truth must have at least one key_value
        kv = ground_truth.get("key_values", {})
        if not kv:
            raise SchemaValidationError(
                "Generated tasks must have at least one entry in key_values"
            )
