"use client";

import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { KeyRound } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { changePassword } from "@/lib/api/auth";
import { ApiError } from "@/lib/api-client";
import { MIN_PASSWORD_LENGTH, ROLE_LABELS } from "@/lib/labels";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password"),
    new_password: z
      .string()
      .min(MIN_PASSWORD_LENGTH, `Must be at least ${MIN_PASSWORD_LENGTH} characters`),
    confirm_password: z.string(),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>;

export default function AccountPage() {
  const { user } = useAuth();
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordFormValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  });

  const [formError, setFormError] = useState<string | null>(null);

  const onSubmit = async (values: ChangePasswordFormValues) => {
    setFormError(null);
    setSuccess(false);
    try {
      await changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      });
      setSuccess(true);
      reset();
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "Unable to change your password."
      );
    }
  };

  if (!user) {
    return null;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Account</h1>
        <p className="text-sm text-muted-foreground">
          {ROLE_LABELS[user.role]}
          {user.facilityId ? ` · ${user.facilityId}` : ""}
        </p>
      </div>

      <div className="max-w-md">
        <h2 className="mb-3 text-[11px] font-semibold tracking-widest text-muted-foreground uppercase">
          Security
        </h2>
        <Card>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} noValidate>
              <FieldGroup>
                <Field data-invalid={!!errors.current_password}>
                  <FieldLabel htmlFor="current_password">Current password</FieldLabel>
                  <Input
                    id="current_password"
                    type="password"
                    autoComplete="current-password"
                    {...register("current_password")}
                  />
                  <FieldError errors={[errors.current_password]} />
                </Field>

                <Field data-invalid={!!errors.new_password}>
                  <FieldLabel htmlFor="new_password">New password</FieldLabel>
                  <Input
                    id="new_password"
                    type="password"
                    autoComplete="new-password"
                    {...register("new_password")}
                  />
                  <FieldError errors={[errors.new_password]} />
                </Field>

                <Field data-invalid={!!errors.confirm_password}>
                  <FieldLabel htmlFor="confirm_password">Confirm new password</FieldLabel>
                  <Input
                    id="confirm_password"
                    type="password"
                    autoComplete="new-password"
                    {...register("confirm_password")}
                  />
                  <FieldError errors={[errors.confirm_password]} />
                </Field>

                {formError && (
                  <p role="alert" className="text-sm font-normal text-destructive">
                    {formError}
                  </p>
                )}
                {success && (
                  <p className="text-sm font-normal text-standard">Password updated.</p>
                )}

                <Button type="submit" disabled={isSubmitting} className="w-full">
                  <KeyRound />
                  Update password
                </Button>
              </FieldGroup>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
