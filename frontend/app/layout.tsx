import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'FinAlly — AI Trading Workstation',
  description: 'AI-powered trading workstation with live market data',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang='en'>
      <body style={{ margin: 0, padding: 0, height: '100vh', overflow: 'hidden', backgroundColor: '#0d1117' }}>
        {children}
      </body>
    </html>
  )
}
