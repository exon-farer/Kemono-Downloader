import os
import re


KNOWN_NAMES = []

MAX_FILENAME_COMPONENT_LENGTH = 150

IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.jpe', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp',
    '.heic', '.heif', '.svg', '.ico', '.jfif', '.pjpeg', '.pjp', '.avif'
}
VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.mkv', '.webm', '.avi', '.wmv', '.flv', '.mpeg',
    '.mpg', '.m4v', '.3gp', '.ogv', '.ts', '.vob'
}
ARCHIVE_EXTENSIONS = {
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.bin'
}
AUDIO_EXTENSIONS = {
    '.mp3', '.wav', '.aac', '.flac', '.ogg', '.wma', '.m4a', '.opus',
    '.aiff', '.ape', '.mid', '.midi'
}

FOLDER_NAME_STOP_WORDS = {
    "a", "alone", "am", "an", "and", "at", "be", "blues", "but", "by", "com",
    "for", "grown", "hard", "he", "her", "his", "hitting", "i", "im", "in", "is", "it", "its",
    "me", "much", "my", "net", "not", "of", "on", "or", "org", "our", "please",
    "right", "s", "she", "so", "technically", "tell", "the", "their", "they", "this",
    "to", "ve", "was", "we", "well", "were", "with", "www", "year", "you", "your",
}


def clean_folder_name(name):
    """
    Sanitizes a string to make it a valid folder name.
    Removes invalid characters and trims whitespace.
    """
    if not isinstance(name, str):
        name = str(name)
    
    cleaned = re.sub(r'[<>:"/\\|?*]', '', name)
    cleaned = cleaned.strip()
    
    cleaned = re.sub(r'\s+', ' ', cleaned)

    if not cleaned:
        return "untitled_folder"

    if len(cleaned) > MAX_FILENAME_COMPONENT_LENGTH:
        cleaned = cleaned[:MAX_FILENAME_COMPONENT_LENGTH]

    cleaned = cleaned.rstrip('. ')

    return cleaned if cleaned else "untitled_folder"


def clean_filename(name):
    """
    Sanitizes a string to make it a valid file name.
    """
    if not isinstance(name, str):
        name = str(name)
        
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', name)
    cleaned = cleaned.strip()
    
    if not cleaned:
        return "untitled_file"
        
    base_name, ext = os.path.splitext(cleaned)
    max_base_len = MAX_FILENAME_COMPONENT_LENGTH - len(ext)

    if len(base_name) > max_base_len:
        if max_base_len > 0:
            base_name = base_name[:max_base_len]
        else:
            return cleaned[:MAX_FILENAME_COMPONENT_LENGTH]
    
    return base_name + ext



def is_image(filename):
    if not filename: return False
    _, ext = os.path.splitext(filename)
    return ext.lower() in IMAGE_EXTENSIONS

def is_video(filename):
    if not filename: return False
    _, ext = os.path.splitext(filename)
    return ext.lower() in VIDEO_EXTENSIONS

def is_zip(filename):
    if not filename: return False
    return filename.lower().endswith('.zip')

def is_rar(filename):
    if not filename: return False
    return filename.lower().endswith('.rar')

def is_archive(filename):
    if not filename: return False
    _, ext = os.path.splitext(filename)
    return ext.lower() in ARCHIVE_EXTENSIONS

def is_audio(filename):
    if not filename: return False
    _, ext = os.path.splitext(filename)
    return ext.lower() in AUDIO_EXTENSIONS


def get_known_names(filepath):
    """
    Reads Known.txt and supports both standard lines and (alias) groups.
    The FIRST name in the parentheses becomes the Master Folder Name.
    """
    known_characters = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): 
                    continue
                
                if line.startswith('(') and line.endswith(')'):
                    raw_names = re.split(r'\s*,\s*', line[1:-1])
                    aliases = [name.strip() for name in raw_names if name.strip()]
                    
                    if aliases:
                        known_characters.append({
                            'name': aliases[0], 
                            'aliases': aliases
                        })
                else:
                    known_characters.append({
                        'name': line,
                        'aliases': [line]
                    })
                    
        return known_characters
        
    except FileNotFoundError:
        print(f"Warning: Could not find {filepath}")
        return []