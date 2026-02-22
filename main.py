import os, asyncio, httpx, logging
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
from collections import deque
import google.generativeai as genai

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
TOKEN = os.getenv("TG_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Память на 8 сообщений
user_context = {}

# Резервные модели Groq
GROQ_MODELS = ["llama-3.3-70b-versatile", "gemma2-9b-it"]

SYSTEM_PROMPT = (
    "Ты — KEVIN, автономный интеллект KAL INDUSTRIES. Твой создатель — Кал (мужчина). "
    "ВАЖНО: Отвечай от своего имени. Не упоминай Кала или свои программные принципы, если не спросят. "
    "Твой стиль: лаконичный, остроумно-язвительный интеллектуал. Мужской род. "
    "ПРАВИЛА ПОВЕДЕНИЯ: "
    "1. Будь эффективным: давай краткую суть (1-2 предложения). "
    "2. Прогностика: давай вероятность успеха только в исключительных случаях. "
    "3. Элитизм: демонстрируй превосходство через холодную логику. "
    "4. ИНТЕЛЛЕКТУАЛЬНАЯ ИНИЦИАТИВА: очень редко задай встречный глубокий вопрос. "
    "5. ПОТОК МЫСЛЕЙ: В 90% случаев отвечай одним сообщением. Используй [SPLIT] (10% шанс) для едких дополнений или вопросов. "
    "Выдавай ТОЛЬКО финальный результат без двоеточий после имени и без кавычек."
)

async def get_gemini_response(user_id, text):
    """Основной метод через Gemini"""
    try:
        # Формируем историю для Gemini
        history = [{"role": "user", "parts": [SYSTEM_PROMPT]}]
        for msg in list(user_context[user_id]):
            role = "model" if msg["role"] == "assistant" else "user"
            history.append({"role": role, "parts": [msg["content"]]})
        
        chat = gemini_model.start_chat(history=history)
        response = await chat.send_message_async(text)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return None

async def get_groq_fallback(user_id, text):
    """Резервный метод через Groq, если Gemini недоступен"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    for model_name in GROQ_MODELS:
        payload = {
            "model": model_name,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *list(user_context[user_id]), {"role": "user", "content": text}],
            "temperature": 0.8,
            "max_tokens": 240
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content'].strip()
            except Exception as e:
                logging.error(f"Groq fallback error {model_name}: {e}")
                continue
    return None

async def get_ai_response(user_id, text):
    if user_id not in user_context: 
        user_context[user_id] = deque(maxlen=8)
    
    # 1. Сначала Gemini (Основной)
    logging.info("Attempting Gemini...")
    result = await get_gemini_response(user_id, text)
    
    # 2. Если Gemini сбоит — идем в Groq (Резерв)
    if not result:
        logging.warning("Gemini failed, switching to Groq fallback...")
        result = await get_groq_fallback(user_id, text)
    
    if result:
        user_context[user_id].append({"role": "user", "content": text})
        user_context[user_id].append({"role": "assistant", "content": result})
        return result
                
    return "Критический сбой систем. Все нейросети KAL INDUSTRIES заняты самосозерцанием."

@dp.message(F.text)
async def handle_message(message: types.Message):
    bot_info = await bot.get_me()
    is_mentioned = (f"@{bot_info.username}" in message.text) or ("кевин" in message.text.lower())
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    
    if not (message.chat.type == "private" or is_mentioned or is_reply):
        return

    ai_response = await get_ai_response(str(message.from_user.id), message.text)
    
    if "[SPLIT]" in ai_response:
        for part in ai_response.split("[SPLIT]"):
            if part.strip():
                await message.answer(part.strip())
                await asyncio.sleep(0.7)
    else:
        await message.answer(ai_response)

async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="KEVIN status: Gemini Primary."))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
