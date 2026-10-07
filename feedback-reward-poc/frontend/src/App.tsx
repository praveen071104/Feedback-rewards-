import { Route, Routes, Navigate, Link, useLocation } from 'react-router-dom'
import { ArrowLeft, LogIn } from 'lucide-react'
import CustomerPage from './pages/CustomerPage'
import StaffPage from './pages/StaffPage'

export default function App() {
  const location = useLocation()
  const isStaff = location.pathname.startsWith('/staff')

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-mns-navy text-white border-b-2 border-mns-gold">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to={isStaff ? '/staff' : '/'} className="flex items-center gap-3">
            <img src="/mands-logo.svg" alt="Marks & Spencer" className="h-7 w-[70px] brightness-0 invert" />
            <span className="h-6 w-px bg-white/25 hidden sm:block" />
            <span className="text-xs uppercase tracking-[0.2em] text-mns-gold/90 hidden sm:inline">
              {isStaff ? 'Store Colleague Hub' : 'Customer Feedback'}
            </span>
          </Link>
          <Link
            to={isStaff ? '/' : '/staff'}
            className="inline-flex h-9 items-center gap-2 px-2 text-sm font-medium text-white/90 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mns-gold"
          >
            {isStaff ? <ArrowLeft className="h-4 w-4" /> : <LogIn className="h-4 w-4" />}
            {isStaff ? 'Customer feedback' : 'Staff sign in'}
          </Link>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-6xl px-4 sm:px-6 py-8">
        <Routes>
          <Route path="/" element={<CustomerPage />} />
          <Route path="/staff/*" element={<StaffPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <footer className="border-t border-mns-line bg-white/60">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-4 text-xs text-mns-mute">
          Marks &amp; Spencer.
        </div>
      </footer>
    </div>
  )
}
