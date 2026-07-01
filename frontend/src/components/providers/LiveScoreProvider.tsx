/**
 * 全局实时比分 Provider —— 挂在 App 顶层，确保整条 WebSocket 连接
 * 在应用启动时建立，所有页面共享。
 */

import { type ReactNode } from "react";
import { useLiveScore } from "@/hooks/useLiveScore";

export function LiveScoreProvider({ children }: { children: ReactNode }) {
  // 不传回调：WS 连接建立后自动把比分合并进 React Query 缓存
  useLiveScore();
  return <>{children}</>;
}
