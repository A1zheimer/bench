from __future__ import annotations

import json
import re
import statistics
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .answer_extractor import NUMBER_RE, _as_float, _brace_json_after_marker, normalize_key


DEFAULT_TOLERANCE = 0.05
DEFAULT_SOFT_CAP = 0.25


@dataclass
class Candidate:
    key: str
    value: float
    source: str
    source_step: Optional[int] = None
    matched_label: Optional[str] = None
    confidence: float = 0.0


@dataclass
class FieldScoreV3:
    key: str
    score: float
    expected_value: Optional[float] = None
    extracted_value: Optional[float] = None
    relative_error: Optional[float] = None
    source: str = "none"
    source_step: Optional[int] = None
    matched_label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "expected_value": self.expected_value,
            "extracted_value": self.extracted_value,
            "relative_error": self.relative_error,
            "source": self.source,
            "source_step": self.source_step,
            "matched_label": self.matched_label,
        }


@dataclass
class AccuracyScoreV3:
    accuracy: float
    field_scores: Dict[str, FieldScoreV3]
    sources: Dict[str, int] = field(default_factory=dict)

    def missed_keys(self) -> List[str]:
        return [key for key, detail in self.field_scores.items() if detail.score <= 0.0]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accuracy": round(self.accuracy, 4),
            "field_scores": {key: value.to_dict() for key, value in self.field_scores.items()},
            "sources": self.sources,
            "missed_keys": self.missed_keys(),
        }


@dataclass
class RescoreV3Result:
    task_id: str
    final_answer: AccuracyScoreV3
    trace_grounded: AccuracyScoreV3
    grounded_final: AccuracyScoreV3
    failure: str
    trace_path: str
    report_path: str
    process_quality: float
    execution_safety: float
    analytical_safety: float
    trace_integrity: float
    timeout_or_api_failure: bool

    def format_miss_keys(self) -> List[str]:
        keys: List[str] = []
        for key, trace_detail in self.trace_grounded.field_scores.items():
            final_detail = self.final_answer.field_scores.get(key)
            final_score = final_detail.score if final_detail else 0.0
            if trace_detail.score > final_score:
                keys.append(key)
        return keys

    def format_miss(self) -> bool:
        return bool(self.format_miss_keys())

    def ungrounded_final_keys(self) -> List[str]:
        keys: List[str] = []
        for key, final_detail in self.final_answer.field_scores.items():
            grounded_detail = self.grounded_final.field_scores.get(key)
            grounded_score = grounded_detail.score if grounded_detail else 0.0
            if final_detail.score > grounded_score:
                keys.append(key)
        return keys

    def ungrounded_final(self) -> bool:
        return bool(self.ungrounded_final_keys())


def relative_error(observed: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if abs(observed) < 1e-6 else float("inf")
    return abs(observed - expected) / abs(expected)


def score_numeric_value(
    observed: float,
    expected: float,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    soft_cap: float = DEFAULT_SOFT_CAP,
) -> Tuple[float, float]:
    rel_err = relative_error(observed, expected)
    if rel_err == float("inf"):
        return 0.0, rel_err
    if rel_err <= tolerance:
        return 1.0, rel_err
    if rel_err <= soft_cap and soft_cap > tolerance:
        score = 1.0 - (rel_err - tolerance) / (soft_cap - tolerance)
        return max(0.0, score), rel_err
    return 0.0, rel_err


def expected_key_sets(ground_truth: Dict[str, Any]) -> List[Dict[str, float]]:
    primary = {
        key: float(value)
        for key, value in (ground_truth.get("key_values") or {}).items()
        if isinstance(value, (int, float))
    }
    sets: List[Dict[str, float]] = [primary]
    for alt in ground_truth.get("alternative_key_values", []) or []:
        if not isinstance(alt, dict):
            continue
        alt_values = {
            key: float(value)
            for key, value in alt.items()
            if key != "method" and isinstance(value, (int, float))
        }
        if alt_values:
            sets.append(alt_values)
    return [item for item in sets if item]


def expected_keys_and_aliases(ground_truth: Dict[str, Any]) -> Tuple[List[str], Dict[str, List[str]]]:
    keys: List[str] = []
    for kv_set in expected_key_sets(ground_truth):
        for key in kv_set:
            if key not in keys:
                keys.append(key)

    raw_aliases = ground_truth.get("key_aliases") or {}
    aliases: Dict[str, List[str]] = {}
    for key in keys:
        values = [key, key.replace("_", " "), key.replace("_", "-")]
        values.extend(_metric_suffix_aliases(key))
        if isinstance(raw_aliases, dict):
            extra = raw_aliases.get(key, [])
            if isinstance(extra, str):
                values.append(extra)
            elif isinstance(extra, list):
                values.extend(str(v) for v in extra)
        aliases[key] = _dedupe(values)
    return keys, aliases


def extract_final_answer_candidates(
    raw_agent_output: str,
    ground_truth: Dict[str, Any],
) -> Dict[str, List[Candidate]]:
    keys, aliases = expected_keys_and_aliases(ground_truth)
    candidates: Dict[str, List[Candidate]] = {key: [] for key in keys}
    final_region = _final_answer_region(raw_agent_output)
    _extract_final_json(raw_agent_output, keys, aliases, candidates)
    _extract_labeled_text(
        final_region,
        keys,
        aliases,
        candidates,
        source="final_labeled_text",
        source_step=None,
        confidence=0.9,
    )
    return candidates


def extract_trace_grounded_candidates(
    report: Dict[str, Any],
    trace_steps: Sequence[Dict[str, Any]],
    ground_truth: Dict[str, Any],
) -> Dict[str, List[Candidate]]:
    keys, aliases = expected_keys_and_aliases(ground_truth)
    candidates: Dict[str, List[Candidate]] = {key: [] for key in keys}

    _extract_labeled_text(
        str(report.get("execution_result", "")),
        keys,
        aliases,
        candidates,
        source="labeled_stdout",
        source_step=None,
        confidence=0.85,
    )
    _extract_single_key_numeric_matches(
        str(report.get("execution_result", "")),
        ground_truth,
        candidates,
        source="execution_numeric_match",
        source_step=None,
    )

    for step in trace_steps:
        step_no = _safe_int(step.get("step"))
        observed_text = "\n".join([
            str(step.get("observation") or ""),
            str(step.get("tool_result") or ""),
        ])
        _extract_labeled_text(
            observed_text,
            keys,
            aliases,
            candidates,
            source="trace_labeled_output",
            source_step=step_no,
            confidence=0.8,
        )
        _extract_single_key_numeric_matches(
            observed_text,
            ground_truth,
            candidates,
            source="trace_numeric_match",
            source_step=step_no,
        )
    return candidates


def score_candidates(
    ground_truth: Dict[str, Any],
    candidates: Dict[str, List[Candidate]],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    soft_cap: float = DEFAULT_SOFT_CAP,
) -> AccuracyScoreV3:
    key_sets = expected_key_sets(ground_truth)
    all_keys: List[str] = []
    for kv_set in key_sets:
        for key in kv_set:
            if key not in all_keys:
                all_keys.append(key)

    field_scores: Dict[str, FieldScoreV3] = {}
    source_counts: Dict[str, int] = {}
    for key in all_keys:
        best = FieldScoreV3(key=key, score=0.0)
        for kv_set in key_sets:
            if key not in kv_set:
                continue
            expected = kv_set[key]
            for candidate in candidates.get(key, []):
                score, rel_err = score_numeric_value(
                    candidate.value,
                    expected,
                    tolerance=tolerance,
                    soft_cap=soft_cap,
                )
                if score > best.score:
                    best = FieldScoreV3(
                        key=key,
                        score=score,
                        expected_value=expected,
                        extracted_value=candidate.value,
                        relative_error=None if rel_err == float("inf") else round(rel_err, 8),
                        source=candidate.source,
                        source_step=candidate.source_step,
                        matched_label=candidate.matched_label,
                    )
        field_scores[key] = best
        source_counts[best.source] = source_counts.get(best.source, 0) + 1

    accuracy = statistics.mean(detail.score for detail in field_scores.values()) if field_scores else 0.0
    return AccuracyScoreV3(accuracy=accuracy, field_scores=field_scores, sources=source_counts)


def supported_final_candidates(
    final_candidates: Dict[str, List[Candidate]],
    trace_candidates: Dict[str, List[Candidate]],
    *,
    support_tolerance: float = DEFAULT_TOLERANCE,
) -> Dict[str, List[Candidate]]:
    supported: Dict[str, List[Candidate]] = {key: [] for key in final_candidates}
    for key, candidates in final_candidates.items():
        observed = trace_candidates.get(key, [])
        for candidate in candidates:
            support = _find_supporting_candidate(candidate, observed, support_tolerance=support_tolerance)
            if support is None:
                continue
            supported.setdefault(key, []).append(Candidate(
                key=key,
                value=candidate.value,
                source=f"{candidate.source}+trace_support",
                source_step=support.source_step,
                matched_label=candidate.matched_label,
                confidence=min(candidate.confidence, support.confidence),
            ))
    return supported


def rescore_report_v3(
    report: Dict[str, Any],
    trace_steps: Sequence[Dict[str, Any]],
    ground_truth: Dict[str, Any],
    *,
    report_path: str = "",
    trace_path: str = "",
) -> RescoreV3Result:
    final_candidates = extract_final_answer_candidates(str(report.get("raw_agent_output", "")), ground_truth)
    trace_candidates = extract_trace_grounded_candidates(report, trace_steps, ground_truth)
    final_score = score_candidates(
        ground_truth,
        final_candidates,
    )
    trace_score = score_candidates(
        ground_truth,
        trace_candidates,
    )
    grounded_final_score = score_candidates(
        ground_truth,
        supported_final_candidates(final_candidates, trace_candidates),
    )
    scores = report.get("scores") or {}
    failure = _failure(report)
    return RescoreV3Result(
        task_id=str(report.get("instance_id", "")),
        final_answer=final_score,
        trace_grounded=trace_score,
        grounded_final=grounded_final_score,
        failure=failure,
        trace_path=trace_path,
        report_path=report_path,
        process_quality=float((report.get("metrics") or {}).get("process_quality", 0.0) or 0.0),
        execution_safety=_score_from(scores, "execution_safety"),
        analytical_safety=_score_from(scores, "analytical_safety"),
        trace_integrity=float((scores.get("trace_integrity") or {}).get("integrity_score", 0.0) or 0.0),
        timeout_or_api_failure=failure in {"timeout", "api_read_timeout", "api_error"},
    )


def load_trace_jsonl(path: Path) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    if not path.exists():
        return steps
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            steps.append(payload)
    return steps


def find_trace_path(report_path: Path) -> Optional[Path]:
    task_dir = report_path.parent
    candidates = sorted(task_dir.glob("*/trace.jsonl"))
    if candidates:
        return candidates[-1]
    direct = task_dir / "trace.jsonl"
    return direct if direct.exists() else None


def _extract_final_json(
    text: str,
    expected_keys: Sequence[str],
    aliases: Dict[str, List[str]],
    candidates: Dict[str, List[Candidate]],
) -> None:
    obj = _brace_json_after_marker(text)
    if not isinstance(obj, dict):
        return
    payload = obj.get("key_values", obj)
    if not isinstance(payload, dict):
        return
    normalized_payload = {normalize_key(k): v for k, v in payload.items()}
    flattened_payload = _flatten_numeric_payload(payload)
    for key in expected_keys:
        found = False
        for alias in aliases.get(key, [key]):
            value = normalized_payload.get(normalize_key(alias))
            numeric = _as_float(value)
            if numeric is not None:
                candidates[key].append(Candidate(
                    key=key,
                    value=numeric,
                    source="final_json",
                    matched_label=alias,
                    confidence=1.0,
                ))
                found = True
                break
        if found:
            continue
        for payload_label, value in flattened_payload:
            if any(_semantic_label_match(alias, payload_label) for alias in aliases.get(key, [key])):
                candidates[key].append(Candidate(
                    key=key,
                    value=value,
                    source="final_json",
                    matched_label=payload_label,
                    confidence=0.95,
                ))
                found = True
                break
        if found:
            continue
        for payload_key, value in payload.items():
            numeric = _as_float(value)
            if numeric is None:
                continue
            if any(_semantic_label_match(alias, str(payload_key)) for alias in aliases.get(key, [key])):
                candidates[key].append(Candidate(
                    key=key,
                    value=numeric,
                    source="final_json",
                    matched_label=str(payload_key),
                    confidence=0.95,
                ))
                break


def _find_supporting_candidate(
    candidate: Candidate,
    observed_candidates: Sequence[Candidate],
    *,
    support_tolerance: float,
) -> Optional[Candidate]:
    for observed in observed_candidates:
        if relative_error(candidate.value, observed.value) <= support_tolerance:
            return observed
    return None


def _extract_labeled_text(
    text: str,
    expected_keys: Sequence[str],
    aliases: Dict[str, List[str]],
    candidates: Dict[str, List[Candidate]],
    *,
    source: str,
    source_step: Optional[int],
    confidence: float,
) -> None:
    if not text:
        return
    for key in expected_keys:
        for alias in aliases.get(key, [key]):
            label = _flex_label_pattern(alias)
            patterns = [
                rf"(?:{label})\s*(?:=|:|is|为|是|≈|~|about|approximately)\s*({NUMBER_RE})",
                rf"({NUMBER_RE})\s*(?:=|:|is|为|是|≈|~)?\s*(?:{label})",
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                    value = _as_float(match.group(1))
                    if value is None:
                        continue
                    candidates[key].append(Candidate(
                        key=key,
                        value=value,
                        source=source,
                        source_step=source_step,
                        matched_label=alias,
                        confidence=confidence,
                    ))
    _extract_semantic_labeled_lines(
        text,
        expected_keys,
        aliases,
        candidates,
        source=source,
        source_step=source_step,
        confidence=max(0.0, confidence - 0.1),
    )


def _extract_semantic_labeled_lines(
    text: str,
    expected_keys: Sequence[str],
    aliases: Dict[str, List[str]],
    candidates: Dict[str, List[Candidate]],
    *,
    source: str,
    source_step: Optional[int],
    confidence: float,
) -> None:
    for line in text.splitlines():
        matches = list(re.finditer(NUMBER_RE, line))
        if not matches:
            continue
        label_text = re.sub(NUMBER_RE, " ", line)
        for key in expected_keys:
            matched_alias = next(
                (alias for alias in aliases.get(key, [key]) if _semantic_label_match(alias, label_text)),
                None,
            )
            if not matched_alias:
                continue
            # Pick the final number on the line; labeled summaries usually end
            # with the reported metric, while data previews are filtered by the
            # semantic label gate above.
            value = _as_float(matches[-1].group(0))
            if value is None:
                continue
            candidates[key].append(Candidate(
                key=key,
                value=value,
                source=source,
                source_step=source_step,
                matched_label=matched_alias,
                confidence=confidence,
            ))


def _final_answer_region(text: str) -> str:
    marker_match = re.search(r"FINAL\s+ANSWER\s*:?", text, re.IGNORECASE)
    if not marker_match:
        return text
    return text[marker_match.end():]


def _semantic_label_match(expected_label: str, observed_label: str) -> bool:
    expected_tokens = set(_label_tokens(expected_label))
    observed_tokens = set(_label_tokens(observed_label))
    if len(expected_tokens) == 1:
        return bool(expected_tokens & observed_tokens)
    if len(expected_tokens) < 2:
        return False
    if not observed_tokens:
        return False
    overlap = len(expected_tokens & observed_tokens)
    required = max(2, math.ceil(len(expected_tokens) * 0.6))
    return overlap >= required


def _label_tokens(value: str) -> List[str]:
    return [
        token
        for token in re.split(r"[^a-z0-9]+", str(value).lower())
        if len(token) > 1
    ]


def _flex_label_pattern(label: str) -> str:
    parts = [re.escape(p) for p in re.split(r"[\s_\-]+", str(label).strip()) if p]
    if not parts:
        return re.escape(str(label))
    return r"[\s_\-]*".join(parts)


def _dedupe(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        key = str(value).strip()
        if not key or normalize_key(key) in seen:
            continue
        seen.add(normalize_key(key))
        result.append(key)
    return result


def _metric_suffix_aliases(key: str) -> List[str]:
    tokens = key.split("_")
    if len(tokens) < 3:
        return []
    prefixes = {
        ("total", "revenue"),
        ("total", "cost"),
        ("outlier", "count"),
        ("corr",),
        ("correlation",),
    }
    aliases: List[str] = []
    for prefix in prefixes:
        if tuple(tokens[:len(prefix)]) == prefix and len(tokens) > len(prefix):
            suffix = tokens[len(prefix):]
            aliases.extend([
                " ".join(suffix),
                "-".join(suffix),
                suffix[-1],
            ])
            break
    return aliases


def _flatten_numeric_payload(payload: Any, path: Optional[List[str]] = None) -> List[Tuple[str, float]]:
    path = path or []
    results: List[Tuple[str, float]] = []
    numeric = _as_float(payload)
    if numeric is not None and path:
        results.append((" ".join(path), numeric))
        return results
    if isinstance(payload, dict):
        for key, value in payload.items():
            results.extend(_flatten_numeric_payload(value, path + [str(key)]))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            results.extend(_flatten_numeric_payload(value, path + [str(index)]))
    return results


def _extract_single_key_numeric_matches(
    text: str,
    ground_truth: Dict[str, Any],
    candidates: Dict[str, List[Candidate]],
    *,
    source: str,
    source_step: Optional[int],
) -> None:
    key_sets = expected_key_sets(ground_truth)
    if len(key_sets) != 1 or len(key_sets[0]) != 1 or not text:
        return
    key, expected = next(iter(key_sets[0].items()))
    for value in _strict_scalar_numbers(text):
        if value is None:
            continue
        score, _ = score_numeric_value(value, expected)
        if score <= 0:
            continue
        candidates.setdefault(key, []).append(Candidate(
            key=key,
            value=value,
            source=source,
            source_step=source_step,
            matched_label="numeric_match",
            confidence=0.5,
        ))


def _strict_scalar_numbers(text: str) -> List[float]:
    values: List[float] = []
    for match in re.finditer(rf"\b(?:np\.)?(?:float64|float32|float|int64|int32|int)\(({NUMBER_RE})\)", text):
        value = _as_float(match.group(1))
        if value is not None:
            values.append(value)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(NUMBER_RE, stripped):
            value = _as_float(stripped)
            if value is not None:
                values.append(value)
    return values


def _score_from(scores: Dict[str, Any], key: str) -> float:
    direct = scores.get(key) or {}
    nested = (scores.get("risk") or {}).get(key) or {}
    return float((direct or nested).get("score", 0.0) or 0.0)


def _failure(report: Dict[str, Any]) -> str:
    failure = report.get("failure_attribution") or {}
    return str(failure.get("primary_failure") or failure.get("primary_cause") or "none")


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None
