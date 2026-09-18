import { describe, expect, it } from "vitest";
import { AUTHOR, linkProps } from "@/lib/site";

describe("author credit", () => {
  it("names the author", () => {
    expect(AUTHOR.name).toBe("John Wasikye");
    expect(AUTHOR.initials).toBe("JW");
  });

  it("opens a real website in a new tab, safely", () => {
    expect(linkProps("https://example.com/projects")).toEqual({
      href: "https://example.com/projects",
      target: "_blank",
      rel: "noopener noreferrer",
    });
  });

  it("leaves a placeholder link alone so it does not open a blank tab", () => {
    expect(linkProps("#")).toEqual({ href: "#" });
  });
});
