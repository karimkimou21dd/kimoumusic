import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
from threading import Thread
from flask import Flask
from discord.ui import Button, View

# Initialize Flask server for UptimeRobot
app = Flask(__name__)

@app.route('/')
def home():
    return "Discord Music Bot is Online!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# YouTube DL configuration
ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'noplaylist': True,
    'extract_flat': True,
    'socket_timeout': 15,
    'nocheckcertificate': True,
    'retries': 3,
    'no_check_certificate': True
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
    'options': '-vn -threads 4 -bufsize 512k'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# Queue system
queue = []
now_playing = None
queue_lock = asyncio.Lock()
control_message = None  # Store the control panel message

class Song:
    def __init__(self, data, url, requester):
        self.title = data.get('title', 'Unknown Title')
        self.duration = data.get('duration', 0)
        self.url = url
        self.requester = requester
        self.thumbnail = data.get('thumbnail', 'https://i.imgur.com/4M34hi2.png')

    def formatted_duration(self):
        if self.duration:
            minutes, seconds = divmod(self.duration, 60)
            return f"{int(minutes)}:{int(seconds):02d}"
        return "Live"

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.song = Song(data, data.get('url'), data.get('requester'))

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True, requester=None):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            if 'entries' in data:
                data = data['entries'][0]
            data['requester'] = requester
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
        except Exception as e:
            print(f"Error creating audio source: {e}")
            return None

# Control panel view with buttons
class ControlView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)  # Persistent view
        self.ctx = ctx
        self.is_paused = False

    async def update_control_message(self):
        global control_message, now_playing
        if not control_message:
            return

        if not now_playing:
            embed = discord.Embed(title="🎵 Music Player", description="No song is currently playing.", color=discord.Color.red())
            self.play_pause.disabled = True
            self.skip.disabled = True
            self.stop.disabled = True
            self.queue_button.disabled = True
        else:
            embed = discord.Embed(
                title="🎵 Music Player",
                description=f"**Now Playing**: [{now_playing.title}]({now_playing.url})\n"
                            f"**Duration**: {now_playing.formatted_duration()}\n"
                            f"**Requested by**: {now_playing.requester.mention}",
                color=discord.Color.blurple()
            )
            embed.set_thumbnail(url=now_playing.thumbnail)
            self.play_pause.disabled = False
            self.skip.disabled = False
            self.stop.disabled = False
            self.queue_button.disabled = False
            self.play_pause.label = "Resume" if self.is_paused else "Pause"
            self.play_pause.emoji = "▶️" if self.is_paused else "⏸️"

        try:
            await control_message.edit(embed=embed, view=self)
        except discord.HTTPException:
            control_message = None

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.primary, emoji="⏸️")
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.ctx.voice_client or (not self.ctx.voice_client.is_playing() and not self.ctx.voice_client.is_paused()):
            await interaction.response.send_message("❌ No song is playing or paused!", ephemeral=True)
            return

        global control_message
        if self.ctx.voice_client.is_paused():
            self.ctx.voice_client.resume()
            self.is_paused = False
            await interaction.response.send_message("▶️ Resumed the song!", ephemeral=True)
        else:
            self.ctx.voice_client.pause()
            self.is_paused = True
            await interaction.response.send_message("⏸️ Paused the song!", ephemeral=True)

        # Create a new control message to ensure it's the latest
        embed = discord.Embed(
            title="🎵 Music Player",
            description=f"**Now Playing**: [{now_playing.title}]({now_playing.url})\n"
                        f"**Duration**: {now_playing.formatted_duration()}\n"
                        f"**Requested by**: {now_playing.requester.mention}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=now_playing.thumbnail)
        new_view = ControlView(self.ctx)
        new_view.is_paused = self.is_paused
        # Update button state for the new view
        new_view.play_pause.label = "Resume" if new_view.is_paused else "Pause"
        new_view.play_pause.emoji = "▶️" if new_view.is_paused else "⏸️"
        new_view.play_pause.disabled = False
        new_view.skip.disabled = False
        new_view.stop.disabled = False
        new_view.queue_button.disabled = False

        try:
            if control_message:
                await control_message.delete()  # Delete the old control message
        except discord.HTTPException:
            pass
        control_message = await self.ctx.send(embed=embed, view=new_view)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.ctx.voice_client or not self.ctx.voice_client.is_playing():
            await interaction.response.send_message("❌ No song is playing!", ephemeral=True)
            return

        self.ctx.voice_client.stop()  # This triggers play_next via the after callback
        await interaction.response.send_message("⏭️ Skipped the song!", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.ctx.voice_client:
            await interaction.response.send_message("❌ Not connected to a voice channel!", ephemeral=True)
            return

        global control_message
        async with queue_lock:
            queue.clear()
        global now_playing
        now_playing = None
        self.ctx.voice_client.stop()
        await self.ctx.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Stopped and disconnected!", ephemeral=True)

        # Update control message to reflect stopped state
        embed = discord.Embed(title="🎵 Music Player", description="No song is currently playing.", color=discord.Color.red())
        new_view = ControlView(self.ctx)
        new_view.play_pause.disabled = True
        new_view.skip.disabled = True
        new_view.stop.disabled = True
        new_view.queue_button.disabled = True
        try:
            if control_message:
                await control_message.delete()  # Delete the old control message
        except discord.HTTPException:
            pass
        control_message = await self.ctx.send(embed=embed, view=new_view)

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, emoji="📜")
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with queue_lock:
            if not queue:
                await interaction.response.send_message("📜 The queue is empty!", ephemeral=True)
                return

            embed = discord.Embed(title="📜 Queue", color=discord.Color.blue())
            for i, song in enumerate(queue[:5], 1):
                embed.add_field(
                    name=f"#{(i)}: {song.title}",
                    value=f"Duration: {song.formatted_duration()} | Requested by: {song.requester.mention}",
                    inline=False
                )
            if len(queue) > 5:
                embed.set_footer(text=f"And {len(queue) - 5} more...")
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def play_next(ctx):
    global now_playing, control_message

    if not ctx.voice_client:
        return

    async with queue_lock:
        if not queue:
            now_playing = None
            # Update control message to reflect no song playing
            embed = discord.Embed(title="🎵 Music Player", description="No song is currently playing.", color=discord.Color.red())
            view = ControlView(ctx)
            view.play_pause.disabled = True
            view.skip.disabled = True
            view.stop.disabled = True
            view.queue_button.disabled = True
            try:
                if control_message:
                    await control_message.delete()  # Delete the old control message
            except discord.HTTPException:
                pass
            control_message = await ctx.send(embed=embed, view=view)
            return
        next_song = queue.pop(0)
        now_playing = next_song

    try:
        player = await YTDLSource.from_url(next_song.url, loop=bot.loop, requester=next_song.requester)
        if not player:
            raise Exception("Failed to create player")

        def after_playing(error):
            if error:
                print(f"Player error: {error}")
            coro = play_next(ctx)
            fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
            try:
                fut.result()
            except:
                pass

        ctx.voice_client.play(player, after=after_playing)

        # Create new control panel as the latest message
        embed = discord.Embed(
            title="🎵 Music Player",
            description=f"**Now Playing**: [{player.song.title}]({player.song.url})\n"
                        f"**Duration**: {player.song.formatted_duration()}\n"
                        f"**Requested by**: {player.song.requester.mention}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=player.song.thumbnail)
        view = ControlView(ctx)

        # Delete old control message if it exists
        try:
            if control_message:
                await control_message.delete()
        except discord.HTTPException:
            pass

        # Send new control message
        control_message = await ctx.send(embed=embed, view=view)

    except Exception as e:
        print(f"Error in play_next: {e}")
        await ctx.send("⚠️ Error playing song, skipping...")
        await play_next(ctx)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

@bot.command()
async def play(ctx, *, query):
    if not ctx.author.voice:
        return await ctx.send("❌ You need to be in a voice channel!")

    if ctx.voice_client is None:
        await ctx.author.voice.channel.connect()

    msg = await ctx.send("🔍 Searching...")

    try:
        if not query.startswith(('http://', 'https://')):
            query = f"ytsearch:{query}"

        data = await bot.loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        if not data or ('entries' in data and not data['entries']):
            return await msg.edit(content="❌ Couldn't find that song.")

        if 'entries' in data:
            data = data['entries'][0]

        song = Song(data, data.get('url'), ctx.author)

        async with queue_lock:
            queue.append(song)
            position = len(queue)

        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            embed = discord.Embed(
                title="📥 Added to Queue",
                description=f"[{song.title}]({song.url})",
                color=discord.Color.green()
            )
            embed.add_field(name="Position", value=f"#{position}")
            embed.add_field(name="Duration", value=song.formatted_duration())
            embed.add_field(name="Requested by", value=ctx.author.mention)
            embed.set_thumbnail(url=song.thumbnail)
            await msg.edit(content=None, embed=embed)
        else:
            await msg.edit(content="⏳ Preparing to play...")
            await play_next(ctx)

    except Exception as e:
        await msg.edit(content=f"❌ Error: {str(e)}")

# Start the Flask server and run the bot
keep_alive()
bot.run('MTM2Mjg4NDc4MzU4MzI2ODk5NQ.GF4tGi.YrnAFIkJsP3Iz7cUA9bRRg3O_QcdyhsbMPwbwg')  # Replace with your actual bot token
