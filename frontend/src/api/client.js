const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';

const isAbsolutePath = (path) => path.startsWith('/api/') || path.startsWith('/health');

function buildUrl(path) {
  if (isAbsolutePath(path)) {
    return path;
  }
  return `${API_BASE}${path}`;
}

async function request(path, options = {}) {
  const token = localStorage.getItem('netvault_token');
  const response = await fetch(buildUrl(path), {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (response.status === 401) {
    localStorage.removeItem('netvault_token');
    localStorage.removeItem('netvault_user');
    window.location.href = '/login';
    return null;
  }

  if (response.status === 204) {
    return null;
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const detail = errorBody?.detail || `HTTP ${response.status}`;
    throw new Error(detail);
  }

  return response.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, body) =>
    request(path, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  put: (path, body) =>
    request(path, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  patch: (path, body) =>
    request(path, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  delete: (path) =>
    request(path, {
      method: 'DELETE',
    }),
};
