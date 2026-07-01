import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, MapPin, Search, Shield, User, Users } from "lucide-react";

import { useDebounce } from "@/lib/hooks";
import { getTeamIdentity } from "@/lib/utils";
import { getTeams } from "@/api/teams";
import type { Team } from "@/types";

const WORLD_CUP_LEAGUE_ID = 3;

export function TeamList() {
  const [searchQuery, setSearchQuery] = useState<string>("");
  const debouncedSearchQuery = useDebounce(searchQuery, 300);
  const effectiveLeagueId = WORLD_CUP_LEAGUE_ID;
  const effectiveSearch = debouncedSearchQuery.trim() || undefined;

  const { data: teams = [], isLoading: teamsLoading } = useQuery<Team[]>({
    queryKey: ["teams", effectiveLeagueId ?? "all", effectiveSearch ?? ""],
    queryFn: () => getTeams(effectiveLeagueId, effectiveSearch),
  });

  const filteredTeams = useMemo(() => teams, [teams]);

  return (
    <div className="min-h-screen bg-[#0d0f12] text-[#f1f5f9]">
      <div className="mx-auto max-w-[1400px] px-4 py-10">
        <div className="mb-10 flex items-center justify-between">
          <div>
            <div className="mb-3 text-[10px] uppercase tracking-[0.25em] text-[#64748b]">2026 世界杯</div>
            <div className="flex items-baseline gap-4">
              <h1 className="text-3xl font-black tracking-tight md:text-4xl">球队中心</h1>
              <div className="flex items-center gap-2 text-xs text-[#64748b]">
                <Users className="h-3.5 w-3.5" />
                <span className="font-mono">{filteredTeams.length} 支球队</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#64748b]" />
              <input
                type="text"
                placeholder="搜索世界杯球队..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9 w-56 border border-[#23262d] bg-[#1a1f2e] pl-9 pr-3 text-sm text-[#f1f5f9] transition-colors placeholder:text-[#64748b] focus:border-[#22c55e]/50 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {teamsLoading ? (
          <div className="py-16 text-center text-sm text-[#94a3b8]">正在加载球队数据...</div>
        ) : filteredTeams.length === 0 ? (
          <div className="py-16 text-center">
            <Shield className="mx-auto mb-4 h-12 w-12 text-[#475569]" />
            <div className="text-sm text-[#94a3b8]">当前没有可展示的世界杯球队。</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {filteredTeams.map((team) => (
              <TeamCard key={team.id} team={team} leagueName="世界杯" />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TeamCard({ team, leagueName }: { team: Team; leagueName?: string }) {
  const firstLetter = team.name ? team.name.charAt(0).toUpperCase() : "?";
  const identity = getTeamIdentity(team.name);

  return (
    <Link to={`/teams/${team.id}`}>
      <div className="group cursor-pointer border border-[#23262d] bg-[#0d0f12] transition-all hover:border-[#22c55e]/40 hover:bg-[#22c55e]/5">
        <div className="flex items-center gap-3 px-4 py-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center bg-[#1a1f2e] transition-colors group-hover:bg-[#22c55e]/10">
            {identity.flagUrl ? (
              <img src={identity.flagUrl} alt={identity.countryLabel || team.name} className="h-7 w-9 object-cover" />
            ) : (
              <span className="text-lg font-bold text-[#64748b] transition-colors group-hover:text-[#22c55e]">
                {firstLetter}
              </span>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-sm font-medium text-[#f1f5f9] transition-colors group-hover:text-[#22c55e]">
              {identity.displayName}
            </h3>
            <div className="mt-0.5 flex items-center gap-2">
              {identity.countryLabel && <span className="truncate text-[11px] text-[#64748b]">{identity.countryLabel}</span>}
              {leagueName && identity.countryLabel && <span className="text-[#64748b]">·</span>}
              {leagueName && <span className="truncate text-[11px] text-[#64748b]">{leagueName}</span>}
            </div>
          </div>
          <ChevronRight className="h-4 w-4 shrink-0 text-[#475569] transition-all group-hover:translate-x-0.5 group-hover:text-[#22c55e]" />
        </div>
        {(team.venue || team.coach) && (
          <div className="space-y-1 border-t border-[#23262d]/50 px-4 py-2">
            {team.venue && (
              <div className="flex items-center gap-2 text-[11px] text-[#64748b]">
                <MapPin className="h-3 w-3 shrink-0" />
                <span className="truncate">{team.venue}</span>
              </div>
            )}
            {team.coach && (
              <div className="flex items-center gap-2 text-[11px] text-[#64748b]">
                <User className="h-3 w-3 shrink-0" />
                <span className="truncate">主教练：{team.coach}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </Link>
  );
}
