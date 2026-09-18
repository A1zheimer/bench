# DataAgentBench Curated Easy v1 GT Repair Report

Curated version: `curated_easy_v1`

| Task | Formula | Key Values | Dataset SHA256 |
| --- | --- | --- | --- |
| DS_TASK_061 | mean(hospital_stay_days where readmission == 1) | {"average_stay_duration_readmitted": 7.397163120567376} | db2a6793ae88ab21403b0d24d9e0e6d8f38e07a8071175f3a581e7621658909e |
| DS_TASK_066 | groupby(product_category).sum(total_cost) | {"total_revenue_books": 5411.86, "total_revenue_clothing": 12585.89, "total_revenue_electronics": 1062788.49, "total_revenue_food": 4738.28, "total_revenue_home": 4442.07, "total_revenue_sports": 3049.71} | 3da856663bdc2e500635befbb5a446d9f3a279b7e83cc6feef000e1ce5b93487 |
| DS_TASK_120 | crosstab(has_diabetes, has_hypertension); mean(readmitted_30d where both == 1) | {"crosstab_diabetes0_hypertension0": 439, "crosstab_diabetes0_hypertension1": 218, "crosstab_diabetes1_hypertension0": 147, "crosstab_diabetes1_hypertension1": 96, "diabetes_hypertension_count": 96, "diabetes_hypertension_prevalence": 0.10666666666666667, "readmission_rate_diabetes_hypertension": 0.3333333333333333} | ebfbdabee0fc78b1e4eed3c74a8a6b14b8a0c9037dea4bffb1664959e5ea5465 |
| DS_TASK_150 | pearson corr(sepal_length_cm, petal_length_cm), corr(sepal_width_cm, petal_width_cm), max abs off-diagonal corr | {"corr_sepal_length_petal_length": 0.3417212392073352, "corr_sepal_width_petal_width": -0.4035584766677104, "max_abs_correlation": 0.9267822929850092} | 148508aa3b30be8390372e10392a8ed799766dc2de9f4bea7666417caef6bcdb |
| DS_TASK_153 | per-column 1.5*IQR outlier count on numeric iris measurements | {"outlier_count_petal_length_cm": 0, "outlier_count_petal_width_cm": 0, "outlier_count_sepal_length_cm": 2, "outlier_count_sepal_width_cm": 1, "total_outlier_count": 3} | 14dfb6d954da22ba4a30eff105b484fe1c66399131637056fa56ca249cd2d7aa |
