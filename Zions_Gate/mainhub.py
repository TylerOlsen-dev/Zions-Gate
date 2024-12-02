from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime
import traceback
import requests
import discord
import asyncio
import csv
import os

load_dotenv()

from db_connection import db_connection
from role_button import send_role_button, remove_button, recreate_buttons_on_startup
from ticket_button import send_ticket_button, delete_ticket_button, recreate_ticket_buttons

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

WEBHOOK_URL = os.getenv("logs_webhook_url")

async def log_action(guild, message):
    if not WEBHOOK_URL:
        print("Error: 'logs_webhook_url' is not set. Cannot send log messages.")
        return
    data = {
        "username": f"{guild.name} Bot",
        "content": f"**[{guild.name}]** {message}"
    }
    response = requests.post(WEBHOOK_URL, json=data)
    if response.status_code != 204:
        print(f"Failed to send log message: {response.status_code} {response.content}")

hub_guild_id_str = os.getenv("hub_guild_id")
if not hub_guild_id_str:
    print("Error: 'hub_guild_id' is not set in environment variables.")
    hub_guild_id = None
else:
    try:
        hub_guild_id = int(hub_guild_id_str)
    except ValueError:
        print(f"Error: 'hub_guild_id' is invalid: {hub_guild_id_str}")
        hub_guild_id = None

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands globally.')
    except Exception as e:
        print(f'Error syncing commands: {e}')

    await recreate_buttons_on_startup(bot)
    await recreate_ticket_buttons(bot)

    if not synchronize_verified_users.is_running():
        synchronize_verified_users.start()

    if not check_global_bans.is_running():
        check_global_bans.start()

    try:
        conn = db_connection()
        conn.close()
    except Exception as e:
        print(f'Failed to connect to database: {e}')

@bot.event
async def on_member_join(member):
    user_id = member.id
    guild = member.guild 

    if hub_guild_id and guild.id != hub_guild_id:
        return

    conn = db_connection()
    cursor = conn.cursor()

    try:
        sql_insert_user = """
        INSERT INTO users (discord_id, join_date, verify_status)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE join_date = VALUES(join_date)
        """
        cursor.execute(sql_insert_user, (user_id, datetime.utcnow(), 0))
        conn.commit()

        verification_pending_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verification pending', guild.roles)
        if verification_pending_role:
            await member.add_roles(verification_pending_role)
            print(f"Assigned 'verification pending' role to {member} in the hub server.")
        else:
            print("'verification pending' role not found in the hub server.")

    except Exception as e:
        print(f"Error during member join handling in hub server: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

@bot.tree.command(name="verify", description="Verify a user.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def verify(interaction: discord.Interaction, member: discord.Member):
    conn = db_connection()
    cursor = conn.cursor()
    try:
        # Update verification status in the database
        sql_update_status = "UPDATE users SET verify_status = %s WHERE discord_id = %s"
        cursor.execute(sql_update_status, (1, member.id))
        conn.commit()

        # Assign 'verified' role in the hub server
        guild = interaction.guild
        if guild:
            verified_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verified', guild.roles)
            if verified_role:
                await member.add_roles(verified_role)
                print(f"Assigned 'verified' role to {member} in the hub server.")
            else:
                print("'verified' role not found in the hub server.")

            # Remove 'verification pending' role
            verification_pending_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verification pending', guild.roles)
            if verification_pending_role and verification_pending_role in member.roles:
                await member.remove_roles(verification_pending_role)
                print(f"Removed 'verification pending' role from {member} in the hub server.")
            else:
                print(f"'verification pending' role not found or not assigned to {member} in the hub server.")
        else:
            print("Guild not found.")

        # Determine if the channel is in the target category
        if isinstance(interaction.channel, discord.TextChannel):
            channel_category = interaction.channel.category
            if channel_category and channel_category.id == 1303165889344049183:
                # Channel is in the target category
                # Send confirmation message in the channel
                await interaction.response.send_message(
                    f"{member.mention}, you have been verified and this chat will close in 1 minute.",
                    ephemeral=False
                )
                # Close the verification chat after 1 minute
                asyncio.create_task(close_verification_chat_after_delay(interaction.channel, delay=60))
            else:
                # Channel is not in the target category
                await interaction.response.send_message(
                    f"{member.mention} has been verified.",
                    ephemeral=False
                )
        else:
            # Channel is not a text channel
            await interaction.response.send_message(
                f"{member.mention} has been verified.",
                ephemeral=False
            )

    except Exception as e:
        await interaction.response.send_message("An error occurred during verification.", ephemeral=True)
        print(f"Error during verification: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

@bot.tree.command(name="verify_all", description="Verify all users in the server.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def verify_all(interaction: discord.Interaction):
    conn = db_connection()
    cursor = conn.cursor()
    try:

        sql_update_status = "UPDATE users SET verify_status = %s WHERE discord_id = %s"
        cursor.execute(sql_update_status, (1, member.id))
        conn.commit()
        
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        verified_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verified', guild.roles)
        verification_pending_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verification pending', guild.roles)

        if not verified_role:
            await interaction.response.send_message("'Verified' role not found in the server.", ephemeral=True)
            return

        await interaction.response.send_message("Starting the verification process for all members...", ephemeral=True)

        # Iterate over all members in the server
        for member in guild.members:
            try:
                # Skip bots
                if member.bot:
                    continue

                # Update verification status in the database
                sql_update_status = "UPDATE users SET verify_status = %s WHERE discord_id = %s"
                cursor.execute(sql_update_status, (1, member.id))
                conn.commit()

                # Assign 'verified' role
                if verified_role not in member.roles:
                    await member.add_roles(verified_role)
                    print(f"Assigned 'verified' role to {member}.")

                # Remove 'verification pending' role
                if verification_pending_role and verification_pending_role in member.roles:
                    await member.remove_roles(verification_pending_role)
                    print(f"Removed 'verification pending' role from {member}.")

            except Exception as e:
                print(f"Error verifying member {member}: {e}")
                continue

        await interaction.followup.send("Verification process completed for all members.", ephemeral=True)

    except Exception as e:
        await interaction.followup.send("An error occurred during the verification process.", ephemeral=True)
        print(f"Error during verify_all: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()


async def close_verification_chat_after_delay(channel, delay=60):
    print(f"close_verification_chat_after_delay: Waiting for {delay} seconds to close channel {channel.name} ({channel.id})")
    await asyncio.sleep(delay)
    try:
        if 1303165889344049183 is None:
            print("TARGET_CATEGORY_ID is not set. Skipping channel deletion.")
            return

        # Check if the channel is in the target category
        if isinstance(channel, discord.TextChannel):
            if channel.category and channel.category.id == 1303165889344049183:
                await channel.send("This channel will now be closed.")
                await asyncio.sleep(5)
                await channel.delete()
                print(f"Deleted channel {channel.name}")
            else:
                print(f"Channel {channel.name} is not in the target category. Skipping deletion.")
        elif isinstance(channel, discord.Thread):
            await channel.edit(archived=True, locked=True)
            print(f"Archived and locked thread {channel.name}")
        else:
            print(f"Channel type {type(channel)} not supported for closing.")
    except Exception as e:
        print(f"Error closing verification chat: {e}")
        traceback.print_exc()

@tasks.loop(hours=1)
async def synchronize_verified_users():
    await bot.wait_until_ready()
    conn = db_connection()
    cursor = conn.cursor()
    try:
        sql_fetch_verified = "SELECT discord_id FROM users WHERE verify_status = 1"
        cursor.execute(sql_fetch_verified)
        verified_users = cursor.fetchall()

        hub_guild = bot.get_guild(hub_guild_id)
        if not hub_guild:
            print("Hub server not found.")
            return

        verified_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verified', hub_guild.roles)
        if not verified_role:
            print("Verified role not found in the hub server.")
            return

        for user_id_tuple in verified_users:
            user_id = user_id_tuple[0]
            member = hub_guild.get_member(user_id)
            if member:
                if verified_role not in member.roles:
                    try:
                        await member.add_roles(verified_role)
                        print(f"Added 'verified' role to {member} in the hub server.")
                    except Exception as e:
                        print(f"Error adding 'verified' role to {member}: {e}")
            else:
                pass

    except Exception as e:
        print(f"Error during synchronization in hub server: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

@bot.tree.command(name="send_role_button", description="Send a role button to a specific channel.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_send_role_button(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    role: discord.Role,
    message: str,
    button_text: str,
    success_message: str,
    allowed_roles: discord.Role = None
):
    await send_role_button(interaction, channel, role, message, button_text, success_message, allowed_roles)

@bot.tree.command(name="remove_button", description="Remove a button by its message ID.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_remove_button(interaction: discord.Interaction, message_id: str):
    await remove_button(interaction, message_id)

@bot.tree.command(name="send_ticket_button", description="Send a button to open a ticket.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_send_ticket_button(interaction: discord.Interaction, channel: discord.TextChannel):
    await send_ticket_button(interaction, channel)

@bot.tree.command(name="delete_ticket_button", description="Delete a ticket button from the channel and database.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_delete_ticket_button(interaction: discord.Interaction, message_id: str):
    await delete_ticket_button(interaction, message_id)

@bot.tree.command(name="purge", description="Delete messages and log them.")
@discord.app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, channel: discord.TextChannel, limit: int):
    if limit <= 0 or limit > 1000:
        await interaction.response.send_message("Please specify a limit between 1 and 1000.", ephemeral=True)
        return

    await interaction.response.send_message(f"Purging {limit} messages from {channel.mention}.", ephemeral=True)

    deleted_messages = await channel.purge(limit=limit)

    log_filename = f"purged_messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with open(log_filename, mode="w", encoding="utf-8", newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["Timestamp", "Author", "Author ID", "Content"])
        for message in deleted_messages:
            csvwriter.writerow([
                message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                f"{message.author}",
                message.author.id,
                message.content.replace('\n', '\\n')
            ])

    admin_channel_id = os.getenv("admin_channel_id")
    if admin_channel_id:
        try:
            admin_channel = interaction.guild.get_channel(int(admin_channel_id))
            if admin_channel:
                await admin_channel.send(
                    content=f"Purged {len(deleted_messages)} messages from {channel.mention}. Log file attached:",
                    file=discord.File(log_filename)
                )
            else:
                print("Admin channel not found. Log file was not sent.")
        except Exception as e:
            print(f"Error sending log file: {e}")
    else:
        print("Admin channel ID not set. Log file was not sent.")

    os.remove(log_filename)

@bot.tree.command(name="wipe_commands", description="Wipe all commands from a guild and re-sync.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def wipe_commands(interaction: discord.Interaction, guild_id: str):
    await interaction.response.defer(ephemeral=True)
    try:
        guild_id_int = int(guild_id)
        guild = bot.get_guild(guild_id_int)
        if not guild:
            await interaction.followup.send(f"Guild with ID {guild_id} not found.", ephemeral=True)
            return

        bot.tree.clear_commands(guild=discord.Object(id=guild_id_int))
        await bot.tree.sync(guild=discord.Object(id=guild_id_int))
        await interaction.followup.send(f"Commands in guild {guild.name} have been wiped and re-synced.", ephemeral=True)
        print(f"Commands in guild {guild.name} have been wiped and re-synced.")
    except Exception as e:
        await interaction.followup.send("An error occurred while wiping commands.", ephemeral=True)
        print(f"Error wiping commands: {e}")
        traceback.print_exc()

@tasks.loop(hours=1)
async def check_global_bans():
    conn = db_connection()
    cursor = conn.cursor()
    try:
        sql_get_bans = "SELECT discord_id FROM global_bans"
        cursor.execute(sql_get_bans)
        banned_ids = [row[0] for row in cursor.fetchall()]

        hub_guild = bot.get_guild(hub_guild_id)
        if not hub_guild:
            print("Hub server not found.")
            return

        for member_id in banned_ids:
            member = hub_guild.get_member(member_id)
            if member:
                if hub_guild.me.guild_permissions.ban_members:
                    try:
                        await hub_guild.ban(member, reason="Globally banned.")
                        await log_action(hub_guild, f"Globally banned user {member} was banned from the hub server.")
                    except Exception as e:
                        print(f"Error banning {member}: {e}")
                else:
                    print(f"Bot lacks 'Ban Members' permission in the hub server.")
    except Exception as e:
        print(f"Error during global bans check: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()
    await asyncio.sleep(1)

# Run the bot
bot.run(os.getenv("hub_bot_token"))
