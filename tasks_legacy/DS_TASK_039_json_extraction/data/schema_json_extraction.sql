-- JSONB extraction schema
-- PostgreSQL 14+

CREATE TABLE event_log (
    event_id    BIGSERIAL PRIMARY KEY,
    event_time  TIMESTAMP NOT NULL DEFAULT NOW(),
    payload     JSONB NOT NULL
);

-- GIN index for fast JSONB queries
CREATE INDEX idx_event_payload ON event_log USING GIN (payload);

-- Sample events with nested JSONB payload
INSERT INTO event_log (event_time, payload) VALUES
('2024-01-15 10:23:45', '{
    "event_type": "purchase",
    "user": {"id": 1001, "email": "alice@mail.com", "tier": "premium"},
    "product": {"id": "P001", "name": "Laptop", "price": 1299.99, "category": "electronics"},
    "metadata": {"country": "US", "platform": "web", "session_id": "abc123"},
    "tags": ["new_customer", "high_value"]
}'),
('2024-01-15 10:31:22', '{
    "event_type": "view",
    "user": {"id": 1002, "email": "bob@mail.com", "tier": "standard"},
    "product": {"id": "P002", "name": "Mouse", "price": 49.99, "category": "electronics"},
    "metadata": {"country": "UK", "platform": "mobile", "session_id": "def456"},
    "tags": ["returning"]
}'),
('2024-01-15 11:05:33', '{
    "event_type": "purchase",
    "user": {"id": 1003, "email": "carol@mail.com", "tier": "premium"},
    "product": {"id": "P003", "name": "Chair", "price": 389.99, "category": "furniture"},
    "metadata": {"country": "US", "platform": "web", "session_id": "ghi789"},
    "tags": ["high_value", "loyalty"]
}'),
('2024-01-15 11:42:18', '{
    "event_type": "cart_add",
    "user": {"id": 1001, "email": "alice@mail.com", "tier": "premium"},
    "product": {"id": "P004", "name": "Desk", "price": 649.99, "category": "furniture"},
    "metadata": {"country": "US", "platform": "web", "session_id": "abc123"},
    "tags": []
}'),
('2024-01-15 12:15:00', '{
    "event_type": "purchase",
    "user": {"id": 1004, "email": "david@mail.com", "tier": "gold"},
    "product": {"id": "P005", "name": "Monitor", "price": 549.99, "category": "electronics"},
    "metadata": {"country": "CA", "platform": "web", "session_id": "jkl012"},
    "tags": ["loyalty", "repeat_buyer"]
}');

-- Required queries:
-- 1. Extract: SELECT payload->>'event_type', payload->'user'->>'email', (payload->'product'->>'price')::DECIMAL
-- 2. Count by event_type: GROUP BY payload->>'event_type'
-- 3. Filter US purchases: WHERE payload->'metadata'->>'country' = 'US' AND payload->>'event_type' = 'purchase'
-- 4. Unnest tags array: FROM event_log, jsonb_array_elements_text(payload->'tags') AS tag
-- 5. Containment: WHERE payload @> '{"user": {"tier": "premium"}}'
