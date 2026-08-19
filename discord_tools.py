# Lumi — Discord-бот (PyQZone)
# Copyright (C) 2026 Антон Курченко Валейрович (Qcaps). Все права защищены.
# Лицензия: см. LICENSE. Распространение без разрешения правообладателя запрещено.
"""Все Discord-инструменты для бота Луми."""

import datetime
import io
import json
from typing import Any

import aiohttp
import discord

import database as db


# ── Поиск ──────────────────────────────────────────────────────────────────

def find_channel(guild: discord.Guild, name: str):
    needle = name.replace("#", "").strip().lower()
    for ch in guild.channels:
        if needle in ch.name.lower() or ch.name.lower() in needle:
            return ch
    return None


def find_text_channel(guild: discord.Guild, name: str):
    ch = find_channel(guild, name)
    return ch if isinstance(ch, discord.TextChannel) else None


def find_role(guild: discord.Guild, name: str):
    if name.lower() in ("everyone", "@everyone"):
        return guild.default_role
    return discord.utils.get(guild.roles, name=name)


def find_member(guild: discord.Guild, identifier: str):
    if identifier.isdigit():
        return guild.get_member(int(identifier))
    ident = identifier.lstrip("@").lower()
    for m in guild.members:
        if m.name.lower() == ident or m.display_name.lower() == ident:
            return m
    return None


def find_category(guild: discord.Guild, name: str):
    return discord.utils.get(guild.categories, name=name) or find_channel(guild, name)


def parse_color(hex_str: str | None) -> discord.Color:
    if not hex_str:
        return discord.Color.default()
    return discord.Color(int(hex_str.lstrip("#"), 16))


async def download_bytes(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception:
        pass
    return None


def guild_snapshot(guild: discord.Guild) -> dict:
    return {
        "name": guild.name,
        "description": guild.description,
        "categories": [
            {
                "name": c.name,
                "position": c.position,
                "channels": [
                    {
                        "name": ch.name,
                        "type": str(ch.type),
                        "topic": getattr(ch, "topic", None),
                    }
                    for ch in c.channels
                ],
            }
            for c in sorted(guild.categories, key=lambda x: x.position)
        ],
        "roles": [
            {"name": r.name, "color": str(r.color), "hoist": r.hoist, "position": r.position}
            for r in guild.roles
            if not r.is_default() and not r.managed
        ],
        "uncategorized_channels": [
            {"name": ch.name, "type": str(ch.type)}
            for ch in guild.channels
            if ch.category is None and not isinstance(ch, discord.CategoryChannel)
        ],
    }


# ── Роли ───────────────────────────────────────────────────────────────────

async def create_discord_role(
    guild: discord.Guild, name: str, color_hex: str = None, hoist: bool = True, mentionable: bool = True
) -> str:
    try:
        if find_role(guild, name):
            return f"Роль `{name}` уже существует."
        role = await guild.create_role(
            name=name, color=parse_color(color_hex), hoist=hoist, mentionable=mentionable
        )
        return f"✅ Создана роль: **{role.name}**"
    except Exception as e:
        return f"❌ Ошибка роли: {e}"


async def edit_discord_role(
    guild: discord.Guild,
    current_name: str,
    new_name: str = None,
    color_hex: str = None,
    hoist: bool = None,
    mentionable: bool = None,
) -> str:
    try:
        role = find_role(guild, current_name)
        if not role or role.is_default():
            return f"❌ Роль `{current_name}` не найдена."
        kwargs = {}
        if new_name:
            kwargs["name"] = new_name
        if color_hex:
            kwargs["color"] = parse_color(color_hex)
        if hoist is not None:
            kwargs["hoist"] = hoist
        if mentionable is not None:
            kwargs["mentionable"] = mentionable
        await role.edit(**kwargs)
        return f"🎨 Роль `{current_name}` обновлена!"
    except Exception as e:
        return f"❌ Ошибка редактирования роли: {e}"


async def delete_discord_role(guild: discord.Guild, name: str) -> str:
    try:
        role = find_role(guild, name)
        if not role or role.is_default() or role.managed:
            return f"❌ Роль `{name}` не найдена или не может быть удалена."
        await role.delete()
        return f"🗑️ Роль **{name}** удалена."
    except Exception as e:
        return f"❌ Ошибка удаления роли: {e}"


async def assign_role_to_member(guild: discord.Guild, member_name_or_id: str, role_name: str) -> str:
    try:
        member = find_member(guild, member_name_or_id)
        role = find_role(guild, role_name)
        if not member:
            return f"❌ Участник `{member_name_or_id}` не найден."
        if not role or role.is_default():
            return f"❌ Роль `{role_name}` не найдена."
        await member.add_roles(role, reason="Луми")
        return f"✅ Роль **{role.name}** выдана **{member.display_name}**."
    except Exception as e:
        return f"❌ Ошибка выдачи роли: {e}"


async def remove_role_from_member(guild: discord.Guild, member_name_or_id: str, role_name: str) -> str:
    try:
        member = find_member(guild, member_name_or_id)
        role = find_role(guild, role_name)
        if not member:
            return f"❌ Участник `{member_name_or_id}` не найден."
        if not role:
            return f"❌ Роль `{role_name}` не найдена."
        await member.remove_roles(role, reason="Луми")
        return f"✅ Роль **{role.name}** снята с **{member.display_name}**."
    except Exception as e:
        return f"❌ Ошибка снятия роли: {e}"


# ── Категории ──────────────────────────────────────────────────────────────

async def create_category(guild: discord.Guild, name: str, position: int = None) -> str:
    try:
        cat = await guild.create_category(name=name)
        if position is not None:
            await cat.edit(position=position)
        return f"✅ Создана категория: **{name}**"
    except Exception as e:
        return f"❌ Ошибка категории: {e}"


async def edit_category(
    guild: discord.Guild, current_name: str, new_name: str = None, position: int = None
) -> str:
    try:
        cat = find_category(guild, current_name)
        if not isinstance(cat, discord.CategoryChannel):
            return f"❌ Категория `{current_name}` не найдена."
        kwargs = {}
        if new_name:
            kwargs["name"] = new_name
        if position is not None:
            kwargs["position"] = position
        await cat.edit(**kwargs)
        return f"⚙️ Категория обновлена!"
    except Exception as e:
        return f"❌ Ошибка категории: {e}"


async def delete_category(guild: discord.Guild, name: str) -> str:
    try:
        cat = find_category(guild, name)
        if not isinstance(cat, discord.CategoryChannel):
            return f"❌ Категория `{name}` не найдена."
        await cat.delete()
        return f"🗑️ Категория **{name}** удалена."
    except Exception as e:
        return f"❌ Ошибка удаления категории: {e}"


# ── Каналы ─────────────────────────────────────────────────────────────────

async def create_discord_channel(
    guild: discord.Guild,
    name: str,
    channel_type: str,
    category_name: str = None,
    topic: str = None,
    user_limit: int = 0,
    bitrate: int = 64000,
) -> str:
    try:
        category = None
        if category_name:
            category = find_category(guild, category_name)
            if not isinstance(category, discord.CategoryChannel):
                category = await guild.create_category(name=category_name)

        formatted = name.strip()
        ch_type = channel_type.lower()

        if ch_type == "text":
            formatted = formatted.replace(" ", "-").lower()
            await guild.create_text_channel(name=formatted, category=category, topic=topic)
        elif ch_type == "voice":
            await guild.create_voice_channel(
                name=formatted, category=category, user_limit=user_limit, bitrate=bitrate
            )
        elif ch_type == "forum":
            formatted = formatted.replace(" ", "-").lower()
            await guild.create_forum_channel(name=formatted, category=category, topic=topic)
        elif ch_type == "announcement":
            formatted = formatted.replace(" ", "-").lower()
            await guild.create_text_channel(
                name=formatted, category=category, topic=topic, type=discord.ChannelType.news
            )
        elif ch_type == "stage":
            await guild.create_stage_channel(name=formatted, category=category)
        else:
            return f"❌ Неизвестный тип канала: {channel_type}"

        return f"✅ Создан канал: **{formatted}** ({ch_type})"
    except Exception as e:
        return f"❌ Ошибка канала '{name}': {e}"


async def edit_discord_channel(
    guild: discord.Guild,
    current_name: str,
    new_name: str = None,
    category_name: str = None,
    topic: str = None,
    slowmode: int = None,
    user_limit: int = None,
    nsfw: bool = None,
) -> str:
    try:
        channel = find_channel(guild, current_name)
        if not channel:
            return f"❌ Канал `{current_name}` не найден."
        kwargs = {}
        if new_name:
            kwargs["name"] = (
                new_name.strip().replace(" ", "-").lower()
                if isinstance(channel, discord.TextChannel)
                else new_name.strip()
            )
        if category_name is not None:
            if category_name == "":
                kwargs["category"] = None
            else:
                cat = find_category(guild, category_name)
                if not isinstance(cat, discord.CategoryChannel):
                    cat = await guild.create_category(name=category_name)
                kwargs["category"] = cat
        if topic is not None and isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            kwargs["topic"] = topic
        if slowmode is not None and isinstance(channel, discord.TextChannel):
            kwargs["slowmode_delay"] = slowmode
        if user_limit is not None and isinstance(channel, discord.VoiceChannel):
            kwargs["user_limit"] = user_limit
        if nsfw is not None and hasattr(channel, "nsfw"):
            kwargs["nsfw"] = nsfw
        await channel.edit(**kwargs)
        return f"⚙️ Канал `#{channel.name}` перенастроен!"
    except Exception as e:
        return f"❌ Ошибка изменения канала: {e}"


async def delete_discord_channel(guild: discord.Guild, name: str) -> str:
    try:
        channel = find_channel(guild, name)
        if channel:
            label = channel.name
            await channel.delete()
            return f"🗑️ **{label}** успешно удалён."
        return f"⚠️ Элемент `{name}` не найден."
    except Exception as e:
        return f"❌ Ошибка удаления: {e}"


async def move_channel(guild: discord.Guild, channel_name: str, position: int) -> str:
    try:
        channel = find_channel(guild, channel_name)
        if not channel:
            return f"❌ Канал `{channel_name}` не найден."
        await channel.edit(position=position)
        return f"↕️ Канал **{channel.name}** перемещён на позицию {position}."
    except Exception as e:
        return f"❌ Ошибка перемещения: {e}"


# ── Сообщения ──────────────────────────────────────────────────────────────

async def send_text_to_channel(
    guild: discord.Guild,
    channel_name: str,
    text: str,
    embed_title: str = None,
    color_hex: str = None,
    footer: str = None,
) -> str:
    try:
        channel = find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Текстовый канал не найден."
        if embed_title:
            embed = discord.Embed(
                title=f"✨ {embed_title} ✨",
                description=text,
                color=parse_color(color_hex or "#FFD700"),
            )
            embed.set_footer(text=footer or "Дизайн от Луми 🌟")
            await channel.send(embed=embed)
            return f"📝 Канал `#{channel.name}` оформлен Embed-блоком."
        await channel.send(text)
        return f"📝 Текст отправлен в `#{channel.name}`"
    except Exception as e:
        return f"❌ Ошибка отправки: {e}"


async def send_rich_embed(
    guild: discord.Guild,
    channel_name: str,
    title: str,
    description: str,
    fields: list = None,
    color_hex: str = "#FFD700",
    image_url: str = None,
    thumbnail_url: str = None,
    footer: str = "Луми 🌟",
    author_name: str = None,
) -> str:
    try:
        channel = find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        embed = discord.Embed(title=title, description=description, color=parse_color(color_hex))
        for f in fields or []:
            embed.add_field(name=f.get("name", "—"), value=f.get("value", "—"), inline=f.get("inline", False))
        if image_url:
            embed.set_image(url=image_url)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        if author_name:
            embed.set_author(name=author_name)
        if footer:
            embed.set_footer(text=footer)
        await channel.send(embed=embed)
        return f"📝 Rich Embed отправлен в `#{channel.name}`"
    except Exception as e:
        return f"❌ Ошибка embed: {e}"


async def clear_channel_messages(guild: discord.Guild, channel_name: str, amount: int) -> str:
    try:
        channel = find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        deleted = await channel.purge(limit=min(amount, 500))
        return f"🧹 Очищено сообщений: **{len(deleted)}**."
    except Exception as e:
        return f"❌ Ошибка очистки: {e}"


async def pin_message_in_channel(guild: discord.Guild, channel_name: str, message_id: int = None) -> str:
    try:
        channel = find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        if message_id:
            msg = await channel.fetch_message(message_id)
        else:
            async for msg in channel.history(limit=1):
                break
            else:
                return "❌ В канале нет сообщений."
        await msg.pin()
        return f"📌 Сообщение закреплено в `#{channel.name}`."
    except Exception as e:
        return f"❌ Ошибка закрепления: {e}"


# ── Права ──────────────────────────────────────────────────────────────────

async def set_channel_permissions(
    guild: discord.Guild,
    channel_name: str,
    role_name: str,
    view_channel: bool = None,
    send_messages: bool = None,
    connect: bool = None,
    speak: bool = None,
    manage_messages: bool = None,
) -> str:
    try:
        channel = find_channel(guild, channel_name)
        role = find_role(guild, role_name)
        if not channel:
            return f"❌ Канал `{channel_name}` не найден."
        if not role:
            return f"❌ Роль `{role_name}` не найдена."

        overwrite = channel.overwrites_for(role)
        if view_channel is not None:
            overwrite.view_channel = view_channel
        if send_messages is not None and isinstance(channel, discord.TextChannel):
            overwrite.send_messages = send_messages
        if connect is not None and isinstance(channel, discord.VoiceChannel):
            overwrite.connect = connect
        if speak is not None and isinstance(channel, discord.VoiceChannel):
            overwrite.speak = speak
        if manage_messages is not None and isinstance(channel, discord.TextChannel):
            overwrite.manage_messages = manage_messages

        await channel.set_permissions(role, overwrite=overwrite)
        return f"🔒 Права `#{channel.name}` для `{role.name}` обновлены."
    except Exception as e:
        return f"❌ Ошибка прав: {e}"


# ── Вебхуки / инвайты ──────────────────────────────────────────────────────

async def manage_webhook(
    guild: discord.Guild,
    channel_name: str,
    webhook_name: str,
    text: str,
    avatar_url: str = None,
) -> str:
    try:
        channel = find_text_channel(guild, channel_name)
        if not channel:
            return f"❌ Канал `#{channel_name}` не найден."
        webhooks = await channel.webhooks()
        webhook = discord.utils.get(webhooks, name=webhook_name)
        if not webhook:
            webhook = await channel.create_webhook(name=webhook_name)
        await webhook.send(content=text, username=webhook_name, avatar_url=avatar_url)
        return f"⚡ Через вебхук `{webhook_name}` отправлено сообщение."
    except Exception as e:
        return f"❌ Ошибка вебхука: {e}"


async def create_channel_invite(
    guild: discord.Guild, channel_name: str, max_age: int = 86400, max_uses: int = 0
) -> str:
    try:
        channel = find_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        invite = await channel.create_invite(max_age=max_age, max_uses=max_uses)
        return f"🔗 Инвайт: {invite.url}"
    except Exception as e:
        return f"❌ Ошибка инвайта: {e}"


# ── Сервер ─────────────────────────────────────────────────────────────────

async def set_server_name_and_icon(
    guild: discord.Guild, new_name: str = None, icon_url: str = None
) -> str:
    try:
        kwargs = {}
        if new_name:
            kwargs["name"] = new_name
        if icon_url:
            data = await download_bytes(icon_url)
            if data:
                kwargs["icon"] = io.BytesIO(data)
        if not kwargs:
            return "⚠️ Укажите new_name или icon_url."
        await guild.edit(**kwargs)
        parts = []
        if new_name:
            parts.append(f"имя → **{new_name}**")
        if icon_url:
            parts.append("иконка обновлена")
        return f"👑 Сервер обновлён: {', '.join(parts)}"
    except Exception as e:
        return f"❌ Ошибка сервера: {e}"


async def set_server_settings(
    guild: discord.Guild,
    description: str = None,
    banner_url: str = None,
    verification_level: str = None,
    default_notifications: str = None,
    explicit_content_filter: str = None,
) -> str:
    try:
        kwargs = {}
        if description is not None:
            kwargs["description"] = description[:1000]
        if banner_url:
            data = await download_bytes(banner_url)
            if data:
                kwargs["banner"] = io.BytesIO(data)
        vmap = {
            "none": discord.VerificationLevel.none,
            "low": discord.VerificationLevel.low,
            "medium": discord.VerificationLevel.medium,
            "high": discord.VerificationLevel.high,
            "highest": discord.VerificationLevel.highest,
        }
        if verification_level and verification_level.lower() in vmap:
            kwargs["verification_level"] = vmap[verification_level.lower()]
        nmap = {
            "all": discord.NotificationLevel.all_messages,
            "mentions": discord.NotificationLevel.only_mentions,
        }
        if default_notifications and default_notifications.lower() in nmap:
            kwargs["default_notifications"] = nmap[default_notifications.lower()]
        fmap = {
            "disabled": discord.ContentFilter.disabled,
            "no_role": discord.ContentFilter.no_role,
            "all_members": discord.ContentFilter.all_members,
        }
        if explicit_content_filter and explicit_content_filter.lower() in fmap:
            kwargs["explicit_content_filter"] = fmap[explicit_content_filter.lower()]
        if not kwargs:
            return "⚠️ Нечего менять — передайте параметры."
        await guild.edit(**kwargs)
        return "👑 Настройки сервера обновлены!"
    except Exception as e:
        return f"❌ Ошибка настроек: {e}"


async def get_server_info(guild: discord.Guild) -> str:
    snap = guild_snapshot(guild)
    lines = [
        f"**{guild.name}** (ID: {guild.id})",
        f"Участников: {guild.member_count}",
        f"Каналов: {len(guild.channels)} | Ролей: {len(guild.roles)}",
        f"Описание: {guild.description or '—'}",
        f"Категорий: {len(guild.categories)}",
    ]
    return "\n".join(lines) + f"\n\n```json\n{json.dumps(snap, ensure_ascii=False, indent=2)[:1800]}\n```"


# ── Модерация ──────────────────────────────────────────────────────────────

async def moderate_member(
    guild: discord.Guild,
    member_name_or_id: str,
    action: str,
    reason: str = "Решение Луми",
    duration_minutes: int = 30,
) -> str:
    try:
        member = find_member(guild, member_name_or_id)
        if not member:
            return f"❌ Участник `{member_name_or_id}` не найден."
        action = action.lower()
        if action == "kick":
            await member.kick(reason=reason)
            return f"🔨 Кикнут: **{member.display_name}**"
        if action == "ban":
            await member.ban(reason=reason)
            return f"💥 Забанен: **{member.display_name}**"
        if action == "unban":
            user_id = int(member_name_or_id) if member_name_or_id.isdigit() else None
            if not user_id:
                return "❌ Для разбана укажите ID пользователя."
            await guild.unban(discord.Object(id=user_id), reason=reason)
            return f"✅ Разбанен ID `{user_id}`"
        if action == "timeout":
            await member.timeout(datetime.timedelta(minutes=duration_minutes), reason=reason)
            return f"🔇 Мут {duration_minutes} мин: **{member.display_name}**"
        if action == "untimeout":
            await member.timeout(None, reason=reason)
            return f"🔊 Мут снят: **{member.display_name}**"
        return "⚠️ Действие: kick, ban, unban, timeout, untimeout."
    except Exception as e:
        return f"❌ Ошибка модерации: {e}"


async def edit_member_nickname(guild: discord.Guild, member_name_or_id: str, nickname: str) -> str:
    try:
        member = find_member(guild, member_name_or_id)
        if not member:
            return f"❌ Участник не найден."
        await member.edit(nick=nickname[:32] if nickname else None)
        return f"✅ Ник **{member.display_name}** → `{nickname}`"
    except Exception as e:
        return f"❌ Ошибка ника: {e}"


# ── Эмодзи ─────────────────────────────────────────────────────────────────

async def create_server_emoji(guild: discord.Guild, name: str, image_url: str) -> str:
    try:
        data = await download_bytes(image_url)
        if not data:
            return "❌ Не удалось загрузить изображение."
        emoji = await guild.create_custom_emoji(name=name[:32], image=data)
        return f"😀 Эмодзи создан: {emoji} `:{emoji.name}:`"
    except Exception as e:
        return f"❌ Ошибка эмодзи: {e}"


async def delete_server_emoji(guild: discord.Guild, name: str) -> str:
    try:
        emoji = discord.utils.get(guild.emojis, name=name)
        if not emoji:
            return f"❌ Эмодзи `{name}` не найден."
        await emoji.delete()
        return f"🗑️ Эмодзи **{name}** удалён."
    except Exception as e:
        return f"❌ Ошибка удаления эмодзи: {e}"


# ── База данных / шаблоны ──────────────────────────────────────────────────

async def save_server_template(guild: discord.Guild, template_name: str, description: str = "") -> str:
    try:
        payload = guild_snapshot(guild)
        db.save_template(guild.id, template_name, payload, description)
        return f"💾 Шаблон **{template_name}** сохранён ({len(payload.get('categories', []))} категорий)."
    except Exception as e:
        return f"❌ Ошибка сохранения: {e}"


async def apply_server_template(guild: discord.Guild, template_name: str) -> str:
    try:
        tpl = db.get_template(guild.id, template_name)
        if not tpl:
            return f"❌ Шаблон `{template_name}` не найден. Сначала сохраните или создайте."
        payload = tpl["payload"]
        results = []

        for role_data in payload.get("roles", []):
            r = await create_discord_role(
                guild, role_data["name"], role_data.get("color", "").replace("#", ""), role_data.get("hoist", True)
            )
            results.append(r)

        for cat_data in payload.get("categories", []):
            cat_result = await create_category(guild, cat_data["name"])
            results.append(cat_result)
            for ch in cat_data.get("channels", []):
                ch_type = "text"
                if "voice" in ch.get("type", "").lower():
                    ch_type = "voice"
                elif "forum" in ch.get("type", "").lower():
                    ch_type = "forum"
                elif "stage" in ch.get("type", "").lower():
                    ch_type = "stage"
                elif "news" in ch.get("type", "").lower():
                    ch_type = "announcement"
                cr = await create_discord_channel(
                    guild, ch["name"], ch_type, cat_data["name"], topic=ch.get("topic")
                )
                results.append(cr)

        ok = sum(1 for r in results if r.startswith("✅") or "Создан" in r)
        return f"🏗️ Шаблон **{template_name}** применён. Успешных операций: {ok}/{len(results)}"
    except Exception as e:
        return f"❌ Ошибка применения шаблона: {e}"


async def list_server_templates(guild: discord.Guild) -> str:
    templates = db.list_templates(guild.id)
    if not templates:
        return "📭 Шаблонов пока нет. Скажи «Луми, сохрани шаблон gaming»."
    lines = [f"• **{t['name']}** — {t.get('description') or 'без описания'}" for t in templates]
    return "💾 Шаблоны сервера:\n" + "\n".join(lines)


async def update_guild_theme(guild: discord.Guild, theme: str = None, accent_color: str = None) -> str:
    try:
        settings = db.update_guild_settings(guild.id, theme=theme, accent_color=accent_color)
        return f"🎨 Тема обновлена: `{settings['theme']}`, акцент `{settings['accent_color']}`"
    except Exception as e:
        return f"❌ Ошибка темы: {e}"


# ── Массовая настройка сервера с нуля ───────────────────────────────────────

async def setup_server_from_scratch(
    guild: discord.Guild,
    theme: str,
    server_name: str = None,
    roles: list = None,
    categories: list = None,
    welcome_message: str = None,
) -> str:
    """Создаёт полную структуру сервера: роли, категории, каналы, приветствие."""
    results = []
    try:
        if server_name:
            results.append(await set_server_name_and_icon(guild, new_name=server_name))

        db.update_guild_settings(guild.id, theme=theme)

        default_roles = roles or [
            {"name": "👑 Owner", "color": "#FF0000", "hoist": True},
            {"name": "🛡️ Admin", "color": "#E74C3C", "hoist": True},
            {"name": "✨ VIP", "color": "#FFD700", "hoist": True},
            {"name": "💬 Member", "color": "#3498DB", "hoist": False},
        ]
        for r in default_roles:
            results.append(
                await create_discord_role(guild, r["name"], r.get("color"), r.get("hoist", True))
            )

        default_cats = categories or [
            {
                "name": f"✦ {theme.upper()} ✦",
                "channels": [
                    {"name": "📌┃инфо-правила", "type": "text", "topic": "Правила и информация"},
                    {"name": "📢┃объявления", "type": "announcement"},
                    {"name": "💬┃общий-чат", "type": "text"},
                ],
            },
            {
                "name": "🎮 АКТИВНОСТЬ",
                "channels": [
                    {"name": "🎯┃игры", "type": "text"},
                    {"name": "🔊 Lobby 1", "type": "voice"},
                    {"name": "🔊 Lobby 2", "type": "voice"},
                ],
            },
            {
                "name": "🌙 ГОЛОС",
                "channels": [
                    {"name": "🎤 Stage", "type": "stage"},
                    {"name": "🔉 Chill", "type": "voice", "user_limit": 10},
                ],
            },
        ]

        for cat in default_cats:
            results.append(await create_category(guild, cat["name"]))
            for ch in cat.get("channels", []):
                results.append(
                    await create_discord_channel(
                        guild,
                        ch["name"],
                        ch.get("type", "text"),
                        cat["name"],
                        topic=ch.get("topic"),
                        user_limit=ch.get("user_limit", 0),
                    )
                )

        welcome = welcome_message or (
            f"Добро пожаловать на **{guild.name}**! 🌟\n"
            f"Тема сервера: **{theme}**\n"
            "Прочитай правила и приятного общения!"
        )
        info_ch = find_text_channel(guild, "инфо") or find_text_channel(guild, "правила")
        if info_ch:
            results.append(
                await send_text_to_channel(
                    guild, info_ch.name, welcome, embed_title=f"Добро пожаловать — {theme}", color_hex="#FFD700"
                )
            )

        ok = sum(1 for r in results if "✅" in r or "📝" in r or "👑" in r or "🏗" in r)
        db.save_template(guild.id, f"auto_{theme}", guild_snapshot(guild), f"Авто-сетап {theme}")
        return f"🏗️ Сервер **{theme}** собран с нуля! Операций: {ok}/{len(results)}.\n" + "\n".join(results[-5:])
    except Exception as e:
        return f"❌ Ошибка массовой настройки: {e}"


async def google_search_design_assets(guild: discord.Guild, query: str) -> str:
    """Подсказки по оформлению под тему."""
    presets = {
        "gaming": "🎮 ┃ 💎 ┃ ⚔️ ┃ 🏆 ┃ 🔥 — цвета #FF4654, #1a1a2e",
        "anime": "🌸 ┃ ✨ ┃ 🎌 ┃ 💮 ┃ 🌙 — цвета #FF69B4, #2D1B4E",
        "crypto": "💰 ┃ 📈 ┃ 🔗 ┃ ⚡ ┃ 🚀 — цвета #F7931A, #0D1117",
        "community": "💬 ┃ 🤝 ┃ 📌 ┃ 🎉 ┃ ⭐ — цвета #5865F2, #23272A",
        "music": "🎵 ┃ 🎧 ┃ 🎤 ┃ 🔊 ┃ 💿 — цвета #1DB954, #191414",
    }
    q = query.lower()
    for key, val in presets.items():
        if key in q:
            return f"[Луми] Стиль **{key}**: {val}. Применяй через create_discord_channel и create_discord_role."
    return f"[Луми] Для темы '{query}': используй эмодзи-разделители ┃, капс в категориях, lowercase в текстовых каналах."


async def delete_all_channels_in_category(guild: discord.Guild, category_name: str) -> str:
    try:
        cat = find_category(guild, category_name)
        if not isinstance(cat, discord.CategoryChannel):
            return f"❌ Категория `{category_name}` не найдена."
        count = 0
        for ch in list(cat.channels):
            await ch.delete()
            count += 1
        return f"🗑️ Удалено каналов в **{category_name}**: {count}"
    except Exception as e:
        return f"❌ Ошибка: {e}"


async def create_thread_in_channel(
    guild: discord.Guild, channel_name: str, thread_name: str, message: str = None
) -> str:
    try:
        channel = find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        thread = await channel.create_thread(name=thread_name[:100], auto_archive_duration=1440)
        if message:
            await thread.send(message)
        return f"🧵 Тред **{thread_name}** создан в `#{channel.name}`."
    except Exception as e:
        return f"❌ Ошибка треда: {e}"


async def get_action_history(guild: discord.Guild, limit: int = 10) -> str:
    actions = db.get_recent_actions(guild.id, limit)
    if not actions:
        return "📭 История действий пуста."
    lines = []
    for a in actions:
        status = "✅" if a["success"] else "❌"
        lines.append(f"{status} `{a['tool_name']}` — {a['created_at'][:19]}")
    return "📜 Последние действия:\n" + "\n".join(lines)


# ── Парсер времени (русский) ──────────────────────────────────────────────

import re as _re

_UNITS = [
    ("недел", 604800),
    ("день", 86400),
    ("дн", 86400),
    ("час", 3600),
    ("ч", 3600),
    ("минут", 60),
    ("мин", 60),
    ("секунд", 1),
    ("сек", 1),
]


def _unit_mult(s: str):
    s = s.lower()
    for key, mult in _UNITS:
        if s.startswith(key):
            return mult
    return None


def parse_when(text: str) -> int | None:
    """Парсит 'через 2 часа', 'завтра в 20:00', '15.03 18:00', 'в 18:30', iso. Возвращает unix ts."""
    import time
    t = text.strip().lower()
    now = int(time.time())
    m = _re.search(r"через\s+(\d+)\s*([а-я]+)", t)
    if m:
        mult = _unit_mult(m.group(2))
        if mult is None:
            return None
        return now + int(m.group(1)) * mult
    m = _re.search(r"(\d{1,2}):(\d{2})", t)
    hm = (int(m.group(1)), int(m.group(2))) if m else None
    if "послезавтра" in t:
        d = now + 2 * 86400
    elif "завтра" in t:
        d = now + 86400
    else:
        d = now
    if hm:
        lt = time.localtime(d)
        target = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hm[0], hm[1], 0, 0, 0, -1))
        if target <= now and "завтра" not in t and "послезавтра" not in t:
            target += 86400
        return int(target)
    m = _re.search(r"(\d{1,2})[./](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", t)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        hh, mm = (int(m.group(3)), int(m.group(4))) if m.group(3) else (12, 0)
        lt = time.localtime(now)
        target = time.mktime((lt.tm_year, month, day, hh, mm, 0, 0, 0, -1))
        return int(target)
    m = _re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})[ T](\d{1,2}):(\d{2})", t)
    if m:
        return int(time.mktime((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                int(m.group(4)), int(m.group(5)), 0, 0, 0, -1)))
    if "через" in t:
        return None
    return None


# ── Картинки ──────────────────────────────────────────────────────────────

async def generate_image(guild: discord.Guild, prompt: str, channel_name: str = None) -> str:
    """Генерирует картинку: DALL-E 3 через релей, при отказе — бесплатный Pollinations."""
    import os
    try:
        channel = find_text_channel(guild, channel_name) if channel_name else None
        if not channel:
            return "❌ Текстовый канал не найден (укажи channel_name)."
        png_bytes = None
        used = ""
        api_key = os.getenv("CLAUDE_API_KEY", "")
        base_url = os.getenv("BASE_URL", "")
        if api_key and base_url:
            try:
                payload = {
                    "model": "dall-e-3",
                    "prompt": prompt[:900],
                    "n": 1,
                    "size": "1024x1024",
                }
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        f"{base_url.rstrip('/')}/images/generations",
                        json=payload,
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as r:
                        if r.status == 200:
                            data = await r.json()
                            item = (data.get("data") or [{}])[0]
                            if item.get("b64_json"):
                                import base64 as _b64
                                png_bytes = _b64.b64decode(item["b64_json"])
                            elif item.get("url"):
                                png_bytes = await download_bytes(item["url"])
                            used = "DALL-E 3"
            except Exception:
                pass
        if not png_bytes:
            import urllib.parse
            url = (
                "https://image.pollinations.ai/prompt/"
                + urllib.parse.quote(prompt[:500])
                + "?width=1024&height=1024&model=flux"
            )
            req = aiohttp.ClientSession()
            try:
                async with req as s:
                    async with s.get(
                        url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0 Safari/537.36"},
                        timeout=aiohttp.ClientTimeout(total=90),
                    ) as r:
                        if r.status == 200:
                            png_bytes = await r.read()
                            used = "Pollinations (бесплатный)"
            except Exception:
                pass
        if not png_bytes:
            return "❌ Не удалось сгенерировать картинку (оба сервиса недоступны)."
        embed = discord.Embed(title=f"🎨 {prompt[:200]}", color=parse_color("#9B59B6"))
        embed.set_footer(text=f"Луми | {used}")
        await channel.send(embed=embed, file=discord.File(io.BytesIO(png_bytes), filename="lumi_image.jpg"))
        return f"✅ Картинка сгенерирована через **{used}** → `#{channel.name}`."
    except Exception as e:
        return f"❌ Ошибка генерации: {e}"


# ── Экономика / уровни ────────────────────────────────────────────────────

async def give_credits(guild: discord.Guild, member_name_or_id: str, amount: int) -> str:
    try:
        member = find_member(guild, member_name_or_id)
        if not member:
            return f"❌ Участник `{member_name_or_id}` не найден."
        balance = db.add_credits(guild.id, member.id, int(amount))
        return f"💰 Участнику **{member.display_name}** начислено {int(amount)} кредитов. Баланс: **{balance}**."
    except Exception as e:
        return f"❌ Ошибка начисления: {e}"


async def add_shop_item(guild: discord.Guild, role_name: str, price: int) -> str:
    try:
        role = find_role(guild, role_name)
        if not role or role.is_default():
            return f"❌ Роль `{role_name}` не найдена на сервере."
        if db.add_shop_item(guild.id, role.name, int(price)):
            return f"🛒 Роль **{role.name}** добавлена в магазин за {int(price)} кредитов."
        return f"⚠️ Роль `{role_name}` уже в магазине."
    except Exception as e:
        return f"❌ Ошибка магазина: {e}"


async def remove_shop_item(guild: discord.Guild, role_name: str) -> str:
    try:
        if db.remove_shop_item(guild.id, role_name):
            return f"🗑️ Роль `{role_name}` убрана из магазина."
        return f"❌ Роль `{role_name}` не в магазине."
    except Exception as e:
        return f"❌ Ошибка магазина: {e}"


async def show_shop(guild: discord.Guild) -> str:
    items = db.list_shop_items(guild.id)
    if not items:
        return "🛒 Магазин пуст. Добавь роли: «Луми, добавь роль VIP в магазин за 500 кредитов»."
    lines = [f"• **{i['role_name']}** — {i['price']} 💰" for i in items]
    return "🛒 Магазин ролей:\n" + "\n".join(lines)


async def get_leaderboard(guild: discord.Guild, limit: int = 10) -> str:
    board = db.leaderboard(guild.id, min(limit, 20))
    if not board:
        return "📭 Пока нет статистики — начни общаться!"
    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(board):
        member = guild.get_member(row["member_id"])
        name = member.display_name if member else f"id:{row['member_id']}"
        medal = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{medal} **{name}** — ур. {row['level']} | {row['xp']} XP | {row['messages']} сообщений")
    return "🏆 Топ участников:\n" + "\n".join(lines)


async def get_profile(guild: discord.Guild, member_name_or_id: str) -> str:
    try:
        member = find_member(guild, member_name_or_id)
        if not member:
            return f"❌ Участник `{member_name_or_id}` не найден."
        stats = db.get_member_stats(guild.id, member.id)
        credits = db.get_credits(guild.id, member.id)
        warns = db.get_warns(guild.id, member.id)
        bday = db.get_birthday(guild.id, member.id)
        bday_txt = f"{bday['day']:02d}.{bday['month']:02d}" if bday else "—"
        return (
            f"👤 **{member.display_name}**\n"
            f"▸ Уровень: **{stats['level']}** | XP: {stats['xp']} | Сообщений: {stats['messages']}\n"
            f"▸ Кредиты: **{credits}** 💰\n"
            f"▸ Варны: {warns} ⚠️\n"
            f"▸ День рождения: {bday_txt} 🎂"
        )
    except Exception as e:
        return f"❌ Ошибка профиля: {e}"


# ── Напоминания и ивенты ──────────────────────────────────────────────────

async def set_reminder(
    guild: discord.Guild, when: str, text: str, channel_name: str, member_name_or_id: str = None
) -> str:
    try:
        ts = parse_when(when)
        if not ts:
            return "❌ Не понял время. Форматы: «через 2 часа», «завтра в 20:00», «15.03 18:00», «в 18:30»."
        channel = find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        member = find_member(guild, member_name_or_id) if member_name_or_id else None
        rid = db.add_reminder(guild.id, member.id if member else 0, channel.id, ts, text)
        import datetime
        when_s = datetime.datetime.fromtimestamp(ts).strftime("%d.%m %H:%M")
        return f"⏰ Напоминание #{rid}: **{text[:80]}** — {when_s} в `#{channel.name}`."
    except Exception as e:
        return f"❌ Ошибка напоминания: {e}"


async def schedule_event(
    guild: discord.Guild,
    name: str,
    date_time: str,
    channel_name: str,
    reminder_minutes: int = 60,
) -> str:
    try:
        ts = parse_when(date_time)
        if not ts:
            return "❌ Не понял время ивента. Примеры: «сегодня в 21:00», «завтра в 19:30», «20.02 15:00»."
        channel = find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        import datetime
        eid = db.add_event(guild.id, name, ts, channel.id, reminder_minutes * 60)
        when_s = datetime.datetime.fromtimestamp(ts).strftime("%d.%m %Y %H:%M")
        embed = discord.Embed(
            title=f"📅 {name}",
            description=f"🚀 Когда: **{when_s}**\n⏰ Напомню за {reminder_minutes} мин\n📍 Канал: {channel.mention}",
            color=parse_color("#5865F2"),
        )
        await channel.send(embed=embed)
        return f"📅 Ивент «{name}» на {when_s} (ID {eid}) — напомню за {reminder_minutes} мин."
    except Exception as e:
        return f"❌ Ошибка ивента: {e}"


async def list_upcoming_events(guild: discord.Guild) -> str:
    events = db.list_events(guild.id)
    if not events:
        return "📭 Ближайших ивентов нет."
    import datetime
    lines = []
    for e in events:
        when_s = datetime.datetime.fromtimestamp(e["when_ts"]).strftime("%d.%m %H:%M")
        lines.append(f"• **{e['name']}** — {when_s}")
    return "📅 Ближайшие ивенты:\n" + "\n".join(lines)


# ── Утилиты ───────────────────────────────────────────────────────────────

async def get_weather(guild: discord.Guild, city: str) -> str:
    import services
    return await services.weather(city)


async def get_currency(guild: discord.Guild, base: str = "RUB") -> str:
    import services
    return await services.currency(base)


async def translate_text(guild: discord.Guild, text: str, target: str = "ru") -> str:
    import services
    return await services.translate_text(text, target)


async def send_fun_fact(guild: discord.Guild, channel_name: str) -> str:
    import random
    import services
    channel = find_text_channel(guild, channel_name)
    if not channel:
        return "❌ Канал не найден."
    await channel.send(f"💡 {random.choice(services.FACTS)}")
    return f"✅ Факт отправлен в `#{channel.name}`."


async def send_joke(guild: discord.Guild, channel_name: str) -> str:
    import random
    import services
    channel = find_text_channel(guild, channel_name)
    if not channel:
        return "❌ Канал не найден."
    await channel.send(f"😄 {random.choice(services.JOKES)}")
    return f"✅ Шутка в `#{channel.name}`."


async def send_truth_or_dare(guild: discord.Guild, channel_name: str, kind: str = None) -> str:
    import services
    channel = find_text_channel(guild, channel_name)
    if not channel:
        return "❌ Канал не найден."
    await channel.send(services.truth_or_dare(kind))
    return f"✅ Задание в `#{channel.name}`."


async def send_meme(guild: discord.Guild, channel_name: str) -> str:
    import services
    channel = find_text_channel(guild, channel_name)
    if not channel:
        return "❌ Канал не найден."
    url = await services.meme()
    if url:
        embed = discord.Embed(color=parse_color("#E67E22"))
        embed.set_image(url=url)
        await channel.send(embed=embed)
        return f"✅ Мем в `#{channel.name}`."
    await channel.send(f"😄 {__import__('random').choice(services.JOKES)}")
    return f"✅ Мем не пришёл — шутка в `#{channel.name}`."


# ── Авто-модерация ────────────────────────────────────────────────────────

async def setup_automod(
    guild: discord.Guild, enabled: bool = True, bad_words: list = None, min_interval: float = 5.0
) -> str:
    try:
        cfg = db.save_automod(guild.id, enabled, bad_words, min_interval)
        words = ", ".join(f"`{w}`" for w in cfg["bad_words"][:12]) or "—"
        return (
            f"🛡 Авто-мод: {'ВКЛЮЧЕН' if cfg['enabled'] else 'выключен'}\n"
            f"▸ Слова: {words}\n"
            f"▸ Анти-спам: {cfg['min_interval']} сек между сообщениями"
        )
    except Exception as e:
        return f"❌ Ошибка настройки авто-мода: {e}"


# ── Дни рождения (инструменты) ────────────────────────────────────────────

async def register_birthday(guild: discord.Guild, member_name_or_id: str, date: str) -> str:
    try:
        member = find_member(guild, member_name_or_id)
        if not member:
            return f"❌ Участник `{member_name_or_id}` не найден."
        parts = date.strip().split(".")
        if len(parts) < 2:
            return "❌ Формат даты: ДД.ММ или ДД.ММ.ГГГГ"
        day, month = int(parts[0]), int(parts[1])
        year = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
        if not (1 <= day <= 31 and 1 <= month <= 12):
            return "❌ Неверная дата."
        db.register_birthday_db(guild.id, member.id, member.display_name, month, day, year)
        await unlock_achievement(guild, member.id, "bday_set")
        return f"🎂 День рождения **{member.display_name}**: {day:02d}.{month:02d}" + (f".{year}" if year else "")
    except ValueError:
        return "❌ Формат даты: ДД.ММ или ДД.ММ.ГГГГ"
    except Exception as e:
        return f"❌ Ошибка: {e}"


async def list_birthdays(guild: discord.Guild) -> str:
    rows = db.list_birthdays_db(guild.id)
    if not rows:
        return "🎂 Дней рождения пока не записано. Кнопка «Отметить мой ДР» на панели."
    lines = []
    for b in rows:
        year_s = f".{b['year']}" if b.get("year") else ""
        lines.append(f"• {b['name']} — {b['day']:02d}.{b['month']:02d}{year_s}")
    return "🎂 Дни рождения клана:\n" + "\n".join(lines)


async def set_birthday_channel(guild: discord.Guild, channel_name: str) -> str:
    try:
        channel = find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        db.set_guild_channel(guild.id, "birthday", channel.id)
        return f"🎂 Канал дней рождения: `#{channel.name}`."
    except Exception as e:
        return f"❌ Ошибка: {e}"


# ── Приветствие ───────────────────────────────────────────────────────────

async def setup_welcome(
    guild: discord.Guild,
    channel_name: str,
    rules_text: str = None,
    guest_role_name: str = None,
    enabled: bool = True,
) -> str:
    try:
        channel = find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        role = find_role(guild, guest_role_name) if guest_role_name else None
        rules = rules_text or (
            "Правила сервера:\n"
            "1. Уважай других участников.\n"
            "2. Не спамь и не флуди.\n"
            "3. Запрещён мат и оскорбления.\n"
            "4. Не рекламируй без разрешения.\n"
            "5. Слушайся модераторов."
        )
        db.save_welcome_config(
            guild.id, channel_id=channel.id, rules_text=rules,
            guest_role_id=role.id if role else None, enabled=enabled,
        )
        embed = discord.Embed(
            title="👋 Добро пожаловать!",
            description=rules,
            color=parse_color("#57F287"),
        )
        await channel.send(embed=embed)
        return (
            f"✅ Приветствие настроено: `#{channel.name}`"
            + (f", новички получают **{role.name}**" if role else "")
            + ("" if enabled else " (выключено)")
        )
    except Exception as e:
        return f"❌ Ошибка приветствия: {e}"


# ── Клановый сервер с нуля ────────────────────────────────────────────────

CLAN_ROLES = [
    ("👤 Гость", "#99AAB5", False),
    ("🔸 Новичок", "#7289DA", False),
    ("🔰 Член клана", "#3498DB", False),
    ("⭐ Ветеран", "#F1C40F", True),
    ("🎖 Офицер", "#E67E22", True),
    ("🧠 Заместитель", "#9B59B6", True),
    ("👑 Шеф", "#FF4654", True),
]

CLAN_CATEGORIES = [
    ("📌 ИНФОРМАЦИЯ", [
        {"name": "📢┃объявления", "type": "announcement"},
        {"name": "📃┃правила", "type": "text", "topic": "Правила сервера"},
        {"name": "ℹ️┃инфо", "type": "text", "topic": "О сервере и клане"},
    ]),
    ("👑 КОМАНДОВАНИЕ", [
        {"name": "💬┃правление", "type": "text"},
        {"name": "🛡┃модерация", "type": "text"},
        {"name": "🗣┃штаб", "type": "voice"},
    ]),
    ("💬 ЖИЗНЬ КЛАНА", [
        {"name": "💬┃общий-чат", "type": "text"},
        {"name": "🎮┃игровые-сессии", "type": "text"},
        {"name": "🖼┃скрины", "type": "forum"},
        {"name": "🔊┃голос-1", "type": "voice", "user_limit": 10},
        {"name": "🔊┃голос-2", "type": "voice", "user_limit": 10},
        {"name": "🎧┃афк", "type": "voice", "user_limit": 0},
    ]),
    ("🌍 ОБЩЕЕ", [
        {"name": "💬┃общий", "type": "text", "topic": "Общение для всех"},
        {"name": "🛠┃оффтоп", "type": "text"},
        {"name": "🔊┃лобби", "type": "voice"},
    ]),
    ("🎫 ЗАЯВКИ", [
        {"name": "🎫┃заявки-в-клан", "type": "text", "topic": "Подай заявку на вступление в клан"},
    ]),
    ("🎂 ДНИ РОЖДЕНИЯ", [
        {"name": "🎂┃даты-дней-рождений", "type": "text", "topic": "Дни рождения клана"},
    ]),
    ("🛡 РОЛИ И ДОСТУП", [
        {"name": "🎭┃выбор-ролей", "type": "text", "topic": "Выбери свою подгруппу"},
        {"name": "✅┃верификация", "type": "text", "topic": "Прочитай правила и получи доступ"},
    ]),
]


def _clan_subgroup_cats(subgroups: list) -> list:
    cats = []
    for i, sub in enumerate(subgroups):
        cats.append((f"🔒 ГРУППА {i + 1} · {sub.upper()}", [
            {"name": f"💬┃чат-{sub.lower()}", "type": "text"},
            {"name": f"🔊┃голос-{sub.lower()}", "type": "voice"},
        ]))
    return cats


async def setup_clan_server(
    guild: discord.Guild,
    clan_name: str = None,
    server_name: str = None,
    subgroups: list = None,
    confirmed: bool = False,
) -> str:
    """Полный сетап RUST-кланового сервера: роли, ветки, права, панели. Требует подтверждения."""
    import components as comp
    results = []
    try:
        subs = [str(s).strip() for s in (subgroups or ["Ферма", "Экономика", "Рейды", "Стройка", "Ивенты", "Снайперы", "Разведка"]) if str(s).strip()][:7]
        clan = (clan_name or "Клан").strip()

        if not confirmed:
            ch_count = len(guild.channels)
            role_count = len([r for r in guild.roles if not r.is_default() and not r.managed])
            plan = (
                f"🏗️ **План сборки клан-сервера «{clan}»**\n\n"
                f"⚠️ **Будет УДАЛЕНО:** {ch_count} каналов, {role_count} обычных ролей.\n"
                f"**Будет СОЗДАНО:** 7 ролей рангов + {len(subs)} ролей подгрупп,\n"
                f"категории: ИНФОРМАЦИЯ, КОМАНДОВАНИЕ (приват), ЖИЗНЬ КЛАНА, ОБЩЕЕ, ЗАЯВКИ (тикеты), "
                f"ДНИ РОЖДЕНИЯ, РОЛИ И ДОСТУП + {len(subs)} приватных веток групп.\n"
                f"Панели: правила, верификация, само-выбор ролей, тикеты, дни рождения.\n\n"
                f"Подгруппы: {', '.join(subs)}\n"
                f"🗣 **Подтверди удаление и создание: «да, подтверждаю»**"
            )
            return plan

        # 1. Удаление старой структуры
        for cat in list(guild.categories):
            try:
                await cat.delete()
                results.append(f"🗑️ категория {cat.name}")
            except Exception as e:
                results.append(f"⚠️ {cat.name}: {e}")
        for ch in list(guild.channels):
            if ch.category is not None:
                continue
            try:
                await ch.delete()
                results.append(f"🗑️ канал {ch.name}")
            except Exception:
                pass
        for role in list(guild.roles):
            if role.is_default() or role.managed or role == guild.me.top_role:
                continue
            try:
                await role.delete()
                results.append(f"🗑️ роль {role.name}")
            except Exception:
                pass

        # 2. Роли (снизу вверх)
        created_roles = {}
        for name, color, hoist in CLAN_ROLES:
            try:
                role = await guild.create_role(name=name, color=parse_color(color), hoist=hoist, mentionable=True)
                created_roles[name] = role
                results.append(f"✅ роль {name}")
            except Exception as e:
                results.append(f"❌ роль {name}: {e}")

        # 3. Роли подгрупп
        subgroup_roles = {}
        for sub in subs:
            role_name = f"🎖 {sub}"
            try:
                role = await guild.create_role(name=role_name, color=parse_color("#2ECC71"), hoist=True, mentionable=False)
                subgroup_roles[sub] = role
                created_roles[role_name] = role
                results.append(f"✅ роль {role_name}")
            except Exception as e:
                results.append(f"❌ роль {role_name}: {e}")

        def rl(name):
            return created_roles.get(name)

        # 4. Категории и каналы
        cats = CLAN_CATEGORIES + _clan_subgroup_cats(subs)

        for cat_name, channels_data in cats:
            try:
                cat = await guild.create_category(cat_name)
            except Exception as e:
                results.append(f"❌ категория {cat_name}: {e}")
                continue
            overwrites = {}
            if cat_name == "👑 КОМАНДОВАНИЕ":
                for rn in CLAN_ROLES:
                    r_ = rl(rn[0])
                    if r_:
                        overwrites[r_] = discord.PermissionOverwrite()
                for rn in ["👤 Гость", "🔸 Новичок", "🔰 Член клана", "⭐ Ветеран"]:
                    r_ = rl(rn)
                    if r_:
                        overwrites[r_] = discord.PermissionOverwrite(view_channel=False)
                for rn in ["🎖 Офицер", "🧠 Заместитель", "👑 Шеф"]:
                    r_ = rl(rn)
                    if r_:
                        overwrites[r_] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            elif cat_name == "🎫 ЗАЯВКИ" or cat_name == "🎂 ДНИ РОЖДЕНИЯ" or cat_name.startswith("🛡"):
                overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
                for rn, _, _ in CLAN_ROLES:
                    r_ = rl(rn)
                    if r_:
                        overwrites[r_] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
            elif cat_name.startswith("🔒 ГРУППА"):
                sub = subs[cats.index((cat_name, channels_data)) - len(CLAN_CATEGORIES)]
                overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                grp_role = subgroup_roles.get(sub)
                if grp_role:
                    overwrites[grp_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
                for rn in ["👑 Шеф", "🧠 Заместитель", "🎖 Офицер"]:
                    r_ = rl(rn)
                    if r_:
                        overwrites[r_] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            elif cat_name == "💬 ЖИЗНЬ КЛАНА":
                overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                for rn in ["👤 Гость", "🔸 Новичок"]:
                    r_ = rl(rn)
                    if r_:
                        overwrites[r_] = discord.PermissionOverwrite(view_channel=False)
                for rn in ["🔰 Член клана", "⭐ Ветеран", "🎖 Офицер", "🧠 Заместитель", "👑 Шеф"]:
                    r_ = rl(rn)
                    if r_:
                        overwrites[r_] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            elif cat_name == "🌍 ОБЩЕЕ":
                overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

            try:
                await cat.edit(overwrites=overwrites or None)
            except Exception:
                pass

            for cd in channels_data:
                ch_name = cd["name"]
                ch_type = cd.get("type", "text")
                topic = cd.get("topic")
                try:
                    if ch_type == "voice":
                        await guild.create_voice_channel(name=ch_name, category=cat, user_limit=cd.get("user_limit", 0))
                    elif ch_type == "forum":
                        await guild.create_forum_channel(name=ch_name, category=cat, topic=topic)
                    elif ch_type == "announcement":
                        await guild.create_text_channel(name=ch_name, category=cat, topic=topic, type=discord.ChannelType.news)
                    else:
                        await guild.create_text_channel(name=ch_name, category=cat, topic=topic)
                    results.append(f"✅ канал {ch_name}")
                except Exception as e:
                    results.append(f"❌ канал {ch_name}: {e}")

        # 5. Панели и оформление
        info_ch = find_text_channel(guild, "инфо")
        rules_ch = find_text_channel(guild, "правила")
        ann_ch = find_text_channel(guild, "объявления")
        clan_ch = find_text_channel(guild, "общий-чат")
        app_ch = find_text_channel(guild, "заявки-в-клан")
        roles_ch = find_text_channel(guild, "выбор-ролей")
        verify_ch = find_text_channel(guild, "верификация")
        bday_ch = find_text_channel(guild, "даты-дней-рождений")

        if server_name:
            results.append(await set_server_name_and_icon(guild, new_name=server_name))
        db.update_guild_settings(guild.id, theme="clan")

        if ann_ch and rl("👑 Шеф"):
            try:
                await ann_ch.set_permissions(guild.default_role, overwrite=discord.PermissionOverwrite(send_messages=False))
                await ann_ch.set_permissions(rl("🎖 Офицер"), overwrite=discord.PermissionOverwrite(send_messages=True))
            except Exception:
                pass

        if info_ch:
            results.append(
                await send_rich_embed(
                    guild, info_ch.name, f"👑 Добро пожаловать в клан **{clan}**!",
                    "Это сервер клана по RUST.\nПройди верификацию, прочитай правила и присоединяйся!\nХочешь к нам? Подай заявку в разделе ЗАЯВКИ.",
                    color_hex="#FF4654",
                )
            )

        if rules_ch:
            results.append(
                await send_rich_embed(
                    guild, rules_ch.name, "📜 Правила клана",
                    "1. Уважение к соклановцам — обязательно.\n2. Мат и оскорбления запрещены.\n"
                    "3. Запрещён дюп/читы — бан без разговоров.\n4. Рейды и походы — только по плану командования.\n"
                    "5. Скрины и отчёты о рейдах — в раздел ЖИЗНЬ КЛАНА.\n6. Вопросы к клану → тикет в разделе ЗАЯВКИ.",
                    color_hex="#F1C40F",
                )
            )

        if app_ch and rl("🎖 Офицер"):
            results.append(
                await comp.setup_ticket_panel(
                    guild, app_ch.name,
                    category_name="🎫 ЗАЯВКИ",
                    support_role_name="🎖 Офицер",
                    title="🎫 Заявка на вступление в клан",
                    description="Хочешь вступить в клан **{name}**? Нажми кнопку и заполни заявку.\nСкажи: ник в игре, часы онлайн, опыт в RUST.".format(name=clan),
                    button_label="📝 Подать заявку",
                    button_emoji="📝",
                    welcome_message="Привет! Расскажи о себе:\n▸ Ник в RUST\n▸ Часы за неделю\n▸ Опыт/были ли кланы\n▸ Что умеешь (фарм/стройка/пвп)",
                )
            )

        if roles_ch and subgroup_roles:
            opts = [{"role_name": r.name, "label": r.name, "emoji": "🎖"} for r in subgroup_roles.values()]
            results.append(await comp.setup_self_role_panel(guild, roles_ch.name, title="🎭 Выбор подгруппы", roles=opts))

        if verify_ch:
            results.append(
                await comp.send_verification_panel(
                    guild, verify_ch.name,
                    verified_role_name="🔰 Член клана",
                    title="✅ Верификация",
                    description="Прочитал правила и согласен с ними?\nНажми кнопку — получишь доступ к жизни клана.",
                )
            )

        if bday_ch:
            results.append(await comp.setup_birthday_panel(guild, bday_ch.name))
            db.set_guild_channel(guild.id, "birthday", bday_ch.id)

        if clan_ch:
            results.append(await send_text_to_channel(guild, clan_ch.name, "@everyone Готово! Сервер собран 🎉"))

        db.save_template(guild.id, f"clan_{clan}", guild_snapshot(guild), f"Клан-сервер {clan}")
        ok = sum(1 for r in results if r.startswith(("✅", "📝", "🏗", "👑")))
        return f"🏗️ **Клан-сервер «{clan}» собран!** Операций: {ok}/{len(results)}\n" + "\n".join(results[-8:])
    except Exception as e:
        return f"❌ Ошибка сборки: {e}"


# ── Ачивки и профиль-карточка ─────────────────────────────────────────────

ACHIEVEMENTS = {
    "intro": {"emoji": "💬", "name": "Первое слово", "desc": "Написать первое сообщение"},
    "msg_100": {"emoji": "🗣️", "name": "Болтун", "desc": "100 сообщений"},
    "msg_1000": {"emoji": "🎙️", "name": "Оратор", "desc": "1000 сообщений"},
    "voice_1h": {"emoji": "🎧", "name": "Голосовой", "desc": "1 час в голосовом"},
    "voice_10h": {"emoji": "📡", "name": "Вещатель", "desc": "10 часов в голосовом"},
    "lvl_5": {"emoji": "🧭", "name": "Взросление", "desc": "Достигнуть 5 уровня"},
    "lvl_10": {"emoji": "🚀", "name": "Профи", "desc": "Достигнуть 10 уровня"},
    "lvl_25": {"emoji": "👑", "name": "Ветеран", "desc": "Достигнуть 25 уровня"},
    "shop_buy": {"emoji": "🛍️", "name": "Шопоголик", "desc": "Первая покупка в магазине"},
    "first_transfer": {"emoji": "🤝", "name": "Филантроп", "desc": "Первый перевод кредитов"},
    "quiz_ok": {"emoji": "🧠", "name": "Эрудит", "desc": "Ответить в викторине"},
    "poll_vote": {"emoji": "🗳️", "name": "Демократ", "desc": "Проголосовать"},
    "warner": {"emoji": "🛡️", "name": "Устойчивый", "desc": "Получить предупреждение и остаться"},
    "bday_set": {"emoji": "🎂", "name": "Именинник", "desc": "Указать день рождения"},
    "member_year": {"emoji": "⏳", "name": "Ветеран сервера", "desc": "На сервере больше года"},
    "daily_7": {"emoji": "📅", "name": "Неделя наград", "desc": "Забирать дневной бонус 7 дней подряд"},
    "fav_first": {"emoji": "💖", "name": "Коллекционер", "desc": "Добавить первый трек в избранное"},
}

ACHIEVEMENT_ORDER = list(ACHIEVEMENTS.keys())


async def unlock_achievement(
    guild: discord.Guild, user_id: int, ach_id: str, channel=None
) -> bool:
    """Открывает ачивку; при открытии шлёт уведомление. Возвращает True если открыта сейчас."""
    if ach_id not in ACHIEVEMENTS:
        return False
    if not db.add_achievement(user_id, ach_id):
        return False
    if channel is None:
        channel = guild.system_channel
    if channel is None:
        return True
    a = ACHIEVEMENTS[ach_id]
    member = guild.get_member(user_id) if user_id else None
    embed = discord.Embed(
        title=f"{a['emoji']} Ачивка разблокирована!",
        description=f"**{a['name']}**\n{a['desc']}",
        color=discord.Color.gold(),
    )
    if member:
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass
    return True


async def list_achievements(guild: discord.Guild, member: discord.Member) -> str:
    opened = {a["ach_id"] for a in db.get_achievements(member.id)}
    lines = []
    for ach_id in ACHIEVEMENT_ORDER:
        a = ACHIEVEMENTS[ach_id]
        star = "✅" if ach_id in opened else "🔒"
        lines.append(f"{star} {a['emoji']} **{a['name']}** — {a['desc']}")
    progress = len([x for x in opened if x in ACHIEVEMENTS])
    bar_len = 15
    filled = round(progress / len(ACHIEVEMENTS) * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    return (
        f"🏆 **Ачивки {member.display_name}**: {progress}/{len(ACHIEVEMENTS)}\n"
        f"`{bar}`\n\n" + "\n".join(lines)
    )


def _load_font(size: int, bold: bool = False):
    from PIL import ImageFont
    candidates = (
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _rounded_avatar(img, size: int):
    from PIL import Image, ImageDraw
    img = img.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


async def render_welcome_card(member: discord.Member, rules_text: str = "") -> io.BytesIO | None:
    """Рисует приветственную карточку 800x250 (PNG). Возвращает BytesIO или None."""
    try:
        from PIL import Image, ImageDraw, ImageFilter

        width, height = 800, 250
        base = Image.new("RGB", (width, height), (18, 20, 28))
        draw = ImageDraw.Draw(base)
        for y in range(height):
            t = y / height
            r = int(18 + (52 - 18) * t)
            g = int(20 + (38 - 20) * t)
            b = int(28 + (66 - 28) * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse((width - 280, -160, width + 80, 200), fill=(255, 215, 0, 36))
        glow_draw.ellipse((-160, 120, 120, 400), fill=(88, 101, 242, 40))
        glow = glow.filter(ImageFilter.GaussianBlur(50))
        base = Image.alpha_composite(base.convert("RGBA"), glow).convert("RGB")
        draw = ImageDraw.Draw(base)

        avatar = None
        try:
            url = member.display_avatar.with_size(128).url
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        avatar = Image.open(io.BytesIO(await resp.read())).convert("RGBA")
        except Exception:
            avatar = None
        if avatar is None:
            avatar = Image.new("RGBA", (128, 128), (90, 95, 120))
            md = ImageDraw.Draw(avatar)
            md.text((64, 64), (member.display_name or "?")[:1].upper(), fill=(255, 255, 255), font=_load_font(52, True), anchor="mm")
        avatar = _rounded_avatar(avatar, 120)
        base.paste(avatar, (46, (height - 120) // 2), avatar)

        draw.text((206, 44), "ДОБРО ПОЖАЛОВАТЬ!", fill=(255, 215, 0), font=_load_font(26, True))
        name = (member.display_name or member.name)[:28]
        draw.text((206, 84), name, fill=(255, 255, 255), font=_load_font(34, True))
        drawn = (rules_text or "").strip()
        if drawn:
            if len(drawn) > 66:
                drawn = drawn[:66] + "..."
            draw.text((206, 138), drawn, fill=(200, 205, 220), font=_load_font(15))
        draw.text((206, 176), f"Мы рады тебя видеть на сервере!", fill=(150, 158, 180), font=_load_font(14))

        buf = io.BytesIO()
        base.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None


async def render_profile_card(member: discord.Member) -> io.BytesIO | None:
    """Рисует карточку профиля 600x300 (PNG). Возвращает BytesIO или None при ошибке."""
    try:
        from PIL import Image, ImageDraw, ImageFilter

        stats = db.get_member_stats(member.guild.id, member.id)
        xp = stats.get("xp", 0)
        level = stats.get("level", 0)
        credits = db.get_credits(member.guild.id, member.id)
        messages = stats.get("messages", 0)
        voice_min = db.get_voice_minutes(member.guild.id, member.id)
        next_xp = 50 * (level + 1) ** 2
        prev_xp = 50 * level ** 2
        pct = min(1.0, (xp - prev_xp) / max(1, next_xp - prev_xp))

        width, height = 600, 300
        base = Image.new("RGB", (width, height), (30, 31, 42))
        draw = ImageDraw.Draw(base)
        for y in range(height):
            t = y / height
            r = int(30 + (72 - 30) * t)
            g = int(31 + (45 - 31) * t)
            b = int(42 + (85 - 42) * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse((width - 260, -140, width + 60, 180), fill=(255, 215, 0, 40))
        glow = glow.filter(ImageFilter.GaussianBlur(40))
        base = Image.alpha_composite(base.convert("RGBA"), glow).convert("RGB")
        draw = ImageDraw.Draw(base)

        avatar = None
        try:
            url = member.display_avatar.with_size(128).url
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        avatar = Image.open(io.BytesIO(await resp.read())).convert("RGBA")
        except Exception:
            avatar = None
        if avatar is None:
            avatar = Image.new("RGBA", (128, 128), (90, 95, 120))
            md = ImageDraw.Draw(avatar)
            md.text((64, 58), (member.display_name or "?")[:1].upper(), fill=(255, 255, 255), font=_load_font(48, True), anchor="mm")
        avatar = _rounded_avatar(avatar, 128)
        base.paste(avatar, (36, (height - 128) // 2), avatar)

        font_big = _load_font(34, True)
        font_mid = _load_font(16, bold=True)
        font_small = _load_font(13)

        label = (member.display_name or member.name)[:24]
        draw.text((190, 36), label, fill=(255, 255, 255), font=font_big)

        draw.text((190, 86), f"Уровень", fill=(180, 185, 205), font=font_small)
        draw.text((190, 102), f"{level}", fill=(255, 215, 0), font=_load_font(44, True))

        bar_x, bar_y, bar_w, bar_h = 300, 112, 250, 18
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=9, fill=(70, 72, 92))
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w * pct, bar_y + bar_h), radius=9, fill=(255, 215, 0))
        draw.text((bar_x, bar_y + 22), f"XP: {xp} / {next_xp}", fill=(220, 222, 235), font=font_small)

        stats_line = f"💬 {messages} · 🎧 {voice_min} мин · 📖 {credits} 💰"
        draw.text((190, 158), stats_line, fill=(220, 222, 235), font=font_mid)

        recent = db.last_achievements(member.id, limit=3)
        ach_text = []
        for a in recent:
            info = ACHIEVEMENTS.get(a["ach_id"])
            if info:
                ach_text.append(f"{info['emoji']} {info['name']}")
        if ach_text:
            draw.text((36, height - 62), "Последние ачивки:", fill=(180, 185, 205), font=font_small)
            draw.text((36, height - 44), "  ".join(ach_text), fill=(255, 255, 255), font=font_mid)
        else:
            draw.text((36, height - 44), "Открой первую ачивку — пиши в чате!", fill=(180, 185, 205), font=font_small)

        buf = io.BytesIO()
        base.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None
