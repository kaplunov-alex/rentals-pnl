import { Routes, Route, NavLink } from 'react-router-dom'
import ReviewPage from './pages/ReviewPage'
import DashboardPage from './pages/DashboardPage'
import SettingsPage from './pages/SettingsPage'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `block px-4 py-2 rounded-lg font-medium transition-colors ${
    isActive ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
  }`

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-6">
        <span className="font-bold text-lg text-gray-800">Rental P&amp;L</span>
        <nav className="flex gap-2">
          <NavLink to="/" end className={navClass}>Review</NavLink>
          <NavLink to="/dashboard" className={navClass}>Dashboard</NavLink>
          <NavLink to="/settings" className={navClass}>Settings</NavLink>
        </nav>
      </header>
      <main className="flex-1 p-4 max-w-7xl mx-auto w-full">
        <Routes>
          <Route path="/" element={<ReviewPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}
