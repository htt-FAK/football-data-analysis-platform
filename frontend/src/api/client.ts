import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// FastAPI 会对「路由声明带末尾斜杠、请求未带」的情况返回 307 重定向。
// 经 nginx 反代后，307 的 Location 可能指向错误端口，引发 CORS 跨域失败。
// 这里在请求发出前自动补齐末尾斜杠，从源头避免 307。
apiClient.interceptors.request.use((config) => {
  const url = config.url;
  if (typeof url === "string" && url.startsWith("/api/")) {
    // 拆出查询串，只给路径补斜杠
    const [path, search = ""] = url.split("?");
    if (!path.endsWith("/")) {
      config.url = path + "/" + (search ? "?" + search : "");
    }
  }
  return config;
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
