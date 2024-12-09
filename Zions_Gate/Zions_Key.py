from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timezone
import traceback
import requests
import discord
import asyncio
import csv
import os
import aiohttp

load_dotenv()

from db_connection import db_connection

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

WEBHOOK_URL = os.getenv("logs_webhook_url")

CHECK_VERIFICATION_ON_STARTUP = os.getenv("check_verification_on_startup", "false").lower() == "true"

async def log_action(guild, message):
    if not WEBHOOK_URL:
        print("Error: 'logs_webhook_url' is not set. Cannot send log messages.")
        return
    data = {
        "username": f"{guild.name} Bot",
        "content": f"**[{guild.name}]** {message}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(WEBHOOK_URL, json=data) as response:
            if response.status != 204:
                response_text = await response.text()
                print(f"Failed to send log message: {response.status} {response_text}")

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

    # Perform verification check on startup if enabled
    await verify_members_on_startup()

    try:
        conn = db_connection()
        conn.close()
    except Exception as e:
        print(f'Failed to connect to database: {e}')

async def verify_members_on_startup():
    if not CHECK_VERIFICATION_ON_STARTUP:
        print("Verification check on startup is disabled.")
        return

    print("Starting verification check for all members in all guilds...")

    total_kicked = 0  # Counter for kicked members

    try:
        conn = db_connection()
        cursor = conn.cursor()
        try:
            for guild in bot.guilds:
                print(f"Checking members in guild: {guild.name} (ID: {guild.id})")
                # Fetch all verified user IDs for the guild
                sql_get_verified_users = "SELECT discord_id FROM users WHERE verify_status = %s"
                cursor.execute(sql_get_verified_users, (1,))
                verified_ids = {row[0] for row in cursor.fetchall()}

                for member in guild.members:
                    if member.bot:
                        continue  # Skip bots

                    if member.id in verified_ids:
                        continue  # Member is verified

                    # Member is not verified; attempt to kick
                    if guild.me.guild_permissions.kick_members:
                        try:
                            await member.send(
                                f"You have been kicked from **{guild.name}** because you are not verified. "
                                f"Please verify in the hub server to regain access."
                            )
                        except discord.Forbidden:
                            pass  # Cannot send messages to the user

                        try:
                            await member.kick(reason="Member not verified in the database.")
                            total_kicked += 1
                            print(f"Kicked unverified member: {member} from guild: {guild.name}")
                            await log_action(guild, f"Kicked unverified member: {member} ({member.id})")
                            await asyncio.sleep(1)  # Wait to prevent rate limits
                        except discord.Forbidden:
                            print(f"Failed to kick {member} from {guild.name}: Missing Permissions.")
                        except Exception as e:
                            print(f"Error kicking {member} from {guild.name}: {e}")
                    else:
                        print(f"Bot lacks 'Kick Members' permission in {guild.name}. Cannot kick {member}.")

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"Error during verification check on startup: {e}")
        traceback.print_exc()

    print(f"Verification check complete. Total members kicked: {total_kicked}.")

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
            # Assign 'global verified' if it exists
            global_verified_role = discord.utils.find(
                lambda r: r.name.lower().strip() == 'global verified', guild.roles)
            if global_verified_role:
                await member.add_roles(global_verified_role)
            else:
                print(f"'global verified' role not found in {guild.name}. Consider adding it manually.")
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
            if member.bot:
                continue

            sql_check_user = "SELECT COUNT(*) FROM users WHERE discord_id = %s"
            cursor.execute(sql_check_user, (member.id,))
            result = cursor.fetchone()
            user_exists = result[0] > 0

            if not user_exists:
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

        if remove_verification_pending_role:
            verification_pending_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verification pending', hub_guild.roles)
            if verification_pending_role and verification_pending_role in member.roles:
                if hub_guild.me.top_role > verification_pending_role:
                    await member.remove_roles(verification_pending_role)
                    print(f"Removed 'verification pending' role from {member} in the hub server.")
                else:
                    print(f"Bot's role is not higher than 'verification pending' role. Cannot remove role.")

        if ban_user:
            if hub_guild.me.guild_permissions.ban_members:
                await hub_guild.ban(member, reason=reason)
                print(f"Banned {member} from the hub server. Reason: {reason}")
            else:
                print(f"Bot lacks 'Ban Members' permission in the hub server.")
    except Exception as e:
        print(f"Error performing actions in hub server for user {user_id}: {e}")
        traceback.print_exc()

@bot.tree.command(name="global_ban", description="Globally ban a user from all servers.")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def global_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    user_id = member.id
    conn = db_connection()
    cursor = conn.cursor()
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

                global_verified_role = discord.utils.find(lambda r: r.name.lower().strip() == 'global verified', guild.roles)
                if global_verified_role and global_verified_role in member_in_guild.roles:
                    if guild.me.top_role > global_verified_role:
                        await member_in_guild.remove_roles(global_verified_role)
                        print(f"Removed 'global verified' from {member_in_guild} in {guild.name}.")

                if guild.me.guild_permissions.ban_members:
                    try:
                        await guild.ban(member_in_guild, reason=f"Global ban: {reason}")
                    except Exception as e:
                        print(f"Error banning {member_in_guild} from {guild.name}: {e}")
                else:
                    print(f"Bot lacks 'Ban Members' permission in {guild.name}.")

        await perform_hub_server_actions(
            user_id,
            remove_verified_role=False,
            remove_verification_pending_role=False,
            ban_user=True,
            reason=f"Global ban: {reason}"
        )

        await log_action(interaction.guild,  f"{member.mention} ({member.id}) globally banned by {interaction.user}. Reason: {reason}")
        await interaction.followup.send(f"{member} globally banned from all servers.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to globally ban the user.", ephemeral=True)
        print(f"Error during global ban: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

@bot.tree.command(name="global_unban", description="Globally unban a user from all servers.")
@discord.app_commands.checks.has_permissions(ban_members=True)
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
        await interaction.followup.send("Failed to fetch the user. Check the ID.", ephemeral=True)
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

        await log_action(interaction.guild,  f"{user.mention} ({user.id}) globally unbanned by {interaction.user}. Reason: {reason}")
        await interaction.followup.send(f"User {user} globally unbanned.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to globally unban the user.", ephemeral=True)
        print(f"Error during global unban: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

@bot.tree.command(name="global_kick", description="Globally kick a user from all servers.")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def global_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    user_id = member.id
    conn = db_connection()
    cursor = conn.cursor()
    try:
        sql_update_status = "UPDATE users SET verify_status = %s WHERE discord_id = %s"
        cursor.execute(sql_update_status, (0, user_id))
        conn.commit()

        for guild in bot.guilds:
            member_in_guild = guild.get_member(user_id)
            if member_in_guild:
                print(f"Processing {member_in_guild} in {guild.name}")
                global_verified_role = discord.utils.find(lambda r: r.name.lower().strip() == 'global verified', guild.roles)
                if global_verified_role and global_verified_role in member_in_guild.roles:
                    if guild.me.top_role > global_verified_role:
                        await member_in_guild.remove_roles(global_verified_role)
                        print(f"Removed 'global verified' from {member_in_guild} in {guild.name}.")

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
            remove_verified_role=False,
            remove_verification_pending_role=False,
            ban_user=False,
            reason=f"Global kick: {reason}"
        )

        await log_action(interaction.guild, f"{member.mention} ({member.id}) globally kicked by {interaction.user}. Reason: {reason}")
        await interaction.followup.send(f"{member} globally kicked from all servers (except the hub server).", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to globally kick the user.", ephemeral=True)
        print(f"Error during global kick: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

@bot.tree.command(name="local_kick", description="Kick a user from this server.")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def local_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    try:
        if interaction.guild.me.guild_permissions.kick_members:
            await member.kick(reason=f"Kick by {interaction.user}: {reason}")
            await log_action(interaction.guild, f"{member.mention} ({member.id}) locally kicked by {interaction.user}. Reason: {reason}")
            await interaction.followup.send(f"{member} has been kicked from the server.", ephemeral=True)
        else:
            await interaction.followup.send("I do not have permission to kick members.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to kick the user.", ephemeral=True)
        print(f"Error during kick: {e}")
        traceback.print_exc()

@bot.tree.command(name="local_ban", description="Ban a user from this server.")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def local_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    try:
        if interaction.guild.me.guild_permissions.ban_members:
            await interaction.guild.ban(member, reason=f"Ban by {interaction.user}: {reason}")
            await log_action(interaction.guild, f"{member.mention} ({member.id}) locally banned by {interaction.user}. Reason: {reason}")
            await interaction.followup.send(f"{member} has been banned from the server.", ephemeral=True)
        else:
            await interaction.followup.send("I do not have permission to ban members.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to ban the user.", ephemeral=True)
        print(f"Error during ban: {e}")
        traceback.print_exc()

@bot.tree.command(name="verify_all", description="Verify all users in the server.")
@discord.app_commands.checks.has_permissions(administrator=True)  # admin only
async def verify_all(interaction: discord.Interaction):
    conn = db_connection()
    cursor = conn.cursor()
    try:
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        verified_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verified', guild.roles)

        if not verified_role:
            await interaction.response.send_message("'Verified' role not found in the server.", ephemeral=True)
            return

        await interaction.response.send_message("Starting the verification process for all members...", ephemeral=True)

        verification_pending_role = discord.utils.find(lambda r: r.name.lower().strip() == 'verification pending', guild.roles)

        for member in guild.members:
            try:
                if member.bot:
                    continue

                sql_check_user = "SELECT COUNT(*) FROM users WHERE discord_id = %s"
                cursor.execute(sql_check_user, (member.id,))
                result = cursor.fetchone()
                user_exists = result[0] > 0

                if not user_exists:
                    sql_insert_user = "INSERT INTO users (discord_id, verify_status) VALUES (%s, %s)"
                    cursor.execute(sql_insert_user, (member.id, 1))
                    conn.commit()
                else:
                    sql_update_status = "UPDATE users SET verify_status = %s WHERE discord_id = %s"
                    cursor.execute(sql_update_status, (1, member.id))
                    conn.commit()

                if verified_role not in member.roles:
                    await member.add_roles(verified_role)

                if verification_pending_role and verification_pending_role in member.roles:
                    await member.remove_roles(verification_pending_role)

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

    webhook_url = WEBHOOK_URL  # Reuse the existing webhook URL
    if webhook_url:
        try:
            async with aiohttp.ClientSession() as session:
                with open(log_filename, "rb") as log_file:
                    data = aiohttp.FormData()
                    data.add_field(
                        "content",
                        f"Purged {len(deleted_messages)} messages from {channel.mention}. Log file attached:",
                    )
                    data.add_field(
                        "file",
                        log_file,
                        filename=log_filename,
                        content_type="text/csv"
                    )
                    async with session.post(webhook_url, data=data) as response:
                        if response.status in [200, 204]:
                            print("Log file successfully sent to the webhook.")
                        else:
                            response_text = await response.text()
                            print(f"Failed to send log file to the webhook: {response.status} {response_text}")
        except Exception as e:
            print(f"Error sending log file to the webhook: {e}")
    else:
        print("Webhook URL not set. Log file was not sent.")

    os.remove(log_filename)

@bot.tree.command(name="wipe_commands", description="Wipe all commands from a guild and re-sync.")
@discord.app_commands.checks.has_permissions(administrator=True)  # admin only
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

bot.run(os.getenv("connected_bot_token"))
