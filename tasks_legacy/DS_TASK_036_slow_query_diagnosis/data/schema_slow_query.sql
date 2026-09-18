-- Slow query diagnosis schema and EXPLAIN output
-- PostgreSQL 14

-- Schema
CREATE TABLE orders_large (
    order_id        BIGSERIAL PRIMARY KEY,
    customer_id     INT NOT NULL,
    order_date      DATE NOT NULL,
    status          VARCHAR(20) NOT NULL,  -- 'pending', 'completed', 'cancelled', 'refunded'
    total_amount    DECIMAL(12,2),
    shipping_country VARCHAR(50),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE customers_large (
    customer_id     INT PRIMARY KEY,
    email           VARCHAR(150),
    customer_tier   VARCHAR(20),  -- 'gold', 'silver', 'bronze'
    registration_date DATE
);

-- Existing indexes: ONLY the primary keys
-- Table sizes: orders_large = 5,000,000 rows, customers_large = 250,000 rows

-- Slow query being diagnosed:
-- SELECT c.customer_tier, COUNT(*) as order_count, SUM(o.total_amount) as revenue
-- FROM orders_large o
-- JOIN customers_large c ON o.customer_id = c.customer_id
-- WHERE o.order_date BETWEEN '2024-01-01' AND '2024-03-31'
--   AND o.status = 'completed'
-- GROUP BY c.customer_tier
-- ORDER BY revenue DESC;

-- EXPLAIN ANALYZE output (simulated for 5M row table):
/*
QUERY PLAN:
Sort  (cost=185420.12..185420.14 rows=3 width=48) (actual time=45821.234..45821.235 rows=3 loops=1)
  Sort Key: (sum(o.total_amount)) DESC
  Sort Method: quicksort  Memory: 25kB
  ->  HashAggregate  (cost=185420.05..185420.08 rows=3 width=48) (actual time=45821.221..45821.228 rows=3 loops=1)
        Group Key: c.customer_tier
        ->  Hash Join  (cost=7842.00..174938.44 rows=2096322 width=22) (actual time=124.832..44956.127 rows=312450 loops=1)
              Hash Cond: (o.customer_id = c.customer_id)
              ->  Seq Scan on orders_large o  (cost=0.00..159320.00 rows=2096322 width=18)
                                               (actual time=0.023..38942.441 rows=312450 loops=1)
                    Filter: ((order_date BETWEEN '2024-01-01' AND '2024-03-31') AND (status = 'completed'))
                    Rows Removed by Filter: 4687550
              ->  Hash  (cost=4342.00..4342.00 rows=250000 width=16) (actual time=124.791..124.793 rows=250000 loops=1)
                    Buckets: 262144  Batches: 1  Memory Usage: 14421kB
                    ->  Seq Scan on customers_large c  (cost=0.00..4342.00 rows=250000 width=16) (actual time=0.012..62.341 rows=250000 loops=1)
Planning Time: 1.234 ms
Execution Time: 45821.456 ms  -- 45.8 SECONDS!
*/

-- Task: Identify missing indexes and propose fixes
-- Proposed fix should include:
-- 1. CREATE INDEX on orders_large(order_date, status, customer_id, total_amount)
--    (composite covering index)
-- 2. Optionally: CREATE INDEX on customers_large(customer_tier)
-- After fix expected execution time: ~320ms (143x speedup)
