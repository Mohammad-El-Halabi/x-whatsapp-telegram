use crate::contacts::{self, AllowedContact, SafeContact};
use reqwest::header::{HeaderMap, HeaderValue};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::{Mutex, OnceLock};
use tauri::command;

static HTTP_CLIENT: OnceLock<Client> = OnceLock::new();
static AUTH_TOKEN: Mutex<Option<String>> = Mutex::new(None);

fn get_client() -> Client {
    HTTP_CLIENT.get_or_init(Client::new).clone()
}

fn get_token() -> Result<String, String> {
    AUTH_TOKEN
        .lock()
        .map_err(|_| "Authentication state is unavailable".to_string())?
        .clone()
        .ok_or_else(|| "Not authenticated".to_string())
}

fn config() -> Result<(String, String), String> {
    let url = std::env::var("SUPABASE_URL").unwrap_or_default();
    let key = std::env::var("SUPABASE_ANON_KEY")
        .or_else(|_| std::env::var("SUPABASE_KEY"))
        .unwrap_or_default();
    if url.is_empty() || key.is_empty() {
        return Err("Supabase is not configured".to_string());
    }
    Ok((url.trim_end_matches('/').to_string(), key))
}

fn authenticated_headers(key: &str, token: &str) -> Result<HeaderMap, String> {
    let mut headers = HeaderMap::new();
    headers.insert(
        "apikey",
        HeaderValue::from_str(key).map_err(|e| e.to_string())?,
    );
    headers.insert(
        "Authorization",
        HeaderValue::from_str(&format!("Bearer {}", token)).map_err(|e| e.to_string())?,
    );
    headers.insert("Content-Type", HeaderValue::from_static("application/json"));
    Ok(headers)
}

async fn rest_get(path_and_query: &str) -> Result<serde_json::Value, String> {
    let (url, key) = config()?;
    let token = get_token()?;
    let response = get_client()
        .get(format!("{}/rest/v1/{}", url, path_and_query))
        .headers(authenticated_headers(&key, &token)?)
        .send()
        .await
        .map_err(|e| format!("Supabase request failed: {}", e))?;
    let status = response.status();
    let text = response.text().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(format!("Supabase returned {}", status));
    }
    serde_json::from_str(&text).map_err(|e| format!("Invalid Supabase response: {}", e))
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct LoginResult {
    pub user: Option<serde_json::Value>,
    pub session: Option<serde_json::Value>,
    pub error: Option<String>,
    pub token: Option<String>,
}

#[command]
pub async fn supabase_login(email: String, password: String) -> Result<LoginResult, String> {
    let (url, key) = match config() {
        Ok(value) => value,
        Err(message) => {
            return Ok(LoginResult {
                user: None,
                session: None,
                error: Some(message),
                token: None,
            })
        }
    };

    let mut headers = HeaderMap::new();
    headers.insert(
        "apikey",
        HeaderValue::from_str(&key).map_err(|e| e.to_string())?,
    );
    headers.insert("Content-Type", HeaderValue::from_static("application/json"));

    let response = get_client()
        .post(format!("{}/auth/v1/token?grant_type=password", url))
        .headers(headers)
        .json(&serde_json::json!({ "email": email, "password": password }))
        .send()
        .await
        .map_err(|e| format!("Login request failed: {}", e))?;

    let status = response.status();
    let text = response.text().await.map_err(|e| e.to_string())?;
    let parsed: serde_json::Value = serde_json::from_str(&text).unwrap_or_default();

    if !status.is_success() {
        let message = parsed["error_description"]
            .as_str()
            .or_else(|| parsed["msg"].as_str())
            .unwrap_or("Login failed");
        return Ok(LoginResult {
            user: None,
            session: None,
            error: Some(message.to_string()),
            token: None,
        });
    }

    let access_token = parsed["access_token"].as_str().map(str::to_string);
    if let Some(token) = &access_token {
        *AUTH_TOKEN
            .lock()
            .map_err(|_| "Authentication state is unavailable".to_string())? = Some(token.clone());
    }

    Ok(LoginResult {
        user: parsed.get("user").cloned(),
        session: parsed.get("session").cloned(),
        error: None,
        token: access_token,
    })
}

#[command]
pub async fn supabase_restore_session(token: String) -> Result<(), String> {
    *AUTH_TOKEN
        .lock()
        .map_err(|_| "Authentication state is unavailable".to_string())? = Some(token);
    Ok(())
}

#[command]
pub async fn supabase_logout() -> Result<(), String> {
    *AUTH_TOKEN
        .lock()
        .map_err(|_| "Authentication state is unavailable".to_string())? = None;
    Ok(())
}

#[command]
pub async fn supabase_get_staff_assignments(
    user_id: String,
    platform: String,
) -> Result<serde_json::Value, String> {
    let query = format!(
        "staff_assignments?user_id=eq.{}&platform=eq.{}&is_active=eq.true&order=account_slot.asc.nullslast,created_at.asc&select=id,user_id,platform,account_slot,gateway_number,display_name,is_active,connection_status,created_at",
        urlencoding::encode(&user_id),
        urlencoding::encode(&platform.to_ascii_lowercase())
    );
    match rest_get(&query).await {
        Ok(rows) => Ok(rows),
        Err(_) => {
            // Keep older supplied databases usable until the paired-slot migration is applied.
            let legacy_query = format!(
                "staff_assignments?user_id=eq.{}&platform=eq.{}&is_active=eq.true&order=created_at.asc&select=id,user_id,platform,gateway_number,display_name,is_active,connection_status,created_at",
                urlencoding::encode(&user_id),
                urlencoding::encode(&platform.to_ascii_lowercase())
            );
            rest_get(&legacy_query).await
        }
    }
}

#[command]
pub async fn supabase_get_user(user_id: String) -> Result<serde_json::Value, String> {
    rest_get(&format!(
        "users?id=eq.{}&select=*",
        urlencoding::encode(&user_id)
    ))
    .await
}

fn platform_is_enabled(row: &serde_json::Value, platform: &str) -> bool {
    match row.get("platforms").and_then(|value| value.as_array()) {
        Some(platforms) if !platforms.is_empty() => platforms
            .iter()
            .filter_map(|value| value.as_str())
            .any(|value| value.eq_ignore_ascii_case(platform)),
        _ => true,
    }
}

fn gateway_is_enabled(row: &serde_json::Value, gateway_number: &str) -> bool {
    let configured = row
        .get("gateway_number")
        .and_then(|value| value.as_str())
        .unwrap_or("default")
        .trim();
    configured.is_empty()
        || configured.eq_ignore_ascii_case("default")
        || configured == gateway_number.trim()
}

fn platform_identifier(row: &serde_json::Value, platform: &str) -> Option<String> {
    row.get("platform_identifiers")
        .and_then(|value| value.get(platform))
        .and_then(|value| value.as_str())
        .filter(|value| !value.trim().is_empty())
        .or_else(|| row.get("real_identifier").and_then(|value| value.as_str()))
        .map(|value| value.trim().to_string())
}

#[command]
pub async fn supabase_get_allowed_contacts(
    office_id: String,
    platform: String,
    slot_id: String,
    gateway_number: String,
) -> Result<Vec<SafeContact>, String> {
    let platform = platform.to_ascii_lowercase();
    let rows = rest_get(&format!(
        "clients_secure?office_id=eq.{}&order=masked_identity.asc&select=*",
        urlencoding::encode(&office_id)
    ))
    .await?;

    let mut allowed = Vec::new();
    for row in rows.as_array().cloned().unwrap_or_default() {
        if !platform_is_enabled(&row, &platform) || !gateway_is_enabled(&row, &gateway_number) {
            continue;
        }
        let Some(identifier) = platform_identifier(&row, &platform) else {
            continue;
        };
        let id = row
            .get("id")
            .and_then(|value| value.as_str())
            .unwrap_or_default()
            .to_string();
        let name = row
            .get("masked_identity")
            .and_then(|value| value.as_str())
            .or_else(|| row.get("full_name").and_then(|value| value.as_str()))
            .unwrap_or("Approved client")
            .trim()
            .to_string();
        if !id.is_empty() && !name.is_empty() {
            allowed.push(AllowedContact {
                id,
                name,
                identifier,
            });
        }
    }

    contacts::replace(&platform, &slot_id, allowed);
    Ok(contacts::safe_contacts(&platform, &slot_id))
}

#[command]
pub async fn supabase_update_connection_status(
    assignment_id: String,
    status: String,
    connection_data: Option<serde_json::Value>,
) -> Result<(), String> {
    let (url, key) = config()?;
    let token = get_token()?;
    let now = chrono::Utc::now().to_rfc3339();
    let mut body = serde_json::json!({
        "connection_status": status,
        "updated_at": now,
    });
    if status == "connected" {
        body["last_connected_at"] = serde_json::json!(now);
    }
    if let Some(data) = connection_data {
        body["connection_data"] = data;
    }

    let response = get_client()
        .patch(format!(
            "{}/rest/v1/staff_assignments?id=eq.{}",
            url,
            urlencoding::encode(&assignment_id)
        ))
        .headers(authenticated_headers(&key, &token)?)
        .header("Prefer", "return=minimal")
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Status update failed: {}", e))?;
    if !response.status().is_success() {
        return Err(format!("Status update returned {}", response.status()));
    }
    Ok(())
}
