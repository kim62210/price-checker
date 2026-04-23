#[tauri::command]
fn open_login_webview(platform: String) -> Result<String, String> {
    match platform.as_str() {
        "coupang" | "naver" => Ok(format!("login_webview_requested:{platform}")),
        _ => Err("unsupported_platform".to_string()),
    }
}

#[tauri::command]
fn run_comparison(items: Vec<String>) -> Result<usize, String> {
    Ok(items.len())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![open_login_webview, run_comparison])
        .run(tauri::generate_context!())
        .expect("error while running lowest-price Tauri app");
}
