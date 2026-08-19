"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { useAuth } from "@/components/auth-provider";
import { listFacilities, updateFacility } from "@/lib/api/facilities";
import { ApiError } from "@/lib/api-client";
import { BED_TYPE_LABELS, DATA_SOURCE_LABELS, TIER_LABELS } from "@/lib/labels";
import type { BedType, DataSource, Facility, Tier } from "@/lib/types";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

const BED_TYPES = Object.keys(BED_TYPE_LABELS) as BedType[];
const TIERS = Object.keys(TIER_LABELS) as Tier[];
const LIVE_DATA_SOURCES = Object.keys(DATA_SOURCE_LABELS) as Exclude<DataSource, "manual">[];
const NO_DATA_SOURCE = "none" as const;

const facilitySchema = z.object({
  name: z.string().min(1, "Required"),
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
  tier: z.enum(TIERS as [Tier, ...Tier[]]),
  supported_bed_types: z.array(z.enum(BED_TYPES)).min(1, "Select at least one bed type"),
  contact_phone: z.string().min(1, "Required"),
  active_data_source: z.union([z.enum(LIVE_DATA_SOURCES), z.literal(NO_DATA_SOURCE)]),
});

type FacilityFormValues = z.infer<typeof facilitySchema>;

function toFormValues(facility: Facility): FacilityFormValues {
  return {
    name: facility.name,
    latitude: facility.latitude,
    longitude: facility.longitude,
    tier: facility.tier,
    supported_bed_types: facility.supported_bed_types,
    contact_phone: facility.contact_phone,
    // "manual" is never actually stored as a live value (null means manual maintenance —
    // see lib/types.ts), but the type admits it; treat it the same as null defensively.
    active_data_source:
      facility.active_data_source && facility.active_data_source !== "manual"
        ? facility.active_data_source
        : NO_DATA_SOURCE,
  };
}

export default function FacilityProfilePage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const facilitiesQuery = useQuery({ queryKey: ["facilities"], queryFn: listFacilities });
  const facility = facilitiesQuery.data?.find((f) => f.id === user?.facilityId) ?? null;

  const {
    control,
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<FacilityFormValues>({
    resolver: zodResolver(facilitySchema),
    values: facility ? toFormValues(facility) : undefined,
  });

  const mutation = useMutation({
    mutationFn: (values: FacilityFormValues) => {
      if (!facility) throw new Error("no facility loaded");
      return updateFacility(facility.id, {
        name: values.name,
        latitude: values.latitude,
        longitude: values.longitude,
        tier: values.tier,
        supported_bed_types: values.supported_bed_types,
        contact_phone: values.contact_phone,
        active_data_source:
          values.active_data_source === NO_DATA_SOURCE ? null : values.active_data_source,
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["facilities"] }),
  });

  if (facilitiesQuery.isLoading) {
    return <Skeleton className="h-96 w-full max-w-xl" />;
  }

  if (facilitiesQuery.error) {
    return (
      <p className="text-sm text-destructive">
        {facilitiesQuery.error instanceof ApiError
          ? facilitiesQuery.error.message
          : "Failed to load your facility."}
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
        <h1 className="text-xl font-semibold">Facility profile</h1>
        <p className="text-sm text-muted-foreground">
          Static details for {facility.name}, as seen by dispatchers and the registry.
        </p>
      </div>

      <Card className="max-w-xl">
        <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
          <CardContent>
            <FieldGroup>
              <Field data-invalid={!!errors.name}>
                <FieldLabel htmlFor="name">Name</FieldLabel>
                <Input id="name" {...register("name")} />
                <FieldError errors={[errors.name]} />
              </Field>

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

              <Field data-invalid={!!errors.contact_phone}>
                <FieldLabel htmlFor="contact_phone">Contact phone</FieldLabel>
                <Input id="contact_phone" {...register("contact_phone")} />
                <FieldError errors={[errors.contact_phone]} />
              </Field>

              <Field>
                <FieldLabel htmlFor="tier">Tier</FieldLabel>
                <Controller
                  control={control}
                  name="tier"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="tier" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TIERS.map((tier) => (
                          <SelectItem key={tier} value={tier}>
                            {TIER_LABELS[tier]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </Field>

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

              {mutation.isError && (
                <p role="alert" className="text-sm font-normal text-destructive">
                  {mutation.error instanceof ApiError
                    ? mutation.error.message
                    : "Unable to save changes."}
                </p>
              )}
              {mutation.isSuccess && !isDirty && (
                <p className="text-sm font-normal text-standard">Saved.</p>
              )}
            </FieldGroup>
          </CardContent>
          <CardFooter>
            <Button type="submit" disabled={mutation.isPending || !isDirty}>
              Save changes
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
