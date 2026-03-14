import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { OverviewProvider } from './context/OverviewContext'
import { TransactionsProvider } from './context/TransactionsContext'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <OverviewProvider>
        <TransactionsProvider>
          <App />
        </TransactionsProvider>
      </OverviewProvider>
    </BrowserRouter>
  </StrictMode>,
)
