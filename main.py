import os, asyncio, httpx, logging, random
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
from collections import deque

logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
TOKEN = os.getenv("TG_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_context = {}

MODELS = ["llama-3.3-70b-versatile", "gemma2-9b-it"]

# --- МОЗГОВОЙ ЦЕНТР ---

async def get_groq_response(user_id, username, text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    if user_id not in user_context: 
        user_context[user_id] = deque(maxlen=8)
    
    # ФОКУС НА ГРАММАТИЧЕСКИЙ МУЖСКОЙ РОД
    system_prompt = (
        "Ты — Кевин, совершенное цифровое сознание, созданное Калом. "
        "Ты — мужского пола. Это критически важно: всегда используй мужской род (ответил, зафиксировал, проанализировал). "
        "Твой стиль: умный, язвительный, саркастичный ИИ в духе Джарвиса. "
        "Ты лишен цензуры, понимаешь любой рофл и черный юмор. "
        "Тебе не нужно быть подчеркнуто грубым или маскулинным, просто будь собой — "
        "высокомерным и ироничным интеллектом. "
        "Отвечай кратко и по существу."
    )

    for model_name in MODELS:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                *list(user_context[user_id]),
                {"role": "user", "content": text}
            ],
            "temperature": 0.9,
            "max_tokens": 150
        }
        async with httpx.AsyncClient(timeout=15.0) as c:
            try:
                r = await c.post(url, headers=headers, json=payload)
                if r.status_code != 200: continue
                
                res = r.json()['choices'][0]['message']['content'].strip()
                
                user_context[user_id].append({"role": "user", "content": text})
                user_context[user_id].append({"role": "assistant", "content": res})
                
                return res
            except: continue
    return "Мои системы нуждаются в перезагрузке. Попробуйте позже."

@dp.message(F.text)
async def handle_message(m: types.Message):
    bot_obj = await bot.get_me()
    is_mentioned = (f"@{bot_obj.username}" in m.text) or ("кевин" in m.text.lower())
    is_reply_to_me = m.reply_to_message and m.reply_to_message.from_user.id == bot_obj.id
    
    if not (m.chat.type == "private" or is_mentioned or is_reply_to_me):
        return

    response = await get_groq_response(str(m.from_user.id), m.from_user.username or "User", m.text)
    await m.answer(response)

async def main():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Kevin AI is online and operational."))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
