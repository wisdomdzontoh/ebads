"use client";

import { useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { revokeReservation } from "@/lib/api/allocations";
import { ApiError } from "@/lib/api-client";
import type { InboundReservation } from "@/lib/types";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";

const revokeSchema = z.object({
  reason: z.string().min(1, "A reason is required"),
});

type RevokeFormValues = z.infer<typeof revokeSchema>;

interface RevokeReservationDialogProps {
  reservation: InboundReservation | null;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function RevokeReservationDialog({
  reservation,
  onOpenChange,
  onSuccess,
}: RevokeReservationDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RevokeFormValues>({
    resolver: zodResolver(revokeSchema),
    defaultValues: { reason: "" },
  });

  useEffect(() => {
    if (reservation) reset({ reason: "" });
  }, [reservation, reset]);

  const mutation = useMutation({
    mutationFn: (values: RevokeFormValues) =>
      revokeReservation(reservation!.allocation_id, values),
    onSuccess,
  });

  return (
    <Dialog open={!!reservation} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
          <DialogHeader>
            <DialogTitle>Revoke reservation</DialogTitle>
            <DialogDescription>
              The bed held for this patient will be released back to availability, and the
              dispatcher will be notified so they can find another placement. This cannot be
              undone once the vehicle has already arrived.
            </DialogDescription>
          </DialogHeader>

          <FieldGroup className="py-2">
            <Field data-invalid={!!errors.reason}>
              <FieldLabel htmlFor="reason">Reason</FieldLabel>
              <Textarea id="reason" rows={3} {...register("reason")} />
              <FieldError errors={[errors.reason]} />
            </Field>
            {mutation.isError && (
              <p role="alert" className="text-sm font-normal text-destructive">
                {mutation.error instanceof ApiError
                  ? mutation.error.message
                  : "Unable to revoke this reservation."}
              </p>
            )}
          </FieldGroup>

          <DialogFooter>
            <Button type="submit" variant="destructive" disabled={mutation.isPending}>
              Revoke reservation
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
