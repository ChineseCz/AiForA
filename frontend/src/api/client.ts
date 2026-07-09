// axios 实例：附带管理员 JWT（localStorage），401 时清 token。
import axios from "axios";

const TOKEN_KEY = "natapp_admin_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export const api = axios.create({ baseURL: "" });

api.interceptors.request.use((config) => {
  const t = getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      // token 失效：清除，让路由守卫把用户带回登录
      clearToken();
      window.dispatchEvent(new Event("natapp-unauthorized"));
    }
    return Promise.reject(err);
  },
);

/** 从 axios error 里取后端的中文错误信息。 */
export function errMsg(err: unknown, fallback = "请求失败"): string {
  const e = err as { response?: { data?: { error?: string; detail?: string } } };
  return e?.response?.data?.error || e?.response?.data?.detail || fallback;
}
