import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { RunsPage } from './pages/RunsPage'
import { RunDetailPanel } from './pages/RunDetailPanel'
import { WorkersPage } from './pages/WorkersPage'
import { NewRunPage } from './pages/NewRunPage'
import { ComparePage } from './pages/ComparePage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5000, retry: 1 } },
})

function Nav() {
  const { pathname } = useLocation()
  const link = (to: string, label: string) => (
    <Link
      to={to}
      className={`text-sm font-medium transition-colors ${pathname === to ? 'text-primary' : 'text-gray-500 hover:text-secondary'}`}
    >
      {label}
    </Link>
  )
  return (
    <nav className="sticky top-0 z-50 flex h-[52px] items-center gap-6 border-b border-black/5 bg-white/70 px-6 backdrop-blur-xl">
      <Link to="/" className="font-serif text-lg font-bold text-secondary">
        lm<span className="text-primary">pc</span>
      </Link>
      {link('/', 'Runs')}
      {link('/workers', 'Workers')}
      <div className="ml-auto">
        <Link to="/new" className="btn text-sm">
          + New Run
        </Link>
      </div>
    </nav>
  )
}

function Layout() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/" element={<RunsPage />}>
          <Route path="runs/:id" element={<RunDetailPanel />} />
        </Route>
        <Route path="/workers" element={<WorkersPage />} />
        <Route path="/new" element={<NewRunPage />} />
        <Route path="/compare" element={<ComparePage />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
