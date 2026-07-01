import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";

export function AppLayout() {
  return (
    <div className="min-h-screen bg-[#0d0f12]">
      <Sidebar className="w-56" />
      <main className="ml-56 min-h-screen">
        <Outlet />
      </main>
    </div>
  );
}
