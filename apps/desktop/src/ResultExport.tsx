import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Download, FolderOpen, Play } from "lucide-react";
import {
  api,
  bytes,
  chooseFolder,
  reveal,
  time,
  preciseTime,
  mediaUrl,
} from "./api";
import type { Job } from "./api";
import { Dialog, Spinner } from "./components";

export type ResultEdits = {
  start: number;
  end: number;
  gains: Record<string, number>;
};

export function ResultExport({
  jobs,
  edits,
  selectedPath,
  onClose,
}: {
  jobs: Job[];
  edits?: ResultEdits;
  selectedPath?: string;
  onClose: () => void;
}) {
  const outputs = jobs.flatMap((job) =>
    (job.result?.outputs ?? []).map((output) => ({
      ...output,
      preset: job.request.preset.name,
    })),
  );
  const [selected, setSelected] = useState(
    () => new Set(selectedPath ? [selectedPath] : outputs.map((o) => o.path)),
  );
  const [directory, setDirectory] = useState(
    () => localStorage.getItem("separator-export-folder") ?? "",
  );
  const [format, setFormat] = useState(edits ? "FLAC" : "Original");
  const [name, setName] = useState("");
  const [bitrate, setBitrate] = useState(320);
  const [applyEdits, setApplyEdits] = useState(Boolean(edits));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{
    paths: string[];
    directory: string;
  } | null>(null);
  const chosen = outputs.filter((o) => selected.has(o.path));
  const [preview, setPreview] = useState<{ name: string; url: string } | null>(
    null,
  );
  const [preparing, setPreparing] = useState(false);
  const previewRequest = useRef(0);
  useEffect(
    () => () => {
      previewRequest.current++;
    },
    [],
  );
  const previewFile = async (path: string) => {
    const request = ++previewRequest.current;
    setPreparing(true);
    setPreview(null);
    setError(null);
    try {
      const local = await api<string>("preview", { path });
      const url = await mediaUrl(local);
      if (request === previewRequest.current)
        setPreview({
          name: path.split(/[/\\]/).pop() ?? "Exported audio",
          url,
        });
    } catch (e) {
      if (request === previewRequest.current) setError(String(e));
    } finally {
      if (request === previewRequest.current) setPreparing(false);
    }
  };
  const exportSelected = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api<{ paths: string[]; directory: string }>(
        "export_results",
        {
          job_ids: jobs.map((j) => j.id),
          paths: chosen.map((o) => o.path),
          directory,
          name,
          format,
          bitrate,
          ...(applyEdits && edits
            ? { start: edits.start, end: edits.end, gains: edits.gains }
            : {}),
        },
      );
      localStorage.setItem("separator-export-folder", result.directory);
      setDone(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  const showFile = (path: string) =>
    void reveal(path).catch((e) => setError(String(e)));
  return (
    <Dialog
      title={done ? "Export complete" : "Export stems"}
      onClose={() => {
        if (!busy) onClose();
      }}
      busy={busy}
    >
      <div className="result-export">
        {done ? (
          <>
            <p className="export-success" role="status">
              <CheckCircle2 size={20} /> {done.paths.length}{" "}
              {done.paths.length === 1 ? "file" : "files"} saved
            </p>
            <p className="export-destination">{done.directory}</p>
            <ul className="exported-files">
              {done.paths.map((path) => (
                <li key={path}>
                  <button
                    className="text-button"
                    aria-label={`Preview ${path.split(/[/\\]/).pop()}`}
                    onClick={() => void previewFile(path)}
                  >
                    <Play size={14} />
                    {path.split(/[/\\]/).pop()}
                  </button>
                </li>
              ))}
            </ul>
            {preparing && <Spinner label="Preparing exported audio…" />}
            {preview && (
              <div className="export-preview">
                <span>{preview.name}</span>
                <audio
                  key={preview.url}
                  controls
                  preload="metadata"
                  src={preview.url}
                  aria-label={`Preview ${preview.name}`}
                />
              </div>
            )}
          </>
        ) : (
          <>
            <p>
              Choose the stems to save. Existing files receive a new filename.
            </p>
            <fieldset className="export-stems">
              <legend>
                Stems · {chosen.length} of {outputs.length} selected
              </legend>
              {outputs.map((output) => (
                <label key={output.path} className="export-stem">
                  <input
                    type="checkbox"
                    disabled={busy}
                    checked={selected.has(output.path)}
                    onChange={() =>
                      setSelected((previous) => {
                        const next = new Set(previous);
                        if (next.has(output.path)) next.delete(output.path);
                        else next.add(output.path);
                        return next;
                      })
                    }
                  />
                  <span>
                    <strong>{output.stem}</strong>
                    <small>
                      {jobs.length > 1 ? `${output.preset} · ` : ""}
                      {time(output.duration)} ·{" "}
                      {(output.sample_rate / 1000).toFixed(1)} kHz ·{" "}
                      {bytes(output.size)}
                    </small>
                  </span>
                </label>
              ))}
            </fieldset>
            {edits && (
              <label className="check-label">
                <input
                  type="checkbox"
                  disabled={busy}
                  checked={applyEdits}
                  onChange={(e) => setApplyEdits(e.target.checked)}
                />
                Use current edits · {preciseTime(edits.start)}–
                {preciseTime(edits.end)} and stem levels
              </label>
            )}
            <div className="export-options">
              <label>
                Format
                <select
                  disabled={busy}
                  value={format}
                  onChange={(e) => setFormat(e.target.value)}
                >
                  <option value="Original">As created · same format</option>
                  <option value="FLAC">FLAC · lossless</option>
                  <option value="WAV">WAV · 24-bit lossless</option>
                  <option value="MP3">MP3</option>
                  <option value="M4A">M4A / AAC</option>
                  <option value="OGG">OGG / Vorbis</option>
                </select>
              </label>
              {["MP3", "M4A", "OGG"].includes(format) && (
                <label>
                  Bitrate
                  <select
                    disabled={busy}
                    value={bitrate}
                    onChange={(e) => setBitrate(Number(e.target.value))}
                  >
                    {[128, 192, 256, 320].map((n) => (
                      <option key={n} value={n}>
                        {n} kbps
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                Filename prefix (optional)
                <input
                  disabled={busy}
                  maxLength={120}
                  value={name}
                  placeholder="Keep the current filenames"
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
            </div>
            <label>
              Destination folder
              <div className="export-folder">
                <input
                  disabled={busy}
                  value={directory}
                  placeholder="Choose a folder…"
                  onChange={(e) => setDirectory(e.target.value)}
                />
                <button
                  disabled={busy}
                  onClick={() =>
                    void chooseFolder()
                      .then((path) => {
                        if (path) setDirectory(path);
                      })
                      .catch((e) => setError(String(e)))
                  }
                >
                  <FolderOpen size={15} />
                  Browse
                </button>
              </div>
            </label>
            <p className="export-note">
              {applyEdits && edits
                ? "Exports the selected range and stem levels. Source recordings and created stems are preserved."
                : format === "Original"
                  ? "Copies the created files exactly. Listening volume, mute and solo do not affect this export."
                  : "Converts created stems at their original sample rate. Converting compressed audio to lossless cannot restore discarded detail."}
            </p>
          </>
        )}
        {error && (
          <p className="error-inline" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          {busy && <Spinner label="Saving audio…" />}
          <button disabled={busy} onClick={onClose}>
            {done ? "Done" : "Cancel"}
          </button>
          {done ? (
            <button className="primary" onClick={() => showFile(done.paths[0])}>
              <FolderOpen size={15} />
              Open folder
            </button>
          ) : (
            <button
              className="primary"
              disabled={busy || !chosen.length || !directory.trim()}
              onClick={() => void exportSelected()}
            >
              <Download size={15} />
              Export {chosen.length} {chosen.length === 1 ? "stem" : "stems"}
            </button>
          )}
        </div>
      </div>
    </Dialog>
  );
}
