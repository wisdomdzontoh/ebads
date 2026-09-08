import { Smartphone } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** Dispatcher's Overview — dispatching itself happens on the mobile app (docs/05), which is
 * where the dispatcher's own allocation history and live metrics actually live; the web
 * portal has no API surface for that data today. Kept honest rather than showing invented
 * numbers for a role this portal doesn't have real data for. */
export function DispatcherOverview() {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-full bg-brand-soft text-brand">
            <Smartphone className="size-5" />
          </div>
          <div>
            <CardTitle>Dispatching happens on the mobile app</CardTitle>
            <CardDescription>
              Emergency bed allocation, live navigation, and your dispatch history all live in
              the EBADS dispatcher app.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        This portal account can still manage your password from Account.
      </CardContent>
    </Card>
  );
}
