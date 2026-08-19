"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/components/auth-provider";
import { listFacilities } from "@/lib/api/facilities";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const ROLE_SUMMARY: Record<string, string> = {
  system_administrator:
    "Review facility registrations, manage user accounts, and audit system activity.",
  facility_administrator:
    "Manage your facility's profile, staff accounts, and bed inventory.",
  facility_staff:
    "Keep bed availability current and respond to incoming allocations.",
  dispatcher: "Use the EBADS mobile app to dispatch emergency allocations.",
};

export default function DashboardOverviewPage() {
  const { user } = useAuth();

  const facilitiesQuery = useQuery({
    queryKey: ["facilities"],
    queryFn: listFacilities,
    enabled: !!user?.facilityId,
    staleTime: 60_000,
  });
  const facility = facilitiesQuery.data?.find((f) => f.id === user?.facilityId);

  if (!user) {
    return null;
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Welcome back</CardTitle>
          <CardDescription>{ROLE_SUMMARY[user.role]}</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          {user.facilityId ? (
            <p>Facility: {facility?.name ?? user.facilityId}</p>
          ) : (
            <p>No facility assigned to this account.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
