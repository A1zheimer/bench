-- Partition pruning schema and demonstration
-- PostgreSQL 14+

-- Original unpartitioned table (50M rows, slow)
CREATE TABLE sales_all (
    sale_id         BIGSERIAL PRIMARY KEY,
    sale_date       DATE NOT NULL,
    customer_id     INT NOT NULL,
    product_id      INT NOT NULL,
    amount          DECIMAL(12,2) NOT NULL,
    region          VARCHAR(50),
    channel         VARCHAR(30)
);

-- Slow query (full table scan on 50M rows):
-- SELECT region, SUM(amount) as total_sales
-- FROM sales_all
-- WHERE sale_date BETWEEN '2024-01-01' AND '2024-03-31'
-- GROUP BY region;
-- Estimated cost: ~850,000 (seq scan all 50M rows)

-- Partitioned version
CREATE TABLE sales_partitioned (
    sale_id         BIGINT NOT NULL,
    sale_date       DATE NOT NULL,
    customer_id     INT NOT NULL,
    product_id      INT NOT NULL,
    amount          DECIMAL(12,2) NOT NULL,
    region          VARCHAR(50),
    channel         VARCHAR(30)
) PARTITION BY RANGE (sale_date);

-- Monthly partitions for 2024
CREATE TABLE sales_2024_01 PARTITION OF sales_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE sales_2024_02 PARTITION OF sales_partitioned
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

CREATE TABLE sales_2024_03 PARTITION OF sales_partitioned
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');

CREATE TABLE sales_2024_04 PARTITION OF sales_partitioned
    FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');

CREATE TABLE sales_2024_05 PARTITION OF sales_partitioned
    FOR VALUES FROM ('2024-05-01') TO ('2024-06-01');

CREATE TABLE sales_2024_06 PARTITION OF sales_partitioned
    FOR VALUES FROM ('2024-06-01') TO ('2024-07-01');

-- Default partition for out-of-range dates
CREATE TABLE sales_default PARTITION OF sales_partitioned DEFAULT;

-- Fast query with partition pruning (only scans Q1 partitions = 3/6 partitions):
-- SELECT region, SUM(amount) as total_sales
-- FROM sales_partitioned
-- WHERE sale_date BETWEEN '2024-01-01' AND '2024-03-31'
-- GROUP BY region;
-- With pruning: only sales_2024_01, sales_2024_02, sales_2024_03 are scanned
-- Estimated cost after pruning: ~145,000 (6x improvement)

-- EXPLAIN output comparison (simulated):
-- Without partitioning: Seq Scan on sales_all (cost=0..1250000) rows=50000000
-- With partitioning + pruning: Append -> 3 Seq Scans each ~8333333 rows
--   Partitions scanned: 3 of 7
