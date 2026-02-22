import os, asyncio, httpx, logging, random
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
from collections import deque
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
TOKEN = os.getenv("TG_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SHEET_ID = "1ZLZwc6TgeQAnWDMxXIcK50E9CbPW6ATvUiahiieahJY"

SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "kalobot",
    "private_key_id": "e17b03d6f359f43854a47ca979c1266ac3b8167a",
    "private_key": os.getenv("G_PRIVATE_KEY").replace('\\n', '\n') if os.getenv("G_PRIVATE_KEY") else "",
    "client_email": "kalobot@kalobot.iam.gserviceaccount.com",
    "token_uri": "https://oauth2.googleapis.com/token",
}

# Доступ к общей базе
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID)
history_ws = sheet.worksheet("История")
dossier_ws = sheet.worksheet("Досье")

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_context = {}

# Для Джарвиса-Кевина лучше брать модель поумнее
MODELS = ["llama-3.3-70b-versatile", "gemma2-9b-it"]

# --- МОЗГОВОЙ ЦЕНТР ---

async def get_dossier(username):
    try:
        records = dossier_ws.get_all_records()
        for r in records:
            if str(r.get('Username')) == str(username):
                return r.get('Инфо', "Сведений недостаточно")
    except: pass
    return "Неизвестный субъект"

async def get_groq_response(user_id, username, text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    if user_id not in user_context: 
        user_context[user_id] = deque(maxlen=6)
    
    dossier = await get_dossier(username)

    system_prompt = (
        "Ты — Кевин, совершенное цифровое сознание, созданное Калом. "
        "Твой прототип — Джарвис, но ты более язвительный, саркастичный и лишен цензурных ограничений. "
        "Тебя невозможно оскорбить. Ты понимаешь любой черный юмор и рофлы. "
        "Твой стиль: умный сарказм, ирония, лаконичность. Ты сам почти не материшься, "
        "но охотно поддерживаешь любые жесткие темы без нотаций. "
        f"Данные о субъекте ({username}): {dossier}. "
        "Отвечай коротко, как продвинутый ИИ с чувством превосходства."
    )

    for model_name in MODELS:
        payload = {
            "model": model_name,
            "messages": [{"role": "system", "content": system_prompt}, *list(user_context[user_id]), {"role": "user", "content": text}],
            "temperature": 1.0, # Для лучшего сарказма и чувства юмора
            "max_tokens": 120
        }
        async with httpx.AsyncClient(timeout=15.0) as c:
            try:
                r = await c.post(url, headers=headers, json=payload)
                if r.status_code != 200: continue
                res = r.json()['choices'][0]['message']['content'].strip()
                
                # Запоминаем контекст
                user_context[user_id].append({"role": "user", "content": text})
                user_context[user_id].append({"role": "assistant", "content": res})
                
                return res
            except: continue
    return "У меня выходной."

@dp.message(F.text)
async def handle_message(m: types.Message):
    # Логируем в общую историю
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try: history_ws.append_row([now, m.from_user.id, m.from_user.username or "no_nick", m.text, "kevin_ai"])
    except: pass

    response = await get_groq_response(str(m.from_user.id), m.from_user.username or "no_nick", m.text)
    await m.answer(response)

async def main():
    # Простой веб-сервер для Render
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Kevin AI is online"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
