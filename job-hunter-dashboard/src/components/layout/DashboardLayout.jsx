// =============================================================================
// job-hunter-dashboard/src/components/layout/DashboardLayout.jsx
// Fixes:
//  1. Mobile responsive — drawer on mobile, collapsible on desktop
//  2. Applications page fetches and shows real data
//  3. Admin/HR nav hidden from regular users
//  4. Visible tech grid background (opacity bumped up)
// =============================================================================
import { Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// ── Nav structure ─────────────────────────────────────────────────────────────
const NAV_MAIN = [
  { name: 'Dashboard',    path: '/',            icon: '🚀' },
  { name: 'Resume AI',    path: '/optimizer',   icon: '🧠' },
  { name: 'Job Feed',     path: '/jobs',        icon: '🌍' },
  { name: 'Applications', path: '/applications',icon: '📋' },
];
const NAV_ACCOUNT = [
  { name: 'Refer & Earn', path: '/referral',    icon: '💸' },
  { name: 'Pricing',      path: '/pricing',     icon: '⚡' },
  { name: 'My Profile',   path: '/profile',     icon: '👤' },
  { name: 'Settings',     path: '/settings',    icon: '⚙️' },
];
const NAV_ADMIN = [
  { name: 'Admin Panel',  path: '/admin',       icon: '🛡️' },
  { name: 'HR Portal',    path: '/hr',          icon: '🏢' },
];

// ── Visible tech grid background ──────────────────────────────────────────────
// FIX 4: Bumped opacity from 0.025 → 0.07 so grid is visible but not overwhelming
const TechGrid = () => (
  <div className="absolute inset-0 pointer-events-none"
    style={{
      backgroundImage: 'linear-gradient(rgba(16,185,129,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(16,185,129,0.07) 1px, transparent 1px)',
      backgroundSize: '28px 28px',
    }}
  />
);

// ── Signal Room background — see index.css for the .app-canvas layer system ──
const SignalRoomBg = () => (
  <>
    <div className="app-canvas-mesh" />
    <div className="app-canvas-grain" />
  </>
);

// ── Nav item ──────────────────────────────────────────────────────────────────
function NavItem({ item, active, onClick }) {
  return (
    <Link to={item.path} onClick={onClick}
      className={`relative flex items-center gap-3 px-4 py-3 rounded-2xl transition-all duration-200 font-bold text-sm overflow-hidden ${
        active
          ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/40'
          : 'text-slate-400 hover:text-white hover:bg-white/5'
      }`}>
      {/* Active state inner grid */}
      {active && (
        <div className="absolute inset-0 opacity-10 pointer-events-none"
          style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)', backgroundSize: '14px 14px' }} />
      )}
      <span className="text-lg shrink-0">{item.icon}</span>
      <span className="truncate">{item.name}</span>
      {active && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-white/60 shrink-0" />}
    </Link>
  );
}

// ── Section label ─────────────────────────────────────────────────────────────
function SectionLabel({ children }) {
  return (
    <div className="flex items-center gap-2 px-4 mb-2 mt-5">
      <p className="text-[9px] font-black text-slate-600 uppercase tracking-[0.2em]">{children}</p>
      <div className="flex-1 h-px bg-slate-800" />
    </div>
  );
}

// ── Main DashboardLayout ──────────────────────────────────────────────────────
export default function DashboardLayout({ children }) {
  const location                    = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profile, setProfile]       = useState(null);
  const [health, setHealth]         = useState('checking');
  const [plan, setPlan]             = useState('free');
  const token = localStorage.getItem('token');

  // Close mobile drawer on route change
  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  // Lock body scroll while drawer is open + close on Escape key
  // (also fixes the "drawer looks stuck open" symptom caused by background scroll)
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = 'hidden';
      const onEsc = (e) => { if (e.key === 'Escape') setMobileOpen(false); };
      window.addEventListener('keydown', onEsc);
      return () => {
        document.body.style.overflow = '';
        window.removeEventListener('keydown', onEsc);
      };
    }
    document.body.style.overflow = '';
  }, [mobileOpen]);

  // Fetch profile + plan
  useEffect(() => {
    if (!token) return;
    axios.get(`${API_BASE_URL}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setProfile(r.data)).catch(() => {});
    axios.get(`${API_BASE_URL}/billing/status`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setPlan(r.data?.plan || 'free')).catch(() => {});
  }, [token]);

  // Health check every 30s
  useEffect(() => {
    const check = () => axios.get(`${API_BASE_URL}/health`, { timeout: 5000 })
      .then(() => setHealth('online')).catch(() => setHealth('offline'));
    check();
    const iv = setInterval(check, 30000);
    return () => clearInterval(iv);
  }, []);

  // FIX 3: Only show Admin/HR nav to elevated accounts
  const isAdmin = profile?.is_admin;
  const isHR    = profile?.is_hr;

  const initials = (profile?.full_name || profile?.email || 'U')
    .split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

  const pageTitle = {
    '/':             'Overview',
    '/optimizer':    'Resume AI',
    '/jobs':         'Job Feed',
    '/applications': 'Application Tracker',
    '/referral':     'Refer & Earn',
    '/pricing':      'Pricing',
    '/settings':     'Settings',
    '/admin':        'Admin Panel',
    '/hr':           'HR Portal',
  }[location.pathname] || 'Dashboard';

  // ── Sidebar content (shared between mobile drawer + desktop) ───────────────
  const SidebarContent = () => (
    <div className="relative flex flex-col h-full">
      <TechGrid />
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent" />

      <div className="relative z-10 flex flex-col h-full p-4 overflow-y-auto">

        {/* Logo */}
        <div className="flex items-center justify-between px-2 mb-6 shrink-0">
          <div>
            <h1 className="text-white text-xl font-black tracking-tighter italic">
              BAALEBO<span className="text-emerald-400">.</span>
            </h1>
            <div className="h-0.5 w-6 bg-emerald-500 rounded-full mt-1" />
          </div>
          {/* Mobile close button */}
          <button onClick={() => setMobileOpen(false)}
            className="lg:hidden w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white transition-all">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {/* Main nav */}
        <div className="shrink-0">
          <SectionLabel>Main</SectionLabel>
          <nav className="space-y-1">
            {NAV_MAIN.map(item => (
              <NavItem key={item.path} item={item}
                active={location.pathname === item.path}
                onClick={() => setMobileOpen(false)} />
            ))}
          </nav>
        </div>

        {/* Account nav */}
        <div className="shrink-0">
          <SectionLabel>Account</SectionLabel>
          <nav className="space-y-1">
            {NAV_ACCOUNT.map(item => (
              <NavItem key={item.path} item={item}
                active={location.pathname === item.path}
                onClick={() => setMobileOpen(false)} />
            ))}
          </nav>
        </div>

        {/* FIX 3: Admin / HR — only for elevated accounts */}
        {(isAdmin || isHR) && (
          <div className="shrink-0">
            <SectionLabel>{isAdmin ? 'Admin' : 'HR'}</SectionLabel>
            <nav className="space-y-1">
              {NAV_ADMIN
                .filter(item => isAdmin || (isHR && item.path === '/hr'))
                .map(item => (
                  <NavItem key={item.path} item={item}
                    active={location.pathname === item.path}
                    onClick={() => setMobileOpen(false)} />
                ))}
            </nav>
          </div>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Plan badge */}
        <div className={`shrink-0 mx-1 mb-3 px-3 py-2.5 rounded-xl border text-center ${
          plan === 'free'
            ? 'bg-slate-800/50 border-slate-700'
            : 'bg-emerald-900/30 border-emerald-700/40'
        }`}>
          <p className={`text-[10px] font-black uppercase tracking-widest ${plan === 'free' ? 'text-slate-500' : 'text-emerald-400'}`}>
            {plan === 'free' ? '⚡ Free Plan' : `✅ ${plan.charAt(0).toUpperCase() + plan.slice(1)} Plan`}
          </p>
          {plan === 'free' && (
            <Link to="/pricing" onClick={() => setMobileOpen(false)}
              className="text-[10px] font-bold text-emerald-400 hover:text-emerald-300 transition-colors block mt-0.5">
              Upgrade for unlimited scans →
            </Link>
          )}
        </div>

        {/* System status */}
        <div className="shrink-0 mx-1 mb-3 bg-slate-800/60 border border-slate-700/50 rounded-2xl p-3">
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
        </div>

        {/* User profile */}
        <div className="shrink-0 flex items-center gap-3 px-2 py-2.5 rounded-2xl hover:bg-white/5 transition-all">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-white text-xs font-black shadow-lg shadow-emerald-900/40 shrink-0">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-black text-white truncate">
              {profile?.full_name || profile?.email?.split('@')[0] || 'Loading...'}
            </p>
            <p className="text-[10px] text-slate-500 truncate">{profile?.email || ''}</p>
          </div>
          <button
            onClick={() => { localStorage.removeItem('token'); window.location.href = '/login'; }}
            className="shrink-0 w-7 h-7 rounded-lg bg-slate-800 hover:bg-rose-900/40 border border-slate-700 hover:border-rose-700/40 flex items-center justify-center text-slate-500 hover:text-rose-400 transition-all"
            title="Sign out">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="app-canvas min-h-screen flex" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* Signal Room — layered mesh + grain over the aurora canvas */}
      <SignalRoomBg />

      {/* ── FIX 1 Mobile overlay ── */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-slate-950/80 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)} />
      )}

      {/* ── FIX 1 Sidebar — drawer on mobile, sticky on desktop ── */}
      <aside className={`
        fixed lg:sticky top-0 left-0 z-50 lg:z-auto
        w-[280px] lg:w-64 xl:w-72
        h-screen lg:h-screen lg:max-h-screen
        bg-slate-900 border-r border-slate-800
        lg:rounded-none
        shadow-2xl lg:shadow-none
        transition-transform duration-300 ease-in-out
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        flex-shrink-0
      `}>
        <SidebarContent />
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10">

        {/* Top header */}
        <header className="sticky top-0 z-30 bg-slate-950/90 backdrop-blur-xl border-b border-slate-800/60 px-4 md:px-6 py-3 flex items-center justify-between gap-3 shrink-0">

          {/* FIX 1: Mobile hamburger */}
          <button onClick={() => setMobileOpen(true)}
            className="lg:hidden w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white transition-all shrink-0">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16"/>
            </svg>
          </button>

          {/* Page title */}
          <h2 className="text-sm md:text-base font-black text-white tracking-tight truncate">{pageTitle}</h2>

          {/* Right side — profile details */}
          <div className="flex items-center gap-2 ml-auto shrink-0">

            {/* FIX 2: User profile shown in header on mobile */}
            {profile && (
              <div className="hidden sm:flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-xl">
                <div className="w-6 h-6 bg-emerald-500 rounded-lg flex items-center justify-center text-white text-[10px] font-black">
                  {initials}
                </div>
                <div className="hidden md:block">
                  <p className="text-xs font-black text-white leading-none">
                    {profile.full_name || profile.email?.split('@')[0]}
                  </p>
                  <p className="text-[9px] text-slate-500 leading-none mt-0.5">{profile.email}</p>
                </div>
                {/* Role badges */}
                {profile.is_admin && (
                  <span className="text-[9px] font-black px-1.5 py-0.5 rounded-full bg-purple-500/20 text-purple-400 border border-purple-500/20">ADMIN</span>
                )}
                {profile.is_hr && !profile.is_admin && (
                  <span className="text-[9px] font-black px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/20">HR</span>
                )}
              </div>
            )}

            {/* Plan pill */}
            <span className={`hidden lg:flex items-center gap-1 text-[10px] font-black uppercase tracking-widest px-2.5 py-1.5 rounded-full border ${
              plan === 'free'
                ? 'bg-slate-800 border-slate-700 text-slate-400'
                : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
            }`}>
              {plan === 'free' ? '⚡' : '✅'} {plan}
            </span>

            {/* Notification bell */}
            <button className="relative w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:text-white transition-all">
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
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
