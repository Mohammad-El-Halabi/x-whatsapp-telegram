use crate::contacts;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_notification::NotificationExt;

struct TelegramProcess {
    child: Child,
    stdin: ChildStdin,
    stop: Arc<AtomicBool>,
}

static PROCESSES: OnceLock<Mutex<HashMap<String, TelegramProcess>>> = OnceLock::new();

fn processes() -> &'static Mutex<HashMap<String, TelegramProcess>> {
    PROCESSES.get_or_init(|| Mutex::new(HashMap::new()))
}

#[derive(Debug, Deserialize)]
struct TelegramEvent {
    event: String,
    data: serde_json::Value,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct RoutedEvent {
    platform: String,
    slot_id: String,
    event: String,
    data: serde_json::Value,
}

enum SidecarKind {
    Executable(PathBuf),
    Python(PathBuf),
}

fn find_sidecar(app: &AppHandle) -> Option<SidecarKind> {
    if let Ok(configured) = std::env::var("TELEGRAM_SIDECAR_PATH") {
        let path = PathBuf::from(configured);
        if path.exists() {
            return Some(if path.extension().and_then(|value| value.to_str()) == Some("py") {
                SidecarKind::Python(path)
            } else {
                SidecarKind::Executable(path)
            });
        }
    }
    if let Ok(resource_dir) = app.path().resource_dir() {
        for candidate in [
            resource_dir.join("telegram-sidecar").join("telegram-sidecar.exe"),
            resource_dir.join("telegram-sidecar").join("telegram-sidecar"),
        ] {
            if candidate.exists() {
                return Some(SidecarKind::Executable(candidate));
            }
        }
    }
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    let source = manifest
        .parent()
        .unwrap_or(manifest)
        .join("telegram-sidecar")
        .join("main.py");
    source.exists().then_some(SidecarKind::Python(source))
}

fn stop_slot(slot_id: &str) -> Result<(), String> {
    let mut guard = processes()
        .lock()
        .map_err(|_| "Telegram process state is unavailable".to_string())?;
    if let Some(mut process) = guard.remove(slot_id) {
        process.stop.store(true, Ordering::SeqCst);
        let _ = writeln!(process.stdin, "{}", serde_json::json!({"action": "disconnect"}));
        let _ = process.stdin.flush();
        let _ = process.child.kill();
        let _ = process.child.wait();
    }
    contacts::clear_slot("telegram", slot_id);
    Ok(())
}

pub fn shutdown() {
    let slots: Vec<String> = processes()
        .lock()
        .map(|guard| guard.keys().cloned().collect())
        .unwrap_or_default();
    for slot in slots {
        let _ = stop_slot(&slot);
    }
}

fn sanitize_message(slot_id: &str, value: &serde_json::Value) -> Option<serde_json::Value> {
    let raw_id = value.get("chatId").and_then(|item| item.as_str())?;
    let contact = contacts::match_identifier("telegram", slot_id, raw_id)?;
    Some(serde_json::json!({
        "id": value.get("id").cloned().unwrap_or_else(|| serde_json::json!("")),
        "clientId": contact.id,
        "clientName": contact.name,
        "body": value.get("body").cloned().unwrap_or_else(|| serde_json::json!("")),
        "timestamp": value.get("timestamp").cloned().unwrap_or_else(|| serde_json::json!(0)),
        "fromMe": value.get("fromMe").cloned().unwrap_or_else(|| serde_json::json!(false)),
        "hasMedia": value.get("hasMedia").cloned().unwrap_or_else(|| serde_json::json!(false)),
        "mediaType": value.get("mediaType").cloned().unwrap_or(serde_json::Value::Null)
    }))
}

fn sanitize_event(slot_id: &str, event: TelegramEvent) -> Option<RoutedEvent> {
    let data = match event.event.as_str() {
        "new-message" | "message-sent" => sanitize_message(slot_id, &event.data)?,
        "messages" => serde_json::json!(
            event
                .data
                .as_array()
                .into_iter()
                .flatten()
                .filter_map(|message| sanitize_message(slot_id, message))
                .collect::<Vec<_>>()
        ),
        "ready" => serde_json::json!({"name": "Telegram"}),
        "qr" => serde_json::json!({
            "qrValue": event.data.get("qrValue").and_then(|value| value.as_str()).unwrap_or_default()
        }),
        "password-required" => serde_json::json!({}),
        "error" => serde_json::json!({
            "message": event.data.get("message").and_then(|value| value.as_str()).unwrap_or("Telegram action failed")
        }),
        _ => return None,
    };
    Some(RoutedEvent {
        platform: "telegram".to_string(),
        slot_id: slot_id.to_string(),
        event: event.event,
        data,
    })
}

fn send_command(slot_id: &str, action: &str, data: serde_json::Value) -> Result<(), String> {
    let mut guard = processes()
        .lock()
        .map_err(|_| "Telegram process state is unavailable".to_string())?;
    let process = guard
        .get_mut(slot_id)
        .ok_or_else(|| "Telegram is not connected".to_string())?;
    let command = serde_json::json!({"action": action, "data": data});
    writeln!(process.stdin, "{}", command)
        .and_then(|_| process.stdin.flush())
        .map_err(|_| "Telegram runtime is unavailable".to_string())
}

#[tauri::command]
pub async fn telegram_connect(
    app: AppHandle,
    slot_id: String,
    assignment_id: String,
) -> Result<(), String> {
    stop_slot(&slot_id)?;
    let sidecar = find_sidecar(&app)
        .ok_or_else(|| "The Telegram runtime was not found".to_string())?;
    let session_dir = app
        .path()
        .app_data_dir()
        .map_err(|_| "The Telegram session directory is unavailable".to_string())?
        .join("telegram-sessions");
    std::fs::create_dir_all(&session_dir)
        .map_err(|_| "The Telegram session directory could not be created".to_string())?;
    let session_path = session_dir.join(format!("tg_{}", assignment_id));

    let mut command = match sidecar {
        SidecarKind::Executable(path) => Command::new(path),
        SidecarKind::Python(path) => {
            let python = std::env::var("PYTHON_PATH").unwrap_or_else(|_| "python".to_string());
            let mut command = Command::new(python);
            command.arg(path);
            command
        }
    };
    let mut child = command
        .arg(session_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "Could not start the Telegram runtime".to_string())?;
    let stdin = child.stdin.take().ok_or("Could not open Telegram input")?;
    let stdout = child.stdout.take().ok_or("Could not open Telegram output")?;
    let stop = Arc::new(AtomicBool::new(false));
    processes()
        .lock()
        .map_err(|_| "Telegram process state is unavailable".to_string())?
        .insert(slot_id.clone(), TelegramProcess { child, stdin, stop: stop.clone() });

    let reader_slot = slot_id.clone();
    let app_handle = app.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            if stop.load(Ordering::SeqCst) {
                break;
            }
            let Ok(line) = line else { break };
            let Ok(raw) = serde_json::from_str::<TelegramEvent>(&line) else { continue };
            let Some(event) = sanitize_event(&reader_slot, raw) else { continue };
            if event.event == "new-message"
                && !event.data.get("fromMe").and_then(|value| value.as_bool()).unwrap_or(false)
            {
                let name = event.data.get("clientName").and_then(|value| value.as_str()).unwrap_or("Approved client");
                let body = event.data.get("body").and_then(|value| value.as_str()).filter(|value| !value.is_empty()).unwrap_or("New message");
                let preview: String = body.chars().take(80).collect();
                let _ = app_handle.notification().builder().title("Telegram").body(format!("{}: {}", name, preview)).show();
            }
            let _ = app_handle.emit("platform:event", event);
        }
    });
    Ok(())
}

#[tauri::command]
pub fn telegram_submit_password(slot_id: String, password: String) -> Result<(), String> {
    send_command(&slot_id, "submitPassword", serde_json::json!({"password": password}))
}

#[tauri::command]
pub fn telegram_disconnect(slot_id: String) -> Result<(), String> {
    stop_slot(&slot_id)
}

#[tauri::command]
pub fn telegram_disconnect_all() -> Result<(), String> {
    shutdown();
    Ok(())
}

#[tauri::command]
pub fn telegram_send_message(slot_id: String, client_id: String, message: String) -> Result<(), String> {
    let contact = contacts::resolve("telegram", &slot_id, &client_id)
        .ok_or_else(|| "This contact is not approved for this Telegram account".to_string())?;
    send_command(&slot_id, "sendMessage", serde_json::json!({"chatId": contact.identifier, "message": message}))
}

#[tauri::command]
pub fn telegram_send_file(
    slot_id: String,
    client_id: String,
    file_path: String,
    caption: Option<String>,
) -> Result<(), String> {
    let contact = contacts::resolve("telegram", &slot_id, &client_id)
        .ok_or_else(|| "This contact is not approved for this Telegram account".to_string())?;
    send_command(&slot_id, "sendFile", serde_json::json!({
        "chatId": contact.identifier,
        "filePath": file_path,
        "caption": caption.unwrap_or_default()
    }))
}

#[tauri::command]
pub fn telegram_get_messages(slot_id: String, client_id: String) -> Result<(), String> {
    let contact = contacts::resolve("telegram", &slot_id, &client_id)
        .ok_or_else(|| "This contact is not approved for this Telegram account".to_string())?;
    send_command(&slot_id, "getMessages", serde_json::json!({"chatId": contact.identifier}))
}

#[tauri::command]
pub fn telegram_mark_read(slot_id: String, client_id: String) -> Result<(), String> {
    let contact = contacts::resolve("telegram", &slot_id, &client_id)
        .ok_or_else(|| "This contact is not approved for this Telegram account".to_string())?;
    send_command(&slot_id, "markRead", serde_json::json!({"chatId": contact.identifier}))
}
