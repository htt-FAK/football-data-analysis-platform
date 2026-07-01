import { WCHero } from "./WCHero";
import { WCStandings } from "./WCStandings";
import { WCBracket } from "./WCBracket";
import { WCTopScorers } from "./WCTopScorers";
import { WCPlayerRadar } from "./WCPlayerRadar";
import { WCRecentMatches } from "./WCRecentMatches";
import { WCCoverageFooter } from "./WCCoverageFooter";

export function WorldCupDashboard() {
  return (
    <div className="min-h-screen bg-[#0d0f12] text-[#f1f5f9]">
      <WCHero />
      <WCBracket />
      <WCStandings />

      <div className="border-b border-[#23262d]">
        <div className="max-w-[1400px] mx-auto px-4 py-12">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
            <WCTopScorers />
            <WCPlayerRadar />
          </div>
        </div>
      </div>

      <WCRecentMatches />
      <WCCoverageFooter />
    </div>
  );
}

export default WorldCupDashboard;
