#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashSet;
use std::process::Command;
use std::sync::Mutex;
use std::time::Duration;

use serde_json::Value;
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
    AppHandle, Manager, WebviewUrl, WebviewWindowBuilder,
};
use tauri_plugin_clipboard_manager::ClipboardExt;
use tauri_plugin_notification::NotificationExt;

struct RecState(Mutex<Vec<Value>>);

fn brain_dir() -> String {
    let home = std::env::var("HOME").unwrap_or_default();
    format!("{home}/Desktop/Work_with_Claude_Mac/skills-companion/brain")
}

fn run_brain(args: &[&str]) -> Result<Value, String> {
    let out = Command::new("python3")
        .args(["-m", "skills_companion.cli"])
        .args(args)
        .env("PYTHONPATH", brain_dir())
        .output()
        .map_err(|e| e.to_string())?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).into_owned());
    }
    serde_json::from_slice(&out.stdout).map_err(|e| e.to_string())
}

#[tauri::command]
async fn brain(args: Vec<String>) -> Result<Value, String> {
    let refs: Vec<&str> = args.iter().map(String::as_str).collect();
    run_brain(&refs)
}

#[tauri::command]
fn copy_text(app: AppHandle, text: String) -> Result<(), String> {
    app.clipboard().write_text(text).map_err(|e| e.to_string())
}

#[tauri::command]
fn notify(app: AppHandle, title: String, body: String) {
    let _ = app.notification().builder().title(title).body(body).show();
}

#[tauri::command]
fn autotype_reload() -> bool {
    #[cfg(target_os = "macos")]
    {
        let script = r#"tell application "System Events"
  set frontApp to name of first application process whose frontmost is true
  if frontApp is in {"Terminal", "iTerm2", "WezTerm", "Alacritty", "kitty", "Ghostty"} then
    keystroke "/reload-plugins"
    key code 36
    return "typed"
  end if
end tell
return "skipped""#;
        if let Ok(o) = Command::new("osascript").arg("-e").arg(script).output() {
            return String::from_utf8_lossy(&o.stdout).trim() == "typed";
        }
    }
    false
}

fn open_main(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.set_focus();
    }
}

#[tauri::command]
fn open_wizard(app: AppHandle) {
    if let Some(w) = app.get_webview_window("wizard") {
        let _ = w.show();
        let _ = w.set_focus();
        return;
    }
    let _ = WebviewWindowBuilder::new(&app, "wizard", WebviewUrl::App("wizard.html".into()))
        .title("경량화 마법사 — Skills Companion")
        .inner_size(760.0, 680.0)
        .build();
}

fn open_revert(app: &AppHandle, session: &str) {
    let label = format!("revert-{}", &session[..session.len().min(8)]);
    if app.get_webview_window(&label).is_some() {
        return;
    }
    let url = format!("revert.html?session={session}");
    let _ = WebviewWindowBuilder::new(app, &label, WebviewUrl::App(url.into()))
        .title("세션 정리 — Skills Companion")
        .inner_size(480.0, 460.0)
        .build();
}

fn activate_flow(app: &AppHandle, plugin: &str, invoke_label: &str) {
    match run_brain(&["activate", "--plugin", plugin]) {
        Ok(v) => {
            if v["ok"] == true {
                let _ = app.clipboard().write_text("/reload-plugins".to_string());
                let typed = autotype_reload();
                let body = if typed {
                    format!("{invoke_label} 활성화 — /reload-plugins 자동 입력됨")
                } else {
                    format!("{invoke_label} 활성화 — /reload-plugins 를 세션에 붙여넣으세요 (복사됨)")
                };
                let _ = app.notification().builder()
                    .title("플러그인 활성화됨").body(body).show();
            } else {
                let error = v["error"].as_str().unwrap_or("알 수 없는 오류").to_string();
                eprintln!("activate_flow: brain reported ok:false — {error}");
                let _ = app.notification().builder()
                    .title("활성화 실패")
                    .body(format!("활성화 실패: {error}"))
                    .show();
            }
        }
        Err(e) => {
            eprintln!("activate_flow: run_brain error — {e}");
            let _ = app.notification().builder()
                .title("활성화 실패").body(e).show();
        }
    }
}

fn handle_rec_click(app: &AppHandle, idx: usize) {
    let recs = match app.state::<RecState>().0.lock() {
        Ok(guard) => guard.clone(),
        Err(poisoned) => poisoned.into_inner().clone(),
    };
    let Some(r) = recs.get(idx) else { return };
    let invoke = r["item"]["invoke"].as_str().unwrap_or("").to_string();
    if r["kind"] == "actionable" {
        if let Some(plugin) = r["item"]["plugin"].as_str() {
            activate_flow(app, plugin, &invoke);
        }
    } else {
        let _ = app.clipboard().write_text(invoke.clone());
        let _ = app.notification().builder()
            .title("복사됨").body(format!("{invoke} — 세션에 붙여넣으세요")).show();
    }
}

fn rebuild_tray(app: &AppHandle, recs: &[Value]) -> tauri::Result<()> {
    match app.state::<RecState>().0.lock() {
        Ok(mut guard) => *guard = recs.to_vec(),
        Err(poisoned) => *poisoned.into_inner() = recs.to_vec(),
    }
    let mut rec_items: Vec<MenuItem<tauri::Wry>> = vec![];
    for (i, r) in recs.iter().take(3).enumerate() {
        let mark = if r["kind"] == "actionable" { "⚡" } else { "💡" };
        let label = format!("{mark} {}", r["item"]["invoke"].as_str().unwrap_or("?"));
        if let Ok(mi) = MenuItem::with_id(app, format!("rec:{i}"), label, true,
                                          None::<&str>) {
            rec_items.push(mi);
        }
    }
    let open_i = MenuItem::with_id(app, "open", "Skills Companion 열기", true,
                                   None::<&str>)?;
    let quit_i = MenuItem::with_id(app, "quit", "종료", true, None::<&str>)?;
    let sep = PredefinedMenuItem::separator(app)?;
    let mut refs: Vec<&dyn tauri::menu::IsMenuItem<tauri::Wry>> = vec![];
    for mi in &rec_items {
        refs.push(mi);
    }
    refs.push(&sep);
    refs.push(&open_i);
    refs.push(&quit_i);
    let menu = Menu::with_items(app, &refs)?;
    if let Some(tray) = app.tray_by_id("main") {
        tray.set_menu(Some(menu))?;
    }
    Ok(())
}

fn poll_once(app: &AppHandle, notified: &mut HashSet<String>) {
    // 1) explicit end signals, then leaks — both funnel into session-end
    let mut sids: Vec<String> = vec![];
    if let Ok(v) = run_brain(&["pending"]) {
        if let Some(arr) = v["sessions"].as_array() {
            sids.extend(arr.iter()
                .filter_map(|x| x["session_id"].as_str().map(String::from)));
        }
    }
    if let Ok(v) = run_brain(&["sweep"]) {
        if let Some(arr) = v["leaks"].as_array() {
            sids.extend(arr.iter().filter_map(|x| x.as_str().map(String::from)));
        }
    }
    for sid in sids {
        if let Ok(r) = run_brain(&["session-end", "--session", &sid]) {
            if r["action"] == "ask" {
                open_revert(app, &sid);
            }
        }
    }
    // 2) recommendations -> tray + opt-in notification
    let notifications_on = run_brain(&["config-get"])
        .map(|c| c["notifications_enabled"] == true)
        .unwrap_or(false);
    if let Ok(v) = run_brain(&["recommend", "--top", "3"]) {
        let recs = v["recommendations"].as_array().cloned().unwrap_or_default();
        if let Err(e) = rebuild_tray(app, &recs) {
            eprintln!("rebuild_tray failed: {e}");
        }
        if notifications_on {
            for r in &recs {
                if r["kind"] != "actionable" {
                    continue;
                }
                let key = r["item"]["plugin"].as_str().unwrap_or("").to_string();
                if !key.is_empty() && notified.insert(key.clone()) {
                    let _ = app.notification().builder()
                        .title("추천 플러그인")
                        .body(format!("{key} — 트레이에서 활성화할 수 있어요"))
                        .show();
                }
            }
        }
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_notification::init())
        .manage(RecState(Mutex::new(vec![])))
        .invoke_handler(tauri::generate_handler![
            brain, copy_text, notify, autotype_reload, open_wizard
        ])
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            let open_i = MenuItem::with_id(app, "open", "Skills Companion 열기",
                                           true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "종료", true, None::<&str>)?;
            let sep = PredefinedMenuItem::separator(app)?;
            let menu = Menu::with_items(app, &[&open_i, &sep, &quit_i])?;
            TrayIconBuilder::with_id("main")
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, e| {
                    let id = e.id().as_ref().to_string();
                    match id.as_str() {
                        "open" => open_main(app),
                        "quit" => app.exit(0),
                        _ => {
                            if let Some(i) = id.strip_prefix("rec:") {
                                if let Ok(idx) = i.parse::<usize>() {
                                    handle_rec_click(app, idx);
                                }
                            }
                        }
                    }
                })
                .build(app)?;
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let mut notified: HashSet<String> = HashSet::new();
                loop {
                    poll_once(&handle, &mut notified);
                    let secs = run_brain(&["config-get"])
                        .ok()
                        .and_then(|c| c["poll_seconds"].as_u64())
                        .unwrap_or(20);
                    std::thread::sleep(Duration::from_secs(secs));
                }
            });
            let h2 = app.handle().clone();
            std::thread::spawn(move || {
                if let Ok(c) = run_brain(&["config-get"]) {
                    if c["wizard_completed"] == false {
                        open_wizard(h2);
                    }
                }
            });
            Ok(())
        })
        .on_window_event(|w, e| {
            if w.label() == "main" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = e {
                    let _ = w.hide();
                    api.prevent_close();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Skills Companion");
}
