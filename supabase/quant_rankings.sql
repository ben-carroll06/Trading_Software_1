CREATE TABLE IF NOT EXISTS quant_rankings (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_date      DATE NOT NULL,
  strategy      TEXT NOT NULL DEFAULT 'default',
  rankings_json JSONB NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quant_rankings_date_strategy
  ON quant_rankings (run_date DESC, strategy);

COMMENT ON TABLE quant_rankings IS
  'Daily snapshots of quant factor rankings. Written by backend scoring engine.';
