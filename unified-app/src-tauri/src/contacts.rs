use serde::Serialize;
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SafeContact {
    pub id: String,
    pub name: String,
}

#[derive(Clone, Debug)]
pub struct AllowedContact {
    pub id: String,
    pub name: String,
    pub identifier: String,
}

type SlotContacts = HashMap<String, AllowedContact>;
type AllowlistStore = HashMap<String, SlotContacts>;

static ALLOWLISTS: OnceLock<Mutex<AllowlistStore>> = OnceLock::new();

fn store() -> &'static Mutex<AllowlistStore> {
    ALLOWLISTS.get_or_init(|| Mutex::new(HashMap::new()))
}

fn key(platform: &str, slot_id: &str) -> String {
    format!("{}:{}", platform.to_ascii_lowercase(), slot_id)
}

fn normalize_identifier(value: &str) -> String {
    let digits: String = value.chars().filter(|c| c.is_ascii_digit()).collect();
    if digits.len() >= 7 {
        digits
    } else {
        value
            .trim()
            .trim_start_matches('+')
            .split('@')
            .next()
            .unwrap_or(value)
            .to_ascii_lowercase()
    }
}

fn identifiers_match(left: &str, right: &str) -> bool {
    let a = normalize_identifier(left);
    let b = normalize_identifier(right);
    if a.is_empty() || b.is_empty() {
        return false;
    }
    a == b || (a.len() >= 7 && b.len() >= 7 && (a.ends_with(&b) || b.ends_with(&a)))
}

pub fn replace(platform: &str, slot_id: &str, contacts: Vec<AllowedContact>) {
    let mut by_id = HashMap::new();
    for contact in contacts {
        by_id.insert(contact.id.clone(), contact);
    }
    if let Ok(mut guard) = store().lock() {
        guard.insert(key(platform, slot_id), by_id);
    }
}

pub fn clear_slot(platform: &str, slot_id: &str) {
    if let Ok(mut guard) = store().lock() {
        guard.remove(&key(platform, slot_id));
    }
}

pub fn resolve(platform: &str, slot_id: &str, client_id: &str) -> Option<AllowedContact> {
    store()
        .lock()
        .ok()
        .and_then(|guard| guard.get(&key(platform, slot_id)).cloned())
        .and_then(|contacts| contacts.get(client_id).cloned())
}

pub fn match_identifier(platform: &str, slot_id: &str, raw: &str) -> Option<AllowedContact> {
    let contacts = store()
        .lock()
        .ok()
        .and_then(|guard| guard.get(&key(platform, slot_id)).cloned())?;

    contacts
        .values()
        .find(|contact| identifiers_match(&contact.identifier, raw))
        .cloned()
}

pub fn safe_contacts(platform: &str, slot_id: &str) -> Vec<SafeContact> {
    let mut contacts: Vec<SafeContact> = store()
        .lock()
        .ok()
        .and_then(|guard| guard.get(&key(platform, slot_id)).cloned())
        .unwrap_or_default()
        .values()
        .map(|contact| SafeContact {
            id: contact.id.clone(),
            name: contact.name.clone(),
        })
        .collect();
    contacts.sort_by(|a, b| a.name.to_ascii_lowercase().cmp(&b.name.to_ascii_lowercase()));
    contacts
}

