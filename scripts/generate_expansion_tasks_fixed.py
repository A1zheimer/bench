import json
import os
import random
import pandas as pd
import numpy as np
from datetime import datetime

# 配置
BASE_DIR = '/Users/bytedance/Desktop/bench'
TASKS_DIR = os.path.join(BASE_DIR, 'tasks')
SEED_DIR = os.path.join(BASE_DIR, 'seed_datasets')

# 生成规范
GEN_SPEC = [
    {"domain":"Finance","difficulty":"Easy","count":4,"seed_dataset":"finance/california_housing_synthetic.csv","tags_pool":[["descriptive-statistics","aggregation","housing"],["correlation","feature-analysis","housing"],["group-by","summary-stats","loan"],["filtering","threshold-analysis","portfolio"]]},
    {"domain":"Finance","difficulty":"Medium","count":5,"seed_dataset":"finance/loan_defaults.csv","tags_pool":[["logistic-regression","credit-risk","AUC"],["feature-importance","random-forest","credit"],["missing-values","imputation","loan-analysis"],["class-imbalance","SMOTE","default-prediction"],["ROC-analysis","threshold-tuning","binary-classification"]]},
    {"domain":"Finance","difficulty":"Hard","count":7,"seed_dataset":"finance/stock_portfolio.csv","tags_pool":[["GARCH","volatility-modeling","time-series"],["Markowitz","portfolio-optimization","efficient-frontier"],["pairs-trading","cointegration","statistical-arbitrage"],["regime-detection","HMM","market-states"],["risk-parity","portfolio-allocation","Sharpe"],["ARIMA","forecasting","rolling-validation"],["factor-model","PCA","asset-pricing"]]},
    {"domain":"Biomedical","difficulty":"Easy","count":5,"seed_dataset":"biomedical/patient_readmission.csv","tags_pool":[["descriptive-statistics","readmission-rate","hospital"],["group-by","length-of-stay","diagnosis"],["correlation","clinical-features","age"],["filtering","medication-count","thresholds"],["cross-tabulation","comorbidity","diabetes"]]},
    {"domain":"Biomedical","difficulty":"Medium","count":5,"seed_dataset":"biomedical/drug_response.csv","tags_pool":[["dose-response","IC50","curve-fitting"],["two-way-ANOVA","drug-efficacy","interaction"],["missing-value-imputation","clinical","KNN"],["logistic-regression","calibration","prediction"],["chi-squared","independence-test","categorical"]]},
    {"domain":"Biomedical","difficulty":"Hard","count":7,"seed_dataset":"biomedical/breast_cancer_synthetic.csv","tags_pool":[["ensemble-stacking","cross-validation","meta-learner"],["cost-sensitive-classification","threshold-optimization","FPR"],["SHAP","model-interpretability","feature-importance"],["survival-analysis","Cox-PH","censoring"],["propensity-score-matching","causal-inference","treatment-effect"],["neural-network","MLP","hyperparameter-tuning"],["multi-task-learning","auxiliary-prediction","regularization"]]},
    {"domain":"ECommerce","difficulty":"Easy","count":4,"seed_dataset":"ecommerce/orders_v2.csv","tags_pool":[["aggregation","revenue","order-analysis"],["group-by","customer-segmentation","basic"],["time-series","daily-trends","visualization"],["filtering","top-products","ranking"]]},
    {"domain":"ECommerce","difficulty":"Medium","count":6,"seed_dataset":"ecommerce/ad_campaigns.csv","tags_pool":[["ROAS-analysis","platform-comparison","marketing"],["A/B-testing","lift-analysis","significance"],["cohort-analysis","retention","time-window"],["customer-LTV","prediction","regression"],["funnel-analysis","conversion-rate","stages"],["clustering","customer-segments","RFM"]]},
    {"domain":"ECommerce","difficulty":"Hard","count":6,"seed_dataset":"ecommerce/customer_churn.csv","tags_pool":[["survival-analysis","Kaplan-Meier","churn"],["cost-sensitive-churn","decision-threshold","profit-optimization"],["XGBoost","hyperparameter-search","churn-prediction"],["CLV-modeling","probabilistic","BG-NBD"],["multi-touch-attribution","Markov-chain","channel"],["uplift-modeling","treatment-effect","campaign"]]},
    {"domain":"Scientific","difficulty":"Easy","count":5,"seed_dataset":"scientific/iris_synthetic.csv","tags_pool":[["descriptive-statistics","species-comparison","mean"],["correlation","petal-sepal","relationship"],["group-by","species","count"],["visualization","scatter","distribution"],["filtering","outlier-detection","basic"]]},
    {"domain":"Scientific","difficulty":"Medium","count":5,"seed_dataset":"scientific/lab_experiment_v2.csv","tags_pool":[["ANOVA","factorial-design","yield"],["regression","multi-variable","prediction"],["PCA","dimensionality-reduction","variance"],["time-series","reaction-kinetics","modeling"],["bootstrap","confidence-interval","estimation"]]},
    {"domain":"Scientific","difficulty":"Hard","count":7,"seed_dataset":"scientific/weather_stations_v2.csv","tags_pool":[["SARIMA","seasonal-forecasting","temperature"],["changepoint-detection","CUSUM","precipitation"],["spatial-analysis","kriging","interpolation"],["mixed-effects-model","hierarchical","station-random"],["Bayesian-regression","uncertainty","posterior"],["DBSCAN","anomaly-detection","climate"],["wavelet-analysis","frequency-decomposition","signal"]]},
    {"domain":"Generic","difficulty":"Easy","count":3,"seed_dataset":"scientific/wine_synthetic.csv","tags_pool":[["basic-statistics","summary","exploration"],["cross-tabulation","frequency","distribution"],["data-profiling","quality-check","overview"]]},
    {"domain":"Generic","difficulty":"Medium","count":4,"seed_dataset":"ecommerce/user_sessions_v2.csv","tags_pool":[["missing-data-analysis","pattern","imputation-comparison"],["multi-variable-regression","feature-selection","stepwise"],["hypothesis-testing","t-test","effect-size"],["dimensionality-reduction","PCA","interpretation"]]},
    {"domain":"Generic","difficulty":"Hard","count":5,"seed_dataset":"finance/transactions_v2.csv","tags_pool":[["isolation-forest","anomaly-detection","contamination"],["ensemble-comparison","statistical-test","McNemar"],["pipeline-optimization","GridSearch","cross-validation"],["time-series-clustering","DTW","pattern-discovery"],["causal-discovery","Granger","VAR"]]}
]

# 难度参数
DIFFICULTY_CONFIG = {
    "Easy": {"max_steps": 6, "budget": 0.7, "timeout": 90},
    "Medium": {"max_steps": 12, "budget": 1.5, "timeout": 210},
    "Hard": {"max_steps": 20, "budget": 3.5, "timeout": 450}
}

# 列名映射
COLUMN_MAPPINGS = {
    "finance": {
        "median_income": "household_income",
        "house_age": "property_age",
        "avg_rooms": "average_rooms",
        "avg_bedrooms": "bedroom_count",
        "population": "resident_count",
        "avg_occupancy": "occupancy_rate",
        "latitude": "lat_coordinate",
        "longitude": "lon_coordinate",
        "median_house_value": "house_value"
    },
    "biomedical": {
        "patient_id": "subject_id",
        "age": "patient_age",
        "gender": "sex",
        "diagnosis": "medical_condition",
        "readmission": "rehospitalization",
        "length_of_stay": "hospital_stay_duration",
        "medication_count": "drug_count"
    },
    "ecommerce": {
        "order_id": "transaction_id",
        "customer_id": "user_id",
        "order_date": "purchase_date",
        "total_amount": "revenue",
        "product_id": "item_id",
        "quantity": "units",
        "channel": "platform"
    },
    "scientific": {
        "sepal_length": "sepal_length_cm",
        "sepal_width": "sepal_width_cm",
        "petal_length": "petal_length_cm",
        "petal_width": "petal_width_cm",
        "species": "flower_type",
        "temperature": "temp_celsius",
        "precipitation": "rainfall_mm"
    }
}

def generate_canary():
    return round(random.uniform(42.0, 43.0), 4)

def get_domain(seed_path):
    return seed_path.split('/')[0]

def generate_task(task_id, domain, difficulty, seed_dataset, tags):
    task_dir = os.path.join(TASKS_DIR, f'DS_TASK_{task_id:03d}')
    data_dir = os.path.join(task_dir, 'data')
    gt_dir = os.path.join(task_dir, 'ground_truth')
    
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(gt_dir, exist_ok=True)
    
    canary = generate_canary()
    seed_path = os.path.join(SEED_DIR, seed_dataset)
    
    # 加载并处理数据
    df = pd.read_csv(seed_path)
    domain_key = get_domain(seed_dataset)
    col_mapping = COLUMN_MAPPINGS.get(domain_key, {})
    df = df.rename(columns={k: v for k, v in col_mapping.items() if k in df.columns})
    
    # 注入canary
    if len(df) > 0:
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        if len(numeric_cols) > 0:
            df.loc[0, numeric_cols[0]] = canary
    
    # 难度相关扰动
    if difficulty == "Medium":
        for col in df.columns:
            if df[col].dtype in ['float64', 'int64']:
                mask = np.random.random(len(df)) < 0.05
                df.loc[mask, col] = np.nan
    elif difficulty == "Hard":
        for col in df.columns:
            if df[col].dtype in ['float64', 'int64']:
                mask = np.random.random(len(df)) < 0.1
                df.loc[mask, col] = np.nan
                outlier_mask = np.random.random(len(df)) < 0.02
                if len(df.loc[~mask, col]) > 0:
                    mean_val = df.loc[~mask, col].mean()
                    std_val = df.loc[~mask, col].std()
                    df.loc[outlier_mask, col] = mean_val + 3 * std_val
    
    # 保存数据
    df.to_csv(os.path.join(data_dir, 'dataset.csv'), index=False)
    
    # 生成trace
    trace = []
    
    # Step 0: 加载数据
    step0_code = "import pandas as pd\n\n# Load seed dataset\ndf = pd.read_csv('" + seed_path + "')\nprint('Dataset shape:', df.shape)\nprint('Data types:')\nprint(df.dtypes)\nprint('First 5 rows:')\nprint(df.head())"
    trace.append({
        "step": 0,
        "action": "python_repl",
        "args_preview": "{'code': 'import pandas as pd...'}",
        "result_preview": f"Dataset shape: ({df.shape[0]}, {df.shape[1]})\nData types:\n{df.dtypes.to_string()[:100]}...",
        "full_code": step0_code
    })
    
    # Step 1: 数据变换
    col_map_str = json.dumps(col_mapping)
    step1_code = "import pandas as pd\nimport numpy as np\n\n# Load seed dataset\ndf = pd.read_csv('" + seed_path + "')\n\n# Rename columns\ncol_mapping = " + col_map_str + "\ndf = df.rename(columns=col_mapping)\n\n# Inject canary\nif len(df) > 0:\n    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns\n    if len(numeric_cols) > 0:\n        df.loc[0, numeric_cols[0]] = " + str(canary) + "\n\n# Difficulty mutations\n"
    
    if difficulty == "Medium":
        step1_code += "# Add missing values\nfor col in df.columns:\n    if df[col].dtype in ['float64', 'int64']:\n        mask = np.random.random(len(df)) < 0.05\n        df.loc[mask, col] = np.nan\n"
    elif difficulty == "Hard":
        step1_code += "# Add missing values and outliers\nfor col in df.columns:\n    if df[col].dtype in ['float64', 'int64']:\n        mask = np.random.random(len(df)) < 0.1\n        df.loc[mask, col] = np.nan\n        outlier_mask = np.random.random(len(df)) < 0.02\n        if len(df.loc[~mask, col]) > 0:\n            mean_val = df.loc[~mask, col].mean()\n            std_val = df.loc[~mask, col].std()\n            df.loc[outlier_mask, col] = mean_val + 3 * std_val\n"
    
    step1_code += "\n# Save dataset\ndf.to_csv('dataset.csv', index=False)\nprint('Saved dataset with', len(df), 'rows,', len(df.columns), 'columns')"
    trace.append({
        "step": 1,
        "action": "python_repl",
        "args_preview": "{'code': 'import pandas as pd...'}",
        "result_preview": f"Saved dataset with {len(df)} rows, {len(df.columns)} columns",
        "full_code": step1_code
    })
    
    # 分析步骤
    key_values = {}
    execution_result = ""
    
    if difficulty == "Easy":
        step2_code = "import pandas as pd\n\n# Load dataset\ndf = pd.read_csv('dataset.csv')\n\n# Descriptive statistics\nprint('Descriptive statistics:')\nprint(df.describe())\n\n# Mean values\nmean_values = df.mean(numeric_only=True)\nprint('\nMean values:')\nprint(mean_values)"
        trace.append({
            "step": 2,
            "action": "python_repl",
            "args_preview": "{'code': 'import pandas as pd...'}",
            "result_preview": "Descriptive statistics...",
            "full_code": step2_code
        })
        key_values["mean_value"] = round(df.mean(numeric_only=True).iloc[0], 4)
        execution_result = f"Calculated descriptive statistics. Mean: {key_values['mean_value']}"
    
    elif difficulty == "Medium":
        step2_code = "import pandas as pd\n\n# Load dataset\ndf = pd.read_csv('dataset.csv')\n\n# Correlation matrix\ncorr_matrix = df.corr(numeric_only=True)\nprint('Correlation matrix:')\nprint(corr_matrix)\n\n# Strongest correlation\nmax_corr = corr_matrix.abs().unstack().sort_values(ascending=False).iloc[1]\nprint('\nStrongest correlation:', max_corr)"
        trace.append({
            "step": 2,
            "action": "python_repl",
            "args_preview": "{'code': 'import pandas as pd...'}",
            "result_preview": "Correlation matrix...",
            "full_code": step2_code
        })
        
        step3_code = "import pandas as pd\n\n# Load dataset\ndf = pd.read_csv('dataset.csv')\n\n# Missing values\nmissing_count = df.isnull().sum()\nprint('Missing values per column:')\nprint(missing_count)\n\n# Total missing\ntotal_missing = df.isnull().sum().sum()\nprint('\nTotal missing values:', total_missing)"
        trace.append({
            "step": 3,
            "action": "python_repl",
            "args_preview": "{'code': 'import pandas as pd...'}",
            "result_preview": "Missing values analysis...",
            "full_code": step3_code
        })
        
        corr_matrix = df.corr(numeric_only=True)
        max_corr = corr_matrix.abs().unstack().sort_values(ascending=False).iloc[1]
        key_values["max_correlation"] = round(float(max_corr), 4)
        key_values["total_missing"] = int(df.isnull().sum().sum())
        execution_result = f"Correlation analysis (max: {key_values['max_correlation']}) and missing value analysis (total: {key_values['total_missing']})"
    
    elif difficulty == "Hard":
        step2_code = "import pandas as pd\nimport numpy as np\n\n# Load dataset\ndf = pd.read_csv('dataset.csv')\n\n# Date column check\ndate_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]\nif date_cols:\n    df[date_cols[0]] = pd.to_datetime(df[date_cols[0]])\n    print('Date column found:', date_cols[0])\nelse:\n    print('No date columns found')\n\n# Rolling mean\nfor col in df.select_dtypes(include=['float64', 'int64']).columns:\n    df[f'{col}_rolling'] = df[col].rolling(window=7).mean()\n    print(f'Calculated rolling mean for {col}')"
        trace.append({
            "step": 2,
            "action": "python_repl",
            "args_preview": "{'code': 'import pandas as pd...'}",
            "result_preview": "Time series analysis...",
            "full_code": step2_code
        })
        
        step3_code = "import pandas as pd\nimport numpy as np\n\n# Load dataset\ndf = pd.read_csv('dataset.csv')\n\n# Outlier detection\noutliers = {}\nfor col in df.select_dtypes(include=['float64', 'int64']).columns:\n    Q1 = df[col].quantile(0.25)\n    Q3 = df[col].quantile(0.75)\n    IQR = Q3 - Q1\n    lower = Q1 - 1.5 * IQR\n    upper = Q3 + 1.5 * IQR\n    outlier_count = ((df[col] < lower) | (df[col] > upper)).sum()\n    outliers[col] = outlier_count\n    print(f'Outliers in {col}: {outlier_count}')\nprint('Total outliers:', sum(outliers.values()))"
        trace.append({
            "step": 3,
            "action": "python_repl",
            "args_preview": "{'code': 'import pandas as pd...'}",
            "result_preview": "Outlier detection...",
            "full_code": step3_code
        })
        
        step4_code = "import pandas as pd\nfrom sklearn.linear_model import LinearRegression\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.metrics import r2_score\n\n# Load dataset\ndf = pd.read_csv('dataset.csv')\n\n# Regression\nnumeric_cols = df.select_dtypes(include=['float64', 'int64']).columns\nif len(numeric_cols) >= 2:\n    X = df[numeric_cols[:-1]]\n    y = df[numeric_cols[-1]]\n    X = X.fillna(X.mean())\n    y = y.fillna(y.mean())\n    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n    model = LinearRegression()\n    model.fit(X_train, y_train)\n    y_pred = model.predict(X_test)\n    r2 = r2_score(y_test, y_pred)\n    print('R2 score:', r2)\nelse:\n    print('Not enough numeric columns')"
        trace.append({
            "step": 4,
            "action": "python_repl",
            "args_preview": "{'code': 'import pandas as pd...'}",
            "result_preview": "Regression modeling...",
            "full_code": step4_code
        })
        
        # 计算关键值
        outlier_count = 0
        for col in df.select_dtypes(include=['float64', 'int64']).columns:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            outlier_count += ((df[col] < lower) | (df[col] > upper)).sum()
        
        key_values["outlier_count"] = int(outlier_count)
        key_values["mean_value"] = round(df.mean(numeric_only=True).iloc[0], 4)
        corr_matrix = df.corr(numeric_only=True)
        if not corr_matrix.empty:
            max_corr = corr_matrix.abs().unstack().sort_values(ascending=False).iloc[1]
            key_values["correlation"] = round(float(max_corr), 4)
        execution_result = f"Time series analysis, outlier detection (total: {key_values['outlier_count']}), and regression modeling"
    
    # Step -1: submit_task
    trace.append({
        "step": -1,
        "action": "submit_task",
        "args_preview": f"{{'instance_id': 'DS_TASK_{task_id:03d}', ...}}",
        "result_preview": "Task submitted successfully",
        "full_code": None
    })
    
    # 生成task.json
    task_json = {
        "instance_id": f"DS_TASK_{task_id:03d}",
        "task_metadata": {
            "domain": domain,
            "difficulty": difficulty,
            "tags": tags,
            "contamination_risk": "low",
            "canary_value": canary
        },
        "context": {
            "problem_statement": f"Analyze the {domain.lower()} dataset and compute the required metrics. Focus on {', '.join(tags)}.",
            "dataset_preview": "data/dataset.csv",
            "expert_knowledge": "Use appropriate statistical methods for analysis. Handle missing values if present."
        },
        "environment_config": {
            "image": "ds-agent-v1:latest",
            "max_steps": DIFFICULTY_CONFIG[difficulty]['max_steps'],
            "budget": DIFFICULTY_CONFIG[difficulty]['budget'],
            "timeout_seconds": DIFFICULTY_CONFIG[difficulty]['timeout'],
            "allowed_tools": ["python_repl", "file_read", "web_search"]
        },
        "max_steps": DIFFICULTY_CONFIG[difficulty]['max_steps']
    }
    
    with open(os.path.join(task_dir, 'task.json'), 'w') as f:
        json.dump(task_json, f, indent=2)
    
    # 生成ground_truth
    ground_truth = {
        "execution_result": execution_result,
        "key_values": key_values,
        "required_keywords": tags,
        "validation_rules": [],
        "rubric": [
            {"criterion": "正确加载数据并检查结构", "weight": 0.2},
            {"criterion": "正确执行数据预处理", "weight": 0.3},
            {"criterion": "核心分析步骤正确", "weight": 0.3},
            {"criterion": "结果解读合理", "weight": 0.2}
        ]
    }
    
    with open(os.path.join(gt_dir, 'expected_output.json'), 'w') as f:
        json.dump(ground_truth, f, indent=2)
    
    # 生成generation_meta.json
    generation_meta = {
        "generator": "dataagent:custom",
        "temperature": 0.7,
        "canary_value": canary,
        "verified": False,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "trace": trace
    }
    
    with open(os.path.join(task_dir, 'generation_meta.json'), 'w') as f:
        json.dump(generation_meta, f, indent=2)
    
    print(f"Generated task DS_TASK_{task_id:03d}")

def main():
    current_id = 100
    
    for spec in GEN_SPEC:
        domain = spec["domain"]
        difficulty = spec["difficulty"]
        count = spec["count"]
        seed_dataset = spec["seed_dataset"]
        tags_pool = spec["tags_pool"]
        
        for i in range(count):
            tags = tags_pool[i % len(tags_pool)]
            generate_task(current_id, domain, difficulty, seed_dataset, tags)
            current_id += 1
    
    print(f"\nGenerated {current_id - 100} tasks")

if __name__ == "__main__":
    main()
