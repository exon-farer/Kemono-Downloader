import os
import json
import requests
from urllib.parse import urlparse, parse_qs
from PyQt5.QtCore import QThread

class Rule34DownloadThread(QThread):
    def __init__(self, url, output_dir, api_key="", user_id="", parent=None):
        super().__init__(parent)
        self.url = url
        self.output_dir = output_dir
        self.api_key = api_key
        self.user_id = user_id
        self.main_app = parent
        self.session = requests.Session()
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def run(self):
        parsed_url = urlparse(self.url)
        query_params = parse_qs(parsed_url.query)
        tags = query_params.get('tags', [''])[0]
        
        if not tags:
            self.main_app.log_signal.emit("❌ Error: No tags found in the URL.")
            return

        self.main_app.log_signal.emit(f"🚀 Starting download for tags: {tags}")

        pid = 0
        limit = 1000
        total_count = 0

        while True:
            if self.main_app.cancellation_event.is_set():
                break

            api_url = f"https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&tags={tags}&json=1&limit={limit}&pid={pid}"
            
            if self.user_id and self.api_key:
                api_url += f"&user_id={self.user_id}&api_key={self.api_key}"
            else:
                self.main_app.log_signal.emit("⚠️ Warning: No User ID or API Key provided in the app. The server might reject the request.")
            
            try:
                response = self.session.get(api_url, timeout=15)
                response.raise_for_status()
                
                if not response.text.strip():
                    break

                posts = response.json()
                
                if isinstance(posts, str):
                    try:
                        posts = json.loads(posts)
                    except json.JSONDecodeError:
                        self.main_app.log_signal.emit(f"⚠️ API Message: {posts}")
                        break

                if isinstance(posts, dict):
                    posts = posts.get('post', [])

                if not isinstance(posts, list):
                    self.main_app.log_signal.emit(f"❌ API returned an unrecognized format: {type(posts).__name__}")
                    break

                if len(posts) == 0:
                    break

                self.main_app.log_signal.emit(f"📦 Processing page {pid + 1} ({len(posts)} items)...")

                for post in posts:
                    if self.main_app.cancellation_event.is_set():
                        break

                    if not isinstance(post, dict):
                        self.main_app.log_signal.emit(f"⚠️ Skipping invalid post data: {str(post)[:50]}")
                        continue

                    file_url = post.get('file_url')
                    if not file_url:
                        continue

                    ext = os.path.splitext(urlparse(file_url).path)[1]
                    filename = f"{post.get('id')}{ext}"
                    save_path = os.path.join(self.output_dir, filename)

                    if not os.path.exists(save_path):
                        self.download_file(file_url, save_path)
                        total_count += 1

                pid += 1

            except Exception as e:
                self.main_app.log_signal.emit(f"❌ API Error on page {pid}: {e}")
                break

        self.main_app.log_signal.emit(f"✅ Finished! Downloaded {total_count} files for tags: {tags}")

    def download_file(self, url, save_path):
        """Helper method to download and save the actual image/video file."""
        try:
            response = self.session.get(url, stream=True, timeout=20)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.main_app.cancellation_event.is_set():
                        break
                    if chunk:
                        f.write(chunk)
                        
            if self.main_app.cancellation_event.is_set():
                if os.path.exists(save_path):
                    os.remove(save_path)
            else:
                self.main_app.log_signal.emit(f"⬇️ Downloaded: {os.path.basename(save_path)}")
                
        except Exception as e:
            self.main_app.log_signal.emit(f"❌ Failed to download {url}: {e}")