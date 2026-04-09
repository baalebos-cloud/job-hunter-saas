import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://3.92.202.104:8000"
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
