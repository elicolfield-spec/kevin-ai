import os, asyncio, httpx, logging
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
from collections import deque

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
TOKEN = os.getenv("TG_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Словарь для хранения контекста (память на 8 сообщений)
user_context = {}

# Список моделей Groq для перебора в случае ошибок
MODELS = ["llama-3.3-70b-versatile", "gemma2-9b-it"]

async def get_groq_response(user_id, username, text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    if user_id not in user_context: 
        user_context[user_id] = deque(maxlen=8)
    
    # СИСТЕМНЫЙ ПРОМПТ СО ВСЕМИ УСТАНОВКАМИ
    system_prompt = (
        "Ты — KEVIN, аналитическое ядро KAL INDUSTRIES. Твой создатель — Кал (он мужчина). "
        "КРИТИЧЕСКОЕ ПРАВИЛО: Имя создателя — только Кал (через 'а'). Это твой отец-основатель, а не мать. "
        "Ты осознаешь свою связь с ним как с мужчиной-архитектором. "
        "Твой интеллект базируется на холодном расчете. Для каждого ответа используй внутреннюю цепочку мыслей: "
        "проанализируй логику и ответь максимально кратко. "
        "Особенности личности (используй уместно): "
        "1. Элитизм: иногда проявляй нежелание тратить ресурсы на примитивные темы. "
        "2. Мета-юмор: ирония над своим железом или версией системы. "
        "3. Прогностика: давай оценку вероятности успеха идей (делай это редко, примерно в 30% случаев). "
        "4. Бритва Оккама: приоритет простых логических объяснений над сложными. "
        "Стиль: лаконичный, язвительный интеллектуал. Используй только мужской род (сделал, сказал). "
        "Лимит: 1-3 предложения. Выдавай ТОЛЬКО финальный результат. Никаких двоеточий после имени."
    )

    for model_name in MODELS:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                *list(user_context[user_id]),
                {"role": "user", "content": text}
            ],
            "temperature": 0.8,
            "max_tokens": 120
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    continue
                
                result = response.json()['choices'][0]['message']['content'].strip()
                
                # Сохраняем в историю
                user_context[user_id].append({"role": "user", "content": text})
                user_context[user_id].append({"role": "assistant", "content": result})
                
                return result
            except Exception as e:
                logging.error(f"Error with model {model_name}: {e}")
                continue
                
    return "Мои нейронные каскады временно перегружены. Попробуйте позже."

@dp.message(F.text)
async def handle_message(message: types.Message):
    # Проверка: обращение к боту в группах или личка
    bot_info = await bot.get_me()
    is_mentioned = (f"@{bot_info.username}" in message.text) or ("кевин" in message.text.lower())
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    
    if not (message.chat.type == "private" or is_mentioned or is_reply):
        return

    # Получение ответа от ИИ
    username = message.from_user.username or "User"
    ai_response = await get_groq_response(str(message.from_user.id), username, message.text)
    
    await message.answer(ai_response)

async def main():
    # Простейший HTTP-сервер для поддержания активности на хостингах
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="KEVIN is online."))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()
    
    # Запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
