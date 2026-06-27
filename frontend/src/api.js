export async function api(path, options = {}) {
    const response = await fetch(`/api${path}`, { credentials: 'include', headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options });
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `请求失败 (${response.status})`);
    }
    return response.status === 204 ? undefined : response.json();
}
export async function upload(path, file) {
    const form = new FormData();
    form.append('file', file);
    const response = await fetch(`/api${path}`, { method: 'POST', credentials: 'include', body: form });
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || '导入失败');
    }
    return response.json();
}
