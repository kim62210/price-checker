import {
  BellRing,
  FlaskConical,
  LayoutDashboard,
  Package,
  Receipt,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavKey =
  | "dashboard"
  | "jobs"
  | "results"
  | "notifications"
  | "experiments"
  | "settings";

export interface NavItem {
  key: NavKey;
  href: string;
  icon: LucideIcon;
}

export interface NavGroupConfig {
  labelKey: "operations" | "internal";
  items: NavItem[];
}

export const navGroups: NavGroupConfig[] = [
  {
    labelKey: "operations",
    items: [
      { key: "dashboard", href: "/", icon: LayoutDashboard },
      { key: "jobs", href: "/jobs", icon: Package },
      { key: "results", href: "/results", icon: Receipt },
      { key: "notifications", href: "/notifications", icon: BellRing },
    ],
  },
  {
    labelKey: "internal",
    items: [
      { key: "experiments", href: "/experiments", icon: FlaskConical },
      { key: "settings", href: "/settings", icon: Settings },
    ],
  },
];

export const allNavItems: NavItem[] = navGroups.flatMap((group) => group.items);
