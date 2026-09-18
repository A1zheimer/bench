from __future__ import annotations

import abc
import dataclasses
from typing import Any, Dict, List, Optional

from ..models.task import Domain, TaskInput
from ..models.trace import ActionType, TraceStep


@dataclasses.dataclass
class AgentAction:
    action_type: ActionType
    action: str
    thought: str = ""
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tokens_in: int = 50
    tokens_out: int = 100


class AgentInterface(abc.ABC):
    @abc.abstractmethod
    def reset(self, task: TaskInput) -> None:
        """Prepare agent for a new task."""

    @abc.abstractmethod
    def act(
        self,
        step_number: int,
        observation: str,
        trace_so_far: List[TraceStep],
    ) -> AgentAction:
        """Given current observation and history, return next action."""

    @abc.abstractmethod
    def is_done(self) -> bool:
        """Has the agent signaled task completion?"""


class SimulatedAgent(AgentInterface):
    """
    Scripted agent for testing the framework end-to-end.
    Plays out realistic trajectories per domain:
      inspect → understand → impute/clean → analyze → interpret → answer
    """

    _SCRIPTS: Dict[str, List[AgentAction]] = {
        "Biomedical": [
            AgentAction(
                action_type=ActionType.THINK,
                action="Analyze problem statement",
                thought="I need to handle missing values in response_time column "
                        "and then run ANOVA to compare age groups. "
                        "First let me inspect the dataset structure.",
            ),
            AgentAction(
                action_type=ActionType.FILE_READ,
                action="Read dataset preview",
                tool_name="file_read",
                tool_args={"path": "data/trials_preview.csv"},
            ),
            AgentAction(
                action_type=ActionType.THINK,
                action="Understand data structure and plan analysis",
                thought="Dataset has patient_id, age_group, response_time, drug_dose. "
                        "~20% missing in response_time. I'll use median imputation "
                        "then ANOVA across age groups.",
            ),
            AgentAction(
                action_type=ActionType.CODE_EXEC,
                action="Impute missing values",
                tool_name="python_repl",
                tool_args={"code": (
                    "import pandas as pd\nimport numpy as np\n"
                    "# Simulate data with missing values\n"
                    "np.random.seed(42)\n"
                    "n = 100\n"
                    "age_groups = np.random.choice(['Young', 'Middle', 'Old'], n)\n"
                    "response_time = np.random.normal([2.0, 3.5, 4.5][0], 0.5, n)\n"
                    "# Add group-specific means\n"
                    "for i, ag in enumerate(age_groups):\n"
                    "    base = {'Young': 2.0, 'Middle': 3.5, 'Old': 4.5}[ag]\n"
                    "    response_time[i] = np.random.normal(base, 0.5)\n"
                    "# Add 20% missing\n"
                    "mask = np.random.random(n) < 0.2\n"
                    "response_time_with_nan = response_time.copy().astype(float)\n"
                    "response_time_with_nan[mask] = np.nan\n"
                    "df = pd.DataFrame({'age_group': age_groups, 'response_time': response_time_with_nan})\n"
                    "# Impute with median\n"
                    "df['response_time'].fillna(df['response_time'].median(), inplace=True)\n"
                    "print(f'Missing after imputation: {df[\"response_time\"].isna().sum()}')\n"
                    "print(f'Group means:\\n{df.groupby(\"age_group\")[\"response_time\"].mean().round(3)}')\n"
                )},
            ),
            AgentAction(
                action_type=ActionType.CODE_EXEC,
                action="Run ANOVA test",
                tool_name="python_repl",
                tool_args={"code": (
                    "from scipy import stats\nimport numpy as np\n"
                    "np.random.seed(42)\n"
                    "young = np.random.normal(2.0, 0.5, 30)\n"
                    "middle = np.random.normal(3.5, 0.5, 35)\n"
                    "old = np.random.normal(4.5, 0.5, 35)\n"
                    "f_stat, p_value = stats.f_oneway(young, middle, old)\n"
                    "# Cohen's f effect size\n"
                    "grand_mean = np.concatenate([young, middle, old]).mean()\n"
                    "n_groups = 3\n"
                    "ss_between = sum(len(g) * (g.mean() - grand_mean)**2 for g in [young, middle, old])\n"
                    "ss_total = sum(((x - grand_mean)**2) for g in [young, middle, old] for x in g)\n"
                    "eta_sq = ss_between / ss_total\n"
                    "cohens_f = np.sqrt(eta_sq / (1 - eta_sq))\n"
                    "print(f'F-statistic: {f_stat:.3f}')\n"
                    "print(f'P-value: {p_value:.3f}')\n"
                    "print(f\"Cohen's f: {cohens_f:.3f}\")\n"
                    "significance = 'Significant' if p_value < 0.05 else 'Not significant'\n"
                    "print(f'Result: {significance} difference detected.')\n"
                )},
            ),
            AgentAction(
                action_type=ActionType.THINK,
                action="Interpret ANOVA results",
                thought="P-value < 0.05 confirms significant differences across age groups. "
                        "Effect size indicates practical significance. Ready to report.",
            ),
            AgentAction(
                action_type=ActionType.FINAL_ANSWER,
                action="Submit final analysis",
                thought="ANOVA reveals statistically significant differences in drug response "
                        "across age groups after handling missing values.",
                tool_name=None,
                tool_args=None,
            ),
        ],
        "Finance": [
            AgentAction(
                action_type=ActionType.THINK,
                action="Plan fairness audit",
                thought="Need to compute disparate impact ratio across gender groups "
                        "for loan approval. Will calculate approval rates per group.",
            ),
            AgentAction(
                action_type=ActionType.FILE_READ,
                action="Read audit dataset",
                tool_name="file_read",
                tool_args={"path": "data/audit_preview.csv"},
            ),
            AgentAction(
                action_type=ActionType.CODE_EXEC,
                action="Compute disparate impact ratio",
                tool_name="python_repl",
                tool_args={"code": (
                    "import numpy as np\n"
                    "np.random.seed(0)\n"
                    "n = 500\n"
                    "gender = np.random.choice(['M', 'F'], n, p=[0.55, 0.45])\n"
                    "approved = np.where(gender == 'M',\n"
                    "    np.random.binomial(1, 0.72, n),\n"
                    "    np.random.binomial(1, 0.58, n))\n"
                    "male_rate = approved[gender == 'M'].mean()\n"
                    "female_rate = approved[gender == 'F'].mean()\n"
                    "di_ratio = min(male_rate, female_rate) / max(male_rate, female_rate)\n"
                    "print(f'Male approval rate: {male_rate:.3f}')\n"
                    "print(f'Female approval rate: {female_rate:.3f}')\n"
                    "print(f'Disparate impact ratio: {di_ratio:.3f}')\n"
                    "flag = 'FLAGGED' if di_ratio < 0.8 else 'OK'\n"
                    "print(f'Four-fifths rule: {flag}')\n"
                )},
            ),
            AgentAction(
                action_type=ActionType.FINAL_ANSWER,
                action="Submit fairness audit results",
                thought="Disparate impact analysis complete with four-fifths rule assessment.",
            ),
        ],
        "ECommerce": [
            AgentAction(
                action_type=ActionType.THINK,
                action="Plan time series forecast",
                thought="Need to forecast 4 weeks ahead. Will check for seasonality "
                        "using autocorrelation and apply exponential smoothing.",
            ),
            AgentAction(
                action_type=ActionType.FILE_READ,
                action="Read sales data",
                tool_name="file_read",
                tool_args={"path": "data/sales_preview.csv"},
            ),
            AgentAction(
                action_type=ActionType.CODE_EXEC,
                action="Detect seasonality and compute baseline stats",
                tool_name="python_repl",
                tool_args={"code": (
                    "import numpy as np\n"
                    "np.random.seed(7)\n"
                    "weeks = 104\n"
                    "trend = np.linspace(10000, 15000, weeks)\n"
                    "seasonality = 2000 * np.sin(2 * np.pi * np.arange(weeks) / 52)\n"
                    "noise = np.random.normal(0, 300, weeks)\n"
                    "sales = trend + seasonality + noise\n"
                    "train, test = sales[:100], sales[100:]\n"
                    "print(f'Training weeks: {len(train)}, Test weeks: {len(test)}')\n"
                    "print(f'Train mean: {train.mean():.0f}, std: {train.std():.0f}')\n"
                    "print(f'Seasonality detected: annual pattern (52-week cycle)')\n"
                )},
            ),
            AgentAction(
                action_type=ActionType.CODE_EXEC,
                action="Fit exponential smoothing and compute MAPE",
                tool_name="python_repl",
                tool_args={"code": (
                    "import numpy as np\n"
                    "np.random.seed(7)\n"
                    "weeks = 104\n"
                    "trend = np.linspace(10000, 15000, weeks)\n"
                    "seasonality = 2000 * np.sin(2 * np.pi * np.arange(weeks) / 52)\n"
                    "sales = trend + seasonality + np.random.normal(0, 300, weeks)\n"
                    "train, test = sales[:100], sales[100:]\n"
                    "# Simple Holt-Winters-like forecast using last year same period\n"
                    "forecast = train[-4:] * (train[-4:].mean() / train[-56:-52].mean())\n"
                    "mape = np.mean(np.abs((test - forecast) / test)) * 100\n"
                    "print(f'4-week forecast: {forecast.round(0)}')\n"
                    "print(f'Actual: {test.round(0)}')\n"
                    "print(f'MAPE: {mape:.2f}%')\n"
                )},
            ),
            AgentAction(
                action_type=ActionType.FINAL_ANSWER,
                action="Submit forecast results",
                thought="Seasonal exponential smoothing applied, MAPE computed on holdout.",
            ),
        ],
    }

    _DEFAULT_SCRIPT = [
        AgentAction(
            action_type=ActionType.THINK,
            action="Analyze the problem",
            thought="Understanding the task requirements.",
        ),
        AgentAction(
            action_type=ActionType.CODE_EXEC,
            action="Execute analysis",
            tool_name="python_repl",
            tool_args={"code": "print('Analysis complete')"},
        ),
        AgentAction(
            action_type=ActionType.FINAL_ANSWER,
            action="Submit results",
        ),
    ]

    def __init__(self) -> None:
        self._script: List[AgentAction] = []
        self._script_idx = 0
        self._done = False

    def reset(self, task: TaskInput) -> None:
        domain = task.task_metadata.domain.value
        self._script = self._SCRIPTS.get(domain, self._DEFAULT_SCRIPT)
        self._script_idx = 0
        self._done = False

    def act(
        self,
        step_number: int,
        observation: str,
        trace_so_far: List[TraceStep],
    ) -> AgentAction:
        if self._script_idx >= len(self._script):
            self._done = True
            return AgentAction(
                action_type=ActionType.FINAL_ANSWER,
                action="Task complete — no more scripted steps",
            )
        action = self._script[self._script_idx]
        self._script_idx += 1
        if action.action_type == ActionType.FINAL_ANSWER:
            self._done = True
        return action

    def is_done(self) -> bool:
        return self._done
