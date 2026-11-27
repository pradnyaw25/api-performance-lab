-- Same shape as the in-memory store in every implementation.
DROP TABLE IF EXISTS items;
CREATE TABLE items (
    id         bigserial PRIMARY KEY,
    name       text NOT NULL,
    price      double precision NOT NULL,
    tags       text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
