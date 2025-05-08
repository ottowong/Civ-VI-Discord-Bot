import sqlite3
import requests
import json

from flask import Flask, request
from flask_cors import CORS

import os
from dotenv import load_dotenv

from datetime import datetime, timedelta

import math

import concurrent.futures

import discord
from discord import app_commands
from discord.ext import commands
from discord import File

import asyncio

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)

load_dotenv()

app = Flask(__name__)
# CORS(app)

message_queue = []
mention_queue = []
colour_queue = []
player_queue = []

webhook_url = os.getenv("webhook_url")

port = os.getenv("port")
discord_token = os.getenv("discord_token")
channel_id = os.getenv("channel_id")

with open("players.json") as f:
    PLAYER_DATA = json.load(f)

def get_discord_id(player):
    data = PLAYER_DATA.get(player)
    if data:
        return f"<@{data['discord_id']}>"
    return player

def get_readable_name(player):
    data = PLAYER_DATA.get(player)
    if data:
        return data["name"]
    return player

def get_pronoun(player):
    data = PLAYER_DATA.get(player)
    if data:
        return data["pronoun"]
    return "their"

with open("emoji.json", "r") as f:
    EMOJI_THRESHOLDS = sorted(json.load(f), key=lambda x: x["seconds"], reverse=True)

print(EMOJI_THRESHOLDS)

def get_time_emoji(seconds_elapsed):
    for threshold in EMOJI_THRESHOLDS:
        if seconds_elapsed >= threshold["seconds"]:
            return threshold["emoji"]
    return ":question:"  # fallback


def str2dt(string):
    return datetime.strptime(string, "%Y-%m-%d %H:%M:%S.%f")

def splitTime(secs):
    string = ""
    flag = False
    days = math.floor(secs / 86400)
    secs = secs % 86400 # seconds per day
    if(days>0):
        string+=str(days)
        if(days==1):
            string+=" day"
        else:
            string+=" days"
        flag=True

    hours = math.floor(secs / 3600)
    secs = secs % 3600 # seconds per hour
    if(hours>0):
        if(flag):
            string+=", "
        string+=str(hours)
        if(hours==1):
            string+=" hour"
        else:
            string+=" hours"
        flag=True

    mins = math.floor(secs / 60)
    secs = secs % 60 # seconds per minute
    if(mins>0):
        if(flag):
            string+=", "
        string+=str(mins)
        if(mins==1):
            string+=" minute"
        else:
            string+=" minutes"
        flag=True

    if(secs>0):
        if(flag):
            string+=", "
        string+=str(secs)
        if(secs==1):
            string+=" second"
        else:
            string+=" seconds"

    return(string)

@app.route('/webhook', methods=['POST'])
def webhook():
    print(request.method)
    print(request)
    if request.method == 'POST':
        print()
        print("Data received from Webhook is: ", request.json)
        game = request.json["value1"]
        player = request.json["value2"]
        turn = request.json["value3"]
        content=""
        pronoun="their"

        oldTurn = turn

        # map names to discord IDs
        discordName = get_discord_id(player)
        content += (discordName + ", take your turn #" + turn)

        # create turnorder
        turnorder = []
        cur.execute("SELECT * FROM TURNS WHERE TURNNUMBER = ? AND GAMENAME = ? ORDER BY TURNTIME ASC",(str(int(turn)-1),game))
        firstTurns = cur.fetchall()
        if(len(firstTurns) > 0):
            for item in firstTurns:
                turnorder.append(item[0]) # create turn order
            cur.execute("SELECT * FROM TURNS WHERE TURNNUMBER = 1 AND GAMENAME = ? AND NAME = ? ORDER BY TURNTIME ASC",(game,player)) # check if player has taken a turn 1 yet
            checkExists = cur.fetchall() 
            if (len(checkExists) == 0):
                turnorder.append(player)
            if (player == turnorder[0]):
                oldTurn = str(int(oldTurn)-1) # if the player is first in turn order, the previous turn would have a lower turn number
            print("turnorder:",turnorder)
            print("player:",player)
            lastPlayer = turnorder[turnorder.index(player)-1]
        else: # if it's the first turn of the game
            conn.execute("INSERT INTO TURNS (NAME, TURNTIME, TURNNUMBER, GAMENAME) VALUES(?, ?, ?, ?)",(os.getenv("first_player"), str(datetime.now()-timedelta(seconds=60)), 1, game)) # add an entry for 10 seconds ago for the first player, defined in .env
            conn.commit()
            lastPlayer = os.getenv("first_player")

        cur.execute("SELECT * FROM TURNS WHERE NAME = ? AND TURNNUMBER = ? AND GAMENAME = ?",(player, turn, game))
        lastTurn = cur.fetchall()
        if(len(lastTurn) == 0):
            conn.execute("INSERT INTO TURNS (NAME, TURNTIME, TURNNUMBER, GAMENAME) VALUES(?, ?, ?, ?)",(player, str(datetime.now()), turn, game))
            conn.commit()

        # get previous turn info
        cur.execute("SELECT * FROM TURNS WHERE NAME = ? AND TURNNUMBER = ?",(lastPlayer, oldTurn))
        prevTurn = cur.fetchall()
        color = 0xffffff

        if(len(prevTurn) > 0): # if entry exists
            pName = prevTurn[0][0]
            pTurnTime = str2dt(prevTurn[0][1])

            readable_name = get_readable_name(pName)
            pronoun = get_pronoun(pName)

            time = math.floor((datetime.now()-pTurnTime).total_seconds())

            # Define color thresholds
            YELLOW_THRESHOLD_SECONDS = 12 * 60 * 60  # 12 hours
            RED_THRESHOLD_SECONDS = 24 * 60 * 60    # 24 hours
            
            # Calculate proportion of time elapsed for each color
            if time < YELLOW_THRESHOLD_SECONDS:
                # Green to Yellow transition
                proportion = time / YELLOW_THRESHOLD_SECONDS
                green = 255
                red = int(255 * proportion)
                color = (red << 16) + (green << 8)  # RGB color code

            elif time < RED_THRESHOLD_SECONDS:
                # Yellow to Red transition
                proportion = (time - YELLOW_THRESHOLD_SECONDS) / (RED_THRESHOLD_SECONDS - YELLOW_THRESHOLD_SECONDS)
                red = 255
                green = int(255 * (1 - proportion))
                color = (red << 16) + (green << 8)  # RGB color code

            else:
                # Beyond RED_THRESHOLD_SECONDS, stay red
                color = 0xff0000

            emoji = get_time_emoji(time)

            time = splitTime(time)
            content += "\n" + readable_name + " took " + time + " to take " + pronoun + " turn " + emoji

        else:
            content += "\n could not get turn time for some reason :-("
            content += "\ndebug:\nlastPlayer: "+lastPlayer+"\noldTurn: "+str(oldTurn)+"\nturnorder:"
            for i in turnorder:
                content += "\n - " + i
            print("turnorder",turnorder)
            print("lastPlayer",lastPlayer)
            print("oldTurn",oldTurn)

        colour_queue.append(color)
        player_queue.append(player)
        message_queue.append(content)
        mention_queue.append(realName)

        
        # data = {"content":content}
        #r = requests.post(webhook_url, data=json.dumps(data), headers={"Content-Type": "application/json"})
        #print(r)

        print(datetime.now())
        return "Webhook received"

@client.event
async def on_ready():
    while True:
        try:
            if message_queue:
                message = message_queue.pop(0)
                player = player_queue.pop(0)
                mention = mention_queue.pop(0)
                colour = colour_queue.pop(0)
                print(message)
                print(player)
                print(colour)
                print(mention)
                embedVar = discord.Embed(title=player+" Turn",description=message, color=colour)
                channel = await client.fetch_channel(channel_id)
                print("channel",channel)
                print()
                await channel.send(content=mention, embed=embedVar)
                user = await client.fetch_user(int(mention.replace("<","").replace(">","").replace("@","")))
                print(user.name)
                await user.send("!!!ATTENTION!!!\nIT IS CURRENTLY YOUR TURN!!!!!!!!")
    
            await asyncio.sleep(1)
        except Exception as e:
            print("ERROR IN MESSAGE_QUEUE",e)
            await asyncio.sleep(1)

def run_flask():
    app.run(host='0.0.0.0', port=port)

def run_discord_bot():
    client.run(discord_token)

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_flask = executor.submit(run_flask)
        future_discord_bot = executor.submit(run_discord_bot)

        concurrent.futures.wait([future_flask, future_discord_bot])