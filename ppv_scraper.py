import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import aiohttp
from datetime import datetime
import re
import urllib.parse

API_URL = "https://ppv.to/api/streams"

CUSTOM_HEADERS = [
    '#EXTVLCOPT:http-origin=https://ppv.to',
    '#EXTVLCOPT:http-referrer=https://ppv.to/',
    '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0'
]

# Default User-Agent string used when appending params to the URL
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0"

ALLOWED_CATEGORIES = {
    "24/7 Streams", "Football", "Miscellaneous"
}

CATEGORY_LOGOS = {
    "24/7 Streams": "http://drewlive24.duckdns.org:9000/Logos/247.png",
    "Football": "http://drewlive24.duckdns.org:9000/Logos/Football.png",
    "Miscellaneous": "http://drewlive24.duckdns.org:9000/Logos/DrewLiveSports.png"
}

CATEGORY_TVG_IDS = {
    "24/7 Streams": "24.7.Dummy.us",
    "Football": "Soccer.Dummy.us",
    "Miscellaneous": "24.7.Dummy.us"
}

GROUP_RENAME_MAP = {
    "24/7 Streams": "PPVLand - Live Channels 24/7",
    "Football": "PPVLand - Global Football Streams",
    "Miscellaneous": "PPVLand - Random Events"
}

NFL_TEAMS = {
    "arizona cardinals", "atlanta falcons", "baltimore ravens", "buffalo bills",
    "carolina panthers", "chicago bears", "cincinnati bengals", "cleveland browns",
    "dallas cowboys", "denver broncos", "detroit lions", "green bay packers",
    "houston texans", "indianapolis colts", "jacksonville jaguars", "kansas city chiefs",
    "las vegas raiders", "los angeles chargers", "los angeles rams", "miami dolphins",
    "minnesota vikings", "new england patriots", "new orleans saints", "new york giants",
    "new york jets", "philadelphia eagles", "pittsburgh steelers", "san francisco 49ers",
    "seattle seahawks", "tampa bay buccaneers", "tennessee titans", "washington commanders"
}

COLLEGE_TEAMS = {
    "alabama crimson tide", "auburn tigers", "arkansas razorbacks", "georgia bulldogs",
    "florida gators", "lsu tigers", "ole miss rebels", "mississippi state bulldogs",
    "tennessee volunteers", "texas longhorns", "oklahoma sooners", "oklahoma state cowboys",
    "baylor bears", "tcu horned frogs", "kansas jayhawks", "kansas state wildcats",
    "iowa state cyclones", "iowa hawkeyes", "michigan wolverines", "ohio state buckeyes",
    "penn state nittany lions", "michigan state spartans", "wisconsin badgers",
    "minnesota golden gophers", "illinois fighting illini", "northwestern wildcats",
    "indiana hoosiers", "notre dame fighting irish", "usc trojans", "ucla bruins",
    "oregon ducks", "oregon state beavers", "washington huskies", "washington state cougars",
    "arizona wildcats", "stanford cardinal", "california golden bears", "colorado buffaloes",
    "florida state seminoles", "miami hurricanes", "clemson tigers", "north carolina tar heels",
    "duke blue devils", "nc state wolfpack", "wake forest demon deacons", "syracuse orange",
    "virginia cavaliers", "virginia tech hokies", "louisville cardinals", "pittsburgh panthers",
    "maryland terrapins", "rutgers scarlet knights", "nebraska cornhuskers", "purdue boilermakers",
    "texas a&m aggies", "kentucky wildcats", "missouri tigers", "vanderbilt commodores",
    "houston cougars", "utah utes", "byu cougars", "boise state broncos", "san diego state aztecs",
    "cincinnati bearcats", "memphis tigers", "ucf knights", "south florida bulls", "smu mustangs",
    "tulsa golden hurricane", "tulane green wave", "navy midshipmen", "army black knights",
    "arizona state sun devils", "texas tech red raiders", "florida atlantic owls"
}

async def grab_m3u8_from_iframe(page, iframe_url):
    found_streams = set()
    
    def handle_response(response):
        if ".m3u8" in response.url:
            print(f"✅ Found M3U8 Stream: {response.url}")
            found_streams.add(response.url)

    page.on("response", handle_response)
    print(f"🌐 Navigating to iframe: {iframe_url}")
    
    # Determine if this is a problematic domain
    is_problematic = any(domain in iframe_url for domain in ["playembed.top", "playtaku", "embedme"])
    
    try:
        # Use shorter timeout for problematic sites
        nav_timeout = 60000 if is_problematic else 120000
        
        # Navigate with domcontentloaded (faster)
        await page.goto(iframe_url, timeout=nav_timeout, wait_until="domcontentloaded")
        print("✅ Page loaded (domcontentloaded)")
        
        # Try networkidle with shorter timeout and proper error handling
        try:
            idle_timeout = 30000 if is_problematic else 60000
            await page.wait_for_load_state("networkidle", timeout=idle_timeout)
            print("✅ Network idle detected")
        except PlaywrightTimeoutError:
            print("⚠️ Network idle timeout - continuing anyway (common for streaming sites)")
        
    except PlaywrightTimeoutError as e:
        print(f"⚠️ Navigation timeout for {iframe_url}: {e}")
        # Try to salvage the situation
        try:
            await page.wait_for_load_state("load", timeout=30000)
            print("✅ Recovered with basic load state")
        except:
            print(f"❌ Complete failure to load {iframe_url}")
            page.remove_listener("response", handle_response)
            return set()
    except Exception as e:
        print(f"❌ Unexpected error loading {iframe_url}: {e}")
        page.remove_listener("response", handle_response)
        return set()

    # Wait for initial content
    await asyncio.sleep(3)
    
    # Try interaction to trigger lazy-loaded content
    try:
        # Look for play buttons or video elements
        play_selectors = [
            "button[class*='play']",
            "div[class*='play']",
            ".vjs-big-play-button",
            "video",
            "body"
        ]
        
        for selector in play_selectors:
            try:
                await page.click(selector, timeout=2000)
                print(f"✅ Clicked {selector}")
                break
            except:
                continue
                
    except Exception as e:
        print(f"⚠️ Could not interact with page: {e}")
        
    # Wait for stream with adaptive timeout
    stream_wait_time = 15000 if is_problematic else 25000
    print(f"⏳ Waiting for stream (max {stream_wait_time/1000}s)...")
    
    try:
        await page.wait_for_event(
            "response",
            lambda resp: ".m3u8" in resp.url,
            timeout=stream_wait_time
        )
        print("✅ M3U8 stream detected")
        await asyncio.sleep(2)  # Capture any additional streams
    except PlaywrightTimeoutError:
        print("⚠️ No M3U8 detected in time - checking what we captured...")
    except Exception as e:
        print(f"❌ Error waiting for stream: {e}")

    page.remove_listener("response", handle_response)

    if not found_streams:
        print(f"❌ No M3U8 URLs captured for {iframe_url}")
        return set()

    # Validate streams concurrently
    print(f"🔍 Validating {len(found_streams)} captured stream(s)...")
    valid_urls = set()
    tasks = [check_m3u8_url(url, iframe_url) for url in found_streams]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for url, result in zip(found_streams, results):
        if isinstance(result, Exception):
            print(f"🗑️ Error validating {url}: {result}")
        elif result:
            valid_urls.add(url)
        else:
            print(f"🗑️ Invalid/unreachable: {url}")
            
    return valid_urls

async def check_m3u8_url(url, referer):
    """Checks the M3U8 URL using the correct referer for validation."""
    
    # Whitelist known working domains
    if any(domain in url for domain in ["gg.poocloud.in", "hlsplayer"]):
        return True

    try:
        # Extract origin properly
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        
        headers = {
            "User-Agent": DEFAULT_UA,
            "Referer": referer,
            "Origin": origin
        }
        
        timeout = aiohttp.ClientTimeout(total=10)  # Shorter timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers, allow_redirects=True) as resp:
                # Accept more status codes (some streams return 403 but still work)
                is_valid = resp.status in [200, 206, 403]
                if is_valid:
                    print(f"✅ Valid stream ({resp.status}): {url}")
                return is_valid
                
    except asyncio.TimeoutError:
        print(f"⏱️ Timeout checking {url}")
        return False
    except Exception as e:
        print(f"❌ Error checking {url}: {type(e).__name__}")
        return False

async def get_streams():
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0'
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            print(f"🌐 Fetching streams from {API_URL}")
            async with session.get(API_URL) as resp:
                print(f"🔍 Response status: {resp.status}")
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"❌ Error response: {error_text[:500]}")
                    return None
                return await resp.json()
    except Exception as e:
        print(f"❌ Error in get_streams: {str(e)}")
        return None

async def grab_live_now_from_html(page, base_url="https://ppv.to/"):
    print("🌐 Scraping 'Live Now' streams from HTML...")
    live_now_streams = []
    try:
        await page.goto(base_url, timeout=20000)
        await asyncio.sleep(3)

        live_cards = await page.query_selector_all("#livecards a.item-card")
        for card in live_cards:
            href = await card.get_attribute("href")
            name_el = await card.query_selector(".card-title")
            poster_el = await card.query_selector("img.card-img-top")
            name = await name_el.inner_text() if name_el else "Unnamed Live"
            poster = await poster_el.get_attribute("src") if poster_el else None

            if href:
                iframe_url = f"{base_url.rstrip('/')}{href}"
                live_now_streams.append({
                    "name": name.strip(),
                    "iframe": iframe_url,
                    "category": "Live Now",
                    "poster": poster
                })
    except Exception as e:
        print(f"❌ Failed scraping 'Live Now': {e}")

    print(f"✅ Found {len(live_now_streams)} 'Live Now' streams")
    return live_now_streams

def _encode_param(value: str) -> str:
    """Percent-encode a header value for use in the pipe params"""
    return urllib.parse.quote(value or "", safe='')

def build_m3u(streams, url_map):
    """
    Build M3U formatted output compatible with Kodi-style playlist entries.
    For each stream we append a single best URL followed by pipe-separated,
    percent-encoded header params: |User-Agent=...&Referer=...&Origin=...
    """
    lines = ['#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"']
    seen_names = set()
    for s in streams:
        name_lower = s["name"].strip().lower()
        if name_lower in seen_names:
            continue
        seen_names.add(name_lower)

        unique_key = f"{s['name']}::{s['category']}::{s['iframe']}"
        urls = url_map.get(unique_key, [])
        if not urls:
            print(f"⚠️ No working URLs for {s['name']}")
            continue

        orig_category = s.get("category") or "Misc"
        final_group = GROUP_RENAME_MAP.get(orig_category, f"PPVLand - {orig_category}")
        logo = s.get("poster") or CATEGORY_LOGOS.get(orig_category, "http://drewlive24.duckdns.org:9000/Logos/Default.png")
        tvg_id = CATEGORY_TVG_IDS.get(orig_category, "Misc.Dummy.us")

        if orig_category == "American Football":
            matched_team = None
            for team in NFL_TEAMS:
                if team in name_lower:
                    tvg_id = "NFL.Dummy.us"
                    final_group = "PPVLand - NFL Action"
                    matched_team = team
                    break
            if not matched_team:
                for team in COLLEGE_TEAMS:
                    if team in name_lower:
                        tvg_id = "NCAA.Football.Dummy.us"
                        final_group = "PPVLand - College Football"
                        matched_team = team
                        break

        # Pick the first available URL
        url = next(iter(urls))

        # Build the pipe-appended, percent-encoded header params
        try:
            referer = s.get("iframe") or ""
            origin = "https://" + referer.split('/') if referer else "https://ppv.to"
        except Exception:
            origin = "https://ppv.to"

        ua_enc = _encode_param(DEFAULT_UA)
        ref_enc = _encode_param(referer)
        origin_enc = _encode_param(origin)

        param_str = f"|User-Agent={ua_enc}&Referer={ref_enc}&Origin={origin_enc}"

        lines.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{final_group}",{s["name"]}')
        # append the single URL with the pipe-encoded header params (Kodi-style)
        lines.append(f'{url}{param_str}')
    return "\n".join(lines)

async def main():
    print("🚀 Starting Soccer Stream Fetcher")
    data = await get_streams()
    if not data or 'streams' not in data:
        print("❌ No valid data received from the API")
        if data:
            print(f"API Response: {data}")
        return

    # Filter for football-related categories
    football_categories = ["Football"]
    football_streams = []
    
    for category in data.get("streams", []):
        cat = category.get("category", "").strip() or "Misc"
        if cat in football_categories:
            for stream in category.get("streams", []):
                iframe = stream.get("iframe") 
                name = stream.get("name", "Unnamed Event")
                if iframe and is_football_stream(name):
                    football_streams.append({
                        "name": name,
                        "iframe": iframe,
                        "category": cat,
                        "poster": stream.get("poster")
                    })

    # Add live now football streams
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0'
        )
        page = await context.new_page()
        
        live_now_streams = await grab_live_now_from_html(page)
        for s in live_now_streams:
            if is_football_stream(s["name"]):
                football_streams.append(s)
        
        # Process football streams
        url_map = {}
        for idx, s in enumerate(football_streams, start=1):
            key = f"{s['name']}::{s['category']}::{s['iframe']}"
            print(f"\n🔎 Scraping football stream {idx}/{len(football_streams)}: {s['name']}")
            try:
                urls = await grab_m3u8_from_iframe(page, s["iframe"])
                if urls:
                    url_map[key] = urls
                else:
                    print(f"⚠️ No valid streams for {s['name']}")
            except Exception as e:
                print(f"❌ Error scraping {s['name']}: {e}")
                url_map[key] = set()
            finally:
                if idx < len(football_streams):
                    await asyncio.sleep(2)
        
        await browser.close()

    # Build playlist with football-specific logic
    print("\n💾 Writing soccer playlist...")
    playlist = build_m3u(football_streams, url_map)
    with open("SoccerStreams.m3u8", "w", encoding="utf-8") as f:
        f.write(playlist)
    print(f"✅ Done! Soccer playlist saved as SoccerStreams.m3u8")

def is_football_stream(name):
    """Check if a stream name contains football-related terms"""
    football_keywords = ["football", "soccer"]
    return any(keyword in name.lower() for keyword in football_keywords)

if __name__ == "__main__":
    asyncio.run(main())
