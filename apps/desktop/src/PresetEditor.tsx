import { useState } from "react";
import { Plus, X, RotateCcw, Save } from "lucide-react";
import type { Capabilities, ModelInfo, Preset } from "./api";
import { chooseFolder } from "./api";
import type {
  InferenceSettings,
  OutputSettings,
} from "../../../packages/shared/types";

export function InferenceControls({
  value,
  onChange,
  models,
  capabilities,
}: {
  value: InferenceSettings;
  onChange: (v: InferenceSettings) => void;
  models: ModelInfo[];
  capabilities: Capabilities | null;
}) {
  const update = <K extends keyof InferenceSettings>(
    key: K,
    v: InferenceSettings[K],
  ) => onChange({ ...value, [key]: v });
  const roformer = models.some((m) => m.family === "MDXC");
  const mdx = models.some((m) => m.family === "MDX");
  const vr = models.some((m) => m.family === "VR");
  const demucs = models.some((m) => m.family === "Demucs");
  return (
    <div className="form-grid">
      <label>
        Device
        <select
          value={value.device}
          onChange={(e) =>
            update("device", e.target.value as InferenceSettings["device"])
          }
        >
          <option value="auto">Automatic</option>
          <option value="cpu">CPU</option>
          <option value="cuda" disabled={!capabilities?.cuda}>
            NVIDIA CUDA{!capabilities?.cuda ? " · unavailable" : ""}
          </option>
          <option value="mps" disabled={!capabilities?.mps}>
            Apple MPS{!capabilities?.mps ? " · unavailable" : ""}
          </option>
        </select>
      </label>
      {capabilities && capabilities.gpus.length > 1 && (
        <label>
          GPU
          <select
            value={value.gpu_index}
            onChange={(e) => update("gpu_index", Number(e.target.value))}
          >
            {capabilities.gpus.map((g) => (
              <option key={g.index} value={g.index}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        Precision
        <select
          value={value.precision}
          onChange={(e) =>
            update(
              "precision",
              e.target.value as InferenceSettings["precision"],
            )
          }
        >
          <option value="float32">Float32 · full precision</option>
          <option value="autocast">Autocast · lower memory</option>
          <option value="float16">Native Float16 · experimental</option>
        </select>
      </label>
      {roformer && (
        <>
          <label title="Number of overlapping prediction windows. Model default preserves its YAML recommendation.">
            RoFormer overlap
            <select
              value={value.overlap ?? ""}
              onChange={(e) =>
                update(
                  "overlap",
                  e.target.value ? Number(e.target.value) : null,
                )
              }
            >
              <option value="">Model default</option>
              {[2, 4, 8, 12, 16].map((n) => (
                <option key={n} value={n}>
                  {n} windows
                </option>
              ))}
            </select>
          </label>
          <label title="Overriding the trained context can change quality. Keep model default for Ultra.">
            Context size
            <input
              type="number"
              min={64}
              max={4096}
              placeholder="Model default"
              value={value.segment_size ?? ""}
              onChange={(e) =>
                update(
                  "segment_size",
                  e.target.value ? Number(e.target.value) : null,
                )
              }
            />
          </label>
        </>
      )}
      {mdx && (
        <>
          <label>
            MDX overlap
            <input
              type="number"
              min="0"
              max="0.95"
              step="0.05"
              value={value.mdx_overlap}
              onChange={(e) => update("mdx_overlap", Number(e.target.value))}
            />
          </label>
          <label>
            MDX segment
            <input
              type="number"
              min="32"
              max="4096"
              value={value.mdx_segment_size}
              onChange={(e) =>
                update("mdx_segment_size", Number(e.target.value))
              }
            />
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={value.denoise}
              onChange={(e) => update("denoise", e.target.checked)}
            />
            Denoise
          </label>
        </>
      )}
      {(mdx ||
        vr ||
        models.some(
          (m) => m.family === "MDXC" && !m.architecture.includes("RoFormer"),
        )) && (
        <label>
          Batch size
          <input
            type="number"
            min="1"
            max="16"
            value={value.batch_size}
            onChange={(e) => update("batch_size", Number(e.target.value))}
          />
        </label>
      )}
      {vr && (
        <>
          <label>
            Aggression
            <input
              type="number"
              min="0"
              max="100"
              value={value.vr_aggression}
              onChange={(e) => update("vr_aggression", Number(e.target.value))}
            />
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={value.vr_tta}
              onChange={(e) => update("vr_tta", e.target.checked)}
            />
            Test-time augmentation
          </label>
        </>
      )}
      {demucs && (
        <label>
          Demucs shifts
          <input
            type="number"
            min="0"
            max="20"
            value={value.demucs_shifts}
            onChange={(e) => update("demucs_shifts", Number(e.target.value))}
          />
        </label>
      )}
      {roformer && (
        <label
          className="check-label"
          title="May add considerable compilation time and memory."
        >
          <input
            type="checkbox"
            checked={value.torch_compile}
            onChange={(e) => update("torch_compile", e.target.checked)}
          />
          Torch compile · experimental
        </label>
      )}
    </div>
  );
}

export function OutputControls({
  value,
  onChange,
  onError,
}: {
  value: OutputSettings;
  onChange: (v: OutputSettings) => void;
  onError: (e: unknown) => void;
}) {
  const update = <K extends keyof OutputSettings>(
    key: K,
    v: OutputSettings[K],
  ) => onChange({ ...value, [key]: v });
  return (
    <div className="form-grid">
      <label className="wide">
        Output folder
        <div className="input-action">
          <input
            value={value.directory}
            placeholder="Default output folder"
            onChange={(e) => update("directory", e.target.value)}
          />
          <button
            onClick={() =>
              void chooseFolder()
                .then((p) => {
                  if (p) update("directory", p);
                })
                .catch(onError)
            }
          >
            Choose…
          </button>
        </div>
      </label>
      <label>
        Format
        <select
          value={value.format}
          onChange={(e) =>
            update("format", e.target.value as OutputSettings["format"])
          }
        >
          {["FLAC", "WAV", "MP3", "OGG", "M4A"].map((f) => (
            <option key={f}>{f}</option>
          ))}
        </select>
      </label>
      <label>
        Sample rate
        <select
          value={value.sample_rate}
          onChange={(e) =>
            update(
              "sample_rate",
              Number(e.target.value) as OutputSettings["sample_rate"],
            )
          }
        >
          <option value={0}>Preserve original</option>
          {[44100, 48000, 88200, 96000].map((r) => (
            <option key={r} value={r}>
              {r / 1000} kHz
            </option>
          ))}
        </select>
      </label>
      {["MP3", "OGG", "M4A"].includes(value.format) && (
        <label>
          Bitrate
          <select
            value={value.bitrate}
            onChange={(e) =>
              update(
                "bitrate",
                Number(e.target.value) as OutputSettings["bitrate"],
              )
            }
          >
            {[128, 192, 256, 320].map((b) => (
              <option key={b} value={b}>
                {b} kbps
              </option>
            ))}
          </select>
        </label>
      )}
      <label title="Only attenuates peaks exceeding this ceiling; does not amplify quiet stems.">
        Peak ceiling
        <input
          type="number"
          min="0.01"
          max="1"
          step="0.01"
          value={value.normalization}
          onChange={(e) => update("normalization", Number(e.target.value))}
        />
      </label>
      <label className="wide">
        Filename template
        <input
          value={value.template}
          onChange={(e) => update("template", e.target.value)}
        />
        <small>{"{original}, {stem}, {model}, {preset}"}</small>
      </label>
      <label>
        If output exists
        <select
          value={value.collision}
          onChange={(e) =>
            update("collision", e.target.value as OutputSettings["collision"])
          }
        >
          <option value="unique">Create unique filename</option>
          <option value="ask">Stop and ask me to choose</option>
          <option value="overwrite">Overwrite existing outputs</option>
        </select>
      </label>
      <label className="check-label">
        <input
          type="checkbox"
          checked={value.subfolder}
          onChange={(e) => update("subfolder", e.target.checked)}
        />
        Subfolder for each recording
      </label>
    </div>
  );
}

export function PresetEditor({
  initial,
  models,
  capabilities,
  onSave,
  onError,
}: {
  initial: Preset;
  models: ModelInfo[];
  capabilities: Capabilities | null;
  onSave: (p: Preset) => Promise<void>;
  onError: (e: unknown) => void;
}) {
  const [preset, setPreset] = useState<Preset>(structuredClone(initial));
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const chosen = models.filter((m) => preset.models.includes(m.id));
  const add = (id: string) => {
    if (id && !preset.models.includes(id))
      setPreset((p) => ({ ...p, models: [...p.models, id], weights: null }));
  };
  return (
    <div className="preset-editor">
      <div className="form-grid">
        <label>
          Name
          <input
            autoFocus
            value={preset.name}
            onChange={(e) => setPreset({ ...preset, name: e.target.value })}
          />
        </label>
        <label>
          Target
          <select
            value={preset.task}
            onChange={(e) =>
              setPreset({ ...preset, task: e.target.value as Preset["task"] })
            }
          >
            {[
              "Vocals",
              "Instrumental",
              "Both",
              "Drums",
              "Bass",
              "Other",
              "4 Stems",
              "All",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="wide">
          Description
          <input
            value={preset.description}
            onChange={(e) =>
              setPreset({ ...preset, description: e.target.value })
            }
          />
        </label>
      </div>
      <h3>Models & ensemble</h3>
      <p className="muted">
        Models run one at a time. Combine models that produce the same stems.
      </p>
      <div className="ensemble-chain">
        {preset.models.map((id, i) => (
          <div className="ensemble-model" key={id}>
            <span className="model-letter">{String.fromCharCode(65 + i)}</span>
            <div>
              <strong>{models.find((m) => m.id === id)?.name ?? id}</strong>
              <code>{id}</code>
            </div>
            {preset.models.length > 1 && (
              <button
                aria-label={`Remove model ${i + 1}`}
                onClick={() =>
                  setPreset((p) => ({
                    ...p,
                    models: p.models.filter((m) => m !== id),
                    weights: null,
                  }))
                }
              >
                <X size={15} />
              </button>
            )}
          </div>
        ))}
      </div>
      <div className="input-action">
        <input
          placeholder="Search models to add…"
          aria-label="Search ensemble models"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          aria-label="Add model"
          value=""
          disabled={preset.models.length >= 8}
          onChange={(e) => add(e.target.value)}
        >
          <option value="">+ Add model</option>
          {models
            .filter(
              (m) =>
                !preset.models.includes(m.id) &&
                `${m.id} ${m.name}`
                  .toLowerCase()
                  .includes(search.toLowerCase()),
            )
            .slice(0, 100)
            .map((m) => (
              <option value={m.id} key={m.id}>
                {m.name}
              </option>
            ))}
        </select>
      </div>
      {preset.models.length > 1 && (
        <div className="form-grid">
          <label>
            Algorithm
            <select
              value={preset.algorithm}
              onChange={(e) =>
                setPreset({
                  ...preset,
                  algorithm: e.target.value as Preset["algorithm"],
                  weights: null,
                })
              }
            >
              {[
                "avg_fft",
                "uvr_max_spec",
                "uvr_min_spec",
                "avg_wave",
                "median_fft",
                "min_fft",
                "max_fft",
                "median_wave",
                "min_wave",
                "max_wave",
                "ensemble_wav",
              ].map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
          </label>
          {["avg_fft", "avg_wave"].includes(preset.algorithm) && (
            <label className="check-label">
              <input
                type="checkbox"
                checked={preset.weights !== null}
                onChange={(e) =>
                  setPreset({
                    ...preset,
                    weights: e.target.checked
                      ? preset.models.map(() => 1)
                      : null,
                  })
                }
              />
              Custom model weights
            </label>
          )}
          {preset.weights?.map((w, i) => (
            <label key={preset.models[i]}>
              Model {String.fromCharCode(65 + i)} weight
              <input
                type="number"
                min="0"
                step="0.1"
                value={w}
                onChange={(e) =>
                  setPreset({
                    ...preset,
                    weights: preset.weights!.map((weight, j) =>
                      i === j ? Number(e.target.value) : weight,
                    ),
                  })
                }
              />
            </label>
          ))}
        </div>
      )}
      <details open>
        <summary>Inference settings</summary>
        <InferenceControls
          value={preset.parameters}
          onChange={(parameters) => setPreset({ ...preset, parameters })}
          models={chosen}
          capabilities={capabilities}
        />
      </details>
      <details>
        <summary>Output settings</summary>
        <OutputControls
          value={preset.output}
          onChange={(output) => setPreset({ ...preset, output })}
          onError={onError}
        />
      </details>
      <div className="dialog-actions">
        <button onClick={() => setPreset(structuredClone(initial))}>
          <RotateCcw size={15} />
          Reset
        </button>
        <button
          className="primary"
          disabled={busy || !preset.name.trim()}
          onClick={() => {
            setBusy(true);
            void onSave(preset)
              .catch(onError)
              .finally(() => setBusy(false));
          }}
        >
          <Save size={15} />
          {busy ? "Saving…" : "Save preset"}
        </button>
      </div>
      <span className="sr-only">
        <Plus />
      </span>
    </div>
  );
}
