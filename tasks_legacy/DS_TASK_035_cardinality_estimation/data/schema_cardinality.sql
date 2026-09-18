-- Cardinality estimation schema
-- Simulates a high-cardinality events table

CREATE TABLE events (
    event_id        BIGSERIAL PRIMARY KEY,
    user_session_id VARCHAR(36) NOT NULL,  -- UUID-like, high cardinality
    user_id         INT NOT NULL,
    event_type      VARCHAR(50) NOT NULL,  -- low cardinality: click, view, purchase, etc.
    page_url        TEXT,
    event_timestamp TIMESTAMP NOT NULL,
    device_type     VARCHAR(20),
    country_code    CHAR(2)
);

-- Synthetic data generation (for Python simulation)
-- Total rows: 100,000
-- Distinct user_session_ids: ~75,000 (each user may have multiple events per session,
--   and users may have multiple sessions)
-- Distinct user_ids: ~10,000
-- Distinct event_types: 5

-- Example rows:
INSERT INTO events (user_session_id, user_id, event_type, page_url, event_timestamp, device_type, country_code) VALUES
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 1001, 'view', '/products/laptop', '2024-01-15 10:23:45', 'desktop', 'US'),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 1001, 'click', '/products/laptop/buy', '2024-01-15 10:24:12', 'desktop', 'US'),
('b2c3d4e5-f6a7-8901-bcde-f12345678901', 1002, 'view', '/products/phone', '2024-01-15 10:25:00', 'mobile', 'UK'),
('c3d4e5f6-a7b8-9012-cdef-123456789012', 1003, 'purchase', '/checkout', '2024-01-15 10:26:30', 'desktop', 'CA'),
('d4e5f6a7-b8c9-0123-defa-234567890123', 1001, 'view', '/home', '2024-01-16 09:15:00', 'mobile', 'US');
-- ... 99,995 more rows in production

-- Exact distinct count query:
-- SELECT COUNT(DISTINCT user_session_id) FROM events;  -- Expected: ~75,000

-- Sampling approximation query (PostgreSQL):
-- SELECT COUNT(DISTINCT user_session_id) * 10 AS estimated_distinct
-- FROM (SELECT user_session_id FROM events TABLESAMPLE BERNOULLI(10)) sample;

-- EXPLAIN ANALYZE target:
-- EXPLAIN ANALYZE SELECT COUNT(DISTINCT user_session_id) FROM events;
