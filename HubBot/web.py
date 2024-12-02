import requests

WEBHOOK_URL = 'https://discord.com/api/webhooks/1311831249685450792/LDFdYZnQkB94uS_wQckDBQ9TNUPKwJxmMnCLcuFH5PQx2NbEvvQuDm-AqUT0T8hnPp51'

embed = {
    "title": "📜 Global Server Rules",
    "description": "Welcome to our Discord server! Please read and follow all the rules below to ensure a friendly and welcoming environment for everyone.",
    "color": 0x1ABC9C,  # Teal
    "fields": [
        {
            "name": "1️⃣ No Harassment, Hate Speech, or Discrimination",
            "value": "Treat all members with respect. Hate speech, slurs, targeted harassment, or discriminatory remarks against any group or individual are strictly prohibited. This maintains a safe and productive environment for everyone.",
            "inline": False
        },
        {
            "name": "2️⃣ No Spamming or Flooding",
            "value": "Avoid repetitive messages, excessive mentions, emojis, or other spam-like behavior in chats, channels, or DMs. This preserves server usability and ensures meaningful communication.",
            "inline": False
        },
        {
            "name": "3️⃣ No NSFW or Explicit Content",
            "value": "Sharing adult content, graphic violence, or other inappropriate material is forbidden unless it is explicitly allowed in designated NSFW channels (for users over 18). This protects minors and complies with Discord’s *Community Guidelines*.",
            "inline": False
        },
        {
            "name": "4️⃣ Follow Discord’s Terms of Service (ToS) and Community Guidelines",
            "value": "Do not engage in illegal activities, account sharing, phishing, or hacking. Ensure your behavior aligns with Discord’s official rules. This ensures compliance with Discord’s platform-wide policies.",
            "inline": False
        },
        {
            "name": "5️⃣ No Impersonation",
            "value": "Do not impersonate other users, moderators, or staff members. This includes using similar usernames, avatars, or claiming their identity. This prevents confusion and maintains trust in server moderation.",
            "inline": False
        },
        {
            "name": "6️⃣ No Doxxing or Sharing Private Information",
            "value": "Sharing someone’s personal information (e.g., addresses, phone numbers, emails) without their consent is strictly forbidden. This protects privacy and prevents harm to individuals.",
            "inline": False
        },
        {
            "name": "7️⃣ No Self-Promotion or Advertising Without Permission",
            "value": "Promoting your own content, servers, or businesses is not allowed unless explicitly permitted by the server’s rules or moderators. This maintains the focus of the community and prevents unwanted solicitation.",
            "inline": False
        },
        {
            "name": "8️⃣ Respect Channel Topics and Rules",
            "value": "Keep discussions relevant to the topic of the channel (e.g., no memes in serious channels). Always read pinned messages or rules. This keeps conversations organized and meaningful for all participants.",
            "inline": False
        },
        {
            "name": "9️⃣ No Malicious Bots, Scripts, or Exploits",
            "value": "Do not use bots, macros, or scripts to automate actions or exploit server systems. This protects the integrity of the server and prevents abuse.",
            "inline": False
        },
        {
            "name": "🔟 Use Appropriate Usernames and Avatars",
            "value": "Usernames and avatars must not include offensive, explicit, or otherwise inappropriate content. This ensures that profiles remain suitable for all audiences.",
            "inline": False
        },
        {
            "name": "⚖️ Enforcement Framework",
            "value": (
                "To ensure these rules are enforceable equally across all servers, we have implemented a universal penalty system.\n\n"
                "- *First Offense*: Warning or temporary mute.\n"
                "- *Second Offense*: Temporary ban or longer mute.\n"
                "- *Third Offense*: Permanent ban from the server.\n\n"
                "Penalties will vary based on the severity of the infraction (e.g., doxxing may warrant immediate banning whereas misusing channels may not). "
                "Please note that these penalties will be applied across *all* servers, regardless of which server(s) you committed these infractions in."
            ),
            "inline": False
        },
        {
            "name": "📌 Disclaimer",
            "value": (
                "These rules may be updated for any reason at any time, and the current lack of a given rule does not mean that any associated behavior will not be prohibited or enforced in the future. "
                "We will attempt to give notice of rule changes, but our efforts should not be considered a substitute for your own diligence."
            ),
            "inline": False
        }
    ],
    "footer": {
        "text": "Thank you for being a part of our community!",
        "icon_url": "https://example.com/footer_icon.png"
    },
    "thumbnail": {
        "url": "https://example.com/thumbnail.png"
    }
}

data = {
    "username": "Rules Bot",
    "avatar_url": "https://example.com/avatar.png",
    "embeds": [embed]
}

response = requests.post(WEBHOOK_URL, json=data)

if response.status_code == 204:
    print("Message sent successfully.")
else:
    print(f"Failed to send message: {response.status_code}")
    print(response.content)
