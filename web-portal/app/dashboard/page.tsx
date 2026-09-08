"use client";

import { useAuth } from "@/components/auth-provider";

import { DispatcherOverview } from "./overview/dispatcher-overview";
import { FacilityAdminOverview } from "./overview/facility-admin-overview";
import { FacilityStaffOverview } from "./overview/facility-staff-overview";
import { SystemAdminOverview } from "./overview/system-admin-overview";

const GREETING: Record<string, string> = {
  system_administrator: "System-wide overview.",
  facility_administrator: "Your facility, at a glance.",
  facility_staff: "What needs your attention right now.",
  dispatcher: "Welcome back.",
};

export default function DashboardOverviewPage() {
  const { user } = useAuth();

  if (!user) {
    return null;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Overview</h1>
        <p className="text-sm text-muted-foreground">{GREETING[user.role]}</p>
      </div>

      {user.role === "system_administrator" && <SystemAdminOverview />}
      {user.role === "facility_administrator" && <FacilityAdminOverview />}
      {user.role === "facility_staff" && <FacilityStaffOverview />}
      {user.role === "dispatcher" && <DispatcherOverview />}
    </div>
  );
}
