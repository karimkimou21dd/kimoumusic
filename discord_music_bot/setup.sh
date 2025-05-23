#!/bin/bash

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "ffmpeg is not installed. Installing now..."
    sudo apt-get update
    sudo apt-get install -y ffmpeg
else
    echo "ffmpeg is already installed."
fi

# Check if opus is installed
if ! pip3 list | grep -q "PyNaCl"; then
    echo "PyNaCl is not installed. Installing now..."
    pip3 install PyNaCl
else
    echo "PyNaCl is already installed."
fi

echo "All dependencies are installed. You can now run the bot with: python3 bot.py"
