import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const method = String(error?.config?.method || "GET").toUpperCase();
    const url = error?.config?.url || "";
    const isExpectedPrediction404 =
      status === 404 &&
      method === "GET" &&
      typeof url === "string" &&
      /^\/api\/v1\/predict\/matches\/\d+$/.test(url);

    if (!isExpectedPrediction404) {
      console.error("API Error:", status, error?.message, url);
    }
    return Promise.reject(error);
  }
);
