# Lumi — Discord-бот (PyQZone)
# Copyright (C) 2026 Антон Курченко Валейрович (Qcaps). Все права защищены.
# Лицензия: см. LICENSE. Распространение без разрешения правообладателя запрещено.
"""Музыкальный плеер Луми: очередь, громкость, повтор, авто-выход при бездействии."""

import asyncio
import re
import shutil
import time
from pathlib import Path

import discord

FFMPEG_PATH = str(Path(__file__).parent / "ffmpeg" / "bin" / "ffmpeg.exe")
if not Path(FFMPEG_PATH).exists():
    FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"

QUEUE_LIMIT = 50
IDLE_AUTO_LEAVE_SECONDS = 300  # 5 минут бездействия
CACHE_DIR = Path(__file__).parent / "music_cache"
CACHE_DIR.mkdir(exist_ok=True)


def _is_youtube(track: dict) -> bool:
    web = (track.get("webpage_url") or "").lower()
    return "youtube.com" in web or "youtu.be" in web or (track.get("extractor") or "").lower().startswith("youtube")


def download_local(track: dict) -> str | None:
    """Скачивает трек в локальный файл (для YouTube, где ffmpeg-стриминг блокируется 429)."""
    try:
        import yt_dlp
        path = CACHE_DIR / f"{track['id']}.m4a"
        if path.exists():
            return str(path)
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": str(path),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 15,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([track["webpage_url"]])

        if path.exists():
            return str(path)
    except Exception as e:
        print(f"[music] download failed: {type(e).__name__}: {e}", flush=True)
    return None


def search_track(query: str) -> dict | None:
    """Ищет первый трек по запросу/ссылке через yt-dlp. Возвращает dict или None."""
    try:
        import yt_dlp
    except ImportError:
        return None
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 10,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            search_query = query
            stripped = query.strip()
            lowered = stripped.lower()
            if re.match(r"^(https?://)", stripped, re.IGNORECASE):
                pass  # ссылка — yt-dlp сам определит платформу (SoundCloud/YouTube и др.)
            elif lowered.startswith("yt ") or lowered.startswith("ytsearch"):
                search_query = f"ytsearch1:{stripped[3:]}" if lowered.startswith("yt ") else stripped
            elif lowered.startswith("sc ") or "soundcloud" in lowered:
                search_query = f"scsearch1:{stripped.replace('soundcloud', '', 1).strip()}"
            else:
                search_query = f"scsearch1:{stripped}"  # поиск по названию — только SoundCloud
            info = ydl.extract_info(search_query, download=False)
            if not info:
                return None
            if info.get("_type") == "playlist":
                entries = info.get("entries") or []
                info = entries[0] if entries else None
            if not info:
                return None
            duration = info.get("duration") or 0
            if duration > 3 * 3600:
                return None
            return {
                "title": info.get("title") or "Без названия",
                "url": info.get("url") or "",
                "id": info.get("id") or f"t{int(time.time())}",
                "extractor": info.get("extractor") or "",
                "duration": duration,
                "webpage_url": info.get("webpage_url") or info.get("original_url") or "",
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader") or "",
                "headers": info.get("http_headers") or {},
            }
        except Exception:
            return None


def format_duration(seconds: int) -> str:
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class VolumeTransformer(discord.PCMVolumeTransformer):
    pass


class MusicPlayer:
    def __init__(self, guild_id: int, bot):
        self.guild_id = guild_id
        self.bot = bot
        self.queue: list[dict] = []
        self.current: dict | None = None
        self.volume = 0.9
        self.repeat = False
        self.voice_client: discord.VoiceClient | None = None
        self.last_activity = time.time()
        self._playing = False
        self.started_at = 0.0
        self.control_message = None

    @property
    def is_playing(self) -> bool:
        return self._playing

    async def join(self, channel: discord.VoiceChannel):
        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.channel.id != channel.id:
                await self.voice_client.move_to(channel)
            return
        self.voice_client = await channel.connect()

    async def add_track(self, track: dict) -> str:
        if len(self.queue) >= QUEUE_LIMIT:
            return f"❌ Очередь переполнена ({QUEUE_LIMIT} треков)."
        self.queue.append(track)
        if not self._playing:
            await self._play_next()
            return f"▶️ Играет: **{track['title']}** ({format_duration(track['duration'])})"
        return f"➕ В очередь ({len(self.queue)}/ {QUEUE_LIMIT}): **{track['title']}**"

    async def _play_next(self):
        if self.repeat and self.current:
            self.queue.insert(0, self.current)
        if not self.queue:
            self._playing = False
            self.current = None
            self.started_at = 0.0
            self.last_activity = time.time()
            return
        track = self.queue.pop(0)
        self.current = track
        self._playing = True
        self.last_activity = time.time()
        if not self.voice_client or not self.voice_client.is_connected():
            self._playing = False
            self.current = None
            return

        local_path = None
        source_args = {"executable": FFMPEG_PATH}
        if _is_youtube(track):
            local_path = await asyncio.to_thread(download_local, track)
            if not local_path:
                print("[music] no local file for YouTube track — skip", flush=True)
                self._playing = False
                self.current = None
                if self.voice_client and self.voice_client.is_playing():
                    self.voice_client.stop()
                await self._play_next()
                return
        else:
            before = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
            ua = (track.get("headers") or {}).get("User-Agent")
            if ua:
                before += f" -user_agent '{ua}'"
            source_args["before_options"] = before

        source = discord.FFmpegPCMAudio(local_path or track["url"], **source_args)
        if local_path:
            track["local"] = local_path
        player = VolumeTransformer(source, volume=self.volume)
        try:
            self.voice_client.play(player, after=lambda e: self._after_playback(e))
        except Exception as e:
            print(f"[music] play failed: {type(e).__name__}: {e}", flush=True)
            self.queue.insert(0, track)
            self.current = None
            self._playing = False
            return
        print(f"[music] playing: {track['title']}", flush=True)
        self.started_at = time.time()

    def _after_playback(self, error):
        self._playing = False
        if error:
            print(f"[music] playback error: {error}", flush=True)
        if self.current and self.current.get("local"):
            try:
                Path(self.current["local"]).unlink(missing_ok=True)
            except OSError:
                pass
        if error:
            self.current = None
        asyncio.run_coroutine_threadsafe(self._play_next(), self.bot.loop)

    def progress_seconds(self) -> int:
        if not self._playing or not self.current:
            return 0
        return int(time.time() - self.started_at)

    async def skip(self) -> str:
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
            await self._play_next()
            if self.current:
                return f"⏭️ Сейчас: **{self.current['title']}**"
            return "⏭️ Очередь пуста."
        return "❌ Ничего не играет."

    async def stop(self) -> str:
        self.queue.clear()
        self.current = None
        self.started_at = 0.0
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
        return "⏹ Остановлено, очередь очищена."

    def set_volume(self, percent: int) -> str:
        self.volume = max(0.05, min(1.0, percent / 100))
        if self.voice_client and self.voice_client.source:
            self.voice_client.source.volume = self.volume
        return f"🔊 Громкость: **{int(self.volume * 100)}%**"

    async def leave(self):
        self.queue.clear()
        self.current = None
        self.started_at = 0.0
        if self.voice_client:
            if self.voice_client.is_playing():
                self.voice_client.stop()
            await self.voice_client.disconnect(force=False)
        self.voice_client = None
        self._playing = False
        return "👋 Вышел из голосового канала."

    def queue_list(self) -> list[dict]:
        return list(self.queue)

    async def check_idle(self) -> bool:
        """Возвращает True, если плеер покинул канал из-за бездействия."""
        if self.voice_client and not self.voice_client.is_connected():
            self.voice_client = None
            self._playing = False
            return False
        if self.voice_client and not self._playing and time.time() - self.last_activity > IDLE_AUTO_LEAVE_SECONDS:
            await self.leave()
            return True
        return False


_players: dict[int, MusicPlayer] = {}


def get_player(guild_id: int, bot) -> MusicPlayer:
    if guild_id not in _players:
        _players[guild_id] = MusicPlayer(guild_id, bot)
    return _players[guild_id]


def prune_players() -> list[int]:
    """Удаляет плееры без голосового клиента. Возвращает список удалённых guild_id."""
    dead = [gid for gid, p in _players.items() if not p.voice_client]
    for gid in dead:
        _players.pop(gid, None)
    return dead