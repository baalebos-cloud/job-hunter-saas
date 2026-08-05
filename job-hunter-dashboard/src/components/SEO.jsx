// =============================================================================
// job-hunter-dashboard/src/components/SEO.jsx 
// Per-page <title> and meta description for the SPA.
// Since this is Vite + React Router (not Next.js), there's no built-in
// file-based metadata system — this component fills that gap client-side.
//
// Usage: drop <SEO title="..." description="..." /> at the top of any page
// component's return block.
// =============================================================================
import { Helmet } from 'react-helmet-async';

export default function SEO({
  title,
  description = 'Baalebos Cloud uses AI to analyze your resume against any job description, score your ATS compatibility, and match you with live remote jobs globally. Free to use.',
  path = '',
}) {
  const fullTitle = title ? `${title} | Baalebos Cloud` : 'Baalebos Cloud — AI Resume Optimizer & Job Matching Platform';
  const url = `https://www.baalebo.xyz${path}`;

  return (
    <Helmet>
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={url} />

      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={url} />

      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
    </Helmet>
  );
}
