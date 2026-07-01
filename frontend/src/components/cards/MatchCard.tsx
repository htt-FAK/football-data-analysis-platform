import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  cn,
  formatDateTime,
  formatWorldCupDateTime,
  getGroupLabel,
  getStageLabel,
  getStatusColor,
  getStatusLabel,
  getTeamIdentity,
  shouldDisplayMatchScore,
} from "@/lib/utils";
import type { Match, MatchEvent, MatchReport } from "@/types";

function TeamFlag({
  label,
  flagUrl,
}: {
  label: string;
  flagUrl?: string;
}) {
  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full border border-border bg-secondary/60">
      {flagUrl ? (
        <img src={flagUrl} alt={label} className="h-full w-full object-cover" />
      ) : (
        <span className="text-xs font-bold text-muted-foreground">{label.charAt(0).toUpperCase() || "?"}</span>
      )}
    </div>
  );
}

function formatReportEventSummary(event: MatchEvent): string {
  const minute = event.minute != null ? `${event.minute}' ` : "";
  if (event.detail) {
    return `${minute}${event.detail}`;
  }

  const actor = event.player_name || event.team_name || "比赛事件";
  return `${minute}${actor}`;
}

function buildReportSummary(report?: MatchReport | null): string | null {
  if (!report) return null;

  const keyEvents = report.impact_summary?.key_events ?? [];
  if (keyEvents.length > 0) {
    return keyEvents.slice(0, 2).map((event) => formatReportEventSummary(event)).join(" / ");
  }

  const events = report.events ?? [];
  if (events.length > 0) {
    return events.slice(0, 2).map((event) => formatReportEventSummary(event)).join(" / ");
  }

  const availability = report.data_availability?.events;
  if (availability && availability.available === false) {
    return availability.note || "比赛已结束，事件摘要补充中。";
  }

  return "比赛已结束，摘要补充中。";
}

export function MatchCard({
  match,
  report,
}: {
  match: Match;
  report?: MatchReport | null;
}) {
  const isLive = match.status === "live" || match.status === "in_progress" || match.status === "half_time";
  const isFinished = match.status === "finished";
  const hasScore = shouldDisplayMatchScore(match.status, match.home_score, match.away_score);
  const homeTeam = getTeamIdentity(match.home_team_name);
  const awayTeam = getTeamIdentity(match.away_team_name);
  const matchTime = match.date_time ?? match.match_date;
  const reportSummary = isFinished ? buildReportSummary(report) : null;

  return (
    <Link to={`/matches/${match.id}`}>
      <Card className="group relative cursor-pointer overflow-hidden p-4 transition-all duration-200 hover:border-primary/40">
        <div className="absolute left-0 top-0 h-full w-1 bg-primary/0 transition-all duration-200 group-hover:bg-primary" />

        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isLive && (
              <Badge variant="danger" className="animate-pulse">
                <span className="mr-1 h-1.5 w-1.5 rounded-full bg-current" />
                进行中{match.minute ? ` ${match.minute}'` : ""}
              </Badge>
            )}

            {!isLive && match.status && <Badge className={getStatusColor(match.status)}>{getStatusLabel(match.status)}</Badge>}

            {match.stage && (
              <span className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">
                {getStageLabel(match.stage)}
                {match.group_name ? ` · ${getGroupLabel(match.group_name)}` : ""}
              </span>
            )}
          </div>

          <span className="font-mono text-[10px] text-muted-foreground">
            {match.stage ? formatWorldCupDateTime(matchTime, match.venue) : formatDateTime(matchTime)}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
            <span className="min-w-0 text-right text-sm font-semibold transition-colors group-hover:text-primary">
              {homeTeam.displayName}
            </span>
            <TeamFlag label={homeTeam.displayName} flagUrl={homeTeam.flagUrl} />
          </div>

          <div className="flex items-center gap-3 border border-border bg-secondary/50 px-3 py-1.5">
            {hasScore ? (
              <span
                className={cn(
                  "font-mono text-xl font-black tabular-nums",
                  isFinished ? "text-muted-foreground" : "text-foreground"
                )}
              >
                <span className={isLive ? "text-rose-400" : ""}>{match.home_score}</span>
                <span className="mx-1 text-base font-normal text-muted-foreground">-</span>
                <span className={isLive ? "text-rose-400" : ""}>{match.away_score}</span>
              </span>
            ) : (
              <span className="px-2 font-mono text-sm font-bold text-muted-foreground">VS</span>
            )}
          </div>

          <div className="flex min-w-0 flex-1 items-center gap-2">
            <TeamFlag label={awayTeam.displayName} flagUrl={awayTeam.flagUrl} />
            <span className="text-sm font-semibold transition-colors group-hover:text-primary">
              {awayTeam.displayName}
            </span>
          </div>
        </div>

        {match.venue && (
          <div className="mt-2 flex items-center justify-center gap-1 text-center text-[10px] text-muted-foreground">
            <span className="h-1 w-1 rounded-full bg-muted-foreground/30" />
            {match.venue}
          </div>
        )}

        {reportSummary ? (
          <div className="mt-3 border-t border-border/50 pt-3">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">完赛摘要</div>
            <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{reportSummary}</div>
          </div>
        ) : null}
      </Card>
    </Link>
  );
}
