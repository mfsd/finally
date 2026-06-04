"use client";

import { ResponsiveTreeMap } from "@nivo/treemap";
import type { LivePosition } from "@/lib/types";
import { Panel } from "./Panel";

interface TreemapNode {
  name: string;
  value?: number;
  pnl?: number;
  children?: TreemapNode[];
}

function colorForPnl(node: TreemapNode) {
  const pnl = node.pnl ?? 0;
  if (pnl > 3) return "#16a34a";
  if (pnl > 0) return "#22c55e";
  if (pnl < -3) return "#dc2626";
  if (pnl < 0) return "#ef4444";
  return "#374151";
}

export function Heatmap({ positions, totalValue }: { positions: LivePosition[]; totalValue: number }) {
  const data: TreemapNode = {
    name: "portfolio",
    children: positions.map((position) => ({
      name: position.ticker,
      value: Math.max(position.market_value, 0.01),
      pnl: position.pnl_pct
    }))
  };

  return (
    <Panel
      title="Portfolio Map"
      testId="portfolio-heatmap"
      action={<span className="font-mono text-[11px] text-terminal-muted">{positions.length} holdings</span>}
    >
      <div className="h-[calc(100%-36px)] min-h-[180px]">
        {positions.length ? (
          <ResponsiveTreeMap
            data={data}
            identity="name"
            value="value"
            margin={{ top: 6, right: 6, bottom: 6, left: 6 }}
            label={(node) => `${node.id}`}
            labelSkipSize={32}
            labelTextColor="#f8fafc"
            parentLabelSize={0}
            borderColor="#111827"
            borderWidth={2}
            colors={(node) => colorForPnl(node.data as TreemapNode)}
            tooltip={({ node }) => {
              const datum = node.data as TreemapNode;
              const weight = totalValue > 0 && datum.value ? (datum.value / totalValue) * 100 : 0;
              return (
                <div className="border border-terminal-border bg-terminal-bg px-2 py-1 font-mono text-xs text-terminal-text">
                  {node.id}: {weight.toFixed(1)}% weight, {(datum.pnl ?? 0).toFixed(2)}% P&L
                </div>
              );
            }}
            theme={{ labels: { text: { fontFamily: "ui-monospace, monospace", fontSize: 12, fontWeight: 700 } } }}
          />
        ) : (
          <div className="flex h-full items-center justify-center font-mono text-sm text-terminal-muted">No holdings for map.</div>
        )}
      </div>
    </Panel>
  );
}
