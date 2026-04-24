import type {
  OrderCreatePayload,
  OrderRead,
  NotificationRecipientRead,
  ResultRead,
  ResultUploadPayload,
  ShopCreate,
  ShopRead,
  SummaryReport,
  TenantRead,
  UserRead,
} from '../types/api';
import { apiFetch, type ApiClientOptions } from './client';
import { endpoints } from './endpoints';
import {
  orderSchema,
  orderListSchema,
  notificationRecipientListSchema,
  resultSchema,
  resultListSchema,
  shopListSchema,
  shopSchema,
  summaryReportSchema,
  tenantSchema,
  userSchema,
} from './schemas';

function parseWith<T>(schema: { parse: (value: unknown) => T }, value: unknown): T {
  return schema.parse(value);
}

export async function fetchTenant(options: ApiClientOptions): Promise<TenantRead> {
  const data = await apiFetch<unknown>(endpoints.tenancy.me, {}, options);
  return parseWith(tenantSchema, data);
}

export async function fetchCurrentUser(options: ApiClientOptions): Promise<UserRead> {
  const data = await apiFetch<unknown>(endpoints.tenancy.user, {}, options);
  return parseWith(userSchema, data);
}

export async function fetchShops(options: ApiClientOptions): Promise<ShopRead[]> {
  const data = await apiFetch<unknown>(endpoints.tenancy.shops, {}, options);
  return parseWith(shopListSchema, data);
}

export async function createShop(payload: ShopCreate, options: ApiClientOptions): Promise<ShopRead> {
  const data = await apiFetch<unknown>(
    endpoints.tenancy.shops,
    { method: 'POST', body: JSON.stringify(payload) },
    options,
  );
  return parseWith(shopSchema, data);
}

export async function createOrder(payload: OrderCreatePayload, options: ApiClientOptions): Promise<OrderRead> {
  const data = await apiFetch<unknown>(
    endpoints.procurement.orders,
    { method: 'POST', body: JSON.stringify(payload) },
    options,
  );
  return parseWith(orderSchema, data);
}

export async function fetchOrders(options: ApiClientOptions): Promise<OrderRead[]> {
  const data = await apiFetch<unknown>(endpoints.procurement.orders, {}, options);
  return parseWith(orderListSchema, data);
}

export async function fetchOrderResults(orderId: number, options: ApiClientOptions): Promise<ResultRead[]> {
  const data = await apiFetch<unknown>(endpoints.procurement.orderResults(orderId), {}, options);
  return parseWith(resultListSchema, data);
}

export async function fetchNotificationRecipients(options: ApiClientOptions): Promise<NotificationRecipientRead[]> {
  const data = await apiFetch<unknown>(endpoints.notifications.recipients, {}, options);
  return parseWith(notificationRecipientListSchema, data);
}

export async function uploadResult(
  orderId: number,
  payload: ResultUploadPayload,
  options: ApiClientOptions,
): Promise<ResultRead> {
  const data = await apiFetch<unknown>(
    endpoints.procurement.orderResults(orderId),
    { method: 'POST', body: JSON.stringify(payload) },
    options,
  );
  return parseWith(resultSchema, data);
}

export async function fetchSummaryReport(options: ApiClientOptions): Promise<SummaryReport> {
  const data = await apiFetch<unknown>(endpoints.procurement.reportSummary, {}, options);
  return parseWith(summaryReportSchema, data);
}
