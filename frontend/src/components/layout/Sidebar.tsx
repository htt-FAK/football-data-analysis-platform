import { NavLink } from "react-router-dom";
import { Calendar, Globe2, Sparkles, User, Users } from "lucide-react";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/worldcup", label: "世界杯", icon: Globe2 },
  { to: "/teams", label: "球队", icon: Users },
  { to: "/players", label: "球员", icon: User },
  { to: "/matches", label: "比赛", icon: Calendar },
  { to: "/ai-predict", label: "AI 预测", icon: Sparkles },
];

export function Sidebar({ className }: { className?: string }) {
  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 flex h-screen w-56 flex-col border-r border-sidebar-border bg-sidebar",
        className
      )}
    >
      <div className="border-b border-sidebar-border px-5 pb-5 pt-6">
        <div className="flex items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center">
            <svg viewBox="0 0 40 40" className="h-10 w-10">
              <circle cx="20" cy="20" r="18" fill="none" stroke="hsl(142, 65%, 38%)" strokeWidth="1.5" />
              <path
                d="M20 5C13.5 10 10 15 10 20s3.5 10 10 15c6.5-5 10-10 10-15S26.5 10 20 5z"
                fill="none"
                stroke="hsl(142, 65%, 38%)"
                strokeWidth="1"
                opacity="0.5"
              />
              <path d="M5 20h30" stroke="hsl(142, 65%, 38%)" strokeWidth="0.8" opacity="0.5" />
              <circle cx="20" cy="20" r="2" fill="hsl(142, 65%, 38%)" />
              <text
                x="20"
                y="28"
                textAnchor="middle"
                fill="hsl(142, 65%, 38%)"
                fontSize="8"
                fontWeight="bold"
                fontFamily="Chivo, sans-serif"
              >
                SD
              </text>
            </svg>
          </div>
          <div>
            <div className="font-display text-base font-black leading-none tracking-tight text-foreground">
              世界<span className="text-primary">杯</span>
            </div>
            <div className="mt-1 text-[9px] font-bold uppercase tracking-widest text-muted-foreground">
              足球数据专题
            </div>
          </div>
        </div>
      </div>

      <div className="px-3 pt-2">
        <div className="px-3 py-2 text-[9px] font-bold uppercase tracking-[0.2em] text-muted-foreground/50">
          导航
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-1">
        {NAV_ITEMS.map((item) => (
          <SidebarLink key={item.to} to={item.to} label={item.label} Icon={item.icon} />
        ))}
      </nav>

      <div className="border-t border-sidebar-border px-4 py-3 text-right">
        <span className="font-mono text-[9px] text-muted-foreground/60">v1.0.0</span>
      </div>
    </aside>
  );
}

function SidebarLink({
  to,
  label,
  Icon,
}: {
  to: string;
  label: string;
  Icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <NavLink
      to={to}
      end={to === "/worldcup"}
      className={({ isActive }) => cn("nav-item group", isActive && "nav-item-active")}
    >
      <Icon className="h-4 w-4 flex-shrink-0" />
      <span>{label}</span>
    </NavLink>
  );
}
