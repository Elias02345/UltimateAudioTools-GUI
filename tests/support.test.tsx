import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
const open = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
vi.mock("@tauri-apps/plugin-opener", () => ({ openUrl: open }));
import { Support } from "../apps/desktop/src/Support";
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
describe("creator support", () => {
  it("copies the exact requested wallet address and acknowledges it", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const notify = vi.fn();
    render(<Support notify={notify} onError={vi.fn()} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Copy Ethereum address" }),
    );
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith(
        "0x81deF905D66fd17433003e749f1e69bCFd95664d",
      ),
    );
    expect(notify).toHaveBeenCalledWith("Ethereum address copied.");
  });
  it("opens the supplied PayPal and contributor links through the native opener", () => {
    render(<Support notify={vi.fn()} onError={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Donate with PayPal/ }));
    expect(open).toHaveBeenCalledWith(
      "https://www.paypal.com/paypalme/EliasK09",
    );
    fireEvent.click(screen.getByRole("button", { name: "@Elias02345" }));
    expect(open).toHaveBeenCalledWith("https://github.com/Elias02345");
  });
});
