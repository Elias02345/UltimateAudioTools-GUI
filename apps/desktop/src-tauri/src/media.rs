//! Token-scoped loopback audio streaming for WebKit's custom URI limitation.
use std::collections::HashMap;
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tiny_http::{Header, Method, Response, Server, StatusCode};

pub struct MediaServer {
    server: Arc<Server>,
    files: Mutex<HashMap<String, PathBuf>>,
    token: String,
    port: u16,
    stopped: AtomicBool,
    clients: AtomicUsize,
}

fn range(value: Option<&str>, size: u64) -> Result<(u64, u64, bool), ()> {
    if size == 0 {
        return Err(());
    }
    let Some(value) = value else {
        return Ok((0, size - 1, false));
    };
    let bounds = value.strip_prefix("bytes=").ok_or(())?;
    let (start, end) = bounds.split_once('-').ok_or(())?;
    if start.is_empty() {
        let count: u64 = end.parse().map_err(|_| ())?;
        if count == 0 {
            return Err(());
        }
        return Ok((size.saturating_sub(count), size - 1, true));
    }
    let start: u64 = start.parse().map_err(|_| ())?;
    let end = if end.is_empty() {
        size - 1
    } else {
        end.parse::<u64>().map_err(|_| ())?.min(size - 1)
    };
    if start >= size || end < start {
        return Err(());
    }
    Ok((start, end, true))
}

fn header(name: &str, value: &str) -> Option<Header> {
    Header::from_bytes(name, value).ok()
}

impl MediaServer {
    pub fn start() -> Result<Arc<Self>, String> {
        let server = Arc::new(Server::http(("127.0.0.1", 0)).map_err(|e| e.to_string())?);
        let port = server
            .server_addr()
            .to_ip()
            .ok_or("Audio server address unavailable")?
            .port();
        let media = Arc::new(Self {
            server,
            files: Mutex::new(HashMap::new()),
            token: uuid::Uuid::new_v4().simple().to_string(),
            port,
            stopped: AtomicBool::new(false),
            clients: AtomicUsize::new(0),
        });
        let thread_media = media.clone();
        std::thread::spawn(move || {
            while !thread_media.stopped.load(Ordering::Relaxed) {
                if let Ok(Some(request)) =
                    thread_media.server.recv_timeout(Duration::from_millis(200))
                {
                    if thread_media.clients.fetch_add(1, Ordering::Relaxed) >= 64 {
                        thread_media.clients.fetch_sub(1, Ordering::Relaxed);
                        let _ = request.respond(Response::empty(503));
                        continue;
                    }
                    let current = thread_media.clone();
                    std::thread::spawn(move || {
                        current.respond(request);
                        current.clients.fetch_sub(1, Ordering::Relaxed);
                    });
                }
            }
        });
        Ok(media)
    }

    pub fn url(&self, path: &Path) -> Result<String, String> {
        let mut files = self.files.lock().map_err(|_| "Audio route lock failed")?;
        let id = files
            .iter()
            .find(|(_, candidate)| candidate.as_path() == path)
            .map(|(id, _)| id.clone())
            .unwrap_or_else(|| uuid::Uuid::new_v4().simple().to_string());
        files.insert(id.clone(), path.to_path_buf());
        Ok(format!(
            "http://127.0.0.1:{}/{}/{}",
            self.port, self.token, id
        ))
    }

    fn respond(&self, request: tiny_http::Request) {
        let expected_host = format!("127.0.0.1:{}", self.port);
        let host = request
            .headers()
            .iter()
            .find(|h| h.field.equiv("Host"))
            .map(|h| h.value.as_str());
        if host != Some(expected_host.as_str()) {
            let _ = request.respond(Response::empty(403));
            return;
        }

        if !matches!(request.method(), Method::Get | Method::Head) {
            let _ = request.respond(Response::empty(405));
            return;
        }
        let origin = request
            .headers()
            .iter()
            .find(|h| h.field.equiv("Origin"))
            .map(|h| h.value.as_str());
        if origin.is_some_and(|o| {
            ![
                "tauri://localhost",
                "http://tauri.localhost",
                "https://tauri.localhost",
                "http://localhost:1420",
                "http://127.0.0.1:1420",
            ]
            .contains(&o)
        }) {
            let _ = request.respond(Response::empty(403));
            return;
        }
        let prefix = format!("/{}/", self.token);
        let path = request
            .url()
            .strip_prefix(&prefix)
            .and_then(|id| self.files.lock().ok()?.get(id).cloned());
        let Some(path) = path else {
            let _ = request.respond(Response::empty(404));
            return;
        };
        let Ok(mut file) = File::open(path) else {
            let _ = request.respond(Response::empty(404));
            return;
        };
        let Ok(meta) = file.metadata() else {
            let _ = request.respond(Response::empty(404));
            return;
        };
        let requested = request
            .headers()
            .iter()
            .find(|h| h.field.equiv("Range"))
            .map(|h| h.value.as_str());
        let Ok((start, end, partial)) = range(requested, meta.len()) else {
            let mut response = Response::empty(416);
            if let Some(h) = header("Content-Range", &format!("bytes */{}", meta.len())) {
                response.add_header(h);
            }
            let _ = request.respond(response);
            return;
        };
        if file.seek(SeekFrom::Start(start)).is_err() {
            let _ = request.respond(Response::empty(500));
            return;
        }
        let mut headers = Vec::new();
        for (name, value) in [
            ("Content-Type", "audio/wav"),
            ("Accept-Ranges", "bytes"),
            ("Cache-Control", "private, no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ] {
            if let Some(h) = header(name, value) {
                headers.push(h);
            }
        }
        if let Some(origin) = origin {
            if let Some(h) = header("Access-Control-Allow-Origin", origin) {
                headers.push(h);
            }
        }
        if partial {
            if let Some(h) = header(
                "Content-Range",
                &format!("bytes {}-{}/{}", start, end, meta.len()),
            ) {
                headers.push(h);
            }
        }
        let length = (end - start + 1) as usize;
        let response = Response::new(
            StatusCode(if partial { 206 } else { 200 }),
            headers,
            file.take(length as u64),
            Some(length),
            None,
        )
        .with_chunked_threshold(usize::MAX);
        let _ = request.respond(response);
    }

    pub fn stop(&self) {
        self.stopped.store(true, Ordering::Relaxed);
        self.server.unblock();
    }
}

#[cfg(test)]
mod tests {
    use super::range;
    #[test]
    fn ranges_are_bounded_and_invalid_requests_rejected() {
        assert_eq!(range(None, 100), Ok((0, 99, false)));
        assert_eq!(range(Some("bytes=40-"), 100), Ok((40, 99, true)));
        assert_eq!(range(Some("bytes=-20"), 100), Ok((80, 99, true)));
        assert_eq!(range(Some("bytes=10-999"), 100), Ok((10, 99, true)));
        for bad in [
            "bytes=100-",
            "bytes=50-20",
            "bytes=-0",
            "bytes=1-2,4-5",
            "files=1-2",
        ] {
            assert!(range(Some(bad), 100).is_err());
        }
        assert!(range(None, 0).is_err());
    }
}
