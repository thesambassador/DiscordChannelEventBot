import discord
from discord import app_commands
from discord import guild
from discord.embeds import Embed
from discord.ext.commands.context import Context
from discord.message import Message
from discord.threads import Thread
from GuildCalendar import CreateCalendarForGuild
from discord.ext import commands
from discord.ext.commands.core import command
from discord.ext import tasks
import traceback
import sys

class EventsCog(commands.Cog):
    def __init__(self, bot) :
        self.bot = bot
        self.GuildCalDict = {}
        

    async def cog_load(self):
        print("cog loaded, starting archive loop")
        self.ArchiveOld.start()

    @app_commands.command(name="samsam")
    async def samsam(self, interaction: discord.Interaction):
        await interaction.response.send_message(content="YOU WANT TO CREATE EVENT?", ephemeral=True)


    @app_commands.command(name="event")
    @app_commands.describe(title="Give a descriptive title to the event",
    date="Date in the format mm/dd, such as '6/10'",
    starttime="Time event starts, such as '6:30pm'",
    description="Full details about the event")
    async def event(self, interaction: discord.Interaction, title : str, date : str, starttime : str, description : str):
        await self.GuildCalDict[interaction.guild.id].HandleNewEventSlashCommand(interaction, title, date, starttime, description)
        #await interaction.response.send_message(f"EVENT: {title}, {date}", ephemeral=False, view=EventView())
    
    #for specifying some server-specific config stuff maybe for later
    @app_commands.command(name="setup")
    async def setup(self, interaction: discord.Interaction, eventmention : discord.Role):
        if(interaction.permissions.administrator):
            await self.GuildCalDict[interaction.guild.id].HandleSetupCommand(interaction, eventmention)

    #for when an option in the event responses drop down is selected
    async def on_drop_down_selected(self, interaction : discord.Interaction, selectedValue):
        await self.GuildCalDict[interaction.guild.id].HandleEventDropDownInteraction(interaction, selectedValue)

    async def on_edit_modal_submitted(self, interaction : discord.Interaction, title : str, date : str, starttime : str, description : str):
        await self.GuildCalDict[interaction.guild.id].HandleEditEventSubmit(interaction, title, date, starttime, description)

    async def on_delete_modal_submitted(self, interaction : discord.Interaction):
        await self.GuildCalDict[interaction.guild.id].HandleDeleteEventSubmit(interaction)

    #OLD EVENT COMMAND
    # async def event(self, ctx, *, arg):
    #     if(ctx.guild.id in self.GuildCalDict.keys()):
    #         print("new event command")
    #         await self.GuildCalDict[ctx.guild.id].HandleNewEventCommand(ctx, arg)
    #         print("done with new event")

    # @event.error
    # async def event_error(self, ctx, error):
    #     print("event command failed")

    @commands.command(pass_context = True)
    async def forcearchive(self, ctx : Context):
        if(ctx.guild.id in self.GuildCalDict.keys()):
            await self.GuildCalDict[ctx.guild.id].HandleArchiveOld()
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("Event bot connected, starting up...")

        for guild in self.bot.guilds:
            newCal = await CreateCalendarForGuild(guild)
            self.GuildCalDict[guild.id] = newCal
            print(f'Initialized guild {guild.name} with {len(newCal.EventsList)} events')

    #NO LONGER NECESSARY WITH THE SLASH COMMANDS VERSION
    # @commands.Cog.listener()
    # async def on_raw_message_delete(self, payload):
    #     #right now, doesn't seem to be a way to determine who deleted the message, so can't check to see if it was this bot
    #     if(payload.guild_id in self.GuildCalDict.keys()):
    #         #print("message deleted event")
    #         await self.GuildCalDict[payload.guild_id].HandleMessageDelete(payload)

    # @commands.Cog.listener()
    # async def on_raw_message_edit(self, payload):
    #     if(payload.guild_id in self.GuildCalDict.keys()):
    #         #print("message editted event")
    #         await self.GuildCalDict[payload.guild_id].HandleMessageEdit(payload)

    # @commands.Cog.listener()
    # async def on_raw_reaction_add(self, payload):
    #     if(payload.user_id == self.bot.user.id):
    #         return

    #     if(payload.guild_id in self.GuildCalDict.keys()):
    #         await self.GuildCalDict[payload.guild_id].HandleReactAdd(payload)
        
        #print(str(payload.emoji))
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # All other Errors not returned come here. And we can just print the default TraceBack.
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    #NO LONGER NECESSARY WITH THE SLASH COMMANDS VERSION
    # @commands.Cog.listener()
    # async def on_thread_join(self, thread:Thread):
    #     if(thread.guild.id in self.GuildCalDict.keys()):
    #         await self.GuildCalDict[thread.guild.id].HandleThreadJoined(thread)

    # @commands.Cog.listener()
    # async def on_thread_delete(self, thread:Thread):
    #     if(thread.guild.id in self.GuildCalDict.keys()):
    #         await self.GuildCalDict[thread.guild.id].HandleThreadDeleted(thread)

    # @commands.Cog.listener()
    # async def on_thread_update(self, before:Thread, after:Thread):
    #     if(before.guild.id in self.GuildCalDict.keys()):
    #         await self.GuildCalDict[before.guild.id].HandleThreadUpdated(before, after)

    # @commands.Cog.listener()
    # async def on_message(self, message:Message):
    #     await self.GuildCalDict[message.guild.id].HandleNewMessage(message)

    @tasks.loop(minutes=30)
    async def ArchiveOld(self):
        for guildID, guildCal in self.GuildCalDict.items():
            await guildCal.HandleArchiveOld()


    @ArchiveOld.before_loop
    async def BeforeArchiveOld(self):
        await self.bot.wait_until_ready()

    

async def setup(bot):
    await bot.add_cog(EventsCog(bot))

    