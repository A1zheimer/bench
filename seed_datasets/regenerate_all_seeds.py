"""
DataAgentBench — Seed Dataset Full Regeneration (Academic-Grade)
================================================================
Regenerates ALL 16 seed datasets with:
  - Fixed random seeds for full reproducibility
  - Sufficient row counts for all difficulty levels (Easy/Medium/Hard)
  - Realistic statistical distributions with proper correlations
  - ~1-3% controlled missing values
  - No external dependencies (pure Python stdlib)

For sklearn-inspired datasets: synthetic data generated to match known
distributional properties of the original datasets. NOT copies/slices
of original data — avoids any licensing ambiguity.

Run: python3 regenerate_all_seeds.py
"""

import csv, os, random, math, hashlib, json
from datetime import datetime, timedelta
from collections import Counter

random.seed(20260326)  # fixed global seed, date of generation

BASE = "bench_content/bench/seed_datasets"


def write_csv(path, headers, rows):
    full = os.path.join(BASE, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    n = len(rows)
    c = len(headers)
    total = n * c
    miss = sum(1 for r in rows for v in r if v == "")
    print(f"  {path}: {n} rows × {c} cols, missing={miss}/{total} ({miss/total*100:.2f}%)")
    return n, c


def gauss_clamp(mu, sigma, lo, hi):
    return max(lo, min(hi, random.gauss(mu, sigma)))


def multivariate_normal_2d(mu, cov, n):
    """Generate n samples from 2D normal. Returns list of (x,y) tuples."""
    # Cholesky decomposition for 2x2
    a = math.sqrt(cov[0][0])
    b = cov[0][1] / a
    c = math.sqrt(cov[1][1] - b * b)
    samples = []
    for _ in range(n):
        z1, z2 = random.gauss(0, 1), random.gauss(0, 1)
        x = mu[0] + a * z1
        y = mu[1] + b * z1 + c * z2
        samples.append((x, y))
    return samples


def inject_missing(row, indices, rate=0.02):
    """Randomly blank out values at given column indices."""
    for idx in indices:
        if random.random() < rate:
            row[idx] = ""
    return row


# ============================================================
# PART A: sklearn-inspired synthetic datasets
# ============================================================

def gen_iris():
    """
    Inspired by: Fisher's Iris dataset (1936)
    Original: 150 samples, 4 features, 3 classes
    Our version: 300 samples for broader difficulty coverage
    
    Known cluster centers (approximate):
      setosa:     [5.0, 3.4, 1.5, 0.2]
      versicolor: [5.9, 2.8, 4.3, 1.3]
      virginica:  [6.6, 3.0, 5.6, 2.0]
    """
    random.seed(101)
    headers = ["sepal_length_cm", "sepal_width_cm", "petal_length_cm",
               "petal_width_cm", "species"]
    
    clusters = {
        "setosa":     {"mu": [5.0, 3.4, 1.5, 0.25], "sigma": [0.35, 0.38, 0.17, 0.11]},
        "versicolor": {"mu": [5.94, 2.77, 4.26, 1.33], "sigma": [0.52, 0.31, 0.47, 0.20]},
        "virginica":  {"mu": [6.59, 2.97, 5.55, 2.03], "sigma": [0.64, 0.32, 0.55, 0.27]},
    }
    
    rows = []
    for species, params in clusters.items():
        for _ in range(100):
            row = [
                round(gauss_clamp(params["mu"][i], params["sigma"][i], 
                      params["mu"][i] - 3*params["sigma"][i], 
                      params["mu"][i] + 3*params["sigma"][i]), 1)
                for i in range(4)
            ]
            row.append(species)
            rows.append(row)
    
    random.shuffle(rows)
    return write_csv("scientific/iris_synthetic.csv", headers, rows)


def gen_wine():
    """
    Inspired by: UCI Wine dataset (Forina et al. 1988)
    Original: 178 samples, 13 features, 3 cultivars
    Our version: 500 samples for Hard difficulty support
    """
    random.seed(102)
    headers = [
        "alcohol", "malic_acid", "ash", "alcalinity_of_ash", "magnesium",
        "total_phenols", "flavanoids", "nonflavanoid_phenols", "proanthocyanins",
        "color_intensity", "hue", "od280_od315", "proline", "cultivar"
    ]
    
    # Approximate distributions per cultivar from known data
    cultivar_params = {
        "ClassA": {  # cultivar 1
            "mu": [13.7, 2.0, 2.45, 17.0, 106, 2.84, 3.01, 0.29, 1.90, 5.5, 1.06, 3.16, 1100],
            "sigma": [0.5, 0.7, 0.2, 2.5, 12, 0.34, 0.4, 0.07, 0.4, 1.2, 0.12, 0.36, 220],
        },
        "ClassB": {  # cultivar 2
            "mu": [12.3, 1.9, 2.24, 20.2, 94, 2.26, 2.08, 0.36, 1.63, 3.1, 1.06, 2.78, 520],
            "sigma": [0.5, 0.8, 0.3, 3.3, 17, 0.4, 0.7, 0.12, 0.6, 1.0, 0.2, 0.5, 150],
        },
        "ClassC": {  # cultivar 3
            "mu": [13.2, 3.3, 2.44, 21.4, 99, 1.68, 0.78, 0.45, 1.15, 7.4, 0.68, 1.68, 630],
            "sigma": [0.5, 1.1, 0.2, 2.3, 11, 0.3, 0.3, 0.12, 0.4, 2.0, 0.13, 0.3, 170],
        },
    }
    
    rows = []
    counts = {"ClassA": 170, "ClassB": 175, "ClassC": 155}  # slightly imbalanced
    for cultivar, n in counts.items():
        params = cultivar_params[cultivar]
        for _ in range(n):
            row = []
            for i in range(13):
                val = gauss_clamp(params["mu"][i], params["sigma"][i],
                                  params["mu"][i] - 3*params["sigma"][i],
                                  params["mu"][i] + 3*params["sigma"][i])
                row.append(round(val, 2) if i != 12 else int(val))
            row.append(cultivar)
            inject_missing(row, [1, 4, 8], rate=0.015)
            rows.append(row)
    
    random.shuffle(rows)
    return write_csv("scientific/wine_synthetic.csv", headers, rows)


def gen_breast_cancer():
    """
    Inspired by: Wisconsin Breast Cancer (Diagnostic) Dataset
    Original: 569 samples, 30 features (10 features × mean/se/worst), 2 classes
    Our version: 800 samples, 16 selected features for practical benchmark use
    """
    random.seed(103)
    headers = [
        "mean_radius", "mean_texture", "mean_smoothness", "mean_compactness",
        "mean_concavity", "mean_concave_points", "mean_symmetry",
        "radius_se", "texture_se", "smoothness_se",
        "worst_radius", "worst_texture", "worst_perimeter", "worst_area",
        "worst_concavity", "diagnosis"
    ]
    
    # Malignant vs Benign distributions (approximate from known data)
    class_params = {
        "malignant": {
            "mu":    [17.5, 21.6, 0.103, 0.145, 0.16, 0.088, 0.193, 0.61, 1.21, 0.007, 21.1, 29.3, 141, 1422, 0.45],
            "sigma": [3.2, 3.8, 0.013, 0.05, 0.07, 0.03, 0.02, 0.3, 0.5, 0.003, 4.3, 5.5, 30, 600, 0.15],
            "count": 300,
        },
        "benign": {
            "mu":    [12.1, 17.9, 0.092, 0.080, 0.046, 0.026, 0.174, 0.28, 0.55, 0.005, 13.4, 23.5, 87, 559, 0.17],
            "sigma": [1.8, 4.0, 0.014, 0.035, 0.04, 0.016, 0.025, 0.1, 0.3, 0.002, 2.5, 4.5, 18, 230, 0.1],
            "count": 500,
        },
    }
    
    rows = []
    for diag, params in class_params.items():
        for _ in range(params["count"]):
            row = []
            for i in range(15):
                val = gauss_clamp(params["mu"][i], params["sigma"][i],
                                  max(0, params["mu"][i] - 3.5*params["sigma"][i]),
                                  params["mu"][i] + 3.5*params["sigma"][i])
                row.append(round(val, 4))
            row.append(diag)
            inject_missing(row, [2, 7, 9], rate=0.02)
            rows.append(row)
    
    random.shuffle(rows)
    return write_csv("biomedical/breast_cancer_synthetic.csv", headers, rows)


def gen_diabetes():
    """
    Inspired by: Efron et al. (2004) diabetes dataset
    Original: 442 samples, 10 features (normalized), continuous target
    Our version: 600 samples, 10 features, regression target
    """
    random.seed(104)
    headers = [
        "age", "sex", "bmi", "blood_pressure", "s1_tc", "s2_ldl",
        "s3_hdl", "s4_tch", "s5_ltg", "s6_glucose", "progression"
    ]
    
    rows = []
    for _ in range(600):
        age = round(random.gauss(0, 0.048), 6)
        sex = round(random.choice([-0.045, 0.051]), 6)
        bmi = round(random.gauss(0, 0.048), 6)
        bp = round(random.gauss(0, 0.048), 6)
        s1 = round(random.gauss(0, 0.048), 6)
        s2 = round(s1 * 0.9 + random.gauss(0, 0.015), 6)  # correlated with s1
        s3 = round(random.gauss(0, 0.048), 6)
        s4 = round(random.gauss(0, 0.048), 6)
        s5 = round(random.gauss(0, 0.048), 6)
        s6 = round(random.gauss(0, 0.048), 6)
        
        # Target: progression (linear combination + noise)
        progression = (
            152 + 600 * bmi + 300 * bp + 500 * s5 + 200 * age
            + 100 * s1 - 300 * s3 + random.gauss(0, 50)
        )
        progression = round(max(25, min(346, progression)), 1)
        
        row = [age, sex, bmi, bp, s1, s2, s3, s4, s5, s6, progression]
        inject_missing(row, [3, 5, 9], rate=0.02)
        rows.append(row)
    
    random.shuffle(rows)
    return write_csv("biomedical/diabetes_synthetic.csv", headers, rows)


def gen_california_housing():
    """
    Inspired by: Pace & Barry (1997) California Housing dataset
    Original: 20640 samples, 8 features, continuous target
    Our version: 2000 samples covering realistic housing distributions
    """
    random.seed(105)
    headers = [
        "median_income", "house_age", "avg_rooms", "avg_bedrooms",
        "population", "avg_occupancy", "latitude", "longitude",
        "median_house_value"
    ]
    
    # California geographic regions with different housing characteristics
    regions = [
        {"lat": (32.5, 34.0), "lon": (-118.5, -117.0), "income_mu": 4.5, "price_mu": 250000, "n": 500},   # SoCal urban
        {"lat": (34.0, 35.5), "lon": (-119.0, -117.5), "income_mu": 3.5, "price_mu": 180000, "n": 300},   # SoCal suburban
        {"lat": (36.5, 38.5), "lon": (-122.5, -121.0), "income_mu": 5.5, "price_mu": 350000, "n": 500},   # Bay Area
        {"lat": (38.5, 40.0), "lon": (-122.5, -121.0), "income_mu": 3.0, "price_mu": 150000, "n": 250},   # Sacramento
        {"lat": (33.5, 34.5), "lon": (-118.5, -117.5), "income_mu": 6.0, "price_mu": 400000, "n": 200},   # LA wealthy
        {"lat": (35.0, 37.0), "lon": (-121.0, -119.0), "income_mu": 2.5, "price_mu": 100000, "n": 250},   # Central Valley
    ]
    
    rows = []
    for reg in regions:
        for _ in range(reg["n"]):
            lat = round(random.uniform(*reg["lat"]), 2)
            lon = round(random.uniform(*reg["lon"]), 2)
            income = round(max(0.5, random.gauss(reg["income_mu"], 1.8)), 4)
            age = round(gauss_clamp(28, 13, 1, 52))
            rooms = round(max(1, random.gauss(5.4, 1.8)), 3)
            bedrooms = round(max(0.5, rooms * random.gauss(0.2, 0.05)), 3)
            population = int(max(3, random.gauss(1400, 1100)))
            occupancy = round(max(1, random.gauss(3.0, 1.2)), 3)
            
            # Price model (correlated with income, location, age)
            price = (reg["price_mu"]
                     + 30000 * (income - reg["income_mu"])
                     + random.gauss(0, 40000))
            price = round(max(15000, min(500001, price)), 1)
            
            row = [income, age, rooms, bedrooms, population, occupancy, lat, lon, price]
            inject_missing(row, [3, 5], rate=0.02)
            rows.append(row)
    
    random.shuffle(rows)
    return write_csv("finance/california_housing_synthetic.csv", headers, rows)


# ============================================================
# PART B: Original synthetic datasets (regenerated with fixed seeds)
# ============================================================

def gen_orders():
    """E-commerce orders dataset with realistic purchasing patterns."""
    random.seed(201)
    headers = [
        "order_id", "customer_id", "order_date", "category", "unit_price",
        "quantity", "total_amount", "channel", "returned", "rating"
    ]
    
    categories = {"Electronics": (200, 150), "Clothing": (50, 30), "Books": (20, 12),
                  "Home & Garden": (80, 50), "Sports": (60, 40), "Toys": (30, 20)}
    channels = ["Web", "Mobile", "In-Store"]
    start = datetime(2023, 1, 1)
    
    rows = []
    for i in range(1, 1001):
        cat = random.choice(list(categories.keys()))
        mu, sigma = categories[cat]
        price = round(max(5, random.gauss(mu, sigma)), 2)
        qty = random.choices([1, 2, 3, 4, 5], weights=[50, 25, 15, 7, 3])[0]
        total = round(price * qty, 2)
        dt = start + timedelta(days=random.randint(0, 364))
        channel = random.choices(channels, weights=[45, 35, 20])[0]
        
        # Return probability depends on category
        ret_rate = {"Electronics": 0.12, "Clothing": 0.15, "Books": 0.03,
                    "Home & Garden": 0.08, "Sports": 0.06, "Toys": 0.10}
        returned = 1 if random.random() < ret_rate.get(cat, 0.08) else 0
        
        # Rating: lower if returned
        if returned:
            rating = random.choices([1, 2, 3, 4, 5], weights=[25, 30, 25, 15, 5])[0]
        else:
            rating = random.choices([1, 2, 3, 4, 5], weights=[3, 7, 15, 35, 40])[0]
        
        cust_id = random.randint(100, 999)
        row = [10000 + i, cust_id, dt.strftime("%Y-%m-%d"), cat, price, qty,
               total, channel, returned, rating]
        inject_missing(row, [9], rate=0.03)
        rows.append(row)
    
    return write_csv("ecommerce/orders_v2.csv", headers, rows)


def gen_user_sessions():
    """Web user session data with conversion funnel metrics."""
    random.seed(202)
    headers = [
        "session_id", "user_id", "timestamp", "device", "traffic_source",
        "duration_seconds", "pages_viewed", "bounce", "converted", "cart_value"
    ]
    
    devices = ["Desktop", "Mobile", "Tablet"]
    sources = ["Organic", "Paid", "Social", "Direct", "Email", "Referral"]
    start = datetime(2024, 1, 1)
    
    rows = []
    for i in range(1, 801):
        device = random.choices(devices, weights=[35, 50, 15])[0]
        source = random.choices(sources, weights=[30, 20, 15, 20, 10, 5])[0]
        dt = start + timedelta(
            days=random.randint(0, 179),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
        
        # Duration depends on device
        dur_mu = {"Desktop": 240, "Mobile": 150, "Tablet": 200}[device]
        duration = int(max(3, random.gauss(dur_mu, dur_mu * 0.6)))
        pages = max(1, int(duration / random.gauss(50, 15)))
        bounce = 1 if pages == 1 else 0
        
        # Conversion depends on pages viewed and source
        source_mult = {"Paid": 1.5, "Email": 1.3, "Direct": 1.2,
                       "Organic": 1.0, "Social": 0.7, "Referral": 0.9}
        conv_prob = min(0.3, 0.02 * pages * source_mult.get(source, 1.0))
        converted = 1 if random.random() < conv_prob and not bounce else 0
        cart_val = round(random.gauss(65, 40), 2) if converted else 0
        cart_val = max(0, cart_val)
        
        row = [f"S{i:06d}", random.randint(1000, 9999), dt.strftime("%Y-%m-%d %H:%M"),
               device, source, duration, pages, bounce, converted, round(cart_val, 2)]
        inject_missing(row, [5, 9], rate=0.02)
        rows.append(row)
    
    return write_csv("ecommerce/user_sessions_v2.csv", headers, rows)


def gen_transactions():
    """Financial transaction data with fraud detection labels."""
    random.seed(203)
    headers = [
        "transaction_id", "customer_id", "date", "hour", "day_of_week",
        "amount", "category", "merchant_type", "is_international", "is_fraud"
    ]
    
    categories = ["Electronics", "Groceries", "Dining", "Travel", "Entertainment",
                  "Utilities", "Healthcare", "Retail"]
    merchant_types = ["Online", "POS", "ATM"]
    start = datetime(2024, 1, 1)
    
    rows = []
    for i in range(1, 801):
        cust = random.randint(1000, 2000)
        dt = start + timedelta(days=random.randint(0, 179))
        hour = random.choices(list(range(24)),
            weights=[1,1,1,1,1,2,4,6,7,7,6,6,6,6,5,5,5,6,7,8,6,4,2,1])[0]
        dow = dt.weekday()
        cat = random.choice(categories)
        merchant = random.choices(merchant_types, weights=[40, 50, 10])[0]
        
        # Amount distribution varies by category
        amt_params = {"Electronics": (150, 120), "Groceries": (45, 25),
                      "Dining": (35, 20), "Travel": (300, 200),
                      "Entertainment": (40, 30), "Utilities": (80, 40),
                      "Healthcare": (120, 80), "Retail": (60, 45)}
        mu, sigma = amt_params.get(cat, (50, 30))
        amount = round(max(1, random.gauss(mu, sigma)), 2)
        is_intl = 1 if random.random() < 0.12 else 0
        
        # Fraud model
        fraud_logit = (-4.5
                       + 0.5 * is_intl
                       + 0.3 * (1 if hour < 5 else 0)
                       + 0.002 * amount
                       + 0.3 * (1 if merchant == "Online" else 0))
        is_fraud = 1 if random.random() < (1.0 / (1.0 + math.exp(-fraud_logit))) else 0
        
        row = [i, cust, dt.strftime("%Y-%m-%d"), hour, dow, amount,
               cat, merchant, is_intl, is_fraud]
        inject_missing(row, [5], rate=0.01)
        rows.append(row)
    
    return write_csv("finance/transactions_v2.csv", headers, rows)


def gen_lab_experiment():
    """Scientific lab experiment with factorial design."""
    random.seed(204)
    headers = [
        "experiment_id", "temperature_C", "concentration_mM", "catalyst",
        "ph_level", "replicate", "yield_percent", "reaction_time_min",
        "purity_percent", "byproduct_mg"
    ]
    
    catalysts = ["None", "Platinum", "Palladium", "Nickel"]
    temps = [20, 30, 40, 50, 60, 70, 80]
    concs = [0.1, 0.5, 1.0, 2.0, 5.0]
    
    rows = []
    eid = 0
    for temp in temps:
        for conc in concs:
            for cat in catalysts:
                for rep in range(1, 4):  # 3 replicates
                    eid += 1
                    ph = round(gauss_clamp(7.0, 0.5, 4.0, 10.0), 1)
                    
                    # Yield model: depends on temp, conc, catalyst
                    cat_effect = {"None": 0, "Platinum": 25, "Palladium": 18, "Nickel": 10}[cat]
                    base_yield = (20 + 0.4 * temp + 8 * math.log(conc + 0.1) + cat_effect
                                  - 0.003 * temp * temp)  # diminishing returns at high temp
                    y = gauss_clamp(base_yield, 5, 0, 100)
                    
                    rxn_time = max(5, random.gauss(60 - 0.3 * temp + 10 * conc, 10))
                    purity = gauss_clamp(85 + cat_effect * 0.3 - 0.1 * conc, 4, 50, 100)
                    byproduct = max(0, random.gauss(10 - cat_effect * 0.2 + 0.5 * conc, 3))
                    
                    row = [eid, temp, conc, cat, ph, rep,
                           round(y, 1), round(rxn_time, 1),
                           round(purity, 1), round(byproduct, 2)]
                    inject_missing(row, [4, 8], rate=0.015)
                    rows.append(row)
    
    return write_csv("scientific/lab_experiment_v2.csv", headers, rows)


def gen_weather():
    """Multi-station weather data with seasonal patterns."""
    random.seed(205)
    headers = [
        "date", "station", "latitude", "longitude", "temp_celsius",
        "precipitation_mm", "humidity_percent", "wind_speed_kmh",
        "pressure_hpa", "cloud_cover_pct"
    ]
    
    stations = {
        "NORTH":   {"lat": 48.0, "lon": -122.3, "temp_base": 8,  "precip_base": 3.5},
        "CENTRAL": {"lat": 37.8, "lon": -122.4, "temp_base": 14, "precip_base": 1.8},
        "SOUTH":   {"lat": 34.0, "lon": -118.2, "temp_base": 18, "precip_base": 0.8},
        "INLAND":  {"lat": 36.7, "lon": -119.8, "temp_base": 16, "precip_base": 0.5},
        "COASTAL": {"lat": 32.7, "lon": -117.2, "temp_base": 17, "precip_base": 0.6},
    }
    
    start = datetime(2020, 1, 1)
    rows = []
    
    for day_i in range(730):  # 2 years
        dt = start + timedelta(days=day_i)
        date_str = dt.strftime("%Y-%m-%d")
        day_of_year = dt.timetuple().tm_yday
        season_factor = math.sin(2 * math.pi * (day_of_year - 80) / 365)
        
        for stn, params in stations.items():
            temp = params["temp_base"] + 10 * season_factor + random.gauss(0, 3)
            precip = max(0, params["precip_base"] * (1 - 0.5 * season_factor) 
                        + random.gauss(0, 2))
            if random.random() < 0.4:
                precip = 0  # many dry days
            humidity = gauss_clamp(60 + 10 * (precip > 0) - 5 * season_factor, 12, 10, 100)
            wind = max(0, random.gauss(12, 6))
            pressure = gauss_clamp(1013 - 2 * (precip > 1), 5, 980, 1040)
            cloud = gauss_clamp(40 + 20 * (precip > 0), 20, 0, 100)
            
            row = [date_str, f"STN_{stn}", params["lat"], params["lon"],
                   round(temp, 1), round(precip, 1), round(humidity, 1),
                   round(wind, 1), round(pressure, 1), round(cloud, 0)]
            inject_missing(row, [5, 7, 9], rate=0.01)
            rows.append(row)
    
    return write_csv("scientific/weather_stations_v2.csv", headers, rows)


# ============================================================
# PART C: New synthetic datasets (from previous generation, re-seeded)
# ============================================================

def gen_loan_defaults():
    random.seed(301)
    headers = [
        "loan_id", "age", "income", "employment_years", "loan_amount",
        "interest_rate", "loan_term_months", "credit_score", "dti_ratio",
        "num_credit_lines", "delinquencies_2yr", "home_ownership",
        "loan_purpose", "defaulted"
    ]
    ownerships = ["RENT", "OWN", "MORTGAGE"]
    purposes = ["debt_consolidation", "credit_card", "home_improvement",
                 "major_purchase", "medical", "small_business"]
    rows = []
    for i in range(1, 801):
        age = random.randint(22, 68)
        income = round(max(12000, random.gauss(55000, 22000)), 2)
        emp_years = min(age - 20, max(0, int(random.gauss(7, 5))))
        credit_score = max(350, min(850, int(random.gauss(680, 70))))
        loan_amount = round(max(1000, random.gauss(15000, 10000)), 2)
        interest_rate = round(max(3.5, random.gauss(11.0, 4.0)), 2)
        loan_term = random.choice([36, 60])
        dti_ratio = round(max(0.01, random.gauss(0.18, 0.08)), 4)
        num_lines = max(0, int(random.gauss(8, 4)))
        delinq = 0 if random.random() > 0.2 else random.randint(1, 5)
        ownership = random.choice(ownerships)
        purpose = random.choice(purposes)
        logit = (-3.5 + 0.02*(interest_rate-10) + 0.5*(dti_ratio-0.15)
                 - 0.003*(credit_score-650) + 0.3*delinq - 0.02*emp_years)
        defaulted = 1 if random.random() < 1/(1+math.exp(-logit)) else 0
        row = [i, age, income, emp_years, loan_amount, interest_rate,
               loan_term, credit_score, dti_ratio, num_lines, delinq,
               ownership, purpose, defaulted]
        inject_missing(row, [2, 7], rate=0.02)
        rows.append(row)
    return write_csv("finance/loan_defaults.csv", headers, rows)


def gen_stock_portfolio():
    random.seed(302)
    headers = [
        "date", "ticker", "sector", "open_price", "close_price",
        "daily_return", "volume", "market_cap_B", "pe_ratio",
        "dividend_yield", "sp500_return"
    ]
    tickers = {
        "AAPL": ("Technology", 170, 2800), "MSFT": ("Technology", 380, 2900),
        "JNJ": ("Healthcare", 155, 380), "PFE": ("Healthcare", 28, 160),
        "JPM": ("Financials", 185, 540), "BAC": ("Financials", 33, 260),
        "XOM": ("Energy", 105, 450), "CVX": ("Energy", 155, 300),
        "PG": ("Consumer", 160, 380), "KO": ("Consumer", 60, 260),
    }
    start = datetime(2024, 1, 2)
    rows = []
    prices = {t: info[1] for t, info in tickers.items()}
    for day_i in range(250):
        dt = start + timedelta(days=int(day_i * 365.0 / 250))
        date_str = dt.strftime("%Y-%m-%d")
        sp500_ret = round(random.gauss(0.0004, 0.012), 6)
        for ticker, (sector, _, mcap) in tickers.items():
            open_p = round(prices[ticker], 2)
            ret = sp500_ret * random.gauss(1.0, 0.3) + random.gauss(0, 0.015)
            close_p = round(open_p * (1 + ret), 2)
            volume = max(100000, int(random.gauss(5e6, 2e6)))
            pe = round(max(5, random.gauss(22, 8)), 2)
            div_yield = round(max(0, random.gauss(0.02, 0.01)), 4)
            row = [date_str, ticker, sector, open_p, close_p, round(ret, 6),
                   volume, mcap, pe, div_yield, round(sp500_ret, 6)]
            inject_missing(row, [8, 9], rate=0.01)
            rows.append(row)
            prices[ticker] = close_p
    return write_csv("finance/stock_portfolio.csv", headers, rows)


def gen_patient_readmission():
    random.seed(303)
    headers = [
        "patient_id", "age", "gender", "admission_type", "diagnosis_group",
        "num_procedures", "num_medications", "length_of_stay_days",
        "num_prior_admissions", "has_diabetes", "has_hypertension",
        "discharge_disposition", "a1c_level", "readmitted_30d"
    ]
    admission_types = ["Emergency", "Urgent", "Elective"]
    diag_groups = ["Circulatory", "Respiratory", "Digestive", "Musculoskeletal",
                   "Endocrine", "Genitourinary", "Injury"]
    dispositions = ["Home", "SNF", "Home_Health", "Rehab", "AMA"]
    rows = []
    for i in range(1, 901):
        age = random.randint(18, 95)
        gender = random.choice(["M", "F"])
        adm_type = random.choices(admission_types, weights=[50, 30, 20])[0]
        diag = random.choice(diag_groups)
        n_proc = max(0, int(random.gauss(2, 2)))
        n_meds = max(1, int(random.gauss(12, 6)))
        los = max(1, int(random.gauss(5, 4)))
        prior = max(0, int(random.gauss(1, 2)))
        diabetes = 1 if random.random() < (0.25 + 0.005*(age-50)) else 0
        hypertension = 1 if random.random() < (0.3 + 0.005*(age-45)) else 0
        disp = random.choices(dispositions, weights=[45, 20, 20, 10, 5])[0]
        a1c = round(max(4.0, random.gauss(6.5 if diabetes else 5.2, 0.8)), 1)
        logit = (-2.5 + 0.01*(age-60) + 0.3*(1 if adm_type=="Emergency" else 0)
                 + 0.1*n_proc + 0.02*n_meds + 0.05*los + 0.4*prior
                 + 0.3*diabetes + 0.15*hypertension - 0.3*(1 if disp=="Home" else 0))
        readmitted = 1 if random.random() < 1/(1+math.exp(-logit)) else 0
        row = [i, age, gender, adm_type, diag, n_proc, n_meds, los,
               prior, diabetes, hypertension, disp, a1c, readmitted]
        inject_missing(row, [12, 5], rate=0.025)
        rows.append(row)
    return write_csv("biomedical/patient_readmission.csv", headers, rows)


def gen_drug_response():
    random.seed(304)
    headers = [
        "experiment_id", "drug_name", "cell_line", "concentration_uM",
        "viability_percent", "log_concentration", "replicate",
        "passage_number", "treatment_hours", "ic50_estimated"
    ]
    drugs = {
        "Doxorubicin": {"ic50": 0.5, "hill": 1.2}, "Paclitaxel": {"ic50": 0.02, "hill": 1.5},
        "Cisplatin": {"ic50": 5.0, "hill": 0.8}, "Methotrexate": {"ic50": 1.0, "hill": 1.0},
        "5-FU": {"ic50": 10.0, "hill": 0.9},
    }
    cell_lines = ["MCF-7", "HeLa", "A549", "HCT116", "PC-3"]
    concentrations = [0.001, 0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]
    rows = []
    eid = 0
    for drug, params in drugs.items():
        for cell in cell_lines:
            effective_ic50 = params["ic50"] * max(0.1, random.gauss(1.0, 0.3))
            hill = params["hill"]
            passage = random.randint(5, 30)
            for conc in concentrations:
                for rep in range(1, 4):
                    eid += 1
                    log_c = round(math.log10(conc + 1e-10), 4)
                    viability = 100.0 / (1.0 + (conc / effective_ic50) ** hill)
                    viability = round(max(0, min(105, viability + random.gauss(0, 3))), 2)
                    row = [eid, drug, cell, conc, viability, log_c, rep,
                           passage, random.choice([24, 48, 72]), round(effective_ic50, 4)]
                    inject_missing(row, [4], rate=0.01)
                    rows.append(row)
    return write_csv("biomedical/drug_response.csv", headers, rows)


def gen_ad_campaigns():
    random.seed(305)
    headers = [
        "campaign_id", "date", "platform", "ad_format", "target_audience",
        "budget_usd", "impressions", "clicks", "ctr", "conversions",
        "cost_per_click", "cost_per_conversion", "revenue", "roas"
    ]
    platforms = ["Google", "Facebook", "Instagram", "TikTok", "LinkedIn"]
    formats = ["search", "display", "video", "carousel", "story"]
    audiences = ["18-24", "25-34", "35-44", "45-54", "55+"]
    start = datetime(2024, 7, 1)
    rows = []
    cid = 0
    for day_i in range(180):
        dt = start + timedelta(days=day_i)
        date_str = dt.strftime("%Y-%m-%d")
        season_mult = 1.0 + 0.15 * (1 if dt.weekday() < 5 else -1)
        for platform in platforms:
            if random.random() < 0.3: continue
            for _ in range(random.randint(1, 3)):
                cid += 1
                budget = round(max(20, random.gauss(150, 80)), 2)
                base_ctr = {"Google":0.035,"Facebook":0.012,"Instagram":0.015,"TikTok":0.018,"LinkedIn":0.008}
                ctr_val = max(0.001, random.gauss(base_ctr.get(platform,0.015), 0.005))
                impressions = max(100, int(budget * random.gauss(60, 20) * season_mult))
                clicks = max(0, int(impressions * ctr_val))
                conversions = max(0, int(clicks * max(0, random.gauss(0.03, 0.015))))
                cpc = round(budget / max(1, clicks), 2)
                cost_conv = round(budget / max(1, conversions), 2) if conversions > 0 else ""
                revenue = round(conversions * max(10, random.gauss(65, 30)), 2)
                roas = round(revenue / max(1, budget), 2)
                row = [cid, date_str, platform, random.choice(formats),
                       random.choice(audiences), budget, impressions, clicks,
                       round(ctr_val, 4), conversions, cpc, cost_conv, revenue, roas]
                inject_missing(row, [12], rate=0.02)
                rows.append(row)
    return write_csv("ecommerce/ad_campaigns.csv", headers, rows)


def gen_customer_churn():
    random.seed(306)
    headers = [
        "customer_id", "tenure_months", "monthly_charges", "total_charges",
        "contract_type", "payment_method", "num_support_tickets",
        "avg_monthly_usage_gb", "num_products", "has_premium",
        "satisfaction_score", "age_group", "churned"
    ]
    contracts = ["Month-to-Month", "One-Year", "Two-Year"]
    payments = ["Credit_Card", "Bank_Transfer", "E-Wallet", "Auto_Debit"]
    age_groups = ["18-25", "26-35", "36-45", "46-55", "56+"]
    rows = []
    for i in range(1, 1001):
        contract = random.choices(contracts, weights=[50, 30, 20])[0]
        tenure = max(1, int(random.gauss({"Month-to-Month":15,"One-Year":30,"Two-Year":48}[contract], 12)))
        monthly = round(max(20, random.gauss(70, 25)), 2)
        total = round(monthly * tenure * random.gauss(1.0, 0.05), 2)
        tickets = max(0, int(random.gauss(2, 3)))
        usage = round(max(0.5, random.gauss(15, 8)), 2)
        n_products = random.randint(1, 5)
        premium = 1 if random.random() < 0.3 else 0
        satisfaction = max(1, min(5, int(random.gauss(3.5, 1.0))))
        logit = (-1.5 + 1.0*(1 if contract=="Month-to-Month" else 0)
                 - 0.5*(1 if contract=="Two-Year" else 0)
                 - 0.02*tenure + 0.01*monthly + 0.15*tickets
                 - 0.1*n_products - 0.3*premium - 0.3*(satisfaction-3))
        churned = 1 if random.random() < 1/(1+math.exp(-logit)) else 0
        row = [i, tenure, monthly, total, contract, random.choice(payments),
               tickets, usage, n_products, premium, satisfaction,
               random.choice(age_groups), churned]
        inject_missing(row, [10, 3], rate=0.02)
        rows.append(row)
    return write_csv("ecommerce/customer_churn.csv", headers, rows)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 65)
    print("DataAgentBench — Full Seed Dataset Regeneration")
    print("=" * 65)
    
    results = {}
    
    print("\n--- PART A: sklearn-inspired synthetic datasets ---")
    results["scientific/iris_synthetic.csv"] = gen_iris()
    results["scientific/wine_synthetic.csv"] = gen_wine()
    results["biomedical/breast_cancer_synthetic.csv"] = gen_breast_cancer()
    results["biomedical/diabetes_synthetic.csv"] = gen_diabetes()
    results["finance/california_housing_synthetic.csv"] = gen_california_housing()
    
    print("\n--- PART B: Original synthetic datasets (re-seeded) ---")
    results["ecommerce/orders_v2.csv"] = gen_orders()
    results["ecommerce/user_sessions_v2.csv"] = gen_user_sessions()
    results["finance/transactions_v2.csv"] = gen_transactions()
    results["scientific/lab_experiment_v2.csv"] = gen_lab_experiment()
    results["scientific/weather_stations_v2.csv"] = gen_weather()
    
    print("\n--- PART C: New domain-expansion datasets ---")
    results["finance/loan_defaults.csv"] = gen_loan_defaults()
    results["finance/stock_portfolio.csv"] = gen_stock_portfolio()
    results["biomedical/patient_readmission.csv"] = gen_patient_readmission()
    results["biomedical/drug_response.csv"] = gen_drug_response()
    results["ecommerce/ad_campaigns.csv"] = gen_ad_campaigns()
    results["ecommerce/customer_churn.csv"] = gen_customer_churn()
    
    print("\n" + "=" * 65)
    total_rows = sum(r[0] for r in results.values())
    print(f"Generated {len(results)} datasets, {total_rows:,} total rows")
    print("=" * 65)
