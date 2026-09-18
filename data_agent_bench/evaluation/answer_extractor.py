from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..models.task import TaskInput
from ..models.trace import AgentTrace, TraceStep


NUMBER_RE = r"-?\$?\d[\d,]*(?:\.\d+)?(?:[eE][+-]?\d+)?"


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _flex_label_pattern(label: str) -> str:
    parts = [re.escape(p) for p in re.split(r"[\s_\-]+", str(label).strip()) if p]
    if not parts:
        return re.escape(str(label))
    return r"[\s_\-]*".join(parts)


def _as_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "")
        if re.fullmatch(NUMBER_RE, cleaned):
            return float(cleaned)
    return None


def _brace_json_after_marker(text: str) -> Optional[Dict[str, Any]]:
    marker_match = re.search(r"FINAL\s+ANSWER\s*:?", text, re.IGNORECASE)
    start_at = marker_match.end() if marker_match else 0
    brace_start = text.find("{", start_at)
    if brace_start < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    for idx in range(brace_start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[brace_start: idx + 1])
                except Exception:
                    return None
    return None


class AnswerExtractor:
    """
    Deterministically extracts benchmark-facing key_values from observed output.

    It never rewrites the model's raw answer. It only creates an auditable
    benchmark_extracted_answer for scoring and validity debugging.
    """

    def extract(
        self,
        task: TaskInput,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        ground_truth: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        expected_keys, aliases = self._expected_keys_and_aliases(ground_truth)
        raw_agent_output = str(final_output.get("raw_agent_output", ""))
        execution_result = str(final_output.get("execution_result", ""))

        candidates: Dict[str, List[Dict[str, Any]]] = {key: [] for key in expected_keys}
        if expected_keys:
            self._extract_final_json(raw_agent_output, expected_keys, aliases, candidates)
            self._extract_labeled_text(
                execution_result,
                expected_keys,
                aliases,
                candidates,
                source="labeled_stdout",
                source_step=None,
                confidence=0.85,
            )
            for step in trace.steps:
                step_text = "\n".join([
                    str(step.observation or ""),
                    str(step.tool_result or ""),
                    str(step.thought or ""),
                ])
                self._extract_labeled_text(
                    step_text,
                    expected_keys,
                    aliases,
                    candidates,
                    source="trace_numeric_match",
                    source_step=step.step,
                    confidence=0.75,
                )

        key_values: Dict[str, float] = {}
        source_steps: List[int] = []
        sources: List[str] = []
        confidences: List[float] = []
        selected: Dict[str, Dict[str, Any]] = {}

        for key, key_candidates in candidates.items():
            if not key_candidates:
                continue
            best = sorted(
                key_candidates,
                key=lambda c: (float(c.get("confidence", 0.0)), c.get("source_step") is not None),
                reverse=True,
            )[0]
            key_values[key] = float(best["value"])
            selected[key] = best
            if best.get("source_step") is not None:
                source_steps.append(int(best["source_step"]))
            sources.append(str(best.get("source", "")))
            confidences.append(float(best.get("confidence", 0.0)))

        source = "none"
        for preferred in ("final_json", "labeled_stdout", "trace_numeric_match"):
            if preferred in sources:
                source = preferred
                break

        return {
            "key_values": key_values,
            "source": source,
            "source_steps": sorted(set(source_steps)),
            "extraction_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
            "selected": selected,
            "candidates": candidates,
        }

    def _expected_keys_and_aliases(
        self,
        ground_truth: Optional[Dict[str, Any]],
    ) -> Tuple[List[str], Dict[str, List[str]]]:
        if not ground_truth:
            return [], {}
        keys = [
            key for key, value in (ground_truth.get("key_values") or {}).items()
            if isinstance(value, (int, float))
        ]
        for alt in ground_truth.get("alternative_key_values", []) or []:
            if not isinstance(alt, dict):
                continue
            for key, value in alt.items():
                if key != "method" and isinstance(value, (int, float)) and key not in keys:
                    keys.append(key)

        raw_aliases = ground_truth.get("key_aliases") or {}
        aliases: Dict[str, List[str]] = {}
        for key in keys:
            values = [key]
            if isinstance(raw_aliases, dict):
                extra = raw_aliases.get(key, [])
                if isinstance(extra, str):
                    values.append(extra)
                elif isinstance(extra, list):
                    values.extend(str(v) for v in extra)
            aliases[key] = values
        return keys, aliases

    def _extract_final_json(
        self,
        text: str,
        expected_keys: Sequence[str],
        aliases: Dict[str, List[str]],
        candidates: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        obj = _brace_json_after_marker(text)
        if not isinstance(obj, dict):
            return
        payload = obj.get("key_values", obj)
        if not isinstance(payload, dict):
            return

        normalized_payload = {normalize_key(k): v for k, v in payload.items()}
        for key in expected_keys:
            for alias in aliases.get(key, [key]):
                value = normalized_payload.get(normalize_key(alias))
                numeric = _as_float(value)
                if numeric is not None:
                    candidates[key].append({
                        "value": numeric,
                        "source": "final_json",
                        "source_step": None,
                        "confidence": 1.0,
                        "matched_label": alias,
                    })
                    break

    def _extract_labeled_text(
        self,
        text: str,
        expected_keys: Sequence[str],
        aliases: Dict[str, List[str]],
        candidates: Dict[str, List[Dict[str, Any]]],
        *,
        source: str,
        source_step: Optional[int],
        confidence: float,
    ) -> None:
        if not text:
            return
        for key in expected_keys:
            for alias in aliases.get(key, [key]):
                label_pattern = _flex_label_pattern(alias)
                pattern = rf"(?:{label_pattern})\s*(?:=|:|is|为|是)\s*({NUMBER_RE})"
                for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                    candidates[key].append({
                        "value": float(match.group(1)),
                        "source": source,
                        "source_step": source_step,
                        "confidence": confidence,
                        "matched_label": alias,
                        "span": [match.start(), match.end()],
                    })
