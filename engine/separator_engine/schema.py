"""Single schema source; scripts/generate_schema.py exports the IPC JSON schema."""

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Algorithm = Literal[
    "avg_wave",
    "avg_fft",
    "median_wave",
    "median_fft",
    "min_wave",
    "max_wave",
    "min_fft",
    "max_fft",
    "uvr_max_spec",
    "uvr_min_spec",
    "ensemble_wav",
]
Target = Literal["Vocals", "Instrumental", "Both", "Drums", "Bass", "Other", "4 Stems", "All"]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, json_schema_serialization_defaults_required=True
    )


class InferenceSettings(StrictModel):
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    gpu_index: int = Field(default=0, ge=0, le=16)
    precision: Literal["float32", "autocast", "float16"] = "float32"
    overlap: int | None = Field(default=None, ge=1, le=16)
    segment_size: int | None = Field(default=None, ge=64, le=4096)
    batch_size: int = Field(default=1, ge=1, le=16)
    mdx_overlap: float = Field(default=0.25, ge=0, lt=1)
    mdx_segment_size: int = Field(default=256, ge=32, le=4096)
    denoise: bool = False
    vr_aggression: int = Field(default=5, ge=0, le=100)
    vr_tta: bool = False
    demucs_shifts: int = Field(default=2, ge=0, le=20)
    torch_compile: bool = False
    chunk_duration: int | None = Field(default=None, ge=10, le=3600)


class OutputSettings(StrictModel):
    directory: str = ""
    format: Literal["FLAC", "WAV", "MP3", "OGG", "M4A"] = "FLAC"
    sample_rate: Literal[0, 44100, 48000, 88200, 96000] = 0
    bitrate: Literal[128, 192, 256, 320] = 320
    normalization: float = Field(default=0.98, gt=0, le=1)
    template: str = Field(default="{original} - {stem}", min_length=1, max_length=180)
    subfolder: bool = True
    collision: Literal["unique", "overwrite", "ask"] = "unique"


class Preset(StrictModel):
    version: Literal[1] = 1
    id: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    task: Target = "Both"
    models: list[str] = Field(min_length=1, max_length=8)
    algorithm: Algorithm = "avg_fft"
    weights: list[float] | None = None
    engine: Literal["native", "container"] = "native"
    parameters: InferenceSettings = Field(default_factory=InferenceSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)
    builtin: bool = False
    quality: Literal["Fast", "Balanced", "Ultra", "Custom"] = "Custom"

    @model_validator(mode="after")
    def validate_models(self):
        if len(set(self.models)) != len(self.models):
            raise ValueError("Each model may only appear once in an ensemble.")
        for name in self.models:
            if "/" in name or "\\" in name or name in {".", ".."}:
                raise ValueError("Models must be catalogue filenames, not paths.")
        if self.weights is not None:
            if self.algorithm not in {"avg_wave", "avg_fft"}:
                raise ValueError("Only waveform and FFT averaging support weights.")
            if len(self.weights) != len(self.models):
                raise ValueError("Provide one weight per model.")
            if any(not math.isfinite(w) or w < 0 for w in self.weights) or sum(self.weights) <= 0:
                raise ValueError("Weights must be finite, non-negative and have a positive sum.")
        return self


class JobRequest(StrictModel):
    path: str = Field(min_length=1)
    preset: Preset
    range_start: float | None = Field(default=None, ge=0)
    range_end: float | None = Field(default=None, gt=0)
    comparison_id: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    download_consent: bool = False

    @model_validator(mode="after")
    def valid_range(self):
        if (self.range_start is None) != (self.range_end is None):
            raise ValueError("A comparison range requires both start and end.")
        if self.range_end is not None and self.range_end <= self.range_start:
            raise ValueError("End must be later than start.")
        return self


class Settings(StrictModel):
    version: Literal[1] = 1
    setup_complete: bool = False
    output: OutputSettings = Field(default_factory=OutputSettings)
    parameters: InferenceSettings = Field(default_factory=InferenceSettings)
    auto_download: bool = False
    theme: Literal["dark", "light", "system"] = "dark"
    reduced_motion: bool = False
    notifications: bool = False
    default_quality: Literal["Fast", "Balanced", "Ultra"] = "Ultra"
    model_directory: str = ""
    engine: Literal["native", "container"] = "native"
    container_command: Literal["docker", "podman"] = "docker"
    container_image: str = "separator-engine:0.1.3"


class Request(StrictModel):
    v: Literal[1]
    id: str = Field(min_length=1, max_length=120)
    method: str = Field(min_length=1, max_length=80)
    params: dict[str, Any] = Field(default_factory=dict)


class AudioMetadata(StrictModel):
    path: str
    name: str
    duration: float
    sample_rate: int
    channels: int
    codec: str
    size: int
    bitrate: int


class ModelInfo(StrictModel):
    id: str
    name: str
    family: str
    architecture: str
    stems: list[str]
    target: str | None
    downloaded: bool
    size: int | None
    disk_usage: int
    path: str
    sha256: str | None
    source: str
    license: str
    vip: bool
    download_files: list[str]
    physical_files: list[str]
    benchmark: str


class OutputResult(StrictModel):
    stem: str
    path: str
    duration: float
    sample_rate: int
    size: int


class ModelExecution(StrictModel):
    model: str
    device: str
    precision: str


class JobResult(StrictModel):
    outputs: list[OutputResult]
    device: str
    models: list[ModelExecution]
    engine: str
    engine_version: str
    elapsed: float
    peak_vram: int | None


class Job(StrictModel):
    id: str
    status: Literal[
        "Pending",
        "Preparing",
        "Downloading model",
        "Loading model",
        "Processing",
        "Ensembling",
        "Encoding",
        "Completed",
        "Failed",
        "Cancelled",
        "Interrupted",
    ]
    created_at: float
    request: JobRequest
    source: AudioMetadata
    error: str | None
    result: JobResult | None
    started_at: float | None = None
    completed_at: float | None = None
    stage: str | None = None
    model: str | None = None
    device: str | None = None
    pass_index: int | None = None
    pass_count: int | None = None
    download: dict[str, Any] | None = None


class GPUInfo(StrictModel):
    index: int
    name: str
    vram: int


class Capabilities(StrictModel):
    platform: str
    architecture: str
    cpu: str
    ram: int | None
    gpus: list[GPUInfo]
    cuda: bool
    cuda_installable: bool
    cuda_version: str | None
    mps: bool
    mlx: bool
    directml: bool
    python: str
    torch: str
    engine_version: str
    ffmpeg: str | None
    disk_free: int
    backends: list[str]
    recommended_device: str
    containers: list[str]


class Contract(StrictModel):
    request: Request
    preset: Preset
    settings: Settings
    job: Job
    model: ModelInfo
    capabilities: Capabilities
