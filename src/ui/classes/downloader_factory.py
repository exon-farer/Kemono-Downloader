import re
import requests
from urllib.parse import urlparse

# Utility Imports
from ...utils.network_utils import prepare_cookies_for_request
from ...utils.file_utils import clean_folder_name 

# Downloader Thread Imports (Alphabetical Order Recommended)
from .allcomic_downloader_thread import AllcomicDownloadThread
from .booru_downloader_thread import BooruDownloadThread
from .bunkr_downloader_thread import BunkrDownloadThread
from .discord_downloader_thread import DiscordDownloadThread # Official Discord
from .drive_downloader_thread import DriveDownloadThread
from .erome_downloader_thread import EromeDownloadThread
from .external_link_downloader_thread import ExternalLinkDownloadThread
from .fap_nation_downloader_thread import FapNationDownloadThread
from .hentai2read_downloader_thread import Hentai2readDownloadThread
from .kemono_discord_downloader_thread import KemonoDiscordDownloadThread
from .mangadex_downloader_thread import MangaDexDownloadThread
from .nhentai_downloader_thread import NhentaiDownloadThread
from .pixeldrain_downloader_thread import PixeldrainDownloadThread
from .rule34video_downloader_thread import Rule34VideoDownloadThread
from .saint2_downloader_thread import Saint2DownloadThread
from .simp_city_downloader_thread import SimpCityDownloadThread
from .toonily_downloader_thread import ToonilyDownloadThread
from .deviantart_downloader_thread import DeviantArtDownloadThread
from .hentaifox_downloader_thread import HentaiFoxDownloadThread

def create_downloader_thread(main_app, api_url, service, id1, id2, effective_output_dir_for_run):
    """
    Factory function to create and configure the correct QThread for a given URL.
    Returns a configured QThread instance, a specific error string ("COOKIE_ERROR", "FETCH_ERROR"),
    or None if no special handler is found (indicating fallback to generic BackendDownloadThread).
    """


    # Handler for Booru sites (Danbooru, Gelbooru)
    if service in ['danbooru', 'gelbooru']:
        api_key = main_app.api_key_input.text().strip()
        user_id = main_app.user_id_input.text().strip()
        return BooruDownloadThread(
            url=api_url, output_dir=effective_output_dir_for_run,
            api_key=api_key, user_id=user_id, parent=main_app
        )

    # Handler for cloud storage sites (Mega, GDrive, Dropbox, GoFile)
    platform = None
    if 'mega.nz' in api_url or 'mega.io' in api_url: platform = 'mega'
    elif 'drive.google.com' in api_url: platform = 'gdrive'
    elif 'dropbox.com' in api_url: platform = 'dropbox'
    elif 'gofile.io' in api_url: platform = 'gofile'
    if platform:
        use_post_subfolder = main_app.use_subfolder_per_post_checkbox.isChecked()
        return DriveDownloadThread(
            api_url, effective_output_dir_for_run, platform, use_post_subfolder,
            main_app.cancellation_event, main_app.pause_event, main_app.log_signal.emit,
            parent=main_app # Pass parent for consistency
        )

    # Handler for Erome
    if 'erome.com' in api_url:
        return EromeDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for MangaDex
    if 'mangadex.org' in api_url:
        return MangaDexDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for Saint2
    is_saint2_url = service == 'saint2' or 'saint2.su' in api_url or 'saint2.pk' in api_url # Add more domains if needed
    if is_saint2_url and api_url.strip().lower() != 'saint2.su': # Exclude batch mode trigger if using URL input
        return Saint2DownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for SimpCity
    if service == 'simpcity':
        cookies = prepare_cookies_for_request(
            use_cookie_flag=True, # SimpCity requires cookies
            cookie_text_input=main_app.simpcity_cookie_text_input.text(), # Use dedicated input
            selected_cookie_file_path=main_app.selected_cookie_filepath, # Use shared selection
            app_base_dir=main_app.app_base_dir,
            logger_func=main_app.log_signal.emit,
            target_domain='simpcity.cr' # Specific domain
        )
        if not cookies:
            main_app.log_signal.emit("❌ SimpCity requires valid cookies. Please provide them.")
            return "COOKIE_ERROR" # Sentinel value for cookie failure
        return SimpCityDownloadThread(api_url, id2, effective_output_dir_for_run, cookies, main_app)

    # Handler for Rule34Video
    if service == 'rule34video':
        main_app.log_signal.emit("ℹ️ Rule34Video.com URL detected. Starting dedicated downloader.")
        return Rule34VideoDownloadThread(api_url, effective_output_dir_for_run, main_app) # id1 (video_id) is used inside the thread

    # HANDLER FOR KEMONO DISCORD (Place BEFORE official Discord)
    elif service == 'discord' and any(domain in api_url for domain in ['kemono.cr', 'kemono.su', 'kemono.party']):
        main_app.log_signal.emit("ℹ️ Kemono Discord URL detected. Starting dedicated downloader.")
        cookies = prepare_cookies_for_request(
            use_cookie_flag=main_app.use_cookie_checkbox.isChecked(), # Respect UI setting
            cookie_text_input=main_app.cookie_text_input.text(),
            selected_cookie_file_path=main_app.selected_cookie_filepath,
            app_base_dir=main_app.app_base_dir,
            logger_func=main_app.log_signal.emit,
            target_domain='kemono.cr' # Primary Kemono domain, adjust if needed
        )
        # KemonoDiscordDownloadThread expects parent for events
        return KemonoDiscordDownloadThread(
            server_id=id1,
            channel_id=id2,
            output_dir=effective_output_dir_for_run,
            cookies_dict=cookies,
            parent=main_app
        )

    # Handler for official Discord URLs
    elif service == 'discord' and 'discord.com' in api_url:
        main_app.log_signal.emit("ℹ️ Official Discord URL detected. Starting dedicated downloader.")
        token = main_app.remove_from_filename_input.text().strip() # Token is in the "Remove Words" field for Discord
        if not token:
             main_app.log_signal.emit("❌ Official Discord requires an Authorization Token in the 'Remove Words' field.")
             return None # Or a specific error sentinel

        limit_text = main_app.discord_message_limit_input.text().strip()
        message_limit = int(limit_text) if limit_text.isdigit() else None
        mode = main_app.discord_download_scope # Should be 'pdf' or 'files'

        return DiscordDownloadThread(
            mode=mode,
            session=requests.Session(), # Create a session for this thread
            token=token,
            output_dir=effective_output_dir_for_run,
            server_id=id1,
            channel_id=id2,
            url=api_url,
            app_base_dir=main_app.app_base_dir,
            limit=message_limit,
            parent=main_app # Pass main_app for events/signals
        )

    # Check specific domains or rely on service name if extract_post_info provides it
    if service == 'allcomic' or 'allcomic.com' in api_url or 'allporncomic.com' in api_url:
        return AllcomicDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for Hentai2Read
    if service == 'hentai2read' or 'hentai2read.com' in api_url:
        return Hentai2readDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for Fap-Nation
    if service == 'fap-nation' or 'fap-nation.com' in api_url or 'fap-nation.org' in api_url:
        use_post_subfolder = main_app.use_subfolder_per_post_checkbox.isChecked()
        # Ensure signals are passed correctly if needed by the thread
        return FapNationDownloadThread(
            api_url, effective_output_dir_for_run, use_post_subfolder,
            main_app.pause_event, main_app.cancellation_event, main_app.actual_gui_signals, main_app
        )

    # Handler for Pixeldrain
    if service == 'pixeldrain' or 'pixeldrain.com' in api_url:
        return PixeldrainDownloadThread(api_url, effective_output_dir_for_run, main_app) # URL contains the ID

    # Handler for nHentai
    if service == 'nhentai':
        from ...core.nhentai_client import fetch_nhentai_gallery
        main_app.log_signal.emit(f"ℹ️ nHentai gallery ID {id1} detected. Fetching gallery data...")
        gallery_data = fetch_nhentai_gallery(id1, main_app.log_signal.emit)
        if not gallery_data:
            main_app.log_signal.emit(f"❌ Failed to fetch nHentai gallery data for ID {id1}.")
            return "FETCH_ERROR" # Sentinel value for fetch failure
        return NhentaiDownloadThread(gallery_data, effective_output_dir_for_run, main_app)

    # Handler for Toonily
    if service == 'toonily' or 'toonily.com' in api_url:
        return ToonilyDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for Bunkr
    if service == 'bunkr':
         # id1 contains the full URL or album ID from extract_post_info
        return BunkrDownloadThread(id1, effective_output_dir_for_run, main_app)

    # Handler for DeviantArt
    if service == 'deviantart':
        main_app.log_signal.emit(f"ℹ️ DeviantArt URL detected. Starting dedicated downloader.")
        return DeviantArtDownloadThread(
            url=api_url,
            output_dir=effective_output_dir_for_run,
            pause_event=main_app.pause_event,
            cancellation_event=main_app.cancellation_event,
            parent=main_app
        )

    # Handler for HentaiFox (New)
    if 'hentaifox.com' in api_url or service == 'hentaifox':
        main_app.log_signal.emit("🦊 HentaiFox URL detected.")
        return HentaiFoxDownloadThread(
            url_or_id=api_url,
            output_dir=effective_output_dir_for_run,
            parent=main_app
        )    
    
    
    # ----------------------
    # --- Fallback ---
    # If no specific handler matched based on service name or URL pattern, return None.
    # This signals main_window.py to use the generic BackendDownloadThread/PostProcessorWorker
    # which uses the standard Kemono/Coomer post API.
    main_app.log_signal.emit(f"ℹ️ No specialized downloader found for service '{service}' and URL '{api_url[:50]}...'. Using generic downloader.")
    return None