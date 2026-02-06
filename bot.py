import os
import json
import asyncio
import logging
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

# ===========================
# تحميل المتغيرات البيئية
# ===========================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN غير موجود في .env")

# ===========================
# إعدادات السجلات
# ===========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===========================
# حالات البوت
# ===========================
class BotStates(StatesGroup):
    WAITING_API_ID = State()
    WAITING_API_HASH = State()
    WAITING_PHONE = State()
    WAITING_CODE = State()
    WAITING_PASSWORD = State()
    WAITING_MESSAGE = State()
    WAITING_PHOTOS = State()
    WAITING_GROUPS = State()
    WAITING_KEYWORDS = State()
    WAITING_SCHEDULE = State()

# ===========================
# إنشاء كائنات البوت
# ===========================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===========================
# قاعدة البيانات
# ===========================
class UserDatabase:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.db_file = f"user_{user_id}.json"
        self.data = self.load_data()
    
    def load_data(self):
        """تحميل بيانات المستخدم"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            "api_id": "",
            "api_hash": "",
            "phone": "",
            "message": "",
            "photos": [],
            "groups": [],
            "keywords": [],
            "schedule_time": "09:00",
            "is_active": False,
            "is_monitoring": False,
            "telegram_client": None,
            "phone_code_hash": "",
            "session_string": "",
            "last_sent": None,
            "alerts": [],
            "step": "start",
            "monitoring_handler": None
        }
    
    def save(self):
        """حفظ بيانات المستخدم"""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"خطأ في حفظ البيانات: {e}")
            return False
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def set(self, key, value):
        self.data[key] = value
        self.save()
    
    def append(self, key, value):
        if key not in self.data:
            self.data[key] = []
        if isinstance(self.data[key], list):
            self.data[key].append(value)
            self.save()

# ===========================
# المعالجات الأساسية (نفس الكود السابق)
# ===========================
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """بدء البوت"""
    db = UserDatabase(message.from_user.id)
    db.set("step", "start")
    
    welcome_text = """
🚀 **مرحباً بك في بوت الإرسال والمراقبة المتقدم!**

✨ **المميزات:**
✅ **الإرسال:** يرسل الرسائل والصور للمجموعات المحددة فقط
✅ **المراقبة:** يراقب جميع المحادثات في حسابك
✅ **التنبيهات:** يرسل التنبيهات لك في المحادثة الخاصة

🔧 **الأوامر المتاحة:**
/setup - بدء الإعداد
/status - عرض الحالة
/start_monitoring - بدء المراقبة
/stop_monitoring - إيقاف المراقبة
/send_now - إرسال فوري
/stop - إوقف البوت
/help - المساعدة
    """
    
    await message.answer(welcome_text, parse_mode="Markdown")

# ... (ضع هنا باقي الكود كما هو بدون تغيير)
# يمكنك وضع الكود الكامل السابق هنا

# ===========================
# وظائف المراقبة الداخلية
# ===========================
async def start_monitoring_internal(user_id: int):
    """بدء المراقبة الداخلية"""
    try:
        db = UserDatabase(user_id)
        client = db.get("telegram_client")
        keywords = db.get("keywords", [])
        
        if not client or not keywords:
            return False
        
        @client.on(events.NewMessage)
        async def handler(event):
            if event.message.text:
                message_text = event.message.text.lower()
                for keyword in keywords:
                    if keyword.lower() in message_text:
                        sender = await event.get_sender()
                        sender_name = getattr(sender, 'first_name', '') or getattr(sender, 'username', '') or 'غير معروف'
                        
                        alert = {
                            "keyword": keyword,
                            "message": event.message.text[:200],
                            "sender": sender_name,
                            "sender_id": sender.id if sender else None,
                            "group": getattr(event.chat, 'title', 'محادثة خاصة'),
                            "time": datetime.now().isoformat()
                        }
                        db.append("alerts", alert)
                        
                        alert_text = f"""
🚨 **تنبيه مراقبة**

🔍 **الكلمة:** {keyword}
👤 **المرسل:** {sender_name}
📝 **الرسالة:** {event.message.text[:100]}...
📍 **المكان:** {getattr(event.chat, 'title', 'محادثة خاصة')}
⏰ **الوقت:** {datetime.now().strftime('%H:%M:%S')}
                        """
                        
                        try:
                            await bot.send_message(
                                chat_id=user_id,
                                text=alert_text,
                                parse_mode="Markdown",
                                disable_web_page_preview=True
                            )
                        except Exception as e:
                            logger.error(f"خطأ في إرسال التنبيه: {e}")
        
        db.set("monitoring_handler", handler)
        return True
        
    except Exception as e:
        logger.error(f"خطأ في بدء المراقبة: {e}")
        return False

# ===========================
# المهمات الدورية للإرسال التلقائي
# ===========================
async def scheduled_messages_task():
    """مهمة الإرسال التلقائي"""
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M")
            
            # البحث عن جميع الملفات
            for filename in os.listdir("."):
                if filename.startswith("user_") and filename.endswith(".json"):
                    try:
                        user_id = int(filename[5:-5])
                        db = UserDatabase(user_id)
                        
                        if db.get("is_active") and db.get("schedule_time") == current_time:
                            last_sent = db.get("last_sent")
                            if last_sent:
                                last_time = datetime.fromisoformat(last_sent)
                                if (datetime.now() - last_time).seconds < 60:
                                    continue
                            
                            await send_scheduled_message(user_id)
                    except:
                        continue
            
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"خطأ في المهمة الدورية: {e}")
            await asyncio.sleep(60)

# ===========================
# تشغيل البوت (معدل للـ Render)
# ===========================
async def main():
    """الدالة الرئيسية"""
    # بدء المهمات الدورية
    asyncio.create_task(scheduled_messages_task())
    
    # تشغيل البوت
    logger.info("🚀 بدء تشغيل البوت على Render...")
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت: {e}")

if __name__ == "__main__":
    # تشغيل البوت بشكل مستمر
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("⏹️ تم إيقاف البوت")
            break
        except Exception as e:
            logger.error(f"❌ خطأ غير متوقع: {e}")
            logger.info("🔄 إعادة تشغيل البوت بعد 10 ثواني...")
            import time
            time.sleep(10)
