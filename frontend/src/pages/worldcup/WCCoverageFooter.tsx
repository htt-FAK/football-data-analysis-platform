import { useQuery } from "@tanstack/react-query";
import { getWorldCupCoverage } from "@/api/worldcup";
import type { WorldCupCoverage } from "@/types";

function StatusIcon({ status }: { status: string }) {
  if (status === "ready") {
    return (
      <svg
        className="h-4 w-4 flex-shrink-0 text-[#22c55e]"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
        <polyline points="22 4 12 14.01 9 11.01" />
      </svg>
    );
  }

  if (status === "partial") {
    return (
      <svg
        className="h-4 w-4 flex-shrink-0 text-[#eab308]"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
        <path d="M21 3v5h-5" />
      </svg>
    );
  }

  return (
    <svg
      className="h-4 w-4 flex-shrink-0 text-[#64748b]"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5" />
      <circle cx="12" cy="16" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function WCCoverageFooter() {
  const { data } = useQuery<WorldCupCoverage>({
    queryKey: ["worldcup-coverage"],
    queryFn: () => getWorldCupCoverage(),
  });

  const modules = data?.coverage ?? [];

  return (
    <div className="py-12">
      <div className="mx-auto max-w-[1400px] px-4">
        <div className="mb-6 flex items-baseline justify-between">
          <h2 className="text-sm font-bold uppercase tracking-widest text-[#f1f5f9]">
            覆盖状态
          </h2>
          <span className="text-xs text-[#64748b]">{modules.length} 个后端模块</span>
        </div>

        {modules.length === 0 ? (
          <div className="text-sm text-[#94a3b8]">暂无覆盖状态快照。</div>
        ) : (
          <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-2">
            {modules.map((module) => (
              <div key={module.module} className="border-b border-[#23262d]/50 py-3">
                <div className="flex items-center gap-2">
                  <StatusIcon status={module.status} />
                  <span className="text-sm text-[#f1f5f9]">{module.module}</span>
                </div>
                {module.detail ? (
                  <div className="mt-1 pl-6 text-xs text-[#64748b]">{module.detail}</div>
                ) : null}
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-col items-start justify-between gap-4 border-t border-[#23262d] pt-6 text-xs text-[#64748b] md:flex-row md:items-center">
          <div>
            <span className="text-[#94a3b8]">数据来源:</span> 本地后端世界杯覆盖状态
          </div>
          <div>
            <span className="text-[#94a3b8]">赛季:</span> {data?.season ?? "2026"}
          </div>
          <div>
            <span className="font-medium text-[#f1f5f9]">前后端联调模式</span>
          </div>
        </div>
      </div>
    </div>
  );
}
