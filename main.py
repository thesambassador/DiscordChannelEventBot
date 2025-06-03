import os

import discord
import asyncio
from dotenv import load_dotenv

from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
SERVER = os.getenv('DISCORD_SERVER')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
discord.utils.setup_logging()

async def main():
    async with bot:
        await bot.load_extension("cogs.EventsCog")
        await bot.start(TOKEN)

asyncio.run(main())