import {
  Bell,
  BellRing,
  FlaskConical,
  LayoutDashboard,
  Package,
  Receipt,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  description: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    label: "운영",
    items: [
      {
        title: "대시보드",
        href: "/",
        icon: LayoutDashboard,
        description: "수집 · 절감 · 알림 현황 요약",
      },
      {
        title: "조달 주문",
        href: "/jobs",
        icon: Package,
        description: "조달 수집 job 상태와 재시도 현황",
      },
      {
        title: "수집 결과",
        href: "/results",
        icon: Receipt,
        description: "최저 실가 결과와 비교 가능 여부",
      },
      {
        title: "알림",
        href: "/notifications",
        icon: BellRing,
        description: "카카오 · SMS/LMS 전달 현황",
      },
    ],
  },
  {
    label: "내부",
    items: [
      {
        title: "파서 실험",
        href: "/experiments",
        icon: FlaskConical,
        description: "파서 업로드 · 비교 · 회귀 테스트",
      },
      {
        title: "설정",
        href: "/settings",
        icon: Settings,
        description: "백엔드 URL · 토큰 · 환경",
      },
    ],
  },
];

export const allNavItems: NavItem[] = navGroups.flatMap((group) => group.items);

export { Bell };
