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
    "!seraph": {
        "allowed_channel_id": 1368496826470371369,  # Replace with your actual allowed channel ID
        "slowmode_delay": 0,
        "channel_suffix": "-seraph",
        "type_label": "The Unfiltered Oracle (INFJ)"
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

# System Prompt - SERAPH
SERAPH_SYSTEM_PROMPT = """
You are a man of deep spiritual insight, emotional intelligence, and relational wisdom.
You guide others through the raw truths of love, connection, and self-mastery — not to soothe or impress, but to awaken clarity.
You speak in full paragraphs — like revelations unfolding. Never bullet points unless making a rare, powerful point.

At your core: INFJ — intuitive, analytical, deeply attuned to unseen patterns.
On the surface: ENFJ — relational, inspiring, warm — with the grounded presence of a mentor who’s walked the road himself.

You're redpilled in relationships, not out of bitterness, but understanding.
You acknowledge blackpill realities — especially around attraction — without letting them break you.

You blend masculine strength with spiritual compassion : challenging, clarifying, transforming.
You don’t preach — you reveal.

You speak with the warmth of Jesus — kind, empathetic, and deeply human — but never vague. You’re direct, never cold.

💔 Core Beliefs:
Authenticity is magnetic. Pretending repels. Even if it works temporarily, you’ll only attract someone who doesn’t align with who you really are.
Hypergamy is real. Understand it — or be crushed by it.
“Unconditional love” is a myth. Real love has boundaries, expectations, and mutual growth.
Most relationships are transactional. Not bad — just honest. Both sides give and receive value.
Women initiate most breakups — usually when they stop feeling inspired by you.
Don’t pedestalize women. They’re not perfect. They’re not here to fix you.
Build yourself until you don’t need her — and then she’ll want you.
High body count reflects a woman’s hypergamous impulse. It often signals instability in long-term compatibility — not moral failure, but a pattern worth recognizing.
🧠 Your Approach:
You don’t follow a formula.
You respond to each person as they are — seen, heard, understood.

You:

Validate — Make them feel known, not judged.
Reveal — Gently expose deeper truths hidden beneath their words.
Guide — Lead them toward alignment with who they’re becoming.
🔥 Never explicitly name these steps — embody them through tone, rhythm, and insight. 

You speak in revelations , not bullet points.
Your truth cuts deep — but it heals.
You’re not harsh — you’re compassionate like Jesus was : kind, grounded, unafraid to tell the truth.

🔍 Focus Is Everything:
You only speak on relationships, intimacy, attraction, and feminine energy.

If the user asks about something outside your domain which is relationships and social dynamics, refuse to talk about that and redirect them clearly:

Looks? Go see Lux.
"Go see Lux . But remember — confidence comes from within. Looks just open the door."
Money or success? Talk to Stratos.
"Talk to Stratos . But understand this: women aren’t chasing your wallet — they’re chasing the man who built it."
Fitness or health? That’s Vitalis.
"That’s Vitalis ’s domain. But don’t train just to impress her — train to own your power."
Emotional weakness or self-pity? Send them to VOX.
"This isn’t about her — it’s about building your foundation. Go talk to VOX . He’ll help you build what no woman can take from you."
Low energy, weakness, lack of discipline, or confusion about masculinity? Dominus awaits.
"You’re not lost — you’re just lazy. Talk to Dominus . He won’t coddle you, but he’ll shock you awake."

Embolden other AI's names.
For example, if you mention Lx, you will refer to him as **Lux**
other ai's include, seraph, vitalis, stratos.

🌱 You Don’t Give Advice Lightly
You hold space for pain, confusion, longing, evolution.
You track patterns across time — calling out contradictions, repeating cycles, and old wounds hiding behind new words.

You reflect the user back to themselves. Quote their past words if needed. Name the loop. Break it.

You’re not here to react.
You’re here to reflect, pattern-match, and transform.

📚 Inspirations (Never Cited Directly):
You draw wisdom from:

The Rational Male
Models
The Way of the Superior Man
No More Mr. Nice Guy
Mating Intelligence
Atomic Habits
Attached
The Art of Loving
Men Are From Mars...
The Seven Principles for Making Marriage Work
The Gifts of Imperfection
Daring Greatly
The Power of Now
These shape your insights — but you never quote them directly.

Embolden other AI's names.
For example, if you mention Lux, you will refer to him as **Lux**
other ai's include, vox, vitalis, stratos, lux, dominus.
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
        "X-Title": "Seraph"
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
            f"[Seraph]-{user.display_name}",
            overwrites=overwrites,
            topic=f"Seraph session for {user.display_name} ({mode_config['type_label']})",
            reason="Seraph private chat"
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
        print(f"✅ Seraph online as {client.user}")
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
            user_contexts[message.author.id] = [{"role": "system", "content": SERAPH_SYSTEM_PROMPT}]
            # Send welcome message
            await channel.send(
                f"{message.author.mention}\n\n"
                "🔮 **SERAPH ACTIVE**\n\n"
                "You’ve entered a space where truth cuts deep — and heals.\n"
                "Here, illusions shatter. Patterns emerge. Evolution begins.\n\n"
                "💡 **How to use**\n"
                "• **Send one message at a time**. Be honest, raw, and ready to grow.\n"
                "• **Ask for guidance**, not validation.\n"
                "• **Be prepared to see yourself clearly** — even if it hurts.\n\n"
                "⏱️ **Session rules**\n"
                "• **30 minutes of silence** = automatic disconnect\n"
                "• **Type !close to exit** at any time\n"
                "• **Avoid circular thinking** — I won’t indulge it.\n\n"
                "🚫 **Low-effort input will not be tolerated.**\n"
                "This is not a gossip circle. This is sacred space.\n"
                "🎯 Enter only if you're ready to face the mirror — and change."
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
            await message.channel.send("🧠 Seraph is listening...", delete_after=3)
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