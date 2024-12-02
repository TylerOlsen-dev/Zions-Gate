import requests

WEBHOOK_URL = 'https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN'

BOT_NAME = 'Welcome Bot'
BOT_AVATAR_URL = 'https://example.com/avatar.png'

EMBED_IMAGE_URL = ''


VERIFICATION_CHANNEL_MENTION = '<#YOUR_VERIFICATION_CHANNEL_ID>'

embed = {
    "title": "👋 Welcome to the Hub!",
    "description": (
        "We're excited to have you join our community hub! This server serves as the central point for all our connected servers, "
        "allowing members to verify themselves and gain access to various communities we manage.\n\n"
        "**Why Verify?**\n"
        "Verification helps us ensure a safe and secure environment for all members across our network of servers. "
        "By verifying, you'll gain access to exclusive channels, events, and be able to interact with other verified members.\n\n"
        "**How to Verify**\n"
        "To get started, please head over to "
        f"{VERIFICATION_CHANNEL_MENTION} and follow the instructions provided. Our staff will assist you with the verification process.\n\n"
        "**Need Assistance?**\n"
        "If you have any questions or encounter any issues during verification, feel free to reach out to a staff member directly."
    ),
    "color": 0x2ECC71,  # Green
    "footer": {
        "text": "Thank you for joining the Hub!",
        "icon_url": BOT_AVATAR_URL if BOT_AVATAR_URL else None
    },
    "thumbnail": {
        "url": "https://example.com/server_logo.png"
    },
    "image": {
        "url": EMBED_IMAGE_URL if EMBED_IMAGE_URL else None
    }
}


embed = {k: v for k, v in embed.items() if v is not None}


data = {
    "username": BOT_NAME,  
    "avatar_url": BOT_AVATAR_URL,  
    "embeds": [embed]
}

response = requests.post(WEBHOOK_URL, json=data)

if response.status_code == 204:
    print("Welcome message sent successfully.")
else:
    print(f"Failed to send message: {response.status_code}")
    print(response.content)
