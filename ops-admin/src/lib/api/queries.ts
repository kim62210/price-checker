"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  OrderCreatePayload,
  ResultUploadPayload,
  ShopCreate,
} from "@/types/api";

import { toClientOptions, useApiConfig } from "./config";
import {
  createOrder,
  createShop,
  fetchCurrentUser,
  fetchOrder,
  fetchOrderResults,
  fetchOrders,
  fetchShops,
  fetchSummaryReport,
  fetchTenant,
  triggerCollect,
  uploadResult,
} from "./procurement";
import { fetchNotificationRecipients } from "./notifications";

export const queryKeys = {
  tenant: ["tenant"] as const,
  currentUser: ["user", "me"] as const,
  shops: ["shops"] as const,
  orders: ["orders"] as const,
  order: (id: number) => ["orders", id] as const,
  orderResults: (id: number) => ["orders", id, "results"] as const,
  summary: ["reports", "summary"] as const,
  recipients: ["notifications", "recipients"] as const,
};

export function useTenantQuery() {
  const { config, isAuthorized, isHydrated } = useApiConfig();
  return useQuery({
    queryKey: queryKeys.tenant,
    queryFn: () => fetchTenant(toClientOptions(config)),
    enabled: isHydrated && isAuthorized,
  });
}

export function useCurrentUserQuery() {
  const { config, isAuthorized, isHydrated } = useApiConfig();
  return useQuery({
    queryKey: queryKeys.currentUser,
    queryFn: () => fetchCurrentUser(toClientOptions(config)),
    enabled: isHydrated && isAuthorized,
  });
}

export function useShopsQuery() {
  const { config, isAuthorized, isHydrated } = useApiConfig();
  return useQuery({
    queryKey: queryKeys.shops,
    queryFn: () => fetchShops(toClientOptions(config)),
    enabled: isHydrated && isAuthorized,
  });
}

export function useOrdersQuery() {
  const { config, isAuthorized, isHydrated } = useApiConfig();
  return useQuery({
    queryKey: queryKeys.orders,
    queryFn: () => fetchOrders(toClientOptions(config)),
    enabled: isHydrated && isAuthorized,
  });
}

export function useOrderQuery(id: number | null) {
  const { config, isAuthorized, isHydrated } = useApiConfig();
  return useQuery({
    queryKey: queryKeys.order(id ?? -1),
    queryFn: () => fetchOrder(id as number, toClientOptions(config)),
    enabled: isHydrated && isAuthorized && id !== null,
  });
}

export function useOrderResultsQuery(id: number | null) {
  const { config, isAuthorized, isHydrated } = useApiConfig();
  return useQuery({
    queryKey: queryKeys.orderResults(id ?? -1),
    queryFn: () => fetchOrderResults(id as number, toClientOptions(config)),
    enabled: isHydrated && isAuthorized && id !== null,
  });
}

export function useSummaryQuery() {
  const { config, isAuthorized, isHydrated } = useApiConfig();
  return useQuery({
    queryKey: queryKeys.summary,
    queryFn: () => fetchSummaryReport(toClientOptions(config)),
    enabled: isHydrated && isAuthorized,
  });
}

export function useNotificationRecipientsQuery() {
  const { config, isAuthorized, isHydrated } = useApiConfig();
  return useQuery({
    queryKey: queryKeys.recipients,
    queryFn: () => fetchNotificationRecipients(toClientOptions(config)),
    enabled: isHydrated && isAuthorized,
  });
}

export function useCreateOrderMutation() {
  const { config } = useApiConfig();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OrderCreatePayload) => createOrder(payload, toClientOptions(config)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.orders });
    },
  });
}

export function useCreateShopMutation() {
  const { config } = useApiConfig();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ShopCreate) => createShop(payload, toClientOptions(config)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.shops });
    },
  });
}

export function useUploadResultMutation(orderId: number) {
  const { config } = useApiConfig();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ResultUploadPayload) =>
      uploadResult(orderId, payload, toClientOptions(config)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.orderResults(orderId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.order(orderId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.summary });
    },
  });
}

export function useTriggerCollectMutation() {
  const { config } = useApiConfig();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderId: number) => triggerCollect(orderId, toClientOptions(config)),
    onSuccess: (_data, orderId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.order(orderId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.orders });
    },
  });
}
