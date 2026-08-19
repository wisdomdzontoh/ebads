"use client";

import { useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { rejectRegistration } from "@/lib/api/registrations";
import { ApiError } from "@/lib/api-client";
import type { FacilityRequest } from "@/lib/types";

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

const rejectSchema = z.object({
  reason: z.string().min(1, "A reason is required"),
});

type RejectFormValues = z.infer<typeof rejectSchema>;

interface RejectRegistrationDialogProps {
  request: FacilityRequest | null;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function RejectRegistrationDialog({
  request,
  onOpenChange,
  onSuccess,
}: RejectRegistrationDialogProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RejectFormValues>({
    resolver: zodResolver(rejectSchema),
    defaultValues: { reason: "" },
  });

  useEffect(() => {
    if (request) reset({ reason: "" });
  }, [request, reset]);

  const mutation = useMutation({
    mutationFn: (values: RejectFormValues) => rejectRegistration(request!.id, values),
    onSuccess,
  });

  return (
    <Dialog open={!!request} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
          <DialogHeader>
            <DialogTitle>Reject registration</DialogTitle>
            <DialogDescription>
              {request?.facility_name} will be recorded as rejected with the reason below.
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
                  : "Unable to reject this request."}
              </p>
            )}
          </FieldGroup>

          <DialogFooter>
            <Button type="submit" variant="destructive" disabled={mutation.isPending}>
              Reject request
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
