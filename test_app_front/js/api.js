const API_URL = window.API_URL || 'http://localhost:8080';

const api = {
    async get(path) {
        const res = await fetch(`${API_URL}${path}`);
        if (!res.ok) {
            const err = await res.text();
            throw new Error(`GET ${path}: ${res.status} ${err}`);
        }
        return res.json();
    },

    async post(path, data) {
        const res = await fetch(`${API_URL}${path}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!res.ok) {
            const err = await res.text();
            throw new Error(`POST ${path}: ${res.status} ${err}`);
        }
        return res.json();
    },

    async put(path, data) {
        const res = await fetch(`${API_URL}${path}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!res.ok) {
            const err = await res.text();
            throw new Error(`PUT ${path}: ${res.status} ${err}`);
        }
        return res.json();
    },

    async del(path) {
        const res = await fetch(`${API_URL}${path}`, { method: 'DELETE' });
        if (!res.ok) {
            const err = await res.text();
            throw new Error(`DELETE ${path}: ${res.status} ${err}`);
        }
        return res.json();
    },
};
