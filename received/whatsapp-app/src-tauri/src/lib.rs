mod supabase;
mod whatsapp;

use tauri::{Emitter, Manager, WindowEvent};

fn load_env() {
    // 1. Try current working directory (.env)
    let _ = dotenvy::dotenv();

    // 2. Try next to the executable
    if std::env::var("SUPABASE_URL").is_err() {
        if let Ok(exe_path) = std::env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                let env_path = exe_dir.join(".env");
                let _ = dotenvy::from_path(&env_path);
            }
        }
    }

    // 3. Try the cargo manifest directory (development)
    if std::env::var("SUPABASE_URL").is_err() {
        let manifest = std::env!("CARGO_MANIFEST_DIR");
        let parent_env = std::path::Path::new(manifest).parent().unwrap().join(".env");
        let _ = dotenvy::from_path(&parent_env);
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            whatsapp::whatsapp_connect,
            whatsapp::whatsapp_disconnect,
            whatsapp::whatsapp_send_message,
            whatsapp::whatsapp_send_file,
            whatsapp::whatsapp_send_audio,
            whatsapp::whatsapp_get_chats,
            whatsapp::whatsapp_get_messages,
            whatsapp::whatsapp_get_status,
            whatsapp::whatsapp_mark_read,
            whatsapp::whatsapp_archive_chat,
            whatsapp::whatsapp_delete_chat,
            whatsapp::whatsapp_pin_chat,
            whatsapp::whatsapp_mute_chat,
            supabase::supabase_login,
            supabase::supabase_restore_session,
            supabase::supabase_logout,
            supabase::supabase_get_staff_assignments,
            supabase::supabase_get_user,
            supabase::supabase_get_clients,
            supabase::supabase_update_connection_status,
        ])
        .setup(|app| {
            load_env();

            let window = app.get_webview_window("main").unwrap();
            let _ = window.emit("app:config", serde_json::json!({
                "supabaseUrl": std::env::var("SUPABASE_URL").unwrap_or_default(),
                "supabaseKey": std::env::var("SUPABASE_ANON_KEY").unwrap_or_default(),
            }));

            // Keep sidecar alive when window is minimized or loses focus
            let app_handle = app.handle().clone();
            let w = window.clone();
            window.on_window_event(move |event| {
                match event {
                    WindowEvent::CloseRequested { api, .. } => {
                        // Hide window instead of closing - keeps sidecar alive
                        api.prevent_close();
                        let _ = w.hide();
                    }
                    WindowEvent::Focused(focused) => {
                        if *focused {
                            // Window regained focus - emit a wake event so frontend can re-sync
                            let _ = app_handle.emit("app:focus", ());
                        }
                    }
                    _ => {}
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
