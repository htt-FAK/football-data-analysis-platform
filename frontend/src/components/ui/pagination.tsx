import { cn } from "@/lib/utils";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ currentPage, totalPages, onPageChange }: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages: (number | string)[] = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    pages.push(1);
    if (currentPage > 3) pages.push("...");
    const start = Math.max(2, currentPage - 1);
    const end = Math.min(totalPages - 1, currentPage + 1);
    for (let i = start; i <= end; i++) pages.push(i);
    if (currentPage < totalPages - 2) pages.push("...");
    pages.push(totalPages);
  }

  return (
    <div className="flex items-center justify-center gap-1 mt-6">
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="px-3 py-1.5 text-xs font-semibold border border-border rounded-md hover:bg-secondary/60 disabled:opacity-30 disabled:pointer-events-none transition-colors"
      >
        上一页
      </button>
      {pages.map((p, i) =>
        typeof p === "number" ? (
          <button
            key={i}
            onClick={() => onPageChange(p)}
            className={cn(
              "w-8 h-8 text-xs font-bold rounded-md transition-colors",
              p === currentPage
                ? "bg-primary text-primary-foreground"
                : "border border-border hover:bg-secondary/60"
            )}
          >
            {p}
          </button>
        ) : (
          <span key={i} className="px-1 text-muted-foreground text-xs">{p}</span>
        )
      )}
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="px-3 py-1.5 text-xs font-semibold border border-border rounded-md hover:bg-secondary/60 disabled:opacity-30 disabled:pointer-events-none transition-colors"
      >
        下一页
      </button>
    </div>
  );
}
