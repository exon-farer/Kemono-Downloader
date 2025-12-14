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
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
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
                
                # Handle Token Expiration (401)
                if resp.status_code == 401: 
                    self.logger("   [DeviantArt] Token expired. Refreshing...")
                    if self.authenticate():
                        params['access_token'] = self.access_token
                        continue 
                    else:
                        raise Exception("Failed to refresh token")

                # Handle Rate Limiting (429)
                if resp.status_code == 429:
                    if retries < max_retries:
                        retry_after = resp.headers.get('Retry-After')
                        
                        if retry_after:
                            sleep_time = int(retry_after) + 1
                            msg = f"   [DeviantArt] ⚠️ Rate limit (Server says wait {sleep_time}s)."
                        else:
                            sleep_time = backoff_delay * (2 ** retries)
                            msg = f"   [DeviantArt] ⚠️ Rate limit reached. Retrying in {sleep_time}s..."
                        
                        # --- THREAD-SAFE LOGGING CHECK ---
                        should_log = False
                        with self.log_lock:
                            if sleep_time not in self.logged_waits:
                                self.logged_waits.add(sleep_time)
                                should_log = True
                        
                        if should_log:
                            self.logger(msg)
                        
                        time.sleep(sleep_time)
                        retries += 1
                        continue
                    else:
                        resp.raise_for_status()

                resp.raise_for_status()
                
                # Clear log history on success so we get warned again if limits return later
                with self.log_lock:
                    if self.logged_waits:
                        self.logged_waits.clear()
                        
                return resp.json()

            except requests.exceptions.RequestException as e:
                if retries < max_retries:
                    # Using the lock here too to prevent connection error spam
                    should_log = False
                    with self.log_lock:
                        if "conn_error" not in self.logged_waits:
                            self.logged_waits.add("conn_error")
                            should_log = True
                    
                    if should_log:
                        self.logger(f"   [DeviantArt] Connection error: {e}. Retrying...")
                    
                    time.sleep(2)
                    retries += 1
                    continue
                raise e

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
        try:
            data = self._api_call(f"/deviation/download/{uuid}")
            if 'src' in data:
                return data
        except:
            pass
        
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