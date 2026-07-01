import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { PageHeader, LoadingState, EmptyState } from "@/components/ui/stat-card";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { getLeagues } from "@/api/leagues";
import { getCountryFlagUrl, getCountryLabel, getLeagueTypeLabel } from "@/lib/utils";
import type { League } from "@/types";
import { Trophy, Globe, ChevronRight } from "lucide-react";

export function LeagueList() {
  const [countryFilter, setCountryFilter] = useState<string>("");

  const { data: leagues = [], isLoading } = useQuery({
    queryKey: ["leagues"],
    queryFn: () => getLeagues(),
  });

  const countries = useMemo(() => {
    const set = new Set<string>();
    leagues.forEach((l) => {
      if (l.country) set.add(l.country);
    });
    return Array.from(set).sort();
  }, [leagues]);

  const filteredLeagues = useMemo(() => {
    if (!countryFilter) return leagues;
    return leagues.filter((l) => l.country === countryFilter);
  }, [leagues, countryFilter]);

  return (
    <div className="animate-fade-in">
      <PageHeader title="联赛中心" description="浏览所有联赛" />

      <div className="flex items-center gap-3 mb-6">
        <div className="w-48">
          <Select value={countryFilter} onChange={(e) => setCountryFilter(e.target.value)}>
            <option value="">全部国家</option>
            {countries.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </Select>
        </div>
        <div className="flex-1" />
        <Badge variant="outline" className="gap-1">
          <Globe className="w-3 h-3" />
          共 {filteredLeagues.length} 个联赛
        </Badge>
      </div>

      {isLoading ? (
        <LoadingState rows={8} />
      ) : filteredLeagues.length === 0 ? (
        <EmptyState icon={Trophy} title="暂无联赛数据" description="当前筛选条件下没有联赛" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredLeagues.map((league) => (
            <LeagueCard key={league.id} league={league} />
          ))}
        </div>
      )}
    </div>
  );
}

function LeagueCard({ league }: { league: League }) {
  const firstLetter = league.name ? league.name.charAt(0).toUpperCase() : "?";
  const flagUrl = getCountryFlagUrl(league.country);

  return (
    <Link to={`/leagues/${league.id}`}>
      <Card className="p-5 hover:border-primary/30 transition-all cursor-pointer group">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center text-xl font-display font-bold text-primary shrink-0 group-hover:scale-105 transition-transform">
            {flagUrl ? (
              <img
                src={flagUrl}
                alt={league.country || league.name}
                className="h-8 w-10 rounded-md object-cover shadow-sm"
              />
            ) : (
              firstLetter
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-base group-hover:text-primary transition-colors truncate">
              {league.name}
            </h3>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              {league.country && (
                <Badge variant="outline" className="gap-1">
                  <Globe className="w-3 h-3" />
                  {getCountryLabel(league.country)}
                </Badge>
              )}
              {league.type && (
                <Badge variant="secondary">{getLeagueTypeLabel(league.type)}</Badge>
              )}
            </div>
          </div>
          <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all shrink-0" />
        </div>
      </Card>
    </Link>
  );
}
