# ============================================
# FILE: bot/handlers/start.py
# ============================================
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.models import SessionLocal
from bot.database.db import UserDB
from bot.config import WELCOME_MESSAGE, APPROVED_MESSAGE, REJECTED_MESSAGE, ADMIN_IDS

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    db = SessionLocal()
    
    try:
        db_user = UserDB.get_user(db, user.id)
        
        if not db_user:
            db_user = UserDB.create_user(
                db, user.id, user.username, user.first_name, user.last_name
            )
            await update.message.reply_text(WELCOME_MESSAGE, parse_mode="Markdown")
            
            user_info = (
                f"🆕 **New User Request**\n\n"
                f"👤 User: {user.first_name}"
            )
            if user.last_name:
                user_info += f" {user.last_name}"
            user_info += (
                f"\n🆔 ID: `{user.id}`"
                f"\n👤 Username: @{user.username if user.username else 'None'}"
                f"\n\n/approve {user.id}\n/reject {user.id}"
            )
            
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id, text=user_info, parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"Error notifying admin {admin_id}: {e}")
        
        elif db_user.status == "pending":
            await update.message.reply_text(
                "⏳ သင့်ရဲ့ request ကို စောင့်ဆိုင်းနေပါသေးတယ်။"
            )
        elif db_user.status == "approved":
            await update.message.reply_text(APPROVED_MESSAGE, parse_mode="Markdown")
        elif db_user.status == "rejected":
            await update.message.reply_text(REJECTED_MESSAGE)
        elif db_user.status == "banned":
            await update.message.reply_text("🚫 သင့်အား bot အသုံးပြုခွင့် ပိတ်ပင်ထားပါတယ်။")
    finally:
        db.close()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """📖 **အသုံးပြုနည်း**

**Download:**
1. Apple Music URL ပို့ပါ
2. Format ရွေးပါ:
   • Track by Track
   • ZIP Archive

**Supported:**
🎵 Songs | 💿 Albums | 📋 Playlists | 🎬 Videos

**Commands:**
/start - စတင်ရန်
/help - အကူအညီ
/stats - Download history"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user = update.effective_user
    db = SessionLocal()
    
    try:
        if not UserDB.is_user_approved(db, user.id):
            await update.message.reply_text("⛔ Access denied")
            return
        
        downloads = UserDB.get_user_downloads(db, user.id, 10)
        
        if not downloads:
            await update.message.reply_text("📊 No download history")
            return
        
        stats_text = "📊 **Download History**\n\n"
        for dl in downloads:
            status_emoji = {
                "completed": "✅", "failed": "❌",
                "downloading": "⏳", "pending": "🔄"
            }.get(dl.status, "❓")
            
            stats_text += (
                f"{status_emoji} {dl.download_type.upper()}\n"
                f"   Format: {dl.format_type}\n"
                f"   Date: {dl.started_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            )
        
        await update.message.reply_text(stats_text, parse_mode="Markdown")
    finally:
        db.close()


# ============================================
# FILE: bot/handlers/admin.py
# ============================================
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.models import SessionLocal
from bot.database.db import UserDB, DownloadDB
from bot.config import ADMIN_IDS, APPROVED_MESSAGE, REJECTED_MESSAGE

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve user"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /approve <user_id>")
        return
    
    target_user_id = int(context.args[0])
    db = SessionLocal()
    
    try:
        user = UserDB.update_user_status(
            db, target_user_id, "approved", update.effective_user.id
        )
        
        if user:
            await update.message.reply_text(f"✅ User {target_user_id} approved")
            try:
                await context.bot.send_message(
                    chat_id=target_user_id, text=APPROVED_MESSAGE, parse_mode="Markdown"
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ User not found")
    finally:
        db.close()

async def reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject user"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /reject <user_id>")
        return
    
    target_user_id = int(context.args[0])
    db = SessionLocal()
    
    try:
        user = UserDB.update_user_status(db, target_user_id, "rejected")
        if user:
            await update.message.reply_text(f"❌ User {target_user_id} rejected")
            try:
                await context.bot.send_message(chat_id=target_user_id, text=REJECTED_MESSAGE)
            except:
                pass
        else:
            await update.message.reply_text("❌ User not found")
    finally:
        db.close()

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban user"""
    if not is_admin(update.effective_user.id):
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    
    target_user_id = int(context.args[0])
    db = SessionLocal()
    
    try:
        user = UserDB.update_user_status(db, target_user_id, "banned")
        if user:
            await update.message.reply_text(f"🚫 User {target_user_id} banned")
    finally:
        db.close()

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban user"""
    if not is_admin(update.effective_user.id):
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    
    target_user_id = int(context.args[0])
    db = SessionLocal()
    
    try:
        user = UserDB.update_user_status(db, target_user_id, "approved")
        if user:
            await update.message.reply_text(f"✅ User {target_user_id} unbanned")
    finally:
        db.close()

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List users"""
    if not is_admin(update.effective_user.id):
        return
    
    db = SessionLocal()
    
    try:
        pending = UserDB.get_pending_users(db)
        approved = UserDB.get_all_users(db, "approved")
        
        text = (
            f"👥 **Users**\n\n"
            f"⏳ Pending: {len(pending)}\n"
            f"✅ Approved: {len(approved)}\n"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
        
        if pending:
            pending_text = "⏳ **Pending:**\n\n"
            for user in pending[:10]:
                pending_text += (
                    f"👤 {user.first_name}\n"
                    f"🆔 `{user.user_id}`\n"
                    f"/approve {user.user_id} | /reject {user.user_id}\n\n"
                )
            await update.message.reply_text(pending_text, parse_mode="Markdown")
    finally:
        db.close()

async def systemstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """System stats"""
    if not is_admin(update.effective_user.id):
        return
    
    db = SessionLocal()
    try:
        stats = DownloadDB.get_download_stats(db)
        text = (
            f"📊 **System Stats**\n\n"
            f"📥 Total: {stats['total']}\n"
            f"✅ Completed: {stats['completed']}\n"
            f"❌ Failed: {stats['failed']}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        db.close()
