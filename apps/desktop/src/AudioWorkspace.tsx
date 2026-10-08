import { useEffect, useRef, useState, useCallback } from "react";
import {
  Play,
  Pause,
  SkipBack,
  Volume2,
  FolderOpen,
  Download,
  Repeat2,
  ArrowLeft,
  RotateCcw,
  Scissors,
} from "lucide-react";
import { api, mediaUrl, time, preciseTime, reveal } from "./api";
import type { Job } from "./api";
import { ResultExport } from "./ResultExport";

type EditDraft = { start: number; end: number; gains: Record<string, number> };
function readDraft(job: Job): EditDraft {
  const end = job.result?.outputs[0]?.duration ?? job.source.duration;
  try {
    const value = JSON.parse(
      localStorage.getItem(`separator-edits-${job.id}`) ?? "null",
    );
    if (
      value &&
      Number.isFinite(value.start) &&
      Number.isFinite(value.end) &&
      value.start >= 0 &&
      value.start < value.end &&
      value.end <= end &&
      typeof value.gains === "object" &&
      value.gains !== null &&
      Object.values(value.gains).every(
        (g) => typeof g === "number" && Number.isFinite(g) && g >= 0 && g <= 1,
      )
    )
      return value;
  } catch {
    /* Ignore invalid local drafts; the audio files are unaffected. */
  }
  return { start: 0, end, gains: {} };
}

type Track = { id: string; name: string; path: string; color: string };
type Peaks = { peaks: number[]; duration: number };
function masterAudio(elements: Map<string, HTMLAudioElement>) {
  return elements.get("original") ?? elements.values().next().value;
}
function configureMedia(
  element: HTMLAudioElement,
  muted: boolean,
  volume: number,
  loop: boolean,
) {
  element.muted = muted;
  element.volume = volume;
  element.loop = loop;
}
export function Waveform({
  path,
  position,
  duration,
  onSeek,
  color = "var(--primary)",
  zoom = 1,
  range,
  label = "Seek audio",
}: {
  path: string;
  position: number;
  duration: number;
  onSeek: (value: number) => void;
  color?: string;
  zoom?: number;
  range?: [number, number];
  label?: string;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [peaks, setPeaks] = useState<Peaks | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let alive = true;
    api<Peaks>("waveform", { path })
      .then((p) => {
        if (alive) {
          setPeaks(p);
          setError(false);
        }
      })
      .catch(() => {
        if (alive) setError(true);
      });
    return () => {
      alive = false;
    };
  }, [path]);
  useEffect(() => {
    const element = canvas.current;
    if (!element || !peaks) return;
    const draw = () => {
      const context = element.getContext("2d");
      if (!context) return;
      const width = element.clientWidth,
        height = element.clientHeight,
        scale = window.devicePixelRatio || 1;
      element.width = width * scale;
      element.height = height * scale;
      context.scale(scale, scale);
      context.clearRect(0, 0, width, height);
      context.fillStyle = color.startsWith("var(")
        ? getComputedStyle(element).getPropertyValue(color.slice(4, -1))
        : color;
      const bars = Math.max(1, Math.floor(width / 4));
      const visibleCount = Math.max(1, Math.floor(peaks.peaks.length / zoom));
      const start = Math.max(
        0,
        Math.min(
          peaks.peaks.length - visibleCount,
          Math.floor(
            (position / Math.max(duration, 0.01)) * peaks.peaks.length -
              visibleCount / 2,
          ),
        ),
      );
      if (range) {
        const left = Math.max(
          0,
          (((range[0] / duration) * peaks.peaks.length - start) /
            visibleCount) *
            width,
        );
        const right = Math.min(
          width,
          (((range[1] / duration) * peaks.peaks.length - start) /
            visibleCount) *
            width,
        );
        context.globalAlpha = 0.12;
        if (right > left) context.fillRect(left, 0, right - left, height);
      }
      for (let i = 0; i < bars; i++) {
        const from = start + Math.floor((i * visibleCount) / bars),
          to = start + Math.floor(((i + 1) * visibleCount) / bars);
        let peak = 0;
        for (let j = from; j <= to && j < peaks.peaks.length; j++)
          peak = Math.max(peak, peaks.peaks[j] ?? 0);
        const h = Math.max(2, Math.min(1, peak) * (height - 12));
        context.globalAlpha = 0.7;
        context.fillRect(i * 4, (height - h) / 2, 2, h);
      }
      const x =
        (((position / Math.max(duration, 0.01)) * peaks.peaks.length - start) /
          visibleCount) *
        width;
      context.globalAlpha = 1;
      context.fillStyle = getComputedStyle(element).getPropertyValue("--text");
      context.fillRect(x, 2, 1, height - 4);
    };
    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(element);
    return () => observer.disconnect();
  }, [peaks, position, duration, color, zoom, range]);
  const seek = (fraction: number) => {
    if (!peaks) return;
    const count = peaks.peaks.length / zoom;
    const start = Math.max(
      0,
      Math.min(
        peaks.peaks.length - count,
        (position / Math.max(duration, 0.01)) * peaks.peaks.length - count / 2,
      ),
    );
    onSeek(
      Math.max(
        0,
        Math.min(
          duration,
          ((start + fraction * count) / peaks.peaks.length) * duration,
        ),
      ),
    );
  };
  return (
    <div
      className="waveform"
      role="slider"
      tabIndex={0}
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={duration}
      aria-valuenow={position}
      aria-valuetext={time(position)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault();
          onSeek(
            Math.max(
              0,
              Math.min(duration, position + (e.key === "ArrowRight" ? 5 : -5)),
            ),
          );
        }
      }}
      onClick={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        seek((e.clientX - rect.left) / rect.width);
      }}
    >
      <canvas ref={canvas} aria-hidden="true" />
      {!peaks && (
        <span className="waveform-message">
          {error
            ? "Waveform unavailable; use the seek control below."
            : "Reading waveform…"}
        </span>
      )}
    </div>
  );
}

export function AudioWorkspace(
  props: Parameters<typeof AudioWorkspacePlayer>[0],
) {
  const key = JSON.stringify(
    props.jobs.map((job) => [
      job.source.path,
      job.result?.outputs.map((output) => output.path),
      job.request.range_start,
      job.request.range_end,
    ]),
  );
  return <AudioWorkspacePlayer key={key} {...props} />;
}

function AudioWorkspacePlayer({
  jobs,
  blind = false,
  onReveal,
  onError,
  onAgain,
  onBack,
  backLabel,
}: {
  jobs: Job[];
  blind?: boolean;
  onReveal?: () => void;
  onError: (e: unknown) => void;
  onAgain?: (job: Job) => void;
  onBack?: () => void;
  backLabel?: string;
}) {
  const job = jobs[0];
  const tracks: Track[] = [
    {
      id: "original",
      name: "Original",
      path: job.source.path,
      color: "var(--muted)",
    },
    ...jobs.flatMap((j, i) =>
      (j.result?.outputs ?? []).map((o) => ({
        id: `${j.id}-${o.stem}`,
        path: o.path,
        name:
          jobs.length > 1
            ? `${blind ? String.fromCharCode(65 + i) : j.request.preset.name} · ${o.stem}`
            : o.stem,
        color: o.stem === "Vocals" ? "var(--secondary)" : "var(--primary)",
      })),
    ),
  ];
  const key =
    tracks.map((t) => t.path).join("|") +
    `:${job.request.range_start}:${job.request.range_end}`;
  const audio = useRef(new Map<string, HTMLAudioElement>());
  const [selected, setSelected] = useState<string>("original");
  const [previewPaths, setPreviewPaths] = useState<Record<string, string>>({});
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(
    job.result?.outputs[0]?.duration ?? job.source.duration,
  );
  const [ready, setReady] = useState(false);
  const [volume, setVolume] = useState(0.85);
  const [zoom, setZoom] = useState(1);
  const [loop, setLoop] = useState(false);
  const [muted, setMuted] = useState<Set<string>>(new Set());
  const [draft, setDraft] = useState(() =>
    jobs.length === 1
      ? readDraft(job)
      : ({
          start: 0,
          end: job.result?.outputs[0]?.duration ?? job.source.duration,
          gains: {},
        } as EditDraft),
  );
  const gains = draft.gains;
  const [editing, setEditing] = useState(false);
  const [exportSelection, setExportSelection] = useState<string | null>(null);
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [rangeText, setRangeText] = useState(() => ({
    start: String(draft.start),
    end: String(draft.end),
  }));
  const single = jobs.length === 1;
  const edited =
    single &&
    (draft.start > 0 ||
      draft.end <
        (job.result?.outputs[0]?.duration ?? job.source.duration) - 0.001 ||
      tracks.some(
        (track) => track.id !== "original" && (gains[track.id] ?? 1) !== 1,
      ));
  const validRange =
    draft.start >= 0 && draft.end <= duration + 0.05 && draft.end > draft.start;
  useEffect(() => {
    if (single && validRange)
      localStorage.setItem(`separator-edits-${job.id}`, JSON.stringify(draft));
  }, [draft, job.id, single, validRange]);
  const [mix, setMix] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState<Set<string>>(new Set());
  useEffect(() => {
    let alive = true;
    const created = new Map<string, HTMLAudioElement>();
    const failed = new Set<string>();
    const paths: Record<string, string> = {};
    Promise.allSettled(
      tracks.map(async (track) => {
        const path = await api<string>("preview", {
          path: track.path,
          ...(track.id === "original"
            ? {
                range_start: job.request.range_start,
                range_end: job.request.range_end,
              }
            : {}),
        });
        if (!alive) return;
        const url = await mediaUrl(path);
        if (!alive) return;
        const element = new Audio(url);
        element.preload = "metadata";
        element.muted = true;
        element.addEventListener("error", () => {
          if (!alive) return;
          element.pause();
          failed.add(track.id);
          created.delete(track.id);
          audio.current.delete(track.id);
          setUnavailable((previous) => new Set([...previous, track.id]));
          setSelected((current) =>
            current === track.id
              ? (created.keys().next().value ?? "original")
              : current,
          );
          setReady(created.size > 0);
          if (!created.size) setPlaying(false);
          setLoadError(
            `Audio for ${track.name} could not load. Available tracks can still be played; check the missing file or run the readiness tests in Setup.`,
          );
        });
        element.addEventListener("loadedmetadata", () => {
          if (alive && masterAudio(audio.current) === element)
            setDuration(element.duration);
        });
        element.addEventListener("ended", () => {
          if (alive && masterAudio(audio.current) === element)
            setPlaying(false);
        });
        created.set(track.id, element);
        paths[track.id] = path;
      }),
    )
      .then((results) => {
        if (alive) {
          audio.current = created;
          setPreviewPaths(paths);
          const missing = tracks.filter(
            (track, index) =>
              results[index].status === "rejected" || failed.has(track.id),
          );
          setUnavailable(new Set(missing.map((track) => track.id)));
          setReady(created.size > 0);
          const first = tracks.find((track) => created.has(track.id));
          setSelected((current) =>
            created.has(current) ? current : (first?.id ?? "original"),
          );
          const master = masterAudio(created);
          if (master && Number.isFinite(master.duration))
            setDuration(master.duration);
          if (missing.length)
            setLoadError(
              created.size
                ? `${missing.map((track) => track.name).join(", ")} unavailable. Files may have moved or been removed. Available tracks can still be played.`
                : "Audio files are unavailable. Restore them at their original locations and reopen this result.",
            );
        }
      })
      .catch((e) => {
        if (alive) setLoadError(String(e));
      });
    return () => {
      alive = false;
      for (const a of created.values()) {
        a.pause();
        a.removeAttribute("src");
        a.load();
      }
      audio.current = new Map();
    };
    // The path key completely defines the media resources for this workspace.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => {
    for (const [id, element] of audio.current) {
      const audible = mix
        ? id !== "original" && !muted.has(id)
        : id === selected && !muted.has(id);
      configureMedia(
        element,
        !audible,
        Math.min(1, Math.max(0, volume * (gains[id] ?? 1))),
        loop,
      );
    }
  }, [selected, mix, muted, gains, volume, ready, loop]);
  useEffect(() => {
    if (!ready) return;
    let frame = 0;
    const tick = () => {
      const master = masterAudio(audio.current);
      if (master) {
        if (
          single &&
          validRange &&
          !master.paused &&
          (master.currentTime >= draft.end || master.currentTime < draft.start)
        ) {
          const finished = master.currentTime >= draft.end;
          for (const a of audio.current.values()) {
            a.currentTime = draft.start;
            if (!loop && finished) a.pause();
          }
          if (!loop && finished) setPlaying(false);
        }
        setPosition(master.currentTime);
        if (!master.paused && !master.seeking) {
          for (const [id, a] of audio.current) {
            if (
              id !== "original" &&
              !a.seeking &&
              Math.abs(a.currentTime - master.currentTime) > 0.06
            )
              a.currentTime = master.currentTime;
          }
        }
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [ready, single, validRange, draft.start, draft.end, loop]);
  const toggle = useCallback(async () => {
    const master = masterAudio(audio.current);
    if (!master) return;
    try {
      if (!master.paused) {
        for (const a of audio.current.values()) a.pause();
        setPlaying(false);
      } else {
        if (
          single &&
          validRange &&
          (master.currentTime < draft.start ||
            master.currentTime >= draft.end - 0.01)
        ) {
          for (const a of audio.current.values()) a.currentTime = draft.start;
        }
        await Promise.all([...audio.current.values()].map((a) => a.play()));
        setPlaying(true);
      }
    } catch (e) {
      for (const a of audio.current.values()) a.pause();
      setPlaying(false);
      onError(e);
    }
  }, [onError, single, validRange, draft.start, draft.end]);
  useEffect(() => {
    const shortcut = (e: KeyboardEvent) => {
      if (
        e.code === "Space" &&
        exportSelection === null &&
        !(
          e.target instanceof HTMLElement &&
          e.target.closest(
            'input, textarea, select, button, audio, [role="slider"], [role="dialog"]',
          )
        )
      ) {
        e.preventDefault();
        void toggle();
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, [toggle, exportSelection]);
  const seek = (value: number) => {
    for (const a of audio.current.values())
      if (Number.isFinite(a.duration))
        a.currentTime = Math.min(value, a.duration);
    setPosition(value);
  };
  const current = tracks.find((t) => t.id === selected) ?? tracks[0];
  const updateRange = (start: number, end: number) => {
    if (
      !Number.isFinite(start) ||
      !Number.isFinite(end) ||
      start < 0 ||
      end > duration + 0.05 ||
      start >= end
    ) {
      setRangeError("Choose a start before the end, within the recording.");
      return;
    }
    setRangeError(null);
    setDraft((previous) => ({ ...previous, start, end }));
    seek(start);
  };
  const changeRange = (next: typeof rangeText) => {
    setRangeText(next);
    if (!next.start.trim() || !next.end.trim()) {
      setRangeError("Enter both start and end times.");
      return;
    }
    updateRange(Number(next.start), Number(next.end));
  };
  return (
    <section className="audio-workspace">
      {onBack && (
        <button className="text-button result-back" onClick={onBack}>
          <ArrowLeft size={15} />
          {backLabel ?? "Back to Library"}
        </button>
      )}
      <div className="section-title">
        <div>
          <span className="badge success">
            {jobs.length > 1 ? "Comparison" : "Separation complete"}
          </span>
          <h2 title={job.source.name}>{job.source.name}</h2>
          <p>
            {blind
              ? "Listen first. Reveal the models when you are ready."
              : `${job.request.preset.name} · ${job.result?.device} · Lossless processing`}
          </p>
          {!blind && (
            <p className="result-summary">
              {job.result?.outputs.map((o) => o.stem).join(" + ")} ·{" "}
              {time(duration)} ·{" "}
              {(
                (job.result?.outputs[0]?.sample_rate ??
                  job.source.sample_rate) / 1000
              ).toFixed(1)}{" "}
              kHz
            </p>
          )}
        </div>
        <div className="actions">
          {blind && <button onClick={onReveal}>Reveal models</button>}
          <button
            className="primary"
            disabled={Boolean(rangeError)}
            onClick={() => setExportSelection("")}
          >
            <Download size={15} />
            Export stems
          </button>
          <button
            aria-label="Open output folder"
            onClick={() => {
              const path = job.result?.outputs[0]?.path;
              if (path) void reveal(path).catch(onError);
            }}
          >
            <FolderOpen size={17} />
            Folder
          </button>
        </div>
      </div>
      {loadError && (
        <p className="error-inline" role="alert">
          {loadError}
        </p>
      )}
      {single && (
        <>
          <div
            className="result-mode"
            role="group"
            aria-label="Result workspace mode"
          >
            <button
              aria-pressed={!editing}
              className={!editing ? "active" : ""}
              onClick={() => setEditing(false)}
            >
              Listen
            </button>
            <button
              aria-pressed={editing}
              className={editing ? "active" : ""}
              onClick={() => setEditing(true)}
            >
              <Scissors size={15} />
              Edit audio
            </button>
            <span>
              {edited
                ? "Edits saved locally · export to create files"
                : "Your created stems are preserved"}
            </span>
          </div>
          {editing && (
            <div className="result-editor">
              <div className="edit-heading">
                <strong>Keep a section</strong>
                <button
                  className="text-button"
                  onClick={() => {
                    setDraft({ start: 0, end: duration, gains: {} });
                    setRangeText({ start: "0", end: String(duration) });
                    setRangeError(null);
                    setMuted(new Set());
                    seek(0);
                  }}
                >
                  <RotateCcw size={14} />
                  Reset edits
                </button>
              </div>
              <div className="trim-controls">
                <label>
                  Start (seconds)
                  <input
                    aria-label="Trim start"
                    type="number"
                    min={0}
                    max={draft.end}
                    step="0.1"
                    value={rangeText.start}
                    onChange={(e) => {
                      const start = e.target.value;
                      changeRange({ ...rangeText, start });
                    }}
                  />
                </label>
                <button
                  disabled={!ready || position >= draft.end}
                  onClick={() => {
                    changeRange({
                      ...rangeText,
                      start: position.toFixed(3),
                    });
                  }}
                >
                  Set start here
                </button>
                <label>
                  End (seconds)
                  <input
                    aria-label="Trim end"
                    type="number"
                    min={draft.start}
                    max={duration}
                    step="0.1"
                    value={rangeText.end}
                    onChange={(e) => {
                      const end = e.target.value;
                      changeRange({ ...rangeText, end });
                    }}
                  />
                </label>
                <button
                  disabled={!ready || position <= draft.start}
                  onClick={() => {
                    changeRange({
                      ...rangeText,
                      end: position.toFixed(3),
                    });
                  }}
                >
                  Set end here
                </button>
              </div>
              <p>
                {preciseTime(draft.end - draft.start)} selected · Set stem
                levels below. Mute, solo and master volume are for listening
                only.
              </p>
              {rangeError && (
                <p role="alert" className="error-inline">
                  {rangeError}
                </p>
              )}
            </div>
          )}
        </>
      )}
      <div className="track-list">
        {tracks.map((track) => (
          <div
            className={`track ${selected === track.id && !mix ? "selected" : ""}`}
            key={track.id}
          >
            <button
              className="track-select"
              disabled={!ready || unavailable.has(track.id)}
              onClick={() => {
                setSelected(track.id);
                setMix(false);
              }}
              aria-pressed={selected === track.id && !mix}
            >
              <span className="track-dot" style={{ background: track.color }} />
              <span>{track.name}</span>
              <small>
                {unavailable.has(track.id) ? "Unavailable" : time(duration)}
              </small>
            </button>
            {unavailable.has(track.id) ? (
              <span className="muted">File moved or removed</span>
            ) : (
              <Waveform
                path={previewPaths[track.id] ?? track.path}
                position={position}
                duration={duration}
                onSeek={seek}
                color={track.color}
                zoom={zoom}
                label={`Seek ${track.name}`}
                range={single && edited ? [draft.start, draft.end] : undefined}
              />
            )}
            <div className="track-tools">
              <button
                aria-label={`Mute ${track.name}`}
                disabled={!ready || unavailable.has(track.id)}
                className={muted.has(track.id) ? "active" : ""}
                onClick={() =>
                  setMuted((previous) => {
                    const next = new Set(previous);
                    if (next.has(track.id)) next.delete(track.id);
                    else next.add(track.id);
                    return next;
                  })
                }
              >
                M
              </button>
              <button
                aria-label={`Solo ${track.name}`}
                disabled={!ready || unavailable.has(track.id)}
                aria-pressed={selected === track.id && !mix}
                onClick={() => {
                  setSelected(track.id);
                  setMix(false);
                }}
              >
                S
              </button>
              {(!single || (editing && track.id !== "original")) && (
                <label className="stem-level">
                  <span>{Math.round((gains[track.id] ?? 1) * 100)}%</span>
                  <input
                    aria-label={`${track.name} gain`}
                    disabled={!ready || unavailable.has(track.id)}
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={gains[track.id] ?? 1}
                    onChange={(e) =>
                      setDraft((previous) => ({
                        ...previous,
                        gains: {
                          ...previous.gains,
                          [track.id]: Number(e.target.value),
                        },
                      }))
                    }
                  />
                </label>
              )}
              {track.id !== "original" && (
                <button
                  disabled={Boolean(rangeError)}
                  title={`Export ${track.name}`}
                  aria-label={`Export ${track.name}`}
                  onClick={() => setExportSelection(track.path)}
                >
                  <Download size={14} />
                </button>
              )}
              <button
                aria-label={`Reveal ${track.name}`}
                onClick={() => void reveal(track.path).catch(onError)}
              >
                <FolderOpen size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
      <div className="transport">
        <button
          aria-label="Return to start"
          onClick={() => seek(single ? draft.start : 0)}
        >
          <SkipBack size={17} />
        </button>
        <button
          className="play-button"
          data-testid="play-result"
          disabled={!ready}
          aria-label={playing ? "Pause" : "Play"}
          onClick={() => void toggle()}
        >
          {playing ? (
            <Pause size={21} />
          ) : (
            <Play size={21} fill="currentColor" />
          )}
        </button>
        <span className="time-code">
          {editing ? preciseTime(position) : time(position)}{" "}
          <span>/ {time(duration)}</span>
        </span>
        <input
          className="seek"
          aria-label="Playback position"
          type="range"
          min="0"
          max={duration}
          step="0.1"
          value={position}
          onChange={(e) => seek(Number(e.target.value))}
        />
        <button
          aria-label="Loop recording"
          aria-pressed={loop}
          className={loop ? "active" : ""}
          onClick={() => setLoop(!loop)}
        >
          <Repeat2 size={17} />
        </button>
        <Volume2 size={17} />
        <input
          aria-label="Volume"
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={volume}
          onChange={(e) => setVolume(Number(e.target.value))}
        />
      </div>
      {exportSelection !== null && (
        <ResultExport
          jobs={jobs}
          selectedPath={exportSelection || undefined}
          edits={
            edited
              ? {
                  start: draft.start,
                  end: draft.end,
                  gains: Object.fromEntries(
                    tracks
                      .filter((t) => t.id !== "original")
                      .map((t) => [t.path, gains[t.id] ?? 1]),
                  ),
                }
              : undefined
          }
          onClose={() => setExportSelection(null)}
          onPreviewPlay={() => {
            for (const element of audio.current.values()) element.pause();
            setPlaying(false);
          }}
        />
      )}
      <div className="player-foot">
        <span>
          {ready
            ? `Listening to ${mix ? "stem mix" : current.name}`
            : "Preparing local audio previews…"}
        </span>
        <div className="actions">
          <button
            className="text-button"
            aria-pressed={mix}
            onClick={() => setMix(!mix)}
          >
            Mix stems
          </button>
          <label>
            Waveform zoom{" "}
            <select
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
            >
              <option value={1}>1×</option>
              <option value={2}>2×</option>
              <option value={4}>4×</option>
            </select>
          </label>
          {onAgain && (
            <button className="text-button" onClick={() => onAgain(job)}>
              Run again
            </button>
          )}
        </div>
      </div>
      {!blind && (
        <details className="technical-details">
          <summary>Processing details</summary>
          <pre>
            {JSON.stringify(
              {
                models: job.result?.models,
                engine: `${job.result?.engine} ${job.result?.engine_version}`,
                elapsed: job.result?.elapsed,
                parameters: job.request.preset.parameters,
                peak_vram: job.result?.peak_vram,
              },
              null,
              2,
            )}
          </pre>
        </details>
      )}
    </section>
  );
}
