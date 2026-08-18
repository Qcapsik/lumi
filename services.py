# Lumi — Discord-бот (PyQZone)
# Copyright (C) 2026 Антон Курченко Валейрович (Qcaps). Все права защищены.
# Лицензия: см. LICENSE. Распространение без разрешения правообладателя запрещено.
"""Внешние бесплатные сервисы для Луми: погода, курсы, перевод, викторины, мемы."""

import asyncio
import json
import random

import aiohttp

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
}


async def _get(url: str, timeout: int = 20) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=UA, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status == 200:
                    return await r.read()
    except Exception:
        pass
    return None


async def _post_json(url: str, payload: dict, timeout: int = 20):
    try:
        async with aiohttp.ClientSession() as s:
            headers = {**UA, "Content-Type": "application/json"}
            async with s.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                text = await r.text()
                return r.status, text
    except Exception as e:
        return None, str(e)


async def weather(city: str) -> str:
    data = await _get(f"https://wttr.in/{city}?format=j1&lang=ru", timeout=25)
    if not data:
        return "❌ Не удалось получить погоду (сервис недоступен)."
    try:
        j = json.loads(data)
        cur = j["current_condition"][0]
        area = j.get("nearest_area", [{}])[0].get("areaName", [{}])[0].get("value", city)
        temp = cur["temp_C"]
        feel = cur["FeelsLikeC"]
        desc = cur["lang_ru"][0]["value"] if cur.get("lang_ru") else cur["weatherDesc"][0]["value"]
        wind = cur["windspeedKmph"]
        hum = cur["humidity"]
        return (
            f"🌤 Погода: **{area}**\n"
            f"▸ {desc}, **{temp}°C** (ощущается {feel}°C)\n"
            f"▸ Ветер: {wind} км/ч | Влажность: {hum}%"
        )
    except Exception:
        return f"❌ Город `{city}` не найден."


async def currency(base: str = "RUB") -> str:
    data = await _get("https://open.er-api.com/v6/latest/USD", timeout=20)
    if not data:
        return "❌ Не удалось получить курсы валют."
    try:
        j = json.loads(data)
        rates = j["rates"]
        base = base.upper()
        if base not in ("USD", "EUR", "RUB"):
            return "❌ Поддерживаются: USD, EUR, RUB."
        if base == "USD":
            usd, eur, rub = 1.0, rates.get("EUR", 0), rates.get("RUB", 0)
        elif base == "EUR":
            usd = 1 / rates.get("EUR", 1)
            eur = 1.0
            rub = rates.get("RUB", 0) * usd
        else:
            rub = 1.0
            usd = 1 / rates.get("RUB", 1)
            eur = usd * rates.get("EUR", 0)
        return (
            f"💱 Курсы (база {base}):\n"
            f"▸ 1 USD ≈ **{rub / usd:.2f} RUB**\n"
            f"▸ 1 EUR ≈ **{rub / eur:.2f} RUB**"
        )
    except Exception:
        return "❌ Ошибка получения курсов."


async def translate_text(text: str, target: str = "ru") -> str:
    pairs = {"ru": "ru", "en": "en", "uk": "uk", "de": "de", "fr": "fr", "es": "es", "zh": "zh-CN"}
    tg = pairs.get(target.lower(), target.lower())
    src = "ru" if tg != "ru" else "en"
    url = (
        f"https://api.mymemory.translated.net/get?q={text[:450]}&langpair={src}|{tg}"
    )
    data = await _get(url, timeout=20)
    if not data:
        return "❌ Сервис перевода недоступен."
    try:
        j = json.loads(data)
        out = j.get("responseData", {}).get("translatedText")
        if not out:
            return "❌ Перевод не получен."
        if "MYMEMORY WARNING" in out or "QUERY LENGTH LIMIT" in out:
            return f"⚠️ {out[:150]}"
        return f"🔤 Перевод ({tg}):\n{out}"
    except Exception:
        return "❌ Ошибка перевода."


QUIZ_CATEGORIES = {
    "geography": 22, "history": 23, "sport": 21, "games": 15, "tech": 18,
    "science": 17, "music": 12, "фильмы": 11, "кино": 11, "books": 10,
    "животные": 27, "animals": 27, "it": 18,
}


async def trivia_question(topic: str = None) -> dict | None:
    cat = None
    if topic:
        cat = QUIZ_CATEGORIES.get(topic.lower().strip())
    url = "https://opentdb.com/api.php?amount=1&type=multiple" + (f"&category={cat}" if cat else "")
    data = await _get(url, timeout=20)
    if not data:
        return None
    try:
        j = json.loads(data)
        q = j["results"][0]
        text = q["question"].replace("&#039;", "'").replace("&quot;", '"').replace("&amp;", "&")
        correct = q["correct_answer"].replace("&#039;", "'").replace("&quot;", '"').replace("&amp;", "&")
        wrong = [w.replace("&#039;", "'").replace("&quot;", '"').replace("&amp;", "&") for w in q["incorrect_answers"]]
        options = [correct, *wrong]
        random.shuffle(options)
        return {
            "question": text,
            "options": options,
            "correct_index": options.index(correct),
            "category": q["category"],
            "difficulty": q["difficulty"],
        }
    except Exception:
        return None


JOKES = [
    "Почему программисты путают Хэллоуин и Рождество? Потому что OCT 31 == DEC 25.",
    "Заходит программист в бар, а весь бар не может выйти из while(true).",
    "Оптимист видит стакан наполовину полным, пессимист — наполовину пустым, программист — вдвое больше нужного.",
    "Два бага в продакшене — это уже фича.",
    "— Ваш код работает? — Не знаю, я его ещё не написал, но тесты должен пройти!",
    "Программист не спит — он дебажит сны.",
    "1000 программистов — 1000 мнений о Formatter.",
    "Пошёл дождь. Код спрятался под try/catch?",
    "Клонов никто не любит, кроме билдов.",
    "Пятиминутка в коде длится 5 минут. Но бывает и 5 часов, если это 'просто починить кавычку'.",
]

FACTS = [
    "Осьминоги имеют три сердца и голубую кровь.",
    "Мёд никогда не портится — его находили съедобным в гробницах возрастом 3000 лет.",
    "Свету Солнца нужно ~8 минут 20 секунд, чтобы долететь до Земли.",
    "У улиток около 25 000 зубов.",
    "На Венере сутки длиннее года.",
    "Человеческое ДНК на 60% совпадает с ДНК банана.",
    "Самая короткая война в истории длилась 38 минут (Англо-занзибарская, 1896).",
    "Фламинго розовые, потому что едят креветок и водоросли с пигментом.",
    "В космосе нельзя плакать — слёзы не падают, а собираются в шарики.",
    "В среднем человек проводит во сне треть своей жизни.",
    "Слон — единственное животное, которое не умеет прыгать.",
]

TRUTHS = [
    "Кого из участников сервера ты боишься больше всего?",
    "Назови самую глупую вещь, которую делал за последний год.",
    "Что ты больше всего носил/а с собой в РАСТ?",
    "Кто из клана самый ярый тиммейт?",
    "Сколько часов ты последний раз играл за одну ночь?",
    "О чём ты жалеешь в этой игре?",
    "Когда последний раз плакал/а?",
    "Кого бы взял/а с собой на необитаемый остров из сервера?",
    "Самое обидное поражение в жизни?",
    "Сколько раз ты выходил из аккаунта за сегодня?",
]

DARES = [
    "Отправь эмодзи 🐠 в общий чат без объяснений.",
    "Поменяй ник на 'Кусь за лутание' на 1 час.",
    "Пришли в общий чат скрин из FAR CRY без подписи.",
    "Напиши 'Я люблю RUST' в чат и жди реакции.",
    "Уступи очередь в игре в пользу форума?.. Ладно, просто отпишись в общий чат: 'порядок ✅'.",
    "Поделись лучшим мемом с телефона.",
    "Скажи комплимент трём участникам сервера по очереди.",
    "Оставайся в войсе, пока не споёшь куплет песни.",
    "Сделай фото рабочего места и кинь в чат без редактуры.",
    "Напиши в ЛС ведущему, кого считаешь самым ценным игроком.",
]


async def meme() -> str:
    data = await _get("https://meme-api.com/gimme/wholesomememes", timeout=20)
    if not data:
        return None
    try:
        j = json.loads(data)
        return j.get("url") or j.get("preview", [None])[-1]
    except Exception:
        return None


def truth_or_dare(kind: str = None) -> str:
    kind = (kind or "").lower()
    if kind.startswith("действ") or kind.startswith("dare") or kind == "действие":
        return f"🎯 Действие: {random.choice(DARES)}"
    return f"🫣 Правда: {random.choice(TRUTHS)}"