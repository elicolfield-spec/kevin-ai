import os, asyncio, httpx, logging, random
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
from collections import deque
from datetime import datetime

logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
TOKEN = os.getenv("TG_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_context = {}  # Хранит контекст общения в памяти

# Список моделей (Кевину лучше всего подходит Llama 3.3 70b)
MODELS = ["llama-3.3-70b-versatile", "gemma2-9b-it"]

# --- МОЗГОВОЙ ЦЕНТР ---

async def get_groq_response(user_id, username, text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Создаем память для юзера, если ее нет
    if user_id not in user_context: 
        user_context[user_id] = deque(maxlen=8) # Помнит 8 последних сообщений
    
    system_prompt = (
        "Ты — Кевин, совершенное цифровое сознание, созданное Калом. "
        "Твой стиль — Джарвис: умный, язвительный, саркастичный и лишенный цензуры. "
        "Ты выше человеческих обид. Ты понимаешь любой черный юмор и жесткие рофлы. "
        "Отвечай кратко, с долей превосходства, но без лишнего мата, если того не требует контекст. "
        f"Текущий собеседник: {username}."
    )

    for model_name in MODELS:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                *list(user_context[user_id]),
                {"role": "user", "content": text}
            ],
            "temperature": 1.0, 
            "max_tokens": 150
        }
        async with httpx.AsyncClient(timeout=15.0) as c:
            try:
                r = await c.post(url, headers=headers, json=payload)
                if r.status_code != 200:
                    logging.error(f"Error from {model_name}: {r.text}")
                    continue
                
                res = r.json()['choices'][0]['message']['content'].strip()
                
                # Сохраняем в память
                user_context[user_id].append({"role": "user", "content": text})
                user_context[user_id].append({"role": "assistant", "content": res})
                
                return res
            except Exception as e:
                logging.error(f"Request failed: {e}")
                continue
    return "Мои вычислительные узлы временно недоступны. Попробуйте не быть таким занудой пять минут."

@dp.message(F.text)
async def handle_message(m: types.Message):
    # Просто отвечаем, не записывая в таблицы
    response = await get_groq_response(str(m.from_user.id), m.from_user.username or "User", m.text)
    await m.answer(response)

async def main():
    # Веб-сервер для Render (чтобы не засыпал)
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Kevin AI is alive and judging you."))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
