# --- Standard Library Imports ---
import re
import html

# --- Local Application Imports ---
# Import from file_utils within the same package
from .file_utils import clean_folder_name, FOLDER_NAME_STOP_WORDS

# --- Module Constants ---

# Regular expression patterns for cleaning up titles before matching against Known.txt
KNOWN_TXT_MATCH_CLEANUP_PATTERNS = [
    r'\bcum\b',
    r'\bnsfw\b',
    r'\bsfw\b',
    r'\bweb\b',
    r'\bhd\b',
    r'\bhi\s*res\b',
    r'\bhigh\s*res\b',
    r'\b\d+p\b',
    r'\b\d+k\b',
    r'\[OC\]',
    r'\[Request(?:s)?\]',
    r'\bCommission\b',
    r'\bComm\b',
    r'\bPreview\b',
]

# --- START NEW CODE ---
# Regular expression to detect CJK characters
# Covers Hiragana, Katakana, Half/Full width forms, CJK Unified Ideographs, Hangul Syllables, etc.
cjk_pattern = re.compile(r'[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uffef\u4e00-\u9fff\uac00-\ud7af]')

def contains_cjk(text):
    """Checks if the text contains any CJK characters."""
    return bool(cjk_pattern.search(text))
# --- END NEW CODE ---

# --- Text Matching and Manipulation Utilities ---

def is_title_match_for_character(post_title, character_name_filter):
    """
    Checks if a post title contains a specific character name as a whole word.
    Case-insensitive.

    Args:
        post_title (str): The title of the post.
        character_name_filter (str): The character name to search for.

    Returns:
        bool: True if the name is found as a whole word, False otherwise.
    """
    if not post_title or not character_name_filter:
        return False

    # Use word boundaries (\b) to match whole words only
    pattern = r"(?i)\b" + re.escape(str(character_name_filter).strip()) + r"\b"
    return bool(re.search(pattern, post_title))


def is_filename_match_for_character(filename, character_name_filter):
    """
    Checks if a filename contains a character name. This is a simple substring check.
    Case-insensitive.

    Args:
        filename (str): The name of the file.
        character_name_filter (str): The character name to search for.

    Returns:
        bool: True if the substring is found, False otherwise.
    """
    if not filename or not character_name_filter:
        return False

    return str(character_name_filter).strip().lower() in filename.lower()


def strip_html_tags(html_text):
    """
    Removes HTML tags from a string and cleans up resulting whitespace.

    Args:
        html_text (str): The input string containing HTML.

    Returns:
        str: The text with HTML tags removed.
    """
    if not html_text:
        return ""
    # First, unescape HTML entities like &amp; -> &
    text = html.unescape(str(html_text))
    # Remove all tags
    text_after_tag_removal = re.sub(r'<[^>]+>', ' ', text)
    # Replace multiple whitespace characters with a single space
    cleaned_text = re.sub(r'\s+', ' ', text_after_tag_removal).strip()
    return cleaned_text


def extract_folder_name_from_title(title, unwanted_keywords):
    """
    Extracts a plausible folder name from a post title by finding the first
    significant word that isn't a stop-word.

    Args:
        title (str): The post title.
        unwanted_keywords (set): A set of words to ignore.

    Returns:
        str: The extracted folder name, or 'Uncategorized'.
    """
    if not title:
        return 'Uncategorized'

    title_lower = title.lower()
    # Find all whole words in the title
    tokens = re.findall(r'\b[\w\-]+\b', title_lower)

    for token in tokens:
        clean_token = clean_folder_name(token)
        if clean_token and clean_token.lower() not in unwanted_keywords:
            return clean_token

    # Fallback to cleaning the full title if no single significant word is found
    cleaned_full_title = clean_folder_name(title)
    return cleaned_full_title if cleaned_full_title else 'Uncategorized'


def match_folders_from_title(title, names_to_match, unwanted_keywords):
    """
    Matches folder names from a title based on a list of known name objects.
    Each name object is a dict: {'name': 'PrimaryName', 'aliases': ['alias1', ...]}
    MODIFIED: Uses substring matching for CJK aliases, word boundary for others.

    Args:
        title (str): The post title to check.
        names_to_match (list): A list of known name dictionaries.
        unwanted_keywords (set): A set of folder names to ignore.

    Returns:
        list: A sorted list of matched primary folder names.
    """
    if not title or not names_to_match:
        return []

    # Clean the title by removing common tags like [OC], [HD], etc.
    cleaned_title = title
    for pat_str in KNOWN_TXT_MATCH_CLEANUP_PATTERNS:
        cleaned_title = re.sub(pat_str, ' ', cleaned_title, flags=re.IGNORECASE)
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    # Store both original case cleaned title and lower case for different matching
    title_lower = cleaned_title.lower()

    matched_cleaned_names = set()

    # Sort by name length descending to match longer names first (e.g., "Cloud Strife" before "Cloud")
    sorted_name_objects = sorted(names_to_match, key=lambda x: len(x.get("name", "")), reverse=True)

    for name_obj in sorted_name_objects:
        primary_folder_name = name_obj.get("name")
        aliases = name_obj.get("aliases", [])
        if not primary_folder_name or not aliases:
            continue

        # <<< START MODIFICATION >>>
        cleaned_primary_name = clean_folder_name(primary_folder_name)
        if not cleaned_primary_name or cleaned_primary_name.lower() in unwanted_keywords:
            continue # Skip this entry entirely if its primary name is unwanted or empty

        match_found_for_this_object = False
        for alias in aliases:
            if not alias: continue
            alias_lower = alias.lower()

            # Check if the alias contains CJK characters
            if contains_cjk(alias):
                # Use simple substring matching for CJK
                if alias_lower in title_lower:
                    matched_cleaned_names.add(cleaned_primary_name)
                    match_found_for_this_object = True
                    break # Move to the next name object
            else:
                # Use original word boundary matching for non-CJK
                try:
                    # Compile pattern for efficiency if used repeatedly, though here it changes each loop
                    pattern = r'\b' + re.escape(alias_lower) + r'\b'
                    if re.search(pattern, title_lower):
                        matched_cleaned_names.add(cleaned_primary_name)
                        match_found_for_this_object = True
                        break # Move to the next name object
                except re.error as e:
                    # Log error if the alias creates an invalid regex (unlikely with escape)
                    print(f"Regex error for alias '{alias}': {e}") # Or use proper logging
                    continue

        # This outer break logic remains the same (though slightly redundant with inner breaks)
        if match_found_for_this_object:
             pass # Already added and broke inner loop
        # <<< END MODIFICATION >>>

    return sorted(list(matched_cleaned_names))


def match_folders_from_filename_enhanced(filename, names_to_match, unwanted_keywords):
    """
    Matches folder names from a filename, prioritizing longer and more specific aliases.
    It returns immediately after finding the first (longest) match.
    MODIFIED: Prioritizes boundary-aware matches for Latin characters,
    falls back to substring search for CJK compatibility.

    Args:
        filename (str): The filename to check.
        names_to_match (list): A list of known name dictionaries.
        unwanted_keywords (set): A set of folder names to ignore.

    Returns:
        list: A list containing the single best folder name match, or an empty list.
    """
    if not filename or not names_to_match:
        return []

    filename_lower = filename.lower()

    # Create a flat list of (alias, primary_name) tuples
    alias_map_to_primary = []
    for name_obj in names_to_match:
        primary_name = name_obj.get("name")
        if not primary_name: continue

        cleaned_primary_name = clean_folder_name(primary_name)
        if not cleaned_primary_name or cleaned_primary_name.lower() in unwanted_keywords:
            continue

        for alias in name_obj.get("aliases", []):
            if alias: # Check if alias is not None and not an empty string
                alias_lower_val = alias.lower()
                if alias_lower_val: # Check again after lowercasing
                    alias_map_to_primary.append((alias_lower_val, cleaned_primary_name))

    # Sort by alias length, descending, to match longer aliases first
    alias_map_to_primary.sort(key=lambda x: len(x[0]), reverse=True)

    # Return the FIRST match found, which will be the longest
    for alias_lower, primary_name_for_alias in alias_map_to_primary:
        try:
            # 1. Attempt boundary-aware match first (good for English/Latin)
            # Matches alias if it's at the start/end or surrounded by common separators
            # We use word boundaries (\b) and also check for common non-word separators like +_-
            pattern = r'(?:^|[\s_+-])' + re.escape(alias_lower) + r'(?:[\s_+-]|$)'
            
            if re.search(pattern, filename_lower):
                # Found a precise, boundary-aware match. This is the best case.
                return [primary_name_for_alias]

            # 2. Fallback: Simple substring check (for CJK or other cases)
            # This executes ONLY if the boundary match above failed.
            # We check if the alias contains CJK OR if the filename does.
            # This avoids applying the simple 'in' check for Latin-only aliases in Latin-only filenames.
            elif (contains_cjk(alias_lower) or contains_cjk(filename_lower)) and alias_lower in filename_lower:
                # This is the fallback for CJK compatibility.
                return [primary_name_for_alias]
                
            # If alias is "ul" and filename is "sin+título":
            # 1. re.search(r'(?:^|[\s_+-])ul(?:[\s_+-]|$)', "sin+título") -> Fails (good)
            # 2. contains_cjk("ul") -> False
            # 3. contains_cjk("sin+título") -> False
            # 4. No match is found for "ul". (correct)

        except re.error as e:
            print(f"Regex error matching alias '{alias_lower}' in filename '{filename_lower}': {e}")
            continue # Skip this alias if regex fails

    # If the loop finishes without any matches, return an empty list.
    return []