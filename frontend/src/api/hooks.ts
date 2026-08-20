// TanStack Query hooks + 管理员 mutation。
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  AuthConfigResp, AuthSettingsCfg, Condition, Fundamentals, FieldMeta, GroupItem, GroupMember, JobStatus, KlineView, NewsItem,
  Overview, PostsPage, Quote, ScheduleCfg, ScreenResp, SectorItem, SectorRankResp, StockAiAnalysisResp, SummaryResp,
  TradeNote, TradeRecord, TradeStats, UserItem,
  VisitorLoginResp, VisitorMeResp, WechatQrcodeResp, WechatPollResp,
} from "./types";

const get = async <T>(url: string, params?: object): Promise<T> =>
  (await api.get<T>(url, { params })).data;
const post = async <T>(url: string, body?: object): Promise<T> =>
  (await api.post<T>(url, body)).data;

// ===== 公开只读 =====
export const useUsers = () =>
  useQuery({ queryKey: ["users"], queryFn: () => get<UserItem[]>("/api/users") });

export const useOverview = (user?: string, days?: number) =>
  useQuery({ queryKey: ["overview", user, days ?? 7], queryFn: () => get<Overview>("/api/overview", { user, days: days ?? 7 }) });

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

export const useKline = (code: string, sp?: Record<string, number | boolean>) => {
  const spStr = sp && Object.keys(sp).length ? JSON.stringify(sp) : undefined;
  return useQuery({
    queryKey: ["kline", code, spStr],
    queryFn: () => get<KlineView>("/api/stock/kline", { code, ...(spStr ? { sp: spStr } : {}) }),
    enabled: !!code,
  });
};

export const useIndexKline = (code: string) =>
  useQuery({ queryKey: ["index_kline", code], queryFn: () => get<KlineView>("/api/index/kline", { code }), enabled: !!code, refetchInterval: 10_000 });

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

export const useSectorRank = () =>
  useQuery({ queryKey: ["sectors_rank"], queryFn: () => get<SectorRankResp>("/api/sectors/rank") });

export const useGroups = (isPaper = false) =>
  useQuery({ queryKey: ["groups", isPaper], queryFn: () => get<{ groups: GroupItem[] }>("/api/groups", { is_paper: isPaper || undefined }) });

export interface ScreenBody {
  strategies?: string[];
  conditions?: Condition[];
  name_query?: string;
  limit?: number;
  // 每个策略key -> 该策略的参数覆盖（不传/传空 = 用默认值，走预计算快路径）。
  strategy_params?: Record<string, Record<string, number | boolean>>;
  // user_ids 为空数组 = 全部大V；非空则只看这几位。
  mentioned?: { enabled: boolean; days: number; user_ids: string[]; bullish_only?: boolean };
  sector?: { enabled: boolean; mode: string; names: string[]; days: number; user_ids: string[] };
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

export const useAuthSettings = () =>
  useQuery({ queryKey: ["auth_settings"], queryFn: () => get<AuthSettingsCfg>("/api/auth-settings") });
export const useSaveAuthSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cfg: AuthSettingsCfg) => post<AuthSettingsCfg>("/api/auth-settings", cfg),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auth_settings"] }),
  });
};

// ===== 访客账号（手机号 + 验证码） =====
export const useAuthConfig = () =>
  useQuery({ queryKey: ["auth_config"], queryFn: () => get<AuthConfigResp>("/api/auth/config") });

export const useGuestLogin = () =>
  useMutation({ mutationFn: () => post<VisitorLoginResp>("/api/user/guest-login") });

export const useSendCode = () =>
  useMutation({ mutationFn: (b: { phone: string }) => post<{ error: string }>("/api/user/send-code", b) });

export const useVisitorLogin = () =>
  useMutation({ mutationFn: (b: { phone: string; code: string }) => post<VisitorLoginResp>("/api/user/login", b) });

export const useWechatCodeLogin = () =>
  useMutation({ mutationFn: (b: { code: string }) => post<VisitorLoginResp>("/api/user/wechat/code-login", b) });

// ===== 访客账号（邮箱注册 + 账密登录） =====
export const useSendEmailCode = () =>
  useMutation({ mutationFn: (b: { email: string }) => post<{ error: string }>("/api/user/email/send-code", b) });

export const useEmailRegister = () =>
  useMutation({
    mutationFn: (b: { email: string; code: string; password: string }) =>
      post<VisitorLoginResp>("/api/user/email/register", b),
  });

export const useEmailLogin = () =>
  useMutation({
    mutationFn: (b: { email: string; password: string }) => post<VisitorLoginResp>("/api/user/email/login", b),
  });

export const useVisitorMe = (enabled: boolean) =>
  useQuery({ queryKey: ["visitor_me"], queryFn: () => get<VisitorMeResp>("/api/user/me"), enabled });

export const useSetNickname = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (nickname: string) => post<{ error: string; nickname: string }>("/api/user/nickname", { nickname }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["visitor_me"] }),
  });
};

export const useWechatQrcode = () =>
  useQuery({ queryKey: ["wechat_qrcode"], queryFn: () => get<WechatQrcodeResp>("/api/user/wechat/qrcode") });

export const useWechatPoll = (sceneKey: string) =>
  useQuery({
    queryKey: ["wechat_poll", sceneKey],
    queryFn: () => get<WechatPollResp>(`/api/user/wechat/poll/${sceneKey}`),
    enabled: !!sceneKey,
    refetchInterval: (query) => (query.state.data?.status === "scanned" ? false : 2000),
  });
export const useGroupMutations = (isPaper = false) => {
  const qc = useQueryClient();
  const inval = () => qc.invalidateQueries({ queryKey: ["groups"] });
  const invalMembers = (id: number) => qc.invalidateQueries({ queryKey: ["group_members", id] });
  return {
    create: useMutation({ mutationFn: (name: string) => post("/api/groups", { name, is_paper: isPaper }), onSuccess: inval }),
    remove: useMutation({ mutationFn: (id: number) => api.delete(`/api/groups/${id}`).then((r) => r.data), onSuccess: inval }),
    addMembers: useMutation({
      mutationFn: (v: { id: number; stocks: { code: string; name: string }[] }) =>
        post(`/api/groups/${v.id}/members`, { stocks: v.stocks }),
      onSuccess: (_d, v) => { inval(); invalMembers(v.id); },
    }),
    removeMember: useMutation({
      mutationFn: (v: { groupId: number; code: string }) =>
        api.delete(`/api/groups/${v.groupId}/members/${v.code}`).then((r) => r.data),
      onSuccess: (_d, v) => { inval(); invalMembers(v.groupId); },
    }),
  };
};

export const useGroupMembers = (groupId: number | null) =>
  useQuery({
    queryKey: ["group_members", groupId],
    queryFn: () => get<{ items: GroupMember[] }>(`/api/groups/${groupId}/members`),
    enabled: groupId !== null,
  });

export const useTrades = (code?: string, isPaper = false) =>
  useQuery({
    queryKey: ["trades", code ?? "all", isPaper],
    queryFn: () => get<{ items: TradeRecord[] }>("/api/trades", { ...(code ? { code } : {}), is_paper: isPaper || undefined }),
  });

export const useTradeMutations = (isPaper = false) => {
  const qc = useQueryClient();
  const inval = () => {
    qc.invalidateQueries({ queryKey: ["trades"] });
    if (isPaper) qc.invalidateQueries({ queryKey: ["paper_account"] });
  };
  return {
    create: useMutation({
      mutationFn: (body: Omit<TradeRecord, "id" | "created_at">) => post("/api/trades", { ...body, is_paper: isPaper }),
      onSuccess: inval,
    }),
    remove: useMutation({
      mutationFn: (id: number) => api.delete(`/api/trades/${id}`, { params: { is_paper: isPaper || undefined } }).then((r) => r.data),
      onSuccess: inval,
    }),
    importTxt: useMutation({
      mutationFn: (file: File) => {
        const fd = new FormData();
        fd.append("file", file);
        return api.post<{ imported: number; total: number; error: string }>(
          "/api/trades/import",
          fd,
          { params: { is_paper: isPaper || undefined } },
        ).then((r) => r.data);
      },
      onSuccess: inval,
    }),
  };
};

export const useNoteList = (startDate?: string, endDate?: string, page = 1, pageSize = 20, favoriteOnly = false, isPaper = false) =>
  useQuery({
    queryKey: ["notes", startDate ?? null, endDate ?? null, page, pageSize, favoriteOnly, isPaper],
    queryFn: () =>
      get<{ items: TradeNote[]; total: number }>("/api/notes", {
        start_date: startDate,
        end_date: endDate,
        page,
        page_size: pageSize,
        favorite_only: favoriteOnly || undefined,
        is_paper: isPaper || undefined,
      }),
  });

export const useFavoriteNote = (isPaper = false) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (date: string) =>
      api.patch<{ note: TradeNote }>(`/api/notes/${date}/favorite`, null, { params: { is_paper: isPaper || undefined } }).then((r) => r.data),
    onSuccess: (_data, date) => {
      qc.invalidateQueries({ queryKey: ["notes"] });
      qc.invalidateQueries({ queryKey: ["note", date, isPaper] });
    },
  });
};

export const useNote = (date: string | null, isPaper = false) =>
  useQuery({
    queryKey: ["note", date, isPaper],
    queryFn: () => get<{ note: TradeNote | null }>("/api/notes", { date, is_paper: isPaper || undefined }),
    enabled: date !== null,
  });

export const useNoteMutation = (isPaper = false) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { date: string; content: string }) => post<{ note: TradeNote }>("/api/notes", { ...body, is_paper: isPaper }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["notes"] });
      qc.invalidateQueries({ queryKey: ["note", vars.date, isPaper] });
    },
  });
};

export const useGenerateNote = (isPaper = false) =>
  useMutation({
    mutationFn: (date: string) => post<{ content: string }>("/api/notes/generate", { date, is_paper: isPaper }),
  });

export const useDeleteNote = (isPaper = false) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (date: string) =>
      api.delete(`/api/notes`, { params: { date, is_paper: isPaper || undefined } }).then((r) => r.data),
    onSuccess: (_data, date) => {
      qc.invalidateQueries({ queryKey: ["notes"] });
      qc.invalidateQueries({ queryKey: ["note", date, isPaper] });
    },
  });
};

export const useBatchGenerateNotes = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { start_date: string; end_date: string }) =>
      post<{ generated: number; dates: string[] }>("/api/notes/batch-generate", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notes"] }),
  });
};

export const useTradeStats = (isPaper = false) =>
  useQuery({
    queryKey: ["trade_stats", isPaper],
    queryFn: () => get<{ stats: TradeStats }>("/api/trades/stats", { is_paper: isPaper || undefined }),
  });

// ===== 用户级与系统级设置 =====
export const useUserSettings = (key: string, enabled = true) =>
  useQuery({
    queryKey: ["user_settings", key],
    queryFn: () => get<{ key: string; value: unknown; error: string }>("/api/user/settings", { key }),
    enabled,
    staleTime: 5 * 60 * 1000,
  });

export const useSaveUserSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { key: string; value: unknown }) =>
      api.put<{ error: string }>("/api/user/settings", body).then((r) => r.data),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ["user_settings", vars.key] }),
  });
};

export const useSettingsDefaults = (key: string) =>
  useQuery({
    queryKey: ["settings_defaults", key],
    queryFn: () => get<{ key: string; value: unknown; error: string }>("/api/settings/defaults", { key }),
    staleTime: 5 * 60 * 1000,
  });

export const useSaveAdminSettingDefaults = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { key: string; value: unknown }) =>
      api.put<{ error: string }>("/api/admin/settings/defaults", body).then((r) => r.data),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ["settings_defaults", vars.key] }),
  });
};

export const useDeleteAdminSettingDefaults = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) =>
      api.delete<{ error: string }>("/api/admin/settings/defaults", { params: { key } }).then((r) => r.data),
    onSuccess: (_d, key) => qc.invalidateQueries({ queryKey: ["settings_defaults", key] }),
  });
};

// ===== 模拟盘资金账户 =====
export const usePaperAccount = () =>
  useQuery({
    queryKey: ["paper_account"],
    queryFn: () => get<{ balance: number; error: string }>("/api/trades/paper-account"),
  });

export const useResetPaperAccount = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (capital: number) =>
      api.post<{ balance: number; error: string }>("/api/trades/paper-account/reset", { capital }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["paper_account"] });
      qc.invalidateQueries({ queryKey: ["trades"] });
      qc.invalidateQueries({ queryKey: ["groups"] });
    },
  });
};

export const useStockAiAnalysis = (code: string, enabled: boolean) =>
  useQuery({
    queryKey: ["stock_ai_analysis", code],
    queryFn: () => get<StockAiAnalysisResp>("/api/stock/ai-analysis", { code }),
    enabled: enabled && !!code,
  });

export const useGenerateStockAiAnalysis = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      api.post<StockAiAnalysisResp>("/api/stock/ai-analysis/generate", null, { params: { code } }).then((r) => r.data),
    onSuccess: (_data, code) => qc.setQueryData(["stock_ai_analysis", code], _data),
  });
};
