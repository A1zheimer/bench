-- Multi-table join schema for e-commerce analytics
-- Database: PostgreSQL 14+

CREATE TABLE customers (
    customer_id     SERIAL PRIMARY KEY,
    customer_name   VARCHAR(100) NOT NULL,
    email           VARCHAR(150) UNIQUE NOT NULL,
    segment         VARCHAR(50) NOT NULL,  -- 'Premium', 'Standard', 'Budget'
    registration_date DATE NOT NULL,
    country         VARCHAR(50)
);

CREATE TABLE products (
    product_id      SERIAL PRIMARY KEY,
    product_name    VARCHAR(150) NOT NULL,
    category        VARCHAR(80) NOT NULL,
    unit_price      DECIMAL(10,2) NOT NULL,
    cost_price      DECIMAL(10,2) NOT NULL
);

CREATE TABLE orders (
    order_id        SERIAL PRIMARY KEY,
    customer_id     INT REFERENCES customers(customer_id),
    product_id      INT REFERENCES products(product_id),
    order_date      DATE NOT NULL,
    quantity        INT NOT NULL,
    discount_pct    DECIMAL(5,2) DEFAULT 0.00
);

-- Sample data
INSERT INTO customers VALUES
(1, 'Alice Johnson', 'alice@email.com', 'Premium', '2021-03-15', 'USA'),
(2, 'Bob Smith', 'bob@email.com', 'Standard', '2022-01-10', 'UK'),
(3, 'Carol White', 'carol@email.com', 'Budget', '2022-06-20', 'USA'),
(4, 'David Lee', 'david@email.com', 'Premium', '2020-11-05', 'Canada'),
(5, 'Eve Davis', 'eve@email.com', 'Standard', '2023-02-14', 'Australia');

INSERT INTO products VALUES
(1, 'Laptop Pro', 'Electronics', 1299.99, 800.00),
(2, 'Wireless Mouse', 'Electronics', 49.99, 15.00),
(3, 'Office Chair', 'Furniture', 389.99, 180.00),
(4, 'Standing Desk', 'Furniture', 649.99, 320.00),
(5, 'Monitor 27"', 'Electronics', 549.99, 280.00);

INSERT INTO orders VALUES
(1, 1, 1, '2024-01-10', 2, 0.00),
(2, 1, 5, '2024-01-15', 1, 5.00),
(3, 2, 2, '2024-01-12', 3, 0.00),
(4, 2, 3, '2024-01-18', 1, 0.00),
(5, 3, 2, '2024-01-08', 1, 0.00),
(6, 4, 4, '2024-01-20', 2, 10.00),
(7, 4, 1, '2024-01-22', 1, 5.00),
(8, 5, 3, '2024-01-25', 1, 0.00),
(9, 1, 4, '2024-01-28', 1, 0.00),
(10, 3, 5, '2024-01-30', 1, 0.00);

-- Target query structure:
-- SELECT c.segment,
--        SUM(o.quantity * p.unit_price * (1 - o.discount_pct/100)) AS total_revenue,
--        AVG(o.quantity * p.unit_price * (1 - o.discount_pct/100)) AS avg_order_value,
--        COUNT(DISTINCT c.customer_id) AS distinct_customers,
--        COUNT(o.order_id) AS total_orders,
--        ROUND(100.0 * SUM(...) / SUM(SUM(...)) OVER (), 2) AS revenue_pct
-- FROM orders o
-- JOIN customers c ON o.customer_id = c.customer_id
-- JOIN products p ON o.product_id = p.product_id
-- GROUP BY c.segment
-- ORDER BY total_revenue DESC;
