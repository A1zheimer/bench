-- Employee salary analysis schema
-- Database: PostgreSQL 14+

CREATE TABLE departments (
    dept_id     SERIAL PRIMARY KEY,
    dept_name   VARCHAR(100) NOT NULL,
    location    VARCHAR(100)
);

CREATE TABLE employees (
    emp_id      SERIAL PRIMARY KEY,
    emp_name    VARCHAR(100) NOT NULL,
    dept_id     INT REFERENCES departments(dept_id),
    salary      DECIMAL(10,2) NOT NULL,
    hire_date   DATE NOT NULL,
    job_title   VARCHAR(100)
);

-- Sample data
INSERT INTO departments VALUES
(1, 'Engineering', 'San Francisco'),
(2, 'Marketing', 'New York'),
(3, 'Finance', 'Chicago');

INSERT INTO employees VALUES
(1,  'Alice Chen',    1, 125000, '2019-03-01', 'Senior Engineer'),
(2,  'Bob Kumar',     1, 98000,  '2021-06-15', 'Engineer'),
(3,  'Carol Liu',     1, 125000, '2020-01-10', 'Senior Engineer'),
(4,  'David Park',    1, 145000, '2018-08-20', 'Lead Engineer'),
(5,  'Eve Santos',    2, 85000,  '2022-02-14', 'Marketing Analyst'),
(6,  'Frank Wu',      2, 95000,  '2020-09-01', 'Senior Analyst'),
(7,  'Grace Kim',     2, 85000,  '2021-11-30', 'Marketing Analyst'),
(8,  'Hank Jones',    3, 110000, '2019-07-15', 'Financial Analyst'),
(9,  'Iris Patel',    3, 130000, '2017-04-01', 'Senior Analyst'),
(10, 'Jake Brown',    3, 110000, '2020-03-20', 'Financial Analyst');

-- Target queries:
-- Query 1: RANK and DENSE_RANK by salary within department
-- SELECT emp_name, dept_id, salary,
--        RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC) AS salary_rank,
--        DENSE_RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC) AS salary_dense_rank
-- FROM employees;

-- Query 2: PERCENT_RANK within department
-- SELECT emp_name, dept_id, salary,
--        ROUND(PERCENT_RANK() OVER (PARTITION BY dept_id ORDER BY salary)::NUMERIC, 4) AS pct_rank
-- FROM employees;

-- Query 3: Running salary total by dept ordered by hire_date
-- SELECT emp_name, dept_id, hire_date, salary,
--        SUM(salary) OVER (PARTITION BY dept_id ORDER BY hire_date) AS running_total
-- FROM employees;
