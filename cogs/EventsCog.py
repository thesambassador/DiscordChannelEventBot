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


    @commands.command(pass_context=True)
    async def event(self, ctx, *, arg):
        if(ctx.guild.id in self.GuildCalDict.keys()):
            print("new event command")
            await self.GuildCalDict[ctx.guild.id].HandleNewEventCommand(ctx, arg)
            print("done with new event")

    @commands.command(pass_context=True)
    async def samtest(self, ctx):
        testEmbed = Embed(title="asdf", description="asdf")
        testEmbed.add_field(name="field1", value="WOW LOOK AT ALL THIS TEXT, IT'S NEAT ISN'T IT? THAT IS INCREDIBLE")
        testEmbed.add_field(name="field2", value="2")
        testEmbed.add_field(name="field3", value="WOW LOOK AT ALL THIS TEXT, IT'S NEAT ISN'T IT? THAT IS INCREDIBLE")
        testEmbed.add_field(name="field4", value="4")

        await ctx.send(embed=testEmbed)

    # @event.error
    # async def event_error(self, ctx, error):
    #     print("event command failed")

    @commands.command(pass_context = True)
    async def forcearchive(self, ctx : Context):
        if(ctx.guild.id in self.GuildCalDict.keys()):
            await self.GuildCalDict[ctx.guild.id].HandleArchiveOld()
    
    @commands.command(pass_context = True)
    async def testembed(self, ctx : Context, *, arg):
        args = arg.split()
        if(len(args) == 2):
            resultEmbed = Embed(title=args[0], description=args[1])
            await ctx.send(embed=resultEmbed)
        elif(len(args) == 4):
            resultEmbed = Embed(title=args[0], description=args[1])
            resultEmbed.add_field(name=args[2], value=args[3])
            await ctx.send(embed=resultEmbed)

    # @commands.command(pass_context = True)
    # async def testdelete(self, ctx:Context, *, arg):
    #     if(ctx.guild.name == "SamTestBotServer"):
    #         args = arg.split()
    #         if(len(args) == 1):
    #             id = int(args[0])
    #             targetMessage = await ctx.channel.fetch_message(id)
    #             await targetMessage.delete()

        


    @commands.Cog.listener()
    async def on_ready(self):
        print("Event bot connected, starting up...")
        for guild in self.bot.guilds:
            newCal = await CreateCalendarForGuild(guild)
            self.GuildCalDict[guild.id] = newCal
            print(f'Initialized guild {guild.name} with {len(newCal.EventsList)} events')

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        #right now, doesn't seem to be a way to determine who deleted the message, so can't check to see if it was this bot
        if(payload.guild_id in self.GuildCalDict.keys()):
            #print("message deleted event")
            await self.GuildCalDict[payload.guild_id].HandleMessageDelete(payload)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        if(payload.guild_id in self.GuildCalDict.keys()):
            #print("message editted event")
            await self.GuildCalDict[payload.guild_id].HandleMessageEdit(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if(payload.user_id == self.bot.user.id):
            return

        if(payload.guild_id in self.GuildCalDict.keys()):
            await self.GuildCalDict[payload.guild_id].HandleReactAdd(payload)
        
        #print(str(payload.emoji))
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # All other Errors not returned come here. And we can just print the default TraceBack.
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    @commands.Cog.listener()
    async def on_thread_join(self, thread:Thread):
        if(thread.guild.id in self.GuildCalDict.keys()):
            await self.GuildCalDict[thread.guild.id].HandleThreadJoined(thread)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread:Thread):
        if(thread.guild.id in self.GuildCalDict.keys()):
            await self.GuildCalDict[thread.guild.id].HandleThreadDeleted(thread)

    @commands.Cog.listener()
    async def on_thread_update(self, before:Thread, after:Thread):
        if(before.guild.id in self.GuildCalDict.keys()):
            await self.GuildCalDict[before.guild.id].HandleThreadUpdated(before, after)

    @commands.Cog.listener()
    async def on_message(self, message:Message):
        await self.GuildCalDict[message.guild.id].HandleNewMessage(message)

    @tasks.loop(minutes=30)
    async def ArchiveOld(self):
        for guildID, guildCal in self.GuildCalDict.items():
            await guildCal.HandleArchiveOld()


    @ArchiveOld.before_loop
    async def BeforeArchiveOld(self):
        await self.bot.wait_until_ready()

    

async def setup(bot):
    await bot.add_cog(EventsCog(bot))

    