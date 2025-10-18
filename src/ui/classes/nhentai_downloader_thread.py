import os
import time
import cloudscraper
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

    def run(self):
        title = self.gallery_data.get("title", {}).get("english", f"gallery_{self.gallery_data.get('id')}")
        gallery_id = self.gallery_data.get("id")
        media_id = self.gallery_data.get("media_id")
        pages_info = self.gallery_data.get("pages", [])

        folder_name = clean_folder_name(title)
        gallery_path = os.path.join(self.output_dir, folder_name)

        try:
            os.makedirs(gallery_path, exist_ok=True)
        except OSError as e:
            self.progress_signal.emit(f"❌ Critical error creating directory: {e}")
            self.finished_signal.emit(0, len(pages_info), False)
            return

        self.progress_signal.emit(f"⬇️ Downloading '{title}' to folder '{folder_name}'...")

        scraper = cloudscraper.create_scraper()
        download_count = 0
        skip_count = 0

        for i, page_data in enumerate(pages_info):
            if self.is_cancelled:
                break

            page_num = i + 1
            
            ext_char = page_data.get('t', 'j')
            extension = self.EXTENSION_MAP.get(ext_char, 'jpg')
            
            relative_path = f"/galleries/{media_id}/{page_num}.{extension}"
            
            local_filename = f"{page_num:03d}.{extension}"
            filepath = os.path.join(gallery_path, local_filename)

            if os.path.exists(filepath):
                self.progress_signal.emit(f"   -> Skip (Exists): {local_filename}")
                skip_count += 1
                continue

            download_successful = False
            for server in self.IMAGE_SERVERS:
                if self.is_cancelled:
                    break
                
                full_url = f"{server}{relative_path}"
                try:
                    self.progress_signal.emit(f"   Downloading page {page_num}/{len(pages_info)} from {server} ...")
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                        'Referer': f'https://nhentai.net/g/{gallery_id}/'
                    }

                    response = scraper.get(full_url, headers=headers, timeout=60, stream=True)
                    
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        download_count += 1
                        download_successful = True
                        break
                    else:
                        self.progress_signal.emit(f"      -> {server} returned status {response.status_code}. Trying next server...")

                except Exception as e:
                    self.progress_signal.emit(f"      -> {server} failed to connect or timed out: {e}. Trying next server...")
            
            if not download_successful:
                self.progress_signal.emit(f"   ❌ Failed to download {local_filename} from all servers.")
                skip_count += 1

            time.sleep(0.5)

        self.finished_signal.emit(download_count, skip_count, self.is_cancelled)

    def cancel(self):
        self.is_cancelled = True