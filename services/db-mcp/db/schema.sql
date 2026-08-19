-- Schema for the payments table backing db-mcp's get_payment_failure_stats
-- tool. Kept intentionally small (one table) for a portfolio project's
-- scope — enough to make the "why did payment failures increase"
-- scenario realistic without building a full payments data model.

CREATE TABLE IF NOT EXISTS payments (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    service TEXT NOT NULL DEFAULT 'payment-service',
    status TEXT NOT NULL CHECK (status IN ('success', 'declined', 'gateway_error', 'validation_error')),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    failure_reason TEXT
);

-- The stats query filters by created_at range (always) and sometimes by
-- service; these indexes keep both paths reasonably fast even as the
-- table grows well past the seed script's volume.
CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments (created_at);
CREATE INDEX IF NOT EXISTS idx_payments_service ON payments (service);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments (status);
