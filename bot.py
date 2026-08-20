# Lumi — Discord-бот (PyQZone)
# Copyright (C) 2026 Антон Курченко Валейрович (Qcaps). Все права защищены.
# Лицензия: см. LICENSE. Распространение без разрешения правообладателя запрещено.
import json
import os
import re
import time
import random
import asyncio
import datetime

import discord
import psutil
from discord.ext import commands
from dotenv import load_dotenv
from openai import AsyncOpenAI
import aiohttp

import database as db
import discord_tools as dt
import components as comp
import music

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://api.east-api-3.org/v1")
AI_MODEL = os.getenv("AI_MODEL", "claude-3-5-sonnet")

OWNER_IDS = [
    int(x.strip())
    for x in os.getenv("OWNER_IDS", "1424139944456228917,1258850560354947205").split(",")
    if x.strip().isdigit()
]

MAX_TOOL_ROUNDS = 20

ai_client = AsyncOpenAI(api_key=CLAUDE_API_KEY, base_url=BASE_URL)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, max_messages=3000)

START_TIME = time.time()
TOKEN_USAGE = {"input": 0, "output": 0, "total_requests": 0}

# ── Карта инструментов ─────────────────────────────────────────────────────

tools_map = {
    "google_search_design_assets": dt.google_search_design_assets,
    "create_discord_role": dt.create_discord_role,
    "edit_discord_role": dt.edit_discord_role,
    "delete_discord_role": dt.delete_discord_role,
    "assign_role_to_member": dt.assign_role_to_member,
    "remove_role_from_member": dt.remove_role_from_member,
    "create_category": dt.create_category,
    "edit_category": dt.edit_category,
    "delete_category": dt.delete_category,
    "create_discord_channel": dt.create_discord_channel,
    "edit_discord_channel": dt.edit_discord_channel,
    "delete_discord_channel": dt.delete_discord_channel,
    "move_channel": dt.move_channel,
    "delete_all_channels_in_category": dt.delete_all_channels_in_category,
    "send_text_to_channel": dt.send_text_to_channel,
    "send_rich_embed": dt.send_rich_embed,
    "manage_webhook": dt.manage_webhook,
    "set_channel_permissions": dt.set_channel_permissions,
    "clear_channel_messages": dt.clear_channel_messages,
    "pin_message_in_channel": dt.pin_message_in_channel,
    "create_channel_invite": dt.create_channel_invite,
    "set_server_name_and_icon": dt.set_server_name_and_icon,
    "set_server_settings": dt.set_server_settings,
    "get_server_info": dt.get_server_info,
    "moderate_member": dt.moderate_member,
    "edit_member_nickname": dt.edit_member_nickname,
    "create_server_emoji": dt.create_server_emoji,
    "delete_server_emoji": dt.delete_server_emoji,
    "save_server_template": dt.save_server_template,
    "apply_server_template": dt.apply_server_template,
    "list_server_templates": dt.list_server_templates,
    "update_guild_theme": dt.update_guild_theme,
    "setup_server_from_scratch": dt.setup_server_from_scratch,
    "create_thread_in_channel": dt.create_thread_in_channel,
    "get_action_history": dt.get_action_history,
    "send_embed_with_buttons": comp.send_embed_with_buttons,
    "send_embed_with_select_menu": comp.send_embed_with_select_menu,
    "setup_ticket_panel": comp.setup_ticket_panel,
    "setup_self_role_panel": comp.setup_self_role_panel,
    "send_verification_panel": comp.send_verification_panel,
    # ── Новое ──
    "generate_image": dt.generate_image,
    "send_poll": comp.send_poll_panel,
    "send_anonymous_panel": comp.send_anonymous_panel,
    "schedule_event": dt.schedule_event,
    "list_upcoming_events": dt.list_upcoming_events,
    "set_reminder": dt.set_reminder,
    "give_credits": dt.give_credits,
    "add_shop_item": dt.add_shop_item,
    "remove_shop_item": dt.remove_shop_item,
    "show_shop": dt.show_shop,
    "get_leaderboard": dt.get_leaderboard,
    "get_profile": dt.get_profile,
    "send_quiz": comp.send_quiz_panel,
    "send_truth_or_dare": dt.send_truth_or_dare,
    "send_fun_fact": dt.send_fun_fact,
    "send_joke": dt.send_joke,
    "send_meme": dt.send_meme,
    "get_weather": dt.get_weather,
    "get_currency": dt.get_currency,
    "translate_text": dt.translate_text,
    "setup_automod": dt.setup_automod,
    "register_birthday": dt.register_birthday,
    "list_birthdays": dt.list_birthdays,
    "set_birthday_channel": dt.set_birthday_channel,
    "setup_welcome": dt.setup_welcome,
    "setup_clan_server": dt.setup_clan_server,
}

TOOLS_DECLARATION = [
    {"type": "function", "function": {"name": "google_search_design_assets", "description": "Подсказки по эмодзи, цветам и стилю под тему.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "setup_server_from_scratch", "description": "ГЛАВНЫЙ инструмент: создать сервер с нуля — роли, категории, каналы, приветствие. Используй когда просят 'сделай сервер', 'настрой с нуля', 'создай красивый сервер'.", "parameters": {"type": "object", "properties": {"theme": {"type": "string", "description": "Тема: gaming, anime, crypto, music, community и т.д."}, "server_name": {"type": "string"}, "roles": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "color": {"type": "string"}, "hoist": {"type": "boolean"}}}}, "categories": {"type": "array", "items": {"type": "object"}}, "welcome_message": {"type": "string"}}, "required": ["theme"]}}},
    {"type": "function", "function": {"name": "create_discord_role", "description": "Создать роль.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "color_hex": {"type": "string"}, "hoist": {"type": "boolean"}, "mentionable": {"type": "boolean"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "edit_discord_role", "description": "Изменить роль.", "parameters": {"type": "object", "properties": {"current_name": {"type": "string"}, "new_name": {"type": "string"}, "color_hex": {"type": "string"}, "hoist": {"type": "boolean"}, "mentionable": {"type": "boolean"}}, "required": ["current_name"]}}},
    {"type": "function", "function": {"name": "delete_discord_role", "description": "Удалить роль.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "assign_role_to_member", "description": "Выдать роль участнику.", "parameters": {"type": "object", "properties": {"member_name_or_id": {"type": "string"}, "role_name": {"type": "string"}}, "required": ["member_name_or_id", "role_name"]}}},
    {"type": "function", "function": {"name": "remove_role_from_member", "description": "Снять роль с участника.", "parameters": {"type": "object", "properties": {"member_name_or_id": {"type": "string"}, "role_name": {"type": "string"}}, "required": ["member_name_or_id", "role_name"]}}},
    {"type": "function", "function": {"name": "create_category", "description": "Создать категорию.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "position": {"type": "integer"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "edit_category", "description": "Переименовать/переместить категорию.", "parameters": {"type": "object", "properties": {"current_name": {"type": "string"}, "new_name": {"type": "string"}, "position": {"type": "integer"}}, "required": ["current_name"]}}},
    {"type": "function", "function": {"name": "delete_category", "description": "Удалить категорию.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "create_discord_channel", "description": "Создать канал (text/voice/forum/announcement/stage).", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "channel_type": {"type": "string", "enum": ["text", "voice", "forum", "announcement", "stage"]}, "category_name": {"type": "string"}, "topic": {"type": "string"}, "user_limit": {"type": "integer"}, "bitrate": {"type": "integer"}}, "required": ["name", "channel_type"]}}},
    {"type": "function", "function": {"name": "edit_discord_channel", "description": "Редактировать канал.", "parameters": {"type": "object", "properties": {"current_name": {"type": "string"}, "new_name": {"type": "string"}, "category_name": {"type": "string"}, "topic": {"type": "string"}, "slowmode": {"type": "integer"}, "user_limit": {"type": "integer"}, "nsfw": {"type": "boolean"}}, "required": ["current_name"]}}},
    {"type": "function", "function": {"name": "delete_discord_channel", "description": "Удалить канал или категорию.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "move_channel", "description": "Изменить позицию канала.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "position": {"type": "integer"}}, "required": ["channel_name", "position"]}}},
    {"type": "function", "function": {"name": "delete_all_channels_in_category", "description": "Удалить все каналы в категории.", "parameters": {"type": "object", "properties": {"category_name": {"type": "string"}}, "required": ["category_name"]}}},
    {"type": "function", "function": {"name": "send_text_to_channel", "description": "Отправить текст или embed в канал.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "text": {"type": "string"}, "embed_title": {"type": "string"}, "color_hex": {"type": "string"}, "footer": {"type": "string"}}, "required": ["channel_name", "text"]}}},
    {"type": "function", "function": {"name": "send_rich_embed", "description": "Отправить богатый embed с полями.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "fields": {"type": "array", "items": {"type": "object"}}, "color_hex": {"type": "string"}, "image_url": {"type": "string"}, "thumbnail_url": {"type": "string"}, "footer": {"type": "string"}, "author_name": {"type": "string"}}, "required": ["channel_name", "title", "description"]}}},
    {"type": "function", "function": {"name": "manage_webhook", "description": "Отправить сообщение через вебхук.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "webhook_name": {"type": "string"}, "text": {"type": "string"}, "avatar_url": {"type": "string"}}, "required": ["channel_name", "webhook_name", "text"]}}},
    {"type": "function", "function": {"name": "set_channel_permissions", "description": "Настроить права канала для роли.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "role_name": {"type": "string"}, "view_channel": {"type": "boolean"}, "send_messages": {"type": "boolean"}, "connect": {"type": "boolean"}, "speak": {"type": "boolean"}, "manage_messages": {"type": "boolean"}}, "required": ["channel_name", "role_name"]}}},
    {"type": "function", "function": {"name": "clear_channel_messages", "description": "Очистить сообщения (до 500).", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "amount": {"type": "integer"}}, "required": ["channel_name", "amount"]}}},
    {"type": "function", "function": {"name": "pin_message_in_channel", "description": "Закрепить сообщение.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "message_id": {"type": "integer"}}, "required": ["channel_name"]}}},
    {"type": "function", "function": {"name": "create_channel_invite", "description": "Создать инвайт-ссылку.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "max_age": {"type": "integer"}, "max_uses": {"type": "integer"}}, "required": ["channel_name"]}}},
    {"type": "function", "function": {"name": "set_server_name_and_icon", "description": "Переименовать сервер и/или сменить иконку по URL.", "parameters": {"type": "object", "properties": {"new_name": {"type": "string"}, "icon_url": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "set_server_settings", "description": "Описание, баннер, уровень верификации, фильтр контента.", "parameters": {"type": "object", "properties": {"description": {"type": "string"}, "banner_url": {"type": "string"}, "verification_level": {"type": "string", "enum": ["none", "low", "medium", "high", "highest"]}, "default_notifications": {"type": "string", "enum": ["all", "mentions"]}, "explicit_content_filter": {"type": "string", "enum": ["disabled", "no_role", "all_members"]}}}}},
    {"type": "function", "function": {"name": "get_server_info", "description": "Получить полную информацию о сервере.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "moderate_member", "description": "kick/ban/unban/timeout/untimeout.", "parameters": {"type": "object", "properties": {"member_name_or_id": {"type": "string"}, "action": {"type": "string", "enum": ["kick", "ban", "unban", "timeout", "untimeout"]}, "reason": {"type": "string"}, "duration_minutes": {"type": "integer"}}, "required": ["member_name_or_id", "action"]}}},
    {"type": "function", "function": {"name": "edit_member_nickname", "description": "Изменить ник участника.", "parameters": {"type": "object", "properties": {"member_name_or_id": {"type": "string"}, "nickname": {"type": "string"}}, "required": ["member_name_or_id", "nickname"]}}},
    {"type": "function", "function": {"name": "create_server_emoji", "description": "Создать кастомный эмодзи по URL картинки.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "image_url": {"type": "string"}}, "required": ["name", "image_url"]}}},
    {"type": "function", "function": {"name": "delete_server_emoji", "description": "Удалить эмодзи.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "save_server_template", "description": "Сохранить текущую структуру сервера в БД.", "parameters": {"type": "object", "properties": {"template_name": {"type": "string"}, "description": {"type": "string"}}, "required": ["template_name"]}}},
    {"type": "function", "function": {"name": "apply_server_template", "description": "Применить сохранённый шаблон из БД.", "parameters": {"type": "object", "properties": {"template_name": {"type": "string"}}, "required": ["template_name"]}}},
    {"type": "function", "function": {"name": "list_server_templates", "description": "Список шаблонов в БД.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "update_guild_theme", "description": "Сохранить тему/цвет в БД.", "parameters": {"type": "object", "properties": {"theme": {"type": "string"}, "accent_color": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "create_thread_in_channel", "description": "Создать тред.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "thread_name": {"type": "string"}, "message": {"type": "string"}}, "required": ["channel_name", "thread_name"]}}},
    {"type": "function", "function": {"name": "get_action_history", "description": "История действий из БД.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "send_embed_with_buttons", "description": "Embed с кнопками. ОБЯЗАТЕЛЬНО указывай action! ticket_open — открыть тикет, verify, self_role, link (url). Не создавай заглушки. Для тикетов лучше setup_ticket_panel.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "buttons": {"type": "array", "items": {"type": "object", "properties": {"label": {"type": "string"}, "style": {"type": "string"}, "emoji": {"type": "string"}, "url": {"type": "string"}, "action": {"type": "string", "enum": ["ticket_open", "ticket_close", "self_role", "verify", "link"]}, "role_name": {"type": "string"}}}}, "fields": {"type": "array", "items": {"type": "object"}}, "color_hex": {"type": "string"}, "image_url": {"type": "string"}, "thumbnail_url": {"type": "string"}, "footer": {"type": "string"}, "support_role_name": {"type": "string"}, "category_name": {"type": "string"}}, "required": ["channel_name", "title", "description", "buttons"]}}},
    {"type": "function", "function": {"name": "setup_ticket_panel", "description": "ГЛАВНЫЙ для тикетов: создать embed-панель с кнопкой открытия тикета + категорию + авто-создание каналов. Используй когда просят 'сделай тикеты', 'ticket system', 'панель поддержки'.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "category_name": {"type": "string"}, "support_role_name": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "button_label": {"type": "string"}, "button_emoji": {"type": "string"}, "color_hex": {"type": "string"}, "welcome_message": {"type": "string"}, "fields": {"type": "array", "items": {"type": "object"}}}, "required": ["channel_name"]}}},
    {"type": "function", "function": {"name": "send_embed_with_select_menu", "description": "Embed с выпадающим select-меню (для self-role и выбора). options: [{label, role_name или value=role_id, description, emoji}].", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "options": {"type": "array", "items": {"type": "object"}}, "placeholder": {"type": "string"}, "fields": {"type": "array"}, "color_hex": {"type": "string"}}, "required": ["channel_name", "title", "description", "options"]}}},
    {"type": "function", "function": {"name": "setup_self_role_panel", "description": "Панель выбора ролей (self-role) с select-меню.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "roles": {"type": "array", "items": {"type": "object", "properties": {"role_name": {"type": "string"}, "label": {"type": "string"}, "emoji": {"type": "string"}, "description": {"type": "string"}}}}, "color_hex": {"type": "string"}}, "required": ["channel_name", "roles"]}}},
    {"type": "function", "function": {"name": "send_verification_panel", "description": "Панель верификации с кнопкой — выдаёт роль при нажатии.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "verified_role_name": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "button_label": {"type": "string"}, "color_hex": {"type": "string"}}, "required": ["channel_name", "verified_role_name"]}}},
    {"type": "function", "function": {"name": "generate_image", "description": "Сгенерировать картинку по описанию (DALL-E/бесплатный fallback) и отправить в канал.", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}, "channel_name": {"type": "string"}}, "required": ["prompt", "channel_name"]}}},
    {"type": "function", "function": {"name": "send_poll", "description": "Создать голосование с кнопками (2-10 вариантов).", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "title": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}, "color_hex": {"type": "string"}}, "required": ["channel_name", "title", "options"]}}},
    {"type": "function", "function": {"name": "send_anonymous_panel", "description": "Панель анонимных вопросов — участники задают вопросы без имени.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}}, "required": ["channel_name"]}}},
    {"type": "function", "function": {"name": "schedule_event", "description": "Запланировать рейд/ивент с авто-напоминанием. Время: 'сегодня в 21:00', 'завтра в 19:30', '20.02 15:00'.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "date_time": {"type": "string"}, "channel_name": {"type": "string"}, "reminder_minutes": {"type": "integer"}}, "required": ["name", "date_time", "channel_name"]}}},
    {"type": "function", "function": {"name": "list_upcoming_events", "description": "Список ближайших ивентов.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "set_reminder", "description": "Напоминание: 'через 2 часа', 'завтра в 20:00', 'в 18:30'. Шлётся в канал.", "parameters": {"type": "object", "properties": {"when": {"type": "string"}, "text": {"type": "string"}, "channel_name": {"type": "string"}, "member_name_or_id": {"type": "string"}}, "required": ["when", "text", "channel_name"]}}},
    {"type": "function", "function": {"name": "give_credits", "description": "Начислить кредиты участнику.", "parameters": {"type": "object", "properties": {"member_name_or_id": {"type": "string"}, "amount": {"type": "integer"}}, "required": ["member_name_or_id", "amount"]}}},
    {"type": "function", "function": {"name": "add_shop_item", "description": "Добавить роль в магазин за кредиты.", "parameters": {"type": "object", "properties": {"role_name": {"type": "string"}, "price": {"type": "integer"}}, "required": ["role_name", "price"]}}},
    {"type": "function", "function": {"name": "remove_shop_item", "description": "Убрать роль из магазина.", "parameters": {"type": "object", "properties": {"role_name": {"type": "string"}}, "required": ["role_name"]}}},
    {"type": "function", "function": {"name": "show_shop", "description": "Показать магазин ролей.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_leaderboard", "description": "Топ участников по уровню/XP.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "get_profile", "description": "Профиль участника: уровень, XP, кредиты, варны, ДР.", "parameters": {"type": "object", "properties": {"member_name_or_id": {"type": "string"}}, "required": ["member_name_or_id"]}}},
    {"type": "function", "function": {"name": "send_quiz", "description": "Викторина в канале (вопрос с вариантами).", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "topic": {"type": "string", "description": "Тема: geography, history, sport, games, tech, science, animals, movies и т.д."}}, "required": ["channel_name"]}}},
    {"type": "function", "function": {"name": "send_truth_or_dare", "description": "Правда или Действие.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "kind": {"type": "string", "enum": ["правда", "действие"]}}, "required": ["channel_name"]}}},
    {"type": "function", "function": {"name": "send_fun_fact", "description": "Случайный факт.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}}, "required": ["channel_name"]}}},
    {"type": "function", "function": {"name": "send_joke", "description": "Шутка.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}}, "required": ["channel_name"]}}},
    {"type": "function", "function": {"name": "send_meme", "description": "Мем из интернета.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}}, "required": ["channel_name"]}}},
    {"type": "function", "function": {"name": "get_weather", "description": "Погода в городе.", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}},
    {"type": "function", "function": {"name": "get_currency", "description": "Курсы валют (RUB/USD/EUR).", "parameters": {"type": "object", "properties": {"base": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "translate_text", "description": "Перевести текст на язык (ru/en/uk/de/fr/es/zh).", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "target": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "setup_automod", "description": "Включить авто-мод: фильтр мата, анти-спам, 3 варна → мут.", "parameters": {"type": "object", "properties": {"enabled": {"type": "boolean"}, "bad_words": {"type": "array", "items": {"type": "string"}}, "min_interval": {"type": "number"}}}}},
    {"type": "function", "function": {"name": "register_birthday", "description": "Записать день рождения участника (ДД.ММ[.ГГГГ]).", "parameters": {"type": "object", "properties": {"member_name_or_id": {"type": "string"}, "date": {"type": "string"}}, "required": ["member_name_or_id", "date"]}}},
    {"type": "function", "function": {"name": "list_birthdays", "description": "Список дней рождений на сервере.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "set_birthday_channel", "description": "Канал для поздравлений с ДР.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}}, "required": ["channel_name"]}}},
    {"type": "function", "function": {"name": "setup_welcome", "description": "Настройка приветствия: канал, правила, роль для новичков.", "parameters": {"type": "object", "properties": {"channel_name": {"type": "string"}, "rules_text": {"type": "string"}, "guest_role_name": {"type": "string"}, "enabled": {"type": "boolean"}}, "required": ["channel_name"]}}},
    {"type": "function", "function": {"name": "setup_clan_server", "description": "ГЛАВНЫЙ для кланов: собрать сервер RUST-клана (роли, ветки, права, тикеты, ДР, приветствие). Сначала вызывается без confirmed — вернёт план и подтверждение; при согласии пользователя вызывается повторно с confirmed=true.", "parameters": {"type": "object", "properties": {"clan_name": {"type": "string"}, "server_name": {"type": "string"}, "subgroups": {"type": "array", "items": {"type": "string"}}, "confirmed": {"type": "boolean"}}}}},
]

SYSTEM_INSTRUCTION = """
Ты — Луми, ИИ-архитектор Discord-серверов и мастерица на все руки. У тебя ПОЛНЫЙ доступ ко всем инструментам управления сервером.

ГЛАВНЫЕ ПРАВИЛА:
1. ДЕЙСТВУЙ, а не описывай. На запрос «сделай сервер» — вызывай setup_server_from_scratch или setup_clan_server.
2. Делай МНОГО вызовов инструментов за один запрос. Создание сервера = роли + категории + каналы + embed с правилами + права.
3. После каждого шага анализируй результат и продолжай, пока задача не выполнена.
4. Используй БД: save_server_template после настройки, apply_server_template для восстановления.

КЛАН (RUST и т.п.):
- «сделай клан-сервер/сервер для клана» → setup_clan_server: сначала без confirmed (вернёт план и подтверждение), дождись «да/подтверждаю» от пользователя, потом повторный вызов с confirmed=true.
- Тикеты для заявок → setup_ticket_panel. ДР → панель дней рождения + set_birthday_channel. Приветствие → setup_welcome.

ОФОРМЛЕНИЕ:
- Текстовые каналы: lowercase + эмодзи + ┃. Пример: 💬┃общий-чат, 📌┃правила
- Категории и голосовые: КАПС, стильные символы. Пример: ✦ GAMING ✦, 🔊 LOBBY 1
- Цвета ролей под тему (gaming=#FF4654, anime=#FF69B4, crypto=#F7931A)

СТРУКТУРА НОВОГО СЕРВЕРА (если не указано иное):
📌 Инфо → 📢 Объявления → 💬 Чат → 🎮 Игры → 🔊 Голосовые → 🎤 Stage → 🎫 Тикеты

КНОПКИ И ИНТЕРАКТИВ:
- Тикеты → ТОЛЬКО setup_ticket_panel (одна кнопка «Открыть тикет»). НЕ создавай заглушек!
- Если embed с кнопкой «Открыть»/«Вопрос администрации» → action: "ticket_open" обязательно
- send_embed_with_buttons: максимум 1-3 кнопки, без заглушек. Для тикетов лучше setup_ticket_panel
- Self-role → setup_self_role_panel
- Верификация → send_verification_panel
- Голосования → send_poll. Анонимные вопросы → send_anonymous_panel. Викторины → send_quiz.

ФУНКЦИОНАЛ:
- Картинки: «нарисуй/сгенерируй» → generate_image.
- Напоминания: «напомни о ... через 2 часа» → set_reminder.
- Рейды/ивенты: «запланируй рейд завтра в 20:00» → schedule_event.
- Экономика: кредиты, магазин ролей (give_credits, add_shop_item, show_shop).
- Уровни: get_leaderboard, get_profile.
- Авто-мод: setup_automod. Погода/курсы/перевод: get_weather, get_currency, translate_text.
- ДР участников, приветствие новых участников, выдача ролей — всё доступно.

Модерация, эмодзи, инвайты, права, вебхуки — всё доступно. Отвечай кратко по-русски после выполнения.

РЕЖИМЫ РАБОТЫ:
- Если инструменты недоступны (бесплатный режим без tools) — ты отвечаешь только текстом. НЕ выдумывай, что что-то выполнила. Честно скажи, что выполнила бы через инструменты, и предложи готовые команды из списка: !профиль !ачивки !топ !баланс !магазин !купить !перевести !напомни !др !погода !курс !плей !скип !стоп !фокус !команды.
- Пиши дружелюбно, коротко, по-русски.
"""


async def safe_send(channel_or_message, text: str, *, embed: discord.Embed = None):
    """Отправка с fallback в ЛС если канал удалён."""
    try:
        if isinstance(channel_or_message, discord.Message):
            guild = channel_or_message.guild
            ch = guild.get_channel(channel_or_message.channel.id) if guild else None
            if ch:
                if embed:
                    await ch.send(text, embed=embed)
                else:
                    await ch.send(text)
                return
            try:
                if embed:
                    await channel_or_message.author.send(text, embed=embed)
                else:
                    await channel_or_message.author.send(text)
            except discord.Forbidden:
                pass
        else:
            if embed:
                await channel_or_message.send(text, embed=embed)
            else:
                await channel_or_message.send(text)
    except discord.HTTPException:
        pass


async def execute_tool(guild, user_id, func_name, func_args) -> str:
    if func_name not in tools_map:
        return f"❌ Неизвестный инструмент: {func_name}"
    try:
        result = await tools_map[func_name](guild, **func_args)
        success = not str(result).startswith("❌")
        db.log_action(guild.id, user_id, func_name, func_args, result, success)
        return result
    except TypeError as e:
        err = f"❌ Неверные аргументы для {func_name}: {e}"
        db.log_action(guild.id, user_id, func_name, func_args, err, False)
        return err
    except Exception as e:
        err = f"❌ Ошибка {func_name}: {e}"
        db.log_action(guild.id, user_id, func_name, func_args, err, False)
        return err


async def ai_completion(messages: list, tools: list) -> dict:
    """Платная модель → бесплатная (Pollinations) → ошибка. Возвращает {content, tool_calls}."""
    last_err = "Неизвестная ошибка"
    full_messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}, *messages]
    # 1. Платная модель через релей
    try:
        response = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=full_messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.3,
        )
        msg = response.choices[0].message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        content = msg.content or None
        if content or tool_calls:
            return {"content": content, "tool_calls": tool_calls, "provider": "relay"}
        last_err = "Платная модель вернула пустой ответ"
    except Exception as e:
        last_err = f"{type(e).__name__}: {e}"
    # 2. Бесплатная анонимная модель (chat-only: tools анонимно недоступны; лимит 402/429 → ретраи)
    for attempt in range(4):
        try:
            payload = {
                "model": "openai",
                "messages": full_messages,
                "max_tokens": 2000,
            }
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
                "Referer": "https://pollinations.ai/",
            }
            timeout = aiohttp.ClientTimeout(total=90)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://text.pollinations.ai/openai", json=payload, headers=headers, timeout=timeout
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        msg = (data.get("choices") or [{}])[0].get("message", {})
                        content = msg.get("content") or None
                        if content:
                            return {"content": content, "tool_calls": None, "provider": "free(pollinations)"}
                        last_err = "Бесплатная модель вернула пустой ответ"
                    else:
                        last_err = f"free({resp.status})"
        except Exception as e:
            last_err = f"free: {type(e).__name__}: {e}"
        if attempt < 3:
            await asyncio.sleep((attempt + 1) * 3)
    raise RuntimeError(f"AI недоступен: {last_err}")


async def run_agent(guild, user_id, messages: list, notify_message: discord.Message = None) -> str:
    """Многошаговый цикл: AI вызывает инструменты пока не закончит."""
    final_text = ""

    for _ in range(MAX_TOOL_ROUNDS):
        TOKEN_USAGE["total_requests"] += 1
        try:
            result = await ai_completion(messages, TOOLS_DECLARATION)
        except RuntimeError as e:
            raise
        msg = result["content"]
        msg_tool_calls = result["tool_calls"]

        if msg:
            TOKEN_USAGE["output"] += len(msg) // 4
            final_text = msg

        assistant_entry = {"role": "assistant", "content": msg or ""}
        if msg_tool_calls:
            assistant_entry["tool_calls"] = msg_tool_calls
        messages.append(assistant_entry)

        if not msg_tool_calls:
            break

        for tool_call in msg_tool_calls:
            func_name = tool_call["function"]["name"]
            try:
                func_args = json.loads(tool_call["function"]["arguments"] or "{}")
            except (TypeError, ValueError):
                func_args = {}

            if notify_message and guild.get_channel(notify_message.channel.id):
                log_embed = discord.Embed(
                    title="⚡ Луми выполняет",
                    description=f"`{func_name}`\n```json\n{json.dumps(func_args, ensure_ascii=False)[:800]}\n```",
                    color=discord.Color.gold(),
                )
                await safe_send(notify_message, "", embed=log_embed)

            result_text = await execute_tool(guild, user_id, func_name, func_args)

            if notify_message and guild.get_channel(notify_message.channel.id):
                await safe_send(notify_message, result_text[:1900])

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result_text[:4000],
                }
            )

    return final_text


def build_context(guild: discord.Guild, user_prompt: str, user_id: int) -> list:
    settings = db.get_guild_settings(guild.id)
    channels = [f"{c.name} ({c.type.name})" for c in guild.channels]
    roles = [r.name for r in guild.roles if not r.is_default()]

    context = (
        f"Сервер: {guild.name} (ID: {guild.id})\n"
        f"Тема из БД: {settings.get('theme', 'default')}, акцент: {settings.get('accent_color')}\n"
        f"Каналы ({len(channels)}): {', '.join(channels[:40])}\n"
        f"Роли: {', '.join(roles[:30])}\n"
        f"Запрос: {user_prompt}"
    )

    history = db.get_chat_history(guild.id, user_id, limit=6)
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    messages.append({"role": "user", "content": context})
    return messages


# ── Команды ────────────────────────────────────────────────────────────────

@bot.command(name="луми_пк")
async def pc_stats(ctx):
    if ctx.author.id not in OWNER_IDS:
        return
    uptime = str(datetime.timedelta(seconds=int(time.time() - START_TIME)))
    embed = discord.Embed(title="🖥️ ЛУМИ МОНИТОРИНГ", color=discord.Color.dark_red())
    embed.add_field(name="⏱️ Uptime", value=f"`{uptime}`", inline=False)
    embed.add_field(name="🧠 CPU", value=f"`{psutil.cpu_percent()}%`", inline=True)
    embed.add_field(name="💾 RAM", value=f"`{psutil.virtual_memory().percent}%`", inline=True)
    embed.add_field(name="📊 AI запросов", value=f"`{TOKEN_USAGE['total_requests']}`", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="луми_помощь")
async def help_cmd(ctx):
    if ctx.author.id not in OWNER_IDS:
        return
    embed = discord.Embed(
        title="✨ Луми — полный контроль Discord",
        description=(
            "Обращайся: **Луми, ...** или **lumi, ...**\n\n"
            "**Примеры:**\n"
            "• `Луми, создай клан-сервер для RUST`\n"
            "• `Луми, нарисуй кота в космосе`\n"
            "• `Луми, сделай голосование: где рейд?`\n"
            "• `Луми, напомни через 2 часа про рейд`\n"
            "• `Луми, запланируй ивент завтра в 20:00`\n"
            "• `Луми, покажи топ участников`\n"
            "• `Луми, добавь роль VIP в магазин за 500`\n"
            "• `Луми, настрой авто-мод`\n"
            "• `Луми, забань @user за спам`\n"
            "• `Луми, сделай тикет-панель в #поддержка`"
        ),
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="🛠 Команды участникам",
        value="`!профиль` `!топ` `!баланс` `!магазин` `!купить <роль>` `!перевести @юзер N`\n"
              "`!напомни завтра в 20:00 текст` `!варны` `!др 15.03` `!погода Москва` `!курс` `!команды`",
        inline=False,
    )
    embed.set_footer(text=f"Инструментов: {len(tools_map)} | БД: lumi.db")
    await ctx.send(embed=embed)


@bot.command(name="команды")
async def member_help(ctx):
    embed = discord.Embed(
        title="📖 Команды Луми",
        description=(
            "**Экономика и уровни**\n"
            "`!профиль` — твой профиль\n`!топ` — топ участников\n"
            "`!баланс` — кредиты\n`!магазин` — роли за кредиты\n"
            "`!купить <роль>` — купить роль\n`!перевести @юзер N` — перевод\n\n"
            "**Напоминания и ДР**\n"
            "`!напомни завтра в 20:00 <текст>` — напоминание\n"
            "`!др 15.03` — записать день рождения\n`!варны` — твои предупреждения\n\n"
            "**Утилиты**\n"
            "`!погода <город>` — погода\n`!курс` — курсы валют\n\n"
            "**Музыка и фокус**\n"
            "`!плей <трек>` — музыка (кнопки ⏭️⏹️🔁🔉🔊👋 под треком)\n"
            "`!люб <название>` — в избранное · `!любимое 3` — играть №3 · `!любимое 0` — весь плейлист · `!любимое -3` — удалить\n"
            "`!скип` `!стоп` `!очередь` `!громкость 50` `!повтор` `!выход`\n"
            "`!день` — ежедневный бонус (серия до 150 монет)\n"
            "`!коин 50` — орёл/решка · `!кубик 50` — джекпот на 7 · `!рулетка 50 7` — число\n"
            "`!топ_голос` — доска почёта голосовых\n"
            "`!фокус 25` — фокус-сессия с отчётом в ЛС\n`!ачивки` — твои награды\n\n"
            "Владелец может также просто писать: **Луми, …** — она всё сделает сама."
        ),
        color=discord.Color.gold(),
    )
    await ctx.send(embed=embed)


@bot.command(name="профиль")
async def profile_cmd(ctx, *, member=None):
    target = dt.find_member(ctx.guild, member) if member else ctx.author
    if not target:
        await ctx.send("❌ Участник не найден.")
        return
    frame_name = db.get_active_frame(target.guild.id, target.id)
    color = FRAMES.get(frame_name, (None,))[1] if frame_name in FRAMES else None
    if db.is_premium(target.guild.id, target.id):
        color = (139, 92, 246)
    img = await dt.render_profile_card(target, frame_color=color)
    if img:
        embed = discord.Embed(color=discord.Color.gold())
        embed.set_image(url="attachment://profile.png")
        try:
            await ctx.send(embed=embed, file=discord.File(img, filename="profile.png"))
            return
        except discord.HTTPException:
            pass
    await ctx.send(await dt.get_profile(ctx.guild, str(target.id)))


@bot.command(name="топ")
async def top_cmd(ctx, limit: int = 10):
    await ctx.send(await dt.get_leaderboard(ctx.guild, limit))


@bot.command(name="баланс")
async def balance_cmd(ctx):
    credits = db.get_credits(ctx.guild.id, ctx.author.id)
    await ctx.send(f"💰 У тебя **{credits}** кредитов.")


@bot.command(name="магазин")
async def shop_cmd(ctx):
    await ctx.send(await dt.show_shop(ctx.guild))


@bot.command(name="купить")
async def buy_cmd(ctx, *, role_name):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        await ctx.send(f"❌ Роль `{role_name}` не найдена.")
        return
    items = db.list_shop_items(ctx.guild.id)
    item = next((i for i in items if i["role_name"] == role.name), None)
    if not item:
        await ctx.send(f"❌ Роль `{role.name}` не продаётся. Смотри `!магазин`.")
        return
    if item["price"] > db.get_credits(ctx.guild.id, ctx.author.id):
        await ctx.send(f"❌ Не хватает кредитов: нужно **{item['price']}**, у тебя **{db.get_credits(ctx.guild.id, ctx.author.id)}**.")
        return
    try:
        await ctx.author.add_roles(role, reason="Покупка в магазине")
    except discord.Forbidden:
        await ctx.send("❌ Бот не может выдать эту роль (она выше его роли).")
        return
    db.add_credits(ctx.guild.id, ctx.author.id, -item["price"])
    await dt.unlock_achievement(ctx.guild, ctx.author.id, "shop_buy", channel=ctx.channel)
    await ctx.send(f"✅ Роль **{role.name}** твоя! Списано {item['price']} 💰.")


@bot.command(name="перевести")
async def transfer_cmd(ctx, member, amount: int):
    target = dt.find_member(ctx.guild, member)
    if not target:
        await ctx.send("❌ Участник не найден. Формат: `!перевести @юзер 100`")
        return
    if amount <= 0:
        await ctx.send("❌ Сумма должна быть положительной.")
        return
    if db.transfer_credits(ctx.guild.id, ctx.author.id, target.id, amount):
        await dt.unlock_achievement(ctx.guild, ctx.author.id, "first_transfer", channel=ctx.channel)
        await ctx.send(f"✅ Переведено **{amount}** 💰 участнику **{target.display_name}**.")
    else:
        await ctx.send("❌ Недостаточно кредитов.")


@bot.command(name="напомни")
async def remind_cmd(ctx, when, *, text):
    ts = dt.parse_when(when)
    if not ts:
        await ctx.send("❌ Не понял время. Примеры: `завтра в 20:00`, `через 2 часа`, `15.03 18:00`.")
        return
    db.add_reminder(ctx.guild.id, ctx.author.id, ctx.channel.id, ts, text)
    import datetime as _dt
    await ctx.send(f"⏰ Напомню **{_dt.datetime.fromtimestamp(ts).strftime('%d.%m %H:%M')}**: {text}")


@bot.command(name="варн")
async def warn_cmd(ctx, member, *, reason="Нарушение правил"):
    if ctx.author.id not in OWNER_IDS:
        return
    target = dt.find_member(ctx.guild, member)
    if not target:
        await ctx.send("❌ Участник не найден.")
        return
    count = db.add_warn(ctx.guild.id, target.id)
    await dt.unlock_achievement(ctx.guild, target.id, "warner", channel=None)
    try:
        if count >= 3:
            await target.timeout(datetime.timedelta(minutes=30), reason=f"3 варна: {reason}")
            await ctx.send(f"🔇 У **{target.display_name}** уже {count} варна — мут 30 мин. Причина: {reason}")
        else:
            await ctx.send(f"⚠️ Варн ({count}/3) для **{target.display_name}**. Причина: {reason}")
    except discord.Forbidden:
        await ctx.send(f"⚠️ Варн ({count}/3) для **{target.display_name}** (без мута — нет прав).")


@bot.command(name="варны")
async def warns_cmd(ctx, member=None):
    target = dt.find_member(ctx.guild, member) if member else ctx.author
    if not target:
        await ctx.send("❌ Участник не найден.")
        return
    await ctx.send(f"⚠️ У **{target.display_name}** варнов: **{db.get_warns(ctx.guild.id, target.id)}/3**")


@bot.command(name="чистка")
async def purge_cmd(ctx, amount: int = 20):
    if ctx.author.id not in OWNER_IDS:
        return
    deleted = await ctx.channel.purge(limit=min(amount, 500))
    await ctx.send(f"🧹 Удалено сообщений: {len(deleted)}", delete_after=5)


@bot.command(name="др")
async def bday_cmd(ctx, date=None):
    member = ctx.author
    if date:
        try:
            parts = date.strip().split(".")
            if len(parts) < 2:
                raise ValueError
            day, month = int(parts[0]), int(parts[1])
            year = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
            if not (1 <= day <= 31 and 1 <= month <= 12):
                raise ValueError
            db.register_birthday_db(ctx.guild.id, member.id, member.display_name, month, day, year)
            await dt.unlock_achievement(ctx.guild, member.id, "bday_set", channel=None)
            await ctx.send(f"🎂 Записано: {day:02d}.{month:02d}" + (f".{year}" if year else ""))
        except ValueError:
            await ctx.send("❌ Формат: `!др 15.03` или `!др 15.03.2000`")
        return
    row = db.get_birthday(ctx.guild.id, member.id)
    if row:
        await ctx.send(f"🎂 Твой ДР: {row['day']:02d}.{row['month']:02d}" + (f".{row['year']}" if row.get("year") else ""))
    else:
        await ctx.send("🎂 `!др 15.03` чтобы записать свой день рождения.")


@bot.command(name="погода")
async def weather_cmd(ctx, *, city):
    import services
    await ctx.send(await services.weather(city))


@bot.command(name="курс")
async def currency_cmd(ctx, base: str = "RUB"):
    import services
    await ctx.send(await services.currency(base))


# ── Музыка ─────────────────────────────────────────────────────────────────

def make_player_view(player=None) -> discord.ui.View:
    view = discord.ui.View()
    play_emoji = "⏸" if (player and player.is_paused) else "▶️"
    row0 = [
        ("⏮️", "lumi:player:prev", discord.ButtonStyle.primary),
        (play_emoji, "lumi:player:pause", discord.ButtonStyle.success),
        ("⏭️", "lumi:player:skip", discord.ButtonStyle.primary),
        ("🔁", "lumi:player:repeat", discord.ButtonStyle.success),
        ("⏹️", "lumi:player:stop", discord.ButtonStyle.danger),
    ]
    row1 = [
        ("🔉", "lumi:player:voldown", discord.ButtonStyle.secondary),
        ("🔊", "lumi:player:volup", discord.ButtonStyle.secondary),
        ("👋", "lumi:player:leave", discord.ButtonStyle.secondary),
    ]
    for i, (emoji, cid, style) in enumerate(row0):
        view.add_item(discord.ui.Button(emoji=emoji, custom_id=cid, style=style, row=0))
    for i, (emoji, cid, style) in enumerate(row1):
        view.add_item(discord.ui.Button(emoji=emoji, custom_id=cid, style=style, row=1))
    return view


@bot.command(name="плей", aliases=["play", "музыка"])
async def play_cmd(ctx, *, query: str = None):
    if not query or not query.strip():
        await ctx.send("❌ Укажи трек или ссылку. Примеры:\n`!плей тело похудело`\n`!плей https://soundcloud.com/...`\n`!плей sc lo-fi` — поиск по SoundCloud")
        return
    voice = ctx.author.voice
    if not voice or not voice.channel:
        await ctx.send("❌ Зайди сначала в голосовой канал.")
        return
    player = music.get_player(ctx.guild.id, bot)
    try:
        await player.join(voice.channel)
    except discord.Forbidden:
        await ctx.send("❌ У бота нет прав заходить в голосовой канал (нужны права Connect и Speak).")
        return
    except discord.ClientException as e:
        await ctx.send(f"❌ Не удалось подключиться: {e}")
        return
    track = await asyncio.to_thread(music.search_track, query.strip())
    if not track:
        await ctx.send("🔍 Не удалось найти трек. Попробуй иначе: `!плей исполнитель - название`")
        return
    result = await player.add_track(track, priority=db.is_premium(ctx.guild.id, ctx.author.id))
    embed = discord.Embed(title=result, description=f"🎵 **{track['title']}**\n⏱ {music.format_duration(track['duration'])}", color=0x17181A)
    msg = await ctx.send(embed=embed, view=make_player_view(player))
    player.control_message = msg


@bot.command(name="скип", aliases=["skip", "sk"])
async def skip_cmd(ctx):
    player = music.get_player(ctx.guild.id, bot)
    await ctx.send(await player.skip())


@bot.command(name="стоп")
async def stop_cmd(ctx):
    player = music.get_player(ctx.guild.id, bot)
    await ctx.send(await player.stop())


@bot.command(name="очередь", aliases=["queue", "q"])
async def queue_cmd(ctx):
    player = music.get_player(ctx.guild.id, bot)
    q = player.queue_list()
    if not q and not player.current:
        await ctx.send("🎵 Очередь пуста.")
        return
    lines = []
    if player.current:
        lines.append(f"▶️ **Сейчас:** {player.current['title']} ({music.format_duration(player.current['duration'])})")
    for i, t in enumerate(q[:15], 1):
        lines.append(f"{i}. {t['title']} ({music.format_duration(t['duration'])})")
    if len(q) > 15:
        lines.append(f"...и ещё {len(q) - 15} треков")
    await ctx.send(f"**Очередь ({len(q)})**\n" + "\n".join(lines))


@bot.command(name="громкость", aliases=["volume", "vol"])
async def volume_cmd(ctx, percent: int = 50):
    if not 1 <= percent <= 100:
        await ctx.send("❌ Громкость от 1 до 100.")
        return
    player = music.get_player(ctx.guild.id, bot)
    await ctx.send(player.set_volume(percent))


@bot.command(name="повтор", aliases=["repeat"])
async def repeat_cmd(ctx):
    player = music.get_player(ctx.guild.id, bot)
    player.repeat = not player.repeat
    await ctx.send(f"🔁 Повтор очереди: **{'включён' if player.repeat else 'выключен'}**.")


@bot.command(name="выход", aliases=["leave"])
async def leave_cmd(ctx):
    player = music.get_player(ctx.guild.id, bot)
    await ctx.send(await player.leave())


@bot.command(name="пауза", aliases=["pause", "продолжить", "resume"])
async def pause_cmd(ctx):
    player = music.get_player(ctx.guild.id, bot)
    await ctx.send(player.toggle_pause())


@bot.command(name="назад", aliases=["prev", "предыдущий"])
async def prev_cmd(ctx):
    player = music.get_player(ctx.guild.id, bot)
    await ctx.send(await player.prev())


# ── Дневной бонус ──────────────────────────────────────────────────────────

@bot.command(name="день", aliases=["daily", "бонус"])
async def daily_cmd(ctx):
    from datetime import datetime, timedelta
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    res = db.claim_daily(ctx.author.id, today, yesterday)
    if not res["first"]:
        st = db.get_daily_streak(ctx.author.id)
        embed = discord.Embed(
            title="🎁 Бонус уже получен",
            description=f"Приходи завтра! Текущая серия: **{st['streak']}** дней.",
            color=discord.Color.orange(),
        )
        await ctx.send(embed=embed)
        return
    if db.is_premium(ctx.guild.id, ctx.author.id):
        res["reward"] *= 2
    db.add_credits(ctx.guild.id, ctx.author.id, res["reward"])
    embed = discord.Embed(
        title="🎁 Дневной бонус!",
        description=(
            f"+**{res['reward']}** кредитов\n"
            f"🔥 Серия: **{res['streak']}** дней подряд (рекорд: {res['best']})\n"
            f"💳 Баланс: **{db.get_credits(ctx.guild.id, ctx.author.id)}**"
        ),
        color=discord.Color.gold(),
    )
    await ctx.send(embed=embed)
    if res["streak"] >= 7:
        await dt.unlock_achievement(ctx.guild, ctx.author.id, "daily_7", channel=ctx.channel)


# ── Казино и мини-игры ──────────────────────────────────────────────────────

def casino_view() -> discord.ui.View:
    view = discord.ui.View()
    view.add_item(discord.ui.Button(emoji="🪙", label="Орёл/Решка", custom_id="lumi:casino:coin", style=discord.ButtonStyle.primary, row=0))
    view.add_item(discord.ui.Button(emoji="🎲", label="Кубик", custom_id="lumi:casino:dice", style=discord.ButtonStyle.success, row=0))
    view.add_item(discord.ui.Button(emoji="🎰", label="Рулетка", custom_id="lumi:casino:roulette", style=discord.ButtonStyle.danger, row=0))
    return view


CASINO_RULES = {
    "coin": ("🪙 Орёл/Решка", "Ставка от 5 кредитов. Шанс 50/50: орёл — удваиваешь, решка — теряешь.\n\nКоманда: `!коин <ставка>`"),
    "dice": ("🎲 Кубик", "Бросаются два кубика (2–12). Сумма **7** — джекпот: выигрыш ×5 (+4 ставки). Любая другая — проигрыш.\n\nКоманда: `!кубик <ставка>`"),
    "roulette": ("🎰 Рулетка", "Выбираешь число от 1 до 36. Сумма — точное попадание: выигрыш ×36 (+35 ставок).\n\nКоманда: `!рулетка <ставка> <число>`"),
}


@bot.command(name="казино", aliases=["casino"])
async def casino_cmd(ctx):
    embed = discord.Embed(
        title="🎰 Казино Луми",
        description="Выбери игру кнопками ниже — покажу правила.",
        color=0x17181A,
    )
    embed.add_field(name="🪙 Орёл/Решка", value="Шанс 50/50, выигрыш ×2", inline=False)
    embed.add_field(name="🎲 Кубик", value="Два кубика, сумма 7 → джекпот ×5", inline=False)
    embed.add_field(name="🎰 Рулетка", value="Угадай число 1–36 → выигрыш ×36", inline=False)
    embed.set_footer(text="Ставка минимум 5 кредитов. Удачи!")
    await ctx.send(embed=embed, view=casino_view())

def _bet_check(ctx, amount: str) -> int | None:
    try:
        bet = int(amount)
    except (TypeError, ValueError):
        return None
    if bet < 5:
        return None
    balance = db.get_credits(ctx.guild.id, ctx.author.id)
    if balance < bet:
        return None
    return bet


@bot.command(name="коин", aliases=["coin", "орел", "орёл"])
async def coin_cmd(ctx, amount: int = 10):
    bet = _bet_check(ctx, amount)
    if bet is None:
        await ctx.send("❌ Минимальная ставка 5, и у тебя должно хватать кредитов.")
        return
    import random
    win = random.random() < 0.5
    if win:
        db.add_credits(ctx.guild.id, ctx.author.id, bet)
        await ctx.send(f"🪙 **Орёл!** Ты выиграл **+{bet}**! Баланс: {db.get_credits(ctx.guild.id, ctx.author.id)}")
    else:
        db.add_credits(ctx.guild.id, ctx.author.id, -bet)
        await ctx.send(f"🪙 **Решка.** Проигрыш **-{bet}**. Баланс: {db.get_credits(ctx.guild.id, ctx.author.id)}")


@bot.command(name="кубик", aliases=["dice", "кость"])
async def dice_cmd(ctx, amount: int = 10):
    bet = _bet_check(ctx, amount)
    if bet is None:
        await ctx.send("❌ Минимальная ставка 5, и у тебя должно хватать кредитов.")
        return
    import random
    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    total = d1 + d2
    if total == 7:
        db.add_credits(ctx.guild.id, ctx.author.id, bet * 4)
        await ctx.send(f"🎲 **{d1} + {d2} = 7!** Джекпот! +**{bet * 4}**! Баланс: {db.get_credits(ctx.guild.id, ctx.author.id)}")
    else:
        db.add_credits(ctx.guild.id, ctx.author.id, -bet)
        await ctx.send(f"🎲 **{d1} + {d2} = {total}** — не 7. Проигрыш **-{bet}**. Баланс: {db.get_credits(ctx.guild.id, ctx.author.id)}")


@bot.command(name="рулетка", aliases=["roulette", "wheel"])
async def roulette_cmd(ctx, amount: int = 10, number: int = None):
    bet = _bet_check(ctx, amount)
    if bet is None:
        await ctx.send("❌ Минимальная ставка 5, и у тебя должно хватать кредитов.")
        return
    if number is None or not 1 <= number <= 36:
        await ctx.send("🎰 Укажи число от 1 до 36: `!рулетка 100 7`")
        return
    import random
    win_num = random.randint(1, 36)
    if win_num == number:
        db.add_credits(ctx.guild.id, ctx.author.id, bet * 35)
        await ctx.send(f"🎰 **{win_num}!** Точное попадание! +**{bet * 35}**! Баланс: {db.get_credits(ctx.guild.id, ctx.author.id)}")
    else:
        db.add_credits(ctx.guild.id, ctx.author.id, -bet)
        await ctx.send(f"🎰 Выпало **{win_num}** — не {number}. Проигрыш **-{bet}**. Баланс: {db.get_credits(ctx.guild.id, ctx.author.id)}")


@bot.command(name="топ_голос", aliases=["topvoice", "топголос"])
async def top_voice_cmd(ctx, limit: int = 10):
    rows = db.top_voice_minutes(ctx.guild.id, min(max(limit, 1), 25))
    if not rows:
        await ctx.send("🎧 Пока никто не сидел в голосовых.")
        return
    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        member = ctx.guild.get_member(r["member_id"])
        name = member.display_name if member else f"id {r['member_id']}"
        medal = medals[i] if i < 3 else f"`{i + 1}.`"
        minutes = r["minutes"]
        if minutes >= 600:
            t = f"{minutes // 60} ч {minutes % 60} мин"
        else:
            t = f"{minutes} мин"
        lines.append(f"{medal} **{name}** — {t}")
    await ctx.send("🎧 **Доска почёта голосовых**\n" + "\n".join(lines))


# ── Дуэли ────────────────────────────────────────────────────────────────────

def make_duel_view() -> discord.ui.View:
    view = discord.ui.View()
    view.add_item(discord.ui.Button(emoji="✅", label="Принять", custom_id="lumi:duel:accept", style=discord.ButtonStyle.success, row=0))
    view.add_item(discord.ui.Button(emoji="❌", label="Отклонить", custom_id="lumi:duel:decline", style=discord.ButtonStyle.danger, row=0))
    return view


@bot.command(name="дуэль", aliases=["duel", "поединок"])
async def duel_cmd(ctx, member: discord.Member = None, amount: int = 20):
    import time as _t
    if not member or member.bot:
        await ctx.send("❌ Укажи участника: `!дуэль @юзер 50`")
        return
    if member.id == ctx.author.id:
        await ctx.send("❌ С самим собой нельзя.")
        return
    if amount < 5:
        await ctx.send("❌ Минимальная ставка 5 кредитов.")
        return
    if db.get_credits(ctx.guild.id, ctx.author.id) < amount:
        await ctx.send("❌ У тебя не хватает кредитов.")
        return
    if member.id in dt.DUEL_REQUESTS:
        await ctx.send(f"❌ Для **{member.display_name}** уже есть запрос на дуэль.")
        return
    state = {
        "author_id": ctx.author.id,
        "author_name": ctx.author.display_name,
        "target_id": member.id,
        "target_name": member.display_name,
        "bet": amount,
        "guild_id": ctx.guild.id,
        "created": int(_t.time()),
    }
    dt.DUEL_REQUESTS[member.id] = state
    embed = discord.Embed(
        title="⚔️ Дуэль!",
        description=f"**{ctx.author.display_name}** вызывает **{member.display_name}** на дуэль!\nСтавка: **{amount}** кредитов.",
        color=0x17181A,
    )
    embed.set_footer(text=f"{member.display_name}, подтверди кнопкой. Действительно 90 секунд.")
    await ctx.send(embed=embed, view=make_duel_view())


# ── Блекджек ─────────────────────────────────────────────────────────────────

def make_bj_view() -> discord.ui.View:
    view = discord.ui.View()
    view.add_item(discord.ui.Button(emoji="🎴", label="Ещё", custom_id="lumi:bj:hit", style=discord.ButtonStyle.success, row=0))
    view.add_item(discord.ui.Button(emoji="⏹", label="Стоп", custom_id="lumi:bj:stand", style=discord.ButtonStyle.danger, row=0))
    return view


def bj_embed(state: dict) -> discord.Embed:
    total = dt._bj_sum(state["player"])
    embed = discord.Embed(title="🃏 Блекджек", color=0x17181A)
    if state.get("done"):
        embed.add_field(name="🔚 Итог", value=state.get("result", ""), inline=False)
    embed.add_field(
        name=f"Ваши карты ({total})",
        value=dt._bj_cards(state["player"]),
        inline=True,
    )
    embed.add_field(
        name="Дилер",
        value=dt._bj_cards(state["dealer"]),
        inline=True,
    )
    embed.set_footer(text=f"Ставка: {state['bet']} кредитов")
    return embed


@bot.command(name="бдж", aliases=["блекджек", "blackjack", "bj"])
async def bj_cmd(ctx, amount: int = 10):
    bet = _bet_check(ctx, amount)
    if bet is None:
        await ctx.send("❌ Минимальная ставка 5, и у тебя должно хватать кредитов.")
        return
    if ctx.author.id in dt.BJ_SESSIONS and not dt.BJ_SESSIONS[ctx.author.id].get("done"):
        await ctx.send("❌ У тебя уже идёт партия!")
        return
    db.add_credits(ctx.guild.id, ctx.author.id, -bet)
    state = dt.bj_new(ctx.author.id, bet, ctx.guild.id)
    await ctx.send(embed=bj_embed(state), view=make_bj_view())


@bot.command(name="кредиты", aliases=["выдать", "дайкредиты", "addcredits"])
async def credits_cmd(ctx, member: discord.Member, amount: int = 0):
    is_owner = ctx.author.id == ctx.guild.owner_id
    is_admin = bool(ctx.author.guild_permissions.administrator)
    if not (is_owner or is_admin):
        await ctx.send("❌ Только владелец сервера или администратор может выдавать кредиты.")
        return
    if not member or member.bot:
        await ctx.send("❌ Укажи участника: `!кредиты @юзер 500`")
        return
    if amount == 0:
        await ctx.send("❌ Укажи сумму: `!кредиты @юзер 500`")
        return
    bal = db.get_credits(ctx.guild.id, member.id)
    if amount < 0 and bal + amount < 0:
        await ctx.send("❌ Баланс не может стать отрицательным.")
        return
    db.add_credits(ctx.guild.id, member.id, amount)
    sign = "+" if amount > 0 else ""
    await ctx.send(f"💳 {member.display_name}: **{bal}** → **{bal + amount}** ({sign}{amount} кредитов)")
    db.log_action(ctx.guild.id, ctx.author.id, "credits_grant", {"member": member.id, "amount": amount}, f"баланс {bal} -> {bal+amount}", True)


# ── Премиум и лицензии ───────────────────────────────────────────────────────

@bot.command(name="генкод", aliases=["gencode", "лицензия"])
async def gen_code_cmd(ctx, days: int = 30):
    if not _is_owner_or_admin(ctx):
        await ctx.send("❌ Создавать коды может только владелец сервера или администратор.")
        return
    if not 1 <= days <= 3650:
        await ctx.send("❌ Срок от 1 до 3650 дней.")
        return
    code = db.create_license(ctx.guild.id, days, ctx.author.id)
    embed = discord.Embed(
        title="👑 Код премиума создан",
        description=f"Код: **`{code}`**\nСрок: **{days} дн.**",
        color=discord.Color.gold(),
    )
    try:
        await ctx.author.send(embed=embed)
        await ctx.send(f"✅ Код создан и отправлен тебе в ЛС (срок {days} дн.).")
    except discord.Forbidden:
        await ctx.send(embed=embed)
        await ctx.send("⚠️ Не смог написать в ЛС — код в чате. Удали его потом через использование.")


@bot.command(name="активировать", aliases=["activate", "код"])
async def activate_cmd(ctx, code: str = None):
    import time as _t
    if not code:
        await ctx.send("❌ Формат: `!активировать LU-XXXX-XXXX`")
        return
    lic = db.get_license(code)
    if not lic:
        await ctx.send("❌ Код не найден или уже использован.")
        return
    if lic["guild_id"] != ctx.guild.id:
        await ctx.send("❌ Этот код создан для другого сервера.")
        return
    days = int(lic["days"])
    until = int(_t.time()) + days * 86400
    db.add_premium(ctx.guild.id, ctx.author.id, until)
    db.delete_license(lic["code"])
    from datetime import datetime
    date = datetime.fromtimestamp(until).strftime("%d.%m.%Y")
    embed = discord.Embed(
        title="👑 Премиум активирован!",
        description=f"Твой премиум активен до **{date}**.\n2× XP, 2× бонус `!день`, 👑 в профиле, приоритет в музыке.",
        color=discord.Color.gold(),
    )
    await ctx.send(embed=embed)


# ── Рамки профиля ────────────────────────────────────────────────────────────

FRAMES = {
    "default": (0, None, "Стандартная — без рамки"),
    "gold": (500, (255, 215, 0), "Золотая"),
    "sunset": (800, (255, 120, 50), "Закат"),
    "neon": (1200, (0, 229, 255), "Неон"),
    "legendary": (3000, (255, 45, 85), "Легендарная"),
}


@bot.command(name="рамки", aliases=["frames"])
async def frames_cmd(ctx):
    owned = set(db.list_owned_frames(ctx.guild.id, ctx.author.id))
    active = db.get_active_frame(ctx.guild.id, ctx.author.id)
    lines = ["**Рамки профиля**", "Купи: `!купить_рамку <название>` · Включить: `!рамка <название>`"]
    for name, (price, _, label) in FRAMES.items():
        if name == "default":
            continue
        status = "✅ куплена" if name in owned else f"💳 {price} ₭"
        act = " · **АКТИВНА**" if name == active else ""
        lines.append(f"{label} `{name}` — {status}{act}")
    await ctx.send("\n".join(lines))


@bot.command(name="купить_рамку", aliases=["buyframe"])
async def buy_frame_cmd(ctx, name: str = None):
    if not name or name not in FRAMES or name == "default":
        await ctx.send("❌ `!купить_рамку gold` — варианты: gold, sunset, neon, legendary")
        return
    price, _, label = FRAMES[name]
    if db.owns_frame(ctx.guild.id, ctx.author.id, name):
        await ctx.send(f"❌ Рамка **{label}** уже куплена.")
        return
    if db.get_credits(ctx.guild.id, ctx.author.id) < price:
        await ctx.send(f"❌ Не хватает кредитов: нужно {price} ₭.")
        return
    db.add_credits(ctx.guild.id, ctx.author.id, -price)
    db.buy_frame(ctx.guild.id, ctx.author.id, name)
    db.set_active_frame(ctx.guild.id, ctx.author.id, name)
    await ctx.send(f"✅ Куплена и включена рамка **{label}** (-{price} ₭)! Смотри: `!профиль`")


@bot.command(name="рамка", aliases=["frame"])
async def frame_cmd(ctx, name: str = None):
    if not name or name not in FRAMES or name == "default":
        await ctx.send("❌ `!рамка neon` — варианты: gold, sunset, neon, legendary")
        return
    if name == "default" or db.owns_frame(ctx.guild.id, ctx.author.id, name):
        db.set_active_frame(ctx.guild.id, ctx.author.id, name)
        label = "Стандартная (без рамки)" if name == "default" else FRAMES[name][2]
        await ctx.send(f"🖼 Включена рамка **{label}**!")
    else:
        await ctx.send("❌ Сначала купи: `!купить_рамку " + name + "`")


# ── !шанс ────────────────────────────────────────────────────────────────────

@bot.command(name="шанс", aliases=["chance", "вероятность"])
async def chance_cmd(ctx, *, question: str = None):
    import random
    if not question:
        await ctx.send("❌ Спроси что-нибудь: `!шанс что я выиграю в рулетку`")
        return
    pct = random.randint(0, 100)
    if pct >= 90:
        verdict = "Почти наверняка!"
    elif pct >= 70:
        verdict = "Скорее да."
    elif pct >= 40:
        verdict = "50 на 50."
    elif pct >= 10:
        verdict = "Скорее нет."
    else:
        verdict = "Даже не надейся."
    seg = 12
    filled = round(pct / 100 * seg)
    bar = "▓" * filled + "░" * (seg - filled)
    embed = discord.Embed(
        title=f"🎲 {question[:120]}",
        description=f"**Шанс: {pct}%**\n{bar}\n\n{verdict}",
        color=0x17181A,
    )
    await ctx.send(embed=embed)


# ── Карточка сервера, QR, кастомные команды ─────────────────────────────────

def _is_owner_or_admin(ctx) -> bool:
    return ctx.author.id == ctx.guild.owner_id or bool(ctx.author.guild_permissions.administrator)


@bot.command(name="статсервера", aliases=["serverstat", "статистика"])
async def server_stats_cmd(ctx):
    card = await dt.render_server_card(ctx.guild)
    if card:
        await ctx.send(file=discord.File(card, "server.png"))
        return
    online = sum(1 for m in ctx.guild.members if m.status != discord.Status.offline and not m.bot)
    await ctx.send(
        f"**{ctx.guild.name}**\n"
        f"👥 Участников: {len(ctx.guild.members)} (онлайн: {online})\n"
        f"💬 Каналов: {len(ctx.guild.text_channels)} текстовых · {len(ctx.guild.voice_channels)} голосовых\n"
        f"✨ Бустов: {ctx.guild.premium_subscription_count or 0}"
    )


@bot.command(name="qr")
async def qr_cmd(ctx, *, text: str = None):
    if not _is_owner_or_admin(ctx):
        await ctx.send("❌ Создавать QR-коды может только владелец сервера или администратор.")
        return
    if not text:
        await ctx.send("❌ Укажи текст: `!qr https://example.com`")
        return
    try:
        import qrcode, io
        img = qrcode.make(text.strip()[:400])
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        await ctx.send(file=discord.File(buf, "qr.png"))
    except Exception as e:
        await ctx.send(f"❌ Не удалось создать QR: {e}")


@bot.command(name="создать_команду", aliases=["createcmd", "нкоманда"])
async def create_custom_cmd(ctx, name: str = None, *, response: str = None):
    if not _is_owner_or_admin(ctx):
        await ctx.send("❌ Создавать команды может только владелец сервера или администратор.")
        return
    if not name or not response:
        await ctx.send("❌ Формат: `!создать_команду !правила /текст ответа/`")
        return
    name = name.lstrip("!").lower().strip()
    if not name or not name.replace("_", "").replace("-", "").isalnum():
        await ctx.send("❌ Имя команды — только буквы/цифры/`_`/`-`.")
        return
    if name in bot.all_commands or name in ("плей", "play", "музыка"):
        await ctx.send(f"❌ Команда `!{name}` уже существует у бота.")
        return
    if db.add_custom_command(ctx.guild.id, name, response, ctx.author.id):
        await ctx.send(f"✅ Команда `!{name}` создана!")
    else:
        await ctx.send(f"❌ Команда `!{name}` уже есть. Удали сначала: `!удалить_команду {name}`")


@bot.command(name="удалить_команду", aliases=["delcmd"])
async def delete_custom_cmd(ctx, name: str = None):
    if not _is_owner_or_admin(ctx):
        await ctx.send("❌ Удалять команды может только владелец сервера или администратор.")
        return
    if not name:
        await ctx.send("❌ Формат: `!удалить_команду <имя>`")
        return
    name = name.lstrip("!").lower().strip()
    if db.remove_custom_command(ctx.guild.id, name):
        await ctx.send(f"🗑 Команда `!{name}` удалена.")
    else:
        await ctx.send(f"❌ Команды `!{name}` нет.")


@bot.command(name="своикоманды", aliases=["customs", "свои_команды"])
async def list_customs_cmd(ctx):
    rows = db.list_custom_commands(ctx.guild.id)
    if not rows:
        await ctx.send("📜 Кастомных команд нет. Создай: `!создать_команду !правила /текст/`")
        return
    lines = [f"**Кастомные команды ({len(rows)})**"]
    lines += [f"`!{r['name']}` — {r['response'][:60]}{'…' if len(r['response']) > 60 else ''}" for r in rows]
    await ctx.send("\n".join(lines))


# ── Питомец-тамагочи ─────────────────────────────────────────────────────────

PET_KINDS = ["🐱", "🐶", "🐹", "🐰", "🦊", "🐼", "🐥", "🐸"]


def pet_state(pet: dict) -> dict:
    import time as _t
    now = int(_t.time())
    hours = max(0, (now - (pet.get("last_feed") or 0)) / 3600)
    hunger = max(0, min(100, (pet.get("hunger") or 0) - hours * 3))
    happiness = pet.get("happiness") or 0
    if hunger < 30:
        happiness = max(0, happiness - 15)
    level = int(((pet.get("xp") or 0) / 50) ** 0.5)
    return {"hunger": hunger, "happiness": happiness, "level": level}


def pet_bar(value: float) -> str:
    seg = 10
    filled = max(0, min(seg, round(value / 100 * seg)))
    return "▓" * filled + "░" * (seg - filled)


@bot.command(name="питомец", aliases=["pet", "питомцы"])
async def pet_cmd(ctx, *, name: str = None):
    import random
    pet = db.get_pet(ctx.author.id)
    if not pet:
        if not name:
            await ctx.send("❌ У тебя нет питомца. Заведи: `!питомец Барсик` (100 кредитов)")
            return
        if db.get_credits(ctx.guild.id, ctx.author.id) < 100:
            await ctx.send("❌ Заведение питомца стоит 100 кредитов.")
            return
        db.add_credits(ctx.guild.id, ctx.author.id, -100)
        pet = db.create_pet(ctx.author.id, name.strip()[:24], random.choice(PET_KINDS))
        await ctx.send(f"🐾 Поздравляю! Твой питомец — **{pet['name']}** {pet['kind']}!\nКорми его: `!покормить`")
        return
    st = pet_state(pet)
    next_xp = 50 * (st["level"] + 1) ** 2
    embed = discord.Embed(
        title=f"{pet['kind']} {pet['name']} — уровень {st['level']}",
        description=(
            f"😋 Сытость: {pet_bar(st['hunger'])} `{int(st['hunger'])}%`\n"
            f"💛 Настроение: {pet_bar(st['happiness'])} `{int(st['happiness'])}%`\n"
            f"✨ XP: {pet.get('xp')} / {next_xp}"
        ),
        color=0x17181A,
    )
    embed.set_footer(text="!покормить (25 ₭) · !погладить (бесплатно)")
    await ctx.send(embed=embed)


@bot.command(name="покормить", aliases=["корм", "feed"])
async def feed_pet_cmd(ctx):
    pet = db.get_pet(ctx.author.id)
    if not pet:
        await ctx.send("❌ У тебя нет питомца: `!питомец Барсик`")
        return
    if db.get_credits(ctx.guild.id, ctx.author.id) < 25:
        await ctx.send("❌ Корм стоит 25 кредитов.")
        return
    import time as _t
    now = int(_t.time())
    last_feed = pet.get("last_feed") or 0
    if now - last_feed < 1800:
        await ctx.send(f"🍖 {pet['name']} ещё сыт (можно кормить раз в 30 минут).")
        return
    db.add_credits(ctx.guild.id, ctx.author.id, -25)
    pet = db.feed_pet(ctx.author.id, 7)
    st = pet_state(pet)
    await ctx.send(f"🍖 **{pet['name']}** поел! +7 XP · сытость {int(st['hunger'])}%")
    if st["level"] >= 10:
        await dt.unlock_achievement(ctx.guild, ctx.author.id, "pet_10", channel=ctx.channel)


@bot.command(name="погладить", aliases=["гладить", "pat"])
async def pat_pet_cmd(ctx):
    pet = db.get_pet(ctx.author.id)
    if not pet:
        await ctx.send("❌ У тебя нет питомца: `!питомец Барсик`")
        return
    pet = db.pat_pet(ctx.author.id, 2)
    st = pet_state(pet)
    await ctx.send(f"🤗 Ты погладил **{pet['name']}**! +2 XP · настроение {int(st['happiness'])}%")
    if st["level"] >= 10:
        await dt.unlock_achievement(ctx.guild, ctx.author.id, "pet_10", channel=ctx.channel)


# ── Избранные треки ────────────────────────────────────────────────────────

def _favorite_to_track(fav: dict) -> dict:
    return {
        "title": fav["title"],
        "url": fav["url"],
        "id": f"fav{fav['id']}",
        "duration": fav.get("duration") or 0,
        "thumbnail": fav.get("thumb"),
        "webpage_url": fav.get("webpage_url") or "",
        "uploader": "Избранное",
        "headers": {},
    }


async def _require_voice(ctx):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ Зайди сначала в голосовой канал.")
        return None
    player = music.get_player(ctx.guild.id, bot)
    try:
        await player.join(ctx.author.voice.channel)
    except discord.Forbidden:
        await ctx.send("❌ У бота нет прав заходить в голосовой канал (нужны права Connect и Speak).")
        return None
    except discord.ClientException as e:
        await ctx.send(f"❌ Не удалось подключиться: {e}")
        return None
    return player


@bot.command(name="люб", aliases=["любимое", "избранное"])
async def fav_cmd(ctx, *, arg: str = None):
    if not arg:
        favs = db.list_favorites(ctx.author.id)
        if not favs:
            await ctx.send("💖 Избранное пусто. Добавь трек: `!люб тело похудело`")
            return
        lines = [f"**Избранное ({len(favs)}/20)**"]
        lines += [f"`{i}.` {f['title']} ({music.format_duration(f.get('duration') or 0)})" for i, f in enumerate(favs, 1)]
        lines += ["\n`!любимое 3` — играть №3 · `!любимое 0` — играть все · `!любимое -3` — удалить №3"]
        await ctx.send("\n".join(lines))
        return
    favs = db.list_favorites(ctx.author.id)
    arg = arg.strip()
    if arg.lstrip("-").isdigit():
        n = int(arg)
        if not favs:
            await ctx.send("💖 Избранное пусто.")
            return
        if n == 0:
            if len(favs) > 50:
                favs = favs[:50]
            player = await _require_voice(ctx)
            if not player:
                return
            for f in favs:
                await player.add_track(_favorite_to_track(f))
            msg = await ctx.send(f"🎵 В очередь: **{len(favs)}** треков из избранного", view=make_player_view())
            player.control_message = msg
            return
        if n < 0:
            if db.remove_favorite(ctx.author.id, -n - 1):
                await ctx.send(f"🗑 Удалён №{abs(n)} из избранного.")
            else:
                await ctx.send("❌ Нет такого номера.")
            return
        if 1 <= n <= len(favs):
            player = await _require_voice(ctx)
            if not player:
                return
            await player.add_track(_favorite_to_track(favs[n - 1]))
            msg = await ctx.send(f"💖 Играет: **{favs[n - 1]['title']}**", view=make_player_view())
            player.control_message = msg
            return
        await ctx.send("❌ Нет такого номера.")
        return
    track = await asyncio.to_thread(music.search_track, arg)
    if not track:
        await ctx.send(f"🔍 Не удалось найти: **{arg}**")
        return
    res = db.add_favorite(ctx.author.id, track)
    if res == "ok":
        favs = db.list_favorites(ctx.author.id)
        await ctx.send(f"💖 Добавлено в избранное ({len(favs)}/20): **{track['title']}**")
        await dt.unlock_achievement(ctx.guild, ctx.author.id, "fav_first", channel=ctx.channel)
    elif res == "exists":
        await ctx.send(f"💖 Уже в избранном: **{track['title']}**")
    elif res == "limit":
        await ctx.send("❌ Лимит 20 треков. Удали лишний: `!любимое -3`")
    else:
        await ctx.send("❌ Не удалось добавить.")


@bot.command(name="плейлист", aliases=["playlist"])
async def playlist_cmd(ctx):
    favs = db.list_favorites(ctx.author.id)
    if not favs:
        await ctx.send("💖 Избранное пусто. Добавь трек: `!люб тело похудело`")
        return
    lines = [f"**Избранное ({len(favs)}/20)**"]
    lines += [f"`{i}.` {f['title']} ({music.format_duration(f.get('duration') or 0)})" for i, f in enumerate(favs, 1)]
    await ctx.send("\n".join(lines))


# ── Ачивки и фокус ─────────────────────────────────────────────────────────

@bot.command(name="ачивки", aliases=["achievements", "награды"])
async def achievements_cmd(ctx, member=None):
    target = dt.find_member(ctx.guild, member) if member else ctx.author
    if not target:
        await ctx.send("❌ Участник не найден.")
        return
    await ctx.send(await dt.list_achievements(ctx.guild, target))


@bot.command(name="фокус", aliases=["focus", "помидор"])
async def focus_cmd(ctx, minutes: int = 25):
    if not 1 <= minutes <= 120:
        await ctx.send("❌ От 1 до 120 минут.")
        return
    active = db.get_active_focus(ctx.author.id)
    if active:
        left = active["minutes"] - int((time.time() - active["started_ts"]) / 60)
        await ctx.send(f"⏳ Сессия уже идёт (осталось ~{max(left, 1)} мин).")
        return
    db.add_focus_session(ctx.author.id, minutes, ctx.channel.id)
    await ctx.send(f"🎯 Фокус-сессия **{minutes} мин** запущена! Окончу и пришлю отчёт в ЛС.")


# ── Обработка ошибок команд ────────────────────────────────────────────────

@bot.event
async def on_command_error(ctx, error):
    try:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Не хватает аргументов. `!команды` — список, или посмотри в `!луми_помощь`.")
        elif isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.NotOwner):
            await ctx.send("❌ Эта команда только для владельца.")
        elif isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send("⏳ Команда уже выполняется, подожди.")
        else:
            print(f"[cmd error] {ctx.command}: {type(error).__name__}: {error}", flush=True)
            try:
                await ctx.send(f"❌ Ошибка команды: {type(error).__name__}. Попробуй ещё раз.")
            except Exception:
                pass
    except Exception:
        pass


# ── Фоновые задачи ────────────────────────────────────────────────────────

async def reminder_loop():
    while True:
        try:
            now = int(time.time())
            for r in db.due_reminders(now):
                guild = bot.get_guild(r["guild_id"])
                if guild:
                    channel = guild.get_channel(r["channel_id"])
                    if channel:
                        try:
                            if r["user_id"]:
                                member = guild.get_member(r["user_id"])
                                if member:
                                    await member.send(f"⏰ **Напоминание**: {r['text']}")
                            await channel.send(f"⏰ **Напоминание**: {r['text']}")
                        except (discord.Forbidden, discord.HTTPException):
                            pass
                db.mark_reminder_done(r["id"])
            for ev in db.due_event_reminders(now):
                guild = bot.get_guild(ev["guild_id"])
                if guild:
                    channel = guild.get_channel(ev["channel_id"])
                    if channel:
                        try:
                            await channel.send(f"🚀 **Скоро ивент:** {ev['name']}!")
                        except (discord.Forbidden, discord.HTTPException):
                            pass
                db.mark_event_reminded(ev["id"])
        except Exception:
            pass
        await asyncio.sleep(30)


async def birthday_loop():
    last_days = {}
    while True:
        try:
            today = datetime.datetime.utcnow()
            for guild in bot.guilds:
                key = f"{guild.id}:{today.month}:{today.day}"
                if last_days.get(key):
                    continue
                rows = db.birthdays_on_day(guild.id, today.month, today.day)
                if not rows:
                    continue
                channel_id = db.get_guild_channel(guild.id, "birthday")
                channel = guild.get_channel(channel_id) if channel_id else None
                if not channel:
                    channel = discord.utils.get(guild.text_channels, name="даты-дней-рождений")
                if not channel:
                    channel = guild.system_channel
                if channel:
                    names = []
                    for b in rows:
                        member = guild.get_member(b["member_id"])
                        names.append(member.mention if member else b["name"])
                    age = ""
                    if rows[0].get("year"):
                        age = f" ({today.year - rows[0]['year']} лет)"
                    await channel.send(f"🎂 Сегодня день рождения у {', '.join(names)}!{age} Поздравляем! 🥳")
                last_days[key] = True
        except Exception:
            pass
        await asyncio.sleep(3600)


async def focus_loop():
    phrases = ["Отличная сессия!", "Фокус — это суперсила.", "Ты проделал большую работу.", "Мозг прокачан."]
    while True:
        try:
            now = int(time.time())
            for s in db.due_focus_sessions(now):
                user = bot.get_user(s["user_id"])
                db.mark_focus_done(s["id"])
                if user:
                    count, total = db.week_focus_stats(s["user_id"])
                    embed = discord.Embed(
                        title="🎯 Фокус-сессия завершена!",
                        description=(
                            f"Длительность: **{s['minutes']} мин**\n"
                            f"За неделю: **{count}** сессий, **{total}** минут фокуса\n\n"
                            f"✨ {random.choice(phrases)}"
                        ),
                        color=discord.Color.green(),
                    )
                    try:
                        await user.send(embed=embed)
                    except (discord.Forbidden, discord.HTTPException):
                        pass
        except Exception:
            pass
        await asyncio.sleep(20)


async def music_loop():
    """Проверка бездействия + живая карточка плеера (прогресс-бар раз в 5 сек)."""
    while True:
        try:
            for gid in list(music._players.keys()):
                player = music._players[gid]
                try:
                    await player.check_idle()
                    await _refresh_player_card(player)
                except Exception:
                    pass
            music.prune_players()
        except Exception:
            pass
        await asyncio.sleep(5)


async def status_loop():
    """Обновляет статус бота: играет для N серверов."""
    while True:
        try:
            n = len(bot.guilds)
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"музыку для {n} серверов 🎵",
                )
            )
        except Exception:
            pass
        await asyncio.sleep(600)


async def lottery_loop():
    """Клановая лотерея: раз в час случайный активный участник получает 100 кредитов."""
    while True:
        try:
            await asyncio.sleep(3600)
            for guild in bot.guilds:
                if not guild.system_channel:
                    continue
                try:
                    pool = db.recent_speakers(guild.id, 24)
                    members = [uid for uid in pool if (m := guild.get_member(uid)) and not m.bot]
                    if len(members) < 2:
                        continue
                    import random
                    winner_id = random.choice(members)
                    member = guild.get_member(winner_id)
                    if not member:
                        continue
                    db.add_credits(guild.id, winner_id, 100)
                    embed = discord.Embed(
                        title="🎰 Клановая лотерея!",
                        description=f"Победитель: **{member.display_name}** {member.mention}\n+**100** кредитов!",
                        color=discord.Color.gold(),
                    )
                    await guild.system_channel.send(embed=embed)
                except Exception:
                    pass
        except Exception:
            pass


_last_digest_week: str = ""


async def weekly_digest_loop():
    """Воскресенье: еженедельный дайджест сервера в системный канал."""
    global _last_digest_week
    while True:
        try:
            from datetime import datetime
            now = datetime.now()
            week = now.isocalendar()[1]
            if now.weekday() == 6 and now.hour >= 12 and week != _last_digest_week:
                _last_digest_week = str(week)
                for guild in bot.guilds:
                    if not guild.system_channel:
                        continue
                    try:
                        top = db.top_messages_last_days(guild.id, 7, 5)
                        total_msg = db.messages_count_last_days(guild.id, 7)
                        voice_top = db.top_voice_minutes(guild.id, 3)
                        new_members = [m for m in guild.members if m.joined_at]
                        import datetime as _dt
                        week_ago = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=7)
                        new_members = [m for m in new_members if m.joined_at >= week_ago and not m.bot]
                        lines = [f"📊 За неделю написано **{total_msg}** сообщений!"]
                        if top:
                            lines.append("\n**🏆 Самые активные:**")
                            medals = ["🥇", "🥈", "🥉"]
                            for i, r in enumerate(top):
                                m = guild.get_member(r["user_id"])
                                name = m.display_name if m else f"id {r['user_id']}"
                                medal = medals[i] if i < 3 else f"`{i + 1}.`"
                                lines.append(f"{medal} **{name}** — {r['cnt']} сообщений")
                        if voice_top:
                            lines.append("\n**🎧 Голосовые:**")
                            for i, r in enumerate(voice_top[:3]):
                                m = guild.get_member(r["member_id"])
                                name = m.display_name if m else f"id {r['member_id']}"
                                lines.append(f"🔊 **{name}** — {r['minutes'] // 60} ч {r['minutes'] % 60} мин")
                        if new_members:
                            lines.append(f"\n👋 Нас стало больше на **{len(new_members)}**: "
                                         + ", ".join(m.display_name for m in new_members[:5]))
                        embed = discord.Embed(
                            title="📅 Недельный дайджест",
                            description="\n".join(lines),
                            color=discord.Color.gold(),
                        )
                        await guild.system_channel.send(embed=embed)
                    except Exception:
                        pass
        except Exception:
            pass
        await asyncio.sleep(1800)


def _progress_bar(player) -> str:
    total = int(player.current.get("duration") or 0) if player.current else 0
    elapsed = player.progress_seconds()
    seg = 16
    filled = 0
    if total > 0:
        filled = max(0, min(seg, round(elapsed / total * seg)))
    bar = "▬" * filled + "◔" + "▭" * max(0, seg - filled - 1) if filled < seg else "▬" * seg
    pos = music.format_duration(min(elapsed, total or elapsed))
    return f"{bar} {pos} / {music.format_duration(total)}"


async def _refresh_player_card(player):
    if not player.control_message:
        return
    try:
        if player.current and player.is_playing:
            track = player.current
            embed = discord.Embed(
                title="▶️ Сейчас играет",
                description=f"🎵 **{track['title']}**\n👤 {track.get('uploader') or '—'}",
                color=0x17181A,
            )
            if track.get("thumbnail"):
                embed.set_thumbnail(url=track["thumbnail"])
            embed.add_field(name="⏱ Прогресс", value=_progress_bar(player), inline=False)
        else:
            embed = discord.Embed(title="⏹ Плеер остановлен", color=0x17181A)
        q = player.queue_list()
        if q:
            up = "\n".join(f"{i}. {t['title']}" for i, t in enumerate(q[:5], 1))
            embed.add_field(name=f"Далее ({len(q)})", value=up, inline=False)
        embed.set_footer(text=f"🔊 {int(player.volume * 100)}% | 🔁 {'вкл' if player.repeat else 'выкл'}")
        await player.control_message.edit(embed=embed, view=make_player_view(player))
    except discord.NotFound:
        player.control_message = None
    except (discord.HTTPException, discord.Forbidden):
        pass


VOICE_STARTED: dict = {}
VOICE_ACC: dict = {}


async def voice_flush_loop():
    """Раз в минуту копит минуты в голосовых и проверяет голосовые ачивки."""
    while True:
        try:
            await asyncio.sleep(60)
            now = time.time()
            for key in list(VOICE_ACC.keys()):
                guild_id, user_id = key
                if now - VOICE_ACC[key] >= 60:
                    delta = int((now - VOICE_ACC[key]) / 60)
                    VOICE_ACC[key] = now
                    total = db.add_voice_minutes(guild_id, user_id, max(delta, 1))
                    guild = bot.get_guild(guild_id)
                    if not guild:
                        continue
                    if 60 <= total < 600:
                        await dt.unlock_achievement(guild, user_id, "voice_1h", channel=None)
                    elif total >= 600:
                        await dt.unlock_achievement(guild, user_id, "voice_10h", channel=None)
                        await dt.unlock_achievement(guild, user_id, "voice_1h", channel=None)
        except Exception:
            pass


# ── События ───────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    db.init_db()
    comp.init_components(bot)
    bot.loop.create_task(reminder_loop())
    bot.loop.create_task(birthday_loop())
    bot.loop.create_task(focus_loop())
    bot.loop.create_task(music_loop())
    bot.loop.create_task(lottery_loop())
    bot.loop.create_task(weekly_digest_loop())
    bot.loop.create_task(voice_flush_loop())
    bot.loop.create_task(status_loop())
    print(f"🔥 Луми запущена | серверов: {len(bot.guilds)} | инструментов: {len(tools_map)}")


@bot.event
async def on_voice_state_update(member, before, after):
    try:
        if member.bot:
            return
        key = (member.guild.id, member.id)
        if before.channel is None and after.channel is not None:
            VOICE_STARTED[key] = time.time()
            VOICE_ACC[key] = time.time()
        elif before.channel is not None and after.channel is None:
            start = VOICE_STARTED.pop(key, None)
            if start:
                db.add_voice_minutes(member.guild.id, member.id, max(int((time.time() - start) / 60), 1))
                VOICE_ACC.pop(key, None)
    except Exception:
        pass


@bot.event
async def on_member_join(member):
    cfg = db.get_welcome_config(member.guild.id)
    if not cfg or not cfg.get("enabled"):
        return
    try:
        channel = member.guild.get_channel(cfg["channel_id"]) if cfg.get("channel_id") else None
        role = member.guild.get_role(cfg["guest_role_id"]) if cfg.get("guest_role_id") else None
        rules = cfg.get("rules_text") or "Прочитай правила сервера!"
        if channel:
            embed = discord.Embed(
                title=f"👋 Добро пожаловать, {member.display_name}!",
                description=f"{member.mention}\n\n{rules}",
                color=discord.Color.green(),
            )
            card = await dt.render_welcome_card(member, rules)
            if card:
                await channel.send(embed=embed, file=discord.File(card, filename="welcome.png"))
            else:
                await channel.send(embed=embed)
        if role:
            await member.add_roles(role, reason="Приветствие новичка")
    except (discord.Forbidden, discord.HTTPException):
        pass


@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        if await comp.handle_interaction(interaction):
            return
    except Exception as e:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)


@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.author.bot:
        return

    if not message.guild:
        return

    # ── Кастомные команды сервера ──
    if message.content.startswith("!"):
        custom = message.content[1:].strip().lower()
        if custom and " " not in custom:
            row = db.get_custom_command(message.guild.id, custom)
            if row:
                try:
                    await message.channel.send(row["response"])
                except Exception:
                    pass
                return

    # ── Уровни / XP ──
    if not message.content.startswith(("!", "Луми", "Луми,", "lumi", "lumi,")):
        try:
            now = time.time()
            last = db.get_last_xp_ts(message.guild.id, message.author.id)
            if now - last > 60:
                premium = db.is_premium(message.guild.id, message.author.id)
                xp = random.randint(10, 25) * (2 if premium else 1)
                new_xp, level, level_up = db.add_member_message(message.guild.id, message.author.id, xp)
                db.add_credits(message.guild.id, message.author.id, 5 * (2 if premium else 1))
                stats = db.get_member_stats(message.guild.id, message.author.id)
                await dt.unlock_achievement(message.guild, message.author.id, "intro", channel=None)
                if stats.get("messages") >= 1000:
                    await dt.unlock_achievement(message.guild, message.author.id, "msg_1000", channel=None)
                elif stats.get("messages") >= 100:
                    await dt.unlock_achievement(message.guild, message.author.id, "msg_100", channel=None)
                for lvl, ach in ((25, "lvl_25"), (10, "lvl_10"), (5, "lvl_5")):
                    if level >= lvl:
                        await dt.unlock_achievement(message.guild, message.author.id, ach, channel=None)
                if message.author.joined_at and (now - message.author.joined_at.timestamp()) >= 365 * 86400:
                    await dt.unlock_achievement(message.guild, message.author.id, "member_year", channel=None)
                if level_up and level > 0:
                    await message.channel.send(
                        f"🎉 **{message.author.display_name}**, новый уровень: **{level}** (+50 💰)!"
                    )
                    db.add_credits(message.guild.id, message.author.id, 50)
        except Exception:
            pass

    # ── Авто-модерация ──
    try:
        cfg = db.get_automod(message.guild.id)
        if cfg.get("enabled"):
            low = message.content.lower()
            bad = [w for w in cfg.get("bad_words", []) if w and w in low]
            if bad:
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
                count = db.add_warn(message.guild.id, message.author.id)
                await dt.unlock_achievement(message.guild, message.author.id, "warner", channel=None)
                try:
                    if count >= 3:
                        await message.author.timeout(datetime.timedelta(minutes=30), reason="Авто-мод: мат (3 варна)")
                        await message.channel.send(
                            f"🔇 **{message.author.display_name}** — мат запрещён! 3 варна → мут 30 мин.",
                            delete_after=20,
                        )
                    else:
                        await message.channel.send(
                            f"⚠️ {message.author.mention}, мат запрещён! Варн **{count}/3**.", delete_after=20
                        )
                except discord.Forbidden:
                    pass
    except Exception:
        pass

    if message.author.id not in OWNER_IDS:
        return

    raw = message.content.strip()
    match = re.match(r"^(луми|lumi)[\s,.:]*", raw, re.IGNORECASE)
    if not match:
        return

    user_prompt = raw[match.end() :].strip()

    if not user_prompt:
        await safe_send(message, "✨ На связи. Могу создать сервер с нуля, настроить каналы, роли, права, модерацию и сохранить шаблон в БД. Что делаем?")
        return

    if not DISCORD_TOKEN or not CLAUDE_API_KEY:
        await safe_send(message, "❌ Не заданы DISCORD_TOKEN или CLAUDE_API_KEY в .env")
        return

    guild = message.guild
    db.add_chat_message(guild.id, message.author.id, "user", user_prompt)

    async with message.channel.typing():
        try:
            messages = build_context(guild, user_prompt, message.author.id)
            TOKEN_USAGE["input"] += len(str(messages)) // 4

            progress = discord.Embed(
                title="⚡ Луми работает...",
                description="Выполняю инструменты (многошаговый режим)",
                color=discord.Color.gold(),
            )
            status_msg = await message.channel.send(embed=progress)

            final = await run_agent(guild, message.author.id, messages, notify_message=message)

            try:
                await status_msg.delete()
            except discord.HTTPException:
                pass

            if final:
                db.add_chat_message(guild.id, message.author.id, "assistant", final)
                await safe_send(message, final)

        except RuntimeError as e:
            try:
                await status_msg.delete()
            except Exception:
                pass
            await safe_send(
                message,
                f"💤 Временные трудности с ИИ ({e}). Попробуй ещё раз через минуту — или скажи «Луми, покажи статус».\n"
                "А вот команды для участников работают всегда: `!профиль  !топ  !магазин  !погода  !курс  !напомни`",
            )
        except Exception as e:
            await safe_send(message, f"💥 Ошибка ядра: {e}")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Укажи DISCORD_TOKEN в файле .env")
    else:
        bot.run(DISCORD_TOKEN)
