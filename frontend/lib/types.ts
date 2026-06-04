export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";

export interface MarketDataStatus {
  source: "massive" | "simulator" | "unknown";
  mode: "primary" | "fallback" | "free_eod" | "snapshot" | "unknown";
  label: string;
  description?: string;
}

export type PriceDirection = "up" | "down" | "flat";

export interface PriceEvent {
  ticker: string;
  price: number;
  prev_price: number;
  session_open: number;
  ts: number;
  direction: PriceDirection;
}

export interface ChartPoint {
  time: number;
  value: number;
}

export interface WatchlistItem {
  ticker: string;
  id?: string;
  added_at?: string;
  price?: number | null;
  prev_price?: number | null;
  session_open?: number | null;
  daily_change_pct?: number | null;
  quote?: PriceEvent | null;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price?: number | null;
  market_value?: number;
  unrealized_pl?: number;
  unrealized_pl_pct?: number;
  unrealized_pnl?: number;
  pnl_pct?: number;
  session_open?: number | null;
  daily_change_pct?: number | null;
  quote?: PriceEvent | null;
}

export interface LivePosition extends Position {
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  pnl_pct: number;
  daily_change_pct: number;
}

export interface PortfolioResponse {
  cash_balance: number;
  positions: Position[];
  total_value: number;
  positions_value?: number;
  unrealized_pl?: number;
  unrealized_pl_pct?: number;
  total_pnl?: number;
  total_pnl_pct?: number;
}

export interface PortfolioSnapshot {
  total_value: number;
  recorded_at: string;
}

export interface TradeRequest {
  ticker: string;
  quantity: number;
  side: "buy" | "sell";
}

export interface TradeAction {
  ticker: string;
  side: "buy" | "sell";
  quantity: number;
  success?: boolean;
  error?: string;
}

export interface WatchlistAction {
  ticker: string;
  action: "add" | "remove";
  success?: boolean;
  error?: string;
}

export interface ChatActions {
  trades?: TradeAction[];
  trades_executed?: TradeAction[];
  trades_failed?: TradeAction[];
  watchlist_changes?: WatchlistAction[];
}

export interface ChatResponse {
  message: string;
  trades?: TradeAction[];
  watchlist_changes?: WatchlistAction[];
  actions?: ChatActions;
  results?: Array<Record<string, unknown>>;
  errors?: Array<Record<string, unknown>>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions?: ChatActions;
  created_at: string;
}
