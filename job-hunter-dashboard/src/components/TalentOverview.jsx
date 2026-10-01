import {useState,useEffect} from 'react';
import {Link} from 'react-router-dom';
import axios from 'axios';
import ApplicationsTable from './dashboard/ApplicationsTable';
const API=import.meta.env.VITE_API_URL||'http://localhost:8000/api/v1';
export default function TalentOverview(){
 const [apps,setApps]=useState([]);const [profile,setProfile]=useState(null);const [error,setError]=useState('');const [loading,setLoading]=useState(true);
 useEffect(()=>{const config={headers:{Authorization:`Bearer ${localStorage.getItem('token')}`}};Promise.all([axios.get(`${API}/dashboard/applied`,config),axios.get(`${API}/profile/me`,config)]).then(([a,p])=>{setApps(a.data);setProfile(p.data)}).catch(()=>setError('Your dashboard could not load. Please refresh when the service is available.')).finally(()=>setLoading(false))},[]);
 if(loading)return <p role="status" className="text-slate-500">Loading your workspace…</p>;
 if(error)return <p role="alert" className="rounded-xl bg-amber-50 p-5 text-amber-800">{error}</p>;
 const fields=[profile?.about,profile?.career_track,profile?.country,profile?.linkedin_url,profile?.resume_url];const completeness=Math.round(fields.filter(Boolean).length/fields.length*100);
 return <div className="space-y-7"><div><h2 className="text-2xl font-semibold">Welcome back{profile?.full_name?`, ${profile.full_name.split(' ')[0]}`:''}</h2><p className="text-slate-500 mt-2">Prepare a strong application and keep every opportunity organized.</p></div>
 <div className="grid sm:grid-cols-3 gap-4">{[['Tracked opportunities',apps.length],['Interviews',apps.filter(a=>a.status==='interview').length],['Profile completion',`${completeness}%`]].map(([label,value])=><div key={label} className="bg-white rounded-2xl border border-slate-200 p-6"><p className="text-sm text-slate-500">{label}</p><p className="text-3xl font-semibold mt-3">{value}</p></div>)}</div>
 <div className="grid xl:grid-cols-[1.6fr_1fr] gap-6"><section><div className="flex justify-between mb-4"><h3 className="font-semibold text-lg">Recent applications</h3><Link className="text-emerald-700 text-sm" to="/applications">View all</Link></div><ApplicationsTable applications={apps.slice(0,4)} token={localStorage.getItem('token')}/></section>
 <div className="space-y-5"><section className="bg-white rounded-2xl p-6 border border-slate-200"><h3 className="font-semibold text-lg">Your next steps</h3><div className="space-y-3 mt-5">{[['Complete your professional profile','/profile'],['Tailor a resume to a vacancy','/optimizer'],['Explore opportunities','/jobs']].map(([label,url])=><Link key={url} to={url} className="block border border-slate-200 rounded-xl p-4 hover:bg-emerald-50 text-sm">{label} →</Link>)}</div></section><section className="bg-emerald-50 border border-emerald-100 rounded-2xl p-6"><h3 className="font-semibold">Invite your network</h3><p className="text-sm text-slate-600 mt-2">See your referral link, qualifying conversions, and reward terms.</p><Link className="inline-block mt-4 text-emerald-800 font-medium" to="/referral">View referrals →</Link></section></div></div></div>
}
