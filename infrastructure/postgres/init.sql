-- Portfolio Optimizer — initial schema
-- Designed for Phase 2 auth from day 1:
--   user_id column exists but is nullable until the auth layer is added.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── portfolios ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolios (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Nullable until Phase 2 auth is added.
    -- Phase 2: add users table + FK constraint below.
    user_id     UUID        NULL,

    name        TEXT        NOT NULL,

    -- Array of {ticker, shares, fee_per_trade}
    holdings    JSONB       NOT NULL DEFAULT '[]',

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Phase 2: uncomment when auth is implemented ───────────────────────────────
-- CREATE TABLE IF NOT EXISTS users (
--     id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
--     email      TEXT        UNIQUE NOT NULL,
--     created_at TIMESTAMPTZ NOT NULL DEFAULT now()
-- );
--
-- ALTER TABLE portfolios
--     ADD CONSTRAINT fk_portfolios_user
--     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
