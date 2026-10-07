use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

struct DesktopLogger {
    path: PathBuf,
    file: Mutex<Option<File>>,
}

static LOGGER: OnceLock<DesktopLogger> = OnceLock::new();

impl log::Log for DesktopLogger {
    fn enabled(&self, metadata: &log::Metadata) -> bool {
        metadata.level() <= log::Level::Info
    }

    fn log(&self, record: &log::Record) {
        if !self.enabled(record.metadata()) {
            return;
        }
        let Ok(mut file) = self.file.lock() else {
            return;
        };
        if file
            .as_ref()
            .and_then(|f| f.metadata().ok())
            .is_some_and(|m| m.len() >= 2_000_000)
        {
            *file = None;
            let _ = fs::remove_file(self.path.with_extension("log.3"));
            for index in (1..3).rev() {
                let _ = fs::rename(
                    self.path.with_extension(format!("log.{index}")),
                    self.path.with_extension(format!("log.{}", index + 1)),
                );
            }
            let _ = fs::rename(&self.path, self.path.with_extension("log.1"));
        }
        if file.is_none() {
            *file = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&self.path)
                .ok();
        }
        if let Some(file) = file.as_mut() {
            let timestamp = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs();
            let _ = writeln!(
                file,
                "{timestamp} {} {} {}",
                record.level(),
                record.target(),
                record.args()
            );
        }
    }

    fn flush(&self) {
        if let Ok(mut file) = self.file.lock() {
            if let Some(file) = file.as_mut() {
                let _ = file.flush();
            }
        }
    }
}

pub fn initialize(directory: &Path) -> Result<(), std::io::Error> {
    fs::create_dir_all(directory)?;
    let path = directory.join("desktop.log");
    let file = OpenOptions::new().create(true).append(true).open(&path)?;
    let logger = LOGGER.get_or_init(|| DesktopLogger {
        path,
        file: Mutex::new(Some(file)),
    });
    let _ = log::set_logger(logger);
    log::set_max_level(log::LevelFilter::Info);
    log::info!("Separator desktop started");
    Ok(())
}
