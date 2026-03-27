export default function JobDetailsModal({ job, isOpen, onClose, onApply }) {
  if (!isOpen || !job) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex justify-between items-start">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">{job.title}</h2>
            <p className="text-emerald-600 font-medium">{job.company} • {job.location}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-2xl">&times;</button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto">
          <div className="mb-6">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-2">Job Description</h3>
            <div className="text-slate-600 leading-relaxed whitespace-pre-wrap">
              {job.description || "No detailed description provided. Click 'View Original' to see full details."}
            </div>
          </div>
          
          <div className="flex gap-4 mb-2">
            <div className="bg-slate-50 p-3 rounded-lg flex-1">
              <span className="block text-xs text-slate-400 uppercase">Source</span>
              <span className="font-semibold text-slate-700">{job.source}</span>
            </div>
            <div className="bg-slate-50 p-3 rounded-lg flex-1">
              <span className="block text-xs text-slate-400 uppercase">Category</span>
              <span className="font-semibold text-slate-700">{job.category}</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-100 bg-slate-50 flex justify-between items-center">
          <a href={job.url} target="_blank" rel="noreferrer" className="text-slate-500 hover:text-slate-800 font-medium">
            View Original Posting ↗
          </a>
          <button 
            onClick={() => { onApply(job.id); onClose(); }}
            className="bg-emerald-600 hover:bg-emerald-700 text-white px-8 py-3 rounded-xl font-bold transition-all"
          >
            Apply with Baalebos AI
          </button>
        </div>
      </div>
    </div>
  );
}
