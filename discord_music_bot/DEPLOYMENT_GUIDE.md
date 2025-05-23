# Discord Music Bot - Deployment and Usage Guide

## Prerequisites
- Python 3.8 or higher
- FFmpeg installed on your system
- Discord Bot Token (from Discord Developer Portal)

## Setup Instructions

### 1. Create a Discord Bot
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" tab and click "Add Bot"
4. Under the "TOKEN" section, click "Copy" to copy your bot token
5. Under "Privileged Gateway Intents", enable:
   - Message Content Intent
   - Server Members Intent
   - Voice States Intent
6. Save changes

### 2. Invite the Bot to Your Server
1. Go to the "OAuth2" tab in the Developer Portal
2. In the "URL Generator" section, select the following scopes:
   - bot
   - applications.commands
3. In the "Bot Permissions" section, select:
   - Send Messages
   - Connect
   - Speak
   - Use Voice Activity
   - Add Reactions
   - Embed Links
   - Attach Files
   - Read Message History
   - Use External Emojis
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

### 3. Set Up the Bot Environment
1. Clone or download the bot files to your server
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
   Or run the setup script:
   ```
   ./setup.sh
   ```
3. Create a `.env` file in the bot directory with the following content:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   PREFIX=!
   ```
   Replace `your_discord_bot_token_here` with the token you copied earlier

### 4. Run the Bot
```
python bot.py
```

## Hosting Options

### Option 1: Local Hosting
- Run the bot on your personal computer
- Requires your computer to be on whenever you want the bot to be active
- Good for testing and personal use

### Option 2: VPS Hosting (Recommended for 24/7 availability)
1. Rent a VPS from providers like DigitalOcean, AWS, or Linode
2. Set up the bot as described above
3. Use a process manager like PM2 to keep the bot running:
   ```
   npm install -g pm2
   pm2 start bot.py --name "discord-music-bot" --interpreter python3
   ```

### Option 3: Specialized Bot Hosting
- Services like Railway, Heroku, or Replit can host Discord bots
- Follow their specific deployment instructions

## Command Documentation

| Command | Description | Usage |
|---------|-------------|-------|
| `!join` | Joins your current voice channel | `!join` |
| `!play` | Plays a song from YouTube | `!play [YouTube URL or search term]` |
| `!pause` | Pauses the currently playing song | `!pause` |
| `!resume` | Resumes a paused song | `!resume` |
| `!skip` | Skips the current song | `!skip` |
| `!queue` | Shows the current song queue | `!queue` |
| `!clear` | Clears the song queue | `!clear` |
| `!volume` | Changes the player volume (0-100) | `!volume [0-100]` |
| `!now` | Shows the currently playing song | `!now` |
| `!leave` | Disconnects the bot from voice | `!leave` |
| `!ping` | Checks if the bot is responsive | `!ping` |
| `!help` | Shows the help message | `!help [command]` |

## Troubleshooting

### Bot doesn't join voice channel
- Ensure the bot has proper permissions
- Check if you're in a voice channel before using `!join` or `!play`

### No sound is playing
- Ensure FFmpeg is properly installed
- Check if the YouTube URL is valid
- Try using a different YouTube URL

### Bot disconnects frequently
- Check your internet connection
- Ensure your hosting provider has stable connectivity

### Error with YouTube playback
- YouTube-DL might need an update: `pip install --upgrade youtube-dl`

## Maintenance
- Periodically update dependencies with `pip install --upgrade -r requirements.txt`
- Check for updates to discord.py and youtube-dl libraries

## Support
If you encounter any issues, please check the error messages in the console output for troubleshooting.
