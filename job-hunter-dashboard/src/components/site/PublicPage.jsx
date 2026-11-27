/* eslint-disable react/prop-types -- the project does not use the prop-types package */
import SiteFooter from './SiteFooter';

// Shell for public pages (About, Contact, legal): simple header, content, full footer.
export default function PublicPage({ children }) {
  const signedIn = (() => { try { return !!localStorage.getItem('token'); } catch { return false; } })();
  return (
    <div className="min-h-screen flex flex-col bg-[#fbfaf7] text-slate-900" style={{ fontFamily: 'Inter, sans-serif' }}>
      <header className="border-b border-slate-200 bg-[#fbfaf7]/90 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 h-16 flex items-center gap-6">
          <a href="/" className="text-xl font-extrabold tracking-tight">baalebos<span className="text-emerald-500">.</span></a>
          <nav className="hidden sm:flex gap-6 text-sm text-slate-600 flex-1" aria-label="Site">
            <a href="/pricing" className="hover:text-slate-900">Pricing</a><a href="/about" className="hover:text-slate-900">About</a>
            <a href="/contact" className="hover:text-slate-900">Contact</a>
          </nav>
          <span className="flex-1 sm:hidden" />
          {signedIn ? <a href="/" className="rounded-lg bg-slate-900 text-white text-sm font-semibold px-4 py-2">Dashboard</a>
            : <><a href="/login" className="text-sm font-semibold text-slate-700 hover:text-slate-900">Sign in</a>
              <a href="/signup" className="rounded-lg bg-slate-900 text-white text-sm font-semibold px-4 py-2">Start free</a></>}
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </div>
  );
}
