import os
import boto3
import discord
from discord import app_commands
from discord.ext import commands
from discord import File
import sqlite3
import math
from dotenv import load_dotenv
from datetime import datetime
import json

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)

# Load players.json
with open("players.json", "r") as f:
    players_data = json.load(f)

def get_trust_status(discord_id):
    for player in players_data.values():
        if player.get("discord_id") == discord_id:
            return player.get("trusted")  # True/False/None
    return None


def get_player_by_discord_name(discord_name):
    clean_name = discord_name.strip("<>@")
    for key, player in players_data.items():
        if player.get("discord_id") == clean_name:
            return key, player
    return None, None

def get_player_by_steam_name(steam_name):
    print("STEAM NAME",steam_name)
    for player_key, info in players_data.items():
        if player_key == steam_name:
            print(info)
            return info
    return None

# Load emoji.json
with open("emoji.json", "r") as f:
    emoji_list = json.load(f)

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()

load_dotenv()

discord_token = os.getenv("discord_token")

emojis = {
    1: ":slightly_smiling_face:",
    2: ":melting_face:",
    3: ":neutral_face:",
    4: ":no_mouth:",
    5: ":confused:",
    6: ":slightly_frowning_face:",
    7: ":face_with_raised_eyebrow:",
    8: ":pensive:",
    9: ":weary:",
    10: ":grimacing:",
    11: ":yawning_face:",
    12: ":sleeping:",
    13: ":unamused:",
    14: ":angry:",
    15: ":triumph:",
    16: ":rage:",
    17: ":face_with_symbols_over_mouth:",
    18: ":scream:",
    19: ":clown_face:",
    20: ":moe:",
    21: ":hankey:",
    22: ":skull:",
    23: ":index_pointing_at_the_viewer:",
    24: ":gru:",
    48: ":saul:",
    72: ":loading:",
    96: ":crabrave:",
    120: ":soyrage:",
    144: ":angery:"
}

def get_latest_game():
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT GAMENAME FROM TURNS ORDER BY TURNTIME DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def str2dt(string):
    return datetime.strptime(string, "%Y-%m-%d %H:%M:%S.%f")

def splitTime(secs):
    units = [
        (86400, 'day'),
        (3600, 'hour'),
        (60, 'minute'),
        (1, 'second')
    ]
    
    time_string_parts = []

    for unit, unit_name in units:
        value = math.floor(secs / unit)
        secs %= unit
        if value > 0:
            time_string_parts.append(f"{value} {unit_name}" + ("s" if value != 1 else ""))
    
    if not time_string_parts:
        return "0 seconds"

    return ", ".join(time_string_parts)

@client.event
async def on_ready():
    print('Ready')

@client.event
async def on_message(message):
    content = message.content
    args = " ".join(str(content).split()[1:])
    content = content.lower()
    game = get_latest_game()
    if message.author == client.user:
        return
    if content == '!turnorder' or content == "!order" or content == "!players":
        print("!turnorder")
        turnString = ""
        turnorder = []
        cur.execute("SELECT * FROM TURNS WHERE TURNNUMBER = 1 AND GAMENAME = ? ORDER BY TURNTIME ASC",(game,)) # change this to get the previous turn (or turn 1 if its still turn 1)
        firstTurns = cur.fetchall()

        cur.execute("SELECT * FROM TURNS WHERE GAMENAME = ? ORDER BY TURNTIME DESC",(game,))
        lastTurns = cur.fetchall()
        if(len(firstTurns) > 0):
            i = 0
            for item in firstTurns:
                i += 1
                turnorder.append(item[0]) # create turn order
                if(item[0]==lastTurns[0][0]):
                    turnString = turnString + "**"
                turnString = turnString + str(i) + ") " + get_player_by_steam_name(item[0])["name"]
                if(item[0]==lastTurns[0][0]):
                    turnString = turnString + "**"
                turnString = turnString + "\n"
        #await message.channel.send(turnString)
        embedVar = discord.Embed(title="Turn Order", description=turnString, color=0x00ff00)
        await message.channel.send(embed=embedVar)
    elif content.startswith("!turn"):
        print("!turn")
        cur.execute("SELECT * FROM TURNS WHERE GAMENAME = ? ORDER BY TURNTIME DESC",(game,))
        lastTurns = cur.fetchall()
        print("DEBUG", lastTurns)
        player = get_player_by_steam_name(lastTurns[0][0])
        
        firstTime = str2dt(lastTurns[0][1])

        time = math.floor((datetime.utcnow() - firstTime).total_seconds())
        emoji = ":smiley:"

        for threshold in sorted(emojis.keys(), reverse=True):
            if time > threshold * 3600:
                emoji = emojis[threshold]
                break

        elapsed_time_seconds = (datetime.utcnow() - firstTime).total_seconds()
        # Define color thresholds
        YELLOW_THRESHOLD_SECONDS = 12 * 60 * 60  # 12 hours
        RED_THRESHOLD_SECONDS = 24 * 60 * 60    # 24 hours

        # Calculate proportion of time elapsed for each color
        if elapsed_time_seconds < YELLOW_THRESHOLD_SECONDS:
            # Green to Yellow transition
            proportion = elapsed_time_seconds / YELLOW_THRESHOLD_SECONDS
            green = 255
            red = int(255 * proportion)
            color = (red << 16) + (green << 8)  # RGB color code

        elif elapsed_time_seconds < RED_THRESHOLD_SECONDS:
            # Yellow to Red transition
            proportion = (elapsed_time_seconds - YELLOW_THRESHOLD_SECONDS) / (RED_THRESHOLD_SECONDS - YELLOW_THRESHOLD_SECONDS)
            red = 255
            green = int(255 * (1 - proportion))
            color = (red << 16) + (green << 8)  # RGB color code

        else:
            # Beyond RED_THRESHOLD_SECONDS, stay red
            color = 0xff0000
        if color < 0:
            color = 0xff0000

        time = splitTime(time)

        print("PLAYER", player)

        embedVar = discord.Embed(title="Turn Reminder",description="It is <@"+player["discord_id"]+">'s turn now.\n We have been waiting for " + time + " " + emoji, color=color)
        print(player["discord_id"], embedVar)
        print("COLOUR",color)
        await message.channel.send(content="<@"+player["discord_id"]+">", embed=embedVar)
        
    elif content.startswith("!fix"):
        print("id...", message.author.id)
        args = args.replace("@", "")
        trust_status = get_trust_status(str(message.author.id))
        if trust_status is not True:
            await message.channel.send("You are not allowed to use that command.")
            return
        print("args", args)

        
        if message.reference and isinstance(message.reference.resolved, discord.Message):
            replied_message = message.reference.resolved
            new_time = replied_message.created_at.replace(tzinfo=None)
        else:
            new_time = datetime.utcnow()

        if len(args) == 0:
            await message.channel.send("Usage: \n`!fix @[player_whose_turn_it_is_now]`")
            return
        else:
            steam_name, turn_person = get_player_by_discord_name(args)
            print("turn_person", turn_person)
            print("steam_name", steam_name)


        cur.execute("SELECT TURNNUMBER FROM TURNS WHERE GAMENAME = ? AND NAME = ? ORDER BY TURNTIME DESC LIMIT 1",(game, steam_name,))
        new_turn_number = int(cur.fetchall()[0][0]) + 1
        print("NEW",new_turn_number)
        if(new_turn_number):
            try:
                cur.execute("INSERT INTO TURNS (NAME, TURNTIME, TURNNUMBER, GAMENAME) VALUES (?, ?, ?, ?)",(steam_name, new_time, new_turn_number, game))
                conn.commit()
                sendString = f"Fixed.\n<@{turn_person['discord_id']}>, it is now your turn."
                embedVar = discord.Embed(title="Turn Fixed", description=sendString, color=0x0000ff)
                await message.channel.send(embed=embedVar)
            except Exception as e:
                conn.rollback()
                await message.channel.send("An error occurred:\n" + str(e))

    elif (content =="!backup"):
        filename = "data.db"
        
        await message.channel.send(file=File(filename))

    elif content.startswith("!test"):
        print("!test")
        print(content)
        print(args)
        embedVar = discord.Embed(title="Test",description="Desc :grinning: :+1: :saul:", color=0x00ff00)
        embedVar.add_field(name="asd", value="<pmbQn8Pd>")
        # await message.channel.send(embed=embedVar)
        await message.channel.send(str(message.author))
        user = await client.fetch_user(634015256028512276)
        print(user.name)
        await user.send("HELLO")
        pass
        
client.run(discord_token)