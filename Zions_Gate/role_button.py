import discord
from db_connection import db_connection

class RoleButton(discord.ui.View):
    def __init__(self, role_id, button_text, success_message, allowed_roles=None):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.success_message = success_message
        self.allowed_roles = allowed_roles or []

        button = discord.ui.Button(
            label=button_text,
            style=discord.ButtonStyle.green,
            custom_id=f"role_button_{role_id}"
        )
        button.callback = self.assign_role
        self.add_item(button)

    async def assign_role(self, interaction: discord.Interaction):
        if self.allowed_roles:
            user_roles = [role.id for role in interaction.user.roles]
            if not any(role_id in self.allowed_roles for role_id in user_roles):
                await interaction.response.send_message(
                    "You do not have permission to press this button.",
                    ephemeral=True
                )
                return

        role = interaction.guild.get_role(self.role_id)
        if role in interaction.user.roles:
            await interaction.response.send_message(
                "You already have this role!",
                ephemeral=True
            )
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                self.success_message,
                ephemeral=True
            )

def save_button_config(message_id, channel_id, role_id, message, button_text, success_message, allowed_roles=None):
    conn = db_connection()
    cursor = conn.cursor()
    sql = '''
    INSERT INTO button_configs (message_id, channel_id, role_id, message, button_text, success_message, allowed_roles)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE channel_id = VALUES(channel_id), role_id = VALUES(role_id),
    message = VALUES(message), button_text = VALUES(button_text), success_message = VALUES(success_message),
    allowed_roles = VALUES(allowed_roles)
    '''
    allowed_roles_str = ",".join(map(str, allowed_roles)) if allowed_roles else None
    values = (
        message_id,
        channel_id,
        role_id,
        message,
        button_text,
        success_message,
        allowed_roles_str
    )
    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()

def update_button_message_id(old_message_id, new_message_id):
    conn = db_connection()
    cursor = conn.cursor()
    sql = "UPDATE button_configs SET message_id = %s WHERE message_id = %s"
    cursor.execute(sql, (new_message_id, old_message_id))
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Updated message ID in database: {old_message_id} -> {new_message_id}")

def load_all_button_configs():
    conn = db_connection()
    cursor = conn.cursor()
    sql = "SELECT message_id, channel_id, role_id, message, button_text, success_message, allowed_roles FROM button_configs"
    cursor.execute(sql)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def remove_button_from_database(message_id):
    conn = db_connection()
    cursor = conn.cursor()
    sql = "DELETE FROM button_configs WHERE message_id = %s"
    cursor.execute(sql, (message_id,))
    conn.commit()
    cursor.close()
    conn.close()

async def recreate_buttons_on_startup(bot):
    configs = load_all_button_configs()
    for config in configs:
        (
            message_id,
            channel_id,
            role_id,
            message,
            button_text,
            success_message,
            allowed_roles_str
        ) = config
        allowed_roles = (
            list(map(int, allowed_roles_str.split(","))) if allowed_roles_str else None
        )
        channel = bot.get_channel(channel_id)

        if not channel:
            print(f"Channel {channel_id} not found for message {message_id}. Skipping.")
            continue

        try:
            msg = await channel.fetch_message(int(message_id))
            view = RoleButton(role_id, button_text, success_message, allowed_roles)
            bot.add_view(view, message_id=msg.id) 
            print(f"Rebound button view for message {message_id} in channel {channel.name}.")
        except discord.NotFound:
            view = RoleButton(role_id, button_text, success_message, allowed_roles)
            new_message = await channel.send(content=message, view=view)
            update_button_message_id(message_id, new_message.id)
            bot.add_view(view, message_id=new_message.id)
            print(f"Recreated button message in channel {channel.name} with new message ID {new_message.id}.")

async def send_role_button(interaction, channel, role, message, button_text, success_message, allowed_roles):
    allowed_roles_ids = [allowed_roles.id] if allowed_roles else []
    if len(allowed_roles_ids) > 6:
        await interaction.response.send_message("You can specify up to 6 roles only.", ephemeral=True)
        return

    view = RoleButton(role.id, button_text, success_message, allowed_roles_ids)
    sent_message = await channel.send(content=message, view=view)
    save_button_config(
        sent_message.id,
        channel.id,
        role.id,
        message,
        button_text,
        success_message,
        allowed_roles_ids
    )
    await interaction.response.send_message(
        f"Button sent to {channel.mention} and saved to the database!",
        ephemeral=True
    )

async def remove_button(interaction, message_id):
    conn = db_connection()
    cursor = conn.cursor()
    sql_select = "SELECT channel_id FROM button_configs WHERE message_id = %s"
    cursor.execute(sql_select, (message_id,))
    result = cursor.fetchone()

    if not result:
        await interaction.response.send_message(
            f"No button found with message ID {message_id}.",
            ephemeral=True
        )
        cursor.close()
        conn.close()
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

    remove_button_from_database(message_id)
    await interaction.response.send_message(
        f"Button with message ID {message_id} removed from the server and database.",
        ephemeral=True
    )
