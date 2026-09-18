-- Temporal query schema for sales analytics

CREATE TABLE daily_sales (
    sale_date       DATE PRIMARY KEY,
    daily_revenue   DECIMAL(12,2) NOT NULL,
    transaction_count INT NOT NULL,
    avg_order_value DECIMAL(10,2),
    channel         VARCHAR(20)  -- 'online', 'retail', 'wholesale'
);

-- Sample data: 30 days of sales
INSERT INTO daily_sales VALUES
('2024-01-01', 45200.00, 312, 144.87, 'online'),
('2024-01-02', 52300.00, 358, 146.09, 'retail'),
('2024-01-03', 48700.00, 335, 145.37, 'online'),
('2024-01-04', 61200.00, 421, 145.37, 'retail'),
('2024-01-05', 55800.00, 384, 145.31, 'online'),
('2024-01-06', 38200.00, 263, 145.25, 'retail'),
('2024-01-07', 41500.00, 285, 145.61, 'online'),
('2024-01-08', 58900.00, 405, 145.43, 'retail'),
('2024-01-09', 63400.00, 436, 145.41, 'online'),
('2024-01-10', 71200.00, 489, 145.60, 'retail'),
('2024-01-11', 66800.00, 459, 145.54, 'online'),
('2024-01-12', 82300.00, 566, 145.41, 'retail'),
('2024-01-13', 75600.00, 519, 145.66, 'online'),
('2024-01-14', 58400.00, 401, 145.64, 'retail'),
('2024-01-15', 22100.00, 152, 145.39, 'online'),  -- anomaly: very low
('2024-01-16', 68900.00, 473, 145.67, 'retail'),
('2024-01-17', 72400.00, 497, 145.67, 'online'),
('2024-01-18', 78200.00, 537, 145.62, 'retail'),
('2024-01-19', 83500.00, 573, 145.73, 'online'),
('2024-01-20', 91200.00, 626, 145.69, 'retail'),
('2024-01-21', 85700.00, 588, 145.75, 'online'),
('2024-01-22', 68300.00, 469, 145.63, 'retail'),
('2024-01-23', 74500.00, 511, 145.79, 'online'),
('2024-01-24', 79800.00, 548, 145.62, 'retail'),
('2024-01-25', 88600.00, 608, 145.72, 'online'),
('2024-01-26', 95400.00, 655, 145.65, 'retail'),
('2024-01-27', 102300.00, 702, 145.73, 'online'),
('2024-01-28', 97800.00, 671, 145.75, 'retail'),
('2024-01-29', 78200.00, 537, 145.62, 'online'),
('2024-01-30', 84700.00, 581, 145.78, 'retail');

-- Query 1: 7-day rolling average
-- SELECT sale_date, daily_revenue,
--        AVG(daily_revenue) OVER (ORDER BY sale_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_7day_avg
-- FROM daily_sales;

-- Query 2: Day of week analysis
-- SELECT EXTRACT(DOW FROM sale_date) AS day_of_week,
--        AVG(daily_revenue) AS avg_daily_revenue
-- FROM daily_sales
-- GROUP BY 1 ORDER BY 2 DESC;
