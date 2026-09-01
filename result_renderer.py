import json
from pathlib import Path
import discord

def result_embed(result):
    status = str(result.get("status") or "N/A")
    color = discord.Color.green() if "PASS" in status.upper() else discord.Color.red()
    embed = discord.Embed(title="🎓 BISE GUJRANWALA RESULT", color=color)
    embed.add_field(name="Roll Number", value=f"`{result.get('roll_number','N/A')}`", inline=True)
    embed.add_field(name="Class", value=str(result.get("class_name","N/A")), inline=True)
    embed.add_field(name="Year", value=str(result.get("year","N/A")), inline=True)
    embed.add_field(name="Student", value=str(result.get("name") or "N/A"), inline=False)
    embed.add_field(name="Status", value=status, inline=True)

    total = result.get("total_marks")
    maximum = result.get("max_marks")
    pct = result.get("percentage")
    if total is not None:
        embed.add_field(name="Marks", value=f"{total:g}" + (f" / {maximum:g}" if maximum else ""), inline=True)
    if pct is not None:
        embed.add_field(name="Percentage", value=f"{pct:.2f}%", inline=True)

    subjects = result.get("subjects") or {}
    if subjects:
        lines = [f"**{k}:** {v}" for k, v in subjects.items()]
        embed.add_field(name="Subject Marks", value="\n".join(lines)[:1024], inline=False)

    embed.set_footer(text="BISE Gujranwala Result Monitor")
    return embed

def save_result_json(result, path):
    Path(path).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
