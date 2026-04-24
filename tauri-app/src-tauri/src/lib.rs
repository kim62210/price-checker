mod marketplace;

use marketplace::{search_marketplaces, MarketplaceSearchResult, SearchItemInput};

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

#[tauri::command]
async fn search_marketplace_items(
    items: Vec<SearchItemInput>,
) -> Result<Vec<MarketplaceSearchResult>, String> {
    search_marketplaces(items).await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            open_login_webview,
            run_comparison,
            search_marketplace_items,
        ])
        .run(tauri::generate_context!())
        .expect("error while running lowest-price Tauri app");
}
