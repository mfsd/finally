'use client'
import { create } from 'zustand'
import { getPortfolio, getPortfolioHistory } from '@/lib/api'

export interface Position {
  ticker: string
  quantity: number
  avg_cost: number
  current_price: number
  unrealized_pnl: number
  pnl_pct: number
  daily_change_pct: number
}

interface PortfolioStore {
  cashBalance: number
  positions: Position[]
  totalValue: number
  totalPnl: number
  totalPnlPct: number
  history: { total_value: number; recorded_at: string }[]
  loading: boolean
  refresh: () => Promise<void>
  refreshHistory: () => Promise<void>
}

export const usePortfolioStore = create<PortfolioStore>((set) => ({
  cashBalance: 10000,
  positions: [],
  totalValue: 10000,
  totalPnl: 0,
  totalPnlPct: 0,
  history: [],
  loading: false,

  async refresh() {
    set({ loading: true })
    try {
      const data = await getPortfolio()
      set({
        cashBalance: data.cash_balance,
        positions: data.positions ?? [],
        totalValue: data.total_value,
        totalPnl: data.total_pnl,
        totalPnlPct: data.total_pnl_pct,
        loading: false,
      })
    } catch {
      set({ loading: false })
    }
  },

  async refreshHistory() {
    try {
      const data = await getPortfolioHistory()
      set({ history: data.history ?? [] })
    } catch { /* silent */ }
  },
}))
