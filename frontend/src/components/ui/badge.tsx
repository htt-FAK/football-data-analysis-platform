import * as React from "react";
import { cn } from "@/lib/utils";

const Badge = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & {
    variant?: "default" | "secondary" | "success" | "warning" | "danger" | "outline" | "gold";
  }
>(({ className, variant = "default", ...props }, ref) => {
  const variantClasses = {
    default: "bg-primary/15 text-primary font-semibold",
    secondary: "bg-secondary text-secondary-foreground",
    success: "bg-emerald-500/15 text-emerald-400 font-semibold",
    warning: "bg-amber-500/15 text-amber-400 font-semibold",
    danger: "bg-rose-500/15 text-rose-400 font-semibold",
    gold: "bg-amber-500/15 text-amber-400 font-semibold border border-amber-500/30",
    outline: "border border-border text-muted-foreground",
  };
  return (
    <div
      ref={ref}
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
});
Badge.displayName = "Badge";

export { Badge };
