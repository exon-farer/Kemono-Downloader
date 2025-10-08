# src/core/simpcity_client.py

import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote
import os
import re
from ..utils.file_utils import clean_folder_name
import urllib.parse 

def fetch_single_simpcity_page(url, logger_func, cookies=None, post_id=None):
    """
    Scrapes a single SimpCity page for images, external links, video tags, and iframes.
    """
    scraper = cloudscraper.create_scraper()
    headers = {'Referer': 'https://simpcity.cr/'}
    
    try:
        response = scraper.get(url, timeout=30, headers=headers, cookies=cookies)
        if response.status_code == 404:
            return None, []
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        album_title = None
        title_element = soup.find('h1', class_='p-title-value')
        if title_element:
            album_title = title_element.text.strip()
        
        search_scope = soup
        if post_id:
            post_content_container = soup.find('div', attrs={'data-lb-id': f'post-{post_id}'})
            if post_content_container:
                logger_func(f"   [SimpCity] ✅ Isolating search to post content container for ID {post_id}.")
                search_scope = post_content_container
            else:
                logger_func(f"   [SimpCity] ⚠️ Could not find content container for post ID {post_id}.")

        jobs_on_page = []

        # Find native SimpCity images
        image_tags = search_scope.find_all('img', class_='bbImage')
        for img_tag in image_tags:
            thumbnail_url = img_tag.get('src')
            if not thumbnail_url or not isinstance(thumbnail_url, str) or 'saint2.su' in thumbnail_url: continue
            full_url = thumbnail_url.replace('.md.', '.')
            filename = img_tag.get('alt', '').replace('.md.', '.') or os.path.basename(unquote(urlparse(full_url).path))
            jobs_on_page.append({'type': 'image', 'filename': filename, 'url': full_url})
            
        # Find links in <a> tags, now with redirect handling
        link_tags = search_scope.find_all('a', href=True)
        for link in link_tags:
            href = link.get('href', '')
            
            actual_url = href
            if '/misc/goto?url=' in href:
                try:
                    # Extract and decode the real URL from the 'url' parameter
                    parsed_href = urlparse(href)
                    query_params = dict(urllib.parse.parse_qsl(parsed_href.query))
                    if 'url' in query_params:
                        actual_url = unquote(query_params['url'])
                except Exception:
                    actual_url = href # Fallback if parsing fails
            
            # Perform all checks on the 'actual_url' which is now the real destination
            if re.search(r'pixeldrain\.com/[lud]/', actual_url): jobs_on_page.append({'type': 'pixeldrain', 'url': actual_url})
            elif re.search(r'saint2\.(su|pk|cr|to)/embed/', actual_url): jobs_on_page.append({'type': 'saint2', 'url': actual_url})
            elif re.search(r'bunkr\.(?:cr|si|la|ws|is|ru|su|red|black|media|site|to|ac|ci|fi|pk|ps|sk|ph)|bunkrr\.ru', actual_url): jobs_on_page.append({'type': 'bunkr', 'url': actual_url})
            elif re.search(r'mega\.(nz|io)', actual_url): jobs_on_page.append({'type': 'mega', 'url': actual_url})
            elif re.search(r'gofile\.io', actual_url): jobs_on_page.append({'type': 'gofile', 'url': actual_url})

        # Find direct Saint2 video embeds in <video> tags
        video_tags = search_scope.find_all('video')
        for video in video_tags:
            source_tag = video.find('source')
            if source_tag and source_tag.get('src'):
                src_url = source_tag['src']
                if re.search(r'saint2\.(su|pk|cr|to)', src_url):
                    jobs_on_page.append({'type': 'saint2_direct', 'url': src_url})
        
        # Find embeds in <iframe> tags (as a fallback)
        iframe_tags = search_scope.find_all('iframe')
        for iframe in iframe_tags:
            src_url = iframe.get('src')
            if src_url and isinstance(src_url, str):
                if re.search(r'saint2\.(su|pk|cr|to)/embed/', src_url):
                    jobs_on_page.append({'type': 'saint2', 'url': src_url})

        if jobs_on_page:
            # We use a set to remove duplicate URLs that might be found in multiple ways
            unique_jobs = list({job['url']: job for job in jobs_on_page}.values())
            logger_func(f"   [SimpCity] Scraper found jobs: {[job['type'] for job in unique_jobs]}")
            return album_title, unique_jobs

        return album_title, []

    except Exception as e:
        logger_func(f"   [SimpCity] ❌ Error fetching page {url}: {e}")
        raise e