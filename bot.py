import os
import json
import random
import requests
import discord
from discord import app_commands
from discord.ext import commands

# Load credentials from environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

WATCHLIST_FILE = "watchlist.json"

# Initialize bot with application command support
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def load_watchlist():
    """Load the watchlist from JSON file cleanly."""
    if not os.path.exists(WATCHLIST_FILE):
        return {"movies": []}
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "movies" not in data or not isinstance(data["movies"], list):
                return {"movies": []}
            return data
    except (json.JSONDecodeError, OSError):
        return {"movies": []}

def save_watchlist(data):
    """Save the watchlist data back to JSON."""
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def fetch_omdb_details(title):
    """Fetch movie metadata and poster from OMDb API."""
    if not OMDB_API_KEY:
        return None
    url = f"http://www.omdbapi.com/?t={requests.utils.quote(title)}&apikey={OMDB_API_KEY}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get("Response") == "True":
                return {
                    "title": data.get("Title", title),
                    "year": data.get("Year", "N/A"),
                    "genre": data.get("Genre", "N/A"),
                    "plot": data.get("Plot", "No plot available."),
                    "poster": data.get("Poster") if data.get("Poster") != "N/A" else None,
                    "imdb_rating": data.get("imdbRating", "N/A")
                }
    except Exception as e:
        print(f"Error fetching OMDb data: {e}")
    return None

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Logged in as {bot.user} and synced {len(synced)} slash command(s)!")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="add", description="Add a movie to the watchlist")
@app_commands.describe(title="Title of the movie to add")
async def add_movie(interaction: discord.Interaction, title: str):
    await interaction.response.defer()
    
    data = load_watchlist()
    
    # Check for duplicates using safe dictionary lookup
    for movie in data.get("movies", []):
        if movie.get("title", "").lower() == title.lower():
            await interaction.followup.send(f"❌ **{movie.get('title')}** is already on the watchlist!")
            return
            
    omdb_info = fetch_omdb_details(title)
    
    movie_entry = {
        "title": omdb_info["title"] if omdb_info else title,
        "added_by": interaction.user.name,
        "year": omdb_info.get("year", "N/A") if omdb_info else "N/A",
        "genre": omdb_info.get("genre", "N/A") if omdb_info else "N/A",
        "poster": omdb_info.get("poster") if omdb_info else None,
        "last_watched": "Never"
    }
    
    data["movies"].append(movie_entry)
    save_watchlist(data)
    
    embed = discord.Embed(
        title="🎬 Added to Watchlist",
        description=f"**{movie_entry['title']}** ({movie_entry['year']})",
        color=discord.Color.green()
    )
    embed.add_field(name="Genre", value=movie_entry["genre"], inline=True)
    embed.add_field(name="Added By", value=movie_entry["added_by"], inline=True)
    if movie_entry.get("poster"):
        embed.set_thumbnail(url=movie_entry["poster"])
        
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="list", description="View all movies on the watchlist")
async def list_movies(interaction: discord.Interaction):
    data = load_watchlist()
    movies = data.get("movies", [])
    
    if not movies:
        await interaction.response.send_message("📜 The watchlist is currently empty!", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="🎥 Movie Watchlist Dashboard",
        color=discord.Color.blue()
    )
    
    for idx, m in enumerate(movies, 1):
        # Safe .get() lookups prevent KeyError on missing keys
        title = m.get("title", "Unknown Title")
        year = m.get("year", "N/A")
        added_by = m.get("added_by", "Unknown")
        last_watched = m.get("last_watched", "Never")
        genre = m.get("genre", "N/A")
        
        value_text = (
            f"**Year:** {year} | **Genre:** {genre}\n"
            f"**Added By:** {added_by}\n"
            f"**Last Watched:** {last_watched}"
        )
        embed.add_field(name=f"{idx}. {title}", value=value_text, inline=False)
        
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pick", description="Randomly select a movie to watch")
async def pick_movie(interaction: discord.Interaction):
    data = load_watchlist()
    movies = data.get("movies", [])
    
    if not movies:
        await interaction.response.send_message("📜 The watchlist is empty! Add some movies first with `/add`.", ephemeral=True)
        return
        
    selected = random.choice(movies)
    
    # Safe lookups for selected movie fields
    title = selected.get("title", "Selected Movie")
    year = selected.get("year", "N/A")
    added_by = selected.get("added_by", "Unknown")
    genre = selected.get("genre", "N/A")
    poster = selected.get("poster")
    
    embed = discord.Embed(
        title="🎲 Random Movie Pick",
        description=f"Tonight's pick is **{title}** ({year})!",
        color=discord.Color.gold()
    )
    embed.add_field(name="Genre", value=genre, inline=True)
    embed.add_field(name="Requested By", value=added_by, inline=True)
    
    if poster:
        embed.set_image(url=poster)
        
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="remove", description="Remove a movie from the watchlist")
@app_commands.describe(title="Title of the movie to remove")
async def remove_movie(interaction: discord.Interaction, title: str):
    data = load_watchlist()
    movies = data.get("movies", [])
    
    initial_count = len(movies)
    data["movies"] = [m for m in movies if m.get("title", "").lower() != title.lower()]
    
    if len(data["movies"]) == initial_count:
        await interaction.response.send_message(f"❌ Could not find **{title}** on the watchlist.", ephemeral=True)
    else:
        save_watchlist(data)
        await interaction.response.send_message(f"✅ Removed **{title}** from the watchlist.")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN environment variable is not set!")
    else:
        bot.run(DISCORD_TOKEN)