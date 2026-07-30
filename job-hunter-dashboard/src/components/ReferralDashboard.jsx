// =============================================================================
// job-hunter-dashboard/src/components/ReferralDashboard.jsx
// Full referral dashboard — connects to /api/v1/referral/stats
// =============================================================================
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const TIERS = [
  { name: 'Starter',    min: 0,  max: 4,  reward: '$5/ref'  },
  { name: 'Growth',     min: 5,  max: 14, reward: '$8/ref'  },
  { name: 'Elite',      min: 15, max: null, reward: '$12/ref' },
]

export default function ReferralDashboard() {
  const [stats, setStats]       = useState(null)
  const [loading, setLoading]   = useState(true)
  const [copied, setCopied]     = useState(false)
  const [leaderboard, setLeaderboard] = useState([])
  const navigate                = useNavigate()
  const token                   = localStorage.getItem('token')

  useEffect(() => {
    if (!token) { navigate('/login'); return }
    Promise.all([
      axios.get(`${API_BASE_URL}/referral/stats`,       { headers: { Authorization: `Bearer ${token}` } }),
      axios.get(`${API_BASE_URL}/referral/leaderboard`, { headers: { Authorization: `Bearer ${token}` } }),
    ])
      .then(([statsRes, lbRes]) => {
        setStats(statsRes.data)
        setLeaderboard(lbRes.data)
      })
      .catch(err => {
        if (err.response?.status === 401) { navigate('/login') }
      })
      .finally(() => setLoading(false))
  }, [token, navigate])

  const copyLink = () => {
    if (!stats?.ref_link) return
    navigator.clipboard?.writeText(stats.ref_link).catch(() => {
      const el = document.createElement('textarea')
      el.value = stats.ref_link
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
    })
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const share = (platform) => {
    const url  = stats?.ref_link || ''
    const msgs = {
      twitter:  `I use Baalebos AI to optimize my resume for tech jobs worldwide. Try it free: ${url}`,
      linkedin: `I'm using Baalebos AI to land remote tech jobs globally. Sign up free: ${url}`,
      whatsapp: `Check out Baalebos AI — AI resume optimizer for tech jobs worldwide: ${url}`,
    }
    const urls = {
      twitter:  `https://twitter.com/intent/tweet?text=${encodeURIComponent(msgs.twitter)}`,
      linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
      whatsapp: `https://wa.me/?text=${encodeURIComponent(msgs.whatsapp)}`,
    }
    window.open(urls[platform], '_blank')
  }

  const tierIdx = stats
    ? TIERS.findIndex(t => stats.total >= t.min && (t.max === null || stats.total <= t.max))
    : 0

  if (loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-400 text-sm font-bold uppercase tracking-widest">Loading referral data...</p>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-slate-950" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* Navbar */}
      <nav className="sticky top-0 z-40 border-b border-slate-800/60 bg-slate-950/90 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
          <a href="/" className="flex items-center gap-3">
            <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center shadow-lg shadow-emerald-500/30">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z"/>
              </svg>
            </div>
            <span className="font-black text-white text-base tracking-tight">BAALEBOS CLOUD</span>
          </a>
          <div className="flex items-center gap-3">
            <a href="/" className="text-sm font-bold text-slate-400 hover:text-white transition-colors px-4 py-2">← Dashboard</a>
            <a href="/pricing" className="text-sm font-bold text-slate-400 hover:text-white transition-colors px-4 py-2">Pricing</a>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-4 md:px-8 py-12">

        {/* Header */}
        <div className="mb-10">
          <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-4 py-2 mb-4">
            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            <span className="text-emerald-400 text-xs font-bold uppercase tracking-widest">Earn $5–$12 per conversion</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-black text-white mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>
            Refer & Earn
          </h1>
          <p className="text-slate-400 text-lg max-w-xl">
            Share your link. Every friend who upgrades to Pro earns you cash — instantly tracked, paid monthly.
          </p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total referred',    value: stats?.total ?? 0,                        color: 'text-white' },
            { label: 'Converted',         value: stats?.converted ?? 0,                    color: 'text-emerald-400' },
            { label: 'Conversion rate',   value: `${stats?.conversion_rate ?? 0}%`,        color: 'text-blue-400' },
            { label: 'Total earned',      value: `$${stats?.total_earned ?? 0}`,           color: 'text-emerald-400' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <div className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">{label}</div>
              <div className={`text-3xl font-black ${color}`}>{value}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">

          {/* Referral link card */}
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6">
            <h2 className="text-base font-black text-white mb-4">Your referral link</h2>
            <div className="flex items-center gap-3 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 mb-4">
              <span className="flex-1 text-sm text-emerald-400 font-mono overflow-hidden whitespace-nowrap text-ellipsis">
                {stats?.ref_link || 'Loading...'}
              </span>
              <button onClick={copyLink}
                className="shrink-0 flex items-center gap-2 text-xs font-black text-white bg-emerald-600 hover:bg-emerald-500 px-3 py-2 rounded-lg transition-all">
                {copied ? '✓ Copied!' : 'Copy'}
              </button>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[
                { platform: 'twitter',  label: '𝕏 Twitter',   color: 'bg-slate-800 hover:bg-slate-700' },
                { platform: 'whatsapp', label: '💬 WhatsApp',  color: 'bg-green-900/40 hover:bg-green-900/60 border border-green-700/30' },
                { platform: 'linkedin', label: 'in LinkedIn',  color: 'bg-blue-900/40 hover:bg-blue-900/60 border border-blue-700/30' },
              ].map(({ platform, label, color }) => (
                <button key={platform} onClick={() => share(platform)}
                  className={`${color} text-white text-xs font-black py-2.5 rounded-xl transition-all text-center`}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Tier + progress card */}
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-black text-white">Reward tiers</h2>
              <span className="text-xs font-black px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                {TIERS[tierIdx]?.name} tier
              </span>
            </div>
            <div className="grid grid-cols-3 gap-3 mb-5">
              {TIERS.map((tier, i) => (
                <div key={tier.name}
                  className={`rounded-xl p-3 border transition-all ${
                    i === tierIdx
                      ? 'border-emerald-500/50 bg-emerald-500/10'
                      : i < tierIdx
                      ? 'border-slate-700 bg-slate-800/50'
                      : 'border-slate-800 bg-slate-950'
                  }`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-[10px] font-black uppercase tracking-widest ${i === tierIdx ? 'text-emerald-400' : 'text-slate-500'}`}>
                      {tier.name}
                    </span>
                    {i < tierIdx && <span className="text-emerald-400 text-xs">✓</span>}
                    {i === tierIdx && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
                  </div>
                  <div className={`text-base font-black ${i === tierIdx ? 'text-white' : 'text-slate-500'}`}>{tier.reward}</div>
                  <div className="text-[10px] text-slate-600 mt-0.5">
                    {tier.max ? `${tier.min}–${tier.max} refs` : `${tier.min}+ refs`}
                  </div>
                </div>
              ))}
            </div>

            {/* Progress bar */}
            <div>
              <div className="flex justify-between text-xs font-bold mb-2">
                <span className="text-slate-400">
                  {stats?.next_tier
                    ? `${stats.total} of ${stats.next_tier.min} to reach ${stats.next_tier.name}`
                    : '🏆 Elite tier — maximum rewards unlocked'}
                </span>
                <span className="text-emerald-400">{stats?.progress_pct ?? 0}%</span>
              </div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full transition-all duration-700"
                  style={{ width: `${stats?.progress_pct ?? 0}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Payout summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {[
            { label: 'Pending payout',  value: `$${stats?.pending_payout ?? 0}`, sub: 'Will be paid next cycle', color: 'text-amber-400' },
            { label: 'Total paid out',  value: `$${stats?.paid_out ?? 0}`,       sub: 'Sent to your account',    color: 'text-emerald-400' },
            { label: 'Pending signups', value: stats?.pending ?? 0,              sub: 'Free users not yet paid', color: 'text-slate-300' },
          ].map(({ label, value, sub, color }) => (
            <div key={label} className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <div className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">{label}</div>
              <div className={`text-2xl font-black ${color} mb-1`}>{value}</div>
              <div className="text-xs text-slate-600">{sub}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

          {/* Referrals table */}
          <div className="md:col-span-2 bg-slate-900 border border-slate-800 rounded-3xl p-6">
            <h2 className="text-base font-black text-white mb-4">Referred users</h2>
            {!stats?.referrals?.length ? (
              <div className="text-center py-12">
                <div className="text-4xl mb-3">🔗</div>
                <p className="text-slate-400 font-bold mb-1">No referrals yet</p>
                <p className="text-slate-600 text-sm">Share your link above to start earning</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm" style={{ tableLayout: 'fixed' }}>
                  <thead>
                    <tr className="border-b border-slate-800">
                      <th className="text-left py-3 text-xs font-black text-slate-500 uppercase tracking-widest" style={{ width: '35%' }}>User</th>
                      <th className="text-left py-3 text-xs font-black text-slate-500 uppercase tracking-widest" style={{ width: '18%' }}>Joined</th>
                      <th className="text-left py-3 text-xs font-black text-slate-500 uppercase tracking-widest" style={{ width: '15%' }}>Plan</th>
                      <th className="text-left py-3 text-xs font-black text-slate-500 uppercase tracking-widest" style={{ width: '17%' }}>Status</th>
                      <th className="text-right py-3 text-xs font-black text-slate-500 uppercase tracking-widest" style={{ width: '15%' }}>Earned</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.referrals.map((ref) => (
                      <tr key={ref.id} className="border-b border-slate-800/50 last:border-0">
                        <td className="py-3 text-slate-300 overflow-hidden text-ellipsis whitespace-nowrap">{ref.email}</td>
                        <td className="py-3 text-slate-500 text-xs">{ref.created_at}</td>
                        <td className="py-3 text-slate-400 text-xs">{ref.plan}</td>
                        <td className="py-3">
                          <span className={`text-xs font-black px-2 py-1 rounded-full ${
                            ref.status === 'converted'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          }`}>
                            {ref.status === 'converted' ? 'Converted' : 'Pending'}
                          </span>
                        </td>
                        <td className="py-3 text-right font-black">
                          {ref.status === 'converted'
                            ? <span className="text-emerald-400">${ref.reward}</span>
                            : <span className="text-slate-600">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* How it works + Leaderboard */}
          <div className="space-y-4">
            <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6">
              <h2 className="text-base font-black text-white mb-4">How it works</h2>
              <div className="space-y-3">
                {[
                  { icon: '🔗', title: 'Share your link',      desc: 'Copy and share on WhatsApp, LinkedIn, or X' },
                  { icon: '👤', title: 'Friend signs up',       desc: 'Tracked automatically when they use your link' },
                  { icon: '💳', title: 'They upgrade to Pro',   desc: 'Stripe fires — referral converts instantly' },
                  { icon: '💰', title: 'You get paid',          desc: '$5–$12 per conversion, paid monthly' },
                ].map(({ icon, title, desc }) => (
                  <div key={title} className="flex gap-3">
                    <span className="text-xl shrink-0 mt-0.5">{icon}</span>
                    <div>
                      <div className="text-sm font-black text-white">{title}</div>
                      <div className="text-xs text-slate-500 mt-0.5">{desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {leaderboard.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6">
                <h2 className="text-base font-black text-white mb-4">🏆 Top referrers</h2>
                <div className="space-y-2">
                  {leaderboard.slice(0, 5).map((row) => (
                    <div key={row.rank} className="flex items-center justify-between py-1.5">
                      <div className="flex items-center gap-3">
                        <span className={`text-sm font-black w-5 ${row.rank === 1 ? 'text-amber-400' : row.rank === 2 ? 'text-slate-300' : row.rank === 3 ? 'text-amber-700' : 'text-slate-600'}`}>
                          #{row.rank}
                        </span>
                        <div>
                          <div className="text-sm font-bold text-white">{row.name}</div>
                          <div className="text-[10px] text-slate-500">{row.tier} · {row.converted} converted</div>
                        </div>
                      </div>
                      <span className="text-sm font-black text-emerald-400">${row.earned}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
