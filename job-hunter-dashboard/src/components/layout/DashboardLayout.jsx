import { Link, useLocation } from 'react-router-dom';

const navItems = [
  { name: 'Dashboard', path: '/', icon: '🚀' },
  { name: 'AI Optimizer', path: '/optimizer', icon: '🧠' },
  { name: 'Job Tracker', path: '/jobs', icon: '🎯' },
  { name: 'Settings', path: '/settings', icon: '⚙️' },
];

export default function DashboardLayout({ children }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-brand-surface flex font-sans">
      {/* Premium Sidebar */}
      <aside className="w-72 h-[calc(100vh-2.5rem)] sticky top-5 left-5 m-5 bg-brand-dark rounded-[2.5rem] p-10 flex flex-col shadow-2xl shadow-slate-900/40">
        <div className="mb-14">
          <h1 className="text-white text-2xl font-black tracking-tighter italic">BAALEBO<span className="text-brand-primary">.</span></h1>
          <div className="h-1 w-8 bg-brand-primary rounded-full mt-1"></div>
        </div>

        <nav className="flex-1 space-y-3">
          {navItems.map((item) => (
            <Link
              key={item.name}
              to={item.path}
              className={`flex items-center gap-4 px-6 py-4 rounded-2xl transition-all duration-300 font-bold text-sm ${
                location.pathname === item.path 
                ? "bg-brand-primary text-white shadow-lg shadow-emerald-900/30 scale-105" 
                : "text-slate-500 hover:text-white hover:bg-white/5"
              }`}
            >
              <span className="text-xl">{item.icon}</span>
              {item.name}
            </Link>
          ))}
        </nav>

        <div className="bg-white/5 border border-white/10 p-6 rounded-3xl">
          <p className="text-[10px] font-black text-brand-primary uppercase tracking-[0.2em]">System Status</p>
          <p className="text-white text-xs font-bold mt-1">AWS Nodes: Online</p>
        </div>
      </aside>

      {/* Content Area */}
      <main className="flex-1 p-12 overflow-y-auto animate-fade-in">
        <header className="flex justify-between items-center mb-12">
          <h2 className="text-2xl font-black text-slate-900 tracking-tight capitalize">
            {location.pathname.replace('/', '') || 'Overview'}
          </h2>
          <div className="flex items-center gap-4 bg-white p-2 rounded-2xl shadow-sm border border-slate-100">
            <span className="px-4 py-2 text-xs font-black text-slate-400 uppercase">Engineer ID: 01</span>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-brand-primary shadow-inner" />
          </div>
        </header>

        {children}
      </main>
    </div>
  );
}
