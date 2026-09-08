"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BellOff } from "lucide-react";

import { acknowledgeReservation, listInboundReservations } from "@/lib/api/allocations";
import { ApiError } from "@/lib/api-client";
import { BED_TYPE_LABELS, URGENCY_CLASSES, URGENCY_LABELS } from "@/lib/labels";
import type { InboundReservation } from "@/lib/types";
import { useNewItemNotifications } from "@/hooks/use-new-item-notifications";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";

import { EtaCountdown } from "./eta-countdown";
import { RevokeReservationDialog } from "./revoke-dialog";

// Refreshed from the server periodically (a new reservation, or one acknowledged/revoked
// from another session, should show up without a manual reload) on top of the countdown's
// own second-by-second local tick.
const REFRESH_INTERVAL_MS = 15_000;

export default function InboundPage() {
  const [revokeTarget, setRevokeTarget] = useState<InboundReservation | null>(null);
  const [acknowledging, setAcknowledging] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["inbound-reservations"],
    queryFn: listInboundReservations,
    refetchInterval: REFRESH_INTERVAL_MS,
  });

  // A live (OS-level) alert on every NEW reservation, so staff don't have to keep this tab
  // focused and watch the list — the poll above already refreshes every 15s regardless of
  // whether notifications are permitted; this only adds an alert on top of it.
  const { permission, requestPermission } = useNewItemNotifications(
    data,
    (r) => r.allocation_id,
    (r) => ({
      title: "Incoming reservation",
      body: `${URGENCY_LABELS[r.urgency ?? "standard"]} · ${BED_TYPE_LABELS[r.required_bed_type]} bed`,
    }),
  );

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["inbound-reservations"] });

  async function handleAcknowledge(reservation: InboundReservation) {
    setAcknowledging(reservation.allocation_id);
    try {
      await acknowledgeReservation(reservation.allocation_id);
      invalidate();
    } finally {
      setAcknowledging(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Incoming allocations</h1>
          <p className="text-sm text-muted-foreground">
            Active reservations held for your facility, most urgent first. Acknowledge to let
            the dispatcher know you&apos;ve seen it, or revoke if the bed is no longer
            available — arrival itself is recorded by the dispatcher on arrival.
          </p>
        </div>
        {permission === "default" && (
          <Button variant="outline" size="sm" onClick={requestPermission} className="shrink-0">
            <Bell />
            Enable live alerts
          </Button>
        )}
        {permission === "denied" && (
          <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
            <BellOff className="size-3.5" />
            Blocked in browser settings
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : error ? (
        <p className="text-sm text-destructive">
          {error instanceof ApiError ? error.message : "Failed to load incoming allocations."}
        </p>
      ) : !data || data.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyTitle>No incoming reservations</EmptyTitle>
            <EmptyDescription>
              Nothing is currently held for your facility. New reservations appear here
              automatically.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {data.map((reservation) => {
            const classes = reservation.urgency ? URGENCY_CLASSES[reservation.urgency] : null;
            return (
              <Card
                key={reservation.allocation_id}
                className={classes ? `border-l-4 ${classes.border}` : "border-l-4"}
              >
                <CardContent className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center gap-2">
                      {reservation.urgency && classes ? (
                        <Badge className={`${classes.bg} ${classes.text}`}>
                          {URGENCY_LABELS[reservation.urgency]}
                        </Badge>
                      ) : (
                        <Badge variant="outline">Urgency unknown</Badge>
                      )}
                      <span className="text-sm font-medium">
                        {BED_TYPE_LABELS[reservation.required_bed_type]} bed
                      </span>
                      {reservation.acknowledged_at && (
                        <Badge variant="secondary">Acknowledged</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>Submitted {new Date(reservation.created_at).toLocaleTimeString()}</span>
                      <span>
                        {reservation.confirmed ? "Arrived" : "Awaiting arrival"}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <EtaCountdown
                      createdAt={reservation.created_at}
                      etaMinutes={reservation.eta_minutes}
                    />
                    <div className="flex gap-2">
                      {!reservation.acknowledged_at && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={acknowledging === reservation.allocation_id}
                          onClick={() => handleAcknowledge(reservation)}
                        >
                          Acknowledge
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => setRevokeTarget(reservation)}
                      >
                        Revoke
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <RevokeReservationDialog
        reservation={revokeTarget}
        onOpenChange={(open) => !open && setRevokeTarget(null)}
        onSuccess={() => {
          setRevokeTarget(null);
          invalidate();
        }}
      />
    </div>
  );
}
