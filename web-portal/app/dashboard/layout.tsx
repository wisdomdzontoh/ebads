"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { LogOut } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { ROLE_LABELS } from "@/lib/labels";
import type { Role } from "@/lib/types";

interface NavItem {
  title: string;
  /** Omitted while the view for this role hasn't been built yet (later increments). */
  href?: string;
}

const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  system_administrator: [
    { title: "Overview", href: "/dashboard" },
    { title: "Facility registrations", href: "/dashboard/registrations" },
    { title: "Users", href: "/dashboard/users" },
    { title: "Audit log", href: "/dashboard/audit-log" },
  ],
  facility_administrator: [
    { title: "Overview", href: "/dashboard" },
    { title: "Facility profile", href: "/dashboard/facility" },
    { title: "Users", href: "/dashboard/users" },
    { title: "Beds", href: "/dashboard/beds" },
  ],
  facility_staff: [
    { title: "Overview", href: "/dashboard" },
    { title: "Bed availability" },
    { title: "Incoming allocations" },
  ],
  dispatcher: [{ title: "Overview", href: "/dashboard" }],
};

export default function DashboardLayout({
  children,
}: LayoutProps<"/dashboard">) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isLoading, logout } = useAuth();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, user, router]);

  if (isLoading || !user) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  const navItems = NAV_BY_ROLE[user.role];

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon">
        <SidebarHeader>
          <div className="flex items-center gap-2 px-2 py-1.5">
            <span className="text-sm font-semibold text-sidebar-foreground">
              EBADS
            </span>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>{ROLE_LABELS[user.role]}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {navItems.map((item) => (
                  <SidebarMenuItem key={item.title}>
                    {item.href ? (
                      <SidebarMenuButton
                        render={<Link href={item.href} />}
                        isActive={pathname === item.href}
                      >
                        <span>{item.title}</span>
                      </SidebarMenuButton>
                    ) : (
                      <SidebarMenuButton disabled>
                        <span>{item.title}</span>
                        <Badge variant="outline" className="ml-auto">
                          Soon
                        </Badge>
                      </SidebarMenuButton>
                    )}
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <Button
            variant="ghost"
            size="sm"
            className="justify-start"
            onClick={logout}
          >
            <LogOut />
            Log out
          </Button>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset>
        <header className="flex h-12 items-center gap-2 border-b border-border px-3">
          <SidebarTrigger />
          <div className="flex-1" />
          <Badge variant="secondary">{ROLE_LABELS[user.role]}</Badge>
        </header>
        <div className="flex-1 p-6">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
