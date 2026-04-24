export interface TenantRead {
  id: number;
  name: string;
  plan: "starter" | "pro" | "enterprise";
  api_quota_monthly: number;
  created_at: string;
  updated_at: string;
}

export interface UserRead {
  id: number;
  tenant_id: number;
  email: string;
  auth_provider: "kakao" | "naver" | "local";
  provider_user_id: string;
  role: "owner" | "staff";
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ShopRead {
  id: number;
  tenant_id: number;
  name: string;
  business_number: string | null;
  created_at: string;
  updated_at: string;
}

export interface ShopCreate {
  name: string;
  business_number?: string | null;
}

export type OrderStatus = "draft" | "collecting" | "completed" | "cancelled";

export interface OrderCreatePayload {
  shop_id: number;
  product_name: string;
  option_text?: string | null;
  quantity: number;
  unit: string;
  target_unit_price?: number | null;
  memo?: string | null;
  status?: OrderStatus;
}

export interface OrderRead {
  id: number;
  tenant_id: number;
  shop_id: number;
  product_name: string;
  option_text: string | null;
  quantity: number;
  unit: string;
  target_unit_price: string | number | null;
  memo: string | null;
  status: OrderStatus;
  created_at: string;
  updated_at: string;
}

export interface NotificationRecipientRead {
  id: number;
  tenant_id: number;
  shop_id: number | null;
  user_id: number | null;
  phone_e164: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type ResultSource = "naver" | "coupang" | "manual";

export interface ResultUploadPayload {
  source: ResultSource;
  product_url: string;
  seller_name?: string | null;
  listed_price: number;
  per_unit_price: number;
  shipping_fee: number;
  unit_count: number;
  collected_at?: string | null;
}

export interface ResultRead {
  id: number;
  order_id: number;
  tenant_id: number;
  source: ResultSource;
  product_url: string;
  seller_name: string | null;
  listed_price: string | number;
  per_unit_price: string | number;
  shipping_fee: string | number;
  unit_count: number;
  collected_at: string;
  created_at: string;
}

export interface SummaryReport {
  date_from: string | null;
  date_to: string | null;
  orders_count: number;
  completed_orders_count: number;
  results_count: number;
  total_savings: string | number;
}
