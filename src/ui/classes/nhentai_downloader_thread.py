import os
import time
import requests 
from PyQt5.QtCore import QThread, pyqtSignal

from ...utils.file_utils import clean_folder_name


class NhentaiDownloadThread(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int, int, bool)

    IMAGE_SERVERS = [
        "https://i.nhentai.net", "https://i2.nhentai.net", "https://i3.nhentai.net",
        "https://i5.nhentai.net", "https://i7.nhentai.net"
    ]
    
    EXTENSION_MAP = {'j': 'jpg', 'p': 'png', 'g': 'gif', 'w': 'webp' }

    def __init__(self, gallery_data, output_dir, parent=None):
        super().__init__(parent)
        self.gallery_data = gallery_data
        self.output_dir = output_dir
        self.is_cancelled = False
        self.proxies = None

    def run(self):
        if self.proxies:
            self.progress_signal.emit(f"   🌍 Network: Using Proxy {self.proxies}")
        else:
            self.progress_signal.emit("   🌍 Network: Direct Connection (No Proxy)")

        title = self.gallery_data.get("title", {}).get("english", f"gallery_{self.gallery_data.get('id')}")
        gallery_id = self.gallery_data.get("id")
        media_id = self.gallery_data.get("media_id")
        pages_info = self.gallery_data.get("pages", [])

        folder_name = clean_folder_name(title)
        save_path = os.path.join(self.output_dir, folder_name)
        
        try:
            os.makedirs(save_path, exist_ok=True)
            self.progress_signal.emit(f"   Saving to: {folder_name}")
        except Exception as e:
            self.progress_signal.emit(f"   ❌ Error creating directory: {e}")
            self.finished_signal.emit(0, len(pages_info), False)
            return

        download_count = 0
        skip_count = 0
        total_pages = len(pages_info)

        scraper = requests.Session()
        
        img_timeout = (30, 120) if self.proxies else 60

        for i, page_data in enumerate(pages_info):
            if self.is_cancelled: break
            
            file_ext = self.EXTENSION_MAP.get(page_data.get('t'), 'jpg')
            local_filename = f"{i+1:03d}.{file_ext}"
            filepath = os.path.join(save_path, local_filename)

            if os.path.exists(filepath):
                self.progress_signal.emit(f"   Skipping {local_filename} (already exists).")
                skip_count += 1
                continue

            download_successful = False
            
            for server in self.IMAGE_SERVERS:
                if self.is_cancelled: break
                
                full_url = f"{server}/galleries/{media_id}/{i+1}.{file_ext}"
                
                try:
                    self.progress_signal.emit(f"   Downloading page {i+1}/{total_pages}...")
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Referer': f'https://nhentai.net/g/{gallery_id}/'
                    }

                    response = scraper.get(full_url, headers=headers, timeout=img_timeout, stream=True, proxies=self.proxies, verify=False)
                    
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        download_count += 1
                        download_successful = True
                        break
                    else:
                        pass 

                except Exception as e:
                    pass
            
            if not download_successful:
                self.progress_signal.emit(f"   ❌ Failed to download {local_filename} from all servers.")
                skip_count += 1

            time.sleep(0.5)

        self.finished_signal.emit(download_count, skip_count, self.is_cancelled)

    def cancel(self):
        self.is_cancelled = True