import { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

// Must match CAREER_TRACKS in Signup.jsx
const CAREER_TRACKS = [
  { value: 'Frontend Developer', label: '🎨 Frontend Developer' },
  { value: 'Backend Developer', label: '⚙️ Backend Developer' },
  { value: 'Full Stack Developer', label: '🔥 Full Stack Developer' },
  { value: 'DevOps Engineer', label: '🚀 DevOps Engineer' },
  { value: 'Data Engineer', label: '📊 Data Engineer' },
  { value: 'Data Scientist', label: '🧠 Data Scientist' },
  { value: 'Machine Learning Engineer', label: '🤖 ML Engineer' },
  { value: 'Cloud Engineer', label: '☁️ Cloud Engineer' },
  { value: 'Cybersecurity Engineer', label: '🔒 Cybersecurity' },
  { value: 'Product Manager', label: '📋 Product Manager' },
  { value: 'UI/UX Designer', label: '✏️ UI/UX Designer' },
  { value: 'Mobile Developer', label: '📱 Mobile Developer' },
];

export default function ResumeUpload({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [jobTitle, setJobTitle] = useState("");
  const [jobDesc, setJobDesc] = useState("");
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (e) => {
    e.preventDefault();

    const token = localStorage.getItem("token");

    if (!token) {
      alert("Please login to use the AI Optimizer.");
      window.location.href = "/login";
      return;
    }

    if (!file || !jobTitle || !jobDesc) {
      alert("Please provide a Job Title, Job Description, and your Resume.");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("job_description", jobDesc);
    formData.append("job_title", jobTitle.trim());

    try {
      const res = await axios.post(`${API_BASE_URL}/resume/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${token}`
        }
      });

      const taskId = res.data.task_id;

      if (taskId) {
        console.log("Baalebos AI Task Started:", taskId);
        if (onUploadSuccess) onUploadSuccess(taskId);
      } else {
        alert("Server received the file but didn't start the task. Check backend logs.");
      }
    } catch (err) {
      console.error("Upload Error:", err);
      const errorMsg = err.response?.data?.detail || "Upload failed. Verify your connection.";
      alert(typeof errorMsg === 'string' ? errorMsg : "Check all fields and try again.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-white p-8 md:p-12 rounded-[2rem] shadow-2xl shadow-slate-200/50 border border-slate-100 max-w-3xl mx-auto my-8">
      <div className="text-center mb-10">
        <h2 className="text-3xl font-black text-slate-900 tracking-tight uppercase">AI Engine</h2>
        <p className="text-slate-400 font-medium mt-2">Optimization Core v1.5</p>
      </div>

      <form onSubmit={handleUpload} className="space-y-6">

        {/* Job Title — supports free text OR career track selection */}
        <div>
          <label className="block text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2 ml-1">
            Target Job Title
          </label>
          <div className="space-y-2">
            {/* Quick select from career tracks */}
            <div className="relative">
              <select
                className="w-full p-4 rounded-2xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500 focus:bg-white transition-all font-bold appearance-none cursor-pointer pr-10"
                style={{ color: jobTitle ? '#0f172a' : '#94a3b8' }}
                value={CAREER_TRACKS.find(t => t.value === jobTitle) ? jobTitle : ''}
                onChange={(e) => setJobTitle(e.target.value)}
              >
                <option value="" disabled>Quick select your track...</option>
                {CAREER_TRACKS.map(track => (
                  <option key={track.value} value={track.value} style={{ color: '#0f172a' }}>
                    {track.label}
                  </option>
                ))}
              </select>
              <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">▾</span>
            </div>
            {/* Or type custom */}
            <div className="flex items-center gap-2">
              <div className="flex-1 h-px bg-slate-200" />
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">or type custom</span>
              <div className="flex-1 h-px bg-slate-200" />
            </div>
            <input
              type="text"
              placeholder="e.g. Senior DevOps Engineer"
              className="w-full p-4 rounded-2xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500 focus:bg-white transition-all !text-slate-900 font-bold placeholder:text-slate-300"
              style={{ color: '#0f172a' }}
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
            />
          </div>
          <p className="text-[10px] text-slate-400 mt-1.5 ml-1">
            This is used to match you with relevant jobs after the analysis.
          </p>
        </div>

        {/* Job Description */}
        <div>
          <label className="block text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2 ml-1">
            Job Description
          </label>
          <textarea
            rows="5"
            required
            placeholder="Paste the full job description here — the AI will extract keywords and score your resume against it..."
            className="w-full p-4 rounded-2xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500 focus:bg-white transition-all !text-slate-900 font-medium text-sm placeholder:text-slate-300 resize-none"
            style={{ color: '#0f172a' }}
            value={jobDesc}
            onChange={(e) => setJobDesc(e.target.value)}
          />
        </div>

        {/* File Upload */}
        <div className="relative group">
          <input
            type="file"
            id="resume-upload"
            className="hidden"
            onChange={(e) => setFile(e.target.files[0])}
            accept=".pdf,.docx,.doc"
          />
          <label
            htmlFor="resume-upload"
            className="flex flex-col items-center justify-center border-2 border-dashed border-slate-200 rounded-2xl p-10 cursor-pointer hover:border-emerald-400 hover:bg-emerald-50/30 transition-all bg-slate-50/50 group-hover:scale-[1.01]"
          >
            <div className="text-4xl mb-3">{file ? '✅' : '📄'}</div>
            <p className="text-slate-900 font-bold text-sm">
              {file ? file.name : "Click to Upload Your Resume"}
            </p>
            <p className="text-slate-400 text-xs mt-1">
              {file ? `${(file.size / 1024).toFixed(0)} KB` : "PDF, DOCX, or DOC — max 10MB"}
            </p>
          </label>
        </div>

        <button
          type="submit"
          disabled={uploading || !file || !jobTitle || !jobDesc}
          className={`w-full py-5 rounded-2xl font-black uppercase tracking-widest text-xs text-white shadow-xl transition-all active:scale-[0.98] ${
            uploading || !file || !jobTitle || !jobDesc
              ? 'bg-slate-300 cursor-not-allowed'
              : 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-600/20'
          }`}
        >
          {uploading ? "🚀 Analyzing Infrastructure..." : "Run AI Analysis →"}
        </button>

        {(!file || !jobTitle || !jobDesc) && (
          <p className="text-center text-xs text-slate-400">
            {!jobTitle ? 'Select or type a job title' : !jobDesc ? 'Paste a job description' : 'Upload your resume'} to enable analysis
          </p>
        )}
      </form>
    </div>
  );
}