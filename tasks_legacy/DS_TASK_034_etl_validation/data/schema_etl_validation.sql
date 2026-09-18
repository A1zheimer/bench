-- ETL Validation Schema
-- Simulates source and target tables for pipeline validation

CREATE TABLE customers (
    customer_id     INT PRIMARY KEY,
    customer_name   VARCHAR(100),
    email           VARCHAR(150)
);

CREATE TABLE source_transactions (
    txn_id          INT PRIMARY KEY,
    customer_id     INT,
    txn_date        DATE,
    amount          DECIMAL(12,2),
    currency        VARCHAR(3),
    status          VARCHAR(20),
    category        VARCHAR(50)
);

CREATE TABLE target_transactions_cleaned (
    txn_id          INT PRIMARY KEY,
    customer_id     INT,
    txn_date        DATE,
    amount_usd      DECIMAL(12,2),  -- converted to USD
    status          VARCHAR(20),
    category        VARCHAR(50),
    load_timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sample data: source has 15 rows, target has 13 (2 dropped), 1 value changed
INSERT INTO customers VALUES
(1, 'Alice', 'alice@mail.com'),
(2, 'Bob', 'bob@mail.com'),
(3, 'Carol', 'carol@mail.com'),
(99, 'Orphan Customer', 'orphan@mail.com');  -- not referenced in target

INSERT INTO source_transactions VALUES
(1001, 1, '2024-01-10', 500.00, 'USD', 'completed', 'retail'),
(1002, 2, '2024-01-11', 1200.00, 'EUR', 'completed', 'online'),
(1003, 3, '2024-01-12', 350.00, 'USD', 'pending', 'retail'),
(1004, 1, '2024-01-13', 800.00, 'USD', 'completed', 'wholesale'),
(1005, 2, '2024-01-14', 2500.00, 'GBP', 'completed', 'online'),
(1006, 3, '2024-01-15', 150.00, 'USD', 'failed', 'retail'),
(1007, 1, '2024-01-16', 950.00, 'USD', 'completed', 'wholesale'),
(1008, 2, '2024-01-17', 600.00, 'EUR', 'completed', 'online'),
(1009, 3, '2024-01-18', 420.00, 'USD', 'pending', 'retail'),
(1010, 1, '2024-01-19', 1100.00, 'USD', 'completed', 'wholesale'),
(1011, 2, '2024-01-20', 750.00, 'USD', 'completed', 'retail'),
(1012, 3, '2024-01-21', 280.00, 'USD', 'completed', 'retail'),
(1013, 1, '2024-01-22', 1850.00, 'EUR', 'completed', 'online'),
(1014, 99,'2024-01-23', 450.00, 'USD', 'completed', 'retail'),  -- orphan customer
(1015, 2, '2024-01-24', 920.00, 'USD', 'failed', 'retail');     -- dropped in ETL

-- Target: missing txn 1014 and 1015; txn 1002 has wrong amount
INSERT INTO target_transactions_cleaned VALUES
(1001, 1, '2024-01-10', 500.00, 'completed', 'retail', NOW()),
(1002, 2, '2024-01-11', 1100.00, 'completed', 'online', NOW()),  -- BUG: should be 1296.00 (EUR->USD)
(1003, 3, '2024-01-12', 350.00, 'pending', 'retail', NOW()),
(1004, 1, '2024-01-13', 800.00, 'completed', 'wholesale', NOW()),
(1005, 2, '2024-01-14', 3175.00, 'completed', 'online', NOW()),
(1006, 3, '2024-01-15', 150.00, 'failed', 'retail', NOW()),
(1007, 1, '2024-01-16', 950.00, 'completed', 'wholesale', NOW()),
(1008, 2, '2024-01-17', 648.00, 'completed', 'online', NOW()),
(1009, 3, '2024-01-18', 420.00, 'pending', 'retail', NOW()),
(1010, 1, '2024-01-19', 1100.00, 'completed', 'wholesale', NOW()),
(1011, 2, '2024-01-20', 750.00, 'completed', 'retail', NOW()),
(1012, 3, '2024-01-21', 280.00, 'completed', 'retail', NOW()),
(1013, 1, '2024-01-22', 2349.50, 'completed', 'online', NOW());
