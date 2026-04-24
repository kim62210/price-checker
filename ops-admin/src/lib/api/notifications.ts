import type { NotificationRecipientRead } from "@/types/api";

import { apiFetch, type ApiClientOptions } from "./client";
import { endpoints } from "./endpoints";
import { notificationRecipientListSchema, parseWith } from "./schemas";

export async function fetchNotificationRecipients(
  options: ApiClientOptions,
): Promise<NotificationRecipientRead[]> {
  const data = await apiFetch<unknown>(endpoints.notifications.recipients, {}, options);
  return parseWith(notificationRecipientListSchema, data);
}
