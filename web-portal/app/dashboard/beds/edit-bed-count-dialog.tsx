"use client";

import { useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { updateBedCount } from "@/lib/api/beds";
import { ApiError } from "@/lib/api-client";
import { BED_TYPE_LABELS } from "@/lib/labels";
import type { BedCount, BedType } from "@/lib/types";

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
import { Input } from "@/components/ui/input";

const bedCountSchema = z
  .object({
    available: z.number().int().min(0),
    capacity: z.number().int().min(0),
  })
  .refine((v) => v.available <= v.capacity, {
    message: "Available cannot exceed capacity",
    path: ["available"],
  });

type BedCountFormValues = z.infer<typeof bedCountSchema>;

interface EditBedCountDialogProps {
  facilityId: string;
  bedType: BedType | null;
  current: BedCount | null;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function EditBedCountDialog({
  facilityId,
  bedType,
  current,
  onOpenChange,
  onSuccess,
}: EditBedCountDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BedCountFormValues>({
    resolver: zodResolver(bedCountSchema),
    defaultValues: { available: current?.available ?? 0, capacity: current?.capacity ?? 0 },
  });

  useEffect(() => {
    if (bedType) {
      reset({ available: current?.available ?? 0, capacity: current?.capacity ?? 0 });
    }
  }, [bedType, current, reset]);

  const mutation = useMutation({
    mutationFn: (values: BedCountFormValues) =>
      updateBedCount(facilityId, { bed_type: bedType!, ...values }),
    onSuccess,
  });

  return (
    <Dialog open={!!bedType} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
          <DialogHeader>
            <DialogTitle>{bedType ? BED_TYPE_LABELS[bedType] : ""} beds</DialogTitle>
            <DialogDescription>
              Set the current availability. This overwrites the count directly — use it for
              manual corrections, not per-patient allocation.
            </DialogDescription>
          </DialogHeader>

          <FieldGroup className="py-2">
            <div className="grid grid-cols-2 gap-3">
              <Field data-invalid={!!errors.available}>
                <FieldLabel htmlFor="available">Available</FieldLabel>
                <Input
                  id="available"
                  type="number"
                  min={0}
                  {...register("available", { valueAsNumber: true })}
                />
              </Field>
              <Field data-invalid={!!errors.capacity}>
                <FieldLabel htmlFor="capacity">Capacity</FieldLabel>
                <Input
                  id="capacity"
                  type="number"
                  min={0}
                  {...register("capacity", { valueAsNumber: true })}
                />
              </Field>
            </div>
            <FieldError errors={[errors.available, errors.capacity]} />

            {mutation.isError && (
              <p role="alert" className="text-sm font-normal text-destructive">
                {mutation.error instanceof ApiError
                  ? mutation.error.message
                  : "Unable to update this bed count."}
              </p>
            )}
          </FieldGroup>

          <DialogFooter>
            <Button type="submit" disabled={mutation.isPending}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
