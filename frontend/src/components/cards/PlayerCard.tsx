import { Link } from "react-router-dom";
import { Card } from "@/components/ui/card";
import {
  formatNumber,
  getCountryLabel,
  getGroupLabel,
  getPlayerNameLabel,
  getPlayerPhoto,
  getPositionLabel,
  getTeamIdentity,
  handleImageError,
} from "@/lib/utils";
import type { Player } from "@/types";

export function PlayerCard({ player }: { player: Player }) {
  const rating = player.overall_rating ?? 0;
  const identity = getTeamIdentity(player.team_name);
  const displayName = getPlayerNameLabel(player.name, player.full_name);

  return (
    <Link to={`/players/${player.id}`}>
      <Card className="group hover:border-primary/40 transition-all duration-200 cursor-pointer relative overflow-hidden">
        <div className="absolute top-0 left-0 w-1 h-full bg-primary/0 group-hover:bg-primary transition-all duration-200" />
        <div className="flex items-center gap-0">
          <div className="relative flex-shrink-0 p-3">
            <img
              src={getPlayerPhoto(player.photo_url)}
              alt={displayName}
              className="w-14 h-14 object-cover object-[center_12%] bg-secondary border border-border"
              loading="lazy"
              onError={handleImageError}
            />
            {rating > 0 && (
              <div className="absolute top-2 right-2 w-7 h-7 bg-primary flex items-center justify-center text-[11px] font-black text-primary-foreground font-mono">
                {formatNumber(rating, 0)}
              </div>
            )}
          </div>
          <div className="min-w-0 flex-1 px-3 py-3 border-l border-border/50">
            <div className="font-bold text-sm text-foreground truncate group-hover:text-primary transition-colors">
              {displayName}
            </div>
            <div className="flex items-center gap-2 mt-1">
              {player.position && (
                <span className="text-[9px] font-bold px-1 py-0.5 bg-secondary text-muted-foreground uppercase tracking-wider">
                  {getPositionLabel(player.position)}
                </span>
              )}
              {player.jersey_number && (
                <span className="text-[10px] text-muted-foreground font-mono font-bold">#{player.jersey_number}</span>
              )}
            </div>
            <div className="text-xs text-muted-foreground mt-1 truncate">
              {player.team_name ? identity.displayName : getCountryLabel(player.nationality)}
              {player.group_name && ` · ${getGroupLabel(player.group_name)}`}
            </div>
          </div>
        </div>
      </Card>
    </Link>
  );
}
