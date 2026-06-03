'use client'
import { create } from 'zustand'

export interface PriceData {
  price: number
  prevPrice: number
  sessionOpen: number
  direction: 'up' | 'down' | 'flat'
  timestamp: number
  history: number[]
}

type ConnectionStatus = 'connected' | 'reconnecting' | 'disconnected'

interface PriceStore {
  prices: Record<string, PriceData>
  status: ConnectionStatus
  lastMessageAt: number
  connect: () => void
  disconnect: () => void
}

let es: EventSource | null = null
let heartbeatTimer: ReturnType<typeof setInterval> | null = null

export const usePriceStore = create<PriceStore>((set, get) => ({
  prices: {},
  status: 'disconnected',
  lastMessageAt: 0,

  connect() {
    if (es) return
    const BASE = process.env.NEXT_PUBLIC_API_URL ?? ''
    es = new EventSource(`${BASE}/api/stream/prices`)

    es.onopen = () => set({ status: 'connected', lastMessageAt: Date.now() })

    es.onmessage = (event) => {
      const now = Date.now()
      set({ lastMessageAt: now, status: 'connected' })
      try {
        const d = JSON.parse(event.data)
        const { ticker, price, prev_price, session_open, timestamp, direction } = d
        set((state) => {
          const prev = state.prices[ticker]
          const history = prev ? [...prev.history.slice(-199), price] : [price]
          return {
            prices: {
              ...state.prices,
              [ticker]: {
                price,
                prevPrice: prev_price,
                sessionOpen: session_open,
                direction,
                timestamp,
                history,
              }
            }
          }
        })
      } catch { /* ignore malformed events */ }
    }

    es.onerror = () => {
      if (es?.readyState === EventSource.CONNECTING) {
        set({ status: 'reconnecting' })
      } else {
        set({ status: 'disconnected' })
        es = null
      }
    }

    heartbeatTimer = setInterval(() => {
      const { lastMessageAt, status } = get()
      if (status === 'connected' && Date.now() - lastMessageAt > 35000) {
        set({ status: 'disconnected' })
      }
    }, 5000)
  },

  disconnect() {
    es?.close()
    es = null
    if (heartbeatTimer) clearInterval(heartbeatTimer)
    heartbeatTimer = null
    set({ status: 'disconnected' })
  },
}))
