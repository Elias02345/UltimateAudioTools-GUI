import { useEffect, useRef, useState, useCallback } from "react";
import {
  Play,
  Pause,
  SkipBack,
  Volume2,
  FolderOpen,
  Download,
  Repeat2,
} from "lucide-react";
import { api, mediaUrl, time, reveal, exportAudio } from "./api";
import type { Job } from "./api";

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
}: {
  path: string;
  position: number;
  duration: number;
  onSeek: (value: number) => void;
  color?: string;
  zoom?: number;
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
  }, [peaks, position, duration, color, zoom]);
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
      aria-label="Seek audio"
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
}: {
  jobs: Job[];
  blind?: boolean;
  onReveal?: () => void;
  onError: (e: unknown) => void;
  onAgain?: (job: Job) => void;
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
  const [gains, setGains] = useState<Record<string, number>>({});
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
  }, [ready]);
  const toggle = useCallback(async () => {
    const master = masterAudio(audio.current);
    if (!master) return;
    try {
      if (!master.paused) {
        for (const a of audio.current.values()) a.pause();
        setPlaying(false);
      } else {
        await Promise.all([...audio.current.values()].map((a) => a.play()));
        setPlaying(true);
      }
    } catch (e) {
      for (const a of audio.current.values()) a.pause();
      setPlaying(false);
      onError(e);
    }
  }, [onError]);
  useEffect(() => {
    const shortcut = (e: KeyboardEvent) => {
      if (
        e.code === "Space" &&
        !(
          e.target instanceof HTMLElement &&
          e.target.closest('input, textarea, select, button, [role="slider"]')
        )
      ) {
        e.preventDefault();
        void toggle();
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, [toggle]);
  const seek = (value: number) => {
    for (const a of audio.current.values())
      if (Number.isFinite(a.duration))
        a.currentTime = Math.min(value, a.duration);
    setPosition(value);
  };
  const current = tracks.find((t) => t.id === selected) ?? tracks[0];
  return (
    <section className="audio-workspace">
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
        </div>
        <div className="actions">
          {blind && <button onClick={onReveal}>Reveal models</button>}
          <button
            onClick={() =>
              void exportAudio(
                jobs.flatMap((j) => j.result?.outputs.map((o) => o.path) ?? []),
              ).catch(onError)
            }
          >
            <Download size={15} />
            Export
          </button>
          <button
            aria-label="Open output folder"
            onClick={() => {
              const path = job.result?.outputs[0]?.path;
              if (path) void reveal(path).catch(onError);
            }}
          >
            <FolderOpen size={17} />
          </button>
        </div>
      </div>
      {loadError && (
        <p className="error-inline" role="alert">
          {loadError}
        </p>
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
              <input
                aria-label={`${track.name} gain`}
                disabled={!ready || unavailable.has(track.id)}
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={gains[track.id] ?? 1}
                onChange={(e) =>
                  setGains((previous) => ({
                    ...previous,
                    [track.id]: Number(e.target.value),
                  }))
                }
              />
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
        <button aria-label="Return to start" onClick={() => seek(0)}>
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
          {time(position)} <span>/ {time(duration)}</span>
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
