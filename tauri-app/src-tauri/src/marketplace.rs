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
    free_threshold: Option<f64>,
    is_rocket: bool,
    source: &'static str,
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
        push_platform_results(&client, &mut all_results, &item, "coupang", coupang).await;

        // Human-like lightweight pacing between marketplace domains.
        tokio_sleep(450).await;

        let naver = search_naver(&client, &item).await;
        push_platform_results(&client, &mut all_results, &item, "naver", naver).await;

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

async fn push_platform_results(
    client: &reqwest::Client,
    all_results: &mut Vec<MarketplaceSearchResult>,
    item: &SearchItemInput,
    platform: &'static str,
    candidates: Result<Vec<MarketplaceCandidate>, String>,
) {
    match candidates {
        Ok(candidates) if !candidates.is_empty() => {
            for (index, candidate) in candidates.into_iter().enumerate() {
                let enriched = enrich_candidate(client, candidate).await;
                all_results.push(to_result(item, enriched, index));
                tokio_sleep(220).await;
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
        option_text: format!("{} · {}", candidate.title, candidate.source),
        seller_name: candidate.seller,
        listed_price: candidate.price,
        shipping_fee: candidate.shipping_fee,
        unit_count: parsed_unit_count,
        unit: item.unit.clone(),
        unit_price,
        unit_price_confidence: if candidate.source.contains("detail")
            && parsed_unit_count != Some(item.quantity.max(1))
        {
            "high".to_string()
        } else if parsed_unit_count == Some(item.quantity.max(1)) {
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
            free_threshold: Some(19_800.0),
            is_rocket: full_text.contains("로켓"),
            source: "search_selector",
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
            free_threshold: None,
            is_rocket: false,
            source: "search_selector",
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
            free_threshold: None,
            is_rocket: false,
            source: "search_embedded_json",
            url,
        });
        if candidates.len() >= DEFAULT_LIMIT_PER_PLATFORM {
            break;
        }
    }
    candidates
}

async fn enrich_candidate(
    client: &reqwest::Client,
    candidate: MarketplaceCandidate,
) -> MarketplaceCandidate {
    if !candidate.url.starts_with("http") {
        return candidate;
    }
    let detail = match candidate.platform {
        "coupang" => fetch_html(client, &candidate.url, Some("https://www.coupang.com/"))
            .await
            .ok()
            .and_then(|html| parse_coupang_detail(&html)),
        "naver" => fetch_html(client, &candidate.url, Some("https://shopping.naver.com/"))
            .await
            .ok()
            .and_then(|html| parse_naver_detail(&html)),
        _ => None,
    };

    let Some(detail) = detail else {
        return candidate;
    };

    let price = detail.price.unwrap_or(candidate.price);
    let shipping_fee = apply_shipping_policy(
        candidate.platform,
        price,
        detail
            .shipping_fee
            .or(Some(candidate.shipping_fee))
            .unwrap_or(0.0),
        detail.free_threshold.or(candidate.free_threshold),
        detail.is_rocket || candidate.is_rocket,
    );

    MarketplaceCandidate {
        title: detail.option_text.unwrap_or(candidate.title),
        seller: detail.seller.unwrap_or(candidate.seller),
        price,
        shipping_fee,
        free_threshold: detail.free_threshold.or(candidate.free_threshold),
        is_rocket: detail.is_rocket || candidate.is_rocket,
        source: detail.source,
        ..candidate
    }
}

#[derive(Debug, Clone)]
struct DetailData {
    option_text: Option<String>,
    seller: Option<String>,
    price: Option<f64>,
    shipping_fee: Option<f64>,
    free_threshold: Option<f64>,
    is_rocket: bool,
    source: &'static str,
}

fn parse_coupang_detail(html: &str) -> Option<DetailData> {
    let document = Html::parse_document(html);
    let body_text = normalize_space(&document.root_element().text().collect::<Vec<_>>().join(" "));
    let json_ld_price = parse_json_ld_price(html);
    let meta_price = parse_meta_price(
        &document,
        &["product:price:amount", "og:price:amount", "twitter:data1"],
    );
    let selector_price = first_price_by_selector(
        &document,
        &[".price-value", ".total-price", "[class*='price']"],
    );
    let price = json_ld_price.or(meta_price).or(selector_price);
    let shipping_fee = parse_shipping_fee(&body_text);
    let is_rocket = body_text.contains("로켓") || body_text.to_lowercase().contains("rocket");
    let option_text = first_text_by_selector(
        &document,
        &[
            "h1.prod-buy-header__title",
            "h1[class*='title']",
            "meta[property='og:title']",
        ],
    );
    let seller = first_text_by_selector(
        &document,
        &[
            ".prod-sale-vendor-name",
            "[class*='vendor']",
            "[class*='seller']",
        ],
    );
    let source = if json_ld_price.is_some() {
        "detail_json_ld"
    } else if meta_price.is_some() {
        "detail_meta_tag"
    } else {
        "detail_selector"
    };
    if price.is_none() && option_text.is_none() && shipping_fee.is_none() {
        return None;
    }
    Some(DetailData {
        option_text,
        seller,
        price,
        shipping_fee,
        free_threshold: Some(19_800.0),
        is_rocket,
        source,
    })
}

fn parse_naver_detail(html: &str) -> Option<DetailData> {
    let document = Html::parse_document(html);
    let body_text = normalize_space(&document.root_element().text().collect::<Vec<_>>().join(" "));
    let preloaded = parse_naver_preloaded_state(html);
    if preloaded.price.is_some() || preloaded.option_text.is_some() {
        return Some(preloaded);
    }
    let meta_price = parse_meta_price(&document, &["product:price:amount", "og:price:amount"]);
    let selector_price = first_price_by_selector(&document, &["[class*='price']", "strong", "em"]);
    let price = meta_price.or(selector_price);
    let shipping_fee = parse_shipping_fee(&body_text);
    let free_threshold = parse_free_threshold(&body_text);
    let option_text = first_text_by_selector(
        &document,
        &["meta[property='og:title']", "h1", "[class*='title']"],
    );
    if price.is_none()
        && option_text.is_none()
        && shipping_fee.is_none()
        && free_threshold.is_none()
    {
        return None;
    }
    Some(DetailData {
        option_text,
        seller: Some("네이버 스마트스토어".to_string()),
        price,
        shipping_fee,
        free_threshold,
        is_rocket: false,
        source: "detail_selector",
    })
}

fn parse_naver_preloaded_state(html: &str) -> DetailData {
    let state_re = Regex::new(r#"(?s)__PRELOADED_STATE__\s*=\s*(?P<json>\{.*?\})\s*</script>"#)
        .expect("valid regex");
    let Some(json_text) = state_re
        .captures(html)
        .and_then(|cap| cap.name("json"))
        .map(|m| m.as_str())
    else {
        return empty_detail("preloaded_state_missing");
    };
    let title_re =
        Regex::new(r#"(?:productName|name|title)"\s*:\s*"([^"]{2,180})"#).expect("valid regex");
    let option_re =
        Regex::new(r#"(?:optionName|name)"\s*:\s*"([^"]{2,180})"#).expect("valid regex");
    let price_re = Regex::new(r#"(?:salePrice|discountedSalePrice|price)"\s*:\s*"?([0-9,]{3,})"?"#)
        .expect("valid regex");
    let shipping_re = Regex::new(r#"(?:baseFee|deliveryFee|shippingFee)"\s*:\s*"?([0-9,]{1,})"?"#)
        .expect("valid regex");
    let free_re = Regex::new(
        r#"(?:freeShippingPrice|freeDeliveryPrice|freeThreshold)"\s*:\s*"?([0-9,]{3,})"?"#,
    )
    .expect("valid regex");
    let title = option_re
        .captures(json_text)
        .and_then(|cap| cap.get(1))
        .or_else(|| title_re.captures(json_text).and_then(|cap| cap.get(1)))
        .map(|m| decode_jsonish(m.as_str()));
    DetailData {
        option_text: title,
        seller: Some("네이버 스마트스토어".to_string()),
        price: price_re
            .captures(json_text)
            .and_then(|cap| cap.get(1))
            .and_then(|m| parse_price(m.as_str())),
        shipping_fee: shipping_re
            .captures(json_text)
            .and_then(|cap| cap.get(1))
            .and_then(|m| parse_price(m.as_str())),
        free_threshold: free_re
            .captures(json_text)
            .and_then(|cap| cap.get(1))
            .and_then(|m| parse_price(m.as_str())),
        is_rocket: false,
        source: "detail_preloaded_state",
    }
}

fn empty_detail(source: &'static str) -> DetailData {
    DetailData {
        option_text: None,
        seller: None,
        price: None,
        shipping_fee: None,
        free_threshold: None,
        is_rocket: false,
        source,
    }
}

fn parse_json_ld_price(html: &str) -> Option<f64> {
    let script_re =
        Regex::new(r#"(?s)<script[^>]*application/ld\+json[^>]*>(?P<json>.*?)</script>"#)
            .expect("valid regex");
    let price_re =
        Regex::new(r#"(?:price|lowPrice)"\s*:\s*"?([0-9,]{3,})"?"#).expect("valid regex");
    let parsed = script_re
        .captures_iter(html)
        .filter_map(|cap| cap.name("json"))
        .find_map(|json| {
            price_re
                .captures(json.as_str())
                .and_then(|cap| cap.get(1))
                .and_then(|m| parse_price(m.as_str()))
        });
    parsed
}

fn parse_meta_price(document: &Html, properties: &[&str]) -> Option<f64> {
    for property in properties {
        let query = format!("meta[property='{property}'], meta[name='{property}']");
        let selector = Selector::parse(&query).ok()?;
        if let Some(price) = document
            .select(&selector)
            .filter_map(|node| node.value().attr("content"))
            .find_map(parse_price)
        {
            return Some(price);
        }
    }
    None
}

fn first_price_by_selector(document: &Html, selectors: &[&str]) -> Option<f64> {
    selectors.iter().find_map(|query| {
        let selector = Selector::parse(query).ok()?;
        document
            .select(&selector)
            .map(text_of)
            .find_map(|text| parse_price(&text))
    })
}

fn first_text_by_selector(document: &Html, selectors: &[&str]) -> Option<String> {
    selectors.iter().find_map(|query| {
        let selector = Selector::parse(query).ok()?;
        document.select(&selector).find_map(|node| {
            let content = node
                .value()
                .attr("content")
                .map(str::to_string)
                .unwrap_or_else(|| text_of(node));
            let text = normalize_space(&content);
            (text.len() >= 2).then_some(text)
        })
    })
}

fn parse_shipping_fee(text: &str) -> Option<f64> {
    if text.contains("무료배송") || text.contains("배송비 무료") {
        return Some(0.0);
    }
    let shipping_re = Regex::new(r"배송(?:비|료)?\s*([0-9,]{3,})\s*원").expect("valid regex");
    shipping_re
        .captures(text)
        .and_then(|cap| cap.get(1))
        .and_then(|m| parse_price(m.as_str()))
}

fn parse_free_threshold(text: &str) -> Option<f64> {
    let free_re = Regex::new(r"([0-9,]{4,})\s*원\s*이상\s*무료").expect("valid regex");
    free_re
        .captures(text)
        .and_then(|cap| cap.get(1))
        .and_then(|m| parse_price(m.as_str()))
}

fn apply_shipping_policy(
    platform: &str,
    subtotal: f64,
    explicit_fee: f64,
    free_threshold: Option<f64>,
    is_rocket: bool,
) -> f64 {
    if platform == "coupang" && is_rocket && subtotal >= 19_800.0 {
        return 0.0;
    }
    if let Some(threshold) = free_threshold {
        if subtotal >= threshold {
            return 0.0;
        }
    }
    explicit_fee
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

    #[test]
    fn parses_coupang_detail_json_ld_and_shipping() {
        let html = r#"
            <html><head>
            <script type="application/ld+json">{"offers":{"price":"12900","priceCurrency":"KRW"}}</script>
            <meta property="og:title" content="콜라 500ml 24개" />
            </head><body>배송비 3,000원</body></html>
        "#;
        let detail = parse_coupang_detail(html).expect("detail parsed");
        assert_eq!(detail.price, Some(12900.0));
        assert_eq!(detail.shipping_fee, Some(3000.0));
        assert_eq!(detail.source, "detail_json_ld");
    }

    #[test]
    fn applies_free_shipping_threshold() {
        assert_eq!(
            apply_shipping_policy("naver", 35000.0, 3000.0, Some(30000.0), false),
            0.0
        );
        assert_eq!(
            apply_shipping_policy("coupang", 25000.0, 3000.0, Some(19800.0), true),
            0.0
        );
    }
}
