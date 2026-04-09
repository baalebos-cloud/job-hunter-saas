import { useState } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || "https://baalebo.xyz/api/v1";

export default function ResumeUpload({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [jobTitle, setJobTitle] = useState("");
  const [jobDesc, setJobDesc] = useState("");
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (e) => {
    e.preventDefault();

    const token = localStorage.getItem("token");

    // BACKEND CHECK: The route requires a logged-in user (get_current_user)
    if (!token) {
      alert("Please login to use the AI Optimizer.");
      window.location.href = "/login";
      return;
    }

    if (!file || !jobTitle || !jobDesc) {
      alert("Please provide a Job Title, Description, and your Resume.");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("job_description", jobDesc);
    formData.append("job_title", jobTitle); // Matches backend parameter name

    try {
      const res = await axios.post(`${API_BASE_URL}/resume/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${token}` // Critical for the 'get_current_user' dependency
        }
      });

      // BACKEND MATCH: The backend returns { "task_id": "..." }
      const taskId = res.data.task_id;

      if (taskId) {
        console.log("Baalebos AI Task Started:", taskId);
        
        // This is where the download URL is constructed for the final output
        const downloadUrl = `${API_BASE_URL}/output/download/${taskId}`;
        console.log("Future Download Path:", downloadUrl);

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
        <div>
          <label className="block text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2 ml-1">Target Job Title</label>
          <input
            type="text"
            required
            placeholder="e.g. DevOps Engineer"
            className="w-full p-4 rounded-2xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500 focus:bg-white transition-all font-bold"
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2 ml-1">Job Description</label>
          <textarea
            rows="5"
            required
            placeholder="Paste requirements here..."
            className="w-full p-4 rounded-2xl border border-slate-200 bg-slate-50 outline-none focus:border-emerald-500 focus:bg-white transition-all font-medium text-sm"
            value={jobDesc}
            onChange={(e) => setJobDesc(e.target.value)}
          ></textarea>
        </div>

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
            className="flex flex-col items-center justify-center border-2 border-dashed border-slate-200 rounded-2xl p-10 cursor-pointer hover:border-emerald-400 hover:bg-emerald-50/30 transition-all bg-slate-50/50"
          >
            <div className="text-4xl mb-2">📄</div>
            <p className="text-slate-900 font-bold text-sm">
              {file ? file.name : "Upload Master Resume"}
            </p>
          </label>
        </div>

        <button
          type="submit"
          disabled={uploading}
          className={`w-full py-5 rounded-2xl font-black uppercase tracking-widest text-xs text-white shadow-xl transition-all ${
            uploading ? 'bg-slate-300' : 'bg-emerald-600 hover:bg-emerald-500'
          }`}
        >
          {uploading ? "Analyzing Infrastructure..." : "Run Analysis →"}
        </button>
      </form>
    </div>
  );
}
