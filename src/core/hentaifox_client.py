import requests
import re
from bs4 import BeautifulSoup 


BASE_URL = "https://hentaifox.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Referer": "https://hentaifox.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

def get_gallery_id(url_or_id):
    """Extracts numbers from URL or returns the ID string."""
    match = re.search(r"(\d+)", str(url_or_id))
    return match.group(1) if match else None

def get_gallery_metadata(gallery_id):
    """
    Fetches the main gallery page to get the Title and Total Pages.
    Equivalent to the first part of the 'hentaifox' function in .sh file.
    """
    url = f"{BASE_URL}/gallery/{gallery_id}/"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    html = response.text
    

    title_match = re.search(r'<title>(.*?)</title>', html)
    title = title_match.group(1).replace(" - HentaiFox", "").strip() if title_match else f"Gallery {gallery_id}"

    pages_match = re.search(r'Pages: (\d+)', html)
    if not pages_match:
        raise ValueError("Could not find total pages count.")
    
    total_pages = int(pages_match.group(1))
    
    return {
        "id": gallery_id,
        "title": title,
        "total_pages": total_pages
    }

def get_image_link_for_page(gallery_id, page_num):
    """
    Fetches the specific reader page to find the actual image URL.
    Equivalent to the loop in the 'hentaifox' function:
    url="https://hentaifox.com/g/${id}/${i}/"
    """
    url = f"{BASE_URL}/g/{gallery_id}/{page_num}/"
    response = requests.get(url, headers=HEADERS)
    
    # Extract image source (Bash: grep -Eo 'data-src="..."')
    # Regex looks for: data-src="https://..."
    match = re.search(r'data-src="(https://[^"]+)"', response.text)
    
    if match:
        return match.group(1)
    return None