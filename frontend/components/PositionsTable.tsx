import { formatCurrency, formatNumber, formatPercent, pnlClass } from "@/lib/format";
import type { LivePosition } from "@/lib/types";
import { Panel } from "./Panel";

export function PositionsTable({ positions }: { positions: LivePosition[] }) {
  return (
    <Panel title="Positions" testId="positions-panel">
      <div className="terminal-scrollbar h-[calc(100%-36px)] overflow-auto">
        <table className="w-full border-collapse font-mono text-xs" data-testid="positions-table">
          <thead className="sticky top-0 bg-terminal-panel text-terminal-muted">
            <tr className="border-b border-terminal-border text-right uppercase">
              <th className="px-2 py-2 text-left">Ticker</th>
              <th className="px-2 py-2">Qty</th>
              <th className="px-2 py-2">Avg</th>
              <th className="px-2 py-2">Last</th>
              <th className="px-2 py-2">Value</th>
              <th className="px-2 py-2">P&L</th>
              <th className="px-2 py-2">%Chg</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position) => (
              <tr key={position.ticker} className="border-b border-terminal-border/70 text-right" data-testid={`position-row-${position.ticker}`}>
                <td className="px-2 py-2 text-left font-semibold text-white">{position.ticker}</td>
                <td className="px-2 py-2">{formatNumber(position.quantity, 4)}</td>
                <td className="px-2 py-2">{formatCurrency(position.avg_cost)}</td>
                <td className="px-2 py-2">{formatCurrency(position.current_price)}</td>
                <td className="px-2 py-2">{formatCurrency(position.market_value)}</td>
                <td className={`px-2 py-2 ${pnlClass(position.unrealized_pnl)}`}>{formatCurrency(position.unrealized_pnl)}</td>
                <td className={`px-2 py-2 ${pnlClass(position.pnl_pct)}`}>{formatPercent(position.pnl_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!positions.length && <div className="p-4 font-mono text-sm text-terminal-muted">No open positions.</div>}
      </div>
    </Panel>
  );
}
