// TanStack Query hooks + 管理员 mutation。
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  Condition, Fundamentals, FieldMeta, GroupItem, JobStatus, KlineView, NewsItem,
  Overview, PostsPage, Quote, ScheduleCfg, ScreenResp, SectorItem, SummaryResp, UserItem,
} from "./types";

const get = async <T>(url: string, params?: object): Promise<T> =>
  (await api.get<T>(url, { params })).data;
const post = async <T>(url: string, body?: object): Promise<T> =>
  (await api.post<T>(url, body)).data;

// ===== 公开只读 =====
export const useUsers = () =>
  useQuery({ queryKey: ["users"], queryFn: () => get<UserItem[]>("/api/users") });

export const useOverview = (user?: string) =>
  useQuery({ queryKey: ["overview", user], queryFn: () => get<Overview>("/api/overview", { user }) });

export const usePosts = (p: { user?: string; start?: string; end?: string; q?: string; page: number; size: number }) =>
  useQuery({ queryKey: ["posts", p], queryFn: () => get<PostsPage>("/api/posts", p) });

export const useSummaryKeys = (user: string, type: string) =>
  useQuery({
    queryKey: ["summary_keys", user, type],
    queryFn: () => get<string[]>("/api/summary_keys", { user, type }),
    enabled: !!user,
  });

export const useSummary = (user: string, type: string, key: string) =>
  useQuery({
    queryKey: ["summary", user, type, key],
    queryFn: () => get<SummaryResp>("/api/summary", { user, type, key }),
    enabled: !!user && !!key,
  });

export const useScreenFields = () =>
  useQuery({ queryKey: ["screen_fields"], queryFn: () => get<FieldMeta[]>("/api/screen/fields") });

export const useSectors = () =>
  useQuery({ queryKey: ["sectors"], queryFn: () => get<SectorItem[]>("/api/screen/sectors") });

export const useKline = (code: string) =>
  useQuery({ queryKey: ["kline", code], queryFn: () => get<KlineView>("/api/stock/kline", { code }), enabled: !!code });

export const useFundamentals = (code: string) =>
  useQuery({ queryKey: ["fundamentals", code], queryFn: () => get<Fundamentals>("/api/stock/fundamentals", { code }), enabled: !!code });

export const useNews = (code: string) =>
  useQuery({ queryKey: ["news", code], queryFn: () => get<{ items: NewsItem[] }>("/api/stock/news", { code }), enabled: !!code });

// 秒级轮询实时价格（仅用于合并展示到最后一根K线，不影响 MA/MACD/KDJ 等日级指标）。
// refetchIntervalInBackground 默认 false：切到后台标签页/锁屏后自动停止轮询，省流量电量。
export const useQuote = (code: string) =>
  useQuery({
    queryKey: ["quote", code],
    queryFn: () => get<Quote>("/api/stock/quote", { code }),
    enabled: !!code,
    refetchInterval: 1000,
    staleTime: 0,
  });

export const useGroups = () =>
  useQuery({ queryKey: ["groups"], queryFn: () => get<{ groups: GroupItem[] }>("/api/groups") });

export interface ScreenBody {
  strategies?: string[];
  conditions?: Condition[];
  name_query?: string;
  limit?: number;
  mentioned?: { enabled: boolean; days: number; user_id: string; bullish_only?: boolean };
  sector?: { enabled: boolean; mode: string; names: string[]; days: number; user_id: string };
}
export const useScreen = () =>
  useMutation({ mutationFn: (body: ScreenBody) => post<ScreenResp>("/api/screen", body) });
export const usePreset = () =>
  useMutation({ mutationFn: (body: ScreenBody) => post<ScreenResp>("/api/screen/preset", body) });

// ===== 管理员 =====
export const useLogin = () =>
  useMutation({
    mutationFn: (b: { username: string; password: string }) =>
      post<{ access_token: string; username: string }>("/api/admin/login", b),
  });

export const useJobStatus = (kind: string, path: string, polling: boolean) =>
  useQuery({
    queryKey: ["jobstatus", kind],
    queryFn: () => get<JobStatus>(path),
    refetchInterval: polling ? 1500 : false,
  });

export const useTrigger = (path: string, body?: object) =>
  useMutation({ mutationFn: () => post<{ started: boolean; running: boolean }>(path, body) });

export const useSchedule = () =>
  useQuery({ queryKey: ["schedule"], queryFn: () => get<ScheduleCfg>("/api/schedule") });
export const useSaveSchedule = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cfg: ScheduleCfg) => post<ScheduleCfg>("/api/schedule", cfg),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedule"] }),
  });
};

export const useAsk = () =>
  useMutation({
    mutationFn: (b: { user: string; type: string; key: string; question: string }) =>
      post<{ answer: string; html: string }>("/api/summary/ask", b),
  });

// 分组写
export const useGroupMutations = () => {
  const qc = useQueryClient();
  const inval = () => qc.invalidateQueries({ queryKey: ["groups"] });
  return {
    create: useMutation({ mutationFn: (name: string) => post("/api/groups", { name }), onSuccess: inval }),
    remove: useMutation({ mutationFn: (id: number) => api.delete(`/api/groups/${id}`).then((r) => r.data), onSuccess: inval }),
    addMembers: useMutation({
      mutationFn: (v: { id: number; stocks: { code: string; name: string }[] }) =>
        post(`/api/groups/${v.id}/members`, { stocks: v.stocks }),
      onSuccess: inval,
    }),
  };
};
