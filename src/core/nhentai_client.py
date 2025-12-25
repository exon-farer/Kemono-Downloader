import requests
import json

# 1. Update arguments to accept proxies=None
def fetch_nhentai_gallery(gallery_id, logger=print, proxies=None):
    """
    Fetches the metadata for a single nhentai gallery.
    Switched to standard requests to support proxies with self-signed certs.
    """
    api_url = f"https://nhentai.net/api/gallery/{gallery_id}"
    
    # 2. Use a real User-Agent to avoid immediate blocking
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    logger(f"   Fetching nhentai gallery metadata from: {api_url}")

    # 3. Smart timeout logic
    req_timeout = (30, 120) if proxies else 20

    try:
        # 4. Use requests.get with proxies, verify=False, and timeout
        response = requests.get(api_url, headers=headers, timeout=req_timeout, proxies=proxies, verify=False)
        
        if response.status_code == 404:
            logger(f"   ❌ Gallery not found (404): ID {gallery_id}")
            return None
        elif response.status_code == 403:
            logger(f"   ❌ Access Denied (403): Cloudflare blocked the request. Try a different proxy or User-Agent.")
            return None
            
        response.raise_for_status()

        gallery_data = response.json()
        
        if "id" in gallery_data and "media_id" in gallery_data and "images" in gallery_data:
            logger(f"   ✅ Successfully fetched metadata for '{gallery_data['title']['english']}'")
            gallery_data['pages'] = gallery_data.pop('images')['pages']
            return gallery_data
        else:
            logger("   ❌ API response is missing essential keys (id, media_id, images).")
            return None

    except Exception as e:
        logger(f"   ❌ Error fetching nhentai metadata: {e}")
        return None