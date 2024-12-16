import discord
import asyncio
import os
import aiohttp
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import traceback
import csv

load_dotenv()
from db_connection import db_connection

mountain_time = datetime.now(ZoneInfo("America/Denver"))
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

WEBHOOK_URL = os.getenv("webhook_url")
ZIONS_KEY_BOT_TOKEN = os.getenv("zions_key_bot_token")
ZIONS_GATE_GUILD_ID = int(os.getenv("zions_gate_guild_id", "0"))
GLOBAL_VERIFIED_ROLE_NAME = os.getenv("global_verified_role_name", "global verified")
CHECK_VERIFICATION_ON_STARTUP = os.getenv("check_verification_on_startup", "true").lower() == "true"

async def log_action(guild, message):
    if not WEBHOOK_URL:
        print("Error: 'webhook_url' is not set.")
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

@bot.event
async def on_ready():
    # On Ready Event
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands globally.')
    except Exception as e:
        print(f'Error syncing commands: {e}')

    # Always perform global ban check on startup
    total_banned = 0
    try:
        print("Performing global ban check on startup...")
        conn = db_connection()
        cursor = conn.cursor()
        try:
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

    if CHECK_VERIFICATION_ON_STARTUP:
        await verify_members_on_startup()

    try:
        conn = db_connection()
        conn.close()
    except Exception as e:
        print(f'Failed to connect to database: {e}')

async def verify_members_on_startup():
    # Verification Check on Startup (controlled by CHECK_VERIFICATION_ON_STARTUP)
    print("Starting verification check for all members in all guilds...")
    total_kicked = 0
    try:
        conn = db_connection()
        cursor = conn.cursor()
        try:
            for guild in bot.guilds:
                if guild.id == ZIONS_GATE_GUILD_ID:
                    continue
                print(f"Checking members in guild: {guild.name} (ID: {guild.id})")
                sql_get_verified_users = "SELECT discord_id FROM users WHERE verify_status = %s"
                cursor.execute(sql_get_verified_users, (1,))
                verified_ids = {row[0] for row in cursor.fetchall()}
                for member in guild.members:
                    if member.bot:
                        continue
                    if member.id not in verified_ids:
                        if guild.me.guild_permissions.kick_members:
                            try:
                                await member.send(
                                    f"You have been kicked from **{guild.name}** because you are not verified in the Zions Gate server."
                                )
                            except discord.Forbidden:
                                pass
                            try:
                                await member.kick(reason="Member not verified in the Zions Gate server.")
                                total_kicked += 1
                                print(f"Kicked unverified member: {member} from {guild.name}")
                                await log_action(guild, f"Kicked unverified member: {member} ({member.id})")
                                await asyncio.sleep(1)
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
    # On Member Join Event
    user_id = member.id
    guild = member.guild
    if ZIONS_GATE_GUILD_ID and guild.id == ZIONS_GATE_GUILD_ID:
        print(f"User {member} joined the Zions Gate server.")
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
            global_verified_role = discord.utils.find(
                lambda r: r.name.lower().strip() == GLOBAL_VERIFIED_ROLE_NAME.lower(), guild.roles)
            if global_verified_role:
                await member.add_roles(global_verified_role)
            else:
                print(f"'{GLOBAL_VERIFIED_ROLE_NAME}' role not found in {guild.name}.")
        else:
            try:
                await member.send("You must verify in the Zions Gate server before accessing this server.")
            except discord.Forbidden:
                pass
            if guild.me.guild_permissions.kick_members:
                try:
                    await member.kick(reason="Not verified in Zions Gate.")
                    await log_action(guild, f"Unverified user {member} attempted to join and was kicked.")
                except Exception as e:
                    print(f"Error kicking user {member}: {e}")
    except Exception as e:
        print(f"Error during member join handling: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

# add_all_to_database Command
@bot.command(name="add_all_to_database", help="Adds all members of the server to the database. Skips existing members.")
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

async def perform_zions_gate_server_actions(user_id, remove_global_verified_role=False, ban_user=False, reason=None):
    zions_gate_guild = bot.get_guild(ZIONS_GATE_GUILD_ID)
    if not zions_gate_guild:
        print(f"Bot is not in the Zions Gate server with ID {ZIONS_GATE_GUILD_ID}.")
        return
    member = zions_gate_guild.get_member(user_id)
    if not member:
        print(f"User with ID {user_id} not found in the Zions Gate server.")
        return
    try:
        if remove_global_verified_role:
            global_verified_role = discord.utils.find(lambda r: r.name.lower().strip() == GLOBAL_VERIFIED_ROLE_NAME.lower(), zions_gate_guild.roles)
            if global_verified_role and global_verified_role in member.roles:
                if zions_gate_guild.me.top_role > global_verified_role:
                    await member.remove_roles(global_verified_role)
                    print(f"Removed '{GLOBAL_VERIFIED_ROLE_NAME}' role from {member} in the Zions Gate server.")
                else:
                    print(f"Bot's role is not higher than '{GLOBAL_VERIFIED_ROLE_NAME}' role.")
        if ban_user:
            if zions_gate_guild.me.guild_permissions.ban_members:
                await zions_gate_guild.ban(member, reason=reason)
                print(f"Banned {member} from the Zions Gate server. Reason: {reason}")
            else:
                print("Bot lacks 'Ban Members' permission in the Zions Gate server.")
    except Exception as e:
        print(f"Error performing actions in Zions Gate server for user {user_id}: {e}")
        traceback.print_exc()

def extract_id_from_input(input_str: str):
    if input_str.isdigit():
        return int(input_str)
    if input_str.startswith("<@") and input_str.endswith(">"):
        extracted = ''.join(ch for ch in input_str if ch.isdigit())
        if extracted.isdigit():
            return int(extracted)
    return None

# global_ban Command
@bot.tree.command(name="global_ban", description="Globally ban a user from all servers.")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def global_ban(interaction: discord.Interaction, member: str, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    user_id = extract_id_from_input(member)
    if not user_id:
        await interaction.followup.send("Please provide a valid user mention or ID.", ephemeral=True)
        return
    conn = db_connection()
    cursor = conn.cursor()
    try:
        try:
            user = await bot.fetch_user(user_id)
        except:
            await interaction.followup.send("Could not find a user with that ID.", ephemeral=True)
            return
        sql_insert_ban = """
        INSERT INTO global_bans (discord_id, banned_at, reason)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE banned_at = VALUES(banned_at), reason = VALUES(reason)
        """
        cursor.execute(sql_insert_ban, (user_id, mountain_time, reason))
        conn.commit()
        sql_update_status = "UPDATE users SET verify_status = %s WHERE discord_id = %s"
        cursor.execute(sql_update_status, (0, user_id))
        conn.commit()
        for g in bot.guilds:
            member_in_guild = g.get_member(user_id)
            if member_in_guild:
                global_verified_role = discord.utils.find(lambda r: r.name.lower().strip() == GLOBAL_VERIFIED_ROLE_NAME.lower(), g.roles)
                if global_verified_role and global_verified_role in member_in_guild.roles:
                    if g.me.top_role > global_verified_role:
                        await member_in_guild.remove_roles(global_verified_role)
                if g.me.guild_permissions.ban_members:
                    try:
                        await g.ban(member_in_guild, reason=f"Global ban: {reason}")
                    except Exception as e:
                        print(f"Error banning {member_in_guild} from {g.name}: {e}")
                else:
                    print(f"Bot lacks 'Ban Members' permission in {g.name}.")
        await perform_zions_gate_server_actions(
            user_id,
            remove_global_verified_role=False,
            ban_user=True,
            reason=f"Global ban: {reason}"
        )
        await log_action(interaction.guild,  f"{user.mention} ({user.id}) globally banned by {interaction.user}. Reason: {reason}")
        await interaction.followup.send(f"{user} globally banned from all servers.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to globally ban the user.", ephemeral=True)
        print(f"Error during global ban: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

# global_unban Command
@bot.tree.command(name="global_unban", description="Globally unban a user from all servers.")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def global_unban(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    conn = db_connection()
    cursor = conn.cursor()
    try:
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
        sql_delete_ban = "DELETE FROM global_bans WHERE discord_id = %s"
        cursor.execute(sql_delete_ban, (user_id_int,))
        conn.commit()
        for g in bot.guilds:
            if g.me.guild_permissions.ban_members:
                try:
                    await g.unban(user, reason=f"Global unban: {reason}")
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    print(f"Bot lacks permission to unban in {g.name}.")
                except Exception as e:
                    print(f"Error unbanning user {user_id_int} from {g.name}: {e}")
                finally:
                    await asyncio.sleep(1)
            else:
                print(f"Bot lacks 'Ban Members' permission in {g.name}.")
        await log_action(interaction.guild,  f"{user.mention} ({user.id}) globally unbanned by {interaction.user}. Reason: {reason}")
        await interaction.followup.send(f"User {user} globally unbanned.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to globally unban the user.", ephemeral=True)
        print(f"Error during global unban: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

# global_kick Command
@bot.tree.command(name="global_kick", description="Globally kick a user from all servers.")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def global_kick(interaction: discord.Interaction, member: str, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    user_id = extract_id_from_input(member)
    if not user_id:
        await interaction.followup.send("Please provide a valid user mention or ID.", ephemeral=True)
        return
    conn = db_connection()
    cursor = conn.cursor()
    try:
        sql_update_status = "UPDATE users SET verify_status = %s WHERE discord_id = %s"
        cursor.execute(sql_update_status, (0, user_id))
        conn.commit()
        for g in bot.guilds:
            if g.id == ZIONS_GATE_GUILD_ID:
                continue
            member_in_guild = g.get_member(user_id)
            if member_in_guild:
                global_verified_role = discord.utils.find(lambda r: r.name.lower().strip() == GLOBAL_VERIFIED_ROLE_NAME.lower(), g.roles)
                if global_verified_role and global_verified_role in member_in_guild.roles:
                    if g.me.top_role > global_verified_role:
                        await member_in_guild.remove_roles(global_verified_role)
                if g.me.guild_permissions.kick_members:
                    try:
                        await member_in_guild.kick(reason=f"Global kick: {reason}")
                    except Exception as e:
                        print(f"Error kicking {member_in_guild} from {g.name}: {e}")
                else:
                    print(f"Bot lacks 'Kick Members' permission in {g.name}.")
        await perform_zions_gate_server_actions(
            user_id,
            remove_global_verified_role=False,
            ban_user=False,
            reason=f"Global kick: {reason}"
        )

        try:
            user = await bot.fetch_user(user_id)
        except:
            user = f"User ID {user_id}"
        if isinstance(user, discord.User):
            await log_action(interaction.guild, f"{user.mention} ({user.id}) globally kicked by {interaction.user}. Reason: {reason}")
            await interaction.followup.send(f"{user} globally kicked from all servers (except the Zions Gate server).", ephemeral=True)
        else:
            await log_action(interaction.guild, f"{user} globally kicked by {interaction.user}. Reason: {reason}")
            await interaction.followup.send(f"{user} globally kicked from all servers (except the Zions Gate server).", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to globally kick the user.", ephemeral=True)
        print(f"Error during global kick: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

# local_kick Command
@bot.tree.command(name="local_kick", description="Kick a user from this server.")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def local_kick(interaction: discord.Interaction, member: str, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
        return
    user_id = extract_id_from_input(member)
    if not user_id:
        await interaction.followup.send("Please provide a valid user mention or ID.", ephemeral=True)
        return
    member_obj = interaction.guild.get_member(user_id)
    if not member_obj:
        try:
            member_obj = await interaction.guild.fetch_member(user_id)
        except:
            pass
    if not member_obj:
        await interaction.followup.send("User not found in this server.", ephemeral=True)
        return
    try:
        if interaction.guild.me.guild_permissions.kick_members:
            await member_obj.kick(reason=f"Kick by {interaction.user}: {reason}")
            await log_action(interaction.guild, f"{member_obj.mention} ({member_obj.id}) locally kicked by {interaction.user}. Reason: {reason}")
            await interaction.followup.send(f"{member_obj} has been kicked from the server.", ephemeral=True)
        else:
            await interaction.followup.send("I do not have permission to kick members.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to kick the user.", ephemeral=True)
        print(f"Error during kick: {e}")
        traceback.print_exc()

# local_ban Command
@bot.tree.command(name="local_ban", description="Ban a user from this server.")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def local_ban(interaction: discord.Interaction, member: str, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
        return
    user_id = extract_id_from_input(member)
    if not user_id:
        await interaction.followup.send("Please provide a valid user mention or ID.", ephemeral=True)
        return
    member_obj = interaction.guild.get_member(user_id)
    if not member_obj:
        try:
            member_obj = await interaction.guild.fetch_member(user_id)
        except:
            member_obj = None
    if not member_obj:
        try:
            user = await bot.fetch_user(user_id)
            if interaction.guild.me.guild_permissions.ban_members:
                await interaction.guild.ban(user, reason=f"Ban by {interaction.user}: {reason}")
                await log_action(interaction.guild, f"{user.mention} ({user.id}) locally banned by {interaction.user}. Reason: {reason}")
                await interaction.followup.send(f"{user} has been banned from the server.", ephemeral=True)
            else:
                await interaction.followup.send("I do not have permission to ban members.", ephemeral=True)
            return
        except:
            await interaction.followup.send("User not found or could not be fetched.", ephemeral=True)
            return
    try:
        if interaction.guild.me.guild_permissions.ban_members:
            await interaction.guild.ban(member_obj, reason=f"Ban by {interaction.user}: {reason}")
            await log_action(interaction.guild, f"{member_obj.mention} ({member_obj.id}) locally banned by {interaction.user}. Reason: {reason}")
            await interaction.followup.send(f"{member_obj} has been banned from the server.", ephemeral=True)
        else:
            await interaction.followup.send("I do not have permission to ban members.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("An error occurred while trying to ban the user.", ephemeral=True)
        print(f"Error during ban: {e}")
        traceback.print_exc()

# verify_all Command
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
        global_verified_role = discord.utils.find(lambda r: r.name.lower().strip() == GLOBAL_VERIFIED_ROLE_NAME.lower(), guild.roles)
        if not global_verified_role:
            await interaction.response.send_message(f"'{GLOBAL_VERIFIED_ROLE_NAME}' role not found in the server.", ephemeral=True)
            return
        await interaction.response.send_message("Starting the verification process for all members...", ephemeral=True)
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
                if global_verified_role not in member.roles:
                    await member.add_roles(global_verified_role)
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

# purge Command
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
    webhook_url = WEBHOOK_URL
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
                        if response.status not in [200, 204]:
                            response_text = await response.text()
                            print(f"Failed to send log file to the webhook: {response.status} {response_text}")
        except Exception as e:
            print(f"Error sending log file to the webhook: {e}")
    else:
        print("Webhook URL not set. Log file was not sent.")
    os.remove(log_filename)

# wipe_commands Command
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

bot.run(ZIONS_KEY_BOT_TOKEN)
