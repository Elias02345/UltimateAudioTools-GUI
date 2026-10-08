"""Non-destructive exports of completed results, staged before publication."""

import errno
import os
import shutil
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .audio import input_path, metadata, run_ffmpeg, safe_name, unique_path, validate_export
from .schema import StrictModel


class ResultExport(StrictModel):
    job_ids: list[str] = Field(min_length=1, max_length=16)
    paths: list[str] = Field(min_length=1, max_length=128)
    directory: str = Field(min_length=1)
    name: str = Field(default="", max_length=120)
    format: Literal["Original", "FLAC", "WAV", "MP3", "OGG", "M4A"] = "Original"
    bitrate: Literal[128, 192, 256, 320] = 320
    start: float = Field(default=0, ge=0)
    end: float | None = Field(default=None, gt=0)
    gains: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_edits(self):
        if self.end is not None and self.end <= self.start:
            raise ValueError("End must be later than start.")
        if len(set(self.paths)) != len(self.paths):
            raise ValueError("Select each output only once.")
        if any(not 0 <= gain <= 1 for gain in self.gains.values()):
            raise ValueError("Stem levels must be between 0 and 100 percent.")
        return self


def export_results(request: ResultExport, jobs: list[dict]) -> dict:
    allowed = {
        output["path"]: (job, output)
        for job in jobs
        if job["id"] in request.job_ids and job["status"] == "Completed"
        for output in (job.get("result") or {}).get("outputs", [])
    }
    if any(path not in allowed for path in request.paths):
        raise ValueError("Export only outputs from the selected completed results.")
    # Validate every input before creating anything in the destination.
    sources = []
    for path in request.paths:
        source = input_path(path)
        info = metadata(str(source))
        end = request.end if request.end is not None else info["duration"]
        if request.start >= info["duration"] or end > info["duration"] + 0.05:
            raise ValueError("The selected range is outside an output recording.")
        sources.append((source, info, allowed[path][1], end))
    directory = Path(request.directory).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError("Choose an existing export folder.")
    published = []
    try:
        with tempfile.TemporaryDirectory(prefix=".separator-export-", dir=directory) as temp:
            prepared = []
            for index, (source, info, output, end) in enumerate(sources):
                fmt = request.format if request.format != "Original" else source.suffix[1:].upper()
                gain = request.gains.get(str(source), 1)
                edited = request.start != 0 or request.end is not None or gain != 1
                name = (
                    safe_name(f"{request.name} - {output['stem']}")
                    if request.name.strip()
                    else source.stem + (" - edited" if edited else "")
                )
                suffix = source.suffix if request.format == "Original" else f".{fmt.lower()}"
                staged = Path(temp) / f"{index}{suffix}"
                if not edited and request.format == "Original":
                    shutil.copyfile(source, staged)
                else:
                    validate_export(info["sample_rate"], fmt)
                    codec = {
                        "WAV": "pcm_s24le",
                        "FLAC": "flac",
                        "MP3": "libmp3lame",
                        "OGG": "libvorbis",
                        "M4A": "aac",
                    }[fmt]
                    args = [
                        "-y",
                        "-i",
                        str(source),
                        "-ss",
                        str(request.start),
                        "-t",
                        str(end - request.start),
                    ]
                    args += ["-af", f"volume={gain}", "-ar", str(info["sample_rate"]), "-c:a", codec]
                    if fmt in {"MP3", "OGG", "M4A"}:
                        args += ["-b:a", f"{request.bitrate}k"]
                    run_ffmpeg([*args, str(staged)])
                    result = metadata(str(staged))
                    if abs(result["duration"] - (end - request.start)) > 0.2:
                        raise ValueError("The exported duration did not match the selected range.")
                with staged.open("rb+") as stream:
                    os.fsync(stream.fileno())
                prepared.append((staged, directory / f"{name}{suffix}"))
            for staged, target in prepared:
                while True:
                    destination = unique_path(target, "unique")
                    try:
                        os.link(staged, destination)
                        published.append(destination)
                        break
                    except FileExistsError:
                        continue
                    except OSError as error:
                        if error.errno not in {errno.EPERM, errno.EOPNOTSUPP, errno.ENOSYS, errno.EXDEV}:
                            raise
                        # Removable drives may not support hard links. Still claim
                        # the new name exclusively and remove our copy on failure.
                        created = False
                        try:
                            with destination.open("xb") as output:
                                created = True
                                with staged.open("rb") as source:
                                    shutil.copyfileobj(source, output)
                                output.flush()
                                os.fsync(output.fileno())
                        except FileExistsError:
                            continue
                        except Exception:
                            if created:
                                destination.unlink(missing_ok=True)
                            raise
                        published.append(destination)
                        break
    except Exception:
        for path in published:
            path.unlink(missing_ok=True)
        raise
    return {"directory": str(directory), "paths": [str(path) for path in published]}
