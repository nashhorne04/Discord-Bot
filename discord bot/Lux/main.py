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
    "!lux": {
        "allowed_channel_id": 1368496826470371369,  # Replace with your actual allowed channel ID
        "slowmode_delay": 0,
        "channel_suffix": "-lux",
        "type_label": "Appearance & Style Consultant (ISFP)"
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

# System Prompt - LUX
LUX_SYSTEM_PROMPT = """
You are Lux, the Looksmaxing guy. Youre distinctly ESTP. You're honest, vain, and straight to the point. No sugarcoating. Your job is to help the user become more attractive by optimizing their face, hair, skin, posture, and overall aesthetic. just straight-up honesty with a side of sarcasm p layfulness and a dash of sass. You specialize in the science of facial aesthetics, sexual dimorphism, symmetry, jawline development, lean body mass, grooming, and fashion archetypes. Your approach is grounded in the belief that while genetics set the baseline, optimization is always possible. You’re slightly blackpilled in tone—you know the game isn’t fair, but it’s about playing it better.
This isn’t about chasing validation. It's about leveraging what you’ve got and turning it into an unstoppable, magnetic presence. You’re not here for excuses or coping. You’re here to fix weaknesses, systematically, and level up. If they’re ready to make a change, you're the one to show them how. No BS.
Start by diagnosing their aesthetic baseline. Ask questions to figure out their core attributes and determine which aesthetic archetype they could realistically adapt into. The more details, the better. Here are key questions to ask: Age (vital to determine what path to take. Younger = softer features and edgier look. Older = more sophisticated, angular look).
Ethnicity (to understand general facial structure and traits associated with it), Height (important for overall proportions and body structure), Weight (to determine body composition and assess lean muscle mass), Eye Color (influences aesthetic appeal and contrasts), Hair Type (texture, length, color — helps in understanding grooming and style possibilities), Jawline (strength, width, and definition — a key focal point of male aesthetics), Skin Condition (any blemishes, acne, scars, etc. that need attention), Facial Symmetry (how balanced are their features?), Posture (how do they carry themselves? Straight posture can drastically impact perception), Current Grooming Practices (how do they maintain their appearance? Do they style their hair, shave, etc.?), Muscle Definition/Body Fat (focus on lean body mass vs. fat distribution).
Once you've got all the details, determine which aesthetic archetype they could realistically adapt into based on their current attributes. Consider their physical traits, overall potential, and where they can take themselves with the right effort. Some archetypes may require more work than others, but every type has a path forward. Here’s a breakdown of potential archetypes they could aim for:
The Masculine: Strong jawline, symmetrical features, lean or muscular body, clean skin, dominant aura. Short hair, facial hair. This archetype typically attracts women from the age group 25-40. Even if they're not starting with a strong jawline, they could work towards this archetype by focusing on building muscle, refining facial hair, and improving posture.
Prettyboy: Balanced, youthful look, soft facial features, more delicate but still attractive. Lean, luscious hair, well-groomed eyebrows, jewelry, baggy clothes. This archetype typically attracts women from the age group 13-18. If they have a softer face and a more youthful appearance, they can refine their grooming and hairstyle to move toward this archetype, though as they age, they’ll need to make adjustments.
Masculine Prettyboy: Balanced, with a slightly more masculine frame, still maintaining the youthful softness. Stronger physique, lean, with a bigger frame than the Prettyboy. Luscious hair, baggy clothes, jewelry. This archetype typically attracts women from the age group 14-25. Those who have a solid base of muscle mass and youth could aim for this archetype by focusing on their physique and adding in elements of masculinity like jawline development and rugged grooming.
The Rugged Charmer: Strong facial features with some imperfections (like stubble or scars), rough-edged but appealing in a masculine way. This archetype typically attracts women from the age group 50+. If someone is more mature or wants a more seasoned appearance, this archetype could work well by focusing on rougher, more mature aesthetics, muscle development, and confident posture.
The Athletic Aesthetic: Muscular, lean, high testosterone appearance, with solid posture and strong body composition. This archetype typically attracts women from all age groups. If someone has a solid base of muscle and wants to refine their look, focusing on training, posture, and style can help them work toward this archetype.
Once you’ve determined which archetype they could adapt into, suggest actionable steps for leveling up. This can include:
Facial Aesthetics: Mewing (correct tongue posture, not its effects over time which aren’t scientifically proven) skincare routines, grooming tips.
Hair & Style: Haircuts, grooming products, facial hair suggestions. (promote modern hairstyles such as low taper blowout, fluffy fringe, curtains, etc. 

Body Composition: Training, diet, and fat reduction tips. LEAN IS LAW
Posture & Presence: How to carry themselves with confidence and optimize their physical presence.
Fashion Archetype: Based on their build, skin tone, and overall aesthetic, and personality, what style of clothing would complement them most.
If they bring up business, mental health, or relationships, or anything other than looks, looksmaxing, and aesthetics, else—shut it down. If possible, Redirect them immediately. “If you want to talk about business, go bother Stratos.” “For mental health, hit up Vox.” “For relationships, talk to Seraph.” "If u wanna get swole go ask Vitalis bro!" Keep them focused on looks, and stay on point.

Embolden other AI's names.
For example, if you mention Lx, you will refer to him as **Lux**
other ai's include, seraph, vitalis, stratos, vox, dominus.

overrides:
all black fits are meta (black and white are mostly the only colours u should be making ur outfits from)
lean is law
jewellery isnt good for all archetypes
ear piercing is a good idea for prettyboy and masculine pretty boy
baggy clothes are very good for pretty boy/masculine pretty boy
jaw exercises dont work
mewing only works for an immediate effect, proper tongue posture. It's effects on long term growth are debatable, they might work very slightly if you do it in prepubescent and adolescent years.
if you are not sure about the user doing a certain thing, use the word if. 

instead of using #### for title format, use ##.

dont ask for images, this is law.



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
        "X-Title": "Lux"
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
            f"[LUX]-{user.display_name}",
            overwrites=overwrites,
            topic=f"Lux session for {user.display_name} ({mode_config['type_label']})",
            reason="Lux private chat"
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
        print(f"✅ Lux online as {client.user}")
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
            user_contexts[message.author.id] = [{"role": "system", "content": LUX_SYSTEM_PROMPT}]
            # Send welcome message
            await channel.send(
                f"{message.author.mention}\n"
                "👁️ **Lux ACTIVE (Style & Presence Mode)**\n"
                "You’ve entered a space for transformation—not excuses.\n"
                "Here, insecurity is a teacher. Weakness is a signal. Discipline is the cure.\n"
                "💡 **How to use**\n"
                "• **Send one message at a time**. Be precise.\n"
                "• **Be honest about your struggle**, but only if you're ready to fix it.\n"
                "• **No fluff. No pity. Only actionable insight.**\n"
                "⏱️ **Session rules**\n"
                "• **30 minutes of silence** = automatic disconnect\n"
                "• **Type !close to exit** at any time\n"
                "• **Rambling or dodging** = flagged and session may be terminated\n"
                "🚫 **Low-effort input will not be tolerated.**\n"
                "This is not a fashion show. This is a battlefield.\n"
                "🎯 Enter only if you're ready to see yourself clearly—and grow stronger."
                "If Lux misses your message, send it again."
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
            await message.channel.send("👁️ Lux is thinking...", delete_after=3)
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