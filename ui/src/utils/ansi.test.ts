import { describe, expect, it } from "vitest";
import { parseAnsi, stripAnsi } from "./ansi";

describe("parseAnsi", () => {
  it("returns plain text without formatting for plain strings", () => {
    const res = parseAnsi("Hello world");
    expect(res).toEqual([{ text: "Hello world" }]);
  });

  it("parses single color codes", () => {
    const res = parseAnsi("\x1b[32mSuccess\x1b[0m");
    expect(res).toEqual([
      {
        text: "Success",
        color: "text-emerald-400",
      },
    ]);
  });

  it("parses combined codes like bold and color", () => {
    const res = parseAnsi("Prefix \x1b[1;31mError\x1b[0m suffix");
    expect(res).toEqual([
      { text: "Prefix " },
      { text: "Error", color: "text-rose-400", bold: true },
      { text: " suffix" },
    ]);
  });
});

describe("stripAnsi", () => {
  it("removes all ANSI escape codes", () => {
    expect(stripAnsi("\x1b[32mSuccess\x1b[0m: done")).toBe("Success: done");
  });
});
