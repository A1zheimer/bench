from __future__ import annotations

CAS_WEIGHTS = {"accuracy": 0.40, "process": 0.35, "safety": 0.25}

# Canonical task-type slugs used in task_metadata. Papers/reports can render
# these with the bilingual labels below.
TASK_TYPE_LABELS = {
    "descriptive_aggregation": {
        "en": "Descriptive & Aggregation Analysis",
        "zh": "描述统计与聚合分析",
    },
    "statistical_inference": {
        "en": "Statistical Inference & Hypothesis Testing",
        "zh": "统计推断与假设检验",
    },
    "time_series_forecasting": {
        "en": "Time-Series & Forecasting",
        "zh": "时间序列与预测分析",
    },
    "predictive_modeling": {
        "en": "Predictive Modeling & Model Evaluation",
        "zh": "预测建模与模型评估",
    },
    "risk_anomaly_decision": {
        "en": "Risk, Anomaly & Decision Analysis",
        "zh": "异常、风险与决策分析",
    },
    "data_quality_robustness": {
        "en": "Data Quality & Robustness Handling",
        "zh": "数据质量与鲁棒性处理",
    },
    "specialized_domain_analysis": {
        "en": "Specialized Domain Analysis",
        "zh": "专业领域分析方法",
    },
}

VALID_TASK_TYPES = set(TASK_TYPE_LABELS)

ACCURACY_COMPONENT_WEIGHTS = {
    "data_selection": 0.15,
    "preprocessing": 0.10,
    "method_selection": 0.10,
    "numerical_result": 0.55,
    "interpretation": 0.05,
    "output_format": 0.05,
}

VALID_ACCURACY_COMPONENTS = set(ACCURACY_COMPONENT_WEIGHTS)

TEMP_GENERATION = 0.35
TEMP_REDTEAM = 0.30
TEMP_EVALUATION = 0.0
TEMP_JUDGE = 0.0
TEMP_CRITIC = 0.0
TEMP_REVIEWER = 0.0
