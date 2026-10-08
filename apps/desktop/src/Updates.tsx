import { useCallback, useEffect, useRef, useState } from "react";
import { check } from "@tauri-apps/plugin-updater";
import type { Update } from "@tauri-apps/plugin-updater";
import { Download, RefreshCw, X } from "lucide-react";
import { BRAND, bytes, restartApplication } from "./api";
import { Dialog, Spinner } from "./components";

type Phase =
  "idle" | "checking" | "available" | "downloading" | "installing" | "restart";
const releaseResource = (update: Update | null) => {
  if (update) void update.close().catch(() => {});
};

/** Track in-flight work synchronously, including before React paints busy state. */
export function usePendingOperations() {
  const count = useRef(0);
  const begin = useCallback(() => {
    count.current++;
  }, []);
  const end = useCallback(() => {
    count.current--;
  }, []);
  const hasPendingWork = useCallback(() => count.current > 0, []);
  return { begin, end, hasPendingWork };
}

export function useAppUpdates({
  enabled,
  canInstall,
  notify,
  hasPendingWork = () => false,
}: {
  enabled: boolean;
  canInstall: boolean;
  notify: (message: string, error?: boolean) => void;
  hasPendingWork?: () => boolean;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [available, setAvailable] = useState<{
    version: string;
    body?: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<number | null>(null);
  const [progress, setProgress] = useState({ downloaded: 0, total: 0 });
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(() =>
    localStorage.getItem("separator-dismissed-update"),
  );
  const resource = useRef<Update | null>(null);
  const checking = useRef(false);
  const installing = useRef(false);
  const isBusy = useCallback(() => installing.current, []);
  const restartPending = useRef(false);
  const alive = useRef(true);
  const allowed = useRef(canInstall);
  const attemptedAt = useRef(0);
  useEffect(() => {
    allowed.current = canInstall;
  }, [canInstall]);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      releaseResource(resource.current);
      resource.current = null;
    };
  }, []);
  const checkForUpdates = useCallback(
    async (manual = false) => {
      if (checking.current || installing.current || restartPending.current)
        return;
      checking.current = true;
      attemptedAt.current = Date.now();
      setPhase("checking");
      if (manual) setError(null);
      try {
        const update = await check({ timeout: 20000 });
        if (!alive.current) {
          releaseResource(update);
          return;
        }
        releaseResource(resource.current);
        resource.current = update;
        setAvailable(
          update ? { version: update.version, body: update.body } : null,
        );
        setError(null);
        setLastChecked(Date.now());
        setPhase(update ? "available" : "idle");
        if (manual) {
          setDismissed(null);
          localStorage.removeItem("separator-dismissed-update");
          notify(
            update
              ? `Separator ${update.version} is available.`
              : "You have the latest published version.",
          );
        }
      } catch (e) {
        if (alive.current) {
          const message = `Could not check for updates: ${String(e instanceof Error ? e.message : e)}`;
          setError(message);
          setPhase(resource.current ? "available" : "idle");
          if (manual) notify(message, true);
        }
      } finally {
        checking.current = false;
      }
    },
    [notify],
  );
  useEffect(() => {
    if (!enabled) return;
    const initial = window.setTimeout(() => void checkForUpdates(), 5000);
    const interval = window.setInterval(
      () => void checkForUpdates(),
      60 * 60 * 1000,
    );
    const focus = () => {
      if (Date.now() - attemptedAt.current >= 60 * 60 * 1000)
        void checkForUpdates();
    };
    window.addEventListener("focus", focus);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(interval);
      window.removeEventListener("focus", focus);
    };
  }, [enabled, checkForUpdates]);
  const restart = async () => {
    if (!allowed.current || hasPendingWork()) {
      setError(
        "Finish or pause processing and finish downloads before restarting.",
      );
      return;
    }
    setError(null);
    try {
      await restartApplication();
    } catch (e) {
      setError(
        `The update is installed, but restart failed: ${String(e)}. Close and reopen Separator or try again.`,
      );
    }
  };
  const install = async () => {
    const update = resource.current;
    if (!update || checking.current || installing.current) return;
    if (!allowed.current || hasPendingWork()) {
      setError(
        "Finish or pause processing and finish all model/runtime downloads before installing.",
      );
      return;
    }
    installing.current = true;
    setError(null);
    setProgress({ downloaded: 0, total: 0 });
    setPhase("downloading");
    try {
      await update.downloadAndInstall(
        (event) => {
          if (!alive.current) return;
          if (event.event === "Started")
            setProgress({
              downloaded: 0,
              total: event.data.contentLength ?? 0,
            });
          if (event.event === "Progress")
            setProgress((p) => ({
              ...p,
              downloaded: p.downloaded + event.data.chunkLength,
            }));
          if (event.event === "Finished") setPhase("installing");
        },
        { timeout: 900000 },
      );
      releaseResource(update);
      resource.current = null;
      restartPending.current = true;
      setPhase("restart");
      await restart();
    } catch (e) {
      if (resource.current === update) {
        releaseResource(update);
        resource.current = null;
        setAvailable(null);
        setPhase("idle");
      }
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      installing.current = false;
    }
  };
  const dismiss = () => {
    if (!available) return;
    setDismissed(available.version);
    localStorage.setItem("separator-dismissed-update", available.version);
  };
  return {
    phase,
    available,
    error,
    lastChecked,
    progress,
    open,
    setOpen,
    checkForUpdates,
    install,
    restart,
    dismiss,
    isBusy,
    busy: ["downloading", "installing"].includes(phase),
    showBanner: Boolean(available && available.version !== dismissed),
    canInstall,
  };
}

export function UpdateBanner({
  updates,
}: {
  updates: ReturnType<typeof useAppUpdates>;
}) {
  if (!updates.showBanner || !updates.available) return null;
  return (
    <div className="update-banner" role="status">
      <Download size={18} />
      <span>
        <strong>
          Separator {updates.available.version}{" "}
          {updates.phase === "restart" ? "is installed" : "is available"}
        </strong>
        <small>
          {updates.phase === "restart"
            ? "Restart Separator to finish the update."
            : "A new signed application update is ready."}
        </small>
      </span>
      <button onClick={() => updates.setOpen(true)}>Review update</button>
      <button
        aria-label="Dismiss update notification"
        onClick={updates.dismiss}
      >
        <X size={15} />
      </button>
    </div>
  );
}
export function UpdateSettings({
  updates,
  enabled,
  onToggle,
}: {
  updates: ReturnType<typeof useAppUpdates>;
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
}) {
  return (
    <section className="settings-section">
      <h2>Application updates</h2>
      <p>
        Installed version: {BRAND.version}. Updates are checked against the
        signed GitHub release feed.
      </p>
      <label className="check-label">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onToggle(e.target.checked)}
          disabled={updates.busy}
        />
        Automatically check on startup and hourly
      </label>
      <p className="muted">
        Available updates appear in the app. Checks contact GitHub; your audio
        stays local. Installation always requires your choice.
      </p>
      <div className="actions">
        <button
          disabled={
            updates.phase === "checking" ||
            updates.phase === "restart" ||
            updates.busy
          }
          onClick={() => void updates.checkForUpdates(true)}
        >
          <RefreshCw size={15} />
          {updates.phase === "checking"
            ? "Checking…"
            : "Check for signed updates"}
        </button>
        {updates.available && (
          <button className="primary" onClick={() => updates.setOpen(true)}>
            Review {updates.available.version}
          </button>
        )}
      </div>
      {updates.lastChecked && (
        <p className="muted">
          Last checked: {new Date(updates.lastChecked).toLocaleString()}
        </p>
      )}
      {updates.error && (
        <p className="error-inline" role="alert">
          {updates.error}
        </p>
      )}
    </section>
  );
}
export function UpdateDialog({
  updates,
}: {
  updates: ReturnType<typeof useAppUpdates>;
}) {
  if (!updates.open) return null;
  return (
    <Dialog
      title={
        updates.phase === "restart"
          ? "Update installed"
          : `Update to ${updates.available?.version ?? "the latest version"}`
      }
      busy={updates.busy}
      onClose={() => {
        if (!updates.busy) updates.setOpen(false);
      }}
    >
      <p>
        Models, projects, presets and audio files are preserved. The app will
        restart after installation.
      </p>
      {updates.available?.body && (
        <pre className="update-notes">{updates.available.body}</pre>
      )}
      {updates.busy && (
        <div className="update-progress">
          <Spinner
            label={
              updates.phase === "downloading"
                ? "Downloading signed update…"
                : updates.phase === "restart"
                  ? "Ready to restart"
                  : "Verifying and installing…"
            }
          />
          <progress
            aria-label="Application update download"
            value={
              updates.progress.total ? updates.progress.downloaded : undefined
            }
            max={updates.progress.total || undefined}
          />
          <small>
            {bytes(updates.progress.downloaded)}
            {updates.progress.total
              ? ` of ${bytes(updates.progress.total)}`
              : " downloaded"}
          </small>
        </div>
      )}
      {updates.error && (
        <p role="alert" className="error-inline">
          {updates.error}
        </p>
      )}
      {!updates.canInstall && !updates.busy && (
        <p>
          Finish or pause processing and finish downloads before installing.
        </p>
      )}
      <div className="dialog-actions">
        <button disabled={updates.busy} onClick={() => updates.setOpen(false)}>
          Later
        </button>
        {updates.phase === "restart" ? (
          <button
            className="primary"
            disabled={!updates.canInstall}
            onClick={() => void updates.restart()}
          >
            Restart now
          </button>
        ) : (
          <button
            className="primary"
            disabled={
              !updates.available ||
              !updates.canInstall ||
              updates.busy ||
              updates.phase === "checking"
            }
            onClick={() => void updates.install()}
          >
            Install and restart
          </button>
        )}
      </div>
    </Dialog>
  );
}
