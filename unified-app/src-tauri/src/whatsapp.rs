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

struct SidecarProcess {
    child: Child,
    stdin: ChildStdin,
    stop: Arc<AtomicBool>,
}

static PROCESSES: OnceLock<Mutex<HashMap<String, SidecarProcess>>> = OnceLock::new();

fn processes() -> &'static Mutex<HashMap<String, SidecarProcess>> {
    PROCESSES.get_or_init(|| Mutex::new(HashMap::new()))
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct WhatsAppEvent {
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

fn find_sidecar_dir(app: &AppHandle) -> Option<PathBuf> {
    if let Ok(resource_dir) = app.path().resource_dir() {
        for candidate in [
            resource_dir.join("sidecar"),
            resource_dir.join("_up_").join("sidecar"),
        ] {
            if candidate.join("index.js").exists() {
                return Some(candidate);
            }
        }
    }

    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let candidate = exe_dir.join("sidecar");
            if candidate.join("index.js").exists() {
                return Some(candidate);
            }
        }
    }

    let manifest = std::env!("CARGO_MANIFEST_DIR");
    let candidate = Path::new(manifest)
        .parent()
        .unwrap_or_else(|| Path::new(manifest))
        .join("sidecar");
    if candidate.join("index.js").exists() {
        return Some(candidate);
    }

    std::env::current_dir()
        .ok()
        .map(|cwd| cwd.join("sidecar"))
        .filter(|candidate| candidate.join("index.js").exists())
}

fn ensure_node_modules(sidecar_dir: &Path) -> Result<(), String> {
    if sidecar_dir.join("node_modules").exists() {
        return Ok(());
    }
    let status = Command::new("npm")
        .args(["ci", "--ignore-scripts", "--omit=dev", "--no-audit", "--no-fund"])
        .current_dir(sidecar_dir)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map_err(|e| format!("Node dependencies are missing and npm could not start: {}", e))?;
    if status.success() {
        Ok(())
    } else {
        Err("Could not install the WhatsApp runtime dependencies".to_string())
    }
}

fn stop_slot(slot_id: &str) -> Result<(), String> {
    let mut guard = processes()
        .lock()
        .map_err(|_| "WhatsApp process state is unavailable".to_string())?;
    if let Some(mut process) = guard.remove(slot_id) {
        process.stop.store(true, Ordering::SeqCst);
        let _ = process.child.kill();
        let _ = process.child.wait();
    }
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

fn matched_contact(slot_id: &str, object: &serde_json::Value) -> Option<contacts::AllowedContact> {
    let from_me = object
        .get("fromMe")
        .and_then(|value| value.as_bool())
        .unwrap_or(false);
    let field = if from_me { "to" } else { "from" };
    let identifier = object.get(field).and_then(|value| value.as_str())?;
    contacts::match_identifier("whatsapp", slot_id, identifier)
}

fn sanitize_message(slot_id: &str, value: &serde_json::Value) -> Option<serde_json::Value> {
    let contact = matched_contact(slot_id, value)?;
    let mut safe = value.clone();
    if let Some(object) = safe.as_object_mut() {
        object.remove("from");
        object.remove("to");
        object.remove("fromName");
        object.insert("clientId".to_string(), serde_json::json!(contact.id));
        object.insert("clientName".to_string(), serde_json::json!(contact.name));
    }
    Some(safe)
}

fn sanitize_event(slot_id: &str, event: WhatsAppEvent) -> Option<RoutedEvent> {
    let data = match event.event.as_str() {
        "new-message" | "message-sent" => sanitize_message(slot_id, &event.data)?,
        "messages" => {
            let safe: Vec<serde_json::Value> = event
                .data
                .as_array()
                .into_iter()
                .flatten()
                .filter_map(|message| sanitize_message(slot_id, message))
                .collect();
            serde_json::json!(safe)
        }
        "chats" => {
            let mut safe_chats = Vec::new();
            for chat in event.data.as_array().into_iter().flatten() {
                let raw_id = chat.get("id").and_then(|value| value.as_str()).unwrap_or_default();
                let Some(contact) = contacts::match_identifier("whatsapp", slot_id, raw_id) else {
                    continue;
                };
                safe_chats.push(serde_json::json!({
                    "id": contact.id,
                    "name": contact.name,
                    "unreadCount": chat.get("unreadCount").cloned().unwrap_or(serde_json::json!(0)),
                    "lastMessage": chat.get("lastMessage").cloned().unwrap_or(serde_json::Value::Null),
                    "pinned": chat.get("pinned").cloned().unwrap_or(serde_json::json!(false)),
                    "archived": chat.get("archived").cloned().unwrap_or(serde_json::json!(false)),
                    "isMuted": chat.get("isMuted").cloned().unwrap_or(serde_json::json!(false))
                }));
            }
            serde_json::json!(safe_chats)
        }
        "ready" => serde_json::json!({
            "name": event.data.get("name").and_then(|value| value.as_str()).unwrap_or("WhatsApp")
        }),
        "error" => serde_json::json!({"message": "WhatsApp action failed"}),
        "disconnected" | "authenticated" => serde_json::json!({}),
        "debug" => return None,
        _ => event.data,
    };

    Some(RoutedEvent {
        platform: "whatsapp".to_string(),
        slot_id: slot_id.to_string(),
        event: event.event,
        data,
    })
}

#[tauri::command]
pub async fn whatsapp_connect(
    app: AppHandle,
    slot_id: String,
    assignment_id: String,
    gateway_number: String,
) -> Result<(), String> {
    stop_slot(&slot_id)?;
    let sidecar_dir = find_sidecar_dir(&app)
        .ok_or_else(|| "The WhatsApp sidecar directory was not found".to_string())?;
    ensure_node_modules(&sidecar_dir)?;

    let mut child = Command::new("node")
        .arg(sidecar_dir.join("index.js"))
        .args(["connect", &assignment_id, &gateway_number])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Could not start the WhatsApp runtime: {}", e))?;

    let stdin = child.stdin.take().ok_or("Could not open WhatsApp input")?;
    let stdout = child.stdout.take().ok_or("Could not open WhatsApp output")?;
    let stderr = child.stderr.take();
    let stop = Arc::new(AtomicBool::new(false));

    processes()
        .lock()
        .map_err(|_| "WhatsApp process state is unavailable".to_string())?
        .insert(
            slot_id.clone(),
            SidecarProcess {
                child,
                stdin,
                stop: stop.clone(),
            },
        );

    let app_handle = app.clone();
    let reader_slot = slot_id.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            if stop.load(Ordering::SeqCst) {
                break;
            }
            let Ok(line) = line else { break };
            let Ok(raw_event) = serde_json::from_str::<WhatsAppEvent>(line.trim()) else {
                continue;
            };
            let Some(event) = sanitize_event(&reader_slot, raw_event) else {
                continue;
            };
            if event.event == "new-message" {
                let name = event
                    .data
                    .get("clientName")
                    .and_then(|value| value.as_str())
                    .unwrap_or("Approved client");
                let body = event
                    .data
                    .get("body")
                    .and_then(|value| value.as_str())
                    .filter(|value| !value.is_empty())
                    .unwrap_or("New message");
                let preview: String = body.chars().take(80).collect();
                let _ = app_handle
                    .notification()
                    .builder()
                    .title("WhatsApp")
                    .body(format!("{}: {}", name, preview))
                    .show();
            }
            let _ = app_handle.emit("platform:event", event);
        }
    });

    if let Some(stderr) = stderr {
        std::thread::spawn(move || {
            for line in BufReader::new(stderr).lines() {
                if line.is_err() {
                    break;
                }
            }
        });
    }

    Ok(())
}

#[tauri::command]
pub async fn whatsapp_disconnect(slot_id: String) -> Result<(), String> {
    stop_slot(&slot_id)
}

#[tauri::command]
pub async fn whatsapp_disconnect_all() -> Result<(), String> {
    let slots: Vec<String> = processes()
        .lock()
        .map_err(|_| "WhatsApp process state is unavailable".to_string())?
        .keys()
        .cloned()
        .collect();
    for slot in slots {
        stop_slot(&slot)?;
    }
    Ok(())
}

fn send_to_sidecar(slot_id: &str, action: &str, data: serde_json::Value) -> Result<(), String> {
    let mut guard = processes()
        .lock()
        .map_err(|_| "WhatsApp process state is unavailable".to_string())?;
    let process = guard
        .get_mut(slot_id)
        .ok_or_else(|| "This WhatsApp account is not running".to_string())?;
    let mut bytes = serde_json::to_vec(&serde_json::json!({
        "action": action,
        "data": data
    }))
    .map_err(|e| e.to_string())?;
    bytes.push(b'\n');
    process.stdin.write_all(&bytes).map_err(|e| e.to_string())?;
    process.stdin.flush().map_err(|e| e.to_string())
}

fn resolve_client(slot_id: &str, client_id: &str) -> Result<String, String> {
    contacts::resolve("whatsapp", slot_id, client_id)
        .map(|contact| contact.identifier)
        .ok_or_else(|| "This contact is not approved for this WhatsApp account".to_string())
}

#[tauri::command]
pub async fn whatsapp_send_message(
    slot_id: String,
    client_id: String,
    message: String,
) -> Result<(), String> {
    let number = resolve_client(&slot_id, &client_id)?;
    send_to_sidecar(
        &slot_id,
        "send-message",
        serde_json::json!({ "number": number, "message": message }),
    )
}

#[tauri::command]
pub async fn whatsapp_send_file(
    slot_id: String,
    client_id: String,
    file_path: String,
    caption: Option<String>,
) -> Result<(), String> {
    let number = resolve_client(&slot_id, &client_id)?;
    send_to_sidecar(
        &slot_id,
        "send-file",
        serde_json::json!({ "number": number, "filePath": file_path, "caption": caption }),
    )
}

#[tauri::command]
pub async fn whatsapp_send_audio(
    slot_id: String,
    client_id: String,
    base64: String,
    mime_type: Option<String>,
) -> Result<(), String> {
    let number = resolve_client(&slot_id, &client_id)?;
    send_to_sidecar(
        &slot_id,
        "send-audio",
        serde_json::json!({
            "number": number,
            "base64": base64,
            "mimeType": mime_type.unwrap_or_else(|| "audio/webm;codecs=opus".to_string())
        }),
    )
}

#[tauri::command]
pub async fn whatsapp_get_chats(slot_id: String) -> Result<(), String> {
    send_to_sidecar(&slot_id, "get-chats", serde_json::json!({}))
}

#[tauri::command]
pub async fn whatsapp_get_messages(slot_id: String, client_id: String) -> Result<(), String> {
    let chat_id = resolve_client(&slot_id, &client_id)?;
    send_to_sidecar(
        &slot_id,
        "get-messages",
        serde_json::json!({ "chatId": chat_id }),
    )
}

#[tauri::command]
pub async fn whatsapp_get_status(slot_id: String, client_id: String) -> Result<(), String> {
    let number = resolve_client(&slot_id, &client_id)?;
    send_to_sidecar(
        &slot_id,
        "get-status",
        serde_json::json!({ "number": number }),
    )
}

#[tauri::command]
pub async fn whatsapp_mark_read(slot_id: String, client_id: String) -> Result<(), String> {
    let chat_id = resolve_client(&slot_id, &client_id)?;
    send_to_sidecar(
        &slot_id,
        "mark-read",
        serde_json::json!({ "chatId": chat_id }),
    )
}

fn chat_action(slot_id: &str, client_id: &str, action: &str) -> Result<(), String> {
    let chat_id = resolve_client(slot_id, client_id)?;
    send_to_sidecar(slot_id, action, serde_json::json!({ "chatId": chat_id }))
}

#[tauri::command]
pub async fn whatsapp_archive_chat(slot_id: String, client_id: String) -> Result<(), String> {
    chat_action(&slot_id, &client_id, "archive-chat")
}

#[tauri::command]
pub async fn whatsapp_delete_chat(slot_id: String, client_id: String) -> Result<(), String> {
    chat_action(&slot_id, &client_id, "delete-chat")
}

#[tauri::command]
pub async fn whatsapp_pin_chat(slot_id: String, client_id: String) -> Result<(), String> {
    chat_action(&slot_id, &client_id, "pin-chat")
}

#[tauri::command]
pub async fn whatsapp_mute_chat(slot_id: String, client_id: String) -> Result<(), String> {
    chat_action(&slot_id, &client_id, "mute-chat")
}
