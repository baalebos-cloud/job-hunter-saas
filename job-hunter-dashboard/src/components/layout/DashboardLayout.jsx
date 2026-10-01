import { Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { LayoutDashboard, FileText, Briefcase, ListChecks, Gift, UserRound, Settings, ShieldCheck, Building2, Menu, X, LogOut, CreditCard } from 'lucide-react';
import axios from 'axios';
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const links = [['Dashboard','/',LayoutDashboard],['Resume workspace','/optimizer',FileText],['Jobs','/jobs',Briefcase],['Applications','/applications',ListChecks],['Referrals','/referral',Gift],['My profile','/profile',UserRound],['Plans','/pricing',CreditCard],['Settings','/settings',Settings]];
export default function DashboardLayout({children}) {
  const {pathname}=useLocation(); const [open,setOpen]=useState(false); const [profile,setProfile]=useState(null);
  useEffect(()=>{setOpen(false)},[pathname]);
  useEffect(()=>{axios.get(`${API}/auth/me`,{headers:{Authorization:`Bearer ${localStorage.getItem('token')}`}}).then(r=>setProfile(r.data)).catch(()=>{})},[]);
  useEffect(()=>{if(!open)return; const close=e=>{if(e.key==='Escape')setOpen(false)}; window.addEventListener('keydown',close); return()=>window.removeEventListener('keydown',close)},[open]);
  const nav=[...links,...(profile?.is_admin?[['Owner console','/admin',ShieldCheck]]:[]),...(profile?.is_hr||profile?.is_admin?[['Employer portal','/hr',Building2]]:[])];
  return <div className="talent-shell min-h-screen flex bg-slate-50 text-slate-900">
    {open&&<button aria-label="Close navigation" className="fixed inset-0 bg-black/30 z-40 lg:hidden" onClick={()=>setOpen(false)}/>}
    <aside className={`fixed lg:sticky top-0 h-screen w-64 bg-white border-r border-slate-200 flex flex-col z-50 shrink-0 transition-transform ${open?'translate-x-0':'-translate-x-full lg:translate-x-0'}`}>
      <div className="p-7 flex items-center justify-between"><Link to="/" className="text-xl font-bold tracking-tight">baalebos<span className="text-emerald-600">.</span></Link><button className="lg:hidden" aria-label="Close navigation" onClick={()=>setOpen(false)}><X size={20}/></button></div>
      <nav className="px-3 space-y-1 overflow-y-auto flex-1" aria-label="Main navigation">{nav.map(([label,path,Icon])=><Link key={path} to={path} aria-current={pathname===path?'page':undefined} className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium ${pathname===path?'bg-emerald-50 text-emerald-800':'text-slate-600 hover:bg-slate-50'}`}><Icon size={19}/>{label}</Link>)}</nav>
      <div className="p-4 border-t border-slate-100 flex gap-3 items-center"><div className="rounded-full bg-emerald-100 w-9 h-9 flex items-center justify-center text-emerald-800 font-semibold">{(profile?.full_name||'B').slice(0,1)}</div><Link to="/profile" className="truncate text-sm flex-1">{profile?.full_name||'Your account'}</Link><button aria-label="Sign out" onClick={()=>{localStorage.removeItem('token');localStorage.removeItem('lastTaskId');window.location.href='/login'}}><LogOut size={18}/></button></div>
    </aside>
    <div className="min-w-0 flex-1"><header className="h-20 px-5 md:px-9 flex gap-4 items-center border-b border-slate-100 bg-white"><button className="lg:hidden" aria-label="Open navigation" onClick={()=>setOpen(true)}><Menu/></button><h1 className="text-xl font-semibold">{nav.find(x=>x[1]===pathname)?.[0]||'Baalebos'}</h1><span className="ml-auto text-sm text-slate-500 hidden sm:block">Your next opportunity starts here</span></header><main className="p-5 md:p-9 max-w-7xl mx-auto">{children}</main></div>
  </div>
}
