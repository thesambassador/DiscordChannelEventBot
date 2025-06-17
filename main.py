import os

import discord
import asyncio
from dotenv import load_dotenv

from discord.ext import commands
from EventBotViews import EventViewActive

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
SERVER = os.getenv('DISCORD_SERVER')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class EventClient(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self) -> None:
        self.add_view(EventViewActive())
        await self.load_extension("cogs.EventsCog")
        #synced = await self.tree.sync()
        #print(f"synced {len(synced)} commands")
        

bot = EventClient()
discord.utils.setup_logging()
   

async def main():
    async with bot:
        await bot.start(TOKEN)


asyncio.run(main())