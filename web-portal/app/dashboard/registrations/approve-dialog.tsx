"use client";

import { useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { approveRegistration } from "@/lib/api/registrations";
import { ApiError } from "@/lib/api-client";
import { BED_TYPE_LABELS, DATA_SOURCE_LABELS, MIN_PASSWORD_LENGTH } from "@/lib/labels";
import type { BedType, DataSource, FacilityRequest } from "@/lib/types";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const BED_TYPES = Object.keys(BED_TYPE_LABELS) as BedType[];
const LIVE_DATA_SOURCES = Object.keys(DATA_SOURCE_LABELS) as Exclude<DataSource, "manual">[];
const NO_DATA_SOURCE = "none" as const;

const approveSchema = z.object({
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
  supported_bed_types: z.array(z.enum(BED_TYPES)).min(1, "Select at least one bed type"),
  active_data_source: z.union([z.enum(LIVE_DATA_SOURCES), z.literal(NO_DATA_SOURCE)]),
  initial_admin_email: z.email("Enter a valid email address"),
  initial_admin_password: z
    .string()
    .min(MIN_PASSWORD_LENGTH, `Must be at least ${MIN_PASSWORD_LENGTH} characters`),
});

type ApproveFormValues = z.infer<typeof approveSchema>;

const DEFAULT_VALUES: ApproveFormValues = {
  latitude: 0,
  longitude: 0,
  supported_bed_types: [],
  active_data_source: NO_DATA_SOURCE,
  initial_admin_email: "",
  initial_admin_password: "",
};

interface ApproveRegistrationDialogProps {
  request: FacilityRequest | null;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function ApproveRegistrationDialog({
  request,
  onOpenChange,
  onSuccess,
}: ApproveRegistrationDialogProps) {
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ApproveFormValues>({
    resolver: zodResolver(approveSchema),
    defaultValues: DEFAULT_VALUES,
  });

  useEffect(() => {
    if (request) reset(DEFAULT_VALUES);
  }, [request, reset]);

  const mutation = useMutation({
    mutationFn: (values: ApproveFormValues) =>
      approveRegistration(request!.id, {
        latitude: values.latitude,
        longitude: values.longitude,
        supported_bed_types: values.supported_bed_types,
        active_data_source:
          values.active_data_source === NO_DATA_SOURCE ? null : values.active_data_source,
        initial_admin_email: values.initial_admin_email,
        initial_admin_password: values.initial_admin_password,
      }),
    onSuccess,
  });

  return (
    <Dialog open={!!request} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
          <DialogHeader>
            <DialogTitle>Approve registration</DialogTitle>
            <DialogDescription>
              Creates {request?.facility_name} as a live facility and provisions its first
              administrator account.
            </DialogDescription>
          </DialogHeader>

          <FieldGroup className="py-2">
            <div className="grid grid-cols-2 gap-3">
              <Field data-invalid={!!errors.latitude}>
                <FieldLabel htmlFor="latitude">Latitude</FieldLabel>
                <Input
                  id="latitude"
                  type="number"
                  step="any"
                  {...register("latitude", { valueAsNumber: true })}
                />
                <FieldError errors={[errors.latitude]} />
              </Field>
              <Field data-invalid={!!errors.longitude}>
                <FieldLabel htmlFor="longitude">Longitude</FieldLabel>
                <Input
                  id="longitude"
                  type="number"
                  step="any"
                  {...register("longitude", { valueAsNumber: true })}
                />
                <FieldError errors={[errors.longitude]} />
              </Field>
            </div>

            <Field data-invalid={!!errors.supported_bed_types}>
              <FieldLabel>Supported bed types</FieldLabel>
              <Controller
                control={control}
                name="supported_bed_types"
                render={({ field }) => (
                  <div className="flex flex-col gap-2 pt-1">
                    {BED_TYPES.map((bedType) => (
                      <label
                        key={bedType}
                        className="flex items-center gap-2 text-sm font-normal"
                      >
                        <Checkbox
                          checked={field.value.includes(bedType)}
                          onCheckedChange={(checked) => {
                            field.onChange(
                              checked
                                ? [...field.value, bedType]
                                : field.value.filter((v) => v !== bedType)
                            );
                          }}
                        />
                        {BED_TYPE_LABELS[bedType]}
                      </label>
                    ))}
                  </div>
                )}
              />
              <FieldError errors={[errors.supported_bed_types]} />
            </Field>

            <Field>
              <FieldLabel htmlFor="active_data_source">Data source</FieldLabel>
              <Controller
                control={control}
                name="active_data_source"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="active_data_source" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NO_DATA_SOURCE}>Manual (default)</SelectItem>
                      {LIVE_DATA_SOURCES.map((source) => (
                        <SelectItem key={source} value={source}>
                          {DATA_SOURCE_LABELS[source]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>

            <Field data-invalid={!!errors.initial_admin_email}>
              <FieldLabel htmlFor="initial_admin_email">Administrator email</FieldLabel>
              <Input
                id="initial_admin_email"
                type="email"
                {...register("initial_admin_email")}
              />
              <FieldError errors={[errors.initial_admin_email]} />
            </Field>

            <Field data-invalid={!!errors.initial_admin_password}>
              <FieldLabel htmlFor="initial_admin_password">Administrator password</FieldLabel>
              <Input
                id="initial_admin_password"
                type="password"
                {...register("initial_admin_password")}
              />
              <FieldError errors={[errors.initial_admin_password]} />
            </Field>

            {mutation.isError && (
              <p role="alert" className="text-sm font-normal text-destructive">
                {mutation.error instanceof ApiError
                  ? mutation.error.message
                  : "Unable to approve this request."}
              </p>
            )}
          </FieldGroup>

          <DialogFooter>
            <Button type="submit" disabled={mutation.isPending}>
              Approve &amp; create facility
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
