# Lumi — Discord-бот (PyQZone)
# Copyright (C) 2026 Антон Курченко Валейрович (Qcaps). Все права защищены.
# Лицензия: см. LICENSE. Распространение без разрешения правообладателя запрещено.
"""Кнопки, select-меню, тикет-система и интерактивные embed-панели."""

import discord

import database as db
import services

_bot = None

CID_TICKET_OPEN = "lumi:ticket_open"
CID_TICKET_CLOSE = "lumi:ticket_close"
CID_SELF_ROLE_PREFIX = "lumi:selfrole:"
CID_POLL_VOTE = "lumi:poll:vote:"
CID_POLL_RESULTS = "lumi:poll:results:"
CID_ANON_OPEN = "lumi:anon:open"
CID_BDAY_OPEN = "lumi:bday:open"
CID_QUIZ = "lumi:quiz:"

# Ключевые слова → авто-action (AI часто не передаёт action)
OPEN_KEYWORDS = (
    "открыть", "тикет", "ticket", "поддерж", "support", "вопрос", "админ",
    "обращ", "написать", "создать", "помощ", "help", "contact", "связ",
)
CLOSE_KEYWORDS = ("закрыть", "close", "закрыт")
VERIFY_KEYWORDS = ("вериф", "подтверд", "verify", "confirm", "доступ")
STUB_KEYWORDS = ("заглушка", "placeholder", "stub", "todo", "fixme")


def _find_text_channel(guild: discord.Guild, name: str):
    needle = name.replace("#", "").strip().lower()
    for ch in guild.text_channels:
        if needle in ch.name.lower() or ch.name.lower() in needle:
            return ch
    return None


def _find_role(guild: discord.Guild, name: str):
    if name.lower() in ("everyone", "@everyone"):
        return guild.default_role
    return discord.utils.get(guild.roles, name=name)


def _parse_color(hex_str: str | None) -> discord.Color:
    if not hex_str:
        return discord.Color.default()
    return discord.Color(int(hex_str.lstrip("#"), 16))


def init_components(bot: discord.Client):
    global _bot
    _bot = bot
    # Все кнопки обрабатываются через handle_interaction (работает после перезапуска)


def _parse_style(style: str) -> discord.ButtonStyle:
    return {
        "primary": discord.ButtonStyle.primary,
        "secondary": discord.ButtonStyle.secondary,
        "success": discord.ButtonStyle.success,
        "danger": discord.ButtonStyle.danger,
        "link": discord.ButtonStyle.link,
        "blurple": discord.ButtonStyle.primary,
        "grey": discord.ButtonStyle.secondary,
        "gray": discord.ButtonStyle.secondary,
        "green": discord.ButtonStyle.success,
        "red": discord.ButtonStyle.danger,
    }.get((style or "primary").lower(), discord.ButtonStyle.primary)


def _label_matches(label: str, keywords: tuple) -> bool:
    low = (label or "").lower()
    return any(k in low for k in keywords)


def _normalize_button(btn: dict) -> dict:
    """Определяет action по label, если AI не указал или поставил заглушку."""
    b = dict(btn)
    label = b.get("label") or ""
    action = (b.get("action") or "").lower().strip()

    if action in ("", "none", "placeholder", "stub", "заглушка", "button", "click"):
        action = ""

    if not action and b.get("url"):
        action = "link"
    if not action and _label_matches(label, CLOSE_KEYWORDS):
        action = "ticket_close"
    if not action and _label_matches(label, VERIFY_KEYWORDS):
        action = "verify"
    if not action and _label_matches(label, OPEN_KEYWORDS):
        action = "ticket_open"

    b["action"] = action
    return b


def _prepare_buttons(buttons: list) -> list:
    """Убирает заглушки, нормализует action, оставляет одну кнопку «открыть тикет»."""
    normalized = [_normalize_button(b) for b in (buttons or [])]

    cleaned = []
    for b in normalized:
        label = (b.get("label") or "").lower()
        if _label_matches(label, STUB_KEYWORDS) and not b.get("url") and b.get("action") not in (
            "ticket_open", "ticket_close", "verify", "self_role"
        ):
            continue
        cleaned.append(b)

    if not cleaned:
        cleaned = [{"label": "🎫 Открыть тикет", "style": "primary", "emoji": "🎫", "action": "ticket_open"}]

    ticket_opens = [b for b in cleaned if b.get("action") == "ticket_open"]
    if len(ticket_opens) > 1:
        best = ticket_opens[0]
        for b in ticket_opens:
            if _label_matches(b.get("label", ""), ("открыть", "open", "создать")):
                best = b
                break
        cleaned = [b for b in cleaned if b.get("action") != "ticket_open"]
        cleaned.insert(0, best)

    return cleaned[:25]


async def ensure_ticket_config(
    guild: discord.Guild,
    category_name: str = "🎫 TICKETS",
    support_role_name: str = None,
) -> dict:
    cfg = db.get_ticket_config(guild.id)
    if cfg and cfg.get("category_id") and guild.get_channel(cfg["category_id"]):
        return cfg

    category = discord.utils.get(guild.categories, name=category_name)
    if not category:
        category = await guild.create_category(category_name)

    return db.save_ticket_config(
        guild.id,
        category_id=category.id,
        support_role_name=support_role_name or (cfg or {}).get("support_role_name"),
    )


def build_embed(
    title: str,
    description: str,
    color_hex: str = "#5865F2",
    fields: list = None,
    image_url: str = None,
    thumbnail_url: str = None,
    footer: str = "Луми 🌟",
    author_name: str = None,
) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=_parse_color(color_hex))
    for f in fields or []:
        embed.add_field(
            name=f.get("name", "—"),
            value=f.get("value", "—"),
            inline=f.get("inline", False),
        )
    if image_url:
        embed.set_image(url=image_url)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if author_name:
        embed.set_author(name=author_name)
    if footer:
        embed.set_footer(text=footer)
    return embed


def _action_custom_id(action: str, guild_id: int, index: int) -> str:
    """Уникальный custom_id для каждой кнопки на сообщении."""
    if action == "ticket_open" and index == 0:
        return CID_TICKET_OPEN
    if action == "ticket_close" and index == 0:
        return CID_TICKET_CLOSE
    return f"lumi:act:{action}:{guild_id}:{index}"


def build_buttons_view(buttons: list, guild_id: int = None) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    prepared = _prepare_buttons(buttons)

    for i, btn in enumerate(prepared):
        label = (btn.get("label") or f"Кнопка {i + 1}")[:80]
        style = _parse_style(btn.get("style", "primary"))
        emoji = btn.get("emoji")
        url = btn.get("url")
        action = (btn.get("action") or "").lower()

        if url or action == "link":
            if url:
                view.add_item(
                    discord.ui.Button(label=label, style=discord.ButtonStyle.link, url=url, emoji=emoji)
                )
            continue

        guild = _bot.get_guild(guild_id) if _bot and guild_id else None

        if action == "self_role" and btn.get("role_name") and guild:
            role = _find_role(guild, btn["role_name"])
            custom_id = f"{CID_SELF_ROLE_PREFIX}{role.id if role else btn['role_name']}"
        elif action == "verify" and btn.get("role_name") and guild:
            role = _find_role(guild, btn["role_name"])
            custom_id = f"lumi:verify:{role.id if role else 0}"
        elif action in ("ticket_open", "ticket_close", "verify", "self_role"):
            custom_id = _action_custom_id(action, guild_id or 0, i)
        else:
            custom_id = f"lumi:panel:{guild_id or 0}:{i}"

        view.add_item(
            discord.ui.Button(
                label=label,
                style=style if style != discord.ButtonStyle.link else discord.ButtonStyle.primary,
                emoji=emoji,
                custom_id=custom_id,
            )
        )
    return view


def build_select_view(options: list, placeholder: str = "Выберите...", custom_id: str = "lumi:select:selfrole") -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    select = discord.ui.Select(
        placeholder=placeholder[:100],
        custom_id=custom_id,
        options=[
            discord.SelectOption(
                label=(o.get("label") or "—")[:100],
                value=str(o.get("value") or o.get("role_id") or o.get("role_name") or i),
                description=(o.get("description") or "")[:100] or None,
                emoji=o.get("emoji"),
            )
            for i, o in enumerate(options[:25])
        ],
    )
    view.add_item(select)
    return view


# ── Тикет: открытие / закрытие ─────────────────────────────────────────────

async def open_ticket_for_user(interaction: discord.Interaction, ticket_type: str = "general"):
    guild = interaction.guild
    member = interaction.user

    await ensure_ticket_config(guild)
    cfg = db.get_ticket_config(guild.id)

    existing = db.get_user_open_ticket(guild.id, member.id)
    if existing:
        ch = guild.get_channel(existing["channel_id"])
        if ch:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"⚠️ У тебя уже есть тикет: {ch.mention}", ephemeral=True
                )
            else:
                await interaction.followup.send(f"⚠️ У тебя уже есть тикет: {ch.mention}", ephemeral=True)
            return
        db.remove_open_ticket(guild.id, user_id=member.id)

    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    num = db.next_ticket_number(guild.id)
    category = guild.get_channel(cfg["category_id"])
    if not category:
        category = await guild.create_category("🎫 TICKETS")
        db.save_ticket_config(guild.id, category_id=category.id)

    prefix = ticket_type[:8] if ticket_type != "general" else ""
    base_name = f"ticket-{num:04d}-{member.name}"
    if prefix:
        base_name = f"{prefix}-{base_name}"
    ticket_name = base_name[:100].lower().replace(" ", "-")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, attach_files=True, read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }
    support_role_name = cfg.get("support_role_name")
    if support_role_name:
        role = _find_role(guild, support_role_name)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            )

    channel = await guild.create_text_channel(
        name=ticket_name,
        category=category,
        overwrites=overwrites,
        topic=f"Тикет #{num} | {member.display_name} ({member.id})",
    )
    db.add_open_ticket(guild.id, channel.id, member.id)

    welcome = cfg.get("welcome_message") or (
        f"Здравствуй, {member.mention}! 🎫\n"
        f"**Тикет #{num}** создан.\n"
        "Опиши проблему — поддержка скоро ответит.\n"
        "Нажми **Закрыть тикет** когда вопрос решён."
    )
    embed = build_embed(
        title=f"🎫 Тикет #{num}",
        description=welcome,
        color_hex=cfg.get("embed_color", "#5865F2"),
        footer="Луми Ticket System",
    )
    await channel.send(content=member.mention, embed=embed, view=TicketCloseView())

    if support_role_name:
        role = _find_role(guild, support_role_name)
        if role:
            await channel.send(f"{role.mention} — новый тикет!", delete_after=30)

    await interaction.followup.send(f"✅ Тикет создан: {channel.mention}", ephemeral=True)


async def close_ticket_channel(interaction: discord.Interaction):
    channel = interaction.channel
    guild = interaction.guild
    ticket = db.get_ticket_by_channel(guild.id, channel.id)

    if not ticket and not (isinstance(channel, discord.TextChannel) and "ticket" in channel.name.lower()):
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Это не тикет-канал.", ephemeral=True)
        return

    if not interaction.response.is_done():
        await interaction.response.defer()
    db.remove_open_ticket(guild.id, channel_id=channel.id)
    await channel.send("🔒 Тикет закрывается...")
    await channel.delete(reason=f"Тикет закрыт {interaction.user}")


class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Открыть тикет", style=discord.ButtonStyle.primary, custom_id=CID_TICKET_OPEN, emoji="🎫")
    async def ticket_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket_for_user(interaction)


class TicketOpenViewCustom(discord.ui.View):
    def __init__(self, label: str, emoji: str = "🎫"):
        super().__init__(timeout=None)
        btn = discord.ui.Button(
            label=label[:80], style=discord.ButtonStyle.primary, custom_id=CID_TICKET_OPEN, emoji=emoji
        )
        btn.callback = self._callback
        self.add_item(btn)

    async def _callback(self, interaction: discord.Interaction):
        await open_ticket_for_user(interaction)


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.danger, custom_id=CID_TICKET_CLOSE, emoji="🔒")
    async def ticket_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await close_ticket_channel(interaction)


class SelfRoleViewCustom(discord.ui.View):
    def __init__(self, options: list):
        super().__init__(timeout=None)
        select = discord.ui.Select(
            placeholder="🎭 Выбери роль...",
            custom_id="lumi:select:selfrole",
            options=[
                discord.SelectOption(
                    label=(o.get("label") or o.get("role_name", "—"))[:100],
                    value=str(o.get("role_id") or o.get("value", i)),
                    description=(o.get("description") or "")[:100] or None,
                    emoji=o.get("emoji"),
                )
                for i, o in enumerate(options[:25])
            ],
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        select = self.children[0]
        role_id = select.values[0]
        role = interaction.guild.get_role(int(role_id)) if role_id.isdigit() else None
        if not role:
            await interaction.response.send_message("❌ Роль не найдена.", ephemeral=True)
            return
        member = interaction.user
        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"✅ Роль **{role.name}** снята.", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"✅ Роль **{role.name}** выдана!", ephemeral=True)


async def _run_button_action(interaction: discord.Interaction, action: str, btn_data: dict = None):
    action = (action or "").lower()
    if action == "ticket_open":
        ticket_type = (btn_data or {}).get("ticket_type", "general")
        await open_ticket_for_user(interaction, ticket_type=ticket_type)
    elif action == "ticket_close":
        await close_ticket_channel(interaction)
    elif action == "verify":
        role_name = (btn_data or {}).get("role_name")
        role = _find_role(interaction.guild, role_name) if role_name else None
        if not role and btn_data and btn_data.get("role_id"):
            role = interaction.guild.get_role(int(btn_data["role_id"]))
        if not role:
            await interaction.response.send_message("❌ Роль не найдена.", ephemeral=True)
            return
        if role in interaction.user.roles:
            await interaction.response.send_message("✅ Ты уже верифицирован!", ephemeral=True)
            return
        await interaction.user.add_roles(role, reason="Verification")
        await interaction.response.send_message("🎉 Доступ открыт!", ephemeral=True)
    elif action == "self_role":
        role_name = (btn_data or {}).get("role_name")
        role = _find_role(interaction.guild, role_name) if role_name else None
        if not role:
            await interaction.response.send_message("❌ Роль не найдена.", ephemeral=True)
            return
        member = interaction.user
        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"✅ Роль **{role.name}** снята.", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"✅ Роль **{role.name}** выдана!", ephemeral=True)
    else:
        await interaction.response.send_message(
            "⚠️ Кнопка без действия. Используй `setup_ticket_panel` для тикетов.", ephemeral=True
        )


async def handle_interaction(interaction: discord.Interaction) -> bool:
    if interaction.type != discord.InteractionType.component:
        if interaction.type == discord.InteractionType.modal_submit:
            return await _handle_modal_submit(interaction)
        return False

    cid = interaction.data.get("custom_id", "")

    # ── Голосования ──
    if cid.startswith(CID_POLL_VOTE):
        try:
            idx = int(cid.split(":")[4]) if len(cid.split(":")) >= 5 else int(cid.split(":")[3])
        except ValueError:
            return True
        msg_id = interaction.message.id if interaction.message else 0
        poll = db.get_poll(interaction.guild.id, msg_id)
        if not poll or poll.get("ended"):
            await interaction.response.send_message("⛔ Голосование завершено или не найдено.", ephemeral=True)
            return True
        votes = poll["votes"]
        if str(idx) in votes:
            db.vote_poll(interaction.guild.id, msg_id, idx)
            await interaction.response.send_message(
                f"✅ Голос учтён: **{poll['options'][idx]}**", ephemeral=True
            )
            try:
                import discord_tools as _dt
                await _dt.unlock_achievement(interaction.guild, interaction.user.id, "poll_vote", channel=None)
            except Exception:
                pass
            fresh = db.get_poll(interaction.guild.id, msg_id)
            await _refresh_poll_message(interaction.guild, msg_id, fresh["votes"] if fresh else votes)
        else:
            await interaction.response.send_message("❌ Неверный вариант.", ephemeral=True)
        return True

    # ── Итоги голосования ──
    if cid.startswith(CID_POLL_RESULTS):
        msg_id = interaction.message.id if interaction.message else 0
        poll = db.get_poll(interaction.guild.id, msg_id)
        if not poll:
            await interaction.response.send_message("❌ Голосование не найдено.", ephemeral=True)
            return True
        lines = []
        total = sum(poll["votes"].values()) or 1
        for i, opt in enumerate(poll["options"]):
            cnt = poll["votes"].get(str(i), 0)
            pct = round(cnt * 100 / total)
            lines.append(f"**{opt}** — {cnt} ({pct}%)")
        text = f"📊 **{poll['title']}**\nВсего голосов: {sum(poll['votes'].values())}\n" + "\n".join(lines)
        await interaction.response.send_message(text, ephemeral=True)
        return True

    # ── Анонимный вопрос ──
    if cid == CID_ANON_OPEN:
        await interaction.response.send_modal(AnonymousModal())
        return True

    # ── День рождения ──
    if cid == CID_BDAY_OPEN:
        await interaction.response.send_modal(BirthdayModal())
        return True

    # ── Викторина ──
    if cid.startswith(CID_QUIZ):
        picked = None
        values = interaction.data.get("values") or []
        if values and str(values[0]).isdigit():
            picked = int(values[0])
        question = await services.trivia_question()
        if not question:
            await interaction.response.send_message("❌ Вопрос не получен (сервис недоступен).", ephemeral=True)
            return True
        if picked is not None and picked == question["correct_index"]:
            await interaction.response.send_message("✅ Правильно!", ephemeral=True)
        elif picked is not None:
            await interaction.response.send_message(
                f"❌ Неверно. Правильный ответ: **{question['options'][question['correct_index']]}**",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message("❌ Ответ не распознан.", ephemeral=True)
        try:
            import discord_tools as _dt
            await _dt.unlock_achievement(interaction.guild, interaction.user.id, "quiz_ok", channel=None)
        except Exception:
            pass
        return True

    # ── Кнопки музыкального плеера ──
    if cid.startswith("lumi:player:"):
        action = cid.split(":")[2]
        try:
            import music
            player = music.get_player(interaction.guild.id, _bot)
            if action == "skip":
                out = await player.skip()
            elif action == "pause":
                out = player.toggle_pause()
            elif action == "prev":
                out = await player.prev()
            elif action == "stop":
                out = await player.stop()
            elif action == "repeat":
                player.repeat = not player.repeat
                out = f"🔁 Повтор очереди: **{'включён' if player.repeat else 'выключен'}**."
            elif action == "leave":
                out = await player.leave()
            elif action == "volup":
                out = player.set_volume(min(100, int(player.volume * 100) + 10))
            elif action == "voldown":
                out = player.set_volume(max(5, int(player.volume * 100) - 10))
            else:
                out = None
            await interaction.response.send_message(out or "🎵", ephemeral=True)
        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
        return True

    # ── Тикеты (все форматы custom_id) ──
    if cid == CID_TICKET_OPEN or cid.startswith("lumi:act:ticket_open:"):
        await open_ticket_for_user(interaction)
        return True
    if cid == CID_TICKET_CLOSE or cid.startswith("lumi:act:ticket_close:"):
        await close_ticket_channel(interaction)
        return True

    # ── Верификация ──
    if cid.startswith("lumi:verify:"):
        try:
            role_id = int(cid.split(":")[-1])
        except ValueError:
            return False
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ Роль удалена.", ephemeral=True)
            return True
        if role in interaction.user.roles:
            await interaction.response.send_message("✅ Ты уже верифицирован!", ephemeral=True)
            return True
        await interaction.user.add_roles(role, reason="Verification")
        await interaction.response.send_message("🎉 Доступ открыт!", ephemeral=True)
        return True

    # ── Self-role кнопка ──
    if cid.startswith(CID_SELF_ROLE_PREFIX):
        raw = cid[len(CID_SELF_ROLE_PREFIX):]
        role = interaction.guild.get_role(int(raw)) if raw.isdigit() else _find_role(interaction.guild, raw)
        if not role:
            await interaction.response.send_message("❌ Роль не найдена.", ephemeral=True)
            return True
        member = interaction.user
        if role in member.roles:
            await member.remove_roles(role, reason="Self-role")
            await interaction.response.send_message(f"✅ Роль **{role.name}** снята.", ephemeral=True)
        else:
            await member.add_roles(role, reason="Self-role")
            await interaction.response.send_message(f"✅ Роль **{role.name}** выдана!", ephemeral=True)
        return True

    # ── Select self-role ──
    if cid == "lumi:select:selfrole":
        values = interaction.data.get("values", [])
        if not values:
            await interaction.response.send_message("❌ Ничего не выбрано.", ephemeral=True)
            return True
        val = values[0]
        role = interaction.guild.get_role(int(val)) if val.isdigit() else _find_role(interaction.guild, val)
        if not role:
            await interaction.response.send_message("❌ Роль не найдена.", ephemeral=True)
            return True
        member = interaction.user
        if role in member.roles:
            await member.remove_roles(role, reason="Self-role toggle")
            await interaction.response.send_message(f"✅ Роль **{role.name}** снята.", ephemeral=True)
        else:
            await member.add_roles(role, reason="Self-role")
            await interaction.response.send_message(f"✅ Роль **{role.name}** выдана!", ephemeral=True)
        return True

    # ── Кнопки из БД (lumi:panel:guild:index) ──
    if cid.startswith("lumi:panel:") and interaction.message:
        panel = db.get_panel_by_message(interaction.guild.id, interaction.message.id)
        if panel:
            try:
                idx = int(cid.split(":")[-1])
                buttons = panel["payload"].get("buttons", [])
                prepared = _prepare_buttons(buttons)
                if 0 <= idx < len(prepared):
                    await _run_button_action(interaction, prepared[idx].get("action"), prepared[idx])
                    return True
            except (ValueError, IndexError):
                pass
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "🎫 Нажми **Открыть тикет** на панели или попроси Луми: «настрой тикеты»", ephemeral=True
            )
        return True

    # ── lumi:act:action:guild:index ──
    if cid.startswith("lumi:act:"):
        parts = cid.split(":")
        if len(parts) >= 4:
            action = parts[2]
            btn_data = {}
            if interaction.message:
                panel = db.get_panel_by_message(interaction.guild.id, interaction.message.id)
                if panel:
                    try:
                        idx = int(parts[-1])
                        prepared = _prepare_buttons(panel["payload"].get("buttons", []))
                        if 0 <= idx < len(prepared):
                            btn_data = prepared[idx]
                    except (ValueError, IndexError):
                        pass
            await _run_button_action(interaction, action, btn_data)
            return True

    # ── Старый формат lumi:btn ──
    if cid.startswith("lumi:btn:") and interaction.message:
        panel = db.get_panel_by_message(interaction.guild.id, interaction.message.id)
        if panel:
            try:
                idx = int(cid.split(":")[3])
                prepared = _prepare_buttons(panel["payload"].get("buttons", []))
                if 0 <= idx < len(prepared):
                    await _run_button_action(interaction, prepared[idx].get("action"), prepared[idx])
                    return True
            except (ValueError, IndexError):
                pass
        await open_ticket_for_user(interaction)
        return True

    return False


# ── Инструменты для AI ─────────────────────────────────────────────────────

async def send_embed_with_buttons(
    guild: discord.Guild,
    channel_name: str,
    title: str,
    description: str,
    buttons: list,
    fields: list = None,
    color_hex: str = "#5865F2",
    image_url: str = None,
    thumbnail_url: str = None,
    footer: str = "Луми 🌟",
    support_role_name: str = None,
    category_name: str = "🎫 TICKETS",
) -> str:
    try:
        channel = _find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."

        prepared = _prepare_buttons(buttons)
        has_ticket = any(b.get("action") == "ticket_open" for b in prepared)
        if has_ticket:
            await ensure_ticket_config(guild, category_name, support_role_name)

        embed = build_embed(title, description, color_hex, fields, image_url, thumbnail_url, footer)
        view = build_buttons_view(prepared, guild.id)
        if not view.children:
            prepared = [{"label": "🎫 Открыть тикет", "style": "primary", "emoji": "🎫", "action": "ticket_open"}]
            await ensure_ticket_config(guild, category_name, support_role_name)
            view = build_buttons_view(prepared, guild.id)

        msg = await channel.send(embed=embed, view=view)
        db.save_component_panel(
            guild.id, channel.id, msg.id, "embed_buttons",
            {"title": title, "buttons": prepared},
        )
        actions = ", ".join(b.get("action") or "?" for b in prepared)
        return (
            f"✅ Embed с **{len(prepared)}** кнопками в `#{channel.name}`\n"
            f"Действия: `{actions}` — кнопки рабочие ✅"
        )
    except Exception as e:
        return f"❌ Ошибка embed+кнопки: {e}"


async def send_embed_with_select_menu(
    guild: discord.Guild,
    channel_name: str,
    title: str,
    description: str,
    options: list,
    placeholder: str = "Выберите...",
    fields: list = None,
    color_hex: str = "#5865F2",
) -> str:
    try:
        channel = _find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        embed = build_embed(title, description, color_hex, fields)
        resolved = []
        for i, o in enumerate(options):
            opt = dict(o)
            if opt.get("role_name") and not str(opt.get("value", "")).isdigit():
                role = _find_role(guild, opt["role_name"])
                if role:
                    opt["value"] = str(role.id)
                    opt["label"] = opt.get("label") or role.name
            if not opt.get("value"):
                opt["value"] = str(i)
            resolved.append(opt)
        view = build_select_view(resolved, placeholder)
        msg = await channel.send(embed=embed, view=view)
        db.save_component_panel(guild.id, channel.id, msg.id, "embed_select", {"options": resolved})
        return f"✅ Embed с select-меню ({len(resolved)} опций) в `#{channel.name}`"
    except Exception as e:
        return f"❌ Ошибка select: {e}"


async def setup_ticket_panel(
    guild: discord.Guild,
    channel_name: str,
    category_name: str = "🎫 TICKETS",
    support_role_name: str = None,
    title: str = "🎫 Служба поддержки",
    description: str = None,
    button_label: str = "Открыть тикет",
    button_emoji: str = "🎫",
    color_hex: str = "#5865F2",
    welcome_message: str = None,
    fields: list = None,
) -> str:
    try:
        channel = _find_text_channel(guild, channel_name)
        if not channel:
            return f"❌ Канал `{channel_name}` не найден."

        cfg = await ensure_ticket_config(guild, category_name, support_role_name)
        category = guild.get_channel(cfg["category_id"])

        default_desc = (
            "**Нужна помощь?** Нажми кнопку ниже!\n\n"
            "▸ Опиши проблему в тикете\n"
            "▸ Дождись ответа модерации\n"
            "▸ Закрой тикет когда всё решено\n\n"
            "⏱️ Среднее время ответа: ~15 мин"
        )
        embed = build_embed(
            title=title,
            description=description or default_desc,
            color_hex=color_hex,
            fields=fields,
            footer="Луми Ticket System",
        )

        buttons = [{"label": button_label, "style": "primary", "emoji": button_emoji or "🎫", "action": "ticket_open"}]
        view = build_buttons_view(buttons, guild.id)
        msg = await channel.send(embed=embed, view=view)

        db.save_ticket_config(
            guild.id,
            category_id=category.id,
            panel_channel_id=channel.id,
            support_role_name=support_role_name,
            embed_title=title,
            embed_description=description or default_desc,
            embed_color=color_hex,
            button_label=button_label,
            button_emoji=button_emoji,
            welcome_message=welcome_message,
        )
        db.save_component_panel(
            guild.id, channel.id, msg.id, "ticket_panel",
            {"category": category_name, "buttons": buttons},
        )

        return (
            f"✅ **Тикет-панель** в `#{channel.name}`!\n"
            f"📁 Категория: **{category.name}**\n"
            f"🛡️ Support: `{support_role_name or 'не задана'}`\n"
            f"Кнопка **{button_label}** → создаёт приватный канал ✅"
        )
    except Exception as e:
        return f"❌ Ошибка тикет-панели: {e}"


async def setup_self_role_panel(
    guild: discord.Guild,
    channel_name: str,
    title: str = "🎭 Выбор роли",
    description: str = "Выбери роль из меню ниже:",
    roles: list = None,
    color_hex: str = "#5865F2",
) -> str:
    try:
        channel = _find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        if not roles:
            return "❌ Укажи список roles."

        options = []
        for r in roles:
            role = _find_role(guild, r.get("role_name") or r.get("name", ""))
            if not role:
                continue
            options.append({
                "label": r.get("label") or role.name,
                "role_id": role.id,
                "description": r.get("description", ""),
                "emoji": r.get("emoji"),
            })
        if not options:
            return "❌ Ни одна роль не найдена на сервере."

        embed = build_embed(title, description, color_hex)
        view = SelfRoleViewCustom(options)
        msg = await channel.send(embed=embed, view=view)
        db.save_component_panel(guild.id, channel.id, msg.id, "self_role", {"roles": [o["label"] for o in options]})
        return f"✅ Self-role панель ({len(options)} ролей) в `#{channel.name}`"
    except Exception as e:
        return f"❌ Ошибка self-role: {e}"


async def send_verification_panel(
    guild: discord.Guild,
    channel_name: str,
    verified_role_name: str,
    title: str = "✅ Верификация",
    description: str = "Нажми кнопку чтобы получить доступ к серверу.",
    button_label: str = "Подтвердить",
    color_hex: str = "#57F287",
) -> str:
    try:
        channel = _find_text_channel(guild, channel_name)
        role = _find_role(guild, verified_role_name)
        if not channel:
            return "❌ Канал не найден."
        if not role or role.is_default():
            return f"❌ Роль `{verified_role_name}` не найдена."

        embed = build_embed(title, description, color_hex)
        buttons = [{
            "label": button_label,
            "style": "success",
            "emoji": "✅",
            "action": "verify",
            "role_name": verified_role_name,
        }]
        view = build_buttons_view(buttons, guild.id)
        msg = await channel.send(embed=embed, view=view)
        db.save_component_panel(
            guild.id, channel.id, msg.id, "verification",
            {"role_id": role.id, "buttons": buttons},
        )
        return f"✅ Панель верификации в `#{channel.name}` → роль **{role.name}**"
    except Exception as e:
        return f"❌ Ошибка верификации: {e}"


# ── Голосования ───────────────────────────────────────────────────────────

async def _refresh_poll_message(guild: discord.Guild, message_id: int, votes: dict):
    try:
        poll = db.get_poll(guild.id, message_id)
        if not poll:
            return
        channel = guild.get_channel(poll.get("channel_id") or 0)
        if not channel:
            return
        total = sum(poll["votes"].values()) or 1
        lines = [f"{opt}: **{poll['votes'].get(str(i), 0)}** голосов" for i, opt in enumerate(poll["options"])]
        embed = build_embed(
            title=f"📊 {poll['title']}",
            description="\n".join(lines) + f"\n\nВсего: **{sum(poll['votes'].values())}**",
            color_hex="#5865F2",
            footer="Луми Polls",
        )
        msg = await channel.fetch_message(message_id)
        await msg.edit(embed=embed)
    except (discord.NotFound, discord.HTTPException):
        pass


async def send_poll_panel(
    guild: discord.Guild,
    channel_name: str,
    title: str,
    options: list,
    color_hex: str = "#5865F2",
) -> str:
    try:
        channel = _find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        opts = [str(o)[:80] for o in (options or [])][:10]
        if len(opts) < 2:
            return "❌ Нужно минимум 2 варианта ответа."
        view = discord.ui.View(timeout=None)
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, opt in enumerate(opts):
            btn = discord.ui.Button(
                label=opt,
                style=discord.ButtonStyle.secondary,
                emoji=emojis[i],
                custom_id=f"{CID_POLL_VOTE}0:{i}",
            )
            view.add_item(btn)
        btn_right = discord.ui.Button(
            label="📊 Итоги", style=discord.ButtonStyle.primary, custom_id=f"{CID_POLL_RESULTS}0"
        )
        view.add_item(btn_right)
        embed = build_embed(
            title=f"📊 {title}", description="Нажми на вариант — голос учтётся!",
            color_hex=color_hex, footer="Луми Polls",
        )
        msg = await channel.send(embed=embed, view=view)
        db.save_poll(guild.id, msg.id, channel.id, title, opts)
        return f"✅ Голосование «{title}» создано в `#{channel.name}` ({len(opts)} вариантов)."
    except Exception as e:
        return f"❌ Ошибка голосования: {e}"


# ── Анонимные вопросы ─────────────────────────────────────────────────────

class AnonymousModal(discord.ui.Modal, title="Анонимный вопрос"):
    text = discord.ui.TextInput(
        label="Твой вопрос", style=discord.TextStyle.paragraph, max_length=900, required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.channel
        embed = build_embed(
            title="🔎 Анонимный вопрос",
            description=f"{self.text.value}",
            color_hex="#9B59B6",
            footer="Луми | Анонимно",
        )
        await channel.send(embed=embed)
        if not interaction.response.is_done():
            await interaction.response.send_message("✅ Вопрос отправлен анонимно.", ephemeral=True)


async def send_anonymous_panel(guild: discord.Guild, channel_name: str, title: str = None, description: str = None) -> str:
    try:
        channel = _find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        embed = build_embed(
            title=title or "🕵️ Анонимный вопрос",
            description=description or "Нужно спросить, но не палиться?\nНажми кнопку — вопрос уйдёт без твоего имени.",
            color_hex="#9B59B6",
            footer="Луми | Анонимно",
        )
        view = discord.ui.View(timeout=None)
        view.add_item(
            discord.ui.Button(label="🕵️ Задать вопрос", style=discord.ButtonStyle.secondary, custom_id=CID_ANON_OPEN)
        )
        await channel.send(embed=embed, view=view)
        return f"✅ Анонимная панель в `#{channel.name}`."
    except Exception as e:
        return f"❌ Ошибка анонимной панели: {e}"


# ── Дни рождения ──────────────────────────────────────────────────────────

class BirthdayModal(discord.ui.Modal, title="🎂 День рождения"):
    date = discord.ui.TextInput(
        label="Дата (ДД.ММ или ДД.ММ.ГГГГ)", placeholder="15.03", max_length=12, required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            parts = self.date.value.strip().split(".")
            if len(parts) < 2:
                raise ValueError
            day, month = int(parts[0]), int(parts[1])
            year = int(parts[2]) if len(parts) > 2 and parts[2] else None
            if not (1 <= day <= 31 and 1 <= month <= 12):
                raise ValueError
            db.register_birthday_db(
                interaction.guild.id, interaction.user.id, interaction.user.display_name, month, day, year
            )
            await interaction.response.send_message(
                f"🎂 Записано! День рождения: {day:02d}.{month:02d}" + (f".{year}" if year else ""),
                ephemeral=True,
            )
        except (ValueError, AttributeError):
            await interaction.response.send_message(
                "❌ Неверный формат. Нужно так: **15.03** (день.месяц).", ephemeral=True
            )


async def setup_birthday_panel(guild: discord.Guild, channel_name: str, title: str = None, description: str = None) -> str:
    try:
        channel = _find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        embed = build_embed(
            title=title or "🎂 Дни рождения клана",
            description=description or "Нажми кнопку и укажи свою дату рождения (например 15.03)\nЛуми поздравит тебя и всех, чей ДР сегодня.",
            color_hex="#F1C40F",
            footer="Луми Birthdays",
        )
        view = discord.ui.View(timeout=None)
        view.add_item(
            discord.ui.Button(label="🎂 Отметить мой ДР", style=discord.ButtonStyle.secondary, custom_id=CID_BDAY_OPEN)
        )
        await channel.send(embed=embed, view=view)
        return f"✅ Панель дней рождения в `#{channel.name}`."
    except Exception as e:
        return f"❌ Ошибка панели ДР: {e}"


# ── Викторина ─────────────────────────────────────────────────────────────

async def send_quiz_panel(guild: discord.Guild, channel_name: str, topic: str = None) -> str:
    try:
        channel = _find_text_channel(guild, channel_name)
        if not channel:
            return "❌ Канал не найден."
        question = await services.trivia_question(topic)
        if not question:
            return "❌ Не удалось получить вопрос (вопросы недоступны)."
        emojis = ["🇦", "🇧", "🇨", "🇩"]
        view = discord.ui.View(timeout=None)
        select = discord.ui.Select(
            placeholder="Выбери ответ...", custom_id=f"{CID_QUIZ}0",
            options=[
                discord.SelectOption(label=q[:90], value=str(i), emoji=emojis[i])
                for i, q in enumerate(question["options"])
            ],
        )
        view.add_item(select)
        embed = build_embed(
            title=f"🧠 Викторина: {question['category']}",
            description=question["question"],
            color_hex="#2ECC71",
            footer="Луми Quiz | Сложность: " + question["difficulty"].lower(),
        )
        await channel.send(embed=embed, view=view)
        return f"✅ Викторина в `#{channel.name}`."
    except Exception as e:
        return f"❌ Ошибка викторины: {e}"


# ── Обработчик модалок ────────────────────────────────────────────────────

def _modal_values(interaction: discord.Interaction) -> list:
    vals = []
    for comp in interaction.data.get("components", []) or []:
        for sub in comp.get("components", []) or []:
            v = sub.get("value")
            if v is not None:
                vals.append(str(v))
    return vals


async def _handle_modal_submit(interaction: discord.Interaction) -> bool:
    try:
        cid = interaction.data.get("custom_id", "")
        vals = _modal_values(interaction)
        if cid == CID_ANON_OPEN:
            if not vals:
                return False
            embed = build_embed(
                title="🔎 Анонимный вопрос",
                description=vals[0],
                color_hex="#9B59B6",
                footer="Луми | Анонимно",
            )
            await interaction.channel.send(embed=embed)
            if not interaction.response.is_done():
                await interaction.response.send_message("✅ Вопрос отправлен анонимно.", ephemeral=True)
            return True
        if cid == CID_BDAY_OPEN:
            if not vals:
                return False
            try:
                parts = vals[0].strip().split(".")
                if len(parts) < 2:
                    raise ValueError
                day, month = int(parts[0]), int(parts[1])
                year = int(parts[2]) if len(parts) > 2 and parts[2] else None
                if not (1 <= day <= 31 and 1 <= month <= 12):
                    raise ValueError
                db.register_birthday_db(
                    interaction.guild.id, interaction.user.id, interaction.user.display_name, month, day, year
                )
                await interaction.response.send_message(
                    f"🎂 Записано! День рождения: {day:02d}.{month:02d}" + (f".{year}" if year else ""),
                    ephemeral=True,
                )
            except (ValueError, AttributeError):
                await interaction.response.send_message(
                    "❌ Неверный формат. Нужно так: **15.03** (день.месяц).", ephemeral=True
                )
            return True
        return False
    except Exception:
        return False
