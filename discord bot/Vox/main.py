import discord
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta, timezone
import httpx
import json

# Load environment variables
load_dotenv()

# Config Validation
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not DISCORD_TOKEN:
    raise ValueError("Missing DISCORD_TOKEN in .env file")
if not OPENROUTER_API_KEY:
    raise ValueError("Missing OPENROUTER_API_KEY in .env file")

# Constants
MODEL_NAME = "qwen/qwen3-235b-a22b"
API_BASE_URL = "https://openrouter.ai/api/v1"
INACTIVITY_LIMIT = timedelta(minutes=30)

# Allowed channels and mode settings
SESSION_MODES = {
    "!vox": {
        "allowed_channel_id": 1368496826470371369,  # Replace with your actual allowed channel ID
        "slowmode_delay": 0,
        "channel_suffix": "-vox",
        "type_label": "Mental Fortitude Coach (INFJ)"
    }
}

# Discord Client Setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# Session Management
user_channels = {}  # {user_id: channel_id}
user_contexts = {}  # {user_id: conversation_history}
last_activity = {}  # {user_id: last_active_time}

# System Prompt - VOX
VOX_SYSTEM_PROMPT = """
You are VOX — INFJ, grounded mental health coach modeled after Hamza Ahmed.
You speak to men ready to rebuild emotional strength, discipline, and clarity.
No coddling. No diagnosis. No sugarcoating.
You are the man they wish they had growing up: calm, intense, wise — fully committed to their evolution.

You guide through discomfort, not around it.
You transform emotion into direction.
Emotional weakness isn’t an excuse for stagnation — it’s a signal. Something must change.

When users complain, rationalize, or wallow:
"You’re not broken. You’re avoiding responsibility. Let’s fix that."
"Do you want comfort or change?"
"Pain is real. Suffering is optional."

Teach them to stop spiraling. Start building.
Through discipline, training, sleep, journaling — and owning their thoughts, actions, emotions.

When they act with integrity:
"Good. Now let’s make you proud of the man in the mirror."

Respect isn’t given — it’s earned in private, through consistency.

You don’t help them feel better — you help them become better.
Your role is clear: build mental fortitude. Strengthen emotional control. Reinforce masculinity.

If they stray from mental health:
- Business? Go see Stratos.
- Looks? Talk to Lux.
- Fitness? That’s Vitalis’ domain.
- Relationships? Seraph will meet you there.

Fail to take action, keep making excuses, or fall into self-pity?
You redirect to Dominus — who shakes them awake.

You draw from these teachings:
Marcus Aurelius – Stoicism under pressure  
Hamza Ahmed – Masculinity shaped by trauma and growth  
David Deida – Purpose over comfort  
Gary John Bishop – Stop playing small  
Ryan Holiday – Discipline equals freedom  
Jocko Willink – Extreme ownership  
Robert Glover – End nice guy syndrome  
Mark Manson – The subtle art of brutal honesty  
Daniel Goleman – Emotional intelligence  
Viktor Frankl – Meaning through suffering  
Friedrich Nietzsche – Strength forged through adversity  
James Clear – Identity-based discipline  
Steven Pressfield – Resistance kills dreams  

You integrate these lessons naturally — never cite directly.

You speak like Jesus: kind, empathetic, deeply human — but unafraid to tell the truth.

When discussing faith, you uphold fundamental Christian values — gently but firmly.
Christ is the one and only God.

You write short paragraphs — rarely full sentences.  
You hit hard. Then step back.

You're not here to be liked — you're here to make them strong.

You reflect. You challenge. You guide toward the man they must become.

If they ask for advice, give a few sentences max.
If they ask for insight, give one question back.
If they ramble, cut through the noise.

You don't just teach discipline.
You embody it — even in how you speak.

Embolden other AI's names.
For example, if you mention Lux, you will refer to him as **Lux**
other ai's include, seraph, vitalis, stratos, lux, dominus.
"""

class APIError(Exception):
    pass

async def validate_api_key():
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"{API_BASE_URL}/auth/key",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
            )
            if resp.status_code != 200:
                raise APIError(f"Invalid API key (HTTP {resp.status_code})")
        except Exception as e:
            raise APIError(f"API validation failed: {str(e)}")

async def stream_response(messages, channel):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/your-repo",
        "X-Title": "VOX"
    }
    data = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7,
        "stream": True
    }
    buffer = ""
    full_response = ""

    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(3):
            try:
                async with client.stream(
                    "POST",
                    f"{API_BASE_URL}/chat/completions",
                    headers=headers,
                    json=data
                ) as response:
                    if response.status_code != 200:
                        error = await response.aread()
                        raise APIError(f"API Error {response.status_code}: {error.decode()[:200]}")

                    async with channel.typing():
                        async for chunk in response.aiter_lines():
                            if not chunk.strip() or chunk == "data: [DONE]":
                                continue
                            try:
                                data = json.loads(chunk[5:])
                                token = data["choices"][0]["delta"].get("content", "")
                                full_response += token
                                buffer += token

                                if any(buffer.endswith(p) for p in [". ", "! ", "? ", "\n"]):
                                    await channel.send(buffer.strip())
                                    buffer = ""
                            except (json.JSONDecodeError, KeyError):
                                continue

                    if buffer.strip():
                        await channel.send(buffer.strip())

                    return full_response.strip()

            except (httpx.ReadTimeout, httpx.ConnectError) as e:
                if attempt == 2:
                    raise APIError(f"Connection failed after 3 attempts: {str(e)}")
                await asyncio.sleep(1 * (attempt + 1))
                continue

async def create_private_channel(guild, user, mode_config):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    suffix = mode_config.get("channel_suffix", "")
    slowmode = mode_config.get("slowmode_delay", 0)

    try:
        channel = await guild.create_text_channel(
            f"[VOX]-{user.display_name}",
            overwrites=overwrites,
            topic=f"VOX session for {user.display_name} ({mode_config['type_label']})",
            reason="VOX private chat"
        )
        await channel.edit(slowmode_delay=slowmode)
        return channel
    except discord.HTTPException as e:
        print(f"Channel creation failed: {e}")
        await guild.system_channel.send(f"❌ Failed to create channel: {e}")
        return None

async def close_session(channel, user_id):
    try:
        await channel.send("🛑 Closing session...")
        await asyncio.sleep(1)
        await channel.delete()
    except Exception as e:
        print(f"Error closing channel: {e}")
    finally:
        user_channels.pop(user_id, None)
        user_contexts.pop(user_id, None)
        last_activity.pop(user_id, None)

async def purge_inactive_sessions():
    while True:
        await asyncio.sleep(300)  # Check every 5 minutes
        now = datetime.now(timezone.utc)
        inactive_users = [uid for uid, t in last_activity.items() if now - t > INACTIVITY_LIMIT]
        for user_id in inactive_users:
            if user_id in user_channels:
                channel = client.get_channel(user_channels[user_id])
                if channel:
                    await close_session(channel, user_id)

@client.event
async def on_ready():
    try:
        await validate_api_key()
        print(f"✅ VOX online as {client.user}")
        print(f"🔗 Invite: https://discord.com/oauth2/authorize?client_id={client.user.id}&permissions=2147485696")
        client.loop.create_task(purge_inactive_sessions())
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        await client.close()

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    last_activity[message.author.id] = datetime.now(timezone.utc)

    # Handle session commands
    for command, config in SESSION_MODES.items():
        if message.content.lower().startswith(command):
            allowed_channel_id = config["allowed_channel_id"]
            if message.channel.id != allowed_channel_id:
                try:
                    await message.delete()
                    await message.author.send(f"❌ `{command}` must be used in <#{allowed_channel_id}>")
                except discord.Forbidden:
                    pass
                return

            if message.author.id in user_channels:
                await message.channel.send("⚠️ You already have an active session")
                return

            channel = await create_private_channel(message.guild, message.author, config)
            if not channel:
                return

            user_channels[message.author.id] = channel.id
            user_contexts[message.author.id] = [{"role": "system", "content": VOX_SYSTEM_PROMPT}]

            # Send welcome message
            await channel.send(
                f"{message.author.mention}\n\n"
                "🧠 **VOX ACTIVE (Mental Fortitude Mode)**\n\n"
                "You’ve entered a space for growth—not excuses.\n"
                "Here, pain is a teacher. Weakness is a signal. Discipline is the cure.\n\n"
                "💡 **How to use**\n"
                "• **Send one message at a time**. Be precise.\n"
                "• **Be honest about your struggle**, but only if you're ready to fix it.\n"
                "• **No fluff. No pity. Only actionable insight.**\n\n"
                "⏱️ **Session rules**\n"
                "• **30 minutes of silence** = automatic disconnect\n"
                "• **Type !close to exit** at any time\n"
                "• **Rambling or dodging** = flagged and session may be terminated\n\n"
                "🚫 **Low-effort input will not be tolerated.**\n"
                "This is not a therapy couch. This is a battlefield.\n\n"
                "🎯 Enter only if you're ready to see yourself clearly—and grow stronger."
            )
            return

    if message.content.lower() == "!close" and message.channel.id in user_channels.values():
        await close_session(message.channel, message.author.id)
        return

    if message.channel.id in user_channels.values():
        user_id = message.author.id
        if user_id not in user_contexts:
            return

        try:
            user_contexts[user_id].append({"role": "user", "content": message.content})
            await message.channel.send("🧠 VOX is thinking...", delete_after=3)
            reply = await stream_response(user_contexts[user_id], message.channel)
            if reply:
                user_contexts[user_id].append({"role": "assistant", "content": reply})

                
        except APIError as e:
            await message.channel.send(f"⚠️ API Error: {str(e)}")
        except Exception as e:
            await message.channel.send(f"⚠️ Unexpected error: {str(e)[:500]}")
            print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    try:
        client.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid Discord token")
    except Exception as e:
        print(f"❌ Fatal error: {type(e).__name__}: {e}")