import discord
import asyncio
import youtube_dl
import os
from discord.ext import commands

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

# YouTube DL options
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # Bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # Take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.now_playing = {}
        self.volume = {}

    def get_queue(self, ctx):
        """Get the server's song queue."""
        guild_id = ctx.guild.id
        if guild_id not in self.queue:
            self.queue[guild_id] = []
        return self.queue[guild_id]

    @commands.command(name='join', help='Joins a voice channel')
    async def join(self, ctx):
        """Join the user's voice channel."""
        if ctx.author.voice is None:
            await ctx.send("You are not connected to a voice channel.")
            return False

        channel = ctx.author.voice.channel
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        
        # Initialize server-specific settings if needed
        guild_id = ctx.guild.id
        if guild_id not in self.volume:
            self.volume[guild_id] = 0.5
            
        await ctx.send(f"Joined {channel.name}")
        return True

    @commands.command(name='play', help='Plays a song from YouTube')
    async def play(self, ctx, *, url):
        """Play a song from YouTube."""
        # Join the voice channel if not already in one
        if ctx.voice_client is None:
            if not await self.join(ctx):
                return

        async with ctx.typing():
            try:
                # Add song to queue
                queue = self.get_queue(ctx.guild.id)
                queue.append(url)
                
                await ctx.send(f"Added to queue: {url}")
                
                # If nothing is playing, start playing
                if not ctx.voice_client.is_playing() and len(queue) == 1:
                    await self.play_next(ctx)
            except Exception as e:
                await ctx.send(f"An error occurred: {str(e)}")

    async def play_next(self, ctx):
        """Play the next song in the queue."""
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        
        if not queue:
            return
            
        url = queue[0]
        
        try:
            async with ctx.typing():
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.song_finished(ctx), self.bot.loop))
                ctx.voice_client.source.volume = self.volume.get(guild_id, 0.5)
                
                self.now_playing[guild_id] = player
                await ctx.send(f"Now playing: {player.title}")
                
                # Remove the song from the queue
                queue.pop(0)
        except Exception as e:
            await ctx.send(f"Error playing song: {str(e)}")
            # Skip to next song
            queue.pop(0)
            await self.play_next(ctx)

    async def song_finished(self, ctx):
        """Called when a song finishes playing."""
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        
        if queue:
            await self.play_next(ctx)

    @commands.command(name='pause', help='Pauses the currently playing song')
    async def pause(self, ctx):
        """Pause the currently playing song."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Playback paused.")
        else:
            await ctx.send("Nothing is playing right now.")

    @commands.command(name='resume', help='Resumes the paused song')
    async def resume(self, ctx):
        """Resume the paused song."""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Playback resumed.")
        else:
            await ctx.send("The audio is not paused.")

    @commands.command(name='skip', help='Skips the current song')
    async def skip(self, ctx):
        """Skip the current song."""
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("Skipped the current song.")
            # The song_finished callback will automatically play the next song
        else:
            await ctx.send("Nothing is playing right now.")

    @commands.command(name='queue', help='Shows the current song queue')
    async def show_queue(self, ctx):
        """Show the current song queue."""
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        
        if not queue and guild_id not in self.now_playing:
            await ctx.send("The queue is empty.")
            return
            
        # Create an embed for the queue
        embed = discord.Embed(title="Music Queue", color=discord.Color.blue())
        
        # Add currently playing song
        if guild_id in self.now_playing and self.now_playing[guild_id]:
            embed.add_field(name="Now Playing", value=self.now_playing[guild_id].title, inline=False)
        
        # Add queued songs
        if queue:
            queue_text = ""
            for i, url in enumerate(queue, 1):
                queue_text += f"{i}. {url}\n"
            embed.add_field(name="Up Next", value=queue_text, inline=False)
        else:
            embed.add_field(name="Up Next", value="Nothing in queue", inline=False)
            
        await ctx.send(embed=embed)

    @commands.command(name='clear', help='Clears the song queue')
    async def clear(self, ctx):
        """Clear the song queue."""
        guild_id = ctx.guild.id
        if guild_id in self.queue:
            self.queue[guild_id] = []
            await ctx.send("Queue cleared.")
        else:
            await ctx.send("Queue is already empty.")

    @commands.command(name='leave', help='Disconnects the bot from voice')
    async def leave(self, ctx):
        """Leave the voice channel."""
        if ctx.voice_client:
            guild_id = ctx.guild.id
            
            # Clear queue and now playing
            if guild_id in self.queue:
                self.queue[guild_id] = []
            if guild_id in self.now_playing:
                self.now_playing[guild_id] = None
                
            await ctx.voice_client.disconnect()
            await ctx.send("Disconnected from voice channel.")
        else:
            await ctx.send("I'm not connected to a voice channel.")

    @commands.command(name='volume', help='Changes the player volume')
    async def volume(self, ctx, volume: int):
        """Change the player volume."""
        if ctx.voice_client is None:
            await ctx.send("Not connected to a voice channel.")
            return

        # Ensure volume is between 0 and 100
        volume = max(0, min(100, volume))
        
        # Store volume setting for this server
        guild_id = ctx.guild.id
        self.volume[guild_id] = volume / 100
        
        if ctx.voice_client.source:
            ctx.voice_client.source.volume = volume / 100

        await ctx.send(f"Volume set to {volume}%")

    @commands.command(name='now', help='Shows the currently playing song')
    async def now_playing_cmd(self, ctx):
        """Show the currently playing song."""
        guild_id = ctx.guild.id
        
        if guild_id in self.now_playing and self.now_playing[guild_id]:
            player = self.now_playing[guild_id]
            embed = discord.Embed(title="Now Playing", color=discord.Color.green())
            embed.add_field(name="Title", value=player.title, inline=False)
            embed.add_field(name="URL", value=player.url, inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Nothing is playing right now.")

    @play.before_invoke
    async def ensure_voice(self, ctx):
        """Ensure the bot is in a voice channel before playing music."""
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")

def setup(bot):
    bot.add_cog(Music(bot))
