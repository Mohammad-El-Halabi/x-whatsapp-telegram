use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::command;

static HTTP_CLIENT: Mutex<Option<Client>> = Mutex::new(None);
static AUTH_TOKEN: Mutex<Option<String>> = Mutex::new(None);

fn get_client() -> Result<Client, String> {
    let mut guard = HTTP_CLIENT.lock().map_err(|e: std::sync::PoisonError<_>| e.to_string())?;
    if guard.is_none() {
        *guard = Some(Client::new());
    }
    Ok(guard.as_ref().unwrap().clone())
}

fn get_token() -> Option<String> {
    AUTH_TOKEN.lock().ok().and_then(|g| g.clone())
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
    let url = std::env::var("SUPABASE_URL").unwrap_or_default();
    let key = std::env::var("SUPABASE_ANON_KEY").unwrap_or_default();

    if url.is_empty() || key.is_empty() {
        return Ok(LoginResult {
            user: None,
            session: None,
            error: Some("Supabase not configured".to_string()),
            token: None,
        });
    }

    let client = get_client()?;
    let auth_url = format!("{}/auth/v1/token?grant_type=password", url);

    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert("apikey", key.parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);
    headers.insert("Content-Type", "application/json".parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);

    let body = serde_json::json!({ "email": email, "password": password });

    let resp = client
        .post(&auth_url)
        .headers(headers)
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    let status = resp.status();
    let text = resp.text().await.map_err(|e| e.to_string())?;

    if !status.is_success() {
        let parsed: serde_json::Value = serde_json::from_str(&text).unwrap_or_default();
        let msg = parsed["error_description"]
            .as_str()
            .or_else(|| parsed["msg"].as_str())
            .unwrap_or("Login failed");
        return Ok(LoginResult {
            user: None,
            session: None,
            error: Some(msg.to_string()),
            token: None,
        });
    }

    let parsed: serde_json::Value = serde_json::from_str(&text).map_err(|e| e.to_string())?;
    let access_token = parsed["access_token"].as_str().map(|s| s.to_string());

    if let Some(ref token) = access_token {
        *AUTH_TOKEN.lock().map_err(|e: std::sync::PoisonError<_>| e.to_string())? = Some(token.clone());
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
    *AUTH_TOKEN.lock().map_err(|e: std::sync::PoisonError<_>| e.to_string())? = Some(token);
    Ok(())
}

#[command]
pub async fn supabase_logout() -> Result<(), String> {
    *AUTH_TOKEN.lock().map_err(|e: std::sync::PoisonError<_>| e.to_string())? = None;
    Ok(())
}

#[command]
pub async fn supabase_get_staff_assignments(user_id: String) -> Result<serde_json::Value, String> {
    let url = std::env::var("SUPABASE_URL").unwrap_or_default();
    let key = std::env::var("SUPABASE_ANON_KEY").unwrap_or_default();
    let token = get_token().ok_or("Not authenticated")?;

    let client = get_client()?;
    let query_url = format!(
        "{}/rest/v1/staff_assignments?user_id=eq.{}&platform=eq.whatsapp&is_active=eq.true&select=*",
        url, user_id
    );

    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert("apikey", key.parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);
    headers.insert("Authorization", format!("Bearer {}", token).parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);
    headers.insert("Prefer", "return=representation".parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);

    let resp = client
        .get(&query_url)
        .headers(headers)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    let status = resp.status();
    let text = resp.text().await.map_err(|e| e.to_string())?;

    if !status.is_success() {
        return Ok(serde_json::json!([]));
    }

    let parsed: serde_json::Value =
        serde_json::from_str(&text).map_err(|e| format!("Parse error: {} - response: {}", e, &text[..200.min(text.len())]))?;

    if parsed.is_array() {
        Ok(parsed)
    } else {
        Ok(serde_json::json!([]))
    }
}

#[command]
pub async fn supabase_get_user(user_id: String) -> Result<serde_json::Value, String> {
    let url = std::env::var("SUPABASE_URL").unwrap_or_default();
    let key = std::env::var("SUPABASE_ANON_KEY").unwrap_or_default();
    let token = get_token().ok_or("Not authenticated")?;

    let client = get_client()?;
    let query_url = format!("{}/rest/v1/users?id=eq.{}&select=*", url, user_id);

    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert("apikey", key.parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);
    headers.insert("Authorization", format!("Bearer {}", token).parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);

    let resp = client
        .get(&query_url)
        .headers(headers)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    let text = resp.text().await.map_err(|e| e.to_string())?;
    let parsed: serde_json::Value = serde_json::from_str(&text).map_err(|e| format!("Parse error: {}", e))?;
    Ok(parsed)
}

#[command]
pub async fn supabase_get_clients(office_id: String) -> Result<serde_json::Value, String> {
    let url = std::env::var("SUPABASE_URL").unwrap_or_default();
    let key = std::env::var("SUPABASE_ANON_KEY").unwrap_or_default();
    let token = get_token().ok_or("Not authenticated")?;

    let client = get_client()?;
    let query_url = format!(
        "{}/rest/v1/clients_secure?office_id=eq.{}&order=created_at.desc&select=*",
        url, office_id
    );

    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert("apikey", key.parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);
    headers.insert("Authorization", format!("Bearer {}", token).parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);
    headers.insert("Prefer", "return=representation".parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);

    let resp = client
        .get(&query_url)
        .headers(headers)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    let status = resp.status();
    let text = resp.text().await.map_err(|e| e.to_string())?;

    if !status.is_success() {
        return Ok(serde_json::json!([]));
    }

    serde_json::from_str(&text).map_err(|e| format!("Parse error: {}", e))
}

#[command]
pub async fn supabase_update_connection_status(
    assignment_id: String,
    status: String,
    connection_data: Option<serde_json::Value>,
) -> Result<(), String> {
    let url = std::env::var("SUPABASE_URL").unwrap_or_default();
    let key = std::env::var("SUPABASE_ANON_KEY").unwrap_or_default();
    let token = get_token().ok_or("Not authenticated")?;

    let client = get_client()?;
    let update_url = format!("{}/rest/v1/staff_assignments?id=eq.{}", url, assignment_id);

    let now = chrono_now();
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

    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert("apikey", key.parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);
    headers.insert("Authorization", format!("Bearer {}", token).parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);
    headers.insert("Content-Type", "application/json".parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);
    headers.insert("Prefer", "return=minimal".parse().map_err(|e: reqwest::header::InvalidHeaderValue| e.to_string())?);

    let _ = client
        .patch(&update_url)
        .headers(headers)
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    Ok(())
}

fn chrono_now() -> String {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64();
    format!("{:.0}", now)
}
