CREATE TABLE IF NOT EXISTS quant_factor_config (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy     TEXT NOT NULL,
  factor_name  TEXT NOT NULL,
  weight       NUMERIC NOT NULL,
  updated_by   UUID REFERENCES auth.users(id),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (strategy, factor_name)
);

COMMENT ON TABLE quant_factor_config IS
  'User-adjustable factor weights. Overrides config.py defaults when populated.';
