import os

import discord
from dotenv import load_dotenv

from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
SERVER = os.getenv('DISCORD_SERVER')

bot = commands.Bot(command_prefix='!')
bot.load_extension("cogs.EventsCog")
bot.run(TOKEN)
