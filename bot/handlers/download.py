# ============================================
# FILE: bot/handlers/download.py
# ============================================
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.models import SessionLocal
from bot.database.db import UserDB, DownloadDB
from bot.utils.downloader import GamdlWrapper
from bot.utils.zip_helper import ZipHelper
from bot.utils.uploader import TelegramUploader
from bot.config import UNAUTHORIZED_MESSAGE, DUMP_CHANNEL_ID, TEMP_PATH

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Apple Music URL"""
    user = update.effective_user
    message_text = update.message.text
    db = SessionLocal()
    
    try:
        if not UserDB.is_user_approved(db, user.id):
            await update.message.reply_text(UNAUTHORIZED_MESSAGE)
            return
        
        downloader = GamdlWrapper()
        url_info = downloader.parse_url(message_text)
        
        if not url_info:
            await update.message.reply_text("❌ Invalid Apple Music URL")
            return
        
        status_msg = await update.message.reply_text("🔍 Checking URL...")
        
        try:
            metadata = downloader.get_metadata(message_text)
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)}")
            return
        
        info_text = "🎵 **Apple Music Download**\n\n"
        info_text += f"📝 Type: {metadata['type'].upper()}\n"
        info_text += f"🎯 Tracks: {metadata['tracks_count']}\n"
        
        if metadata.get('album_name'):
            info_text += f"💿 Album: {metadata['album_name']}\n"
        elif metadata.get('playlist_name'):
            info_text += f"📋 Playlist: {metadata['playlist_name']}\n"
        
        if metadata['tracks_count'] > 1:
            info_text += "\n**Tracks:**\n"
            for i, track in enumerate(metadata['tracks'][:5], 1):
                info_text += f"{i}. {track['title']} - {track['artist']}\n"
            if metadata['tracks_count'] > 5:
                info_text += f"... +{metadata['tracks_count'] - 5} more\n"
        else:
            track = metadata['tracks'][0]
            info_text += f"\n🎵 {track['title']}\n👤 {track['artist']}\n"
        
        keyboard = []
        if metadata['tracks_count'] == 1:
            keyboard.append([
                InlineKeyboardButton("📥 Download", callback_data=f"dl_track|{message_text}")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("📥 Track by Track", callback_data=f"dl_track|{message_text}"),
                InlineKeyboardButton("🗜️ ZIP", callback_data=f"dl_zip|{message_text}")
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="dl_cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await status_msg.edit_text(info_text, reply_markup=reply_markup, parse_mode="Markdown")
    finally:
        db.close()

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "dl_cancel":
        await query.edit_message_text("❌ Cancelled")
        return
    
    action, url = query.data.split("|", 1)
    user = query.from_user
    db = SessionLocal()
    
    try:
        if not UserDB.is_user_approved(db, user.id):
            await query.edit_message_text(UNAUTHORIZED_MESSAGE)
            return
        
        if action == "dl_track":
            await start_track_download(query, url, user.id, db, context)
        elif action == "dl_zip":
            await start_zip_download(query, url, user.id, db, context)
    finally:
        db.close()

async def start_track_download(query, url: str, user_id: int, db, context):
    """Download tracks individually"""
    await query.edit_message_text("⏳ Starting download...")
    
    try:
        downloader = GamdlWrapper()
        metadata = downloader.get_metadata(url)
        
        download_record = DownloadDB.create_download(
            db, user_id, url, metadata['type'], "track"
        )
        DownloadDB.update_download_status(db, download_record.id, "downloading")
        
        progress_msg = await context.bot.send_message(
            chat_id=query.message.chat_id, text="📥 Downloading..."
        )
        
        def progress_cb(current, total, track_name):
            asyncio.create_task(
                progress_msg.edit_text(f"📥 {current}/{total}\n🎵 {track_name}")
            )
        
        files = downloader.download_tracks(url, progress_cb)
        
        if not files:
            await progress_msg.edit_text("❌ No files downloaded")
            DownloadDB.update_download_status(db, download_record.id, "failed", "No files")
            return
        
        await progress_msg.edit_text("📤 Uploading...")
        uploader = TelegramUploader(context.bot, DUMP_CHANNEL_ID)
        
        async def upload_cb(current, total, filename):
            await progress_msg.edit_text(f"📤 Uploading ZIP ({zip_size:.1f} MB)...")
        
        uploader = TelegramUploader(context.bot, DUMP_CHANNEL_ID)
        caption = f"🗜️ {zip_name}\n📊 {len(files)} tracks\n💾 {zip_size:.1f} MB"
        
        msg_id = await uploader.upload_to_dump_and_forward(
            zip_path, query.message.chat_id, caption
        )
        
        DownloadDB.update_download_files(
            db, download_record.id,
            json.dumps([str(zip_path)]),
            json.dumps([msg_id]) if msg_id else None
        )
        DownloadDB.update_download_status(db, download_record.id, "completed")
        
        ZipHelper.cleanup_files(files + [zip_path])
        await progress_msg.edit_text("✅ ZIP completed!")
    
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {str(e)}")
        if 'download_record' in locals():
            DownloadDB.update_download_status(db, download_record.id, "failed", str(e))


# ============================================
# FILE: bot/utils/downloader.py
# ============================================
import re
from pathlib import Path
from typing import List, Dict, Optional
from gamdl.apple_music_api import AppleMusicApi
from gamdl.itunes_api import ItunesApi
from gamdl.downloader import Downloader
from gamdl.downloader_song import DownloaderSong
from gamdl.downloader_song_legacy import DownloaderSongLegacy
from gamdl.downloader_music_video import DownloaderMusicVideo
from gamdl.enums import SongCodec, RemuxMode, DownloadMode, CoverFormat, SyncedLyricsFormat, MusicVideoCodec
from bot.config import COOKIES_PATH, OUTPUT_PATH, TEMP_PATH

class GamdlWrapper:
    def __init__(self):
        self.apple_music_api = AppleMusicApi(
            cookies_path=COOKIES_PATH, language="en-US"
        )
        self.itunes_api = ItunesApi(
            self.apple_music_api.storefront, self.apple_music_api.language
        )
        self.downloader = Downloader(
            self.apple_music_api, self.itunes_api,
            output_path=OUTPUT_PATH, temp_path=TEMP_PATH,
            download_mode=DownloadMode.YTDLP,
            remux_mode=RemuxMode.FFMPEG,
            cover_format=CoverFormat.JPG, silent=True
        )
        self.downloader_song = DownloaderSong(
            self.downloader, codec=SongCodec.AAC_LEGACY,
            synced_lyrics_format=SyncedLyricsFormat.LRC
        )
        self.downloader_song_legacy = DownloaderSongLegacy(
            self.downloader, codec=SongCodec.AAC_LEGACY
        )
        self.downloader_music_video = DownloaderMusicVideo(
            self.downloader, codec=MusicVideoCodec.H264
        )
        self.downloader.set_cdm()
    
    def parse_url(self, url: str) -> Optional[Dict]:
        try:
            url_info = self.downloader.get_url_info(url)
            return {"type": url_info.type, "id": url_info.id, "storefront": url_info.storefront}
        except:
            return None
    
    def get_metadata(self, url: str) -> Optional[Dict]:
        url_info = self.downloader.get_url_info(url)
        download_queue = self.downloader.get_download_queue(url_info)
        
        if not download_queue.tracks_metadata:
            return None
        
        metadata = {
            "type": url_info.type,
            "tracks_count": len(download_queue.tracks_metadata),
            "tracks": []
        }
        
        for track in download_queue.tracks_metadata:
            track_info = {
                "id": track["id"],
                "title": track["attributes"]["name"],
                "artist": track["attributes"].get("artistName", "Unknown"),
                "type": track["type"]
            }
            if track["attributes"].get("albumName"):
                track_info["album"] = track["attributes"]["albumName"]
            metadata["tracks"].append(track_info)
        
        if url_info.type == "playlist" and download_queue.playlist_attributes:
            metadata["playlist_name"] = download_queue.playlist_attributes["name"]
        elif url_info.type == "album" and metadata["tracks"]:
            metadata["album_name"] = metadata["tracks"][0].get("album", "Unknown")
        
        return metadata
    
    def download_tracks(self, url: str, progress_callback=None) -> List[Path]:
        downloaded_files = []
        
        url_info = self.downloader.get_url_info(url)
        download_queue = self.downloader.get_download_queue(url_info)
        total_tracks = len(download_queue.tracks_metadata)
        
        for index, track_metadata in enumerate(download_queue.tracks_metadata, 1):
            if progress_callback:
                progress_callback(index, total_tracks, track_metadata["attributes"]["name"])
            
            try:
                if not track_metadata["attributes"].get("playParams"):
                    continue
                
                if track_metadata["type"] == "songs":
                    file_path = self._download_song(track_metadata)
                elif track_metadata["type"] == "music-videos":
                    file_path = self._download_music_video(track_metadata)
                else:
                    continue
                
                if file_path and file_path.exists():
                    downloaded_files.append(file_path)
            except Exception as e:
                print(f"Error downloading: {e}")
            finally:
                self.downloader.cleanup_temp_path()
        
        return downloaded_files
    
    def _download_song(self, track_metadata: dict) -> Optional[Path]:
        lyrics = self.downloader_song.get_lyrics(track_metadata)
        webplayback = self.apple_music_api.get_webplayback(track_metadata["id"])
        tags = self.downloader_song.get_tags(webplayback, lyrics.unsynced)
        final_path = self.downloader.get_final_path(tags, ".m4a")
        
        if final_path.exists():
            return final_path
        
        stream_info = self.downloader_song_legacy.get_stream_info(webplayback)
        decryption_key = self.downloader_song_legacy.get_decryption_key(
            stream_info.pssh, track_metadata["id"]
        )
        
        encrypted_path = self.downloader_song.get_encrypted_path(track_metadata["id"])
        decrypted_path = self.downloader_song.get_decrypted_path(track_metadata["id"])
        remuxed_path = self.downloader_song.get_remuxed_path(track_metadata["id"])
        
        self.downloader.download(encrypted_path, stream_info.stream_url)
        self.downloader_song_legacy.remux(
            encrypted_path, decrypted_path, remuxed_path, decryption_key
        )
        
        cover_url = self.downloader.get_cover_url(track_metadata)
        self.downloader.apply_tags(remuxed_path, tags, cover_url)
        self.downloader.move_to_output_path(remuxed_path, final_path)
        
        return final_path
    
    def _download_music_video(self, track_metadata: dict) -> Optional[Path]:
        music_video_id_alt = self.downloader_music_video.get_music_video_id_alt(track_metadata)
        itunes_page = self.itunes_api.get_itunes_page("music-video", music_video_id_alt)
        
        if music_video_id_alt == track_metadata["id"]:
            stream_url = self.downloader_music_video.get_stream_url_from_itunes_page(itunes_page)
        else:
            webplayback = self.apple_music_api.get_webplayback(track_metadata["id"])
            stream_url = self.downloader_music_video.get_stream_url_from_webplayback(webplayback)
        
        m3u8_data = self.downloader_music_video.get_m3u8_master_data(stream_url)
        tags = self.downloader_music_video.get_tags(music_video_id_alt, itunes_page, track_metadata)
        final_path = self.downloader.get_final_path(tags, ".m4v")
        
        if final_path.exists():
            return final_path
        
        stream_info_video = self.downloader_music_video.get_stream_info_video(m3u8_data)
        stream_info_audio = self.downloader_music_video.get_stream_info_audio(m3u8_data)
        
        decryption_key_video = self.downloader.get_decryption_key(stream_info_video.pssh, track_metadata["id"])
        decryption_key_audio = self.downloader.get_decryption_key(stream_info_audio.pssh, track_metadata["id"])
        
        encrypted_path_video = self.downloader_music_video.get_encrypted_path_video(track_metadata["id"])
        encrypted_path_audio = self.downloader_music_video.get_encrypted_path_audio(track_metadata["id"])
        decrypted_path_video = self.downloader_music_video.get_decrypted_path_video(track_metadata["id"])
        decrypted_path_audio = self.downloader_music_video.get_decrypted_path_audio(track_metadata["id"])
        remuxed_path = self.downloader_music_video.get_remuxed_path(track_metadata["id"])
        
        self.downloader.download(encrypted_path_video, stream_info_video.stream_url)
        self.downloader.download(encrypted_path_audio, stream_info_audio.stream_url)
        
        self.downloader_music_video.decrypt(encrypted_path_video, decryption_key_video, decrypted_path_video)
        self.downloader_music_video.decrypt(encrypted_path_audio, decryption_key_audio, decrypted_path_audio)
        
        self.downloader_music_video.remux(
            decrypted_path_video, decrypted_path_audio, remuxed_path,
            stream_info_video.codec, stream_info_audio.codec
        )
        
        cover_url = self.downloader.get_cover_url(track_metadata)
        self.downloader.apply_tags(remuxed_path, tags, cover_url)
        self.downloader.move_to_output_path(remuxed_path, final_path)
        
        return final_path


# ============================================
# FILE: bot/utils/zip_helper.py
# ============================================
import zipfile
import shutil
from pathlib import Path
from typing import List

class ZipHelper:
    @staticmethod
    def create_zip(files: List[Path], output_name: str, temp_dir: Path) -> Path:
        temp_dir.mkdir(parents=True, exist_ok=True)
        safe_name = ZipHelper._sanitize_filename(output_name)
        zip_path = temp_dir / f"{safe_name}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=5) as zipf:
            for file_path in files:
                if file_path.exists():
                    zipf.write(file_path, arcname=file_path.name)
        
        return zip_path
    
    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:200]
    
    @staticmethod
    def get_zip_size_mb(zip_path: Path) -> float:
        if zip_path.exists():
            return zip_path.stat().st_size / (1024 * 1024)
        return 0.0
    
    @staticmethod
    def cleanup_files(files: List[Path]):
        for file_path in files:
            try:
                if file_path.exists():
                    if file_path.is_file():
                        file_path.unlink()
                    elif file_path.is_dir():
                        shutil.rmtree(file_path)
            except Exception as e:
                print(f"Cleanup error: {e}")


# ============================================
# FILE: bot/utils/uploader.py
# ============================================
import asyncio
from pathlib import Path
from typing import List, Optional
from telegram import Bot
from telegram.error import TelegramError
from bot.config import MAX_FILE_SIZE_MB

class TelegramUploader:
    def __init__(self, bot: Bot, dump_channel_id: int):
        self.bot = bot
        self.dump_channel_id = dump_channel_id
    
    async def upload_file(self, file_path: Path, chat_id: int, 
                         caption: str = None) -> Optional[int]:
        try:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            
            if file_size_mb > MAX_FILE_SIZE_MB:
                return None
            
            suffix = file_path.suffix.lower()
            
            if suffix in ['.m4a', '.mp3', '.flac', '.aac']:
                message = await self.bot.send_audio(
                    chat_id=chat_id, audio=open(file_path, 'rb'),
                    caption=caption, filename=file_path.name
                )
            elif suffix in ['.mp4', '.m4v', '.mkv']:
                message = await self.bot.send_video(
                    chat_id=chat_id, video=open(file_path, 'rb'),
                    caption=caption, filename=file_path.name, supports_streaming=True
                )
            else:
                message = await self.bot.send_document(
                    chat_id=chat_id, document=open(file_path, 'rb'),
                    caption=caption, filename=file_path.name
                )
            
            return message.message_id
        except Exception as e:
            print(f"Upload error: {e}")
            return None
    
    async def upload_to_dump_and_forward(self, file_path: Path, 
                                        user_chat_id: int, caption: str = None) -> Optional[int]:
        try:
            dump_msg_id = await self.upload_file(file_path, self.dump_channel_id, caption)
            
            if dump_msg_id:
                await self.bot.forward_message(
                    chat_id=user_chat_id,
                    from_chat_id=self.dump_channel_id,
                    message_id=dump_msg_id
                )
            
            return dump_msg_id
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    async def upload_multiple_files(self, files: List[Path], user_chat_id: int,
                                    progress_callback=None) -> List[int]:
        dump_message_ids = []
        total_files = len(files)
        
        for index, file_path in enumerate(files, 1):
            if progress_callback:
                await progress_callback(index, total_files, file_path.name)
            
            caption = f"📁 {file_path.name}\n📊 {index}/{total_files}"
            msg_id = await self.upload_to_dump_and_forward(file_path, user_chat_id, caption)
            
            if msg_id:
                dump_message_ids.append(msg_id)
            
            await asyncio.sleep(0.5)
        
        return dump_message_ids{current}/{total}\n📁 {filename}")
        
        msg_ids = await uploader.upload_multiple_files(
            files, query.message.chat_id, upload_cb
        )
        
        DownloadDB.update_download_files(
            db, download_record.id,
            json.dumps([str(f) for f in files]),
            json.dumps(msg_ids)
        )
        DownloadDB.update_download_status(db, download_record.id, "completed")
        
        ZipHelper.cleanup_files(files)
        await progress_msg.edit_text(f"✅ Completed! {len(files)} files")
    
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {str(e)}")
        if 'download_record' in locals():
            DownloadDB.update_download_status(db, download_record.id, "failed", str(e))

async def start_zip_download(query, url: str, user_id: int, db, context):
    """Download as ZIP"""
    await query.edit_message_text("⏳ Starting download...")
    
    try:
        downloader = GamdlWrapper()
        metadata = downloader.get_metadata(url)
        
        download_record = DownloadDB.create_download(
            db, user_id, url, metadata['type'], "zip"
        )
        DownloadDB.update_download_status(db, download_record.id, "downloading")
        
        progress_msg = await context.bot.send_message(
            chat_id=query.message.chat_id, text="📥 Downloading..."
        )
        
        def progress_cb(current, total, track_name):
            asyncio.create_task(
                progress_msg.edit_text(f"📥 {current}/{total}\n🎵 {track_name}")
            )
        
        files = downloader.download_tracks(url, progress_cb)
        
        if not files:
            await progress_msg.edit_text("❌ No files")
            DownloadDB.update_download_status(db, download_record.id, "failed", "No files")
            return
        
        await progress_msg.edit_text("🗜️ Creating ZIP...")
        
        zip_name = metadata.get('album_name') or metadata.get('playlist_name') or f"Apple_Music_{metadata['type']}"
        zip_path = ZipHelper.create_zip(files, zip_name, TEMP_PATH)
        zip_size = ZipHelper.get_zip_size_mb(zip_path)
        
        await progress_msg.edit_text(f"📤
