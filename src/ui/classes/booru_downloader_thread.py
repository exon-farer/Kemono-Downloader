import os
import threading
import time
import datetime
import requests
from PyQt5.QtCore import QThread, pyqtSignal

from ...core.booru_client import fetch_booru_data, BooruClientException
from ...utils.file_utils import clean_folder_name

_ff_ver = (datetime.date.today().toordinal() - 735506) // 28
USERAGENT_FIREFOX = (f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; "
                     f"rv:{_ff_ver}.0) Gecko/20100101 Firefox/{_ff_ver}.0")

class BooruDownloadThread(QThread):
    """A dedicated QThread for handling Danbooru and Gelbooru downloads."""
    progress_signal = pyqtSignal(str)
    overall_progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(int, int, bool) # dl_count, skip_count, cancelled

    def __init__(self, url, output_dir, api_key, user_id, parent=None):
        super().__init__(parent)
        self.booru_url = url
        self.output_dir = output_dir
        self.api_key = api_key
        self.user_id = user_id
        self.is_cancelled = False
        self.pause_event = parent.pause_event if hasattr(parent, 'pause_event') else threading.Event()

    def run(self):
        download_count = 0
        skip_count = 0
        processed_count = 0
        cumulative_total = 0
        
        def logger(msg):
            self.progress_signal.emit(str(msg))

        try:
            self.progress_signal.emit("=" * 40)
            self.progress_signal.emit(f"🚀 Starting Booru Download for: {self.booru_url}")
            
            item_generator = fetch_booru_data(self.booru_url, self.api_key, self.user_id, logger)
            
            download_path = self.output_dir # Default path
            path_initialized = False
            
            session = requests.Session()
            session.headers["User-Agent"] = USERAGENT_FIREFOX

            for item in item_generator:
                if self.is_cancelled:
                    break

                if isinstance(item, tuple) and item[0] == 'PAGE_UPDATE':
                    newly_found = item[1]
                    cumulative_total += newly_found
                    self.progress_signal.emit(f"   Found {newly_found} more posts. Total so far: {cumulative_total}")
                    self.overall_progress_signal.emit(cumulative_total, processed_count)
                    continue

                post_data = item
                processed_count += 1

                if not path_initialized:
                    base_folder_name = post_data.get('search_tags', 'booru_download')
                    download_path = os.path.join(self.output_dir, clean_folder_name(base_folder_name))
                    os.makedirs(download_path, exist_ok=True)
                    path_initialized = True
                
                if self.pause_event.is_set():
                    self.progress_signal.emit("   Download paused...")
                    while self.pause_event.is_set():
                        if self.is_cancelled: break
                        time.sleep(0.5)
                    if self.is_cancelled: break
                    self.progress_signal.emit("   Download resumed.")

                file_url = post_data.get('file_url')
                if not file_url:
                    skip_count += 1
                    self.progress_signal.emit(f"   -> Skip ({processed_count}/{cumulative_total}): Post ID {post_data.get('id')} has no file URL.")
                    continue

                cat = post_data.get('category', 'booru')
                post_id = post_data.get('id', 'unknown')
                md5 = post_data.get('md5', '')
                fname = post_data.get('filename', f"file_{post_id}")
                ext = post_data.get('extension', 'jpg')
                
                final_filename = f"{cat}_{post_id}_{md5 or fname}.{ext}"
                filepath = os.path.join(download_path, final_filename)

                if os.path.exists(filepath):
                    self.progress_signal.emit(f"   -> Skip ({processed_count}/{cumulative_total}): '{final_filename}' already exists.")
                    skip_count += 1
                else:
                    try:
                        self.progress_signal.emit(f"   Downloading ({processed_count}/{cumulative_total}): '{final_filename}'...")
                        response = session.get(file_url, stream=True, timeout=60)
                        response.raise_for_status()
                        
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if self.is_cancelled: break
                                f.write(chunk)
                        
                        if not self.is_cancelled:
                            download_count += 1
                        else:
                            if os.path.exists(filepath): os.remove(filepath)
                            skip_count += 1
                            
                    except Exception as e:
                        self.progress_signal.emit(f"   ❌ Failed to download '{final_filename}': {e}")
                        skip_count += 1
                
                self.overall_progress_signal.emit(cumulative_total, processed_count)
                time.sleep(0.2)

            if not path_initialized:
                self.progress_signal.emit("No posts found for the given URL/tags.")

        except BooruClientException as e:
            self.progress_signal.emit(f"❌ A Booru client error occurred: {e}")
        except Exception as e:
            self.progress_signal.emit(f"❌ An unexpected error occurred in Booru thread: {e}")
        finally:
            self.finished_signal.emit(download_count, skip_count, self.is_cancelled)

    def cancel(self):
        self.is_cancelled = True
        self.progress_signal.emit("   Cancellation signal received by Booru thread.")