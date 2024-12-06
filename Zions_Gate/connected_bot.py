from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime
from datetime import datetime, timezone
import traceback
import requests
import discord
import asyncio
import csv
import os










# Load environment variables
load_dotenv()










# Import database connection
from db_connection import db_connection\










# Initialize Discord bot intents
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True










# Create the bot instance
bot = commands.Bot(command_prefix="!", intents=intents)










# Set the webhook URL for logging
WEBHOOK_URL = os.getenv("logs_webhook_url")










# Function to send log messages to a webhook
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










# Initialize the hub server ID from environment variables
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










# Load environment variable for the startup ban check toggle
CHECK_BANS_ON_STARTUP = os.getenv("check_bans_on_startup", "true").lower() == "true"

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

    try:
        # Sync slash commands globally
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands globally.')
    except Exception as e:
        print(f'Error syncing commands: {e}')

    # Perform global ban check on startup if enabled
    if CHECK_BANS_ON_STARTUP:
        total_banned = 0  # Counter for banned users
        try:
            print("Performing global ban check on startup...")
            conn = db_connection()
            cursor = conn.cursor()
            try:
                # Fetch all globally banned users
                sql_get_bans = "SELECT discord_id FROM global_bans"
                cursor.execute(sql_get_bans)
                banned_ids = [row[0] for row in cursor.fetchall()]

                for guild in bot.guilds:
                    for member in guild.members:
                        if member.id in banned_ids:
                            if guild.me.guild_permissions.ban_members:
                                try:
                                    await guild.ban(member, reason="Globally banned.")
                                    print(f"Banned globally banned user {member} in {guild.name}.")
                                    await log_action(guild, f"Banned globally banned user {member}.")
                                    total_banned += 1
                                except Exception as e:
                                    print(f"Error banning {member} in {guild.name}: {e}")
                            else:
                                print(f"Bot lacks 'Ban Members' permission in {guild.name}.")
            finally:
                cursor.close()
                conn.close()
        except Exception as e:
            print(f"Error during global ban check on startup: {e}")
            traceback.print_exc()

        print(f"Global ban check complete. Total users banned: {total_banned}.")
    else:
        print("Global ban check on startup is disabled.")

    try:
        conn = db_connection()
        conn.close()
    except Exception as e:
        print(f'Failed to connect to database: {e}')












# Event triggered when a new member joins a server
@bot.event
async def on_member_join(member):
    user_id = member.id
    guild = member.guild 

    
    if hub_guild_id and guild.id == hub_guild_id:

        print(f"User {member} joined the hub server.")
        return

    conn = db_connection()
    cursor = conn.cursor()

    try:
        
        sql_check_ban = "SELECT reason FROM global_bans WHERE discord_id = %s"
        cursor.execute(sql_check_ban, (user_id,))
        ban_result = cursor.fetchone()

        if ban_result:
            reason = ban_result[0]
            try:
                await member.send(f"You are globally banned. Reason: {reason}")
            except discord.Forbidden:
                pass  
            await member.ban(reason="Globally banned.")
            await log_action(guild, f"Globally banned user {member} attempted to join and was banned.")
            return

        
        sql_check = "SELECT verify_status FROM users WHERE discord_id = %s"
        cursor.execute(sql_check, (user_id,))
        result = cursor.fetchone()

        if result and result[0] == 1:
            verified_role = discord.utils.find(
                lambda r: r.name.lower().strip() == 'global verified', guild.roles)
            if verified_role:
                await member.add_roles(verified_role)
            else:
                print(f"'global verified' role not found in {guild.name}.")
        else:
            try:
                await member.send("You must verify in the hub server before accessing this server.")
            except discord.Forbidden:
                pass
            await member.kick(reason="Not verified in hub.")
            await log_action(guild, f"Unverified user {member} attempted to join and was kicked.")
    except Exception as e:
        print(f"Error during member join handling: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()









# Add all users to the database
@bot.command(name="add_all_to_database", help="Adds all members of the server to the database. Skips existing members.")
@commands.has_permissions(administrator=True)
async def add_all_to_database(ctx):
    guild = ctx.guild
    if not guild:
        await ctx.send("This command can only be used in a server.")
        return

    conn = db_connection()
    cursor = conn.cursor()

    try:
        await ctx.send("Starting to add all members to the database. This may take a while...")

        added_members = 0
        skipped_members = 0

        for member in guild.members:
            # Skip bots
            if member.bot:
                continue

            # Check if user already exists in the database
            sql_check_user = "SELECT COUNT(*) FROM users WHERE discord_id = %s"
            cursor.execute(sql_check_user, (member.id,))
            result = cursor.fetchone()
            user_exists = result[0] > 0

            if not user_exists:
                # Add user to the database
                sql_insert_user = """
                INSERT INTO users (discord_id, time_created, verify_status, username)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(sql_insert_user, (member.id, datetime.now(timezone.utc), 0, member.name))
                conn.commit()
                added_members += 1
                print(f"Added {member.name} (ID: {member.id}) to the database.")
            else:
                skipped_members += 1

        await ctx.send(
            f"Finished adding members to the database.\n"
            f"Added: {added_members}\n"
            f"Skipped (already in database): {skipped_members}"
        )

    except Exception as e:
        await ctx.send("An error occurred while adding members to the database.")
        print(f"Error in add_all_to_database: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()










# Perform actions in the hub server (e.g., remove roles, ban users)
async def perform_hub_server_actions(user_id, remove_verified_role=False, remove_verification_pending_role=False, ban_user=False, reason=None):

    if not hub_guild_id:
        print("Hub guild ID is not set. Cannot perform hub server actions.")
        return

    hub_guild = bot.get_guild(hub_guild_id)
    if not hub_guild:
        print(f"Bot is not in the hub server with ID {hub_guild_id}. Cannot perform hub server actions.")
        return

    member = hub_guild.get_member(user_id)
    if not member:
        print(f"User with ID {user_id} not found in the hub server.")
        return

    try:
        if remove_verified_role:
            verified_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verified', hub_guild.roles)
            if verified_role and verified_role in member.roles:
                if hub_guild.me.top_role > verified_role:
                    await member.remove_roles(verified_role)
                    print(f"Removed 'verified' role from {member} in the hub server.")
                else:
                    print(f"Bot's role is not higher than 'verified' role. Cannot remove role from {member} in hub server.")
            else:
                print(f"'verified' role not found or not assigned to {member} in the hub server.")

        
        if remove_verification_pending_role:
            verification_pending_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verification pending', hub_guild.roles)
            if verification_pending_role and verification_pending_role in member.roles:
                if hub_guild.me.top_role > verification_pending_role:
                    await member.remove_roles(verification_pending_role)
                    print(f"Removed 'verification pending' role from {member} in the hub server.")
                else:
                    print(f"Bot's role is not higher than 'verification pending' role. Cannot remove role from {member} in hub server.")
            else:
                print(f"'verification pending' role not found or not assigned to {member} in the hub server.")

        if ban_user:
            if hub_guild.me.guild_permissions.ban_members:
                await hub_guild.ban(member, reason=reason)
                print(f"Banned {member} from the hub server. Reason: {reason}")
            else:
                print(f"Bot lacks 'Ban Members' permission in the hub server.")
    except Exception as e:
        print(f"Error performing actions in hub server for user {user_id}: {e}")
        traceback.print_exc()










# Slash command to globally ban a user from all servers
@bot.tree.command(name="global_ban", description="Globally ban a user from all servers.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def global_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    user_id = member.id
    conn = db_connection()
    cursor = conn.cursor()

    await interaction.response.defer(ephemeral=True)

    try:
        sql_insert_ban = """
        INSERT INTO global_bans (discord_id, banned_at, reason)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE banned_at = VALUES(banned_at), reason = VALUES(reason)
        """
        cursor.execute(sql_insert_ban, (user_id, datetime.utcnow(), reason))
        conn.commit()

        sql_update_status = "UPDATE users SET verify_status = %s WHERE discord_id = %s"
        cursor.execute(sql_update_status, (0, user_id))
        conn.commit()

        for guild in bot.guilds:
            member_in_guild = guild.get_member(user_id)
            if member_in_guild:
                print(f"Processing {member_in_guild} in {guild.name}")


                verified_role = discord.utils.find(lambda r: r.name.lower().strip() == 'global verified', guild.roles)
                if verified_role and verified_role in member_in_guild.roles:
                    if guild.me.top_role > verified_role:
                        await member_in_guild.remove_roles(verified_role)
                        print(f"Removed 'global verified' role from {member_in_guild} in {guild.name}.")
                    else:
                        print(f"Bot's role is not higher than 'global verified' role in {guild.name}. Cannot remove role.")
                else:
                    print(f"'global verified' role not found or not assigned to {member_in_guild} in {guild.name}.")

                verification_pending_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verification pending', guild.roles)
                if verification_pending_role and verification_pending_role in member_in_guild.roles:
                    if guild.me.top_role > verification_pending_role:
                        await member_in_guild.remove_roles(verification_pending_role)
                        print(f"Removed 'verification pending' role from {member_in_guild} in {guild.name}.")
                    else:
                        print(f"Bot's role is not higher than 'verification pending' role in {guild.name}. Cannot remove role.")
                else:
                    print(f"'verification pending' role not found or not assigned to {member_in_guild} in {guild.name}.")

                
                if guild.me.guild_permissions.ban_members:
                    try:
                        await guild.ban(member_in_guild, reason=f"Global ban: {reason}")
                        
                    except Exception as e:
                        print(f"Error banning {member_in_guild} from {guild.name}: {e}")
                else:
                    print(f"Bot lacks 'Ban Members' permission in {guild.name}.")

        
        await perform_hub_server_actions(
            user_id,
            remove_verified_role=True,
            remove_verification_pending_role=True,
            ban_user=True,
            reason=f"Global ban: {reason}"
        )

        
        await log_action(interaction.guild,  f"{member.mention} ({member.id}) has been globally banned by {interaction.user} in {interaction.guild.name}. Reason: {reason}")
        
        await interaction.followup.send(f"{member} has been globally banned from all servers.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to globally ban the user.", ephemeral=True)
        print(f"Error during global ban: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()










# Slash command to globally unban a user from all servers
@bot.tree.command(name="global_unban", description="Globally unban a user from all servers.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def global_unban(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
    
    await interaction.response.defer(ephemeral=True)

    conn = db_connection()
    cursor = conn.cursor()

    try:
        user_id_int = int(user_id)
        user = await bot.fetch_user(user_id_int)
    except ValueError:
        await interaction.followup.send("Invalid user ID provided.", ephemeral=True)
        return
    except Exception as e:
        await interaction.followup.send("Failed to fetch the user. Please ensure the user ID is correct.", ephemeral=True)
        print(f"Error fetching user: {e}")
        return

    try:
        
        sql_delete_ban = "DELETE FROM global_bans WHERE discord_id = %s"
        cursor.execute(sql_delete_ban, (user_id_int,))
        conn.commit()

        
        for guild in bot.guilds:
            if guild.me.guild_permissions.ban_members:
                try:
                    await guild.unban(user, reason=f"Global unban: {reason}")
                    
                except discord.NotFound:
                    
                    pass
                except discord.Forbidden:
                    print(f"Bot lacks permission to unban in {guild.name}.")
                except Exception as e:
                    print(f"Error unbanning user {user_id_int} from {guild.name}: {e}")
                finally:
                    await asyncio.sleep(1)
            else:
                print(f"Bot lacks 'Ban Members' permission in {guild.name}.")

        await log_action(interaction.guild,  f"{user.mention} ({user.id}) has been globally unbanned by {interaction.user} in {interaction.guild.name}. Reason: {reason}")

        await interaction.followup.send(f"User {user} has been globally unbanned from all servers.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to globally unban the user.", ephemeral=True)
        print(f"Error during global unban: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()










# Slash command to globally kick a user from all servers
@bot.tree.command(name="global_kick", description="Globally kick a user from all servers.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def global_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    user_id = member.id
    conn = db_connection()
    cursor = conn.cursor()

    await interaction.response.defer(ephemeral=True)

    try:
        sql_update_status = "UPDATE users SET verify_status = %s WHERE discord_id = %s"
        cursor.execute(sql_update_status, (0, user_id))
        conn.commit()


        for guild in bot.guilds:
            member_in_guild = guild.get_member(user_id)
            if member_in_guild:
                print(f"Processing {member_in_guild} in {guild.name}")

                verified_role = discord.utils.find(lambda r: r.name.lower().strip() == 'global verified', guild.roles)
                if verified_role and verified_role in member_in_guild.roles:
                    if guild.me.top_role > verified_role:
                        await member_in_guild.remove_roles(verified_role)
                        print(f"Removed 'global verified' role from {member_in_guild} in {guild.name}.")
                    else:
                        print(f"Bot's role is not higher than 'global verified' role in {guild.name}. Cannot remove role.")
                else:
                    print(f"'global verified' role not found or not assigned to {member_in_guild} in {guild.name}.")

                
                verification_pending_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verification pending', guild.roles)
                if verification_pending_role and verification_pending_role in member_in_guild.roles:
                    if guild.me.top_role > verification_pending_role:
                        await member_in_guild.remove_roles(verification_pending_role)
                        print(f"Removed 'verification pending' role from {member_in_guild} in {guild.name}.")
                    else:
                        print(f"Bot's role is not higher than 'verification pending' role in {guild.name}. Cannot remove role.")
                else:
                    print(f"'verification pending' role not found or not assigned to {member_in_guild} in {guild.name}.")

                if hub_guild_id and guild.id == hub_guild_id:
                    continue

                
                if guild.me.guild_permissions.kick_members:
                    try:
                        await member_in_guild.kick(reason=f"Global kick: {reason}")
                        
                    except Exception as e:
                        print(f"Error kicking {member_in_guild} from {guild.name}: {e}")
                else:
                    print(f"Bot lacks 'Kick Members' permission in {guild.name}.")

        
        await perform_hub_server_actions(
            user_id,
            remove_verified_role=True,
            remove_verification_pending_role=True,
            ban_user=False,
            reason=f"Global kick: {reason}"
        )

        
        await log_action(interaction.guild, f"{member.mention} ({member.id}) has been globally kicked by {interaction.user} in {interaction.guild.name}. Reason: {reason}")

        await interaction.followup.send(f"{member} has been globally kicked from all servers (except the hub server).", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to globally kick the user.", ephemeral=True)
        print(f"Error during global kick: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()










# Slash command to locally kick a user from the current server
@bot.tree.command(name="local_kick", description="Kick a user from this server.")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def local_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    try:
        if interaction.guild.me.guild_permissions.kick_members:
            await member.kick(reason=f"Kick by {interaction.user}: {reason}")
            await log_action(interaction.guild, f"{member.mention} ({member.id}) has been locally kicked by {interaction.user} in {interaction.guild.name}. Reason: {reason}")
            await interaction.followup.send(f"{member} has been kicked from the server.", ephemeral=True)
        else:
            await interaction.followup.send("I do not have permission to kick members.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to kick the user.", ephemeral=True)
        print(f"Error during kick: {e}")
        traceback.print_exc()










# Slash command to locally ban a user from the current server
@bot.tree.command(name="local_ban", description="Ban a user from this server.")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def local_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    try:
        if interaction.guild.me.guild_permissions.ban_members:
            await interaction.guild.ban(member, reason=f"Ban by {interaction.user}: {reason}")
            await log_action(interaction.guild, f"{member.mention} ({member.id}) has been locally banned by {interaction.user} in {interaction.guild.name}. Reason: {reason}")
            await interaction.followup.send(f"{member} has been banned from the server.", ephemeral=True)
        else:
            await interaction.followup.send("I do not have permission to ban members.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to ban the user.", ephemeral=True)
        print(f"Error during ban: {e}")
        traceback.print_exc()










# Slash command to verify all users in the server
@bot.tree.command(name="verify_all", description="Verify all users in the server.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def verify_all(interaction: discord.Interaction):
    conn = db_connection()
    cursor = conn.cursor()
    try:
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

                # Check if user exists in the database
                sql_check_user = "SELECT COUNT(*) FROM users WHERE discord_id = %s"
                cursor.execute(sql_check_user, (member.id,))
                result = cursor.fetchone()
                user_exists = result[0] > 0

                if not user_exists:
                    # Insert the user into the database
                    sql_insert_user = "INSERT INTO users (discord_id, verify_status) VALUES (%s, %s)"
                    cursor.execute(sql_insert_user, (member.id, 1))
                    conn.commit()
                    print(f"Inserted new user {member} into the database.")
                else:
                    # Update verification status
                    sql_update_status = "UPDATE users SET verify_status = %s WHERE discord_id = %s"
                    cursor.execute(sql_update_status, (1, member.id))
                    conn.commit()
                    print(f"Updated verify_status for user {member}.")

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









# Slash command to purge messages and log them
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










# Slash command to wipe all commands from a guild and re-sync
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

# Start the bot with the token from environment variables
bot.run(os.getenv("connected_bot_token"))
