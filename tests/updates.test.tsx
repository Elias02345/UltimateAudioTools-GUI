import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ check: vi.fn(), restart: vi.fn() }));
vi.mock("@tauri-apps/plugin-updater", () => ({ check: mocks.check }));
vi.mock("../apps/desktop/src/api", () => ({
  BRAND: { name: "Separator", version: "0.1.5" },
  bytes: (n: number) => String(n),
  restartApplication: mocks.restart,
}));
import { useAppUpdates } from "../apps/desktop/src/Updates";

function update(version = "0.1.6") {
  return {
    version,
    body: "Release notes",
    close: vi.fn().mockResolvedValue(undefined),
    downloadAndInstall: vi.fn().mockResolvedValue(undefined),
  };
}
beforeEach(() => {
  localStorage.clear();
  vi.useFakeTimers();
  mocks.check.mockReset();
  mocks.restart.mockReset().mockResolvedValue(undefined);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
describe("signed update lifecycle", () => {
  it("checks automatically, keeps a persistent notice and releases the native resource", async () => {
    const candidate = update();
    mocks.check.mockResolvedValue(candidate);
    const notify = vi.fn();
    const hook = renderHook(() =>
      useAppUpdates({ enabled: true, canInstall: true, notify }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(mocks.check).toHaveBeenCalledWith({ timeout: 20000 });
    expect(hook.result.current.showBanner).toBe(true);
    expect(notify).not.toHaveBeenCalled();
    act(() => hook.result.current.dismiss());
    expect(hook.result.current.showBanner).toBe(false);
    hook.unmount();
    expect(candidate.close).toHaveBeenCalledOnce();
  });
  it("stays quiet automatically offline and gives a useful manual error", async () => {
    mocks.check.mockRejectedValue(new Error("offline"));
    const notify = vi.fn();
    const hook = renderHook(() =>
      useAppUpdates({ enabled: true, canInstall: true, notify }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(notify).not.toHaveBeenCalled();
    expect(hook.result.current.available).toBeNull();
    await act(() => hook.result.current.checkForUpdates(true));
    expect(notify).toHaveBeenCalledWith(
      expect.stringContaining("offline"),
      true,
    );
  });
  it("checks installation safety again after work starts", async () => {
    const candidate = update();
    mocks.check.mockResolvedValue(candidate);
    const notify = vi.fn();
    const hook = renderHook(
      ({ canInstall }) => useAppUpdates({ enabled: false, canInstall, notify }),
      { initialProps: { canInstall: true } },
    );
    await act(() => hook.result.current.checkForUpdates(true));
    hook.rerender({ canInstall: false });
    await act(() => hook.result.current.install());
    expect(candidate.downloadAndInstall).not.toHaveBeenCalled();
    expect(hook.result.current.error).toContain("processing");
  });
  it("accounts for real chunk progress and restarts only after installation", async () => {
    const candidate = update();
    candidate.downloadAndInstall.mockImplementation(async (event) => {
      event({ event: "Started", data: { contentLength: 100 } });
      event({ event: "Progress", data: { chunkLength: 40 } });
      event({ event: "Progress", data: { chunkLength: 60 } });
      event({ event: "Finished" });
    });
    mocks.check.mockResolvedValue(candidate);
    const notify = vi.fn();
    const hook = renderHook(() =>
      useAppUpdates({ enabled: false, canInstall: true, notify }),
    );
    await act(() => hook.result.current.checkForUpdates());
    await act(() => hook.result.current.install());
    expect(hook.result.current.progress).toEqual({
      downloaded: 100,
      total: 100,
    });
    expect(hook.result.current.phase).toBe("restart");
    expect(mocks.restart).toHaveBeenCalledOnce();
    expect(candidate.close).toHaveBeenCalledOnce();
  });
  it("closes a check that finishes after the view unmounts", async () => {
    const candidate = update();
    let resolve: (value: unknown) => void = () => {};
    mocks.check.mockImplementation(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    const notify = vi.fn();
    const hook = renderHook(() =>
      useAppUpdates({ enabled: false, canInstall: true, notify }),
    );
    let pending: Promise<void>;
    act(() => {
      pending = hook.result.current.checkForUpdates();
    });
    hook.unmount();
    await act(async () => {
      resolve(candidate);
      await pending;
    });
    expect(candidate.close).toHaveBeenCalledOnce();
  });
  it("releases a failed download and allows a fresh check", async () => {
    const candidate = update();
    candidate.downloadAndInstall.mockRejectedValue(new Error("bad signature"));
    mocks.check.mockResolvedValue(candidate);
    const notify = vi.fn();
    const hook = renderHook(() =>
      useAppUpdates({ enabled: false, canInstall: true, notify }),
    );
    await act(() => hook.result.current.checkForUpdates());
    await act(() => hook.result.current.install());
    expect(hook.result.current.busy).toBe(false);
    expect(hook.result.current.error).toContain("bad signature");
    expect(mocks.restart).not.toHaveBeenCalled();
    expect(candidate.close).toHaveBeenCalledOnce();
  });
});

it("keeps the update guard live in a continuation captured before downloading", async () => {
  const candidate = update();
  let finish: () => void = () => {};
  candidate.downloadAndInstall.mockImplementation(
    () =>
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
  );
  mocks.check.mockResolvedValue(candidate);
  const notify = vi.fn();
  const hook = renderHook(() =>
    useAppUpdates({ enabled: false, canInstall: true, notify }),
  );
  await act(() => hook.result.current.checkForUpdates());
  const capturedGuard = hook.result.current.isBusy;
  let installation: Promise<void>;
  act(() => {
    installation = hook.result.current.install();
  });
  expect(capturedGuard()).toBe(true);
  await act(async () => {
    finish();
    await installation;
  });
  expect(capturedGuard()).toBe(false);
});

it("blocks installation while a work-start operation is awaiting a response", async () => {
  const candidate = update();
  mocks.check.mockResolvedValue(candidate);
  const notify = vi.fn();
  let pending = false;
  const hook = renderHook(() =>
    useAppUpdates({
      enabled: false,
      canInstall: true,
      notify,
      hasPendingWork: () => pending,
    }),
  );
  await act(() => hook.result.current.checkForUpdates());
  pending = true;
  await act(() => hook.result.current.install());
  expect(candidate.downloadAndInstall).not.toHaveBeenCalled();
});

it("rechecks work safety before retrying an installed update restart", async () => {
  const candidate = update();
  mocks.check.mockResolvedValue(candidate);
  mocks.restart.mockRejectedValue(new Error("restart unavailable"));
  const notify = vi.fn();
  const hook = renderHook(
    ({ canInstall }) => useAppUpdates({ enabled: false, canInstall, notify }),
    { initialProps: { canInstall: true } },
  );
  await act(() => hook.result.current.checkForUpdates());
  await act(() => hook.result.current.install());
  expect(hook.result.current.phase).toBe("restart");
  hook.rerender({ canInstall: false });
  await act(() => hook.result.current.restart());
  expect(mocks.restart).toHaveBeenCalledOnce();
  expect(hook.result.current.error).toContain("before restarting");
});
