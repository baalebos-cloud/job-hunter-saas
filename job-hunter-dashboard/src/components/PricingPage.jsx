// =============================================================================
// job-hunter-dashboard/src/components/PricingPage.jsx
// Pricing page — matches your existing dark slate/emerald design system
// =============================================================================
import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://job-hunter-saas-production-bb41.up.railway.app/api/v1';

const PLANS = [
  {
    id:       'free',
    name:     'Free',
    price:    0,
    badge:    null,
    color:    'slate',
    features: [
      '2 AI resume scans per month',
      'ATS score + keyword analysis',
      'Basic PDF download',
      'Global job feed access',
      'Application tracker',
    ],
    limits: ['No unlimited scans', 'No priority support'],
    cta:      'Current Plan',
    ctaStyle: 'border-2 border-slate-700 text-slate-400 cursor-default',
  },
  {
    id:       'pro',
    name:     'Pro',
    price:    19,
    badge:    '🔥 Most Popular',
    color:    'emerald',
    features: [
      'Unlimited AI resume scans',
      'Full ATS score + keyword gap analysis',
      'AI-optimized PDF resume download',
      'Priority AI processing',
      'Resume history (last 30 scans)',
      'Email support',
    ],
    limits: [],
    cta:      'Upgrade to Pro →',
    ctaStyle: 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-xl shadow-emerald-600/25',
  },
  {
    id:       'enterprise',
    name:     'Enterprise',
    price:    49,
    badge:    '⚡ Best Value',
    color:    'purple',
    features: [
      'Everything in Pro',
      'Team access (up to 10 seats)',
      'Bulk resume processing',
      'API access for integrations',
      'Dedicated Slack support',
      'Custom branding on PDF exports',
    ],
    limits: [],
    cta:      'Upgrade to Enterprise →',
    ctaStyle: 'bg-purple-600 hover:bg-purple-500 text-white shadow-xl shadow-purple-600/25',
  },
];

const Check = () => (
  <svg className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
  </svg>
);

const Cross = () => (
  <svg className="w-4 h-4 text-slate-600 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

export default function PricingPage() {
  const [billing, setBilling]   = useState(null);
  const [loading, setLoading]   = useState(true);
  const [upgrading, setUpgrading] = useState('');
  const token = localStorage.getItem('token');

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    axios.get(`${API_BASE_URL}/billing/status`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => setBilling(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  const handleUpgrade = async (planId) => {
    if (!token) { window.location.href = '/signup'; return; }
    if (planId === 'free') return;
    setUpgrading(planId);
    try {
      const res = await axios.post(
        `${API_BASE_URL}/billing/checkout?plan=${planId}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      window.location.href = res.data.checkout_url;
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to start checkout. Please try again.');
    } finally {
      setUpgrading('');
    }
  };

  const handlePortal = async () => {
    if (!token) return;
    try {
      const res = await axios.post(
        `${API_BASE_URL}/billing/portal`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      window.location.href = res.data.portal_url;
    } catch {
      alert('Could not open billing portal. Please contact support.');
    }
  };

  const currentPlan = billing?.plan || 'free';

  return (
    <div className="min-h-screen bg-slate-950" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* Header */}
      <div className="max-w-6xl mx-auto px-4 md:px-8 pt-20 pb-12 text-center">
        <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-4 py-2 mb-6">
          <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
          <span className="text-emerald-400 text-xs font-bold uppercase tracking-widest">Simple Pricing · Cancel Anytime</span>
        </div>
        <h1 className="text-5xl md:text-6xl font-black text-white mb-4"
          style={{ fontFamily: "'Playfair Display', serif" }}>
          Invest in Your<br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 via-blue-400 to-purple-400">
            Career Growth
          </span>
        </h1>
        <p className="text-slate-400 text-lg max-w-xl mx-auto">
          Start free. Upgrade when you need unlimited AI resume optimization.
        </p>

        {/* Current usage pill */}
        {billing && (
          <div className="inline-flex items-center gap-3 mt-6 bg-slate-900 border border-slate-800 rounded-2xl px-6 py-3">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-slate-400 text-sm font-medium">
              Current plan: <span className="text-white font-black">{billing.plan_name}</span>
            </span>
            {billing.scans_limit !== -1 && (
              <span className="text-slate-500 text-sm">
                · <span className="text-emerald-400 font-bold">{billing.scans_this_month}</span>/{billing.scans_limit} scans used
              </span>
            )}
            {billing.scans_limit === -1 && (
              <span className="text-emerald-400 text-sm font-bold">· Unlimited scans</span>
            )}
            {billing.is_pro && (
              <button onClick={handlePortal}
                className="text-xs font-black text-slate-400 hover:text-white border border-slate-700 hover:border-slate-500 px-3 py-1 rounded-lg transition-all ml-2">
                Manage Billing →
              </button>
            )}
          </div>
        )}
      </div>

      {/* Plans grid */}
      <div className="max-w-6xl mx-auto px-4 md:px-8 pb-24">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {PLANS.map((plan) => {
            const isCurrentPlan = currentPlan === plan.id;
            const isPro         = plan.id === 'pro';
            const isEnterprise  = plan.id === 'enterprise';

            return (
              <div key={plan.id}
                className={`relative rounded-3xl p-8 flex flex-col border-2 transition-all ${
                  isPro
                    ? 'bg-emerald-950/30 border-emerald-500/50 shadow-2xl shadow-emerald-500/10'
                    : isEnterprise
                    ? 'bg-purple-950/20 border-purple-500/30'
                    : 'bg-slate-900 border-slate-800'
                }`}>

                {/* Badge */}
                {plan.badge && (
                  <div className={`absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full text-xs font-black whitespace-nowrap ${
                    isPro ? 'bg-emerald-500 text-white' : 'bg-purple-500 text-white'
                  }`}>
                    {plan.badge}
                  </div>
                )}

                {/* Current plan indicator */}
                {isCurrentPlan && (
                  <div className="absolute top-4 right-4 px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700">
                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Active</span>
                  </div>
                )}

                {/* Plan name & price */}
                <div className="mb-8">
                  <h3 className={`text-lg font-black uppercase tracking-widest mb-4 ${
                    isPro ? 'text-emerald-400' : isEnterprise ? 'text-purple-400' : 'text-slate-400'
                  }`}>{plan.name}</h3>

                  <div className="flex items-end gap-1">
                    <span className="text-5xl font-black text-white">${plan.price}</span>
                    {plan.price > 0 && <span className="text-slate-500 font-bold mb-2">/month</span>}
                    {plan.price === 0 && <span className="text-slate-500 font-bold mb-2">forever</span>}
                  </div>
                </div>

                {/* Features */}
                <ul className="space-y-3 mb-8 flex-1">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5">
                      <Check />
                      <span className="text-slate-300 text-sm font-medium">{f}</span>
                    </li>
                  ))}
                  {plan.limits.map((l) => (
                    <li key={l} className="flex items-start gap-2.5">
                      <Cross />
                      <span className="text-slate-600 text-sm font-medium">{l}</span>
                    </li>
                  ))}
                </ul>

                {/* CTA */}
                <button
                  onClick={() => handleUpgrade(plan.id)}
                  disabled={isCurrentPlan || upgrading === plan.id}
                  className={`w-full py-4 rounded-2xl font-black text-sm uppercase tracking-widest transition-all active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed ${
                    isCurrentPlan ? plan.ctaStyle : plan.ctaStyle
                  }`}>
                  {upgrading === plan.id
                    ? 'Opening Checkout...'
                    : isCurrentPlan
                    ? '✓ Current Plan'
                    : plan.cta}
                </button>
              </div>
            );
          })}
        </div>

        {/* Scan limit warning banner — shown when free user is close to limit */}
        {billing && billing.plan === 'free' && billing.scans_this_month >= 1 && (
          <div className={`mt-8 rounded-2xl border p-6 flex flex-col md:flex-row items-center justify-between gap-4 ${
            billing.scans_this_month >= billing.scans_limit
              ? 'bg-rose-950/30 border-rose-500/30'
              : 'bg-amber-950/20 border-amber-500/20'
          }`}>
            <div>
              <p className={`font-black text-base ${
                billing.scans_this_month >= billing.scans_limit ? 'text-rose-400' : 'text-amber-400'
              }`}>
                {billing.scans_this_month >= billing.scans_limit
                  ? '🚫 Monthly scan limit reached'
                  : `⚠️ ${billing.scans_left} free scan${billing.scans_left !== 1 ? 's' : ''} remaining this month`}
              </p>
              <p className="text-slate-400 text-sm mt-1">
                Upgrade to Pro for unlimited AI resume analysis — $19/month.
              </p>
            </div>
            <button onClick={() => handleUpgrade('pro')}
              className="shrink-0 bg-emerald-600 hover:bg-emerald-500 text-white font-black px-6 py-3 rounded-xl text-sm uppercase tracking-widest transition-all shadow-lg shadow-emerald-600/20 whitespace-nowrap">
              Upgrade Now →
            </button>
          </div>
        )}

        {/* FAQ */}
        <div className="mt-20">
          <h2 className="text-3xl font-black text-white text-center mb-10"
            style={{ fontFamily: "'Playfair Display', serif" }}>
            Frequently Asked Questions
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
            {[
              ['Can I cancel anytime?', 'Yes — cancel anytime from the billing portal. You keep Pro access until the end of your billing period.'],
              ['What counts as a scan?', 'Each time you upload a resume and run an AI analysis, that counts as one scan.'],
              ['Do unused scans roll over?', 'Free plan scans reset monthly and do not roll over. Pro and Enterprise users have unlimited scans so rollover doesn\'t apply.'],
              ['What payment methods are accepted?', 'All major credit/debit cards via Stripe. Paystack integration for Nigerian cards coming soon.'],
              ['Is there a refund policy?', 'Yes — if you are not satisfied within 7 days of your first payment, contact support for a full refund.'],
              ['Can I upgrade or downgrade?', 'Yes — upgrade or downgrade at any time from the billing portal. Changes take effect immediately.'],
            ].map(([q, a]) => (
              <div key={q} className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                <h4 className="font-black text-white mb-2 text-sm">{q}</h4>
                <p className="text-slate-400 text-sm leading-relaxed">{a}</p>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
