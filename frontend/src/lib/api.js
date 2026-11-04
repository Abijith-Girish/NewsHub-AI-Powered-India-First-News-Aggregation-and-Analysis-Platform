import axios from 'axios';

export const TOKEN_KEY = 'newshub.token';

export const api = axios.create({
  baseURL: '/api',
  timeout: 45000,
  headers: { Accept: 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

/** Turn an API/network failure into one readable sentence for the UI. */
export function apiErrorMessage(error) {
  if (!error) return 'Something went wrong.';
  if (error.code === 'ERR_CANCELED') return 'Request cancelled.';
  if (error.code === 'ECONNABORTED') {
    return 'The request took too long. News providers can be slow — please try again.';
  }
  const data = error.response?.data;
  if (typeof data === 'string' && data.trim()) return data;
  if (data?.detail) return data.detail;
  if (data && typeof data === 'object') {
    const [field, value] = Object.entries(data)[0] || [];
    if (Array.isArray(value) && value[0]) return `${field}: ${value[0]}`;
    if (typeof value === 'string') return `${field}: ${value}`;
  }
  if (error.response?.status === 401) return 'Please sign in to continue.';
  if (error.response?.status === 403) return 'You do not have access to this resource.';
  if (error.response?.status === 404) return 'That page or article could not be found.';
  if (!error.response) {
    return 'Cannot reach the NewsHub API. Check that the Django server is running.';
  }
  return 'The server could not complete that request. Please try again.';
}

const longRequest = { timeout: 75000 };

export const newsApi = {
  list: (params) => api.get('/news/', { params }),
  latest: (params) => api.get('/news/latest/', { params }),
  breaking: () => api.get('/news/breaking/'),
  trending: () => api.get('/news/trending/'),
  search: (params) => api.get('/news/search/', { params, ...longRequest }),
  recommended: (params) => api.get('/news/recommended/', { params }),
  articlesByCategory: (slug, params) =>
    api.get(`/news/category/${slug}/`, { params }),
  article: (id) => api.get(`/news/${id}/`),
  articleContent: (id) => api.get(`/news/${id}/content/`, longRequest),
  recommendations: (id) => api.get(`/news/${id}/recommendations/`),
  save: (id) => api.post(`/news/${id}/save/`),
  unsave: (id) => api.delete(`/news/${id}/save/`),
  saved: () => api.get('/user/saved-news/'),
  categories: () => api.get('/categories/'),
  sources: () => api.get('/news/sources/'),
  health: () => api.get('/health/'),
  newsLens: (id) => api.get(`/news/${id}/newslens/`),
  recordReading: (payload) => api.post('/analytics/reading-event/', payload),
  readingAnalytics: () => api.get('/analytics/reading/'),
  briefing: () => api.get('/ai/daily-briefing/'),
  trackClaim: (payload) => api.post('/truth-trace/', payload),
  trackedClaims: () => api.get('/truth-trace/'),
  trackedClaim: (id) => api.get(`/truth-trace/${id}/`),
  deleteTrackedClaim: (id) => api.delete(`/truth-trace/${id}/`),
};

export const aiApi = {
  summarize: (payload) => api.post('/ai/summarize/', payload, longRequest),
  sentiment: (payload) => api.post('/ai/sentiment/', payload, longRequest),
  categorize: (payload) => api.post('/ml/categorize/', payload),
  metrics: () => api.get('/ml/metrics/'),
  translate: (payload) => api.post('/ai/translate/', payload, longRequest),
};

export const factCheckApi = {
  analyze: (payload) => api.post('/fact-check/', payload, longRequest),
  detail: (id) => api.get(`/fact-check/${id}/`),
  history: () => api.get('/fact-check/history/'),
};

export const authApi = {
  register: (payload) => api.post('/auth/register/', payload),
  login: (payload) => api.post('/auth/login/', payload),
  logout: () => api.post('/auth/logout/'),
  profile: () => api.get('/auth/profile/'),
  updateProfile: (payload) => api.patch('/auth/profile/', payload),
  preferences: () => api.get('/user/preferences/'),
  updatePreferences: (payload) => api.put('/user/preferences/', payload),
};

export const adminApi = {
  dashboard: () => api.get('/admin/dashboard/'),
  articles: (params) => api.get('/admin/news/', { params }),
  article: (id) => api.get(`/admin/news/${id}/`),
  createArticle: (payload) => api.post('/admin/news/', payload),
  updateArticle: (id, payload) => api.patch(`/admin/news/${id}/`, payload),
  deleteArticle: (id) => api.delete(`/admin/news/${id}/`),
  setCategory: (id, payload) => api.post(`/admin/news/${id}/category/`, payload),
  reviewQueue: () => api.get('/admin/review-queue/'),
  categories: () => api.get('/admin/categories/'),
  createCategory: (payload) => api.post('/admin/categories/', payload),
  updateCategory: (id, payload) => api.patch(`/admin/categories/${id}/`, payload),
  deleteCategory: (id) => api.delete(`/admin/categories/${id}/`),
  users: () => api.get('/admin/users/'),
  factChecks: () => api.get('/admin/fact-checks/'),
  ingest: (scope = 'general') => api.post('/admin/ingest/', { scope }, longRequest),
};
