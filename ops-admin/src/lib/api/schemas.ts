import { z } from "zod";

const decimalLike = z.union([z.string(), z.number()]);

export const tenantSchema = z.object({
  id: z.number(),
  name: z.string(),
  plan: z.enum(["starter", "pro", "enterprise"]),
  api_quota_monthly: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const userSchema = z.object({
  id: z.number(),
  tenant_id: z.number(),
  email: z.string(),
  auth_provider: z.enum(["kakao", "naver", "local"]),
  provider_user_id: z.string(),
  role: z.enum(["owner", "staff"]),
  last_login_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const shopSchema = z.object({
  id: z.number(),
  tenant_id: z.number(),
  name: z.string(),
  business_number: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const orderSchema = z.object({
  id: z.number(),
  tenant_id: z.number(),
  shop_id: z.number(),
  product_name: z.string(),
  option_text: z.string().nullable(),
  quantity: z.number(),
  unit: z.string(),
  target_unit_price: decimalLike.nullable(),
  memo: z.string().nullable(),
  status: z.enum(["draft", "collecting", "completed", "cancelled"]),
  created_at: z.string(),
  updated_at: z.string(),
});

export const notificationRecipientSchema = z.object({
  id: z.number(),
  tenant_id: z.number(),
  shop_id: z.number().nullable(),
  user_id: z.number().nullable(),
  phone_e164: z.string(),
  display_name: z.string(),
  is_active: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const resultSchema = z.object({
  id: z.number(),
  order_id: z.number(),
  tenant_id: z.number(),
  source: z.enum(["naver", "coupang", "manual"]),
  product_url: z.string(),
  seller_name: z.string().nullable(),
  listed_price: decimalLike,
  per_unit_price: decimalLike,
  shipping_fee: decimalLike,
  unit_count: z.number(),
  collected_at: z.string(),
  created_at: z.string(),
});

export const summaryReportSchema = z.object({
  date_from: z.string().nullable(),
  date_to: z.string().nullable(),
  orders_count: z.number(),
  completed_orders_count: z.number(),
  results_count: z.number(),
  total_savings: decimalLike,
});

export const shopListSchema = z.array(shopSchema);
export const orderListSchema = z.array(orderSchema);
export const resultListSchema = z.array(resultSchema);
export const notificationRecipientListSchema = z.array(notificationRecipientSchema);

function parseWith<T>(schema: { parse: (value: unknown) => T }, value: unknown): T {
  return schema.parse(value);
}

export { parseWith };
