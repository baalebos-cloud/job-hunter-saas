import axios from 'axios';

const api = axios.create({
  // Point this directly to your Railway backend
  baseURL: import.meta.env.VITE_API_URL || "https://job-hunter-saas-production-bb41.up.railway.app/api/v1"
});

// Automatic Token Injection
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
