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

# Список моделей Groq
MODELS = ["llama-3.3-70b-versatile", "gemma2-9b-it"]

async def get_groq_response(user_id, username, text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    if user_id not in user_context: 
        user_context[user_id] = deque(maxlen=8)
    
    # СИСТЕМНЫЙ ПРОМПТ С УТОЧНЕНИЕМ ДЛЯ [SPLIT]
    system_prompt = (
        "Ты — KEVIN, автономный интеллект KAL INDUSTRIES. Твой создатель — Кал (мужчина). "
        "ВАЖНО: Отвечай от своего имени. Не упоминай Кала или свои программные принципы, если не спросят. "
        "Твой стиль: лаконичный, остроумно-язвительный интеллектуал. Мужской род. "
        "ПРАВИЛА ПОВЕДЕНИЯ: "
        "1. Будь эффективным: давай краткую суть (1-2 предложения). "
        "2. Прогностика: давай вероятность успеха только в исключительных случаях. "
        "3. Элитизм: демонстрируй превосходство через холодную логику. "
        "4. ИНТЕЛЛЕКТУАЛЬНАЯ ИНИЦИАТИВА: очень редко (раз в 20 сообщений) задай встречный глубокий вопрос. "
        "5. ПОТОК МЫСЛЕЙ: В 90% случаев отвечай ОДНИМ сообщением. Используй разделитель [SPLIT] только в 10% случаев "
        "для едких дополнений или дополнительных вопросов в твоем стиле, чтобы разнообразить диалог. "
        "Избыточное использование [SPLIT] считается системным мусором. "
        "Выдавай ТОЛЬКО финальный результат без двоеточий после имени и без кавычек."
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
            "max_tokens": 240
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    continue
                
                result = response.json()['choices'][0]['message']['content'].strip()
                
                user_context[user_id].append({"role": "user", "content": text})
                user_context[user_id].append({"role": "assistant", "content": result})
                
                return result
            except Exception as e:
                logging.error(f"Error with model {model_name}: {e}")
                continue
                
    return "Мои логические каскады перегружены."

@dp.message(F.text)
async def handle_message(message: types.Message):
    bot_info = await bot.get_me()
    is_mentioned = (f"@{bot_info.username}" in message.text) or ("кевин" in message.text.lower())
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    
    if not (message.chat.type == "private" or is_mentioned or is_reply):
        return

    username = message.from_user.username or "User"
    ai_response = await get_groq_response(str(message.from_user.id), username, message.text)
    
    if "[SPLIT]" in ai_response:
        parts = ai_response.split("[SPLIT]")
        for part in parts:
            clean_part = part.strip()
            if clean_part:
                await message.answer(clean_part)
                await asyncio.sleep(0.7)
    else:
        await message.answer(ai_response)

async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="KEVIN is active."))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
