from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timezone
import traceback
import requests
import discord
import asyncio
import os










# Load environment variables
load_dotenv()










# Import custom modules for database and button handling
from db_connection import db_connection
from role_button import send_role_button, remove_button, recreate_buttons_on_startup
from ticket_button import send_ticket_button, delete_ticket_button, recreate_ticket_buttons










# Initialize Discord bot intents
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True










# Create bot instance
bot = commands.Bot(command_prefix="!", intents=intents)










# Webhook URL for logging actions
WEBHOOK_URL = os.getenv("logs_webhook_url")










# Function to log actions to a webhook
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










# Initialize the hub guild ID from environment variables
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

    # Recreate buttons on startup
    await recreate_buttons_on_startup(bot)
    await recreate_ticket_buttons(bot)

    # Start background tasks if they are not already running
    if not synchronize_verified_users.is_running():
        synchronize_verified_users.start()

    # Perform additional checks and setup
    try:
        conn = db_connection()
        cursor = conn.cursor()

        # Check all members in the hub guild
        hub_guild = bot.get_guild(hub_guild_id)
        if not hub_guild:
            print("Hub guild not found.")
        else:
            print(f"Checking members in {hub_guild.name} (ID: {hub_guild.id})...")
            for member in hub_guild.members:
                # Skip bots
                if member.bot:
                    continue

                # Check if the user exists in the database
                sql_check_user = "SELECT COUNT(*) FROM users WHERE discord_id = %s"
                cursor.execute(sql_check_user, (member.id,))
                result = cursor.fetchone()
                user_exists = result[0] > 0

                if not user_exists:
                    # Insert the user into the database
                    sql_insert_user = """
                    INSERT INTO users (discord_id, time_created, verify_status, username)
                    VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(sql_insert_user, (member.id, datetime.now(timezone.utc), 0, member.name))
                    conn.commit()
                    print(f"Added {member.name} (ID: {member.id}) to the database.")

        conn.close()
    except Exception as e:
        print(f'Failed to connect to database or process members: {e}')
        traceback.print_exc()










@bot.event
async def on_member_join(member):
    try:
        guild = member.guild

        # Ensure this is the hub guild
        if guild.id != hub_guild_id:
            print(f"Member {member} joined {guild.name}, but this is not the hub guild. Ignoring.")
            return

        print(f"New member joined: {member.name} (ID: {member.id})")

        # Skip bots
        if member.bot:
            print(f"Skipping bot: {member.name}")
            return

        # Connect to the database
        conn = db_connection()
        cursor = conn.cursor()

        # Check if the user already exists in the database
        sql_check_user = "SELECT COUNT(*) FROM users WHERE discord_id = %s"
        cursor.execute(sql_check_user, (member.id,))
        result = cursor.fetchone()
        user_exists = result[0] > 0

        if not user_exists:
            # Insert the user into the database
            sql_insert_user = """
            INSERT INTO users (discord_id, time_created, verify_status, username)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql_insert_user, (member.id, datetime.now(timezone.utc), 0, member.name))
            conn.commit()
            print(f"Added new member to the database: {member.name} (ID: {member.id})")
        else:
            print(f"Member {member.name} (ID: {member.id}) already exists in the database.")

        cursor.close()
        conn.close()

        # Optionally send a welcome message
        try:
            await member.send(f"Welcome to {guild.name}, {member.name}! Please verify to access the server.")
        except discord.Forbidden:
            print(f"Unable to send DM to {member.name} (ID: {member.id}).")

        # Wait for 3 seconds before creating the onboarding channel
        await asyncio.sleep(2)

        # Create the onboarding channel for the member
        onboarding_category_id = os.getenv("onboarding_category_id")
        if onboarding_category_id:
            category = guild.get_channel(int(onboarding_category_id))
            if category and isinstance(category, discord.CategoryChannel):
                # Create the channel in the specified category
                channel_name = f"welcome-{member.name}".lower().replace(" ", "-").replace("#", "").replace("@", "")
                onboarding_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    reason=f"Onboarding channel for {member.name}",
                    overwrites={
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        member: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    }
                )
                print(f"Created onboarding channel: {onboarding_channel.name} for {member.name}")

                # Create and send the welcome embed
                embed = discord.Embed(
                    title="Welcome to the Zions Gate Hub Server!",
                    description=(
                        f"Hello, {member.mention}, and welcome to **Zions Gate**, your gateway to a network of inspiring "
                        f"and faith-filled communities centered on **The Church of Jesus Christ of Latter-day Saints**.\n\n"
                        "We are thrilled to have you here! This server is the first step into a larger, vibrant network where "
                        "members and friends of the Church can explore gospel truths, build uplifting connections, and strengthen "
                        "their testimony of Jesus Christ."
                    ),
                    color=0x1E90FF  # A calming blue color for the embed
                )
                embed.add_field(
                    name="🌟 A Place of Connection and Growth:",
                    value=(
                        "Here at Zions Gate, you are stepping into a virtual gateway that connects you to an array of communities "
                        "designed to inspire, uplift, and strengthen your testimony. You’ll find spaces where Saints gather to study "
                        "the word of God, share their testimonies, and help one another walk the covenant path.\n\n"
                        "This is a unique opportunity to grow in understanding, build friendships rooted in gospel principles, and "
                        "feel the Savior’s love in every interaction. Whether you’re seeking spiritual guidance, scriptural insights, "
                        "or just a moment of peace in a bustling world, you’ll find a community waiting for you."
                    ),
                    inline=False
                )
                embed.add_field(
                    name="✨ A Spiritual Thought:",
                    value=(
                        "*\"And now, my beloved brethren, after ye have gotten into this straight and narrow path, I would ask if all is done? "
                        "Behold, I say unto you, Nay; for ye have not come thus far save it were by the word of Christ with unshaken faith in him, "
                        "relying wholly upon the merits of him who is mighty to save.\"*\n"
                        "– **2 Nephi 31:19**\n\n"
                        "Remember that as we press forward with faith, the Savior walks with us. This network is built to help us rely on Him more fully "
                        "and discover joy in every step of our journey."
                    ),
                    inline=False
                )
                embed.add_field(
                    name="💡 Why This Community Matters:",
                    value=(
                        "- **Fellowship**: Meet others who share your beliefs, values, and love for the gospel.\n"
                        "- **Learning**: Find resources, discussions, and opportunities to deepen your understanding of the scriptures and doctrine.\n"
                        "- **Service**: Participate in uplifting activities and events designed to strengthen individuals, families, and communities.\n"
                        "- **Growth**: Join a network where every interaction is an opportunity to build your testimony and draw closer to Christ."
                    ),
                    inline=False
                )
                embed.set_footer(
                    text="Welcome to Zions Gate! This is more than a server—it’s a gateway to Zion. 💙"
                )
                embed.set_image(
                    url="https://drive.google.com/uc?id=1XQ6fLWOj79IXR4zlfzhbXWDw97MplrNJ"
                )
                await onboarding_channel.send(embed=embed)
            else:
                print("Onboarding category not found or invalid.")
        else:
            print("Onboarding category ID not set in environment variables.")

    except Exception as e:
        print(f"Error in on_member_join for {member.name} (ID: {member.id}): {e}")
        traceback.print_exc()










# Slash command to verify a user
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










# Function to close verification chat after a delay
async def close_verification_chat_after_delay(channel, delay=60):
    print(f"close_verification_chat_after_delay: Waiting for {delay} seconds to close channel {channel.name} ({channel.id})")
    await asyncio.sleep(delay)
    try:
        if 1303165889344049183 == None:
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










# Background task to synchronize verified users
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










# Slash command to send a role button to a channel
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










# Slash command to remove a button by message ID
@bot.tree.command(name="remove_button", description="Remove a button by its message ID.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_remove_button(interaction: discord.Interaction, message_id: str):
    await remove_button(interaction, message_id)










# Slash command to send a ticket button to a channel
@bot.tree.command(name="send_ticket_button", description="Send a button to open a ticket.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_send_ticket_button(interaction: discord.Interaction, channel: discord.TextChannel):
    await send_ticket_button(interaction, channel)










# Slash command to delete a ticket button
@bot.tree.command(name="delete_ticket_button", description="Delete a ticket button from the channel and database.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_delete_ticket_button(interaction: discord.Interaction, message_id: str):
    await delete_ticket_button(interaction, message_id)









    
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


# Run the bot using the token from the environment variables
bot.run(os.getenv("hub_bot_token"))
