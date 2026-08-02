// =============================================================================
// job-hunter-dashboard/src/components/layout/DashboardLayout.jsx
//  1. Tech grid background on sidebar and main
//  2. Full nav — all 7 routes wired in (Dashboard, Resume, Jobs, Referral,
//     Pricing, Settings, HR / Admin for elevated accounts)
//  3. Live system status with Railway backend health check
//  4. User profile pill from token/auth
//  5. Notification bell placeholder
//  6. Collapsible sidebar on mobile
//  7. Better visual hierarchy — section labels, active states, tooltips
// =============================================================================
import { Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// ── Nav structure ─────────────────────────────────────────────────────────────
const NAV_MAIN = [
  { name: 'Dashboard',      path: '/',         icon: '🚀', tip: 'Overview & stats' },
  { name: 'Resume AI',      path: '/optimizer', icon: '🧠', tip: 'AI resume optimizer' },
  { name: 'Job Feed',       path: '/jobs',      icon: '🌍', tip: 'Global tech jobs' },
  { name: 'Applications',   path: '/applications', icon: '📋', tip: 'Track your applications' },
];
const NAV_ACCOUNT = [
  { name: 'Refer & Earn',   path: '/referral',  icon: '💸', tip: '$5–$12 per referral' },
  { name: 'Pricing',        path: '/pricing',   icon: '⚡', tip: 'Upgrade to Pro' },
  { name: 'Settings',       path: '/settings',  icon: '⚙️', tip: 'Account settings' },
];
const NAV_ADMIN = [
  { name: 'Admin Panel',    path: '/admin',     icon: '🛡️', tip: 'Admin dashboard' },
  { name: 'HR Portal',      path: '/hr',        icon: '🏢', tip: 'Post jobs as HR' },
];

// ── Tech grid SVG background ──────────────────────────────────────────────────
const TechGrid = ({ opacity = 0.025 }) => (
  <div className="absolute inset-0 pointer-events-none rounded-[inherit]"
    style={{
      opacity,
      backgroundImage: 'linear-gradient(#10b981 1px, transparent 1px), linear-gradient(90deg, #10b981 1px, transparent 1px)',
      backgroundSize: '28px 28px',
    }}
  />
);

// ── Sidebar nav item ──────────────────────────────────────────────────────────
function NavItem({ item, active, collapsed }) {
  return (
    <Link to={item.path} title={item.tip}
      className={`relative flex items-center gap-3 px-4 py-3 rounded-2xl transition-all duration-200 font-bold text-sm group overflow-hidden ${
        active
          ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/40'
          : 'text-slate-500 hover:text-white hover:bg-white/5'
      }`}>
      {active && <div className="absolute inset-0 opacity-10 pointer-events-none"
        style={{ backgroundImage: 'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)', backgroundSize: '16px 16px' }} />}
      <span className="text-lg shrink-0">{item.icon}</span>
      {!collapsed && <span className="truncate">{item.name}</span>}
      {active && !collapsed && (
        <span className="ml-auto w-1.5 h-1.5 rounded-full bg-white/60" />
      )}
      {/* Tooltip when collapsed */}
      {collapsed && (
        <span className="absolute left-full ml-3 px-3 py-1.5 bg-slate-800 border border-slate-700 text-white text-xs font-black rounded-xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 shadow-xl">
          {item.name}
        </span>
      )}
    </Link>
  );
}

// ── Main layout ───────────────────────────────────────────────────────────────
export default function DashboardLayout({ children }) {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profile, setProfile]     = useState(null);
  const [health, setHealth]       = useState('checking'); // checking | online | offline
  const [plan, setPlan]           = useState('free');
  const token = localStorage.getItem('token');

  // Fetch user profile + plan
  useEffect(() => {
    if (!token) return;
    axios.get(`${API_BASE_URL}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setProfile(r.data)).catch(() => {});
    axios.get(`${API_BASE_URL}/billing/status`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setPlan(r.data?.plan || 'free')).catch(() => {});
  }, [token]);

  // Health check
  useEffect(() => {
    axios.get(`${API_BASE_URL}/health`, { timeout: 5000 })
      .then(() => setHealth('online'))
      .catch(() => setHealth('offline'));
    const interval = setInterval(() => {
      axios.get(`${API_BASE_URL}/health`, { timeout: 5000 })
        .then(() => setHealth('online'))
        .catch(() => setHealth('offline'));
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const isAdmin = profile?.is_admin;
  const isHR    = profile?.is_hr;
  const initials = (profile?.full_name || profile?.email || 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

  const pageTitle = {
    '/':            'Overview',
    '/optimizer':   'AI Resume Optimizer',
    '/jobs':        'Global Job Feed',
    '/applications':'Application Tracker',
    '/referral':    'Refer & Earn',
    '/pricing':     'Pricing Plans',
    '/settings':    'Settings',
    '/admin':       'Admin Panel',
    '/hr':          'HR Portal',
  }[location.pathname] || 'Dashboard';

  const sidebarW = collapsed ? 'w-20' : 'w-72';

  return (
    <div className="min-h-screen bg-[#020617] flex font-sans" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* ── Mobile overlay ── */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-slate-950/80 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)} />
      )}

      {/* ── Sidebar ── */}
      <aside className={`
        fixed lg:sticky top-0 left-0 z-50 lg:z-auto
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        ${sidebarW}
        h-screen lg:h-[calc(100vh-2rem)] lg:my-4 lg:ml-4
        bg-slate-900 lg:rounded-3xl
        flex flex-col overflow-hidden
        border border-slate-800
        shadow-2xl shadow-slate-950/60
        transition-all duration-300 ease-in-out
        relative
      `}>
        <TechGrid opacity={0.03} />

        {/* Top accent */}
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-emerald-500/60 to-transparent" />

        <div className="relative z-10 flex flex-col h-full p-4">

          {/* Logo + collapse toggle */}
          <div className="flex items-center justify-between mb-8 px-2">
            {!collapsed && (
              <div>
                <h1 className="text-white text-xl font-black tracking-tighter italic">
                  BAALEBO<span className="text-emerald-400">.</span>
                </h1>
                <div className="h-0.5 w-6 bg-emerald-500 rounded-full mt-1" />
              </div>
            )}
            {collapsed && (
              <div className="w-8 h-8 bg-emerald-600 rounded-xl flex items-center justify-center mx-auto shadow-lg shadow-emerald-900/40">
                <span className="text-sm font-black text-white">B</span>
              </div>
            )}
            <button onClick={() => setCollapsed(c => !c)}
              className="hidden lg:flex w-8 h-8 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 items-center justify-center text-slate-400 hover:text-white transition-all shrink-0">
              <svg className={`w-3.5 h-3.5 transition-transform ${collapsed ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7"/>
              </svg>
            </button>
          </div>

          {/* Main nav */}
          <div className="mb-2">
            {!collapsed && (
              <p className="text-[9px] font-black text-slate-600 uppercase tracking-[0.15em] px-4 mb-2">Main</p>
            )}
            <nav className="space-y-1">
              {NAV_MAIN.map(item => (
                <NavItem key={item.path} item={item} active={location.pathname === item.path} collapsed={collapsed} />
              ))}
            </nav>
          </div>

          {/* Account nav */}
          <div className="mb-2">
            {!collapsed && (
              <p className="text-[9px] font-black text-slate-600 uppercase tracking-[0.15em] px-4 mb-2 mt-4">Account</p>
            )}
            {!collapsed && <div className="h-px bg-slate-800 mb-3" />}
            <nav className="space-y-1">
              {NAV_ACCOUNT.map(item => (
                <NavItem key={item.path} item={item} active={location.pathname === item.path} collapsed={collapsed} />
              ))}
            </nav>
          </div>

          {/* Admin / HR nav — only shown for elevated accounts */}
          {(isAdmin || isHR) && (
            <div className="mb-2">
              {!collapsed && (
                <>
                  <p className="text-[9px] font-black text-slate-600 uppercase tracking-[0.15em] px-4 mb-2 mt-4">
                    {isAdmin ? 'Admin' : 'HR'}
                  </p>
                  <div className="h-px bg-slate-800 mb-3" />
                </>
              )}
              <nav className="space-y-1">
                {NAV_ADMIN
                  .filter(item => isAdmin || (isHR && item.path === '/hr'))
                  .map(item => (
                    <NavItem key={item.path} item={item} active={location.pathname === item.path} collapsed={collapsed} />
                  ))}
              </nav>
            </div>
          )}

          {/* Spacer */}
          <div className="flex-1" />

          {/* Plan badge */}
          {!collapsed && (
            <div className={`mb-3 px-3 py-2 rounded-xl border text-center ${
              plan === 'free'
                ? 'bg-slate-800/50 border-slate-700'
                : 'bg-emerald-900/30 border-emerald-700/40'
            }`}>
              <p className={`text-[10px] font-black uppercase tracking-widest ${plan === 'free' ? 'text-slate-500' : 'text-emerald-400'}`}>
                {plan === 'free' ? '⚡ Upgrade to Pro' : `✅ ${plan.charAt(0).toUpperCase() + plan.slice(1)} Plan`}
              </p>
              {plan === 'free' && (
                <Link to="/pricing" className="text-[10px] font-bold text-emerald-400 hover:text-emerald-300 transition-colors">
                  Unlock unlimited scans →
                </Link>
              )}
            </div>
          )}

          {/* System status */}
          <div className={`${collapsed ? 'px-1' : 'px-2'} mb-3`}>
            <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-3">
              {!collapsed ? (
                <>
                  <p className="text-[9px] font-black text-emerald-400 uppercase tracking-[0.15em] mb-1.5">System Status</p>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${
                      health === 'online'  ? 'bg-emerald-400 animate-pulse' :
                      health === 'offline' ? 'bg-rose-500' : 'bg-amber-400 animate-pulse'
                    }`} />
                    <span className="text-xs font-bold text-slate-300">
                      {health === 'online' ? 'API Online' : health === 'offline' ? 'API Offline' : 'Checking...'}
                    </span>
                  </div>
                  <p className="text-[9px] text-slate-600 mt-1">Railway · US East</p>
                </>
              ) : (
                <div className="flex justify-center">
                  <span className={`w-2.5 h-2.5 rounded-full ${
                    health === 'online' ? 'bg-emerald-400 animate-pulse' :
                    health === 'offline' ? 'bg-rose-500' : 'bg-amber-400 animate-pulse'
                  }`} title={`API ${health}`} />
                </div>
              )}
            </div>
          </div>

          {/* User profile */}
          <div className={`flex items-center gap-3 px-2 py-3 rounded-2xl hover:bg-white/5 transition-all cursor-pointer ${collapsed ? 'justify-center' : ''}`}>
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-white text-xs font-black shadow-lg shadow-emerald-900/40 shrink-0">
              {initials}
            </div>
            {!collapsed && profile && (
              <div className="min-w-0 flex-1">
                <p className="text-xs font-black text-white truncate">
                  {profile.full_name || profile.email?.split('@')[0]}
                </p>
                <p className="text-[10px] text-slate-500 truncate">{profile.email}</p>
              </div>
            )}
            {!collapsed && (
              <button onClick={() => { localStorage.removeItem('token'); window.location.href = '/login'; }}
                className="shrink-0 w-7 h-7 rounded-lg bg-slate-800 hover:bg-rose-900/40 hover:border-rose-700/40 border border-slate-700 flex items-center justify-center text-slate-500 hover:text-rose-400 transition-all"
                title="Sign out">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
                </svg>
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 min-w-0 flex flex-col overflow-hidden">

        {/* Top header bar */}
        <header className="sticky top-0 z-30 bg-slate-950/80 backdrop-blur-xl border-b border-slate-800/60 px-6 py-4 flex items-center justify-between gap-4">

          {/* Mobile hamburger */}
          <button onClick={() => setMobileOpen(o => !o)}
            className="lg:hidden w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white transition-all shrink-0">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16"/>
            </svg>
          </button>

          {/* Page title */}
          <div className="flex items-center gap-3">
            <h2 className="text-base font-black text-white tracking-tight">{pageTitle}</h2>
            <span className="hidden sm:block text-[10px] font-bold text-slate-600 uppercase tracking-widest">
              {new Date().toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })}
            </span>
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-3 ml-auto">
            {/* Plan badge */}
            <span className={`hidden sm:flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest px-3 py-1.5 rounded-full ${
              plan === 'free'
                ? 'bg-slate-800 border border-slate-700 text-slate-400'
                : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
            }`}>
              {plan === 'free' ? '⚡' : '✅'} {plan.charAt(0).toUpperCase() + plan.slice(1)}
            </span>

            {/* Notification bell */}
            <button className="relative w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white transition-all"
              title="Notifications">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
              </svg>
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-emerald-500 rounded-full border-2 border-slate-950" />
            </button>

            {/* Avatar */}
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-white text-xs font-black shadow-lg shadow-emerald-900/40 shrink-0">
              {initials}
            </div>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-y-auto p-6 md:p-8 animate-fade-in">
          {children}
        </div>
      </main>
    </div>
  );
}
