'use client'
import { useState, useRef, useEffect } from 'react'
import { sendChatMessage } from '@/lib/api'
import { usePortfolioStore } from '@/store/portfolioStore'

interface TradeResult { ticker: string; side: string; quantity: number; price: number; success: boolean; error?: string }
interface WatchlistResult { ticker: string; action: string; success: boolean }
interface Message { id: string; role: 'user' | 'assistant'; content: string; trades?: TradeResult[]; watchlistChanges?: WatchlistResult[] }

export default function ChatPanel({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const [messages, setMessages] = useState<Message[]>([
    { id: '0', role: 'assistant', content: 'Hello! I\'m FinAlly, your AI trading assistant. I can analyze your portfolio, suggest trades, and execute them for you. What would you like to explore?' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const refresh = usePortfolioStore((s) => s.refresh)

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages])
  async function send() {
    const msg = input.trim()
    if (!msg || loading) return
    setInput('')
    setMessages((prev) => [...prev, { id: String(Date.now()), role: 'user', content: msg }])
    setLoading(true)
    try {
      const resp = await sendChatMessage(msg)
      setMessages((prev) => [...prev, {
        id: String(Date.now() + 1),
        role: 'assistant',
        content: resp.message,
        trades: resp.trades_executed,
        watchlistChanges: resp.watchlist_changes,
      }])
      if ((resp.trades_executed?.length ?? 0) > 0 || (resp.watchlist_changes?.length ?? 0) > 0) await refresh()
    } catch {
      setMessages((prev) => [...prev, { id: String(Date.now()), role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' }])
    } finally { setLoading(false) }
  }

  if (collapsed) {
    return (
      <button onClick={onToggle} style={{ width: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#161b22', borderLeft: '1px solid #30363d', border: 'none', cursor: 'pointer', color: '#8b949e', flexShrink: 0 }}>
        <span style={{ writingMode: 'vertical-rl', fontSize: 11, transform: 'rotate(180deg)' }}>AI Chat</span>
      </button>
    )
  }
  return (
    <div style={{ width: 300, display: 'flex', flexDirection: 'column', flexShrink: 0, borderLeft: '1px solid #30363d', backgroundColor: '#161b22' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', borderBottom: '1px solid #30363d', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 'bold', color: '#ecad0a' }}>AI Assistant</span>
          <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, backgroundColor: '#753991', color: '#fff' }}>FinAlly</span>
        </div>
        <button onClick={onToggle} style={{ fontSize: 16, color: '#8b949e', background: 'none', border: 'none', cursor: 'pointer', lineHeight: 1 }}>&times;</button>
      </div>
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {messages.map((msg) => (
          <div key={msg.id} style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start', gap: 4 }}>
            <div style={{ maxWidth: '90%', padding: '8px 12px', borderRadius: 8, fontSize: 12, lineHeight: 1.5, backgroundColor: msg.role === 'user' ? '#753991' : '#21262d', color: '#e6edf3' }}>{msg.content}</div>
            {msg.trades?.map((t, i) => (
              <div key={i} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, maxWidth: '90%', backgroundColor: t.success ? '#1a3a2a' : '#3a1a1a', color: t.success ? '#3fb950' : '#f85149', border: '1px solid' + (t.success ? ' #3fb950' : ' #f85149') }}>
                {t.success ? '✓' : '✗'} {t.side?.toUpperCase()} {t.quantity} {t.ticker} @ {t.price != null ? '$' + t.price.toFixed(2) : '?'}
              </div>
            ))}
            {msg.watchlistChanges?.map((w, i) => (
              <div key={i} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, maxWidth: '90%', backgroundColor: '#1a2a3a', color: '#209dd7', border: '1px solid #209dd7' }}>
                {w.success ? '✓' : '✗'} Watchlist: {w.action} {w.ticker}
              </div>
            ))}
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'flex-start' }}>
            <div style={{ padding: '8px 12px', borderRadius: 8, backgroundColor: '#21262d', color: '#8b949e', fontSize: 12 }}>FinAlly is thinking...</div>
          </div>
        )}
      </div>
      <div style={{ padding: '10px', borderTop: '1px solid #30363d', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <input style={{ flex: 1, padding: '6px 10px', fontSize: 12, borderRadius: 4, backgroundColor: '#0d1117', border: '1px solid #30363d', color: '#e6edf3', outline: 'none' }} placeholder='Ask FinAlly...' value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()} disabled={loading} />
          <button onClick={send} disabled={loading} style={{ padding: '6px 14px', fontSize: 12, borderRadius: 4, fontWeight: 'bold', backgroundColor: '#753991', color: '#fff', border: 'none', cursor: loading ? 'default' : 'pointer', opacity: loading ? 0.5 : 1 }}>Send</button>
        </div>
      </div>
    </div>
  )
}
