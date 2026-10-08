import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { ValidateFunction } from "ajv";
import * as validators from "../../../packages/shared/validators.js";
import type {
  AudioMetadata,
  Capabilities,
  Job,
  ModelInfo,
  Preset,
  Settings,
} from "../../../packages/shared/types";

export type { AudioMetadata, Capabilities, Job, ModelInfo, Preset, Settings };
export const BRAND = { name: "Separator", version: "0.1.2" };
export function validate<T>(name: string, value: unknown): T {
  const check = (validators as Record<string, ValidateFunction>)[name];
  if (!check || !check(value))
    throw new Error(
      `Invalid ${name} data: ${check?.errors?.map((error) => `${error.instancePath || "/"} ${error.message}`).join("; ") ?? "Unknown contract type"}`,
    );
  return value as T;
}
export async function api<T>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  try {
    return await invoke<T>("engine_request", { method, params });
  } catch (error) {
    void invoke("frontend_log", {
      message: `${method}: ${String(error)}`,
    }).catch(() => {});
    throw error;
  }
}
export const restartApplication = () => invoke<void>("restart_application");
export const restartRuntime = () => invoke<void>("restart_runtime");
export const chooseAudio = () => invoke<string[]>("choose_audio");
export const chooseFolder = () => invoke<string | null>("choose_folder");
export const reveal = (path: string) => invoke("reveal_path", { path });
export const mediaUrl = (path: string) => invoke<string>("audio_url", { path });
export const exportAudio = (paths: string[]) =>
  invoke<string | null>("export_audio", { paths });
export const exportPreset = (preset: Preset) =>
  invoke<boolean>("export_preset", { preset });
export const importPreset = () => invoke<unknown>("import_preset");
export type EngineEvent = {
  v: 1;
  event: string;
  data: Record<string, unknown>;
};
export const onEngineEvent = (callback: (event: EngineEvent) => void) =>
  listen<EngineEvent>("engine-event", (e) => callback(e.payload));
export const activeJob = (j: Job) =>
  [
    "Preparing",
    "Downloading model",
    "Loading model",
    "Processing",
    "Ensembling",
    "Encoding",
  ].includes(j.status);
export const time = (s: number) =>
  `${Math.floor(s / 60)}:${Math.floor(s % 60)
    .toString()
    .padStart(2, "0")}`;
export const bytes = (n: number | null | undefined) =>
  n == null
    ? "Size unknown"
    : n >= 1024 ** 3
      ? `${(n / 1024 ** 3).toFixed(1)} GB`
      : `${(n / 1024 ** 2).toFixed(0)} MB`;
