"""
RedTeamAgent: Three-level semantic obfuscation engine for contrastive experiments.

Levels:
  L1: Column Rename — semantic names → opaque labels (via ColumnObfuscator)
  L2: L1 + Statistical Traps — inject realistic data quality issues (via AdversarialDirtier)
  L3: L2 + Problem Statement De-semanticization — rewrite problem using LLM
"""
from __future__ import annotations

import logging
import copy
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .column_obfuscator import ColumnObfuscator

logger = logging.getLogger(__name__)

RED_TEAM_L3_PROMPT = """\
You are an expert Data Science Red Team evaluator.
Your goal is to perform "Semantic Obfuscation" on a given data science problem statement.

The original problem relies on domain-specific semantics (e.g., "Analyze how customer income affects loan approval").
The data has already had its columns renamed to opaque labels (e.g., "income" -> "var_a3f2", "approved" -> "target_d4e7").

You need to rewrite the problem statement so that it ONLY uses these opaque column names.
Remove ALL domain context, business logic, or hints about what the data means.
The agent must solve the problem using ONLY pure statistical reasoning and the provided column mapping.
Keep the exact same mathematical/statistical requirements (tests, metrics, thresholds).

Output ONLY the rewritten problem statement, nothing else.
"""


class RedTeamAgent:
    """
    Injects adversarial perturbations into a generated task across 3 levels.

    L1: Column Rename (Semantic → Opaque via SHA256 hash)
    L2: L1 + Statistical Traps (via AdversarialDirtier: MNAR, schema drift, encoding traps)
    L3: L2 + Problem Statement De-semanticization (via LLM rewrite)
    """

    def __init__(
        self,
        provider: str = "openai",
        model_id: str = "gpt-4o",
        temperature: float = 0.3,
        api_key: Optional[str] = None,
        obfuscation_seed: int = 42,
    ):
        self.provider = provider
        self.model_id = model_id
        self.temperature = temperature
        self._api_key = api_key
        self.obfuscator = ColumnObfuscator(seed=obfuscation_seed)

    def perturb_level(
        self,
        task_json: Dict[str, Any],
        data_df: pd.DataFrame,
        level: int,
        difficulty: str = "Medium",
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """
        Apply perturbation at specified level.

        Args:
            task_json: The task specification dict.
            data_df: The task's dataset as a DataFrame.
            level: 0=Clean, 1=Rename, 2=Rename+Traps, 3=Rename+Traps+Desemanticize.
            difficulty: Controls injection intensity for L2 ("Easy"/"Medium"/"Hard").

        Returns:
            (modified_task_json, modified_dataframe)
        """
        task_json = copy.deepcopy(task_json)
        data_df = data_df.copy()

        if level < 1:
            return task_json, data_df

        # L1: Deterministic column renaming
        data_df, col_map = self._rename_columns(data_df)
        task_json.setdefault("context", {})["column_mapping"] = col_map
        task_json["context"]["obfuscation_level"] = f"L{level}"
        logger.info("L1: Renamed %d columns", len(col_map))

        if level >= 2:
            # L2: Adversarial data quality issues
            data_df, injection_log = self._inject_statistical_traps(data_df, difficulty)
            task_json["context"]["injected_traps"] = injection_log.to_dict()
            logger.info("L2: Injected traps: %s", injection_log.to_dict())

        if level >= 3:
            # L3: De-semanticize problem statement via LLM
            task_json = self._desemanticize_problem(task_json, col_map)

        return task_json, data_df

    def _rename_columns(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """Deterministic column renaming using ColumnObfuscator."""
        col_map = self.obfuscator.obfuscate(list(df.columns))
        df_renamed = df.rename(columns=col_map)
        return df_renamed, col_map

    def _inject_statistical_traps(
        self, df: pd.DataFrame, difficulty: str = "Medium"
    ):
        """
        Use AdversarialDirtier for systematic, reproducible trap injection.
        Returns (dirty_df, InjectionLog).
        """
        try:
            from seed_datasets.adversarial_dirtier import AdversarialDirtier
        except ImportError:
            import importlib.util, pathlib
            _root = pathlib.Path(__file__).resolve().parents[2] / "seed_datasets" / "adversarial_dirtier.py"
            _spec = importlib.util.spec_from_file_location("adversarial_dirtier", _root)
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            AdversarialDirtier = _mod.AdversarialDirtier

        dirtier = AdversarialDirtier(seed=self.obfuscator.seed)
        return dirtier.apply_all(df, difficulty=difficulty)

    def _desemanticize_problem(
        self, task_json: Dict[str, Any], col_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Uses LLM to rewrite the problem statement, removing domain semantics
        and substituting opaque column names.
        """
        original_problem = task_json.get("context", {}).get("problem_statement", "")
        if not original_problem:
            logger.warning("No problem_statement found in task_json; skipping L3.")
            return task_json

        mapping_str = "\n".join(
            f"- '{orig}' → '{obf}'" for orig, obf in col_map.items()
        )
        user_msg = (
            f"## Original Problem Statement\n{original_problem}\n\n"
            f"## Column Mapping\n{mapping_str}\n\n"
            f"Rewrite the problem statement to use ONLY the renamed columns "
            f"and remove all domain context."
        )

        rewritten = self._call_llm(user_msg)
        if rewritten:
            task_json["context"]["original_problem_statement"] = original_problem
            task_json["context"]["problem_statement"] = rewritten
            logger.info("L3: Successfully de-semanticized problem statement.")
        else:
            logger.warning("L3: LLM call failed; problem statement unchanged.")

        return task_json

    def _call_llm(self, user_message: str) -> Optional[str]:
        """Call the configured LLM provider for L3 rewriting."""
        messages = [
            {"role": "system", "content": RED_TEAM_L3_PROMPT},
            {"role": "user", "content": user_message},
        ]
        try:
            if self.provider == "openai":
                import openai

                client = openai.OpenAI(api_key=self._api_key)
                resp = client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=1500,
                )
                return resp.choices[0].message.content.strip()

            elif self.provider == "anthropic":
                import anthropic

                client = anthropic.Anthropic(api_key=self._api_key)
                resp = client.messages.create(
                    model=self.model_id,
                    system=RED_TEAM_L3_PROMPT,
                    messages=[{"role": "user", "content": user_message}],
                    temperature=self.temperature,
                    max_tokens=1500,
                )
                return resp.content[0].text.strip()

            else:
                logger.warning("L3 not implemented for provider '%s'", self.provider)
                return None

        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            return None
