use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter};
use tauri_plugin_notification::NotificationExt;

static SIDECAR_CHILD: Mutex<Option<Child>> = Mutex::new(None);
static STDIN_WRITER: Mutex<Option<std::process::ChildStdin>> = Mutex::new(None);
static READER_STOP: Mutex<Option<Arc<AtomicBool>>> = Mutex::new(None);

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct WhatsAppEvent {
    pub event: String,
    pub data: serde_json::Value,
}

fn find_sidecar_dir() -> Option<PathBuf> {
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let d = exe_dir.join("sidecar");
            if d.join("index.js").exists() {
                return Some(d);
            }
        }
    }

    let manifest = std::env!("CARGO_MANIFEST_DIR");
    let d = std::path::Path::new(manifest).parent().unwrap().join("sidecar");
    if d.join("index.js").exists() {
        return Some(d);
    }

    if let Ok(cwd) = std::env::current_dir() {
        let d = cwd.join("sidecar");
        if d.join("index.js").exists() {
            return Some(d);
        }
    }

    None
}

fn ensure_node_modules(sidecar_dir: &std::path::Path) {
    let nm = sidecar_dir.join("node_modules");
    if nm.exists() {
        return;
    }
    eprintln!("[WHATSAPP] node_modules not found, running npm install in {:?}", sidecar_dir);
    let status = Command::new("npm")
        .arg("install")
        .arg("--production")
        .current_dir(sidecar_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .status();
    match status {
        Ok(s) => eprintln!("[WHATSAPP] npm install finished: {}", s),
        Err(e) => eprintln!("[WHATSAPP] npm install failed: {}", e),
    }
}

fn find_sidecar_command() -> (String, Vec<String>) {
    if let Some(sidecar_dir) = find_sidecar_dir() {
        ensure_node_modules(&sidecar_dir);
        let script = sidecar_dir.join("index.js");
        return (
            "node".to_string(),
            vec![script.to_str().unwrap().to_string()],
        );
    }

    eprintln!("[WHATSAPP] WARNING: sidecar/index.js not found anywhere!");
    ("node".to_string(), vec![])
}

#[tauri::command]
pub async fn whatsapp_connect(
    app: AppHandle,
    assignment_id: String,
    gateway_number: String,
) -> Result<(), String> {
    {
        // Signal old reader thread to stop
        if let Some(stop) = READER_STOP.lock().map_err(|_| "Lock poisoned".to_string())?.take() {
            stop.store(true, Ordering::SeqCst);
        }
        // Clear stdin writer
        let mut writer = STDIN_WRITER.lock().map_err(|_| "Lock poisoned".to_string())?;
        *writer = None;
        // Kill old child and WAIT for it to exit
        let mut child = SIDECAR_CHILD.lock().map_err(|_| "Lock poisoned".to_string())?;
        if let Some(mut c) = child.take() {
            let _ = c.kill();
            let _ = c.wait();
        }
    }

    let (cmd, mut args) = find_sidecar_command();
    args.extend(vec![
        "connect".to_string(),
        assignment_id.clone(),
        gateway_number.clone(),
    ]);

    eprintln!("[WHATSAPP] Spawning sidecar: {} {}", cmd, args.join(" "));

    let mut child = Command::new(&cmd)
        .args(&args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn sidecar ({}): {}", cmd, e))?;

    let stdin = child.stdin.take().ok_or("Failed to open sidecar stdin")?;
    let stdout = child.stdout.take().ok_or("Failed to open sidecar stdout")?;
    let stderr = child.stderr.take();

    {
        let mut writer = STDIN_WRITER.lock().map_err(|_| "Lock poisoned".to_string())?;
        *writer = Some(stdin);
    }
    {
        let mut guard = SIDECAR_CHILD.lock().map_err(|_| "Lock poisoned".to_string())?;
        *guard = Some(child);
    }

    let app_handle = app.clone();
    let stop_flag = Arc::new(AtomicBool::new(false));
    {
        let mut guard = READER_STOP.lock().map_err(|_| "Lock poisoned".to_string())?;
        *guard = Some(stop_flag.clone());
    }

    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            if stop_flag.load(Ordering::SeqCst) {
                eprintln!("[SIDECAR->RUST] Reader stopped by flag");
                break;
            }
            match line {
                Ok(text) => {
                    let trimmed = text.trim().to_string();
                    if trimmed.is_empty() {
                        continue;
                    }
                    match serde_json::from_str::<WhatsAppEvent>(&trimmed) {
                        Ok(msg) => {
                            // Send OS notification directly from Rust for incoming messages and calls
                            // This ensures notifications work even when the webview is backgrounded
                            if msg.event == "new-message" {
                                let from_me = msg.data.get("fromMe").and_then(|v| v.as_bool()).unwrap_or(false);
                                if !from_me {
                                    let body = msg.data.get("body").and_then(|v| v.as_str()).unwrap_or("");
                                    let from_name = msg.data.get("fromName").and_then(|v| v.as_str()).unwrap_or("");
                                    let from = msg.data.get("from").and_then(|v| v.as_str()).unwrap_or("Unknown");
                                    let media_type = msg.data.get("mediaType").and_then(|v| v.as_str());
                                    let display_body = if body.is_empty() {
                                        match media_type {
                                            Some("image") => "Photo",
                                            Some("video") => "Video",
                                            Some("audio") => "Voice message",
                                            Some("document") => "Document",
                                            _ => "New message",
                                        }
                                    } else if body.len() > 80 {
                                        &body[..80]
                                    } else {
                                        body
                                    };
                                    let from_display = if !from_name.is_empty() {
                                        from_name
                                    } else if from.ends_with("@c.us") {
                                        from.split('@').next().unwrap_or(from)
                                    } else {
                                        from
                                    };
                                    let _ = app_handle.notification().builder()
                                        .title("X-WhatsApp")
                                        .body(format!("{}: {}", from_display, display_body))
                                        .show();
                                }
                            }

                            let _ = app_handle.emit("whatsapp:event", msg);
                        }
                        Err(e) => {
                            eprintln!("[SIDECAR->RUST] PARSE ERROR: {} | raw: {}", e, trimmed);
                        }
                    }
                }
                Err(e) => {
                    eprintln!("[SIDECAR->RUST] stdout read error: {}", e);
                    break;
                }
            }
        }
        eprintln!("[SIDECAR->RUST] stdout reader ended");
    });

    if let Some(stderr_pipe) = stderr {
        std::thread::spawn(move || {
            let reader = BufReader::new(stderr_pipe);
            for line in reader.lines() {
                if let Ok(text) = line {
                    eprintln!("[sidecar stderr] {}", text);
                }
            }
        });
    }

    Ok(())
}

#[tauri::command]
pub async fn whatsapp_disconnect() -> Result<(), String> {
    if let Some(stop) = READER_STOP.lock().map_err(|_| "Lock poisoned".to_string())?.take() {
        stop.store(true, Ordering::SeqCst);
    }
    let mut writer = STDIN_WRITER.lock().map_err(|_| "Lock poisoned".to_string())?;
    *writer = None;
    let mut child = SIDECAR_CHILD.lock().map_err(|_| "Lock poisoned".to_string())?;
    if let Some(mut c) = child.take() {
        let _ = c.kill();
        let _ = c.wait();
    }
    Ok(())
}

#[tauri::command]
pub async fn whatsapp_send_message(number: String, message: String) -> Result<(), String> {
    send_to_sidecar("send-message", serde_json::json!({ "number": number, "message": message }))
}

#[tauri::command]
pub async fn whatsapp_send_file(number: String, file_path: String, caption: Option<String>) -> Result<(), String> {
    let mut data = serde_json::json!({ "number": number, "filePath": file_path });
    if let Some(c) = caption {
        data["caption"] = serde_json::json!(c);
    }
    send_to_sidecar("send-file", data)
}

#[tauri::command]
pub async fn whatsapp_send_audio(number: String, base64: String, mime_type: Option<String>) -> Result<(), String> {
    send_to_sidecar("send-audio", serde_json::json!({
        "number": number,
        "base64": base64,
        "mimeType": mime_type.unwrap_or_else(|| "audio/ogg; codecs=opus".to_string())
    }))
}

#[tauri::command]
pub async fn whatsapp_get_chats() -> Result<(), String> {
    send_to_sidecar("get-chats", serde_json::json!({}))
}

#[tauri::command]
pub async fn whatsapp_get_messages(chat_id: String) -> Result<(), String> {
    send_to_sidecar("get-messages", serde_json::json!({ "chatId": chat_id }))
}

#[tauri::command]
pub async fn whatsapp_get_status(number: String) -> Result<(), String> {
    send_to_sidecar("get-status", serde_json::json!({ "number": number }))
}

#[tauri::command]
pub async fn whatsapp_mark_read(chat_id: String) -> Result<(), String> {
    send_to_sidecar("mark-read", serde_json::json!({ "chatId": chat_id }))
}

#[tauri::command]
pub async fn whatsapp_archive_chat(chat_id: String) -> Result<(), String> {
    send_to_sidecar("archive-chat", serde_json::json!({ "chatId": chat_id }))
}

#[tauri::command]
pub async fn whatsapp_delete_chat(chat_id: String) -> Result<(), String> {
    send_to_sidecar("delete-chat", serde_json::json!({ "chatId": chat_id }))
}

#[tauri::command]
pub async fn whatsapp_pin_chat(chat_id: String) -> Result<(), String> {
    send_to_sidecar("pin-chat", serde_json::json!({ "chatId": chat_id }))
}

#[tauri::command]
pub async fn whatsapp_mute_chat(chat_id: String) -> Result<(), String> {
    send_to_sidecar("mute-chat", serde_json::json!({ "chatId": chat_id }))
}

fn send_to_sidecar(action: &str, data: serde_json::Value) -> Result<(), String> {
    let mut writer = STDIN_WRITER.lock().map_err(|_| "Lock poisoned".to_string())?;
    if let Some(ref mut w) = *writer {
        let msg = serde_json::json!({ "action": action, "data": data });
        let mut bytes = serde_json::to_vec(&msg).map_err(|e| e.to_string())?;
        bytes.push(b'\n');
        w.write_all(&bytes).map_err(|e| e.to_string())?;
        w.flush().map_err(|e| e.to_string())?;
        Ok(())
    } else {
        eprintln!("[RUST->SIDECAR] FAILED: Sidecar not running");
        Err("Sidecar not running".to_string())
    }
}
