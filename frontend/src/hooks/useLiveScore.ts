/**
 * 实时比分 WebSocket 订阅 hook
 *
 * 后端已有 /ws 端点（按联赛订阅，25s 心跳超时），但前端从未接入。
 * 本 hook 用模块级单例管理连接，避免组件重复挂载导致多个连接：
 *   - 首次调用时连接 /ws，自动订阅世界杯联赛
 *   - 收到 match_update 时通过 queryClient.setQueryData 把实时比分
 *     合并进 ["match"] / ["matches","worldcup",...] / ["prediction"] 缓存
 *   - 每 20s 发心跳，断线自动重连（指数退避）
 *   - 组件用 useLiveScore() 注册「当某场比赛更新」的回调
 */

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getWorldCupSummary } from "@/api/worldcup";
import type { MatchPredictionResponse, WorldCupUpcomingMatch } from "@/types";

// 后端 WS_HEARTBEAT_INTERVAL=25s，这里留余量
const HEARTBEAT_INTERVAL_MS = 20_000;
const RECONNECT_BASE_MS = 1500;
const RECONNECT_MAX_MS = 30_000;

/** 后端推送的 match_update 消息数据 */
interface MatchUpdateData {
  match_id: number;
  league_id?: number;
  home_score?: number | null;
  away_score?: number | null;
  status?: string | null;
  match_date?: string | null;
  stage?: string | null;
  group?: string | null;
  source?: string;
}

interface ServerMessage {
  type: "ack" | "match_update" | "event" | "standing_update" | "pong" | "error";
  data?: MatchUpdateData;
  action?: string;
  league_ids?: number[];
  message?: string;
}

type MatchUpdateListener = (data: MatchUpdateData) => void;

// ── 模块级单例 ──
let socket: WebSocket | null = null;
let reconnectAttempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
let worldcupLeagueId: number | null = null;
let isConnecting = false;
// queryClient 在第一次调用时注入（避免循环依赖）
let cachedQueryClient: ReturnType<typeof useQueryClient> | null = null;
const listeners = new Set<MatchUpdateListener>();

function buildWsUrl(): string {
  const baseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) || "";
  if (baseUrl) {
    // http(s)://host → ws(s)://host
    return baseUrl.replace(/^http/i, "ws") + "/ws";
  }
  // 同源：用当前页面协议+host
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws`;
}

async function resolveWorldCupLeagueId(): Promise<number | null> {
  if (worldcupLeagueId != null) return worldcupLeagueId;
  try {
    const summary = await getWorldCupSummary("2026");
    if (summary?.league_id) {
      worldcupLeagueId = summary.league_id;
      return worldcupLeagueId;
    }
  } catch {
    // 拉取失败也不阻塞连接：连上后再补订阅
  }
  return null;
}

function startHeartbeat() {
  stopHeartbeat();
  heartbeatTimer = setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify({ action: "ping" }));
      } catch {
        // ignore
      }
    }
  }, HEARTBEAT_INTERVAL_MS);
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  const delay = Math.min(RECONNECT_BASE_MS * Math.pow(2, reconnectAttempt), RECONNECT_MAX_MS);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    reconnectAttempt += 1;
    connectLiveSocket();
  }, delay);
}

/** 把 WS 推来的比分合并进 React Query 缓存 */
function applyUpdateToCache(data: MatchUpdateData) {
  const qc = cachedQueryClient;
  if (!qc || data.match_id == null) return;

  // 1. ["match", matchId]（MatchDetail 用）
  qc.setQueriesData<{ home_score?: number | null; away_score?: number | null; status?: string | null }>(
    { queryKey: ["match", data.match_id] },
    (old) => (old ? { ...old, home_score: data.home_score ?? old.home_score, away_score: data.away_score ?? old.away_score, status: data.status ?? old.status } : old),
  );

  // 2. ["matches","worldcup",...]（MatchList / fixtures 用）—— 数组结构
  qc.setQueriesData<{ matches?: WorldCupUpcomingMatch[] } | WorldCupUpcomingMatch[]>(
    { queryKey: ["matches"] },
    (old) => {
      if (!old) return old;
      const matches = Array.isArray(old) ? old : (old as { matches?: WorldCupUpcomingMatch[] }).matches;
      if (!Array.isArray(matches)) return old;
      let changed = false;
      const next = matches.map((m) => {
        if (String(m.match_id) === String(data.match_id)) {
          changed = true;
          return {
            ...m,
            home_score: data.home_score ?? m.home_score,
            away_score: data.away_score ?? m.away_score,
            status: data.status ?? m.status,
          };
        }
        return m;
      });
      if (!changed) return old;
      return Array.isArray(old) ? next : { ...(old as object), matches: next };
    },
  );

  // 3. ["worldcup-upcoming", ...]（AIPredict fixtures 用）—— {matches: []}
  qc.setQueriesData<{ matches?: WorldCupUpcomingMatch[] }>(
    { queryKey: ["worldcup-upcoming"] },
    (old) => {
      if (!old || !Array.isArray(old.matches)) return old;
      let changed = false;
      const next = old.matches.map((m) => {
        if (String(m.match_id) === String(data.match_id)) {
          changed = true;
          return {
            ...m,
            home_score: data.home_score ?? m.home_score,
            away_score: data.away_score ?? m.away_score,
            status: data.status ?? m.status,
          };
        }
        return m;
      });
      return changed ? { ...old, matches: next } : old;
    },
  );

  // 4. ["prediction", matchId]（AIPredict 用）—— 更新真实比分
  qc.setQueriesData<MatchPredictionResponse | null>(
    { queryKey: ["prediction", data.match_id] },
    (old) => {
      if (!old) return old;
      // 比赛结束后的命中判定交给下次 HTTP 刷新，这里只更新比分展示
      return {
        ...old,
        real_home_score: data.home_score ?? old.real_home_score,
        real_away_score: data.away_score ?? old.real_away_score,
      };
    },
  );
}

function handleMessage(msg: ServerMessage) {
  if (msg.type === "match_update" && msg.data) {
    applyUpdateToCache(msg.data);
    listeners.forEach((fn) => {
      try {
        fn(msg.data as MatchUpdateData);
      } catch {
        // 单个监听器出错不影响其它
      }
    });
  }
}

async function connectLiveSocket() {
  if (isConnecting || (socket && socket.readyState === WebSocket.OPEN)) return;
  isConnecting = true;

  const leagueId = await resolveWorldCupLeagueId();

  let ws: WebSocket;
  try {
    ws = new WebSocket(buildWsUrl());
  } catch {
    isConnecting = false;
    scheduleReconnect();
    return;
  }
  socket = ws;

  ws.onopen = () => {
    isConnecting = false;
    reconnectAttempt = 0;
    startHeartbeat();
    // 订阅世界杯联赛（拿不到 id 就不订阅，后端仍会广播到该联赛的订阅者；
    // 拿到 id 才能确保收到推送）
    if (leagueId != null) {
      try {
        ws.send(JSON.stringify({ action: "subscribe", league_ids: [leagueId] }));
      } catch {
        // ignore
      }
    }
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data) as ServerMessage;
      handleMessage(msg);
    } catch {
      // 非 JSON 忽略
    }
  };

  ws.onerror = () => {
    // 错误后通常紧跟 onclose，统一在 close 里重连
  };

  ws.onclose = () => {
    isConnecting = false;
    socket = null;
    stopHeartbeat();
    scheduleReconnect();
  };
}

/** 注入 queryClient（在 hook 首次调用时） */
function ensureConnected(qc: ReturnType<typeof useQueryClient>) {
  cachedQueryClient = qc;
  if (!socket && !isConnecting) {
    void connectLiveSocket();
  }
}

/**
 * 订阅实时比分。
 * 传入回调即可在该场比赛更新时收到通知（例如触发 refetch 命中判定）。
 * 即便不传回调，WS 也会自动把比分合并进 React Query 缓存。
 */
export function useLiveScore(onUpdate?: MatchUpdateListener) {
  const qc = useQueryClient();
  const cbRef = useRef<MatchUpdateListener | undefined>(onUpdate);
  cbRef.current = onUpdate;

  useEffect(() => {
    ensureConnected(qc);
    if (!cbRef.current) return;
    const listener: MatchUpdateListener = (data) => cbRef.current?.(data);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, [qc]);
}
