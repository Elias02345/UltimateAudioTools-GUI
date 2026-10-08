/* Generated from Pydantic. Run scripts/generate_schema.py and scripts/generate_types.mjs. */

export type V = 1;
export type Id = string;
export type Method = string;
export type Version = 1;
export type Id1 = string;
export type Name = string;
export type Description = string;
export type Task = "Vocals" | "Instrumental" | "Both" | "Drums" | "Bass" | "Other" | "4 Stems" | "All";
/**
 * @minItems 1
 * @maxItems 8
 */
export type Models = string[];
export type Algorithm =
  | "avg_wave"
  | "avg_fft"
  | "median_wave"
  | "median_fft"
  | "min_wave"
  | "max_wave"
  | "min_fft"
  | "max_fft"
  | "uvr_max_spec"
  | "uvr_min_spec"
  | "ensemble_wav";
export type Weights = number[] | null;
export type Engine = "native" | "container";
export type Device = "auto" | "cpu" | "cuda" | "mps";
export type GpuIndex = number;
export type Precision = "float32" | "autocast" | "float16";
export type Overlap = number | null;
export type SegmentSize = number | null;
export type BatchSize = number;
export type MdxOverlap = number;
export type MdxSegmentSize = number;
export type Denoise = boolean;
export type VrAggression = number;
export type VrTta = boolean;
export type DemucsShifts = number;
export type TorchCompile = boolean;
export type ChunkDuration = number | null;
export type Directory = string;
export type Format = "FLAC" | "WAV" | "MP3" | "OGG" | "M4A";
export type SampleRate = 0 | 44100 | 48000 | 88200 | 96000;
export type Bitrate = 128 | 192 | 256 | 320;
export type Normalization = number;
export type Template = string;
export type Subfolder = boolean;
export type Collision = "unique" | "overwrite" | "ask";
export type Builtin = boolean;
export type Quality = "Fast" | "Balanced" | "Ultra" | "Custom";
export type Version1 = 1;
export type SetupComplete = boolean;
export type AutoDownload = boolean;
export type Theme = "dark" | "light" | "system";
export type ReducedMotion = boolean;
export type Notifications = boolean;
export type CheckUpdates = boolean;
export type DefaultQuality = "Fast" | "Balanced" | "Ultra";
export type ModelDirectory = string;
export type Engine1 = "native" | "container";
export type ContainerCommand = "docker" | "podman";
export type ContainerImage = string;
export type Id2 = string;
export type ProjectId = string | null;
export type Status =
  | "Pending"
  | "Preparing"
  | "Downloading model"
  | "Loading model"
  | "Processing"
  | "Ensembling"
  | "Encoding"
  | "Completed"
  | "Failed"
  | "Cancelled"
  | "Interrupted";
export type CreatedAt = number;
export type Path = string;
export type RangeStart = number | null;
export type RangeEnd = number | null;
export type ComparisonId = string | null;
export type DownloadConsent = boolean;
export type Path1 = string;
export type Name1 = string;
export type Duration = number;
export type SampleRate1 = number;
export type Channels = number;
export type Codec = string;
export type Size = number;
export type Bitrate1 = number;
export type Error = string | null;
export type Stem = string;
export type Path2 = string;
export type Duration1 = number;
export type SampleRate2 = number;
export type Size1 = number;
export type Outputs = OutputResult[];
export type Device1 = string;
export type Model = string;
export type Device2 = string;
export type Precision1 = string;
export type Models1 = ModelExecution[];
export type Engine2 = string;
export type EngineVersion = string;
export type Elapsed = number;
export type PeakVram = number | null;
export type StartedAt = number | null;
export type CompletedAt = number | null;
export type Stage = string | null;
export type Model1 = string | null;
export type Device3 = string | null;
export type PassIndex = number | null;
export type PassCount = number | null;
export type Download = {
  [k: string]: unknown;
} | null;
export type Id3 = string;
export type Name2 = string;
export type Family = string;
export type Architecture = string;
export type Stems = string[];
export type Target = string | null;
export type Downloaded = boolean;
export type Size2 = number | null;
export type DiskUsage = number;
export type Path3 = string;
export type Sha256 = string | null;
export type Source = string;
export type License = string;
export type Vip = boolean;
export type DownloadFiles = string[];
export type PhysicalFiles = string[];
export type Benchmark = string;
export type Platform = string;
export type Architecture1 = string;
export type Cpu = string;
export type Ram = number | null;
export type Index = number;
export type Name3 = string;
export type Vram = number;
export type Gpus = GPUInfo[];
export type Cuda = boolean;
export type CudaInstallable = boolean;
export type CudaVersion = string | null;
export type Mps = boolean;
export type Mlx = boolean;
export type Directml = boolean;
export type Python = string;
export type Torch = string;
export type EngineVersion1 = string;
export type Ffmpeg = string | null;
export type DiskFree = number;
export type Backends = string[];
export type RecommendedDevice = string;
export type Containers = string[];
export type Id4 = string;
export type Name4 = string;
export type CreatedAt1 = number;
export type Archived = boolean;

export interface Contract {
  request: Request;
  preset: Preset;
  settings: Settings;
  job: Job;
  model: ModelInfo;
  capabilities: Capabilities;
  project: Project;
}
export interface Request {
  v: V;
  id: Id;
  method: Method;
  params: Params;
}
export interface Params {
  [k: string]: unknown;
}
export interface Preset {
  version: Version;
  id: Id1;
  name: Name;
  description: Description;
  task: Task;
  models: Models;
  algorithm: Algorithm;
  weights: Weights;
  engine: Engine;
  parameters: InferenceSettings;
  output: OutputSettings;
  builtin: Builtin;
  quality: Quality;
}
export interface InferenceSettings {
  device: Device;
  gpu_index: GpuIndex;
  precision: Precision;
  overlap: Overlap;
  segment_size: SegmentSize;
  batch_size: BatchSize;
  mdx_overlap: MdxOverlap;
  mdx_segment_size: MdxSegmentSize;
  denoise: Denoise;
  vr_aggression: VrAggression;
  vr_tta: VrTta;
  demucs_shifts: DemucsShifts;
  torch_compile: TorchCompile;
  chunk_duration: ChunkDuration;
}
export interface OutputSettings {
  directory: Directory;
  format: Format;
  sample_rate: SampleRate;
  bitrate: Bitrate;
  normalization: Normalization;
  template: Template;
  subfolder: Subfolder;
  collision: Collision;
}
export interface Settings {
  version: Version1;
  setup_complete: SetupComplete;
  output: OutputSettings;
  parameters: InferenceSettings;
  auto_download: AutoDownload;
  theme: Theme;
  reduced_motion: ReducedMotion;
  notifications: Notifications;
  check_updates: CheckUpdates;
  default_quality: DefaultQuality;
  model_directory: ModelDirectory;
  engine: Engine1;
  container_command: ContainerCommand;
  container_image: ContainerImage;
}
export interface Job {
  id: Id2;
  project_id: ProjectId;
  status: Status;
  created_at: CreatedAt;
  request: JobRequest;
  source: AudioMetadata;
  error: Error;
  result: JobResult | null;
  started_at: StartedAt;
  completed_at: CompletedAt;
  stage: Stage;
  model: Model1;
  device: Device3;
  pass_index: PassIndex;
  pass_count: PassCount;
  download: Download;
}
export interface JobRequest {
  path: Path;
  preset: Preset;
  range_start: RangeStart;
  range_end: RangeEnd;
  comparison_id: ComparisonId;
  download_consent: DownloadConsent;
}
export interface AudioMetadata {
  path: Path1;
  name: Name1;
  duration: Duration;
  sample_rate: SampleRate1;
  channels: Channels;
  codec: Codec;
  size: Size;
  bitrate: Bitrate1;
}
export interface JobResult {
  outputs: Outputs;
  device: Device1;
  models: Models1;
  engine: Engine2;
  engine_version: EngineVersion;
  elapsed: Elapsed;
  peak_vram: PeakVram;
}
export interface OutputResult {
  stem: Stem;
  path: Path2;
  duration: Duration1;
  sample_rate: SampleRate2;
  size: Size1;
}
export interface ModelExecution {
  model: Model;
  device: Device2;
  precision: Precision1;
}
export interface ModelInfo {
  id: Id3;
  name: Name2;
  family: Family;
  architecture: Architecture;
  stems: Stems;
  target: Target;
  downloaded: Downloaded;
  size: Size2;
  disk_usage: DiskUsage;
  path: Path3;
  sha256: Sha256;
  source: Source;
  license: License;
  vip: Vip;
  download_files: DownloadFiles;
  physical_files: PhysicalFiles;
  benchmark: Benchmark;
}
export interface Capabilities {
  platform: Platform;
  architecture: Architecture1;
  cpu: Cpu;
  ram: Ram;
  gpus: Gpus;
  cuda: Cuda;
  cuda_installable: CudaInstallable;
  cuda_version: CudaVersion;
  mps: Mps;
  mlx: Mlx;
  directml: Directml;
  python: Python;
  torch: Torch;
  engine_version: EngineVersion1;
  ffmpeg: Ffmpeg;
  disk_free: DiskFree;
  backends: Backends;
  recommended_device: RecommendedDevice;
  containers: Containers;
}
export interface GPUInfo {
  index: Index;
  name: Name3;
  vram: Vram;
}
export interface Project {
  id: Id4;
  name: Name4;
  created_at: CreatedAt1;
  archived: Archived;
}
