import asyncio
import functools
import itertools
import math
import random
import re

import discord
import youtube_dl
from async_timeout import timeout
from discord.ext import commands

from exceptions import YTDLError, VoiceError
from misc.embed import video_embed, embed_msg
from misc.genius import GeniusSong

"""
VOICE MODULE
This module is the base to play music. 

The commands include:
  join    Joins a voice channel.
  leave   Clears the queue and leaves the voice channel.
  loop    Loops the currently playing song.
  now     Displays the currently playing song.
  pause   Pauses the currently playing song.
  play    Plays a song.
  queue   Shows the player's queue.
  remove  Removes a song from the queue at a given index.
  resume  Resumes a currently paused song.
  shuffle Shuffles the queue.
  skip    Vote to skip a song. The requester can automatically skip.
  stop    Stops playing song and clears the queue.
  summon  Summons the bot to a voice channel.
  volume  Sets the volume of the player.
"""


class YTDLSource(discord.PCMVolumeTransformer):
    # YTDL options used to stream
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self,
                 ctx: commands.Context,
                 source: discord.FFmpegPCMAudio,
                 *,
                 data: dict,
                 volume: float = 0.5):
        super().__init__(source, volume)  # Plays the source

        # Get context info
        self.requester = ctx.author
        self.channel = ctx.channel

        # Get all video info
        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        self.title = data.get('title')
        self.track = data.get('track')
        self.artist = data.get('artist')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.url = data.get('webpage_url')

        # Not shown in the response message. Can comment out.
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')

    def __str__(self):
        return f'**{self.title}** by **{self.uploader}**'

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        """
        Creates a source to play.
        :param ctx: the commands.Context
        :param search: the search query
        :param loop: ...
        :return: source
        """
        loop = loop or asyncio.get_event_loop()

        # Create partial function
        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)  # Execute loop

        # Raise error if there is no data
        if data is None:
            raise YTDLError(f"Couldn't find anything that matches `{search}`")

        if 'entries' in data:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            # Raise error if there is no process_info
            if process_info is None:
                raise YTDLError(f"Couldn't find anything that matches `{search}`")

        else:
            process_info = data

        # Get webpage url from the data
        webpage_url = process_info['webpage_url']
        # Create partial function to extract data from the youtube URL
        partial_data_extractor = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
        # Execute partial
        processed_info = await loop.run_in_executor(None, partial_data_extractor)

        if processed_info is None:
            raise YTDLError(f"Couldn't fetch `{webpage_url}`")

        if "entries" in processed_info:
            # Attempt to get an entry out of more entries
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError(f"Couldn\'t retrieve any matches for `{webpage_url}`")
        else:
            info = processed_info

        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

    @staticmethod
    def parse_duration(duration: int) -> str:
        """
        Return a string with the days, hours, minutes and seconds of a given duration in seconds
        :param duration: the duration in seconds
        :return: str
        """
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append(f"{days} days")
        if hours > 0:
            duration.append(f"{hours} hours")
        if minutes > 0:
            duration.append(f"{minutes} minutes")
        if seconds > 0:
            duration.append(f"{seconds} seconds")

        return ', '.join(duration)


class Song:
    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester


class SongQueue(asyncio.Queue):
    """
    Queue class. You can add and remove songs.
    """

    def __getitem__(self, item):
        """
        Get Item using:
        - Index. e.g: list[1]
        - Slice. e.g: list[1:5]
        """
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]


class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()

        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()

            if not self.loop:
                # Try to get the next song within 3 minutes.
                # If no song will be added to the queue in time,
                # the player will disconnect due to performance
                # reasons.
                try:
                    async with timeout(180):  # 3 minutes
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    return

            self.current.source.volume = self._volume
            self.voice.play(self.current.source, after=self.play_next_song)

            # Create custom embed message
            await self.current.source.channel.send(embed=video_embed(self.current))

            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None


class Music(commands.Cog):
    """
    Main class with the commands.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage("This command can't be used in DM channels.")

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send(str(error))

    @commands.command(name='join', invoke_without_subcommand=True)
    async def _join(self, ctx: commands.Context):
        """Joins a voice channel."""
        destination = ctx.author.voice.channel  # Destination is the author's voice channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='summon')
    @commands.has_permissions(manage_guild=True)
    async def _summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):
        """Summons the bot to a voice channel.
        If no channel was specified, it joins your channel.
        """
        if not channel and not ctx.author.voice:
            raise commands.CommandError('You are neither connected to a voice channel nor specified a channel to join.')
            # raise VoiceError()

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='leave', aliases=['disconnect'])
    @commands.has_permissions(manage_guild=True)
    async def _leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""

        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]

    @commands.command(name='volume')
    @commands.has_permissions(manage_guild=True)
    async def _volume(self, ctx: commands.Context, *, volume: int):
        """Sets the volume of the player."""

        # if not ctx.voice_state.is_playing:
        #     return await ctx.send('Nothing being played at the moment.')

        if 0 > volume > 100:
            return await ctx.send('Volume must be between 0 and 100.')

        ctx.voice_state.volume = volume / 100
        await ctx.send(f"Volume of the player set to {volume}%\nThe volume will be applied in the next song.")

    @commands.command(name='now', aliases=['current', 'playing'])
    async def _now(self, ctx: commands.Context):
        """Displays the currently playing song."""
        if not ctx.voice_state.is_playing:
            raise commands.CommandError('Nothing being played at the moment.')

        await ctx.send(embed=video_embed(ctx.voice_state.current))

    @commands.command(name='pause')
    async def _pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""
        try:
            if ctx.voice_state.voice.is_playing:
                ctx.voice_state.voice.pause()
                await ctx.message.add_reaction('⏯')

        except AttributeError:
            await ctx.send("Can't pause. No song is being played!")

    @commands.command(name='resume')
    async def _resume(self, ctx: commands.Context):
        """Resumes a currently paused song."""
        try:
            if ctx.voice_state.voice.is_paused:
                ctx.voice_state.voice.resume()
                await ctx.message.add_reaction('⏯')

            else:
                await ctx.send("No music paused!")

        except AttributeError:
            await ctx.send("Can't pause. No song is being played!")

    @commands.command(name='stop')
    async def _stop(self, ctx: commands.Context):
        """Stops playing song and clears the queue."""
        ctx.voice_state.songs.clear()

        if ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            return await ctx.send(embed=embed_msg(description="🛑 Stopped the music"))

        else:
            return await ctx.send('Cannot stop. Not playing any song right now.')

    @commands.command(name='skip')
    async def _skip(self, ctx: commands.Context):
        """Vote to skip a song. The requester can automatically skip.
        1 skip vote(s) are needed for the song to be skipped.
        """

        if not ctx.voice_state.is_playing:
            return await ctx.send('Cannot skip. Not playing any song right now.')

        voter = ctx.message.author
        if voter == ctx.voice_state.current.requester:
            await ctx.message.add_reaction('⏭')
            ctx.voice_state.skip()

        elif voter.id not in ctx.voice_state.skip_votes:
            ctx.voice_state.skip_votes.add(voter.id)
            total_votes = len(ctx.voice_state.skip_votes)

            if total_votes >= 1:
                await ctx.message.add_reaction('⏭')
                ctx.voice_state.skip()
            else:
                await ctx.send('Skip vote added, currently at **{}/1**'.format(total_votes))

        else:
            await ctx.send('You have already voted to skip this song.')

    @commands.command(name='queue')
    async def _queue(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('The queue is empty.')

        items_per_page = 1
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += f"`{i + 1}.` [**{song.source.title}**]({song.source.url})\n"

        embed = (discord.Embed(
            description=f"**{len(ctx.voice_state.songs)} tracks:**\n\n{queue}")
            .set_footer(
            text=f"Viewing page {page}/{pages}"))

        await ctx.send(embed=embed)

    @commands.command(name='shuffle')
    async def _shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Cannot shuffle because the queue is empty.')

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(name='remove')
    async def _remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Cannot remove song because the queue is empty.')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name='loop')
    async def _loop(self, ctx: commands.Context):
        """Loops the currently playing song.
        Invoke this command again to unloop the song.
        """

        if not ctx.voice_state.is_playing:
            raise commands.CommandError('Nothing being played at the moment.')

        # Inverse boolean value to loop and unloop.
        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.message.add_reaction('✅')

    @commands.command(name='play')
    async def _play(self, ctx: commands.Context, *, search: str):
        """Plays a song.
        If there are songs in the queue, this will be queued until the
        other songs finished playing.
        This command automatically searches from various sites if no URL is provided.
        A list of these sites can be found here: https://rg3.github.io/youtube-dl/supportedsites.html
        """

        if not ctx.voice_state.voice:
            await ctx.invoke(self._join)

        async with ctx.typing():
            try:
                source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                await ctx.send('An error occurred while processing this request: {}'.format(str(e)))
            else:
                song = Song(source)

                await ctx.voice_state.songs.put(song)
                await ctx.send('Enqueued {}'.format(str(source)))

    @commands.command(name='lyrics')
    async def _lyrics(self, ctx: commands.Context):
        """Get the lyrics of the current song."""
        if not ctx.voice_state.is_playing:
            raise commands.CommandError('Nothing being played at the moment.')

        # Get song name listed on youtube
        song_title = ctx.voice_state.current.source.track
        if not song_title:
            return await ctx.send("Couldn't find lyrics for this track!")

        song_title = re.sub("[(\[].*?[)\]]", "", song_title).strip()  # remove parenthesis from song title
        # Get artist name listed on youtube
        artist_name = ctx.voice_state.current.source.artist

        genius_song = GeniusSong(song_title, artist_name)
        res = genius_song.get_response()
        if res:
            hit = genius_song.filter_hit_by_artist(res)
            if not hit:  # Artist didn't match
                hit = res["response"]["hits"][0]  # Get first hit
                await ctx.send("Couldn't find similar artists. The lyrics might not be the expected")

            song_url = hit["result"]["url"]
            raw_lyrics = genius_song.get_lyrics(song_url)

            if raw_lyrics:
                # Generate embed
                fields = genius_song.split_lyrics(raw_lyrics)
                embed = embed_msg(
                    title=song_title.capitalize() + "\n{}".format(artist_name),
                    description="",
                    footer="Lyrics provided by Genius",
                    field_values=fields,
                    inline=False
                )
                return await ctx.send(embed=embed)

            else:
                return await ctx.send(
                    "**Error!**\nThere is a problem with Genius.\nTry again in a few minutes. "
                    "\nYou can also try the command `fastlyrics`")

        return await ctx.send("Lyrics couldn't be found.")

    @_join.before_invoke
    @_play.before_invoke
    @_volume.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to any voice channel.')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('Bot is already in a voice channel.')


def setup(bot):
    bot.add_cog(Music(bot))
