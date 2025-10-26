import re
import os
import time 
import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import queue

def run_hentai2read_download(start_url, output_dir, progress_callback, overall_progress_callback, check_pause_func):
    """
    Orchestrates the download process using a producer-consumer model.
    The main thread scrapes image URLs and puts them in a queue.
    A pool of worker threads consumes from the queue to download images concurrently.
    """
    scraper = cloudscraper.create_scraper()
    
    try:
        progress_callback("   [Hentai2Read] Scraping series page for all metadata...")
        top_level_folder_name, chapters_to_process = _get_series_metadata(start_url, progress_callback, scraper)

        if not chapters_to_process:
            progress_callback("❌ No chapters found to download. Aborting.")
            return 0, 0
        
        total_chapters = len(chapters_to_process)
        overall_progress_callback(total_chapters, 0)
        
        total_downloaded_count = 0
        total_skipped_count = 0

        for idx, chapter in enumerate(chapters_to_process):
            if check_pause_func(): break

            progress_callback(f"\n-- Processing and Downloading Chapter {idx + 1}/{total_chapters}: '{chapter['title']}' --")
            
            series_folder = re.sub(r'[\\/*?:"<>|]', "", top_level_folder_name).strip()
            chapter_folder = re.sub(r'[\\/*?:"<>|]', "", chapter['title']).strip()
            final_save_path = os.path.join(output_dir, series_folder, chapter_folder)
            os.makedirs(final_save_path, exist_ok=True)
            
            # This function now scrapes and downloads simultaneously
            dl_count, skip_count = _process_and_download_chapter(
                chapter_url=chapter['url'],
                save_path=final_save_path,
                scraper=scraper,
                progress_callback=progress_callback,
                check_pause_func=check_pause_func
            )

            total_downloaded_count += dl_count
            total_skipped_count += skip_count
            
            overall_progress_callback(total_chapters, idx + 1)
            if check_pause_func(): break
        
        return total_downloaded_count, total_skipped_count

    except Exception as e:
        progress_callback(f"❌ A critical error occurred in the Hentai2Read client: {e}")
        return 0, 0

def _get_series_metadata(start_url, progress_callback, scraper):
    """
    Scrapes the main series page to get the Artist Name, Series Title, and chapter list.
    Includes a retry mechanism for the initial connection.
    """
    max_retries = 4  # Total number of attempts (1 initial + 3 retries)
    last_exception = None
    soup = None

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                progress_callback(f"   [Hentai2Read] ⚠️ Retrying connection (Attempt {attempt + 1}/{max_retries})...")
            
            response = scraper.get(start_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # If successful, clear exception and break the loop
            last_exception = None
            break

        except Exception as e:
            last_exception = e
            progress_callback(f"   [Hentai2Read] ⚠️ Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))  # Wait 2s, 4s, 6s
            continue  # Try again

    if last_exception:
        progress_callback(f"   [Hentai2Read] ❌ Error getting series metadata after {max_retries} attempts: {last_exception}")
        return "Unknown Series", []

    try:
        series_title = "Unknown Series"
        artist_name = None
        metadata_list = soup.select_one("ul.list.list-simple-mini")
        
        if metadata_list:
            first_li = metadata_list.find('li', recursive=False)
            if first_li and not first_li.find('a'):
                series_title = first_li.get_text(strip=True)

            for b_tag in metadata_list.find_all('b'):
                label = b_tag.get_text(strip=True)
                if label in ("Artist", "Author"):
                    a_tag = b_tag.find_next_sibling('a')
                    if a_tag:
                        artist_name = a_tag.get_text(strip=True)
                        if label == "Artist":
                            break
        
        top_level_folder_name = artist_name if artist_name else series_title
        
        chapter_links = soup.select("div.media a.pull-left.font-w600")
        if not chapter_links:
            chapters_to_process = [{'url': start_url, 'title': series_title}]
        else:
            chapters_to_process = [
                {'url': urljoin(start_url, link['href']), 'title': " ".join(link.stripped_strings)} 
                for link in chapter_links
            ]
            chapters_to_process.reverse()

        progress_callback(f"   [Hentai2Read] ✅ Found Artist/Series: '{top_level_folder_name}'")
        progress_callback(f"   [Hentai2Read] ✅ Found {len(chapters_to_process)} chapters to process.")
        
        return top_level_folder_name, chapters_to_process

    except Exception as e:
        progress_callback(f"   [Hentai2Read] ❌ Error parsing metadata after successful connection: {e}")
        return "Unknown Series", []

def _process_and_download_chapter(chapter_url, save_path, scraper, progress_callback, check_pause_func):
    """
    Uses a producer-consumer pattern to download a chapter.
    The main thread (producer) scrapes URLs one by one.
    Worker threads (consumers) download the URLs as they are found.
    """
    task_queue = queue.Queue()
    num_download_threads = 8
    
    download_stats = {'downloaded': 0, 'skipped': 0}

    def downloader_worker():
        """The function that each download thread will run."""
        worker_scraper = cloudscraper.create_scraper()
        while True:
            try:
                # Get a task from the queue
                task = task_queue.get()
                # The sentinel value to signal the end
                if task is None:
                    break
                
                filepath, img_url = task
                if os.path.exists(filepath):
                    progress_callback(f"   -> Skip: '{os.path.basename(filepath)}'")
                    download_stats['skipped'] += 1
                else:
                    progress_callback(f"   Downloading: '{os.path.basename(filepath)}'...")
                    response = worker_scraper.get(img_url, stream=True, timeout=60, headers={'Referer': chapter_url})
                    response.raise_for_status()
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    download_stats['downloaded'] += 1
            except Exception as e:
                progress_callback(f"   ❌ Download failed for task. Error: {e}")
                download_stats['skipped'] += 1
            finally:
                task_queue.task_done()

    executor = ThreadPoolExecutor(max_workers=num_download_threads, thread_name_prefix='H2R_Downloader')
    for _ in range(num_download_threads):
        executor.submit(downloader_worker)

    page_number = 1
    while True:
        if check_pause_func(): break
        if page_number > 300: # Safety break
            progress_callback("   [Hentai2Read] ⚠️ Safety break: Reached 300 pages.")
            break
        
        page_url_to_check = f"{chapter_url}{page_number}/"
        try:
            page_response = None
            page_last_exception = None
            for page_attempt in range(3): # 3 attempts for sub-pages
                try:
                    page_response = scraper.get(page_url_to_check, timeout=30)
                    page_last_exception = None
                    break
                except Exception as e:
                    page_last_exception = e
                    time.sleep(1) # Short delay for page scraping retries
            
            if page_last_exception:
                raise page_last_exception # Give up after 3 tries

            if page_response.history or page_response.status_code != 200:
                progress_callback(f"   [Hentai2Read] End of chapter detected on page {page_number}.")
                break

            soup = BeautifulSoup(page_response.text, 'html.parser')
            img_tag = soup.select_one("img#arf-reader")
            img_src = img_tag.get("src") if img_tag else None

            if not img_tag or img_src == "https://static.hentai.direct/hentai":
                progress_callback(f"   [Hentai2Read] End of chapter detected (Placeholder image on page {page_number}).")
                break
            
            normalized_img_src = urljoin(page_response.url, img_src)
            ext = os.path.splitext(normalized_img_src.split('/')[-1])[-1] or ".jpg"
            filename = f"{page_number:03d}{ext}"
            filepath = os.path.join(save_path, filename)
            
            task_queue.put((filepath, normalized_img_src))
            
            page_number += 1
            time.sleep(0.1) # Small delay between scraping pages
        except Exception as e:
            progress_callback(f"   [Hentai2Read] ❌ Error while scraping page {page_number}: {e}")
            break
            
    for _ in range(num_download_threads):
        task_queue.put(None)
    
    executor.shutdown(wait=True)
    
    progress_callback(f"   Found and processed {page_number - 1} images for this chapter.")
    return download_stats['downloaded'], download_stats['skipped']