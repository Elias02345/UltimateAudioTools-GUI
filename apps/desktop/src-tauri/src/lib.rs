use serde_json::{json, Value};
mod logs;
mod media;
use std::collections::{HashMap, HashSet};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex};
use std::time::Duration;
use tauri::{Emitter, Manager};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;

type Reply = Result<Value, String>;

struct Engine {
    child: Mutex<Child>,
    input: Mutex<ChildStdin>,
    pending: Arc<Mutex<HashMap<String, mpsc::Sender<Reply>>>>,
}

#[derive(Default)]
struct AppState {
    engine: Mutex<Option<Arc<Engine>>>,
    media: Mutex<Option<Arc<media::MediaServer>>>,
    approved_previews: Mutex<HashSet<PathBuf>>,
}

fn runtime_paths(app: &tauri::AppHandle) -> Result<(PathBuf, PathBuf), String> {
    let resources = app.path().resource_dir().map_err(|e| e.to_string())?;
    let source = if cfg!(debug_assertions) {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../engine")
    } else {
        resources.join("engine")
    };
    let python_relative = if cfg!(windows) {
        "python.exe"
    } else {
        "bin/python3"
    };
    let pointer = app
        .path()
        .app_local_data_dir()
        .map_err(|e| e.to_string())?
        .join("active-runtime.json");
    if let Ok(bytes) = std::fs::read(pointer) {
        if let Ok(value) = serde_json::from_slice::<Value>(&bytes) {
            if let Some(name) = value.get("directory").and_then(Value::as_str).filter(|_| {
                value.get("version").and_then(Value::as_str) == Some(env!("CARGO_PKG_VERSION"))
            }) {
                if name.starts_with("cuda-")
                    && name
                        .chars()
                        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '.')
                {
                    let root = app
                        .path()
                        .app_local_data_dir()
                        .map_err(|e| e.to_string())?
                        .join("runtimes")
                        .join(name);
                    let valid = std::fs::read(root.join("separator-runtime.json"))
                        .ok()
                        .and_then(|bytes| serde_json::from_slice::<Value>(&bytes).ok())
                        .is_some_and(|manifest| {
                            manifest.get("complete").and_then(Value::as_bool) == Some(true)
                                && manifest.get("version").and_then(Value::as_str)
                                    == Some(env!("CARGO_PKG_VERSION"))
                                && manifest.get("backend").and_then(Value::as_str) == Some("cuda")
                                && manifest.get("platform").and_then(Value::as_str)
                                    == Some(if cfg!(windows) { "Windows" } else { "Linux" })
                                && manifest
                                    .get("architecture")
                                    .and_then(Value::as_str)
                                    .is_some_and(|arch| matches!(arch, "x86_64" | "amd64"))
                        });
                    if valid && root.join(python_relative).is_file() {
                        return Ok((root.join(python_relative), source.clone()));
                    }
                }
            }
        }
    }
    {
        let root = resources.join("runtime/python");
        let python = root.join(python_relative);
        if python.is_file() {
            return Ok((python, source.clone()));
        }
    }
    if cfg!(debug_assertions) {
        let repo = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..");
        let python = repo.join(if cfg!(windows) {
            ".venv/Scripts/python.exe"
        } else {
            ".venv/bin/python"
        });
        if python.is_file() {
            return Ok((python, repo.join("engine")));
        }
    }
    Err("The private processing runtime is missing. Install the complete Separator package or repair the runtime in Setup.".into())
}

fn bundled_runtime(resources: &Path, source: &Path) -> Result<(PathBuf, PathBuf), String> {
    let root = if cfg!(debug_assertions) {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("resources/runtime/python")
    } else {
        resources.join("runtime/python")
    };
    let python = root.join(if cfg!(windows) {
        "python.exe"
    } else {
        "bin/python3"
    });
    if python.is_file() {
        Ok((python, source.to_path_buf()))
    } else {
        Err("The bundled CPU runtime is missing. Reinstall the complete package.".into())
    }
}

fn start_engine(app: &tauri::AppHandle) -> Result<Arc<Engine>, String> {
    let (mut python, source) = runtime_paths(app)?;
    let resources = app.path().resource_dir().map_err(|e| e.to_string())?;
    if python
        .components()
        .any(|part| part.as_os_str().to_string_lossy().starts_with("cuda-"))
    {
        if let Err(error) = probe_cuda_runtime(&python, &source) {
            log::warn!("Private CUDA runtime failed startup validation; using CPU: {error}");
            python = bundled_runtime(&resources, &source)?.0;
            let _ = app.emit("engine-event", json!({"v":1,"event":"runtime_recovery","data":{
                "message":"NVIDIA runtime could not start. The bundled CPU runtime is active. Reinstall acceleration in Settings."
            }}));
        }
    }
    let runtime_base = if cfg!(debug_assertions) {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("resources/runtime/python")
    } else {
        resources.join("runtime/python")
    };
    let runtime_manifests = if cfg!(debug_assertions) {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../runtime")
    } else {
        resources.join("runtime-manifests")
    };
    let data = app.path().app_local_data_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&data).map_err(|e| e.to_string())?;
    let mut command = Command::new(python);
    command
        .args(["-u", "-m", "separator_engine"])
        .env("PYTHONPATH", source)
        .env("SEPARATOR_DATA_DIR", data)
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONNOUSERSITE", "1")
        .env_remove("PYTHONHOME")
        .env_remove("VIRTUAL_ENV")
        .env("SEPARATOR_RUNTIME_BASE", runtime_base)
        .env("SEPARATOR_RUNTIME_MANIFESTS", runtime_manifests)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    let mut child = command
        .spawn()
        .map_err(|e| format!("Could not start the processing runtime: {e}"))?;
    let input = child.stdin.take().ok_or("Runtime input pipe unavailable")?;
    let output = child
        .stdout
        .take()
        .ok_or("Runtime output pipe unavailable")?;
    let errors = child
        .stderr
        .take()
        .ok_or("Runtime error pipe unavailable")?;
    let pending: Arc<Mutex<HashMap<String, mpsc::Sender<Reply>>>> =
        Arc::new(Mutex::new(HashMap::new()));
    let reader_pending = pending.clone();
    let handle = app.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(output).lines() {
            let Ok(line) = line else { break };
            let Ok(value) = serde_json::from_str::<Value>(&line) else {
                continue;
            };
            if value.get("v").and_then(Value::as_u64) != Some(1) {
                continue;
            }
            if let Some(id) = value.get("id").and_then(Value::as_str) {
                if let Ok(mut map) = reader_pending.lock() {
                    if let Some(tx) = map.remove(id) {
                        let response = if let Some(error) = value.get("error") {
                            Err(error
                                .get("message")
                                .and_then(Value::as_str)
                                .unwrap_or("Engine request failed")
                                .into())
                        } else {
                            Ok(value.get("result").cloned().unwrap_or(Value::Null))
                        };
                        let _ = tx.send(response);
                    }
                }
            } else if value.get("event").is_some() {
                if let Some(outputs) = value
                    .pointer("/data/job/result/outputs")
                    .and_then(Value::as_array)
                {
                    for output in outputs {
                        if let Some(path) = output.get("path").and_then(Value::as_str) {
                            let _ = handle.asset_protocol_scope().allow_file(path);
                        }
                    }
                }
                let _ = handle.emit("engine-event", value);
            }
        }
        if let Ok(mut map) = reader_pending.lock() {
            for (_, tx) in map.drain() {
                let _ = tx.send(Err("The runtime stopped. Retry to restart it.".into()));
            }
        }
        let _ = handle.emit(
            "engine-event",
            json!({"v":1,"event":"engine_stopped","data":{}}),
        );
    });
    std::thread::spawn(move || {
        for line in BufReader::new(errors).lines().map_while(Result::ok) {
            log::warn!("engine: {}", line);
        }
    });
    Ok(Arc::new(Engine {
        child: Mutex::new(child),
        input: Mutex::new(input),
        pending,
    }))
}

fn probe_cuda_runtime(python: &Path, source: &Path) -> Result<(), String> {
    let mut child = Command::new(python)
        .arg("-I")
        .arg(source.join("separator_engine/runtime_probe.py"))
        .arg("--cuda")
        .env_remove("PYTHONHOME")
        .env_remove("VIRTUAL_ENV")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| e.to_string())?;
    for _ in 0..300 {
        if let Some(status) = child.try_wait().map_err(|e| e.to_string())? {
            return if status.success() {
                Ok(())
            } else {
                Err(format!("Probe exited with {status}"))
            };
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    let _ = child.kill();
    let _ = child.wait();
    Err("CUDA startup probe timed out".into())
}

fn request_engine(app: tauri::AppHandle, method: String, params: Value) -> Reply {
    if method.len() > 80 || !params.is_object() {
        return Err("Invalid engine request".into());
    }
    let state = app.state::<AppState>();
    let engine = {
        let mut guard = state
            .engine
            .lock()
            .map_err(|_| "Runtime state lock failed")?;
        let alive = guard.as_ref().is_some_and(|e| {
            e.child
                .lock()
                .is_ok_and(|mut c| c.try_wait().is_ok_and(|s| s.is_none()))
        });
        if !alive {
            *guard = Some(start_engine(&app)?);
        }
        guard.as_ref().cloned().ok_or("Runtime unavailable")?
    };
    let id = uuid::Uuid::new_v4().to_string();
    let (tx, rx) = mpsc::channel();
    engine
        .pending
        .lock()
        .map_err(|_| "Runtime response lock failed")?
        .insert(id.clone(), tx);
    let message = json!({"v":1,"id":id,"method":method,"params":params}).to_string() + "\n";
    let sent = engine
        .input
        .lock()
        .map_err(|_| "Runtime input lock failed")?
        .write_all(message.as_bytes());
    if let Err(error) = sent {
        if let Ok(mut map) = engine.pending.lock() {
            map.remove(&id);
        }
        return Err(format!("Could not send to runtime: {error}"));
    }
    let result = rx
        .recv_timeout(Duration::from_secs(900))
        .map_err(|_| "The runtime did not respond. Restart the application.")?;
    if let Ok(mut map) = engine.pending.lock() {
        map.remove(&id);
    }
    if method == "preview" {
        if let Ok(Value::String(path)) = &result {
            let _ = app.asset_protocol_scope().allow_file(path);
            if let Ok(path) = Path::new(path).canonicalize() {
                if let Ok(mut previews) = state.approved_previews.lock() {
                    previews.insert(path);
                }
            }
        }
    }
    result
}

#[tauri::command]
async fn engine_request(app: tauri::AppHandle, method: String, params: Value) -> Reply {
    tauri::async_runtime::spawn_blocking(move || request_engine(app, method, params))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
fn frontend_log(message: String) {
    log::warn!("ui: {}", message.chars().take(4000).collect::<String>());
}

#[tauri::command]
fn restart_application(app: tauri::AppHandle) {
    app.restart();
}

#[tauri::command]
async fn restart_runtime(app: tauri::AppHandle) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        stop_engine(&app.state::<AppState>());
    })
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
fn audio_url(app: tauri::AppHandle, path: String) -> Result<String, String> {
    let state = app.state::<AppState>();
    let path = Path::new(&path).canonicalize().map_err(|e| e.to_string())?;
    if !state
        .approved_previews
        .lock()
        .map_err(|_| "Audio authorization lock failed")?
        .contains(&path)
    {
        return Err("Audio preview has not been prepared by this application.".into());
    }
    let mut guard = state.media.lock().map_err(|_| "Audio server lock failed")?;
    if guard.is_none() {
        *guard = Some(media::MediaServer::start()?);
    }
    guard.as_ref().ok_or("Audio server unavailable")?.url(&path)
}

#[tauri::command]
async fn choose_audio(app: tauri::AppHandle) -> Result<Vec<String>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let files = app
            .dialog()
            .file()
            .add_filter(
                "Audio",
                &[
                    "wav", "flac", "mp3", "m4a", "aac", "ogg", "opus", "aiff", "wma", "mp4",
                ],
            )
            .blocking_pick_files();
        let mut paths = Vec::new();
        for file in files.unwrap_or_default() {
            let path = file.into_path().map_err(|e| e.to_string())?;
            app.asset_protocol_scope()
                .allow_file(&path)
                .map_err(|e| e.to_string())?;
            paths.push(path.to_string_lossy().into_owned());
        }
        Ok(paths)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn choose_folder(app: tauri::AppHandle) -> Result<Option<String>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        app.dialog()
            .file()
            .blocking_pick_folder()
            .map(|f| {
                f.into_path()
                    .map(|p| p.to_string_lossy().into_owned())
                    .map_err(|e| e.to_string())
            })
            .transpose()
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
fn reveal_path(app: tauri::AppHandle, path: String) -> Result<(), String> {
    if !Path::new(&path).exists() {
        return Err("This file was moved or deleted.".into());
    }
    app.opener()
        .reveal_item_in_dir(path)
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn export_preset(app: tauri::AppHandle, preset: Value) -> Result<bool, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let Some(file) = app
            .dialog()
            .file()
            .set_file_name("separator-preset.json")
            .add_filter("Preset", &["json"])
            .blocking_save_file()
        else {
            return Ok(false);
        };
        let path = file.into_path().map_err(|e| e.to_string())?;
        std::fs::write(
            path,
            serde_json::to_string_pretty(&preset).map_err(|e| e.to_string())?,
        )
        .map_err(|e| e.to_string())?;
        Ok(true)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn import_preset(app: tauri::AppHandle) -> Result<Option<Value>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let Some(file) = app
            .dialog()
            .file()
            .add_filter("Preset", &["json"])
            .blocking_pick_file()
        else {
            return Ok(None);
        };
        let path = file.into_path().map_err(|e| e.to_string())?;
        if std::fs::metadata(&path).map_err(|e| e.to_string())?.len() > 1_000_000 {
            return Err("Preset file is too large.".into());
        }
        serde_json::from_str(&std::fs::read_to_string(path).map_err(|e| e.to_string())?)
            .map(Some)
            .map_err(|e| e.to_string())
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn export_audio(app: tauri::AppHandle, paths: Vec<String>) -> Result<Option<String>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let Some(folder) = app.dialog().file().blocking_pick_folder() else {
            return Ok(None);
        };
        let folder = folder.into_path().map_err(|e| e.to_string())?;
        for path in paths {
            let src = Path::new(&path);
            let filename = src.file_name().ok_or("Invalid output filename")?;
            let dest = folder.join(filename);
            let mut input = std::fs::File::open(src).map_err(|e| e.to_string())?;
            let mut output = std::fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&dest)
                .map_err(|e| {
                    format!(
                        "Could not export without overwriting {}: {e}",
                        dest.display()
                    )
                })?;
            std::io::copy(&mut input, &mut output).map_err(|e| e.to_string())?;
        }
        Ok(Some(folder.to_string_lossy().into_owned()))
    })
    .await
    .map_err(|e| e.to_string())?
}

fn stop_engine(state: &AppState) {
    if let Ok(mut guard) = state.engine.lock() {
        if let Some(engine) = guard.take() {
            if let Ok(mut input) = engine.input.lock() {
                let _ = input.write_all(
                    b"{\"v\":1,\"id\":\"shutdown\",\"method\":\"shutdown\",\"params\":{}}\n",
                );
            }
            if let Ok(mut child) = engine.child.lock() {
                for _ in 0..60 {
                    if child.try_wait().ok().flatten().is_some() {
                        return;
                    }
                    std::thread::sleep(Duration::from_millis(100));
                }
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

pub fn run() {
    // WebKitGTK's DMA-BUF renderer cannot allocate GBM surfaces with some NVIDIA/Wayland drivers.
    // Apply the documented renderer compatibility switch only on that hardware, before GTK starts.
    #[cfg(target_os = "linux")]
    if Path::new("/proc/driver/nvidia/version").exists()
        && std::env::var_os("WEBKIT_DISABLE_DMABUF_RENDERER").is_none()
    {
        std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
    }
    let app = tauri::Builder::default()
        .setup(|app| {
            logs::initialize(&app.path().app_local_data_dir()?.join("logs"))?;
            Ok(())
        })
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            engine_request,
            frontend_log,
            audio_url,
            restart_runtime,
            restart_application,
            choose_audio,
            choose_folder,
            reveal_path,
            export_preset,
            import_preset,
            export_audio
        ])
        .build(tauri::generate_context!());
    match app {
        Ok(app) => app.run(|handle, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                let state = handle.state::<AppState>();
                stop_engine(&state);
                if let Ok(guard) = state.media.lock() {
                    if let Some(media) = guard.as_ref() {
                        media.stop();
                    }
                };
            }
        }),
        Err(error) => eprintln!("Separator could not start: {error}"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn protocol_preserves_unicode_paths() {
        let message = json!({"v":1,"id":"test","method":"inspect_audio","params":{"path":"C:/音楽/🎵 café.wav"}});
        let parsed: Value = serde_json::from_str(&message.to_string()).expect("valid JSON fixture");
        assert_eq!(parsed["params"]["path"], "C:/音楽/🎵 café.wav");
    }
}
