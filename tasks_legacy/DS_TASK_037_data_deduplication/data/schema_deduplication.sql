-- Data deduplication schema

CREATE TABLE customer_contacts (
    contact_id  SERIAL PRIMARY KEY,
    first_name  VARCHAR(50),
    last_name   VARCHAR(50),
    email       VARCHAR(150),
    phone       VARCHAR(20),
    city        VARCHAR(80),
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP
);

-- Sample data with duplicates
INSERT INTO customer_contacts (contact_id, first_name, last_name, email, phone, city, created_at) VALUES
(1,  'Alice',  'Johnson', 'alice@mail.com',  '555-0101', 'NYC',     '2023-01-10 08:00:00'),
(2,  'Alice',  'Johnson', 'alice@mail.com',  '555-0101', 'New York','2023-03-15 14:30:00'),  -- dup of 1
(3,  'Bob',    'Smith',   'bob@mail.com',    '555-0102', 'LA',      '2023-02-20 10:00:00'),
(4,  'Bob',    'Smith',   'bob@mail.com',    '555-0102', 'Los Ang.','2023-04-01 09:15:00'),  -- dup of 3
(5,  'Bob',    'Smith',   'bob@mail.com',    '555-0102', 'LA',      '2022-12-05 16:00:00'),  -- dup of 3
(6,  'Carol',  'White',   'carol@mail.com',  '555-0103', 'Chicago', '2023-01-25 11:00:00'),
(7,  'David',  'Lee',     'david@mail.com',  '555-0104', 'Houston', '2023-03-10 13:00:00'),
(8,  'David',  'Lee',     'david@mail.com',  '555-0104', 'Houston', '2023-05-20 15:45:00'),  -- dup of 7
(9,  'Eve',    'Davis',   'eve@mail.com',    '555-0105', 'Phoenix', '2023-02-14 09:00:00'),
(10, 'Frank',  'Wu',      'frank@mail.com',  '555-0106', 'Dallas',  '2023-04-30 10:30:00'),
(11, 'Grace',  'Kim',     'grace@mail.com',  '555-0107', 'Seattle', '2023-01-05 08:30:00'),
(12, 'Alice',  'Johnson', 'alice@mail.com',  '555-0108', 'NYC',     '2023-06-01 12:00:00'),  -- near-dup: same email, different phone
(13, 'Hank',   'Jones',   'hank@mail.com',   '555-0109', 'Boston',  '2023-03-22 14:00:00'),
(14, 'Iris',   'Patel',   'iris@mail.com',   '555-0110', 'Denver',  '2023-05-10 11:30:00'),
(15, 'Jake',   'Brown',   'jake@mail.com',   '555-0111', 'Miami',   '2023-04-15 16:00:00');

-- Expected: 4 exact duplicates (contact_ids 1, 3, 5, 7 are older copies to be removed)
-- Keep: 2, 4, 6, 7(-> keep 8), 9, 10, 11, 12, 13, 14, 15
-- Dedup query:
-- WITH ranked AS (
--   SELECT contact_id,
--          ROW_NUMBER() OVER (PARTITION BY email, phone ORDER BY created_at DESC) AS rn
--   FROM customer_contacts
-- )
-- SELECT contact_id FROM ranked WHERE rn > 1;  -- Returns duplicates to delete
