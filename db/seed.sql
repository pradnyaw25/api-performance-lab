-- Identical to the in-memory seed: ids 1..10000, name item-{id},
-- price (id % 1000) + 0.99, tags [tag-{id % 7}, tag-{id % 13}], fixed created_at.
INSERT INTO items (id, name, price, tags, created_at)
SELECT i,
       'item-' || i,
       ((i % 1000) + 0.99)::double precision,
       ARRAY['tag-' || (i % 7), 'tag-' || (i % 13)],
       '2026-01-01T00:00:00Z'::timestamptz
FROM generate_series(1, 10000) AS i;
SELECT setval('items_id_seq', 10000);
ANALYZE items;
