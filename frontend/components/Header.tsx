import { Activity, Database, Wallet } from "lucide-react";
import { formatCurrency, formatPercent, pnlClass } from "@/lib/format";
import type { ConnectionStatus, MarketDataStatus } from "@/lib/types";

const statusColor: Record<ConnectionStatus, string> = {
  connected: "bg-ally-green",
  reconnecting: "bg-ally-yellow",
  disconnected: "bg-ally-red"
};

export function Header({
  status,
  cash,
  total,
  pnl,
  marketData
}: {
  status: ConnectionStatus;
  cash: number;
  total: number;
  pnl: number;
  marketData: MarketDataStatus;
}) {
  const dataSourceClass = marketData.mode === "fallback" ? "text-ally-yellow" : marketData.source === "massive" ? "text-ally-green" : "text-terminal-muted";

  return (
    <header className="flex h-14 items-center justify-between border-b border-terminal-border bg-terminal-panel2 px-4">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center border border-ally-yellow text-ally-yellow">
          <Activity size={16} />
        </div>
        <div>
          <div className="font-mono text-lg font-semibold leading-5 text-white">FinAlly</div>
          <div className="font-mono text-[11px] uppercase text-terminal-muted">AI Trading Workstation</div>
        </div>
      </div>
      <div className="flex items-center gap-6 font-mono text-sm">
        <div>
          <span className="mr-2 text-terminal-muted">Portfolio</span>
          <span className="text-lg text-white">{formatCurrency(total)}</span>
        </div>
        <div className={pnlClass(pnl)}>
          <span className="mr-2 text-terminal-muted">P&L</span>
          {formatCurrency(pnl)} <span className="text-xs">{formatPercent(total ? (pnl / total) * 100 : 0)}</span>
        </div>
        <div className="flex items-center gap-2 text-terminal-text" data-testid="cash-balance" aria-label="Cash balance">
          <Wallet size={15} className="text-ally-blue" />
          <span className="text-terminal-muted">Cash</span>
          <span>{formatCurrency(cash)}</span>
        </div>
        <div className="flex items-center gap-2 text-xs uppercase text-terminal-muted" data-testid="market-data-source" aria-label="Market data source">
          <Database size={14} className={dataSourceClass} />
          <span className={dataSourceClass}>{marketData.label}</span>
        </div>
        <div className="flex items-center gap-2 text-xs uppercase text-terminal-muted" data-testid="connection-status" role="status" aria-label="Market stream connection">
          <span className={`h-2.5 w-2.5 rounded-full ${statusColor[status]}`} />
          {status}
        </div>
      </div>
    </header>
  );
}
