import discord
import random
from db_connection import db_connection

QUESTIONS_POOL = [
"What draws you to participate in a community centered around The Church of Jesus Christ of Latter-day Saints?",    
"How do you feel about connecting with others who share similar values or beliefs?",  
"What is one thing you admire or respect about the teachings of Jesus Christ?",  
"What role does faith or spirituality play in your life?",  
"What do you think it means to be part of a Christ-centered community?",  
"Have you interacted with other communities of The Church of Jesus Christ of Latter-day Saints before? What was your experience?",  
"What is something you have heard about The Church of Jesus Christ of Latter-day Saints that interests or resonates with you?",  
"What do you think is unique about the beliefs or culture of The Church of Jesus Christ of Latter-day Saints?",  
"How do you feel about discussions that focus on uplifting and spiritual topics?",  
"What is one question you have always had about The Church of Jesus Christ of Latter-day Saints?",  
"What do you know about the Book of Mormon or other scriptures of The Church of Jesus Christ of Latter-day Saints?",  
"How do you view the importance of prayer in your daily life?",  
"What do you know about the role of service in The Church of Jesus Christ of Latter-day Saints?",  
"Have you had experiences with missionaries from The Church of Jesus Christ of Latter-day Saints, and what did you think of those interactions?",     
"How do you contribute to creating a positive and respectful online community?",  
"What does it mean to you to uplift and support others in a group setting?",  
"How comfortable are you discussing faith-related topics with people from diverse backgrounds?",   
"What values do you think are important for a community centered on faith?",  
"How do you see yourself participating in a hub with access to multiple communities of The Church of Jesus Christ of Latter-day Saints?",  
"What would make this community a meaningful place for you to spend time?",  
"How do you balance sharing your beliefs with respecting others' perspectives?",  
"What is one way you could help foster kindness and understanding in this server?"
]

class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.blurple, custom_id="open_ticket_button")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        category = discord.utils.get(guild.categories, name="Tickets")
        if category:
            for channel in category.channels:
                permissions = channel.permissions_for(user)
                if permissions.read_messages:
                    await interaction.response.send_message(
                        f"You already have a ticket open: {channel.mention}.", ephemeral=True
                    )
                    return
        else:
            category = await guild.create_category("Tickets")

        channel_name = f"ticket-{user.name.lower()}-{user.discriminator}"
        ticket_channel = await guild.create_text_channel(channel_name, category=category)

        await ticket_channel.set_permissions(guild.default_role, read_messages=False)
        await ticket_channel.set_permissions(user, read_messages=True, send_messages=True)

        questions = random.sample(QUESTIONS_POOL, 3)
        question_text = "\n".join([f"{i + 1}. {q}" for i, q in enumerate(questions)])
        await ticket_channel.send(
            content=f"{user.mention}, please answer the following questions before proceeding:\n\n{question_text}"
        )

        await interaction.response.send_message(
            f"Ticket created! Please go to {ticket_channel.mention} to answer the questions.", ephemeral=True
        )

def save_ticket_button_config(message_id, channel_id):
    conn = db_connection()
    cursor = conn.cursor()
    sql = '''
    INSERT INTO ticket_buttons (message_id, channel_id)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE channel_id = VALUES(channel_id)
    '''
    cursor.execute(sql, (message_id, channel_id))
    conn.commit()
    cursor.close()
    conn.close()

def update_ticket_button_message_id(old_message_id, new_message_id):
    conn = db_connection()
    cursor = conn.cursor()
    sql = "UPDATE ticket_buttons SET message_id = %s WHERE message_id = %s"
    cursor.execute(sql, (new_message_id, old_message_id))
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Updated ticket button message ID in database: {old_message_id} -> {new_message_id}")

def load_ticket_buttons():
    conn = db_connection()
    cursor = conn.cursor()
    sql = "SELECT message_id, channel_id FROM ticket_buttons"
    cursor.execute(sql)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def remove_ticket_button_config(message_id):
    conn = db_connection()
    cursor = conn.cursor()
    sql = "DELETE FROM ticket_buttons WHERE message_id = %s"
    cursor.execute(sql, (message_id,))
    conn.commit()
    cursor.close()
    conn.close()

async def recreate_ticket_buttons(bot):
    configs = load_ticket_buttons()
    for message_id, channel_id in configs:
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"Channel {channel_id} not found. Skipping.")
            continue

        try:
            msg = await channel.fetch_message(message_id)
            view = TicketButton()
            bot.add_view(view, message_id=msg.id)
            print(f"Rebound ticket button for message {message_id} in channel {channel.name}.")
        except discord.NotFound:
            view = TicketButton()
            new_message = await channel.send(content="Click to open a ticket:", view=view)
            update_ticket_button_message_id(message_id, new_message.id)
            print(f"Recreated ticket button in channel {channel.name} with new message ID {new_message.id}.")

async def send_ticket_button(interaction: discord.Interaction, channel: discord.TextChannel):
    view = TicketButton()
    sent_message = await channel.send(content="Click the button below to open a ticket:", view=view)
    save_ticket_button_config(sent_message.id, channel.id)
    await interaction.response.send_message(f"Ticket button sent to {channel.mention} and saved!", ephemeral=True)

async def delete_ticket_button(interaction: discord.Interaction, message_id: str):
    conn = db_connection()
    cursor = conn.cursor()
    sql_select = "SELECT channel_id FROM ticket_buttons WHERE message_id = %s"
    cursor.execute(sql_select, (message_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not result:
        await interaction.response.send_message(f"No ticket button found with message ID {message_id}.", ephemeral=True)
        return

    channel_id = result[0]
    channel = interaction.guild.get_channel(channel_id)

    if channel:
        try:
            msg = await channel.fetch_message(int(message_id))
            await msg.delete()
            print(f"Deleted message with ID {message_id} from channel {channel.name}.")
        except discord.NotFound:
            print(f"Message with ID {message_id} not found in channel {channel.name}.")

    remove_ticket_button_config(message_id)
    await interaction.response.send_message(f"Ticket button with message ID {message_id} deleted.", ephemeral=True)
