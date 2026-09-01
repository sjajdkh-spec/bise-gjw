import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord.ext import commands, tasks

from config import load_config
from database import Database
from result_provider import BiseGujranwalaProvider, ResultNotAvailable, CaptchaRequired, ProviderError
from result_renderer import result_embed, save_result_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("bise-bot")

cfg = load_config()
db = Database(cfg["MONGODB_URI"], cfg["DB_NAME"])
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=cfg["PREFIX"], intents=intents, help_command=None)
provider = BiseGujranwalaProvider(cfg["OFFICIAL_RESULT_URL"], cfg["FALLBACK_RESULT_URL"], timeout=cfg["HTTP_TIMEOUT"])

def admin_only():
    async def predicate(ctx):
        if ctx.guild is None:
            raise commands.CheckFailure("This command can only be used in a server.")
        if ctx.author.guild_permissions.administrator:
            return True
        raise commands.CheckFailure("Administrator permission is required.")
    return commands.check(predicate)

@bot.event
async def on_ready():
    log.info("Logged in as %s (%s)", bot.user, bot.user.id)
    if not result_checker.is_running():
        result_checker.start()

@bot.command(name="addrole")
@admin_only()
async def addrole(ctx, roll_number: str, class_name: str, year: int):
    roll_number = roll_number.strip()
    class_name = class_name.lower().replace("class", "").strip()
    allowed = {"9th", "10th", "11th", "12th"}
    if class_name not in allowed:
        return await ctx.send("❌ Class must be one of: `9th`, `10th`, `11th`, `12th`.")
    await db.add_watch(ctx.guild.id, roll_number, class_name, year)
    await ctx.send(f"✅ Added roll number `{roll_number}` — `{class_name}` — `{year}`.")

@bot.command(name="removerole")
@admin_only()
async def removerole(ctx, roll_number: str):
    removed = await db.remove_watch(ctx.guild.id, roll_number)
    await ctx.send("✅ Removed." if removed else "❌ Roll number was not found.")

@bot.command(name="roles", aliases=["cmd"])
@admin_only()
async def roles(ctx):
    rows = await db.list_watches(ctx.guild.id)
    if not rows:
        return await ctx.send("📋 No roll numbers are configured.")
    lines = [f"`{i}` • `{r['roll_number']}` — {r['class_name']} — {r['year']} — {'ANNOUNCED' if r.get('announced') else 'WAITING'}"
             for i, r in enumerate(rows, 1)]
    text = "\n".join(lines)
    await ctx.send(f"📋 **Configured Results**\n{text}\n\nTotal: **{len(rows)}**")

@bot.command(name="checkresult")
@admin_only()
async def checkresult(ctx, roll_number: str, class_name: str, year: int):
    class_name = class_name.lower().replace("class", "").strip()
    msg = await ctx.send("🔎 Checking the official BISE Gujranwala result page…")
    try:
        result = await provider.fetch(roll_number, class_name, year)
        await db.save_result(ctx.guild.id, roll_number, class_name, year, result, announced=False)
        await msg.edit(content="", embed=result_embed(result))
    except CaptchaRequired:
        await msg.edit(content="⚠️ BISE Gujranwala is presenting a CAPTCHA/security challenge. The bot does not bypass CAPTCHAs. Try again when the official result endpoint is accessible without a challenge.")
    except ResultNotAvailable:
        await msg.edit(content=f"⏳ Result not available yet for `{roll_number}` ({class_name}, {year}).")
    except ProviderError as e:
        await msg.edit(content=f"⚠️ Result provider error: `{e}`")
    except Exception:
        log.exception("checkresult failed")
        await msg.edit(content="❌ Unexpected error while checking the result. See Railway logs for details.")

@bot.command(name="testrole")
@admin_only()
async def testrole(ctx, roll_number: str):
    saved = await db.get_result(ctx.guild.id, roll_number)
    if not saved:
        # Safe local test data: no request is made to BISE.
        saved = {
            "roll_number": roll_number,
            "class_name": "9th",
            "year": 2026,
            "name": "TEST STUDENT",
            "status": "PASS",
            "total_marks": 487,
            "max_marks": 550,
            "percentage": 88.55,
            "subjects": {"English": 82, "Urdu": 85, "Mathematics": 91, "Physics": 79, "Chemistry": 83, "Islamiyat": 67},
            "source": "LOCAL TEST DATA",
        }
    role = ctx.guild.get_role(cfg["MENTION_ROLE_ID"])
    channel = ctx.guild.get_channel(cfg["RESULT_CHANNEL_ID"]) or ctx.channel
    mention = role.mention if role else ""
    await channel.send(content=mention, embed=result_embed(saved))
    await ctx.send("✅ Test announcement sent.")

@bot.command(name="checkall")
@admin_only()
async def checkall(ctx):
    rows = await db.list_watches(ctx.guild.id, announced=False)
    await ctx.send(f"🔎 Checking **{len(rows)}** configured result(s)…")
    for row in rows:
        await process_watch(row, ctx.guild)
        await asyncio.sleep(cfg["PER_REQUEST_DELAY"])

@bot.command(name="setchannel")
@admin_only()
async def setchannel(ctx):
    cfg["RESULT_CHANNEL_ID"] = ctx.channel.id
    cfg["RESULT_CHANNEL_ID"] = int(ctx.channel.id)
    await db.set_setting(ctx.guild.id, "result_channel_id", ctx.channel.id)
    await ctx.send(f"✅ Result channel set to {ctx.channel.mention}.")

@bot.command(name="help")
async def help_cmd(ctx):
    prefix = cfg["PREFIX"]
    embed = discord.Embed(title="BISE Gujranwala Result Bot", color=discord.Color.red())
    embed.description = (
        f"**Admin commands**\n"
        f"`{prefix}addrole <roll> <9th|10th|11th|12th> <year>`\n"
        f"`{prefix}removerole <roll>`\n"
        f"`{prefix}roles` / `{prefix}cmd`\n"
        f"`{prefix}checkresult <roll> <class> <year>`\n"
        f"`{prefix}checkall`\n"
        f"`{prefix}setchannel`\n"
        f"`{prefix}testrole <roll>` — local test, no BISE request\n\n"
        f"Result checking uses the official BISE Gujranwala result page. "
        f"The bot never attempts to bypass CAPTCHA/security controls."
    )
    embed.set_footer(text="BISE Gujranwala Result Monitor")
    await ctx.send(embed=embed)

async def process_watch(row, guild):
    try:
        result = await provider.fetch(row["roll_number"], row["class_name"], row["year"])
    except (ResultNotAvailable, CaptchaRequired, ProviderError) as e:
        log.info("Roll %s: %s", row["roll_number"], e)
        return False
    except Exception:
        log.exception("Failed processing %s", row["roll_number"])
        return False

    await db.save_result(guild.id, row["roll_number"], row["class_name"], row["year"], result, announced=True)
    channel_id = await db.get_setting(guild.id, "result_channel_id") or cfg["RESULT_CHANNEL_ID"]
    role_id = await db.get_setting(guild.id, "mention_role_id") or cfg["MENTION_ROLE_ID"]
    channel = guild.get_channel(int(channel_id)) if channel_id else None
    role = guild.get_role(int(role_id)) if role_id else None
    if not channel:
        log.warning("Result channel not found for guild %s", guild.id)
        return False

    payload = role.mention if role else ""
    await channel.send(content=payload, embed=result_embed(result))
    return True

@tasks.loop(seconds=60)
async def result_checker():
    await bot.wait_until_ready()
    if not cfg["AUTO_CHECK_ENABLED"]:
        return
    guilds = list(bot.guilds)
    for guild in guilds:
        rows = await db.list_watches(guild.id, announced=False)
        for row in rows:
            await process_watch(row, guild)
            await asyncio.sleep(cfg["PER_REQUEST_DELAY"])

@result_checker.before_loop
async def before_checker():
    await bot.wait_until_ready()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send(f"❌ Missing argument. Use `{cfg['PREFIX']}help`.")
    if isinstance(error, commands.BadArgument):
        return await ctx.send(f"❌ Invalid argument. Use `{cfg['PREFIX']}help`.")
    if isinstance(error, commands.CheckFailure):
        return await ctx.send(f"❌ {error}")
    if isinstance(error, commands.CommandNotFound):
        return
    log.error("Command error: %r", error)
    await ctx.send("❌ Something went wrong. Check the Railway logs.")

if __name__ == "__main__":
    bot.run(cfg["DISCORD_TOKEN"])
