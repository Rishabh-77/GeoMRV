import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

/* ──────────────── Projects ──────────────── */
export const projectAPI = {
  list: () => apiClient.get('/projects?limit=500'),
  create: (data) => apiClient.post('/projects', data),
  get: (id) => apiClient.get(`/projects/${id}`),
  update: (id, data) => apiClient.put(`/projects/${id}`, data),
  delete: (id) => apiClient.delete(`/projects/${id}`),
  uploadBoundary: (id, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post(`/projects/${id}/upload-boundary`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getBoundary: (id) => apiClient.get(`/projects/${id}/boundary`),
};

/* ──────────────── Jobs ──────────────── */
export const jobAPI = {
  create: (data) => apiClient.post('/jobs', data),
  get: (id) => apiClient.get(`/jobs/${id}`),
  list: (projectId) =>
    apiClient.get(projectId ? `/jobs?project_id=${projectId}` : '/jobs'),
  observations: (projectId, startDate, endDate) => {
    const params = {};
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    return apiClient.get(`/jobs/projects/${projectId}/observations`, { params });
  },
};

/* ──────────────── Features ──────────────── */
export const featureAPI = {
  extract: (projectId, startDate, endDate) =>
    apiClient.post(
      `/features/${projectId}/extract?start_date=${startDate}&end_date=${endDate}`,
    ),
  latest: (projectId) => apiClient.get(`/features/${projectId}/latest`),
  history: (projectId, limit = 20) =>
    apiClient.get(`/features/${projectId}/history?limit=${limit}`),
};

/* ──────────────── Verification ──────────────── */
export const verificationAPI = {
  verify: (projectId, startDate, endDate) =>
    apiClient.post(
      `/verification/${projectId}/verify?start_date=${startDate}&end_date=${endDate}`,
    ),
  latest: (projectId) =>
    apiClient.get(`/verification/${projectId}/latest`),
  history: (projectId, limit = 20) =>
    apiClient.get(`/verification/${projectId}/history?limit=${limit}`),
};

/* ──────────────── ML Scoring ──────────────── */
export const mlAPI = {
  score: (projectId, startDate, endDate) =>
    apiClient.post(
      `/ml/score/${projectId}?start_date=${startDate}&end_date=${endDate}`,
    ),
  scoreAndVerify: (projectId, startDate, endDate) =>
    apiClient.post(
      `/ml/score-and-verify/${projectId}?start_date=${startDate}&end_date=${endDate}`,
    ),
  latest: (projectId) => apiClient.get(`/ml/${projectId}/latest`),
  history: (projectId, limit = 20) =>
    apiClient.get(`/ml/${projectId}/history?limit=${limit}`),
  status: () => apiClient.get('/ml/status'),
};

/* ──────────────── Evidence ──────────────── */
export const evidenceAPI = {
  list: (projectId) =>
    apiClient.get(projectId ? `/evidence?project_id=${projectId}` : '/evidence'),
  get: (evidenceId) => apiClient.get(`/evidence/${evidenceId}`),
  generate: (projectId, startDate, endDate) =>
    apiClient.post(`/evidence/${projectId}/generate`, {
      start_date: startDate,
      end_date: endDate,
    }),
  download: (packageId) =>
    apiClient.get(`/evidence/${packageId}/download`, { responseType: 'blob' }),
};

/* ──────────────── Timelapse ──────────────── */
export const timelapseAPI = {
  getUrl: (projectId, startDate, endDate) =>
    apiClient.get(`/projects/${projectId}/timelapse`, {
      params: { startDate, endDate },
    }),
};

/* ──────────────── Satellite Thumbnails ──────────────── */
export const thumbnailAPI = {
  get: (projectId, date) =>
    apiClient.get(`/projects/${projectId}/thumbnail`, {
      params: { date },
      timeout: 60000,  // GEE can take a while
    }),
};

/* ──────────────── Health ──────────────── */
export const healthAPI = {
  check: () => apiClient.get('/health', { baseURL: API_BASE.replace('/api/v1', '') }),
};
