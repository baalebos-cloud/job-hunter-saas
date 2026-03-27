import { useState } from 'react';
import axios from 'axios';

export default function ResumeUpload({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [jobTitle, setJobTitle] = useState("");
  const [jobDesc, setJobDesc] = useState("");
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file || !jobTitle || !jobDesc) return alert("Please fill all fields and select a file.");

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("job_description", jobDesc);
    formData.append("job_title", jobTitle);
    formData.append("user_email", "baalebos@example.com"); // Replace with auth later

    try {
      const res = await axios.post("http://127.0.0.1:8000/resume/upload", formData);
      alert("Analysis started! Task ID: " + res.data.task_id);
      if (onUploadSuccess) onUploadSuccess(res.data.task_id);
    } catch (err) {
      console.error(err);
      alert("Upload failed. Make sure the backend is running.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100 max-w-2xl mx-auto my-8">
      <h2 className="text-2xl font-bold text-slate-900 mb-6 text-center">Baalebos AI Matcher</h2>
      
      <form onSubmit={handleUpload} className="space-y-4">
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-1">Target Job Title</label>
          <input 
            type="text" 
            placeholder="e.g. Senior Cloud Architect"
            className="w-full p-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-emerald-500 outline-none"
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-1">Job Description</label>
          <textarea 
            rows="4"
            placeholder="Paste the full job requirements here..."
            className="w-full p-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-emerald-500 outline-none"
            value={jobDesc}
            onChange={(e) => setJobDesc(e.target.value)}
          ></textarea>
        </div>

        <div className="border-2 border-dashed border-slate-200 rounded-2xl p-8 text-center hover:border-emerald-400 transition-colors bg-slate-50">
          <input 
            type="file" 
            id="resume-upload" 
            className="hidden" 
            onChange={(e) => setFile(e.target.files[0])}
            accept=".pdf,.docx,.doc"
          />
          <label htmlFor="resume-upload" className="cursor-pointer">
            <div className="text-slate-400 mb-2">📄</div>
            <p className="text-slate-600 font-medium">
              {file ? file.name : "Click to upload or drag & drop"}
            </p>
            <p className="text-xs text-slate-400 mt-1">PDF or DOCX (Max 5MB)</p>
          </label>
        </div>

        <button 
          type="submit"
          disabled={uploading}
          className={`w-full py-4 rounded-xl font-bold text-white transition-all ${uploading ? 'bg-slate-400' : 'bg-emerald-600 hover:bg-emerald-700'}`}
        >
          {uploading ? "Analyzing with NLP..." : "Calculate ATS Match"}
        </button>
      </form>
    </div>
  );
}
