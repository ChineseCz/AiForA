// axios 实例：附带管理员/访客 JWT（localStorage），401 时清对应 token。
import axios from "axios";

const TOKEN_KEY = "natapp_admin_token";
const VISITOR_TOKEN_KEY = "natapp_visitor_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function getVisitorToken(): string | null {
  return localStorage.getItem(VISITOR_TOKEN_KEY);
}
export function setVisitorToken(t: string) {
  localStorage.setItem(VISITOR_TOKEN_KEY, t);
}
export function clearVisitorToken() {
  localStorage.removeItem(VISITOR_TOKEN_KEY);
}

export const api = axios.create({ baseURL: "" });

// 两个 token 都可能存在（管理员同时也能过访客/匿名开关的只读接口）：管理员优先。
api.interceptors.request.use((config) => {
  const t = getToken() || getVisitorToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      // token 失效：清除请求时实际附带的那个 token，让对应的路由守卫把用户带回登录
      if (getToken()) {
        clearToken();
        window.dispatchEvent(new Event("natapp-unauthorized"));
      } else {
        clearVisitorToken();
        window.dispatchEvent(new Event("natapp-visitor-unauthorized"));
      }
    }
    return Promise.reject(err);
  },
);

/** 从 axios error 里取后端的中文错误信息。 */
export function errMsg(err: unknown, fallback = "请求失败"): string {
  const e = err as { response?: { data?: { error?: string; detail?: string } } };
  return e?.response?.data?.error || e?.response?.data?.detail || fallback;
}
