import discord
from CalendarEvent import CalendarEvent

stringGoing = "Going"
stringMaybe = "Maybe"
stringNo = "Remove RSVP"
stringEdit = "Edit Event (Host Only)"
stringDelete = "Delete Event (Host Only)"
stringClone = "Clone Event"


class EventViewActive(discord.ui.View):
    rsvpOptions=[
            discord.SelectOption(label=stringGoing),
            discord.SelectOption(label=stringMaybe),
            discord.SelectOption(label=stringNo),
            discord.SelectOption(label=stringEdit),
            discord.SelectOption(label=stringDelete),
            #discord.SelectOption(label=stringClone)
            ]

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(placeholder="Event Responses", min_values=1, max_values=1, options=rsvpOptions, custom_id="eventDropDown")
    async def rsvpCallback(self, interaction:discord.Interaction, select : discord.ui.Select):
        selectedOption = select.values[0]
        eventCog = interaction.client.get_cog("EventsCog")
        await eventCog.on_drop_down_selected(interaction, selectedOption)
        

class EventViewArchived(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Clone", style=discord.ButtonStyle.secondary)
    async def clone_submit(self, button:discord.ui.Button, interaction:discord.Interaction):
        eventCog = interaction.client.get_cog("EventsCog")
        await eventCog.on_drop_down_selected(interaction, "Clone")

class EventModal(discord.ui.Modal, title = "Event Details"):
    event_title = discord.ui.TextInput(label="Title", style=discord.TextStyle.short, placeholder="Title of the event, ex: Lunch at Rosalees")
    event_date = discord.ui.TextInput(label="Date", style=discord.TextStyle.short, placeholder="Date of the event, ex: 6/20")
    event_time = discord.ui.TextInput(label="Time", style=discord.TextStyle.short, placeholder="Time of the event, ex: 6pm")
    event_description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Full details of the event, ex: Hang out and get some pizza at Rosalees, all are welcome")

    def __init__(self, existingEvent:CalendarEvent):
        self.event_title.default = existingEvent.Title

        timeString = existingEvent.StartDateTime.strftime("%I:%M %p").replace(" 0", " ")
        dateString = existingEvent.StartDateTime.strftime('%m/%d/%Y')
        self.event_time.default = timeString
        self.event_date.default = dateString
        self.event_description.default = existingEvent.Description

        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        
        eventCog = interaction.client.get_cog("EventsCog")
        await eventCog.on_edit_modal_submitted(interaction, self.event_title.value, self.event_date.value, self.event_time.value, self.event_description.value)
        #await interaction.response.send_message(f"Event {self.event_title} will be updated", ephemeral=True)

    

class DeleteModal(discord.ui.Modal, title = "Are you sure?"):
    text_delete = discord.ui.TextInput(label="Type DELETE to confirm")
    def __init__(self, existingEvent:CalendarEvent):
        super().__init__()
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        if(self.text_delete.value == "DELETE"):
            eventCog = interaction.client.get_cog("EventsCog")
            await eventCog.on_delete_modal_submitted(interaction)
            #await interaction.response.send_message("Event Successfully Deleted", ephemeral=True, delete_after=20)
        else:
            await interaction.response.send_message("Event NOT Deleted, you didn't type in DELETE", ephemeral=True, delete_after=20)