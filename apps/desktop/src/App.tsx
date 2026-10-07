import { useCallback, useEffect, useRef, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { openUrl } from "@tauri-apps/plugin-opener";
import {
  AudioLines,
  ArrowRight,
  ArrowUp,
  ArrowDown,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  Download,
  FolderOpen,
  HardDrive,
  Home,
  Layers3,
  ListMusic,
  Mic2,
  Music2,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import {
  activeJob,
  api,
  BRAND,
  bytes,
  chooseAudio,
  chooseFolder,
  exportPreset,
  importPreset,
  onEngineEvent,
  reveal,
  time,
  validate,
} from "./api";
import type {
  AudioMetadata,
  Capabilities,
  Job,
  ModelInfo,
  Preset,
  Settings,
} from "./api";
import { AudioWorkspace } from "./AudioWorkspace";
import { Dialog, Empty, Spinner } from "./components";
import {
  InferenceControls,
  OutputControls,
  PresetEditor,
} from "./PresetEditor";

type Screen =
  "Home" | "Queue" | "Library" | "Compare" | "Models" | "Presets" | "Settings";
type Initial = {
  v: number;
  settings: Settings;
  jobs: Job[];
  presets: Preset[];
  running: boolean;
};
type DownloadState = {
  kind: string;
  bytes?: number;
  total?: number | null;
  speed?: number;
  eta?: number | null;
  error?: string;
};
type Confirmation = {
  title: string;
  body: string;
  action: string;
  run: () => Promise<void>;
};
const navigation = [
  { label: "Home" as const, icon: Home },
  { label: "Queue" as const, icon: ListMusic },
  { label: "Library" as const, icon: Layers3 },
  { label: "Compare" as const, icon: SlidersHorizontal },
  { label: "Models" as const, icon: HardDrive },
  { label: "Presets" as const, icon: Sparkles },
  { label: "Settings" as const, icon: Settings2 },
];

export function App() {
  const [screen, setScreen] = useState<Screen>(() => {
    const saved = localStorage.getItem("screen");
    return navigation.some((n) => n.label === saved)
      ? (saved as Screen)
      : "Home";
  });
  const [settings, setSettings] = useState<Settings | null>(null);
  const [draftSettings, setDraftSettings] = useState<Settings | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [files, setFiles] = useState<AudioMetadata[]>([]);
  const [target, setTarget] = useState<Preset["task"]>("Instrumental");
  const [quality, setQuality] = useState<Settings["default_quality"]>("Ultra");
  const [custom, setCustom] = useState<Preset | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [running, setRunning] = useState(false);
  const [startup, setStartup] = useState(true);
  const [startupError, setStartupError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<{
    message: string;
    error: boolean;
  } | null>(null);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [editor, setEditor] = useState<Preset | null>(null);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [downloads, setDownloads] = useState<Record<string, DownloadState>>({});
  const [query, setQuery] = useState("");
  const [modelFilter, setModelFilter] = useState("All");
  const [modelDetail, setModelDetail] = useState<ModelInfo | null>(null);
  const [setupChecks, setSetupChecks] = useState<
    { name: string; passed: boolean; detail: string }[]
  >([]);
  const [compareChoices, setCompareChoices] = useState<string[]>([]);
  const [compareGroup, setCompareGroup] = useState<string | null>(null);
  const [blind, setBlind] = useState(true);
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [storage, setStorage] = useState<Record<string, number> | null>(null);
  const [licenses, setLicenses] = useState(false);
  const [listLimit, setListLimit] = useState(100);
  const allowClose = useRef(false);
  const jobsRef = useRef(jobs);
  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);
  const notify = useCallback(
    (message: string, error = false) => setToast({ message, error }),
    [],
  );
  const onError = useCallback(
    (error: unknown) =>
      notify(String(error instanceof Error ? error.message : error), true),
    [notify],
  );
  const perform = useCallback(
    async (name: string, work: () => Promise<void>) => {
      setBusy(name);
      try {
        await work();
      } catch (error) {
        onError(error);
      } finally {
        setBusy(null);
      }
    },
    [onError],
  );
  const refreshJobs = useCallback(
    async () =>
      setJobs(
        (await api<Job[]>("list_jobs")).map((j) => validate<Job>("Job", j)),
      ),
    [],
  );
  const refreshModels = useCallback(
    async (refresh = false) =>
      setModels(
        (await api<ModelInfo[]>("list_models", { refresh })).map((m) =>
          validate<ModelInfo>("ModelInfo", m),
        ),
      ),
    [],
  );
  const saveSettings = useCallback(async (next: Settings) => {
    const saved = await api<Settings>("save_settings", { settings: next });
    setSettings(validate<Settings>("Settings", saved));
    setDraftSettings((current) =>
      current && JSON.stringify(current) !== JSON.stringify(next)
        ? current
        : saved,
    );
  }, []);
  const initialize = useCallback(async () => {
    try {
      const data = await api<Initial>("initialize");
      setStartupError(null);
      setSettings(validate<Settings>("Settings", data.settings));
      setDraftSettings(data.settings);
      setJobs(data.jobs.map((j) => validate<Job>("Job", j)));
      setPresets(data.presets.map((p) => validate<Preset>("Preset", p)));
      setRunning(data.running);
      setQuality(data.settings.default_quality);
      const [caps] = await Promise.all([
        api<Capabilities>("get_capabilities"),
        refreshModels(),
      ]);
      setCapabilities(validate<Capabilities>("Capabilities", caps));
    } catch (error) {
      setStartupError(String(error));
    } finally {
      setStartup(false);
    }
  }, [refreshModels]);
  useEffect(() => {
    const task = window.setTimeout(() => {
      void initialize();
    }, 0);
    return () => window.clearTimeout(task);
  }, [initialize]);
  useEffect(() => {
    let active = true;
    const unlisten = onEngineEvent((event) => {
      if (!active || event.v !== 1) return;
      if (event.event === "job_updated") {
        try {
          const job = validate<Job>("Job", event.data.job);
          setJobs((previous) => {
            const index = previous.findIndex((j) => j.id === job.id);
            return index < 0
              ? [...previous, job]
              : previous.map((j) => (j.id === job.id ? job : j));
          });
          if (job.status === "Completed") {
            notify(`${job.source.name} is ready to listen.`);
            void refreshModels().catch(onError);
          }
          if (job.status === "Failed")
            notify(
              job.error ?? "Separation failed. Open the queue for details.",
              true,
            );
        } catch (error) {
          onError(error);
        }
      } else if (event.event === "queue_state")
        setRunning(event.data.running === true);
      else if (event.event === "model_download") {
        const model = String(event.data.model);
        setDownloads((previous) => ({
          ...previous,
          [model]: event.data as DownloadState,
        }));
        if (event.data.kind === "completed") {
          void refreshModels().catch(onError);
          notify("Model download complete.");
        }
      } else if (event.event === "engine_stopped") {
        setRunning(false);
        notify(
          "The engine stopped. Reload the runtime to recover interrupted jobs.",
          true,
        );
      }
    });
    return () => {
      active = false;
      void unlisten.then((fn) => fn());
    };
  }, [notify, onError, refreshModels]);
  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(
      () => setToast(null),
      toast.error ? 12000 : 5000,
    );
    return () => window.clearTimeout(id);
  }, [toast]);
  useEffect(() => {
    localStorage.setItem("screen", screen);
  }, [screen]);
  useEffect(() => {
    if (settings) {
      document.documentElement.dataset.theme = settings.theme;
      document.documentElement.dataset.motion = settings.reduced_motion
        ? "reduced"
        : "normal";
    }
  }, [settings]);
  const addFiles = useCallback(
    async (paths: string[]) => {
      await perform("import", async () => {
        const loaded: AudioMetadata[] = [];
        for (const path of paths) {
          try {
            loaded.push(await api<AudioMetadata>("inspect_audio", { path }));
          } catch (error) {
            onError(error);
          }
        }
        setFiles((previous) => [
          ...previous,
          ...loaded.filter((f) => !previous.some((p) => p.path === f.path)),
        ]);
      });
    },
    [perform, onError],
  );
  const openFiles = useCallback(async () => {
    await addFiles(await chooseAudio());
  }, [addFiles]);
  useEffect(() => {
    const unlisten = getCurrentWindow().onCloseRequested((event) => {
      if (allowClose.current || !jobsRef.current.some(activeJob)) return;
      event.preventDefault();
      setConfirmation({
        title: "Jobs are still processing",
        body: "Closing Separator will cancel active jobs. Completed audio files are kept.",
        action: "Cancel jobs and quit",
        run: async () => {
          await Promise.all(
            jobsRef.current
              .filter(activeJob)
              .map((j) => api("cancel_job", { id: j.id })),
          );
          allowClose.current = true;
          await getCurrentWindow().destroy();
        },
      });
    });
    const drop = getCurrentWindow().onDragDropEvent((event) => {
      if (event.payload.type === "drop") void addFiles(event.payload.paths);
    });
    return () => {
      void unlisten.then((fn) => fn());
      void drop.then((fn) => fn());
    };
  }, [addFiles]);

  const chosenPreset = (() => {
    if (custom) return custom;
    const stem = target === "Vocals" ? "vocals" : "instrumental";
    const id =
      target === "4 Stems" || ["Drums", "Bass", "Other"].includes(target)
        ? "four_stems"
        : quality === "Ultra"
          ? stem === "vocals"
            ? "vocal_balanced"
            : "instrumental_full"
          : `${quality.toLowerCase()}_${stem}`;
    const base = presets.find((p) => p.id === id);
    if (!base || !settings) return null;
    return {
      ...structuredClone(base),
      task: target,
      output: structuredClone(settings.output),
      parameters: structuredClone(settings.parameters),
      engine: settings.engine,
    };
  })();
  const enqueue = useCallback(
    async (selected: Preset, paths: AudioMetadata[], comparisonId?: string) => {
      const requests = paths.map((file) => ({
        path: file.path,
        preset: selected,
        download_consent: true,
        ...(comparisonId
          ? {
              comparison_id: comparisonId,
              range_start: rangeStart ? Number(rangeStart) : null,
              range_end: rangeEnd ? Number(rangeEnd) : null,
            }
          : {}),
      }));
      await api("enqueue", { requests, start: true });
      setRunning(true);
      await refreshJobs();
      setScreen("Queue");
    },
    [rangeStart, rangeEnd, refreshJobs],
  );
  const start = useCallback(async () => {
    if (!chosenPreset || !files.length) return;
    const missing = chosenPreset.models
      .map((id) => models.find((m) => m.id === id))
      .filter((m) => m && !m.downloaded) as ModelInfo[];
    const work = async () => {
      await enqueue(chosenPreset, files);
      setFiles([]);
    };
    if (missing.length && !settings?.auto_download) {
      const known = missing.every((m) => m.size != null);
      setConfirmation({
        title: "Download required models",
        body: `${missing.length} model${missing.length === 1 ? "" : "s"} will download from upstream (${known ? bytes(missing.reduce((sum, m) => sum + (m.size ?? 0), 0)) : "total size not published"}). Individual weight licenses are listed in Models. Audio stays on this computer.`,
        action: "Download & separate",
        run: work,
      });
    } else await perform("separate", work);
  }, [chosenPreset, files, models, settings?.auto_download, enqueue, perform]);
  useEffect(() => {
    const shortcut = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      if (e.key.toLowerCase() === "o") {
        e.preventDefault();
        void openFiles().catch(onError);
      }
      if (e.key === ",") {
        e.preventDefault();
        setScreen("Settings");
      }
      if (e.key === "Enter" && screen === "Home") {
        e.preventDefault();
        void start();
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, [openFiles, onError, screen, start]);

  const result = jobs.find(
    (j) => j.id === selectedJob && j.status === "Completed",
  );
  const completed = jobs.filter((j) => j.status === "Completed");
  const active = jobs.find(activeJob);
  const runAgain = (job: Job) => {
    setCustom(structuredClone(job.request.preset));
    setFiles([job.source]);
    setScreen("Home");
    setSelectedJob(null);
  };
  const newPreset = () => {
    if (!chosenPreset) return;
    setEditor({
      ...structuredClone(chosenPreset),
      id: `user_${crypto.randomUUID().replaceAll("-", "")}`,
      name: "My ensemble",
      builtin: false,
      quality: "Custom",
    });
  };
  const queueAction = (method: string, id?: string) =>
    perform(method, async () => {
      await api(method, id ? { id } : {});
      await refreshJobs();
    });
  const filteredModels = models.filter(
    (m) =>
      `${m.name} ${m.id} ${m.architecture}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (modelFilter === "All" ||
        (modelFilter === "Downloaded" && m.downloaded) ||
        m.stems.includes(modelFilter) ||
        m.architecture === modelFilter),
  );
  const showSettings = (next: Settings) => setDraftSettings(next);
  const compareResults = jobs.filter(
    (j) => j.request.comparison_id === compareGroup && j.status === "Completed",
  );

  if (startup && !settings)
    return (
      <div className="launch-state">
        <AudioLines size={42} />
        <h1>{BRAND.name}</h1>
        <Spinner label="Starting your local audio engine…" />
      </div>
    );
  if (startupError)
    return (
      <div className="launch-state">
        <AudioLines size={42} />
        <h1>Let’s get the engine ready</h1>
        <p className="error-inline" role="alert">
          {startupError}
        </p>
        <button className="primary" onClick={() => void initialize()}>
          Retry runtime startup
        </button>
      </div>
    );
  if (!settings) return null;
  const editedSettings = draftSettings ?? settings;
  const settingsChanged =
    JSON.stringify(editedSettings) !== JSON.stringify(settings);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <AudioLines size={26} strokeWidth={1.8} />
          <span>
            {BRAND.name}
            <small>Local audio studio</small>
          </span>
        </div>
        <nav aria-label="Main navigation">
          {navigation.map(({ label, icon: Icon }) => (
            <button
              key={label}
              aria-current={screen === label ? "page" : undefined}
              onClick={() => {
                setScreen(label);
                setSelectedJob(null);
                setQuery("");
                setListLimit(100);
              }}
            >
              <Icon size={18} />
              <span>{label}</span>
              {label === "Queue" &&
                jobs.some((j) => j.status === "Pending" || activeJob(j)) && (
                  <span className="nav-count">
                    {
                      jobs.filter((j) => j.status === "Pending" || activeJob(j))
                        .length
                    }
                  </span>
                )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="device-indicator">
            <span className={`status-dot ${capabilities ? "online" : ""}`} />
            <div>
              <strong>
                {capabilities?.gpus[0]?.name.replace("NVIDIA GeForce ", "") ??
                  capabilities?.recommended_device.toUpperCase() ??
                  "Scanning hardware…"}
              </strong>
              <small>
                {capabilities?.cuda
                  ? `CUDA · ${bytes(capabilities.gpus[0]?.vram)}`
                  : capabilities?.mps
                    ? "Apple MPS"
                    : "Local CPU engine"}
              </small>
            </div>
          </div>
          <p>
            <ShieldCheck size={13} />
            Audio stays on this computer
          </p>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            {screen}
            {result && (
              <>
                <ChevronRight size={14} />
                Result
              </>
            )}
          </span>
          <div className="actions">
            {active && (
              <button
                className="processing-link"
                onClick={() => setScreen("Queue")}
              >
                <span className="status-dot online" />
                {active.status}
              </button>
            )}
            <button
              className="icon-button"
              aria-label="Keyboard shortcuts"
              onClick={() =>
                setConfirmation({
                  title: "Keyboard shortcuts",
                  body: "Ctrl/Cmd + O: import audio · Ctrl/Cmd + Enter: separate from Home · Ctrl/Cmd + comma: settings · Space: play/pause in results · Arrow keys on waveform: seek 5 seconds · Escape: close dialog.",
                  action: "Got it",
                  run: async () => {},
                })
              }
            >
              <CircleHelp size={18} />
            </button>
          </div>
        </header>
        <div className="workspace">
          {!settings.setup_complete ? (
            <section className="setup">
              <span className="setup-mark">
                <AudioLines size={48} />
              </span>
              <h1>Your music. Every layer.</h1>
              <p>
                Separate vocals and instruments with exceptional models, right
                on this computer.
              </p>
              <div className="setup-hardware">
                <CheckCircle2 size={22} />
                <div>
                  <strong>
                    {capabilities?.gpus[0]?.name ?? "Local processing"}
                  </strong>
                  <p>
                    {capabilities?.cuda
                      ? "CUDA acceleration is ready."
                      : capabilities?.mps
                        ? "Apple Silicon acceleration is ready."
                        : "Separator will use your CPU."}
                  </p>
                  <small>
                    Python {capabilities?.python} · audio-separator{" "}
                    {capabilities?.engine_version} · FFmpeg bundled
                  </small>
                </div>
              </div>
              <p className="muted">
                Models download when you choose them. Ultra instrumental needs
                about 1.7 GB of model storage. Your recordings are never
                uploaded.
              </p>
              {setupChecks.length > 0 && (
                <ul className="check-list">
                  {setupChecks.map((c) => (
                    <li key={c.name}>
                      {c.passed ? <Check size={16} /> : <X size={16} />}
                      <strong>{c.name}</strong>
                      <span>{c.detail}</span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="actions">
                <button
                  onClick={() =>
                    void perform("selftest", async () =>
                      setSetupChecks(await api("self_test")),
                    )
                  }
                  disabled={busy !== null}
                >
                  {busy === "selftest" ? "Testing…" : "Run readiness test"}
                </button>
                <button
                  className="primary"
                  onClick={() =>
                    void perform("setup", async () => {
                      const checks = await api<typeof setupChecks>("self_test");
                      setSetupChecks(checks);
                      if (checks.some((c) => !c.passed))
                        throw new Error(
                          "A readiness check failed. Review the results and fix the folder or runtime before continuing.",
                        );
                      await saveSettings({ ...settings, setup_complete: true });
                      setScreen("Home");
                    })
                  }
                  disabled={!capabilities || busy !== null}
                >
                  Recommended setup
                  <ArrowRight size={16} />
                </button>
              </div>
            </section>
          ) : result ? (
            <AudioWorkspace
              key={result.id}
              jobs={[result]}
              onError={onError}
              onAgain={runAgain}
            />
          ) : screen === "Home" ? (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">
                    A little less noise. A lot more music.
                  </p>
                  <h1>Find the sound you’re after.</h1>
                  <p>Drop a recording. Choose a layer. Make it yours.</p>
                </div>
                <button
                  onClick={() => {
                    setAdvanced(!advanced);
                    if (!custom && chosenPreset)
                      setCustom(structuredClone(chosenPreset));
                  }}
                  aria-pressed={advanced}
                >
                  <SlidersHorizontal size={16} />
                  {advanced ? "Simple mode" : "Studio mode"}
                </button>
              </div>
              <div className="home-grid">
                <div className="import-area">
                  <button
                    className={`dropzone ${files.length ? "has-files" : ""}`}
                    data-testid="import-audio"
                    onClick={() => void openFiles().catch(onError)}
                  >
                    <span className="drop-symbol">
                      <AudioLines size={38} strokeWidth={1.4} />
                      <Plus size={14} />
                    </span>
                    <strong>
                      {files.length
                        ? "Add another recording"
                        : "Drop your audio here"}
                    </strong>
                    <span>or click to browse files</span>
                    <small>WAV · FLAC · MP3 · M4A · AAC · OGG</small>
                  </button>
                  <div className="import-actions">
                    <button
                      className="text-button"
                      onClick={() =>
                        void perform("folder", async () => {
                          const path = await chooseFolder();
                          if (path)
                            await addFiles(
                              await api<string[]>("import_folder", { path }),
                            );
                        })
                      }
                    >
                      <FolderOpen size={14} />
                      Add folder
                    </button>
                    <span>⌘ / Ctrl O</span>
                  </div>
                  {files.length > 0 ? (
                    <div className="file-list">
                      {files.map((f) => (
                        <div className="file-row" key={f.path}>
                          <span className="file-icon">
                            <Music2 size={19} />
                          </span>
                          <div>
                            <strong title={f.name}>{f.name}</strong>
                            <small>
                              {time(f.duration)} ·{" "}
                              {(f.sample_rate / 1000).toFixed(1)} kHz ·{" "}
                              {f.channels} ch · {f.codec} · {bytes(f.size)}
                            </small>
                          </div>
                          <button
                            aria-label={`Remove ${f.name}`}
                            onClick={() =>
                              setFiles((previous) =>
                                previous.filter((p) => p.path !== f.path),
                              )
                            }
                          >
                            <X size={16} />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="recent-files">
                      <h3>Recent recordings</h3>
                      {jobs.length ? (
                        [
                          ...new Map(
                            [...jobs]
                              .reverse()
                              .map((j) => [j.source.path, j.source]),
                          ).values(),
                        ]
                          .slice(0, 4)
                          .map((f) => (
                            <button
                              key={f.path}
                              onClick={() => void addFiles([f.path])}
                            >
                              <Music2 size={15} />
                              <span>{f.name}</span>
                              <small>{time(f.duration)}</small>
                            </button>
                          ))
                      ) : (
                        <p>
                          Your recordings will appear here after your first
                          separation.
                        </p>
                      )}
                    </div>
                  )}
                </div>
                <section className="separation-options">
                  <div className="option-heading">
                    <Mic2 size={17} />
                    <h2>What would you like?</h2>
                  </div>
                  <label className="sr-only" htmlFor="target">
                    Separation target
                  </label>
                  <select
                    id="target"
                    data-testid="target"
                    value={target}
                    onChange={(e) => {
                      setTarget(e.target.value as Preset["task"]);
                      setCustom(null);
                    }}
                  >
                    <option value="Instrumental">Instrumental</option>
                    <option value="Vocals">Vocals</option>
                    <option value="Both">Vocals + Instrumental</option>
                    <option value="4 Stems">4 stems</option>
                    <option value="Drums">Drums</option>
                    <option value="Bass">Bass</option>
                    <option value="Other">Other</option>
                  </select>
                  <p className="option-description">
                    {target === "Instrumental"
                      ? "Let the instruments take the lead."
                      : target === "Vocals"
                        ? "Bring the voice into focus."
                        : "Discover the layers inside your recording."}
                  </p>
                  <h3>Separation quality</h3>
                  <div className="quality-options">
                    {(["Fast", "Balanced", "Ultra"] as const).map((q) => (
                      <button
                        key={q}
                        className={quality === q && !custom ? "selected" : ""}
                        aria-pressed={quality === q && !custom}
                        onClick={() => {
                          setQuality(q);
                          setCustom(null);
                        }}
                      >
                        <span>
                          {q}
                          {q === "Ultra" && <Sparkles size={13} />}
                        </span>
                        <small>
                          {q === "Fast"
                            ? "Quick preview"
                            : q === "Balanced"
                              ? "One premium model"
                              : "Premium ensemble"}
                        </small>
                        {quality === q && !custom && <Check size={14} />}
                      </button>
                    ))}
                  </div>
                  <div className="preset-summary">
                    <span>
                      {custom ? "Custom selection" : chosenPreset?.name}
                    </span>
                    <small>
                      {chosenPreset?.models.length} model
                      {chosenPreset?.models.length === 1 ? "" : "s"} ·{" "}
                      {chosenPreset?.output.format} export
                    </small>
                    <details>
                      <summary>See the models</summary>
                      {chosenPreset?.models.map((m) => (
                        <code key={m}>{m}</code>
                      ))}
                      <small>
                        {chosenPreset?.algorithm} · model-recommended context
                      </small>
                    </details>
                  </div>
                  <button
                    className="primary separate-button"
                    data-testid="separate"
                    disabled={!files.length || !chosenPreset || busy !== null}
                    onClick={() => void start()}
                  >
                    <AudioLines size={18} />
                    {files.length > 1
                      ? `Separate ${files.length} recordings`
                      : "Separate audio"}
                    <ArrowRight size={16} />
                  </button>
                  <small className="local-note">
                    <ShieldCheck size={12} />
                    Private. Local. Yours.
                  </small>
                </section>
              </div>
              {advanced && chosenPreset && (
                <section className="studio-panel">
                  <div className="section-title">
                    <div>
                      <h2>Studio controls</h2>
                      <p>
                        Exact models, inference settings and export choices.
                      </p>
                    </div>
                    <button
                      onClick={() =>
                        setEditor({
                          ...structuredClone(chosenPreset),
                          id: `user_${crypto.randomUUID().replaceAll("-", "")}`,
                          name: `${chosenPreset.name} copy`,
                          builtin: false,
                          quality: "Custom",
                        })
                      }
                    >
                      Build an ensemble
                    </button>
                  </div>
                  <label>
                    Use preset
                    <select
                      value={custom?.id ?? chosenPreset.id}
                      onChange={(e) =>
                        setCustom(
                          structuredClone(
                            presets.find((p) => p.id === e.target.value)!,
                          ),
                        )
                      }
                    >
                      {presets.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <InferenceControls
                    value={chosenPreset.parameters}
                    onChange={(parameters) =>
                      setCustom({ ...chosenPreset, parameters })
                    }
                    models={models.filter((m) =>
                      chosenPreset.models.includes(m.id),
                    )}
                    capabilities={capabilities}
                  />
                  <details>
                    <summary>Output configuration</summary>
                    <OutputControls
                      value={chosenPreset.output}
                      onChange={(output) =>
                        setCustom({ ...chosenPreset, output })
                      }
                      onError={onError}
                    />
                  </details>
                  <button
                    className="text-button"
                    onClick={() => {
                      setCustom(null);
                    }}
                  >
                    Reset to recommended
                  </button>
                </section>
              )}
            </>
          ) : screen === "Queue" || screen === "Library" ? (
            <>
              <div className="page-heading">
                <div>
                  <h1>
                    {screen === "Queue"
                      ? "Your processing queue"
                      : "Made from your music"}
                  </h1>
                  <p>
                    {screen === "Queue"
                      ? "GPU jobs run one at a time. The next recording starts when the current one is ready."
                      : "Your separations, models and exported stems, together."}
                  </p>
                </div>
                <div className="actions">
                  {screen === "Queue" && (
                    <>
                      <button
                        onClick={() => void queueAction("process_queue")}
                        disabled={
                          running || !jobs.some((j) => j.status === "Pending")
                        }
                      >
                        Process all
                      </button>
                      <button
                        onClick={() =>
                          void perform("next", async () => {
                            await api("process_queue", { single: true });
                            setRunning(true);
                          })
                        }
                        disabled={
                          running || !jobs.some((j) => j.status === "Pending")
                        }
                      >
                        Process next
                      </button>
                      <button
                        onClick={() =>
                          void perform("pause", async () => {
                            await api("pause_queue");
                            setRunning(false);
                          })
                        }
                        disabled={!running}
                      >
                        Pause after current
                      </button>
                    </>
                  )}
                  <button
                    onClick={() => void queueAction("clear_completed")}
                    disabled={!completed.length}
                  >
                    Clear completed
                  </button>
                </div>
              </div>
              {(screen === "Library" ? completed : jobs).length ? (
                <div className="job-list">
                  {(screen === "Library" ? [...completed].reverse() : jobs)
                    .slice(0, listLimit)
                    .map((job) => (
                      <div
                        key={job.id}
                        className={`job-row ${activeJob(job) ? "processing" : ""}`}
                      >
                        <span className="file-icon">
                          {job.status === "Completed" ? (
                            <CheckCircle2 size={19} />
                          ) : (
                            <Music2 size={19} />
                          )}
                        </span>
                        <div className="job-info">
                          <strong title={job.source.name}>
                            {job.source.name}
                          </strong>
                          <small>
                            {job.request.preset.name} ·{" "}
                            {time(job.source.duration)} ·{" "}
                            {new Date(
                              job.created_at * 1000,
                            ).toLocaleDateString()}
                          </small>
                          {activeJob(job) && (
                            <div className="job-progress">
                              <Spinner
                                label={`${job.status}${job.model ? ` · ${job.model}` : ""}`}
                              />
                              {job.download &&
                                typeof job.download.bytes === "number" && (
                                  <>
                                    <progress
                                      value={job.download.bytes}
                                      max={
                                        typeof job.download.total === "number"
                                          ? job.download.total
                                          : undefined
                                      }
                                    />
                                    <small>
                                      {bytes(job.download.bytes)}{" "}
                                      {typeof job.download.total === "number"
                                        ? `of ${bytes(job.download.total)}`
                                        : "downloaded"}
                                    </small>
                                  </>
                                )}
                            </div>
                          )}
                          {job.error && (
                            <p className="error-inline">{job.error}</p>
                          )}
                        </div>
                        <span
                          className={`badge ${job.status === "Completed" ? "success" : job.status === "Failed" ? "danger" : ""}`}
                        >
                          {job.status}
                        </span>
                        <div className="actions">
                          {job.status === "Completed" && (
                            <button
                              onClick={() => {
                                setSelectedJob(job.id);
                              }}
                            >
                              Listen
                              <ArrowRight size={14} />
                            </button>
                          )}
                          {["Failed", "Interrupted", "Cancelled"].includes(
                            job.status,
                          ) && (
                            <button
                              onClick={() =>
                                void queueAction("retry_job", job.id)
                              }
                            >
                              Retry
                            </button>
                          )}
                          {(activeJob(job) || job.status === "Pending") && (
                            <button
                              aria-label={`Cancel ${job.source.name}`}
                              onClick={() =>
                                void queueAction("cancel_job", job.id)
                              }
                            >
                              <X size={16} />
                            </button>
                          )}
                          {job.status === "Pending" && (
                            <>
                              <button
                                aria-label={`Move ${job.source.name} up`}
                                onClick={() =>
                                  void perform("reorder", async () => {
                                    const ids = jobs.map((j) => j.id),
                                      index = ids.indexOf(job.id);
                                    if (index > 0)
                                      [ids[index - 1], ids[index]] = [
                                        ids[index],
                                        ids[index - 1],
                                      ];
                                    await api("reorder_queue", { ids });
                                    await refreshJobs();
                                  })
                                }
                              >
                                <ArrowUp size={14} />
                              </button>
                              <button
                                aria-label={`Move ${job.source.name} down`}
                                onClick={() =>
                                  void perform("reorder", async () => {
                                    const ids = jobs.map((j) => j.id),
                                      index = ids.indexOf(job.id);
                                    if (index < ids.length - 1)
                                      [ids[index + 1], ids[index]] = [
                                        ids[index],
                                        ids[index + 1],
                                      ];
                                    await api("reorder_queue", { ids });
                                    await refreshJobs();
                                  })
                                }
                              >
                                <ArrowDown size={14} />
                              </button>
                            </>
                          )}
                          {!activeJob(job) && (
                            <button
                              aria-label={`Remove ${job.source.name} from history`}
                              onClick={() =>
                                void queueAction("remove_job", job.id)
                              }
                            >
                              <Trash2 size={15} />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  {(screen === "Library" ? completed : jobs).length >
                    listLimit && (
                    <button onClick={() => setListLimit(listLimit + 100)}>
                      Show 100 more
                    </button>
                  )}
                </div>
              ) : (
                <Empty
                  title={
                    screen === "Queue"
                      ? "Ready for your first recording"
                      : "Your music, collected here"
                  }
                  action={
                    <button
                      className="primary"
                      onClick={() => setScreen("Home")}
                    >
                      Import audio
                      <ArrowRight size={15} />
                    </button>
                  }
                >
                  {screen === "Queue"
                    ? "Add audio on Home to start separating. Completed outputs are kept when you clear the queue."
                    : "Completed separations will appear here. Listen again or open their output folders."}
                </Empty>
              )}
            </>
          ) : screen === "Models" ? (
            <>
              <div className="page-heading">
                <div>
                  <h1>A model for every layer.</h1>
                  <p>
                    Discover the current upstream catalogue. Choose a model or
                    combine several in a preset.
                  </p>
                </div>
                <div className="actions">
                  <button
                    onClick={() =>
                      void perform("verify", async () => {
                        const results =
                          await api<{ model: string; valid: boolean }[]>(
                            "verify_models",
                          );
                        notify(
                          results.length
                            ? `${results.filter((r) => r.valid).length}/${results.length} cached models passed integrity checks.`
                            : "No downloaded models to verify.",
                        );
                        await refreshModels();
                      })
                    }
                  >
                    Verify models
                  </button>
                  <button
                    onClick={() =>
                      void perform("refresh", () => refreshModels(true))
                    }
                  >
                    <RefreshCw size={15} />
                    Refresh
                  </button>
                </div>
              </div>
              <div className="filter-bar">
                <label className="search">
                  <Search size={16} />
                  <input
                    aria-label="Search models"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search name, filename or architecture…"
                  />
                </label>
                <select
                  aria-label="Model filter"
                  value={modelFilter}
                  onChange={(e) => setModelFilter(e.target.value)}
                >
                  {[
                    "All",
                    "Downloaded",
                    "Vocals",
                    "Instrumental",
                    "Drums",
                    "Bass",
                    "MelBand RoFormer",
                    "BS-RoFormer",
                    "MDX",
                    "VR",
                    "Demucs",
                  ].map((f) => (
                    <option key={f}>{f}</option>
                  ))}
                </select>
                <span>{filteredModels.length} models</span>
              </div>
              <div className="model-list">
                {filteredModels.slice(0, listLimit).map((model) => {
                  const dl = downloads[model.id];
                  const downloading =
                    dl &&
                    !["completed", "failed", "cancelled"].includes(dl.kind);
                  return (
                    <div key={model.id} className="model-row">
                      <div className="architecture-mark">
                        <AudioLines size={20} />
                      </div>
                      <div className="model-info">
                        <button
                          className="text-button model-name"
                          onClick={() => setModelDetail(model)}
                        >
                          {model.name}
                        </button>
                        <code>{model.id}</code>
                        <div className="model-tags">
                          <span>{model.architecture}</span>
                          <span>
                            {model.stems.join(" + ") ||
                              "Stem metadata unavailable"}
                          </span>
                          {model.vip && <span>UVR subscriber model</span>}
                        </div>
                        {downloading && (
                          <div className="download-status">
                            <progress
                              value={dl.bytes}
                              max={dl.total ?? undefined}
                            />
                            <small>
                              {bytes(dl.bytes ?? 0)}
                              {dl.total ? ` / ${bytes(dl.total)}` : ""}
                              {dl.speed ? ` · ${bytes(dl.speed)}/s` : ""}
                              {dl.eta != null
                                ? ` · ${Math.ceil(dl.eta)}s remaining`
                                : ""}
                            </small>
                          </div>
                        )}
                        {dl?.kind === "failed" && (
                          <p className="error-inline">{dl.error}</p>
                        )}
                      </div>
                      <div className="model-size">
                        {bytes(
                          model.downloaded ? model.disk_usage : model.size,
                        )}
                        <small>
                          {model.downloaded
                            ? "Downloaded"
                            : "Upstream download"}
                        </small>
                      </div>
                      <div className="actions">
                        {downloading ? (
                          <button
                            onClick={() =>
                              void perform("cancel_download", async () => {
                                await api("cancel_download", {
                                  model: model.id,
                                });
                                setDownloads((previous) => ({
                                  ...previous,
                                  [model.id]: { kind: "cancelled" },
                                }));
                              })
                            }
                          >
                            Cancel
                          </button>
                        ) : model.downloaded ? (
                          <>
                            <button
                              onClick={() => {
                                const base = chosenPreset ?? presets[0];
                                setCustom({
                                  ...structuredClone(base),
                                  models: [model.id],
                                  name: model.name,
                                  task: model.stems.includes("Instrumental")
                                    ? "Instrumental"
                                    : model.stems.includes("Vocals")
                                      ? "Vocals"
                                      : "All",
                                  quality: "Custom",
                                });
                                setScreen("Home");
                                setAdvanced(true);
                              }}
                            >
                              Use model
                            </button>
                            <button
                              aria-label={`Reveal ${model.name}`}
                              onClick={() =>
                                void reveal(model.path).catch(onError)
                              }
                            >
                              <FolderOpen size={15} />
                            </button>
                            <button
                              aria-label={`Delete ${model.name}`}
                              onClick={() =>
                                setConfirmation({
                                  title: "Delete cached model?",
                                  body: `Remove ${model.id} from the model cache? Your presets and audio outputs are kept. You can download it again later.`,
                                  action: "Delete model",
                                  run: async () => {
                                    await api("remove_model", {
                                      model: model.id,
                                    });
                                    await refreshModels();
                                  },
                                })
                              }
                            >
                              <Trash2 size={15} />
                            </button>
                          </>
                        ) : (
                          <button
                            disabled={!!active}
                            onClick={() =>
                              setConfirmation({
                                title: "Download model",
                                body: `${model.name} · ${bytes(model.size)}. ${model.license}. ${model.vip ? "Upstream identifies this as a subscriber model; ensure you have the author’s access." : "Downloaded directly from its upstream source."}`,
                                action:
                                  dl?.kind === "failed"
                                    ? "Retry download"
                                    : "Download",
                                run: async () => {
                                  setDownloads((previous) => ({
                                    ...previous,
                                    [model.id]: { kind: "starting" },
                                  }));
                                  await api("download_model", {
                                    model: model.id,
                                  });
                                },
                              })
                            }
                          >
                            <Download size={15} />
                            Download
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
              {filteredModels.length > listLimit && (
                <button onClick={() => setListLimit(listLimit + 100)}>
                  Show 100 more
                </button>
              )}
              {!filteredModels.length && (
                <Empty title="No matching models">
                  Try another search or refresh upstream metadata.
                </Empty>
              )}
            </>
          ) : screen === "Presets" ? (
            <>
              <div className="page-heading">
                <div>
                  <h1>Your sound, your settings.</h1>
                  <p>
                    Keep the combinations you love. User presets stay with you
                    across updates.
                  </p>
                </div>
                <div className="actions">
                  <button
                    onClick={() =>
                      void perform("import_preset", async () => {
                        const raw = await importPreset();
                        if (raw) {
                          const preset = validate<Preset>("Preset", raw);
                          preset.id = `user_${crypto.randomUUID().replaceAll("-", "")}`;
                          preset.builtin = false;
                          setPresets(await api("save_preset", { preset }));
                          notify("Preset imported.");
                        }
                      })
                    }
                  >
                    Import JSON
                  </button>
                  <button className="primary" onClick={newPreset}>
                    <Plus size={15} />
                    Create preset
                  </button>
                </div>
              </div>
              <div className="preset-list">
                {presets.map((preset) => (
                  <div key={preset.id} className="preset-row">
                    <span className="file-icon">
                      <Sparkles size={18} />
                    </span>
                    <div>
                      <strong>{preset.name}</strong>
                      <small>{preset.description}</small>
                      <span className="model-tags">
                        {preset.models.length} model
                        {preset.models.length > 1 ? "s" : ""} ·{" "}
                        {preset.algorithm} · {preset.task}
                      </span>
                    </div>
                    <span className="badge">
                      {preset.builtin ? "Built-in" : "Your preset"}
                    </span>
                    <div className="actions">
                      <button
                        onClick={() => {
                          setCustom(structuredClone(preset));
                          setTarget(preset.task);
                          setScreen("Home");
                        }}
                      >
                        Use
                      </button>
                      <button
                        onClick={() =>
                          setEditor({
                            ...structuredClone(preset),
                            ...(preset.builtin
                              ? {
                                  id: `user_${crypto.randomUUID().replaceAll("-", "")}`,
                                  name: `${preset.name} copy`,
                                  builtin: false,
                                }
                              : {}),
                          })
                        }
                      >
                        {preset.builtin ? "Duplicate" : "Edit"}
                      </button>
                      <button
                        aria-label={`Export ${preset.name}`}
                        onClick={() => void exportPreset(preset).catch(onError)}
                      >
                        <Download size={15} />
                      </button>
                      {!preset.builtin && (
                        <button
                          aria-label={`Delete preset ${preset.name}`}
                          onClick={() =>
                            setConfirmation({
                              title: "Delete preset?",
                              body: `Remove “${preset.name}”? Models and audio outputs are kept.`,
                              action: "Delete preset",
                              run: async () =>
                                setPresets(
                                  await api("delete_preset", { id: preset.id }),
                                ),
                            })
                          }
                        >
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : screen === "Compare" ? (
            <>
              <div className="page-heading">
                <div>
                  <h1>Trust your ears.</h1>
                  <p>
                    Compare the same recording across models. Listen blind, then
                    reveal your choice.
                  </p>
                </div>
                <button
                  onClick={() => {
                    setCompareGroup(null);
                    setBlind(true);
                  }}
                >
                  New comparison
                </button>
              </div>
              {compareResults.length ? (
                <AudioWorkspace
                  key={`${compareGroup}:${compareResults.map((j) => j.id).join(",")}`}
                  jobs={compareResults}
                  blind={blind}
                  onReveal={() => setBlind(false)}
                  onError={onError}
                />
              ) : (
                <div className="compare-setup">
                  <button
                    className="dropzone compact"
                    onClick={() => void openFiles().catch(onError)}
                  >
                    <AudioLines size={30} />
                    <strong>
                      {files[0]?.name ?? "Choose a recording to compare"}
                    </strong>
                    <span>
                      {files[0]
                        ? time(files[0].duration)
                        : "Use one audio file for every comparison pass"}
                    </span>
                  </button>
                  <div className="form-grid">
                    <label>
                      Range start (seconds)
                      <input
                        type="number"
                        min="0"
                        placeholder="Full recording"
                        value={rangeStart}
                        onChange={(e) => setRangeStart(e.target.value)}
                      />
                    </label>
                    <label>
                      Range end (seconds)
                      <input
                        type="number"
                        min="1"
                        placeholder="Full recording"
                        value={rangeEnd}
                        onChange={(e) => setRangeEnd(e.target.value)}
                      />
                    </label>
                  </div>
                  <h3>Choose 2–4 presets</h3>
                  <div className="compare-options">
                    {presets.map((p) => (
                      <label className="compare-choice" key={p.id}>
                        <input
                          type="checkbox"
                          checked={compareChoices.includes(p.id)}
                          disabled={
                            !compareChoices.includes(p.id) &&
                            compareChoices.length >= 4
                          }
                          onChange={(e) =>
                            setCompareChoices((previous) =>
                              e.target.checked
                                ? [...previous, p.id]
                                : previous.filter((id) => id !== p.id),
                            )
                          }
                        />
                        <span>
                          <strong>{p.name}</strong>
                          <small>
                            {p.models.length} models · {p.task}
                          </small>
                        </span>
                      </label>
                    ))}
                  </div>
                  <button
                    className="primary"
                    disabled={
                      !files.length ||
                      compareChoices.length < 2 ||
                      busy !== null
                    }
                    onClick={() =>
                      setConfirmation({
                        title: "Run comparison",
                        body: "Chosen presets run sequentially. Missing models download from upstream. Compare matching stems and use at least 20 seconds for representative model context.",
                        action: "Run comparison",
                        run: async () => {
                          const group = crypto.randomUUID();
                          setCompareGroup(group);
                          setBlind(true);
                          for (const id of compareChoices) {
                            const p = structuredClone(
                              presets.find((p) => p.id === id)!,
                            );
                            p.output = structuredClone(settings.output);
                            p.parameters = structuredClone(settings.parameters);
                            await enqueue(p, [files[0]], group);
                          }
                          setScreen("Compare");
                        },
                      })
                    }
                  >
                    <AudioLines size={17} />
                    Run comparison
                  </button>
                  {compareGroup && (
                    <p className="muted">
                      Comparison is processing. Open Queue for stage details;
                      completed results appear here.
                    </p>
                  )}
                </div>
              )}
            </>
          ) : screen === "Settings" ? (
            <>
              <div className="page-heading">
                <div>
                  <h1>Make yourself at home.</h1>
                  <p>
                    Processing, storage and the small details that make the
                    studio yours.
                  </p>
                </div>
                <button
                  onClick={() =>
                    void perform("rescan", async () =>
                      setCapabilities(
                        await api("get_capabilities", { refresh: true }),
                      ),
                    )
                  }
                >
                  <RefreshCw size={15} />
                  Rescan hardware
                </button>
              </div>
              <div className="actions settings-save">
                <button
                  className="primary"
                  disabled={!settingsChanged || busy === "settings"}
                  onClick={() =>
                    void perform("settings", async () => {
                      await saveSettings(editedSettings);
                      notify("Settings saved.");
                    })
                  }
                >
                  Apply settings
                </button>
                <button
                  disabled={!settingsChanged}
                  onClick={() => setDraftSettings(structuredClone(settings))}
                >
                  Discard changes
                </button>
                <span className="muted">
                  {settingsChanged
                    ? "Changes apply to new jobs after saving."
                    : "All changes saved."}
                </span>
              </div>
              <section className="settings-section">
                <h2>Processing & output</h2>
                <OutputControls
                  value={editedSettings.output}
                  onChange={(output) =>
                    showSettings({ ...editedSettings, output })
                  }
                  onError={onError}
                />
                <div className="form-grid">
                  <label>
                    Default quality
                    <select
                      value={editedSettings.default_quality}
                      onChange={(e) =>
                        showSettings({
                          ...editedSettings,
                          default_quality: e.target
                            .value as Settings["default_quality"],
                        })
                      }
                    >
                      {["Fast", "Balanced", "Ultra"].map((q) => (
                        <option key={q}>{q}</option>
                      ))}
                    </select>
                  </label>
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={editedSettings.auto_download}
                      onChange={(e) =>
                        showSettings({
                          ...editedSettings,
                          auto_download: e.target.checked,
                        })
                      }
                    />
                    Download required models automatically
                  </label>
                </div>
                <InferenceControls
                  value={editedSettings.parameters}
                  onChange={(parameters) =>
                    showSettings({ ...editedSettings, parameters })
                  }
                  models={models
                    .filter((m) =>
                      ["MDXC", "MDX", "VR", "Demucs"].includes(m.family),
                    )
                    .slice(0, 20)}
                  capabilities={capabilities}
                />
              </section>
              <section className="settings-section">
                <h2>Storage & runtime</h2>
                <label>
                  Model cache
                  <div className="input-action">
                    <input
                      value={editedSettings.model_directory}
                      placeholder="Application model cache"
                      readOnly
                    />
                    <button
                      onClick={() =>
                        void chooseFolder()
                          .then((path) => {
                            if (path)
                              showSettings({
                                ...editedSettings,
                                model_directory: path,
                              });
                          })
                          .catch(onError)
                      }
                    >
                      Choose…
                    </button>
                  </div>
                </label>
                <div className="form-grid">
                  <label>
                    Engine
                    <select
                      value={editedSettings.engine}
                      onChange={(e) =>
                        showSettings({
                          ...editedSettings,
                          engine: e.target.value as Settings["engine"],
                        })
                      }
                    >
                      <option value="native">Native Runtime</option>
                      <option
                        value="container"
                        disabled={!capabilities?.containers.length}
                      >
                        Container Runtime
                        {!capabilities?.containers.length
                          ? " · not detected"
                          : ""}
                      </option>
                    </select>
                  </label>
                  {editedSettings.engine === "container" && (
                    <>
                      <label>
                        Container runtime
                        <select
                          value={editedSettings.container_command}
                          onChange={(e) =>
                            showSettings({
                              ...editedSettings,
                              container_command: e.target
                                .value as Settings["container_command"],
                            })
                          }
                        >
                          {capabilities?.containers.map((c) => (
                            <option key={c}>{c}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Container image
                        <input
                          value={editedSettings.container_image}
                          onChange={(e) =>
                            showSettings({
                              ...editedSettings,
                              container_image: e.target.value,
                            })
                          }
                        />
                      </label>
                    </>
                  )}
                </div>
                <div className="actions">
                  <button
                    onClick={() =>
                      void perform("storage", async () =>
                        setStorage(await api("storage")),
                      )
                    }
                  >
                    Calculate storage use
                  </button>
                  <button
                    onClick={() =>
                      setConfirmation({
                        title: "Clear safe caches?",
                        body: "Remove cached waveforms, previews and temporary processing files. Models, presets, history and exported audio are kept.",
                        action: "Clear caches",
                        run: async () => {
                          await api("clear_cache");
                          setStorage(await api("storage"));
                          notify("Caches cleared.");
                        },
                      })
                    }
                  >
                    Clear safe caches
                  </button>
                </div>
                {storage && (
                  <div className="storage-rows">
                    {Object.entries(storage).map(([key, value]) => (
                      <div key={key}>
                        <span>{key.replaceAll("_", " ")}</span>
                        <strong>{bytes(value)}</strong>
                      </div>
                    ))}
                  </div>
                )}
              </section>
              <section className="settings-section">
                <h2>Appearance</h2>
                <div className="form-grid">
                  <label>
                    Theme
                    <select
                      value={editedSettings.theme}
                      onChange={(e) =>
                        showSettings({
                          ...editedSettings,
                          theme: e.target.value as Settings["theme"],
                        })
                      }
                    >
                      <option value="dark">Dark</option>
                      <option value="light">Light</option>
                      <option value="system">System</option>
                    </select>
                  </label>
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={editedSettings.reduced_motion}
                      onChange={(e) =>
                        showSettings({
                          ...editedSettings,
                          reduced_motion: e.target.checked,
                        })
                      }
                    />
                    Reduce motion
                  </label>
                </div>
              </section>
              <section className="settings-section">
                <h2>Diagnostics & About</h2>
                <p>
                  {BRAND.name} {BRAND.version} · Audio stays on this computer.
                  No telemetry.
                </p>
                <div className="actions">
                  <button
                    onClick={() =>
                      void perform("diagnostics", async () => {
                        await navigator.clipboard.writeText(
                          JSON.stringify(await api("diagnostics"), null, 2),
                        );
                        notify("Redacted diagnostics copied.");
                      })
                    }
                  >
                    Copy diagnostics
                  </button>
                  <button
                    onClick={() =>
                      void perform("selftest", async () =>
                        setSetupChecks(await api("self_test")),
                      )
                    }
                  >
                    Run self-test
                  </button>
                  <button onClick={() => setLicenses(true)}>
                    Open Source & Model Licenses
                  </button>
                  <button onClick={() => void initialize()}>
                    Restart engine connection
                  </button>
                </div>
                {setupChecks.length > 0 && (
                  <ul className="check-list">
                    {setupChecks.map((c) => (
                      <li key={c.name}>
                        {c.passed ? <Check size={15} /> : <X size={15} />}
                        <strong>{c.name}</strong>
                        <span>{c.detail}</span>
                      </li>
                    ))}
                  </ul>
                )}
                <details>
                  <summary>Hardware & engine details</summary>
                  <pre>{JSON.stringify(capabilities, null, 2)}</pre>
                </details>
              </section>
            </>
          ) : null}
        </div>
      </main>
      {toast && (
        <div
          className={`toast ${toast.error ? "error" : ""}`}
          role={toast.error ? "alert" : "status"}
        >
          <span>{toast.message}</span>
          <button
            aria-label="Dismiss notification"
            onClick={() => setToast(null)}
          >
            <X size={15} />
          </button>
        </div>
      )}
      {confirmation && (
        <Dialog
          title={confirmation.title}
          onClose={() => setConfirmation(null)}
        >
          <p>{confirmation.body}</p>
          <div className="dialog-actions">
            <button onClick={() => setConfirmation(null)}>Cancel</button>
            <button
              className="primary"
              disabled={busy !== null}
              onClick={() => {
                const run = confirmation.run;
                setConfirmation(null);
                void perform("confirmed", run);
              }}
            >
              {confirmation.action}
            </button>
          </div>
        </Dialog>
      )}
      {editor && (
        <Dialog
          title="Ensemble & preset builder"
          onClose={() => setEditor(null)}
        >
          <PresetEditor
            initial={editor}
            models={models}
            capabilities={capabilities}
            onError={onError}
            onSave={async (preset) => {
              setPresets(await api("save_preset", { preset }));
              setEditor(null);
              notify("Preset saved.");
            }}
          />
        </Dialog>
      )}
      {modelDetail && (
        <Dialog title={modelDetail.name} onClose={() => setModelDetail(null)}>
          <dl className="details-list">
            <dt>Filename</dt>
            <dd>
              <code>{modelDetail.id}</code>
            </dd>
            <dt>Architecture</dt>
            <dd>{modelDetail.architecture}</dd>
            <dt>Stems</dt>
            <dd>{modelDetail.stems.join(", ")}</dd>
            <dt>Benchmark</dt>
            <dd>{modelDetail.benchmark}</dd>
            <dt>License</dt>
            <dd>{modelDetail.license}</dd>
            <dt>SHA256</dt>
            <dd>
              <code>{modelDetail.sha256 ?? "Publisher hash unavailable"}</code>
            </dd>
            <dt>Local path</dt>
            <dd>
              <code>{modelDetail.path}</code>
            </dd>
          </dl>
          <button
            onClick={() => void openUrl(modelDetail.source).catch(onError)}
          >
            Open upstream source
            <ArrowRight size={14} />
          </button>
        </Dialog>
      )}
      {licenses && (
        <Dialog
          title="Open Source & Model Licenses"
          onClose={() => setLicenses(false)}
        >
          <p>
            Separator credits python-audio-separator (MIT), Ultimate Vocal
            Remover, model authors Unwa/pcunwa and Becruily, Demucs, PyTorch
            (BSD), Tauri (MIT/Apache-2.0), React (MIT), and FFmpeg
            (build-dependent LGPL/GPL).
          </p>
          <p>
            Each model weight has its own terms. The four Ultra checkpoint
            author repositories currently provide no explicit weight license. We
            download weights from upstream after your action and do not include
            them in installers. Check the author’s terms before redistribution
            or commercial use.
          </p>
          <button
            onClick={() =>
              void openUrl(
                "https://github.com/Elias02345/UltimateAudioTools-GUI/blob/dev/THIRD_PARTY_NOTICES.md",
              ).catch(onError)
            }
          >
            Read third-party notices
            <ArrowRight size={14} />
          </button>
        </Dialog>
      )}
      <span className="sr-only">
        <Clock3 />
      </span>
    </div>
  );
}
