import axios from "axios";

const API_BASE =
    import.meta.env.VITE_API_BASE || "http://localhost:8000";

export const api = axios.create({
    baseURL: API_BASE,
});

export async function createJob(file) {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await api.post("/jobs", formData);
    return data;
}

export async function startJob(jobId) {
    const { data } = await api.post(`/jobs/${jobId}/start`);
    return data;
}

export async function getJob(jobId) {
    const { data } = await api.get(`/jobs/${jobId}`);
    return data;
}

export async function getTransactions(jobId, page, pageSize, filter) {
    const { data } = await api.get(`/jobs/${jobId}/transactions`, {
        params: {
            page,
            page_size: pageSize,
            filter,
        },
    });
    return data;
}