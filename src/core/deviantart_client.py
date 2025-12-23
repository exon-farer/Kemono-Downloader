import requests
import re
import os
import time
import threading
from urllib.parse import urlparse

class DeviantArtClient:
    # Public Client Credentials
    CLIENT_ID = "5388"
    CLIENT_SECRET = "76b08c69cfb27f26d6161f9ab6d061a1"
    BASE_API = "https://www.deviantart.com/api/v1/oauth2"

    def __init__(self, logger_func=print):
        self.session = requests.Session()
        # Headers matching 1.py (Firefox)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })
        self.access_token = None
        self.logger = logger_func
        
        # --- DEDUPLICATION LOGIC ---
        self.logged_waits = set()
        self.log_lock = threading.Lock()

    def authenticate(self):
        """Authenticates using client credentials flow."""
        try:
            url = "https://www.deviantart.com/oauth2/token"
            data = {
                "grant_type": "client_credentials",
                "client_id": self.CLIENT_ID,
                "client_secret": self.CLIENT_SECRET
            }
            resp = self.session.post(url, data=data, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self.access_token = data.get("access_token")
            return True
        except Exception as e:
            self.logger(f"DA Auth Error: {e}")
            return False

    def _api_call(self, endpoint, params=None):
        if not self.access_token:
            if not self.authenticate():
                raise Exception("Authentication failed")
        
        url = f"{self.BASE_API}{endpoint}"
        params = params or {}
        params['access_token'] = self.access_token
        params['mature_content'] = 'true'
        
        retries = 0
        max_retries = 4
        backoff_delay = 2 

        while True:
            try:
                resp = self.session.get(url, params=params, timeout=20)
                
                # --- Handle Status Codes ---
                
                # 429: Rate Limit (Retry infinitely like 1.py)
                if resp.status_code == 429:
                    retry_after = resp.headers.get('Retry-After')
                    if retry_after:
                        sleep_time = int(retry_after) + 1
                    else:
                        sleep_time = 5 # Default sleep from 1.py
                    
                    self._log_once(sleep_time, f"   [DeviantArt] ⚠️ Rate limit (429). Sleeping {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue

                # 401: Token Expired (Refresh and Retry)
                if resp.status_code == 401: 
                    self.logger("   [DeviantArt] Token expired. Refreshing...")
                    if self.authenticate():
                        params['access_token'] = self.access_token
                        continue 
                    else:
                        raise Exception("Failed to refresh token")

                # 400, 403, 404: Client Errors (DO NOT RETRY)
                # These mean the file doesn't exist or isn't downloadable via this endpoint.
                if 400 <= resp.status_code < 500:
                    resp.raise_for_status() # This raises immediately, breaking the loop

                # 5xx: Server Errors (Retry)
                if 500 <= resp.status_code < 600:
                    resp.raise_for_status() # Will be caught by except block below for retry

                resp.raise_for_status()
                
                # Success - Clear logs
                with self.log_lock:
                    self.logged_waits.clear()
                        
                return resp.json()

            except requests.exceptions.HTTPError as e:
                # If it's a 4xx error (caught above), re-raise it immediately 
                # so get_deviation_content can switch to fallback logic.
                if e.response is not None and 400 <= e.response.status_code < 500:
                    raise e
                
                # Otherwise fall through to general retry logic (for 5xx)
                pass

            except requests.exceptions.RequestException as e:
                # Network errors / 5xx errors -> Retry
                if retries < max_retries:
                    self._log_once("conn_error", f"   [DeviantArt] Connection error: {e}. Retrying...")
                    time.sleep(backoff_delay)
                    retries += 1
                    continue
                raise e
    
    def _log_once(self, key, message):
        """Helper to avoid spamming the same log message during loops."""
        should_log = False
        with self.log_lock:
            if key not in self.logged_waits:
                self.logged_waits.add(key)
                should_log = True
        if should_log:
            self.logger(message)

    def get_deviation_uuid(self, url):
        """Scrapes the deviation page to find the UUID."""
        try:
            resp = self.session.get(url, timeout=15)
            match = re.search(r'"deviationUuid":"([^"]+)"', resp.text)
            if match:
                return match.group(1)
            match = re.search(r'-(\d+)$', url)
            if match:
                return match.group(1)
        except Exception as e:
            self.logger(f"Error scraping UUID: {e}")
        return None

    def get_deviation_content(self, uuid):
        """Fetches download info."""
        # 1. Try high-res download endpoint
        try:
            data = self._api_call(f"/deviation/download/{uuid}")
            if 'src' in data:
                return data
        except:
            # If 400/403 (Not downloadable), we fail silently here 
            # and proceed to step 2 (Metadata fallback)
            pass
        
        # 2. Fallback to standard content
        try:
            meta = self._api_call(f"/deviation/{uuid}")
            if 'content' in meta:
                return meta['content']
        except:
            pass
        return None

    def get_gallery_folder(self, username, offset=0, limit=24):
        """Fetches items from a user's gallery."""
        return self._api_call("/gallery/all", {"username": username, "offset": offset, "limit": limit})

    @staticmethod
    def extract_info_from_url(url):
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        parts = path.split('/')
        
        if len(parts) >= 3 and parts[1] == 'art':
            return 'post', parts[0], parts[2]
        elif len(parts) >= 2 and parts[1] == 'gallery':
            return 'gallery', parts[0], None
        elif len(parts) == 1:
            return 'gallery', parts[0], None
            
        return None, None, None