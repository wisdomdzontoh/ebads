"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/components/auth-provider";
import { listFacilities } from "@/lib/api/facilities";
import { ApiError } from "@/lib/api-client";
import { BED_TYPE_LABELS } from "@/lib/labels";
import type { BedType } from "@/lib/types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";

import { EditBedCountDialog } from "./edit-bed-count-dialog";

export default function BedsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<BedType | null>(null);

  const facilitiesQuery = useQuery({ queryKey: ["facilities"], queryFn: listFacilities });
  const facility = facilitiesQuery.data?.find((f) => f.id === user?.facilityId) ?? null;

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["facilities"] });

  if (facilitiesQuery.isLoading) {
    return <Skeleton className="h-64 w-full max-w-xl" />;
  }

  if (facilitiesQuery.error) {
    return (
      <p className="text-sm text-destructive">
        {facilitiesQuery.error instanceof ApiError
          ? facilitiesQuery.error.message
          : "Failed to load bed availability."}
      </p>
    );
  }

  if (!facility) {
    return (
      <p className="text-sm text-muted-foreground">
        No facility is associated with your account.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Beds</h1>
        <p className="text-sm text-muted-foreground">
          Current availability at {facility.name}. Corrections here overwrite the count
          directly.
        </p>
      </div>

      <div className="grid max-w-2xl gap-3">
        {facility.supported_bed_types.map((bedType) => {
          const count = facility.bed_counts.find((bc) => bc.bed_type === bedType) ?? null;
          const pct = count && count.capacity > 0 ? (count.available / count.capacity) * 100 : 0;
          return (
            <Card key={bedType}>
              <CardContent className="flex items-center justify-between gap-4">
                <div className="flex flex-1 flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{BED_TYPE_LABELS[bedType]}</span>
                    {!count && (
                      <Badge variant="outline" className="text-muted-foreground">
                        Not configured
                      </Badge>
                    )}
                  </div>
                  {count ? (
                    <>
                      <Progress value={pct} />
                      <span className="font-mono text-sm text-muted-foreground">
                        {count.available} / {count.capacity} available
                      </span>
                    </>
                  ) : (
                    <span className="text-sm text-muted-foreground">
                      No availability recorded yet.
                    </span>
                  )}
                </div>
                <Button variant="outline" size="sm" onClick={() => setEditing(bedType)}>
                  {count ? "Update" : "Configure"}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <EditBedCountDialog
        facilityId={facility.id}
        bedType={editing}
        current={facility.bed_counts.find((bc) => bc.bed_type === editing) ?? null}
        onOpenChange={(open) => !open && setEditing(null)}
        onSuccess={() => {
          setEditing(null);
          invalidate();
        }}
      />
    </div>
  );
}
