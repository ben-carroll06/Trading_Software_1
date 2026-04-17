import React, { useEffect, useMemo, useState } from "react";
import "./FactorRanking.css";

interface QuantStock {
  rank: number;
  symbol: string;
  name: string;
  sector: string;
  composite_score: number;
  price: number;
  market_cap: number | null;
  missing_factor_count: number;
  factor_scores: Record<string, number | null>;
  factor_zscores: Record<string, number | null>;
}

interface RankingsResponse {
  strategy: string;
  run_timestamp: string;
  universe_size: number;
  returned: number;
  factor_coverage: Record<string, number>;
  rankings: QuantStock[];
}

interface StrategiesResponse {
  strategies: string[];
}

interface UniverseResponse {
  sectors: Record<string, { name: string; stocks: Array<{ ticker: string; name: string }> }>;
}

interface SortableFactor {
  key: string;
  weight: number;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

const STRATEGY_WEIGHTS: Record<string, Record<string, number>> = {
  default: {
    pe_ratio: 0.08,
    pb_ratio: 0.07,
    peg_ratio: 0.05,
    dividend_yield: 0.05,
    return_1m: 0.05,
    return_3m: 0.07,
    return_6m: 0.08,
    return_12m_skip1: 0.05,
    roe: 0.07,
    roa: 0.05,
    debt_to_equity: 0.05,
    current_ratio: 0.04,
    gross_margin: 0.04,
    operating_margin: 0.05,
    revenue_growth: 0.03,
    earnings_growth: 0.02,
    rsi: 0.08,
    week52_position: 0.07,
  },
  value_tilt: {
    pe_ratio: 0.20,
    pb_ratio: 0.20,
    peg_ratio: 0.15,
    dividend_yield: 0.15,
    roe: 0.10,
    debt_to_equity: 0.10,
    rsi: 0.10,
  },
  momentum_tilt: {
    return_1m: 0.10,
    return_3m: 0.20,
    return_6m: 0.25,
    return_12m_skip1: 0.15,
    rsi: 0.15,
    week52_position: 0.15,
  },
  quality_tilt: {
    roe: 0.20,
    roa: 0.15,
    gross_margin: 0.15,
    operating_margin: 0.15,
    revenue_growth: 0.15,
    earnings_growth: 0.10,
    debt_to_equity: 0.10,
  },
};

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Error caught by boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="quant-error-boundary">
          <h2>Something went wrong</h2>
          <p>We could not render factor rankings. Please refresh and try again.</p>
          <button onClick={() => window.location.reload()} className="quant-btn-primary">
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

const formatMarketCap = (marketCap: number | null): string => {
  if (marketCap == null) {
    return "-";
  }
  if (marketCap >= 1_000_000_000_000) {
    return `${(marketCap / 1_000_000_000_000).toFixed(2)}T`;
  }
  if (marketCap >= 1_000_000_000) {
    return `${(marketCap / 1_000_000_000).toFixed(2)}B`;
  }
  if (marketCap >= 1_000_000) {
    return `${(marketCap / 1_000_000).toFixed(2)}M`;
  }
  return marketCap.toFixed(0);
};

function FactorRankingContent() {
  const [strategies, setStrategies] = useState<string[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [strategy, setStrategy] = useState("default");
  const [sector, setSector] = useState("all");
  const [topN, setTopN] = useState(20);
  const [rankingsData, setRankingsData] = useState<RankingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleFactors, setVisibleFactors] = useState<string[]>([]);

  const weightedFactors = useMemo(() => {
    const weights = STRATEGY_WEIGHTS[strategy] || STRATEGY_WEIGHTS.default;
    return Object.entries(weights)
      .map(([key, weight]): SortableFactor => ({ key, weight }))
      .sort((a, b) => b.weight - a.weight)
      .map((entry) => entry.key);
  }, [strategy]);

  useEffect(() => {
    setVisibleFactors(weightedFactors.slice(0, 5));
  }, [weightedFactors]);

  useEffect(() => {
    let mounted = true;

    const fetchStrategies = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/quant/strategies`);
        if (!res.ok) {
          throw new Error(`Failed to fetch strategies: ${res.status}`);
        }
        const json: StrategiesResponse = await res.json();
        if (mounted) {
          setStrategies(json.strategies);
          if (!json.strategies.includes(strategy) && json.strategies.length > 0) {
            setStrategy(json.strategies[0]);
          }
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Failed to fetch strategies");
        }
      }
    };

    const fetchSectors = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/equities/universe`);
        if (!res.ok) {
          throw new Error(`Failed to fetch sectors: ${res.status}`);
        }
        const json: UniverseResponse = await res.json();
        const sectorNames = Object.values(json.sectors || {}).map((entry) => entry.name);
        if (mounted) {
          setSectors(Array.from(new Set(sectorNames)).sort());
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Failed to fetch sectors");
        }
      }
    };

    fetchStrategies();
    fetchSectors();

    return () => {
      mounted = false;
    };
  }, [strategy]);

  useEffect(() => {
    let mounted = true;

    const fetchRankings = async () => {
      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams();
        params.set("strategy", strategy);
        params.set("top_n", String(topN));
        if (sector !== "all") {
          params.set("sector", sector);
        }

        const res = await fetch(`${API_BASE_URL}/quant/rankings?${params.toString()}`);
        if (!res.ok) {
          throw new Error(`Failed to fetch rankings: ${res.status}`);
        }

        const json: RankingsResponse = await res.json();
        if (mounted) {
          setRankingsData(json);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Failed to fetch rankings");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    fetchRankings();

    return () => {
      mounted = false;
    };
  }, [strategy, sector, topN]);

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      setError(null);

      const res = await fetch(`${API_BASE_URL}/quant/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy }),
      });

      if (!res.ok) {
        throw new Error(`Refresh failed: ${res.status}`);
      }

      const params = new URLSearchParams();
      params.set("strategy", strategy);
      params.set("top_n", String(topN));
      if (sector !== "all") {
        params.set("sector", sector);
      }

      const rankingsRes = await fetch(`${API_BASE_URL}/quant/rankings?${params.toString()}`);
      if (!rankingsRes.ok) {
        throw new Error(`Failed to fetch rankings after refresh: ${rankingsRes.status}`);
      }

      const json: RankingsResponse = await rankingsRes.json();
      setRankingsData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  };

  const handleExport = () => {
    const params = new URLSearchParams();
    params.set("strategy", strategy);
    if (sector !== "all") {
      params.set("sector", sector);
    }
    window.open(`${API_BASE_URL}/quant/rankings/export?${params.toString()}`, "_blank");
  };

  const toggleVisibleFactor = (factorName: string) => {
    setVisibleFactors((prev) => {
      if (prev.includes(factorName)) {
        return prev.filter((name) => name !== factorName);
      }
      if (prev.length >= 8) {
        return prev;
      }
      return [...prev, factorName];
    });
  };

  const formattedUpdatedAt = useMemo(() => {
    if (!rankingsData?.run_timestamp) {
      return "-";
    }
    return new Date(rankingsData.run_timestamp).toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }, [rankingsData?.run_timestamp]);

  const rows = rankingsData?.rankings || [];
  const q1CutoffIndex = Math.floor(rows.length / 4);
  const q3CutoffIndex = Math.ceil((rows.length * 3) / 4);

  return (
    <div className="factor-ranking-page">
      <div className="factor-ranking-header">
        <h1>Daily Top Opportunities</h1>
        <p>Multi-factor rankings across the ISMF universe.</p>
      </div>

      <div className="factor-controls-grid">
        <label className="control-item">
          <span>Strategy</span>
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            {strategies.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <label className="control-item">
          <span>Sector</span>
          <select value={sector} onChange={(e) => setSector(e.target.value)}>
            <option value="all">All Sectors</option>
            {sectors.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <label className="control-item slider-item">
          <span>Top {topN} stocks</span>
          <input
            type="range"
            min={5}
            max={49}
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value))}
          />
        </label>

        <div className="control-actions">
          <button className="quant-btn-secondary" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
          <button className="quant-btn-primary" onClick={handleExport}>
            Export CSV
          </button>
        </div>
      </div>

      <div className="factor-column-toggle">
        <span>Visible factor z-scores:</span>
        <div className="factor-chip-row">
          {weightedFactors.map((factorName) => (
            <button
              key={factorName}
              type="button"
              className={`factor-chip ${visibleFactors.includes(factorName) ? "active" : ""}`}
              onClick={() => toggleVisibleFactor(factorName)}
            >
              {factorName}
            </button>
          ))}
        </div>
      </div>

      {rankingsData && (
        <div className="factor-meta-row">
          <div className="coverage-badges">
            {Object.entries(rankingsData.factor_coverage)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 4)
              .map(([factorName, coverage]) => (
                <span key={factorName} className="coverage-badge">
                  {factorName}: {(coverage * 100).toFixed(0)}%
                </span>
              ))}
          </div>
          <div className="last-updated">Last updated: {formattedUpdatedAt}</div>
        </div>
      )}

      {error && <div className="quant-error">{error}</div>}

      <div className="factor-table-wrap">
        <table className="factor-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Symbol</th>
              <th>Name</th>
              <th>Sector</th>
              <th>Composite Score</th>
              <th>Price ($)</th>
              <th>Market Cap</th>
              {visibleFactors.map((factorName) => (
                <th key={factorName}>{factorName}</th>
              ))}
              <th>Missing Data</th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: Math.min(topN, 8) }).map((_, idx) => (
                  <tr key={`skeleton-${idx}`} className="skeleton-row">
                    <td colSpan={8 + visibleFactors.length}>Loading rankings...</td>
                  </tr>
                ))
              : rows.map((stock, idx) => {
                  const scoreClass = idx < q1CutoffIndex ? "score-top" : idx >= q3CutoffIndex ? "score-bottom" : "";
                  return (
                    <tr key={stock.symbol}>
                      <td>{stock.rank}</td>
                      <td className="symbol-cell">{stock.symbol}</td>
                      <td>{stock.name}</td>
                      <td>{stock.sector}</td>
                      <td className={scoreClass}>{stock.composite_score.toFixed(2)}</td>
                      <td>{stock.price.toFixed(2)}</td>
                      <td>{formatMarketCap(stock.market_cap)}</td>
                      {visibleFactors.map((factorName) => {
                        const z = stock.factor_zscores?.[factorName];
                        return <td key={`${stock.symbol}-${factorName}`}>{z == null ? "-" : z.toFixed(2)}</td>;
                      })}
                      <td className={stock.missing_factor_count > 3 ? "missing-warning" : ""}>
                        {stock.missing_factor_count}
                      </td>
                    </tr>
                  );
                })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function FactorRanking() {
  return (
    <ErrorBoundary>
      <FactorRankingContent />
    </ErrorBoundary>
  );
}
