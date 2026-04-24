import { describe, expect, it } from "vitest";

import { allNavItems, navGroups } from "./nav";

describe("nav", () => {
  it("groups operational and internal items without duplicates", () => {
    const hrefs = allNavItems.map((item) => item.href);
    const uniqueHrefs = new Set(hrefs);
    expect(hrefs.length).toBe(uniqueHrefs.size);
  });

  it("keeps dashboard item pointing to root", () => {
    expect(allNavItems.find((item) => item.key === "dashboard")?.href).toBe("/");
  });

  it("places settings inside the internal group", () => {
    const internal = navGroups.find((group) => group.labelKey === "internal");
    expect(internal?.items.some((item) => item.key === "settings")).toBe(true);
  });
});
