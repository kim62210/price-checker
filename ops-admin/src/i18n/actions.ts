"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";

import { isLocale, type Locale, LOCALE_COOKIE } from "./config";

export async function setLocaleAction(next: Locale) {
  if (!isLocale(next)) return;
  const store = await cookies();
  store.set({
    name: LOCALE_COOKIE,
    value: next,
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
  });
  revalidatePath("/");
}
