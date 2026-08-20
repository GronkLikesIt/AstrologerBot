import discord
from discord.ext import commands, tasks
import ephem
import datetime
import os

# Fixed Location: Belleville, ON
LATITUDE = "44.1628"
LONGITUDE = "-77.3832"
ELEVATION = 76

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)
last_applied_image = None

MONTHLY_FULL_MOONS = {
    1: ("Wolf Moon 🐺", "Fase_9_wolf"),
    2: ("Snow Moon ❄️", "Fase_9_snow"),
    3: ("Worm Moon 🪱", "Fase_9_worm"),
    4: ("Pink Moon 🌸", "Fase_9_pink"),
    5: ("Flower Moon 🌺", "Fase_9_flower"),
    6: ("Strawberry Moon 🍓", "Fase_9_strawberry"),
    7: ("Buck Moon 🦌", "Fase_9_buck"),
    8: ("Sturgeon Moon 🐟", "Fase_9_sturgeon"),
    9: ("Harvest Moon 🌾", "Fase_9_harvest"),
    10: ("Hunter's Moon 🏹", "Fase_9_hunters"),
    11: ("Beaver Moon 🦫", "Fase_9_beaver"),
    12: ("Cold Moon 🥶", "Fase_9_cold"),
}

def get_lunar_data():
    observer = ephem.Observer()
    observer.lat = LATITUDE
    observer.lon = LONGITUDE
    observer.elevation = ELEVATION
    now = datetime.datetime.utcnow()
    observer.date = now

    moon = ephem.Moon()
    moon.compute(observer)
    sun = ephem.Sun()
    sun.compute(observer)

    phase_pct = round(moon.phase, 1)

    # Calculate 16-phase cycle index (1-16)
    last_new = ephem.previous_new_moon(observer.date)
    next_new = ephem.next_new_moon(observer.date)
    progress = (observer.date - last_new) / (next_new - last_new)
    
    phase_index = int((progress * 16) + 0.5) % 16
    if phase_index == 0:
        phase_index = 16

    phase_names = [
        "New Moon 🌑", "Waxing Crescent 🌙", "Waxing Crescent 🌙", "Waxing Crescent 🌙",
        "Waxing Crescent 🌙", "First Quarter 🌓", "Waxing Gibbous 🌔", "Waxing Gibbous 🌔",
        "Full Moon 🌕", "Waning Gibbous 🌖", "Waning Gibbous 🌖", "Third Quarter 🌗",
        "Waning Crescent 🌘", "Waning Crescent 🌘", "Waning Crescent 🌘", "Dark Moon 🌑"
    ]

    phase_name = phase_names[phase_index - 1]
    image_name = f"Fase_{phase_index}"

    distance_km = round(moon.earth_distance * 149597870.7)
    sep_deg = ephem.separation(moon, sun) * (180 / ephem.pi)

    # Special Events & Solstices
    if phase_pct < 2 and sep_deg < 1.5:
        phase_name, image_name = "🔴 SOLAR ECLIPSE ☀️", "solar_eclipse"
    elif phase_pct > 98 and sep_deg > 178.5:
        phase_name, image_name = "🩸 BLOOD MOON 🌕", "Fase_9_Blood"
    elif phase_index == 9 or phase_pct > 97:
        if now.month == 6 and 20 <= now.day <= 22:
            phase_name, image_name = "✨ Rennala's Full Moon 🌕", "rennalas_full_moon"
        elif now.month == 12 and 20 <= now.day <= 22:
            phase_name, image_name = "❄️ Ranni's Dark Moon 🌙", "rannis_dark_moon"
        else:
            prev_full = ephem.previous_full_moon(observer.date).datetime()
            if prev_full.month == now.month and prev_full.day != now.day:
                phase_name, image_name = "💙 Blue Moon 🌕", "Fase_9_Blue"
            else:
                name, asset_file = MONTHLY_FULL_MOONS.get(now.month, ("Full Moon 🌕", "Fase_9"))
                phase_name, image_name = f"Full {name}", asset_file

    azimuth = round(float(moon.az) * 180 / ephem.pi, 1)
    altitude = round(float(moon.alt) * 180 / ephem.pi, 1)
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    dir_str = dirs[int((azimuth + 22.5) // 45) % 8]

    return {
        "phase_name": phase_name,
        "phase_pct": phase_pct,
        "image_path": f"assets/{image_name}.png",
        "pos_str": f"🧭 {dir_str} {azimuth}° | Alt: {altitude}° | {distance_km:,}km",
    }

@tasks.loop(minutes=15)
async def update_lunar_telemetry():
    for guild in bot.guilds:
        data = get_lunar_data()

        category = discord.utils.get(guild.categories, name="🌕 LUNAR TELEMETRY")
        if not category:
            try:
                overwrites = {guild.default_role: discord.PermissionOverwrite(connect=False)}
                category = await guild.create_category("🌕 LUNAR TELEMETRY", overwrites=overwrites, position=0)
                await guild.create_voice_channel(name="Phase: Loading...", category=category)
                await guild.create_voice_channel(name="Pos: Loading...", category=category)
            except discord.Forbidden:
                continue

        channels = category.voice_channels
        if len(channels) >= 2:
            try:
                await channels[0].edit(name=f"{data['phase_name']} ({data['phase_pct']}%)")
                await channels[1].edit(name=data["pos_str"])
            except discord.HTTPException:
                pass

        try:
            if os.path.exists(data["image_path"]):
                with open(data["image_path"], "rb") as img:
                    await guild.edit(icon=img.read())
        except (discord.Forbidden, discord.HTTPException):
            pass

@bot.event
async def on_ready():
    print(f"Bot connected as: {bot.user.name}")
    update_lunar_telemetry.start()

bot.run(os.getenv("DISCORD_TOKEN"))