import discord
import aiohttp
import asyncio
from db_connection import db_connection  # This is your custom database connection file

# Enable the members intent so that the bot can see member data
intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)

async def fetch_image(url: str):
    """
    Asynchronously fetch binary image data from a URL.
    Returns None if the URL is invalid or if the request fails.
    """
    if not url:
        return None
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()
    return None

async def add_member_to_users(member: discord.Member):
    """
    Checks if a member exists in the Users table and adds them if they don't.
    
    Data inserted includes:
      - User_ID: Discord user ID.
      - User_Name: Formatted as "name#discriminator".
      - Account_Age: The date the Discord account was created (formatted as YYYY-MM-DD).
      - User_pfp: The binary data of the user's avatar.
      - User_Banner: The binary data of the user's banner (if available).
      - Global_Banned: Set to "False" by default.
    """
    user_id = member.id
    user_name = f"{member.name}#{member.discriminator}"
    account_age = member.created_at.strftime('%Y-%m-%d')
    avatar_url = member.avatar.url if member.avatar else None

    # Try to fetch the user's banner (if available)
    try:
        user_obj = await client.fetch_user(member.id)
        banner_url = user_obj.banner.url if user_obj.banner else None
    except Exception as e:
        print(f"Could not fetch banner for {user_name}: {e}")
        banner_url = None

    try:
        # Establish a connection using your db_connection() function
        connection = db_connection()
        cursor = connection.cursor()

        # Check if the user already exists in the Users table
        select_query = "SELECT User_ID FROM Users WHERE User_ID = %s"
        cursor.execute(select_query, (user_id,))
        result = cursor.fetchone()

        if result is None:
            # Download the avatar and banner images (if available)
            avatar_data = await fetch_image(avatar_url)
            banner_data = await fetch_image(banner_url)

            # Prepare the insert query
            insert_query = """
                INSERT INTO Users 
                (User_ID, User_Name, Account_Age, User_pfp, User_Banner, Global_Banned)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            data_tuple = (user_id, user_name, account_age, avatar_data, banner_data, "False")
            cursor.execute(insert_query, data_tuple)
            connection.commit()
            print(f"Added new user: {user_name} (ID: {user_id}) to Users table.")
        else:
            print(f"User {user_name} (ID: {user_id}) already exists in Users table.")

        cursor.close()
        connection.close()
    except Exception as e:
        print("Database error:", e)

@client.event
async def on_member_join(member: discord.Member):
    """Triggered when a new member joins a guild."""
    await add_member_to_users(member)

@client.event
async def on_ready():
    """Triggered when the bot is ready. Iterates over all guild members to add any missing users."""
    print(f"Bot logged in as {client.user}")
    for guild in client.guilds:
        print(f"Checking members in guild: {guild.name}")
        # Ensure that the member cache is populated.
        for member in guild.members:
            await add_member_to_users(member)

# Replace 'YOUR_BOT_TOKEN' with your actual Discord bot token.
client.run('')