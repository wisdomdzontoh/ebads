"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { listFacilities } from "@/lib/api/facilities";
import { createUser } from "@/lib/api/users";
import { ApiError } from "@/lib/api-client";
import { MIN_PASSWORD_LENGTH, ROLE_LABELS } from "@/lib/labels";
import type { Role } from "@/lib/types";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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

const FACILITY_SCOPED_ROLES: Role[] = ["facility_administrator", "facility_staff"];

function buildSchema(assignableRoles: Role[], hasFixedFacility: boolean) {
  return z
    .object({
      email: z.email("Enter a valid email address"),
      password: z
        .string()
        .min(MIN_PASSWORD_LENGTH, `Must be at least ${MIN_PASSWORD_LENGTH} characters`),
      role: z.enum(assignableRoles as [Role, ...Role[]]),
      facility_id: z.string().optional(),
    })
    .superRefine((data, ctx) => {
      if (!hasFixedFacility && FACILITY_SCOPED_ROLES.includes(data.role) && !data.facility_id) {
        ctx.addIssue({
          code: "custom",
          path: ["facility_id"],
          message: "Select a facility for this role",
        });
      }
    });
}

type CreateUserFormValues = z.infer<ReturnType<typeof buildSchema>>;

interface CreateUserDialogProps {
  /** Roles this caller is permitted to create, most to least privileged. */
  assignableRoles: Role[];
  defaultRole: Role;
  /** Set when the caller is a facility_administrator: every new account is implicitly
   * pinned to this facility, so the facility picker is hidden entirely. */
  fixedFacilityId?: string;
  onSuccess: () => void;
}

export function CreateUserDialog({
  assignableRoles,
  defaultRole,
  fixedFacilityId,
  onSuccess,
}: CreateUserDialogProps) {
  const [open, setOpen] = useState(false);
  const schema = useMemo(
    () => buildSchema(assignableRoles, !!fixedFacilityId),
    [assignableRoles, fixedFacilityId]
  );
  const defaultValues = useMemo<CreateUserFormValues>(
    () => ({ email: "", password: "", role: defaultRole, facility_id: undefined }),
    [defaultRole]
  );

  const {
    control,
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<CreateUserFormValues>({
    resolver: zodResolver(schema),
    defaultValues,
  });

  const role = watch("role");
  const showFacilityPicker = !fixedFacilityId && FACILITY_SCOPED_ROLES.includes(role);

  const facilitiesQuery = useQuery({
    queryKey: ["facilities"],
    queryFn: listFacilities,
    enabled: open && showFacilityPicker,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (open) reset(defaultValues);
  }, [open, defaultValues, reset]);

  const mutation = useMutation({
    mutationFn: (values: CreateUserFormValues) =>
      createUser({
        email: values.email,
        password: values.password,
        role: values.role,
        facility_id: fixedFacilityId ?? (showFacilityPicker ? values.facility_id : null),
      }),
    onSuccess: () => {
      setOpen(false);
      onSuccess();
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button>New user</Button>} />
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
          <DialogHeader>
            <DialogTitle>Create user</DialogTitle>
            <DialogDescription>
              Provision a new account. The person is notified of their credentials outside
              this portal.
            </DialogDescription>
          </DialogHeader>

          <FieldGroup className="py-2">
            <Field data-invalid={!!errors.email}>
              <FieldLabel htmlFor="email">Email</FieldLabel>
              <Input id="email" type="email" {...register("email")} />
              <FieldError errors={[errors.email]} />
            </Field>

            <Field data-invalid={!!errors.password}>
              <FieldLabel htmlFor="password">Password</FieldLabel>
              <Input id="password" type="password" {...register("password")} />
              <FieldError errors={[errors.password]} />
            </Field>

            <Field>
              <FieldLabel htmlFor="role">Role</FieldLabel>
              <Controller
                control={control}
                name="role"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="role" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {assignableRoles.map((r) => (
                        <SelectItem key={r} value={r}>
                          {ROLE_LABELS[r]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>

            {showFacilityPicker && (
              <Field data-invalid={!!errors.facility_id}>
                <FieldLabel htmlFor="facility_id">Facility</FieldLabel>
                <Controller
                  control={control}
                  name="facility_id"
                  render={({ field }) => (
                    <Select value={field.value ?? ""} onValueChange={field.onChange}>
                      <SelectTrigger id="facility_id" className="w-full">
                        <SelectValue placeholder="Select a facility" />
                      </SelectTrigger>
                      <SelectContent>
                        {facilitiesQuery.data?.map((facility) => (
                          <SelectItem key={facility.id} value={facility.id}>
                            {facility.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                <FieldError errors={[errors.facility_id]} />
              </Field>
            )}

            {mutation.isError && (
              <p role="alert" className="text-sm font-normal text-destructive">
                {mutation.error instanceof ApiError
                  ? mutation.error.message
                  : "Unable to create this user."}
              </p>
            )}
          </FieldGroup>

          <DialogFooter>
            <Button type="submit" disabled={mutation.isPending}>
              Create user
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
