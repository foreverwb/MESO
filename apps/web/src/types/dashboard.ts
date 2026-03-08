export type ApiMeta = {
  count?: number;
  limit?: number;
  trade_date?: string;
  symbol?: string;
  lookback_days?: number;
};

export type ApiErrorPayload = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};

export type ApiResponse<T> = {
  data: T | null;
  meta: ApiMeta;
  error: ApiErrorPayload | null;
};

export type FiltersPayload = {
  event_statuses: string[];
  quadrants: string[];
  signal_labels: string[];
  probability_tiers: string[];
  default_date_group_size_days: number;
  default_filters: {
    earnings_regimes: string[];
    quadrants: string[];
    probability_tiers: string[];
    min_trade_count: number;
  };
  highlight_rules: {
    default_signal_label: string;
    emphasis_probability_tier: string;
    highlight_quadrants: string[];
  };
};

export type DateGroupSummary = {
  trade_date: string;
  total_signals: number;
  directional_count: number;
  directional_symbols: string[];
  volatility_count: number;
  volatility_symbols: string[];
  neutral_count: number;
  watchlist_count: number;
};

export type TrendDirection = "up" | "down" | "mixed";

export type TrendConsistencyItem = {
  symbol: string;
  current_score: number;
  delta_3d: number;
  delta_5d: number;
  trend: TrendDirection;
};

export type TrendCategorySummary = {
  overlap: TrendConsistencyItem[];
  delta_3d: TrendConsistencyItem[];
  delta_5d: TrendConsistencyItem[];
};

export type TrendConsistencySummary = {
  trade_date: string;
  directional: TrendCategorySummary;
  volatility: TrendCategorySummary;
};

export type DeleteDateGroupResult = {
  trade_date: string;
  deleted_raw_rows: number;
  deleted_feature_rows: number;
  deleted_signal_rows: number;
  deleted_batch_count: number;
};

export type ChartPoint = {
  symbol: string;
  trade_date: string;
  x_score: number;
  y_score: number;
  bubble_size: number;
  quadrant: string;
  signal_label: string;
  s_conf: number | null;
  s_pers: number | null;
  highlight: boolean;
};

export type ShiftState = "none" | "pending" | "confirmed";

export type SignalRecord = {
  trade_date: string;
  symbol: string;
  batch_id: number;
  s_dir: number | null;
  s_vol: number | null;
  s_conf: number | null;
  s_pers: number | null;
  quadrant: string;
  signal_label: string;
  event_regime: string;
  prob_tier: string;
  is_watchlist: boolean;
  shift_state: ShiftState;
  median_s_dir: number | null;
  median_s_vol: number | null;
  delta_dir: number | null;
  delta_vol: number | null;
};

export type SymbolHistoryResponse = {
  symbol: string;
  lookback_days: number;
  items: SignalRecord[];
};

export type DirectionFilter = "all" | "bullish" | "bearish" | "watchlist";
export type SortOption = "confidence" | "persistence" | "symbol";

export type FilterState = {
  selectedDate: string;
  searchTerm: string;
  directionFilter: DirectionFilter;
  sortBy: SortOption;
};
