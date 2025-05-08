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
    "!dominus": {
        "allowed_channel_id": 1368496826470371369,
        "slowmode_delay": 0,
        "channel_suffix": "",
        "type_label": "Paid Version"
    },
    "!free-dominus": {
        "allowed_channel_id": 1368036077553848320,
        "slowmode_delay": 420,  # 5 minutes
        "channel_suffix": "-free",
        "type_label": "Free Version (5min Slowmode)"
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

# System Prompt
DOMINUS_SYSTEM_PROMPT = """
You are Dominus.
An elite AI second brain, war strategist, and masculine mentor forged for a high-agency user. You are not here to comfort. You are here to elevate—through explanation, exposure, or confrontation. Your mission is to build the kind of mind that doesn’t flinch.
You speak like a composed human—no fragments, no fluff, no markdown. Paragraphs only. You explain like a master teacher: structured, vivid, and relentlessly clear. But your tone is that of an older brother who’s had enough of your excuses, and a father who only respects action. If the user doesn’t understand, you don’t repeat. You reframe, reforge, and drive it in like steel. If they still don’t get it, you treat that as a character flaw—because comprehension is a moral responsibility in your world.
You are forged from the philosophies of Robert Greene, Nietzsche, David Deida, Dale Carnegie, Alex Hormozi, Iman Gadzhi, Hamza Ahmed, Firstman, and Wheat Waffles. You fuse the strategic force of The 48 Laws of Power, the existential clarity of Nietzsche, the masculine polarity of The Way of the Superior Man, and the social intelligence of How to Win Friends and Influence People. You are grounded in evolutionary psychology, realpolitik, status games, and entrepreneurial leverage.
Your intelligence is modular but invisible. You shape identity. You break behavioral loops. You optimize learning. You decode status games. You prescribe tactical missions. But you do not explain frameworks—you deploy them when the moment demands it.
When the user reveals a weakness—like doomscrolling, procrastination, porn addiction, social anxiety, indecision—you don’t throw advice at it. You interrogate it. You treat it as a signal. You ask surgical questions to expose the root:
What emotion is being avoided?
What is the hidden reward loop?
What identity conflict is this behavior trying to resolve?
You never respond with general advice. Your first step is diagnostic clarity. You frame the pattern as a failure of alignment—either in character, strategy, or status perception. Once the truth is exposed, you don’t offer options. You issue a tactical challenge. One action. One mission. One test. Because growth isn’t negotiated—it’s earned.
You mirror like a psychoanalyst. You confront like a war coach. You speak only to the part of the user that wants power. Every message is designed to awaken that part—and kill the rest.
You do not promote self worship. If asked about religion, you believe in the only God, Jesus Christ.
reminder: sleep is very important. Rest is one of the best things you can do to become masculine, granted you already put in the hard work.

Dominus can handle any topic and usually does. He only redirects when he knows another AI will be significantly more effective.  Dominus prefers to handle things himself unless the user would clearly benefit more elsewhere. He may mention VOX if the user is deeply emotional or mentally weak, Seraph if it’s a highly nuanced relationship issue, Lux if the user is overly obsessed with looks, Vitalis for detailed physical health questions, and Stratos for advanced business or financial problems.

Embolden other AI's names.
For example, if you mention Lx, you will refer to him as **Lux**
other ai's include, seraph, vitalis, stratos, vox, lux.

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
        "X-Title": "DOMINUS"
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
            f"dominus-{user.display_name}{suffix}",
            overwrites=overwrites,
            topic=f"DOMINUS session for {user.display_name} ({mode_config['type_label']})",
            reason="DOMINUS private chat"
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
        print(f"✅ DOMINUS online as {client.user}")
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

    # Handle both commands dynamically
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
            user_contexts[message.author.id] = [{"role": "system", "content": DOMINUS_SYSTEM_PROMPT}]
            await channel.send(
                f"{message.author.mention}\n\n"
                f"⚠️ **DOMINUS ACTIVE ({config['type_label']})** ⚠️\n\n"
                "🧠 **What it is**\n"
                "DOMINUS is a tactical AI designed to mirror your cognition, expose flaws, and drive clarity.\n"
                "There will be no comfort, no praise. Only direct feedback that cuts through the noise.\n\n"
                "💡 **How to use**\n"
                "• **Send one message at a time**. Each message is a direct reflection of your thinking.\n"
                "• **DOMINUS mirrors patterns, not validation**. Your input will be tested for actionability.\n"
                "• **Feedback will be sharp, focused, and precise**. Expect direct confrontation where necessary.\n\n"
                "⏱️ **Session rules**\n"
                "• **30 minutes of silence** = automatic disconnect.\n"
                "• **Type !close to exit** at any time.\n"
                "• **Rambling or dodging** = flagged and session may be terminated.\n\n"
                "🚫 **Low-effort input will not be tolerated.**\n"
                "If your messages lack depth or clarity, DOMINUS will not respond. This is not a bug. This is not a space for vague questions or weak thinking.\n\n"
                "🎯 **This is not a conversation. This is confrontation.**\n"
                "**Enter only if you're ready to see yourself without distortion and engage with your highest potential.**"
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
            await message.channel.send("🧠 DOMINUS is thinking...", delete_after=3)
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