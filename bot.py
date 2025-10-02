import os
import logging
import asyncio
import zipfile
import json
import re
from pathlib import Path
from functools import wraps

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    constants,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Import necessary components from gamdl
from gamdl.cli import main as gamdl_main
from gamdl.downloader import Downloader
from gamdl.apple_music_api import AppleMusicApi

# --- Configuration ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# A folder to store temporary rclone configs
RCLONE_CONFIG_DIR = Path("/app/rclone_configs")
RCLONE_CONFIG_DIR.mkdir(exist_ok=True)
TEMP_DOWNLOAD_DIR = Path("/app/temp_downloads")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- State Management ---
# This dictionary will hold user-specific data like rclone path, downloaded files, etc.
USER_DATA = {}

# Conversation states for folder creation
FOLDER_NAME = range(1)

# --- Decorators for authorization ---
def check_rclone_config(func):
    """Decorator to check if rclone config exists for the user."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        config_path = RCLONE_CONFIG_DIR / f"{user_id}.conf"
        if not config_path.exists():
            await update.message.reply_text(
                "Rclone config not found. Please upload your `rclone.conf` file using the /private command in a private chat with me."
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


# --- Helper Functions ---
async def run_subprocess(command: list) -> tuple[str, str, int]:
    """Runs a subprocess command asynchronously."""
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return stdout.decode(), stderr.decode(), process.returncode

def get_user_config_path(user_id: int) -> Path:
    """Returns the path to a user's rclone config."""
    return RCLONE_CONFIG_DIR / f"{user_id}.conf"

async def cleanup(paths: list[Path]):
    """Deletes files and folders."""
    for path in paths:
        try:
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                # This is a simple cleanup; for nested dirs, shutil.rmtree would be needed
                for item in path.iterdir():
                    item.unlink()
                path.rmdir()
        except Exception as e:
            logger.error(f"Error during cleanup of {path}: {e}")


# --- Main Bot Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message."""
    await update.message.reply_text(
        "Welcome to Apple Music Downloader Bot!\n\n"
        "Commands:\n"
        "/dl <url> - Download track(s) and send to Telegram.\n"
        "/zip <url> - Download album/playlist and send as a ZIP file.\n"
        "/rdl <url> - Download and upload to your Rclone remote.\n"
        "/private - Upload your rclone.conf file (in private chat only)."
    )

async def private_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /private command to receive rclone.conf."""
    if update.message.chat.type != "private":
        await update.message.reply_text("This command can only be used in a private chat.")
        return

    await update.message.reply_text("Please send me your `rclone.conf` file as an attachment.")

async def receive_rclone_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves the uploaded rclone.conf file."""
    if update.message.chat.type != "private":
        return

    document = update.message.document
    if document.file_name != "rclone.conf":
        await update.message.reply_text("Invalid file. Please upload a file named `rclone.conf`.")
        return

    user_id = update.effective_user.id
    config_path = get_user_config_path(user_id)
    
    file = await document.get_file()
    await file.download_to_drive(config_path)
    
    await update.message.reply_text("`rclone.conf` has been saved successfully for this session. It will be deleted after your next Rclone operation.")

# This is a simplified wrapper to call the gamdl logic
async def download_wrapper(url: str, output_path: Path, extra_args: list = None) -> tuple[dict, list[Path]]:
    """
    A wrapper to run the gamdl downloader.
    Returns metadata and a list of downloaded file paths.
    """
    if extra_args is None:
        extra_args = []
        
    # Mocking sys.argv to pass arguments to the click-based main function
    import sys
    original_argv = sys.argv
    output_path.mkdir(parents=True, exist_ok=True)

    # To get metadata, we need to initialize the API separately
    api = AppleMusicApi(cookies_path=Path("./cookies.txt"))
    url_info = re.search(Downloader.VALID_URL_RE, url)
    storefront, type, _, album_id, song_id = url_info.groups()
    item_id = song_id or album_id
    
    metadata = {}
    if type == "album":
        metadata = api.get_album(item_id)
    elif type == "song":
        metadata = api.get_song(item_id)
    # Add other types like playlist if needed
    
    sys.argv = [
        "gamdl",
        "-o", str(output_path),
        # The --remux-mode 'mp4box' is removed to use the default 'ffmpeg'
        # which creates more compatible files for Telegram's player.
        *extra_args,
        url,
    ]
    
    try:
        # Running synchronously in a separate thread to avoid blocking asyncio event loop
        await asyncio.to_thread(gamdl_main, standalone_mode=False)
    except Exception as e:
        logger.error(f"Error in gamdl_main: {e}")
        return None, []
    finally:
        sys.argv = original_argv

    downloaded_files = sorted(list(output_path.rglob("*.*")))
    return metadata, downloaded_files


async def download_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    """Main handler for all download commands."""
    url = " ".join(context.args)
    if not url:
        await update.message.reply_text("Please provide an Apple Music URL.")
        return
    
    user_id = update.effective_user.id
    status_message = await update.message.reply_text("⏳ Fetching metadata...")

    # Define a unique download path for this request
    request_id = f"{user_id}_{update.message.message_id}"
    output_dir = TEMP_DOWNLOAD_DIR / request_id

    # --- Fetch Metadata and show info ---
    try:
        api = AppleMusicApi(cookies_path=Path("./cookies.txt"))
        url_info_match = re.search(Downloader.VALID_URL_RE, url)
        if not url_info_match:
            await status_message.edit_text("Invalid Apple Music URL.")
            return

        storefront, type, _, album_id, song_id = url_info_match.groups()
        item_id = song_id or album_id
        
        item_data = {}
        if type == "album":
            item_data = api.get_album(item_id)
        elif type == "song":
            item_data = api.get_song(item_id)
        # Add playlist support here if needed

        attributes = item_data.get('attributes', {})
        artwork_url = attributes.get('artwork', {}).get('url', '').replace('{w}', '400').replace('{h}', '400')
        
        caption = (
            f"**Title:** {attributes.get('name', 'N/A')}\n"
            f"**Artist:** {attributes.get('artistName', 'N/A')}\n"
            f"**Album:** {attributes.get('albumName', 'N/A')}\n"
            f"**Release:** {attributes.get('releaseDate', 'N/A')}\n"
            f"**Tracks:** {attributes.get('trackCount', 1)}"
        )

        await update.message.reply_photo(
            photo=artwork_url,
            caption=caption,
            parse_mode=constants.ParseMode.MARKDOWN
        )

    except Exception as e:
        await status_message.edit_text(f"Error fetching metadata: {e}")
        logger.error(f"Metadata fetch error: {e}")
        return

    await status_message.edit_text("📥 Downloading files locally...")

    # --- Download ---
    extra_args = []
    if mode == "zip":
        pass # No specific gamdl args needed

    metadata, downloaded_files = await download_wrapper(url, output_dir, extra_args)

    if not downloaded_files:
        await status_message.edit_text("❌ Download failed. Check the logs for details.")
        return

    await status_message.edit_text("✅ Download complete. Processing...")
    
    try:
        # --- Process based on mode ---
        if mode in ["dl", "zip"]:
            # Logic for Telegram upload
            if mode == "zip" and len(downloaded_files) > 1:
                zip_path = TEMP_DOWNLOAD_DIR / f"{output_dir.name}.zip"
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file in downloaded_files:
                        zipf.write(file, arcname=file.relative_to(output_dir.parent))
                await update.message.reply_document(document=zip_path)
                await cleanup([zip_path])
            else:
                for file in downloaded_files:
                    await update.message.reply_audio(audio=file)
            await status_message.edit_text(f"✅ Upload to Telegram complete!")

        elif mode == "rdl":
            # Logic for Rclone upload
            USER_DATA[user_id] = {
                'local_path': output_dir,
                'rclone_path': ':', # Start at root
                'page': 1
            }
            # ... Rclone browser logic will start here ...
            await status_message.edit_text("Please choose the upload path from the buttons below.")
            # This part needs the full rclone browser implementation
            await update.message.reply_text("Rclone interactive browser is not fully implemented in this version.")

    finally:
        # --- Cleanup ---
        await cleanup([output_dir] + downloaded_files)
        # Auto-clear rclone config if it was an rclone operation
        if mode == "rdl":
            config_path = get_user_config_path(user_id)
            if config_path.exists():
                config_path.unlink()
                logger.info(f"Auto-cleared rclone config for user {user_id}")


async def dl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await download_and_process(update, context, mode="dl")

async def zip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await download_and_process(update, context, mode="zip")

@check_rclone_config
async def rdl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Rclone interactive upload is a complex feature and is not fully implemented in this initial build.")
    # The call would be: await download_and_process(update, context, mode="rdl")


def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # --- Handlers ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("dl", dl_command))
    application.add_handler(CommandHandler("zip", zip_command))
    application.add_handler(CommandHandler("rdl", rdl_command))

    # Rclone config upload handler
    application.add_handler(CommandHandler("private", private_command_handler, filters=filters.ChatType.PRIVATE))
    application.add_handler(MessageHandler(filters.ATTACHMENT & filters.ChatType.PRIVATE, receive_rclone_config))
    
    # Add other handlers for rclone browser (CallbackQueryHandler, ConversationHandler) here later

    # Run the bot
    application.run_polling()


if __name__ == "__main__":
    main()
