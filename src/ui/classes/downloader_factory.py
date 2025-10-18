import re
import requests
from urllib.parse import urlparse

from ...utils.network_utils import prepare_cookies_for_request
from ...utils.file_utils import clean_folder_name
from .allcomic_downloader_thread import AllcomicDownloadThread
from .booru_downloader_thread import BooruDownloadThread
from .bunkr_downloader_thread import BunkrDownloadThread
from .discord_downloader_thread import DiscordDownloadThread
from .drive_downloader_thread import DriveDownloadThread
from .erome_downloader_thread import EromeDownloadThread
from .external_link_downloader_thread import ExternalLinkDownloadThread
from .fap_nation_downloader_thread import FapNationDownloadThread
from .hentai2read_downloader_thread import Hentai2readDownloadThread
from .mangadex_downloader_thread import MangaDexDownloadThread
from .nhentai_downloader_thread import NhentaiDownloadThread
from .pixeldrain_downloader_thread import PixeldrainDownloadThread
from .saint2_downloader_thread import Saint2DownloadThread
from .simp_city_downloader_thread import SimpCityDownloadThread
from .toonily_downloader_thread import ToonilyDownloadThread
from .rule34video_downloader_thread import Rule34VideoDownloadThread


def create_downloader_thread(main_app, api_url, service, id1, id2, effective_output_dir_for_run):
    """
    Factory function to create and configure the correct QThread for a given URL.
    Returns a configured QThread instance or None if no special handler is found.
    """

    # Handler for Booru sites (Danbooru, Gelbooru)
    if service in ['danbooru', 'gelbooru']:
        api_key = main_app.api_key_input.text().strip()
        user_id = main_app.user_id_input.text().strip()
        return BooruDownloadThread(
            url=api_url, output_dir=effective_output_dir_for_run,
            api_key=api_key, user_id=user_id, parent=main_app
        )

    # Handler for cloud storage sites (Mega, GDrive, etc.)
    platform = None
    if 'mega.nz' in api_url or 'mega.io' in api_url: platform = 'mega'
    elif 'drive.google.com' in api_url: platform = 'gdrive'
    elif 'dropbox.com' in api_url: platform = 'dropbox'
    elif 'gofile.io' in api_url: platform = 'gofile'
    if platform:
        use_post_subfolder = main_app.use_subfolder_per_post_checkbox.isChecked()
        return DriveDownloadThread(
            api_url, effective_output_dir_for_run, platform, use_post_subfolder,
            main_app.cancellation_event, main_app.pause_event, main_app.log_signal.emit
        )

    # Handler for Erome
    if 'erome.com' in api_url:
        return EromeDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for MangaDex
    if 'mangadex.org' in api_url:
        return MangaDexDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for Saint2
    is_saint2_url = 'saint2.su' in api_url or 'saint2.pk' in api_url
    if is_saint2_url and api_url.strip().lower() != 'saint2.su': # Exclude batch mode trigger
        return Saint2DownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for SimpCity
    if service == 'simpcity':
        cookies = prepare_cookies_for_request(
            use_cookie_flag=True, cookie_text_input=main_app.cookie_text_input.text(),
            selected_cookie_file_path=main_app.selected_cookie_filepath,
            app_base_dir=main_app.app_base_dir, logger_func=main_app.log_signal.emit,
            target_domain='simpcity.cr'
        )
        if not cookies:
            # The main app will handle the error dialog
            return "COOKIE_ERROR"
        return SimpCityDownloadThread(api_url, id2, effective_output_dir_for_run, cookies, main_app)

    if service == 'rule34video':
        main_app.log_signal.emit("ℹ️ Rule34Video.com URL detected. Starting dedicated downloader.")
        # id1 contains the video_id from extract_post_info
        return Rule34VideoDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for official Discord URLs
    if 'discord.com' in api_url and service == 'discord':
        token = main_app.remove_from_filename_input.text().strip()
        limit_text = main_app.discord_message_limit_input.text().strip()
        message_limit = int(limit_text) if limit_text else None
        mode = 'pdf' if main_app.discord_download_scope == 'messages' else 'files'
        return DiscordDownloadThread(
            mode=mode, session=requests.Session(), token=token, output_dir=effective_output_dir_for_run,
            server_id=id1, channel_id=id2, url=api_url, app_base_dir=main_app.app_base_dir,
            limit=message_limit, parent=main_app
        )

    # Handler for Allcomic/Allporncomic
    if 'allcomic.com' in api_url or 'allporncomic.com' in api_url:
        return AllcomicDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for Hentai2Read
    if 'hentai2read.com' in api_url:
        return Hentai2readDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for Fap-Nation
    if 'fap-nation.com' in api_url or 'fap-nation.org' in api_url:
        use_post_subfolder = main_app.use_subfolder_per_post_checkbox.isChecked()
        return FapNationDownloadThread(
            api_url, effective_output_dir_for_run, use_post_subfolder,
            main_app.pause_event, main_app.cancellation_event, main_app.actual_gui_signals, main_app
        )

    # Handler for Pixeldrain
    if 'pixeldrain.com' in api_url:
        return PixeldrainDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for nHentai
    if service == 'nhentai':
        from ...core.nhentai_client import fetch_nhentai_gallery
        gallery_data = fetch_nhentai_gallery(id1, main_app.log_signal.emit)
        if not gallery_data:
            return "FETCH_ERROR" # Sentinel value for fetch failure
        return NhentaiDownloadThread(gallery_data, effective_output_dir_for_run, main_app)

    # Handler for Toonily
    if 'toonily.com' in api_url:
        return ToonilyDownloadThread(api_url, effective_output_dir_for_run, main_app)

    # Handler for Bunkr
    if service == 'bunkr':
        return BunkrDownloadThread(id1, effective_output_dir_for_run, main_app)

    # If no special handler matched, return None
    return None