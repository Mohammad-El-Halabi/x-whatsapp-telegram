mod contacts;
mod telegram;
mod supabase;
mod whatsapp;

use tauri::{Emitter, Manager, WindowEvent};

fn load_env() {
    let _ = dotenvy::dotenv();
    if std::env::var("SUPABASE_URL").is_err() {
        if let Ok(exe_path) = std::env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                let _ = dotenvy::from_path(exe_dir.join(".env"));
            }
        }
    }
    if std::env::var("SUPABASE_URL").is_err() {
        let manifest = std::env!("CARGO_MANIFEST_DIR");
        if let Some(project_dir) = std::path::Path::new(manifest).parent() {
            let _ = dotenvy::from_path(project_dir.join(".env"));
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            whatsapp::whatsapp_connect,
            whatsapp::whatsapp_disconnect,
            whatsapp::whatsapp_disconnect_all,
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
            telegram::telegram_connect,
            telegram::telegram_submit_password,
            telegram::telegram_disconnect,
            telegram::telegram_disconnect_all,
            telegram::telegram_send_message,
            telegram::telegram_send_file,
            telegram::telegram_get_messages,
            telegram::telegram_mark_read,
            supabase::supabase_login,
            supabase::supabase_restore_session,
            supabase::supabase_logout,
            supabase::supabase_get_staff_assignments,
            supabase::supabase_get_user,
            supabase::supabase_get_allowed_contacts,
            supabase::supabase_update_connection_status,
        ])
        .setup(|app| {
            load_env();
            let window = app
                .get_webview_window("main")
                .expect("main window was not created");
            let app_handle = app.handle().clone();
            window.on_window_event(move |event| match event {
                WindowEvent::CloseRequested { .. } => {
                    whatsapp::shutdown();
                    telegram::shutdown();
                }
                WindowEvent::Focused(true) => {
                    let _ = app_handle.emit("app:focus", ());
                }
                _ => {}
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Staff Communications Control");
}
