import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  icon?: LucideIcon;
  description?: string;
  trend?: { value: number; label?: string };
  className?: string;
}

export function StatCard({ title, value, icon: Icon, description, trend, className }: StatCardProps) {
  return (
    <Card className={cn("stat-card relative overflow-hidden", className)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-[0.15em]">
              {title}
            </p>
            <p className="font-display text-3xl font-black tracking-tight">{value}</p>
            {description && (
              <p className="text-xs text-muted-foreground">{description}</p>
            )}
            {trend && (
              <p className={cn(
                "text-xs font-bold flex items-center gap-1",
                trend.value >= 0 ? "text-emerald-400" : "text-rose-400"
              )}>
                <span className="font-mono">{trend.value >= 0 ? "▲" : "▼"} {Math.abs(trend.value)}%</span>
                {trend.label && <span className="text-muted-foreground font-normal"> · {trend.label}</span>}
              </p>
            )}
          </div>
          {Icon && (
            <div className="w-9 h-9 flex items-center justify-center border border-border bg-secondary/50">
              <Icon className="w-4 h-4 text-primary" />
            </div>
          )}
        </div>
      </CardContent>
      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-primary/40 via-primary/10 to-transparent" />
    </Card>
  );
}

export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-end justify-between mb-5">
      <div className="flex items-center gap-3">
        <div className="w-1 h-5 bg-primary" />
        <div>
          <h2 className="section-title text-lg">{title}</h2>
          {description && (
            <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
          )}
        </div>
      </div>
      {action}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-8">
      <div className="flex items-end justify-between">
        <div className="relative">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-px flex-1 w-8 bg-primary/40" />
            <span className="text-[10px] font-bold text-primary uppercase tracking-[0.2em]">
              世界杯数据专题
            </span>
          </div>
          <h1 className="font-display text-4xl font-black tracking-tight">{title}</h1>
          {description && (
            <p className="text-muted-foreground mt-2 text-sm">{description}</p>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
}) {
  return (
    <Card className="p-12 text-center">
      <CardHeader className="items-center">
        {Icon && (
          <div className="w-12 h-12 flex items-center justify-center bg-secondary/50 border border-border mb-3">
            <Icon className="w-6 h-6 text-muted-foreground" />
          </div>
        )}
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      {description && (
        <CardContent>
          <p className="text-sm text-muted-foreground">{description}</p>
        </CardContent>
      )}
    </Card>
  );
}

export function LoadingState({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-14 bg-secondary/30 animate-pulse" />
      ))}
    </div>
  );
}
