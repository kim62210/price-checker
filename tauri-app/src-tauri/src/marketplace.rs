use regex::Regex;
use scraper::{Html, Selector};
use serde::{Deserialize, Serialize};
use std::time::Duration;

const COUPANG_SEARCH: &str = "https://www.coupang.com/np/search";
const NAVER_SEARCH: &str = "https://search.shopping.naver.com/search/all";
const USER_AGENT: &str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
const DEFAULT_LIMIT_PER_PLATFORM: usize = 4;

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SearchItemInput {
    pub id: String,
    pub name: String,
    pub quantity: u32,
    pub unit: String,
    pub target_unit_price: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MarketplaceSearchResult {
    pub id: String,
    pub order_item_id: String,
    pub product_name: String,
    pub platform: String,
    pub option_text: String,
    pub seller_name: String,
    pub listed_price: f64,
    pub shipping_fee: f64,
    pub unit_count: Option<u32>,
    pub unit: String,
    pub unit_price: Option<f64>,
    pub unit_price_confidence: String,
    pub product_url: String,
    pub status: String,
    pub captured_at: String,
    pub saving_vs_target: Option<f64>,
    pub error: Option<String>,
}

#[derive(Debug, Clone)]
struct MarketplaceCandidate {
    platform: &'static str,
    title: String,
    seller: String,
    price: f64,
    shipping_fee: f64,
    url: String,
}

pub async fn search_marketplaces(
    items: Vec<SearchItemInput>,
) -> Result<Vec<MarketplaceSearchResult>, String> {
    if items.is_empty() {
        return Ok(Vec::new());
    }

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(12))
        .user_agent(USER_AGENT)
        .build()
        .map_err(|err| format!("http_client_init_failed:{err}"))?;

    let mut all_results = Vec::new();
    for item in items {
        let coupang = search_coupang(&client, &item).await;
        push_platform_results(&mut all_results, &item, "coupang", coupang);

        // Human-like lightweight pacing between marketplace domains.
        tokio_sleep(450).await;

        let naver = search_naver(&client, &item).await;
        push_platform_results(&mut all_results, &item, "naver", naver);

        tokio_sleep(650).await;
    }

    all_results.sort_by(|a, b| {
        a.order_item_id
            .cmp(&b.order_item_id)
            .then_with(|| null_last(a.unit_price).total_cmp(&null_last(b.unit_price)))
            .then_with(|| a.platform.cmp(&b.platform))
    });
    Ok(all_results)
}

async fn tokio_sleep(ms: u64) {
    tokio::time::sleep(Duration::from_millis(ms)).await;
}

fn null_last(value: Option<f64>) -> f64 {
    value.unwrap_or(f64::MAX)
}

fn push_platform_results(
    all_results: &mut Vec<MarketplaceSearchResult>,
    item: &SearchItemInput,
    platform: &'static str,
    candidates: Result<Vec<MarketplaceCandidate>, String>,
) {
    match candidates {
        Ok(candidates) if !candidates.is_empty() => {
            for (index, candidate) in candidates.into_iter().enumerate() {
                all_results.push(to_result(item, candidate, index));
            }
        }
        Ok(_) => all_results.push(error_result(
            item,
            platform,
            "검색 결과를 찾지 못했습니다.",
            "error",
        )),
        Err(err) => {
            let status = if err.contains("403") || err.contains("blocked") {
                "blocked"
            } else if err.contains("timeout") {
                "timeout"
            } else {
                "error"
            };
            all_results.push(error_result(item, platform, &err, status));
        }
    }
}

fn to_result(
    item: &SearchItemInput,
    candidate: MarketplaceCandidate,
    index: usize,
) -> MarketplaceSearchResult {
    let parsed_unit_count =
        parse_unit_count(&candidate.title).or_else(|| Some(item.quantity.max(1)));
    let unit_price = parsed_unit_count.map(|count| {
        round_two((candidate.price + candidate.shipping_fee) / f64::from(count.max(1)))
    });
    let saving_vs_target = match (item.target_unit_price, unit_price, parsed_unit_count) {
        (Some(target), Some(unit_price), Some(count)) => {
            Some(((target - unit_price) * f64::from(count)).max(0.0).round())
        }
        _ => None,
    };

    MarketplaceSearchResult {
        id: format!("{}-{}-{}", item.id, candidate.platform, index + 1),
        order_item_id: item.id.clone(),
        product_name: item.name.clone(),
        platform: candidate.platform.to_string(),
        option_text: candidate.title,
        seller_name: candidate.seller,
        listed_price: candidate.price,
        shipping_fee: candidate.shipping_fee,
        unit_count: parsed_unit_count,
        unit: item.unit.clone(),
        unit_price,
        unit_price_confidence: if parsed_unit_count == Some(item.quantity.max(1)) {
            "medium".to_string()
        } else {
            "high".to_string()
        },
        product_url: candidate.url,
        status: "ok".to_string(),
        captured_at: now_rfc3339_like(),
        saving_vs_target,
        error: None,
    }
}

fn error_result(
    item: &SearchItemInput,
    platform: &'static str,
    message: &str,
    status: &str,
) -> MarketplaceSearchResult {
    MarketplaceSearchResult {
        id: format!("{}-{}-error", item.id, platform),
        order_item_id: item.id.clone(),
        product_name: item.name.clone(),
        platform: platform.to_string(),
        option_text: format!("{} 검색 실패", item.name),
        seller_name: platform.to_string(),
        listed_price: 0.0,
        shipping_fee: 0.0,
        unit_count: None,
        unit: item.unit.clone(),
        unit_price: None,
        unit_price_confidence: "low".to_string(),
        product_url: match platform {
            "coupang" => "https://www.coupang.com/".to_string(),
            "naver" => "https://shopping.naver.com/".to_string(),
            _ => String::new(),
        },
        status: status.to_string(),
        captured_at: now_rfc3339_like(),
        saving_vs_target: None,
        error: Some(message.to_string()),
    }
}

async fn search_coupang(
    client: &reqwest::Client,
    item: &SearchItemInput,
) -> Result<Vec<MarketplaceCandidate>, String> {
    let url = format!(
        "{COUPANG_SEARCH}?q={}&channel=user",
        urlencoding::encode(&item.name)
    );
    let html = fetch_html(client, &url, Some("https://www.coupang.com/")).await?;
    let document = Html::parse_document(&html);
    let item_selector = selector("li.search-product");
    let title_selector = selector(".name");
    let price_selector = selector(".price-value");
    let link_selector = selector("a.search-product-link");
    let mut candidates = Vec::new();

    for node in document
        .select(&item_selector)
        .take(DEFAULT_LIMIT_PER_PLATFORM * 3)
    {
        let title = node
            .select(&title_selector)
            .next()
            .map(text_of)
            .unwrap_or_default();
        if title.len() < 2 {
            continue;
        }
        let price_text = node
            .select(&price_selector)
            .next()
            .map(text_of)
            .unwrap_or_default();
        let Some(price) = parse_price(&price_text) else {
            continue;
        };
        let href = node
            .select(&link_selector)
            .next()
            .and_then(|link| link.value().attr("href"))
            .unwrap_or("https://www.coupang.com/");
        let url = absolute_url("https://www.coupang.com", href);
        let full_text = text_of(node);
        let shipping_fee = if full_text.contains("무료배송")
            || full_text.contains("로켓") && price >= 19_800.0
        {
            0.0
        } else {
            3_000.0
        };
        candidates.push(MarketplaceCandidate {
            platform: "coupang",
            title,
            seller: "쿠팡".to_string(),
            price,
            shipping_fee,
            url,
        });
        if candidates.len() >= DEFAULT_LIMIT_PER_PLATFORM {
            break;
        }
    }

    Ok(candidates)
}

async fn search_naver(
    client: &reqwest::Client,
    item: &SearchItemInput,
) -> Result<Vec<MarketplaceCandidate>, String> {
    let url = format!(
        "{NAVER_SEARCH}?query={}&cat_id=&frm=NVSHATC",
        urlencoding::encode(&item.name)
    );
    let html = fetch_html(client, &url, Some("https://shopping.naver.com/")).await?;
    let mut candidates = parse_naver_dom(&html);
    if candidates.is_empty() {
        candidates = parse_naver_embedded_json(&html);
    }
    Ok(candidates
        .into_iter()
        .take(DEFAULT_LIMIT_PER_PLATFORM)
        .collect())
}

async fn fetch_html(
    client: &reqwest::Client,
    url: &str,
    referer: Option<&str>,
) -> Result<String, String> {
    let mut request = client
        .get(url)
        .header(
            "accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        )
        .header("accept-language", "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6")
        .header("cache-control", "no-cache");
    if let Some(referer) = referer {
        request = request.header("referer", referer);
    }
    let response = request
        .send()
        .await
        .map_err(|err| format!("request_failed:{err}"))?;
    let status = response.status();
    if !status.is_success() {
        return Err(format!("http_status:{status}"));
    }
    response
        .text()
        .await
        .map_err(|err| format!("read_body_failed:{err}"))
}

fn parse_naver_dom(html: &str) -> Vec<MarketplaceCandidate> {
    let document = Html::parse_document(html);
    let item_selector = selector("li[class*='product_item'], div[class*='product_item']");
    let title_selector = selector(
        "a[class*='product_link'], a[class*='product_title'], strong[class*='product_title'] a",
    );
    let price_selector =
        selector("span[class*='price_num'], strong[class*='price'], em[class*='price']");
    let mall_selector =
        selector("a[class*='product_mall'], span[class*='product_mall'], a[class*='mall']");
    let mut candidates = Vec::new();

    for node in document
        .select(&item_selector)
        .take(DEFAULT_LIMIT_PER_PLATFORM * 4)
    {
        let title_node = node.select(&title_selector).next();
        let title = title_node.map(text_of).unwrap_or_default();
        if title.len() < 2 {
            continue;
        }
        let price_text = node
            .select(&price_selector)
            .next()
            .map(text_of)
            .unwrap_or_default();
        let Some(price) = parse_price(&price_text) else {
            continue;
        };
        let url = title_node
            .and_then(|link| link.value().attr("href"))
            .map(|href| absolute_url("https://search.shopping.naver.com", href))
            .unwrap_or_else(|| NAVER_SEARCH.to_string());
        let seller = node
            .select(&mall_selector)
            .next()
            .map(text_of)
            .filter(|text| !text.is_empty())
            .unwrap_or_else(|| "네이버쇼핑".to_string());
        candidates.push(MarketplaceCandidate {
            platform: "naver",
            title,
            seller,
            price,
            shipping_fee: 0.0,
            url,
        });
        if candidates.len() >= DEFAULT_LIMIT_PER_PLATFORM {
            break;
        }
    }
    candidates
}

fn parse_naver_embedded_json(html: &str) -> Vec<MarketplaceCandidate> {
    let product_re = Regex::new(
        r#"(?s)\{[^{}]*?(?:\"productName\"|\"productTitle\"|\"title\")\s*:\s*\"(?P<title>[^\"]{2,160})\"[^{}]*?(?:\"lowPrice\"|\"price\"|\"salePrice\")\s*:\s*\"?(?P<price>[0-9,]{3,})\"?[^{}]*?\}"#,
    )
    .expect("valid regex");
    let mall_re =
        Regex::new(r#"(?:mallName|mall_name)\"?\s*:\s*\"([^\"]+)\""#).expect("valid regex");
    let url_re = Regex::new(r#"(?:crUrl|mallProductUrl|productUrl|adcrUrl)\"?\s*:\s*\"([^\"]+)\""#)
        .expect("valid regex");
    let mut candidates = Vec::new();

    for cap in product_re
        .captures_iter(html)
        .take(DEFAULT_LIMIT_PER_PLATFORM * 2)
    {
        let title = decode_jsonish(cap.name("title").map(|m| m.as_str()).unwrap_or_default());
        let Some(price) = cap.name("price").and_then(|m| parse_price(m.as_str())) else {
            continue;
        };
        let block = cap.get(0).map(|m| m.as_str()).unwrap_or_default();
        let seller = mall_re
            .captures(block)
            .and_then(|m| m.get(1))
            .map(|m| decode_jsonish(m.as_str()))
            .filter(|text| !text.is_empty())
            .unwrap_or_else(|| "네이버쇼핑".to_string());
        let url = url_re
            .captures(block)
            .and_then(|m| m.get(1))
            .map(|m| decode_jsonish(m.as_str()))
            .filter(|text| text.starts_with("http"))
            .unwrap_or_else(|| NAVER_SEARCH.to_string());
        if title.len() < 2 {
            continue;
        }
        candidates.push(MarketplaceCandidate {
            platform: "naver",
            title,
            seller,
            price,
            shipping_fee: 0.0,
            url,
        });
        if candidates.len() >= DEFAULT_LIMIT_PER_PLATFORM {
            break;
        }
    }
    candidates
}

fn selector(query: &str) -> Selector {
    Selector::parse(query).expect("static selector must be valid")
}

fn text_of(node: scraper::ElementRef<'_>) -> String {
    normalize_space(&node.text().collect::<Vec<_>>().join(" "))
}

fn normalize_space(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn parse_price(text: &str) -> Option<f64> {
    let digits: String = text.chars().filter(|ch| ch.is_ascii_digit()).collect();
    if digits.len() < 3 {
        return None;
    }
    digits.parse::<f64>().ok().filter(|price| *price > 0.0)
}

fn parse_unit_count(text: &str) -> Option<u32> {
    let total_re =
        Regex::new(r"총\s*([0-9]{1,4})\s*(?:개|개입|입|팩|봉|병|매)").expect("valid regex");
    if let Some(count) = capture_count(&total_re, text) {
        return Some(count);
    }

    let multiply_re =
        Regex::new(r"([0-9]{1,4})\s*(?:개|개입|입|팩|봉|병|매)\s*[xX×*]\s*([0-9]{1,4})")
            .expect("valid regex");
    if let Some(cap) = multiply_re.captures(text) {
        let left = cap.get(1)?.as_str().parse::<u32>().ok()?;
        let right = cap.get(2)?.as_str().parse::<u32>().ok()?;
        return Some(left.saturating_mul(right).max(1));
    }

    let count_re =
        Regex::new(r"([0-9]{1,4})\s*(?:개입|개|입|팩|봉|병|매|롤)").expect("valid regex");
    capture_count(&count_re, text)
}

fn capture_count(regex: &Regex, text: &str) -> Option<u32> {
    regex
        .captures(text)
        .and_then(|cap| cap.get(1))
        .and_then(|m| m.as_str().parse::<u32>().ok())
        .filter(|count| *count > 0)
}

fn round_two(value: f64) -> f64 {
    (value * 100.0).round() / 100.0
}

fn absolute_url(base: &str, href: &str) -> String {
    if href.starts_with("http://") || href.starts_with("https://") {
        href.to_string()
    } else if href.starts_with("//") {
        format!("https:{href}")
    } else if href.starts_with('/') {
        format!("{base}{href}")
    } else {
        format!("{base}/{href}")
    }
}

fn decode_jsonish(input: &str) -> String {
    input
        .replace("\\u002F", "/")
        .replace("\\/", "/")
        .replace("\\\"", "\"")
        .replace("&quot;", "\"")
        .replace("&amp;", "&")
}

fn now_rfc3339_like() -> String {
    chrono::Utc::now().to_rfc3339()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_unit_count_from_common_korean_titles() {
        assert_eq!(parse_unit_count("콜라 500ml 24개"), Some(24));
        assert_eq!(parse_unit_count("물티슈 10개입 x 4팩 총 40개"), Some(40));
        assert_eq!(parse_unit_count("라면 5개입 X 8"), Some(40));
    }

    #[test]
    fn parses_price_digits() {
        assert_eq!(parse_price("12,900원"), Some(12900.0));
        assert_eq!(parse_price("무료"), None);
    }
}
