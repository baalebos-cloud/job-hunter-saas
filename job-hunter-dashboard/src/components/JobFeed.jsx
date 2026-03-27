import { Briefcase, MapPin, DollarSign, Send } from 'lucide-react';

export default function JobFeed({ jobs, onApply }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
      {jobs.map((job) => (
        <div key={job.id} className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 hover:border-blue-300 transition-all">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-bold text-lg text-slate-900">{job.title}</h3>
              <p className="text-blue-600 font-medium">{job.company}</p>
            </div>
            <span className="bg-slate-100 text-slate-600 text-xs px-2 py-1 rounded">
              {job.source || 'Scraped'}
            </span>
          </div>
          
          <div className="space-y-2 mb-6">
            <div className="flex items-center text-slate-500 text-sm">
              <MapPin className="w-4 h-4 mr-2" /> {job.location || 'Remote'}
            </div>
            <div className="flex items-center text-slate-500 text-sm">
              <DollarSign className="w-4 h-4 mr-2" /> {job.salary_range || 'Competitive'}
            </div>
          </div>

          <button 
            onClick={() => onApply(job.id)}
            className="w-full bg-slate-900 hover:bg-blue-600 text-white py-2 rounded-lg flex items-center justify-center transition-colors font-medium"
          >
            <Send className="w-4 h-4 mr-2" /> Quick Apply
          </button>
        </div>
      ))}
    </div>
  );
}
