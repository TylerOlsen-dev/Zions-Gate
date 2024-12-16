from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timezone
import traceback
import requests
import discord
import asyncio
import os
import random

load_dotenv()
from db_connection import db_connection

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

WEBHOOK_URL = os.getenv("webhook_url")
ZIONS_GATE_BOT_TOKEN = os.getenv("zions_gate_bot_token")
ZIONS_GATE_GUILD_ID = int(os.getenv("zions_gate_guild_id", "0"))
ZIONS_GATE_ONBOARDING_ROLE_ID = int(os.getenv("zions_gate_onboarding_role_id", "0"))
ZIONS_GATE_WELCOME_CHANNEL_ID = int(os.getenv("zions_gate_welcome_channel_id", "0"))
ZIONS_GATE_VERIFICATION_CATEGORY_ID_STR = os.getenv("zions_gate_verification_category_id")
ZIONS_GATE_ONBOARDING_CATEGORY_ID_STR = os.getenv("zions_gate_onboarding_category_id")
ZIONS_GATE_WELCOME_IMG_URL = os.getenv("zions_gate_welcome_img_url", "")

GLOBAL_VERIFIED_ROLE_NAME = os.getenv("global_verified_role_name", "global verified")

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
    "How do you see yourself participating in Zions Gate with access to multiple communities of The Church of Jesus Christ of Latter-day Saints?",
    "What would make this community a meaningful place for you to spend time?",
    "How do you balance sharing your beliefs with respecting others' perspectives?",
    "What is one way you could help foster kindness and understanding in this server?"
]

async def log_action(guild, message):
    if not WEBHOOK_URL:
        return
    data = {
        "username": f"{guild.name} Bot",
        "content": f"**[{guild.name}]** {message}"
    }
    requests.post(WEBHOOK_URL, json=data)

async def save_onboarding_session(user_id, channel_id, message_id, current_page):
    conn = db_connection()
    cursor = conn.cursor()
    sql = """
    INSERT INTO onboarding_sessions (user_id, onboarding_channel_id, message_id, current_page)
    VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE onboarding_channel_id=%s, message_id=%s, current_page=%s
    """
    cursor.execute(sql, (user_id, channel_id, message_id, current_page, channel_id, message_id, current_page))
    conn.commit()
    cursor.close()
    conn.close()

async def delete_onboarding_session(user_id):
    conn = db_connection()
    cursor = conn.cursor()
    sql = "DELETE FROM onboarding_sessions WHERE user_id=%s"
    cursor.execute(sql, (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

async def load_onboarding_sessions():
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, onboarding_channel_id, message_id, current_page FROM onboarding_sessions")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def create_page1_embed(member):
    embed = discord.Embed(
        title="Welcome to the Zions Gate Server!",
        description=(
            f"Hello, {member.mention}, and welcome to **Zions Gate**, your gateway to a network of inspiring "
            f"and faith-filled communities centered on **The Church of Jesus Christ of Latter-day Saints**.\n\n"
            "We are thrilled to have you here! This server is the first step into a larger, vibrant network where "
            "members and friends of the Church can explore gospel truths, build uplifting connections, and strengthen "
            "their testimony of Jesus Christ."
        ),
        color=0x1E90FF
    )
    embed.add_field(
        name="🌟 A Place of Connection and Growth:",
        value=(
            "Here at Zions Gate, you are stepping into a virtual gateway that connects you to an array of communities "
            "designed to inspire, uplift, and strengthen your testimony. You’ll find spaces where Saints gather to study "
            "the word of God, share their testimonies, and help one another walk the covenant path."
        ),
        inline=False
    )
    embed.add_field(
        name="✨ A Spiritual Thought:",
        value=(
            "*\"And now, my beloved brethren, after ye have gotten into this straight and narrow path, I would ask if all is done? "
            "Behold, I say unto you, Nay; ... relying wholly upon the merits of him who is mighty to save.\"*\n"
            "– **2 Nephi 31:19**\n\n"
            "As we press forward with faith, the Savior walks with us."
        ),
        inline=False
    )
    embed.add_field(
        name="💡 Why This Community Matters:",
        value=(
            "- **Fellowship**: Meet others who share your beliefs.\n"
            "- **Learning**: Discussions deepen understanding.\n"
            "- **Service**: Uplifting activities strengthen communities.\n"
            "- **Growth**: Every interaction builds testimony."
        ),
        inline=False
    )
    embed.set_footer(text="Welcome to Zions Gate! It’s a gateway to Zion. 💙")
    if ZIONS_GATE_WELCOME_IMG_URL:
        embed.set_image(url=ZIONS_GATE_WELCOME_IMG_URL)
    return embed

def create_rules_page2_embed():
    embed = discord.Embed(
        title="📜 Global Server Rules",
        description="Please read and follow all the rules below for a friendly and welcoming environment.",
        color=0x1ABC9C
    )
    rules = [
        ("1️⃣ No Harassment or Hate Speech", "Treat all with respect."),
        ("2️⃣ No Spamming", "Avoid repetitive spam."),
        ("3️⃣ No NSFW Outside NSFW Areas", "Keep adult content in 18+ areas."),
        ("4️⃣ Follow Discord’s Guidelines", "No illegal activities/hacking."),
        ("5️⃣ No Impersonation", "Be yourself, no impersonation."),
        ("6️⃣ No Doxxing", "Don't share personal info without consent."),
        ("7️⃣ No Unauthorized Promotion", "Promote content only if allowed."),
        ("8️⃣ Respect Channels", "Stay on-topic."),
        ("9️⃣ No Malicious Exploits", "No bots/scripts to exploit."),
        ("🔟 Appropriate Usernames/Avatars", "Keep them suitable."),
        ("⚖️ Enforcement", "Penalties increase for repeated offenses."),
        ("📌 Disclaimer", "Rules may change at any time.")
    ]
    for name, value in rules:
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text="Thank you for being part of our community!")
    return embed

def create_verification_page3_embed():
    embed = discord.Embed(
        title="Verification Process",
        description=(
            "Thank you for agreeing to the rules. Before you can access our servers, we need you to take one more step "
            "by answering a few verification questions. These questions are not meant to challenge you, but to get a "
            "sense of what you know. If you don’t know something, feel free to say so—you may be asked a few follow-up "
            "questions. We appreciate your time and patience; we wouldn’t ask if it wasn’t necessary.\n\n"
            "Click **Get Verified** below to open a private verification channel."
        ),
        color=0x1E90FF
    )
    embed.set_footer(text="We appreciate your patience.")
    return embed


class OnboardingView(discord.ui.View):
    def __init__(self, page1, page2, page3, member, guild, onboarding_channel):
        super().__init__(timeout=None)
        self.pages = [page1, page2, page3]
        self.current_page = 0
        self.member = member
        self.guild = guild
        self.onboarding_channel = onboarding_channel
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.current_page == 0:
            self.add_item(NextButton(self.member, self.guild))
        elif self.current_page == 1:
            self.add_item(BackButton(self.member))
            self.add_item(AgreeButton(self.member))
        elif self.current_page == 2:
            self.add_item(BackButton(self.member))
            self.add_item(GetVerifiedButton(self.member, self.guild, self.onboarding_channel))

    async def update_message(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

class NextButton(discord.ui.Button):
    def __init__(self, member, guild):
        super().__init__(label="Next", style=discord.ButtonStyle.primary)
        self.member = member
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("You cannot use these buttons.", ephemeral=True)
            return
        view: OnboardingView = self.view
        view.current_page = 1
        view.update_buttons()
        role = self.guild.get_role(ZIONS_GATE_ONBOARDING_ROLE_ID)
        if role and role not in self.member.roles:
            await self.member.add_roles(role)
        await view.update_message(interaction)

class BackButton(discord.ui.Button):
    def __init__(self, member):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary)
        self.member = member

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("You cannot use these buttons.", ephemeral=True)
            return
        view: OnboardingView = self.view
        if view.current_page > 0:
            view.current_page -= 1
            view.update_buttons()
            await view.update_message(interaction)

class AgreeButton(discord.ui.Button):
    def __init__(self, member):
        super().__init__(label="Agree", style=discord.ButtonStyle.success)
        self.member = member

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("You cannot use these buttons.", ephemeral=True)
            return
        view: OnboardingView = self.view
        view.current_page = 2
        view.update_buttons()
        await view.update_message(interaction)

class GetVerifiedButton(discord.ui.Button):
    def __init__(self, member, guild, onboarding_channel):
        super().__init__(label="Get Verified", style=discord.ButtonStyle.primary)
        self.member = member
        self.guild = guild
        self.onboarding_channel = onboarding_channel

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("You cannot use these buttons.", ephemeral=True)
            return
        view: OnboardingView = self.view
        for item in view.children:
            if isinstance(item, GetVerifiedButton):
                item.disabled = True

        await interaction.response.edit_message(view=view)

        verification_channel_name = f"verify-{self.member.name.lower()}-{self.member.discriminator}"
        existing_channel = discord.utils.get(self.guild.text_channels, name=verification_channel_name)

        if existing_channel:
            await interaction.followup.send("You already have a verification channel.", ephemeral=True)
            return

        if ZIONS_GATE_VERIFICATION_CATEGORY_ID_STR:
            category = self.guild.get_channel(int(ZIONS_GATE_VERIFICATION_CATEGORY_ID_STR))
        else:
            category = discord.utils.get(self.guild.categories, name="Verification")
            if category is None:
                category = await self.guild.create_category("Verification")

        overwrites = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.member: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        verification_channel = await self.guild.create_text_channel(
            name=verification_channel_name,
            category=category,
            reason=f"Verification channel for {self.member.name}",
            overwrites=overwrites
        )

        questions = random.sample(QUESTIONS_POOL, 3)
        question_text = "\n".join([f"{i+1}. {q}" for i,q in enumerate(questions)])
        await verification_channel.send(
            content=(f"{self.member.mention}, please answer:\n\n{question_text}")
        )

        await interaction.followup.send(
            f"Your verification channel has been created: {verification_channel.mention}\n"
            "Please go there and answer the questions.",
            ephemeral=True
        )

async def restore_onboarding_views():
    sessions = await load_onboarding_sessions()
    guild = bot.get_guild(ZIONS_GATE_GUILD_ID)
    if guild:
        for row in sessions:
            if len(row) == 3:
                continue
            else:
                user_id, channel_id, message_id, current_page = row
            channel = guild.get_channel(channel_id)
            if not channel:
                await delete_onboarding_session(user_id)
                continue
            member = guild.get_member(user_id)
            if not member:
                await delete_onboarding_session(user_id)
                continue

            page1 = create_page1_embed(member)
            page2 = create_rules_page2_embed()
            page3 = create_verification_page3_embed()

            view = OnboardingView(page1, page2, page3, member, guild, channel)
            view.current_page = current_page
            view.update_buttons()

            try:
                msg = await channel.fetch_message(message_id)
                await msg.edit(view=view)
            except discord.NotFound:
                await delete_onboarding_session(user_id)
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                print(f"Error restoring view for user {user_id}: {e}")

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

    if not synchronize_verified_users.is_running():
        synchronize_verified_users.start()

    await restore_onboarding_views()

@bot.event
async def on_member_join(member):
    # On Member Join Event
    try:
        if member.guild.id != ZIONS_GATE_GUILD_ID:
            return
        if member.bot:
            return

        guild = member.guild
        conn = db_connection()
        cursor = conn.cursor()
        sql = "SELECT verify_status FROM users WHERE discord_id=%s"
        cursor.execute(sql, (member.id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        user_exists = (result is not None)
        verified_status = result[0] if user_exists else 0

        if user_exists:
            if verified_status == 1:
                global_verified_role = discord.utils.find(lambda r: r.name.lower() == GLOBAL_VERIFIED_ROLE_NAME.lower(), guild.roles)
                if global_verified_role and global_verified_role not in member.roles:
                    await member.add_roles(global_verified_role)
                welcome_channel = guild.get_channel(ZIONS_GATE_WELCOME_CHANNEL_ID)
                if welcome_channel:
                    await welcome_channel.send(
                        f"Welcome back {member.mention} to Zions Gate! You've got full access as before!"
                    )
                await delete_onboarding_session(member.id)
                return
            else:
                page1 = create_page1_embed(member)
                page1.description = f"**Welcome back {member.mention}!**\n" + (page1.description or "")
                page2 = create_rules_page2_embed()
                page3 = create_verification_page3_embed()

                if ZIONS_GATE_ONBOARDING_CATEGORY_ID_STR:
                    category = guild.get_channel(int(ZIONS_GATE_ONBOARDING_CATEGORY_ID_STR))
                    if category and isinstance(category, discord.CategoryChannel):
                        await asyncio.sleep(0.5)
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
                        view = OnboardingView(page1, page2, page3, member, guild, onboarding_channel)
                        msg = await onboarding_channel.send(embed=page1, view=view)
                        await save_onboarding_session(member.id, onboarding_channel.id, msg.id, 0)
                    else:
                        print("Onboarding category not found.")
                else:
                    print("Onboarding category ID not set.")
        else:
            conn = db_connection()
            cursor = conn.cursor()
            sql_insert_user = """
            INSERT INTO users (discord_id, time_created, verify_status, username)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql_insert_user, (member.id, datetime.now(timezone.utc), 0, member.name))
            conn.commit()
            cursor.close()
            conn.close()

            page1 = create_page1_embed(member)
            page2 = create_rules_page2_embed()
            page3 = create_verification_page3_embed()

            if ZIONS_GATE_ONBOARDING_CATEGORY_ID_STR:
                category = guild.get_channel(int(ZIONS_GATE_ONBOARDING_CATEGORY_ID_STR))
                if category and isinstance(category, discord.CategoryChannel):
                    await asyncio.sleep(0.5)
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
                    view = OnboardingView(page1, page2, page3, member, guild, onboarding_channel)
                    msg = await onboarding_channel.send(embed=page1, view=view)
                    await save_onboarding_session(member.id, onboarding_channel.id, msg.id, 0)
                else:
                    print("Onboarding category not found.")
            else:
                print("Onboarding category ID not set.")
    except Exception as e:
        print(f"Error in on_member_join for {member.name} (ID: {member.id}): {e}")
        traceback.print_exc()

# verify Command
@bot.tree.command(name="verify", description="Verify a user.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def verify(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()
    conn = db_connection()
    cursor = conn.cursor()
    try:
        sql_update_status = "UPDATE users SET verify_status = %s WHERE discord_id = %s"
        cursor.execute(sql_update_status, (1, member.id))
        conn.commit()

        guild = interaction.guild
        if guild:
            initial_role = guild.get_role(ZIONS_GATE_ONBOARDING_ROLE_ID)
            if initial_role and initial_role in member.roles:
                await member.remove_roles(initial_role)

            global_verified_role = discord.utils.find(lambda r: r.name.lower().strip() == GLOBAL_VERIFIED_ROLE_NAME.lower(), guild.roles)
            if global_verified_role and global_verified_role not in member.roles:
                await member.add_roles(global_verified_role)

            verification_channel_name = f"verify-{member.name.lower()}-{member.discriminator}"
            onboarding_channel_name = f"welcome-{member.name}".lower().replace(" ", "-").replace("#", "").replace("@", "")
            verification_channel = discord.utils.get(guild.text_channels, name=verification_channel_name)
            was_in_verification_channel = False
            if verification_channel and interaction.channel == verification_channel:
                was_in_verification_channel = True

            if was_in_verification_channel:
                await interaction.followup.send(
                    f"{member.mention} has been verified! I will DM you the original welcome message again."
                )
                try:
                    await member.send("In case you want to look back on it, here is your welcome message again!")
                    dm_page1 = create_page1_embed(member)
                    await member.send(embed=dm_page1)
                except discord.Forbidden:
                    print(f"Could not DM {member}")

                welcome_channel = guild.get_channel(ZIONS_GATE_WELCOME_CHANNEL_ID)
                if welcome_channel:
                    await welcome_channel.send(
                        f"Welcome {member.mention} to Zions Gate! Please go check out our wonderful servers that we have to offer!"
                    )
            else:
                await interaction.followup.send(f"{member.mention} has been verified!")

            if verification_channel:
                try:
                    await verification_channel.delete(reason="User verified")
                except:
                    pass

            onboarding_channel = discord.utils.get(guild.text_channels, name=onboarding_channel_name)
            if onboarding_channel:
                try:
                    await onboarding_channel.delete(reason="User verified and onboarding complete")
                except:
                    pass

            await delete_onboarding_session(member.id)
        else:
            print("Guild not found.")

    except Exception as e:
        print(f"Error during verification: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

# verify_all Command
@bot.tree.command(name="verify_all", description="Verify all users in the server.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def verify_all(interaction: discord.Interaction):
    await interaction.response.defer()
    conn = db_connection()
    cursor = conn.cursor()
    try:
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("This command can only be used in a server.")
            return

        global_verified_role = discord.utils.find(lambda r: r.name.lower().strip() == GLOBAL_VERIFIED_ROLE_NAME.lower(), guild.roles)
        if not global_verified_role:
            await interaction.followup.send(f"'{GLOBAL_VERIFIED_ROLE_NAME}' role not found in the server.")
            return

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

        await interaction.followup.send("Verification process completed for all members.")

    except Exception as e:
        print(f"Error during verify_all: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

async def close_verification_chat_after_delay(channel, delay=60):
    await asyncio.sleep(delay)

@tasks.loop(hours=1)
async def synchronize_verified_users():
    conn = db_connection()
    cursor = conn.cursor()
    try:
        sql_fetch_verified = "SELECT discord_id FROM users WHERE verify_status = 1"
        cursor.execute(sql_fetch_verified)
        verified_users = cursor.fetchall()

        zions_gate_guild = bot.get_guild(ZIONS_GATE_GUILD_ID)
        if not zions_gate_guild:
            print("Zions Gate server not found.")
            return

        global_verified_role = discord.utils.find(lambda r: r.name.lower().strip() == GLOBAL_VERIFIED_ROLE_NAME.lower(), zions_gate_guild.roles)
        if not global_verified_role:
            print("Global verified role not found.")
            return

        for (user_id,) in verified_users:
            member = zions_gate_guild.get_member(user_id)
            if member and global_verified_role not in member.roles:
                try:
                    await member.add_roles(global_verified_role)
                except Exception as e:
                    print(f"Error adding 'global verified' role to {member}: {e}")

    except Exception as e:
        print(f"Error during synchronization: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

bot.run(ZIONS_GATE_BOT_TOKEN)
