import os
import boto3
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import math
from dotenv import load_dotenv
from datetime import datetime

import image
import matplotlib.pyplot as plt; plt.rcdefaults()
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

import json

from labellines import labelLine, labelLines
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()

load_dotenv()

discord_token = os.getenv("discord_token")

with open("players.json", "r") as f:
    player_data = json.load(f)


def str2dt(string):
    return datetime.strptime(string, "%Y-%m-%d %H:%M:%S.%f")

def splitTime(secs):
    string = ""
    flag = False
    days = math.floor(secs / 86400)
    secs = secs % 86400# seconds per day
    if(days>0):
        string+=str(days)
        if(days==1):
            string+=" day"
        else:
            string+=" days"
        flag=True

    hours = math.floor(secs / 3600)
    secs = secs % 3600# seconds per hour
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
    secs = secs % 60# seconds per minute
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

def getName(pName):
    player = player_data.get(pName, {})
    name = player.get("name", pName)
    pronoun = player.get("pronoun", "their")
    colour = player.get("colour", "#ffffff")
    return (name, pronoun, colour)

def getAt(pName):
    player = player_data.get(pName, {})
    discord_id = player.get("discord_id")
    if discord_id:
        return f"<@{discord_id}>"
    return pName

def getSteam(discord_mention):
    discord_id = discord_mention.strip("<@>")
    for key, val in player_data.items():
        if val.get("discord_id") == discord_id:
            return key
    return discord_mention  # fallback

def get_latest_game():
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT GAMENAME FROM TURNS ORDER BY TURNTIME DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

@client.event
async def on_ready():
    print('Ready')

@client.event
async def on_message(message):
    content = message.content
    lower = content.lower()
    game = get_latest_game()
    if message.author == client.user:
        return
    elif lower.startswith("!graph"):
        print("!graph")

        command = content.split()
        name = command[1]
        name = getSteam(name)

        plt.clf()
        fig, ax = plt.subplots()
        fig.set_size_inches(9, 5)
        #plt.ylim(0,24)

        cur.execute("SELECT * FROM TURNS WHERE GAMENAME = ?",(game,))
        allTurns = cur.fetchall()
        objects = []
        i = 0
        performance = []
        for i in range(0,len(allTurns)):
            # name, time, turnNo, game 
            aName = allTurns[i][0]
            aTime = str2dt(allTurns[i][1])
            aTurnNo = allTurns[i][2]
            if aName == name:
                try:
                    time = math.floor((str2dt(allTurns[i+1][1]) - aTime).total_seconds())
                    hours = time/60/60
                    objects.append((aTurnNo))
                    performance.append(hours)
                except Exception as e:
                    print(e)
                    pass # for last turn


        y_pos = np.arange(len(objects))
        #plt.yscale("log")
        ax.yaxis.set_major_formatter(mticker.ScalarFormatter())

        plt.bar(y_pos, performance, align='center', alpha=0.5)
        plt.xticks(y_pos, objects)
        #plt.yticks([1,6,12,24,48])
        plt.ylabel('Turn time (hours)')
        plt.xlabel('Turn number')
        plt.title(name+"'s Turns")
        filename = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")+".png"
        plt.savefig(filename)

        with open(filename, 'rb') as f:
            picture = discord.File(f)
            await message.channel.send(file=picture)
        
        # delete file
        os.remove(filename)

    elif lower.startswith("!total"):
        plt.clf()
        plt.rcParams.update({
                "lines.color": "#32343d",
                "patch.edgecolor": "#373943",#
                "text.color": "white",
                "axes.facecolor": "#373943",
                "axes.edgecolor": "#32343d",
                "axes.labelcolor": "white",
                "axes.grid": False,
                "xtick.color": "white",
                "ytick.color": "white",
                #"grid.color": "lightgray",
                "figure.facecolor": "#32343d",
                "figure.edgecolor": "#32343d",
                "savefig.facecolor": "#32343d",
                "savefig.edgecolor": "#32343d"})
        fig, ax = plt.subplots()
        #plt.ylim(0,24)

        cur.execute("SELECT * FROM TURNS WHERE TURNNUMBER = 1 AND GAMENAME = ? ORDER BY TURNTIME ASC",(game,))
        firstTurns = cur.fetchall()

        turnorder = []
        cur.execute("SELECT * FROM TURNS WHERE GAMENAME = ? ORDER BY TURNTIME DESC",(game,))
        if(len(firstTurns) > 0):
            i = 0
            for item in firstTurns:
                i += 1
                turnorder.append(item[0]) # create turn order

        cur.execute("SELECT * FROM TURNS WHERE GAMENAME = ? ORDER BY TURNTIME ASC",(game,))
        allTurns = cur.fetchall()
        i = 0
        performance = []
        for j in range(0,len(turnorder)):
            print(turnorder[j])
            performance.append(0)
            for i in range(0,len(allTurns)):
                # name, time, turnNo, game 
                aName = allTurns[i][0]
                aTime = str2dt(allTurns[i][1])
                aTurnNo = allTurns[i][2]
                if aName == turnorder[j]:
                    try:
                        time = math.floor((str2dt(allTurns[i+1][1]) - aTime).total_seconds())
                        hours = time/60/60
                        performance[j] = performance[j] + hours
                        print(hours)
                    except Exception as e: # for last turn
                        print(e)
                        # maybe put time since last turn started until now here (?)
            print()
            turnorder[j] += "\n(" + str(int(performance[j]))+"h)"

        y_pos = np.arange(len(turnorder))
        #plt.yscale("log")
        ax.yaxis.set_major_formatter(mticker.ScalarFormatter())

        plt.bar(y_pos, performance, align='center', alpha=0.5, color="red")
        plt.xticks(y_pos, turnorder, rotation=45, ha="right")
        #plt.tight_layout()
        plt.subplots_adjust(bottom=0.3)
        #plt.yticks([1,6,12,24,48])
        plt.ylabel('Turn time (hours)')
        plt.title("Total Turn Time")
        filename = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")+".png"
        plt.savefig(filename)

        with open(filename, 'rb') as f:
            picture = discord.File(f)
            await message.channel.send(file=picture)
            
        # delete file
        os.remove(filename)

    elif lower.startswith("!cum"):
        print("!cum")
        forAllFlag = True
        try:
            name = content.split()[1]
            forAllFlag = False
        except:
            pass
        if forAllFlag:
            #plt.style.use('dark_background')
            plt.rcParams.update({
                "lines.color": "#32343d",
                "patch.edgecolor": "#373943",#
                "text.color": "white",
                "axes.facecolor": "#373943",
                "axes.edgecolor": "#32343d",
                "axes.labelcolor": "white",
                "axes.grid": False,
                "xtick.color": "white",
                "ytick.color": "white",
                #"grid.color": "lightgray",
                "figure.facecolor": "#32343d",
                "figure.edgecolor": "#32343d",
                "savefig.facecolor": "#32343d",
                "savefig.edgecolor": "#32343d"})
            #plt.style.use('Solarize_Light2')
            #plt.style.use('fivethirtyeight')
            plt.clf()
            fig, ax = plt.subplots()
            fig.set_size_inches(9, 5)
            filename = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")+".png"

            turnorder = []
            cur.execute("SELECT * FROM TURNS WHERE TURNNUMBER = 1 AND GAMENAME = ? ORDER BY TURNTIME ASC",(game,))
            firstTurns = cur.fetchall()
    
            cur.execute("SELECT * FROM TURNS WHERE GAMENAME = ? ORDER BY TURNTIME DESC",(game,))
            if(len(firstTurns) > 0):
                i = 0
                for item in firstTurns:
                    i += 1
                    turnorder.append(item[0]) # create turn order

            cur.execute("SELECT * FROM TURNS WHERE GAMENAME = ? ORDER BY TURNNUMBER DESC",(game,))
            maxTurn = cur.fetchall()[0][2]
            print(maxTurn)

            cur.execute("SELECT * FROM TURNS WHERE GAMENAME = ? ORDER BY TURNTIME ASC",(game,))
            allTurns = cur.fetchall()
            objects = []
            performance = []
            for k in range(0,len(turnorder)):
                name = turnorder[k]
                j=0
                performance.append([])
                objects.append([])
                print(name)
                for i in range(0,len(allTurns)):
                    # name, time, turnNo, game
                    aName = allTurns[i][0]
                    aTime = str2dt(allTurns[i][1])
                    aTurnNo = allTurns[i][2]
                    if aName == name:
                        try:
                            time = math.floor((str2dt(allTurns[i+1][1]) - aTime).total_seconds())
                            hours = time/60/60
                            days = hours/24
                            objects[k].append(aTurnNo)
                            performance[k].append(0)
                            #performance[k][j] = hours + performance[k][j-1]
                            performance[k][j] = days + performance[k][j-1]
                            j=j+1
                            print(hours)
                        except Exception as e:
                            print(e)
                            pass # for last turn
                print(turnorder[k])
                x = objects[k]
                print(x)
                y = performance[k]
                print(y)
                #while(len(performance[k]) < maxTurn):
                #    performance[k].append(performance[k][-1])
                #while(len(objects[k]) < maxTurn):
                #    objects[k].append(objects[k][-1]+1)
                x.insert(0,0)
                y.insert(0,0)

                print()
                plt.plot(x,y,label=getName(name)[0], linestyle="-", color=getName(name)[2], linewidth=2)
            #ax.set_yscale('symlog', base=8)
            plt.gca().invert_yaxis()
            labelLines(plt.gca().get_lines(), zorder=2.5)
            ax.yaxis.set_major_formatter(mticker.ScalarFormatter())
            plt.ylabel('Turn time (days)')
            plt.xlabel('Turn number')
            plt.title("Cumulative Turns")


            #fig, ax = plt.subplots()
            #ax.yaxis.set_major_formatter(mticker.ScalarFormatter())

            plt.legend()

            #ax.set_facecolor("#373942")

            plt.savefig(filename,bbox_inches="tight",dpi=800,pad_inches=0)
            with open(filename, 'rb') as f:
                picture = discord.File(f)
                await message.channel.send(file=picture)
            
            # delete file
            os.remove(filename)
            
        else:

            name = getSteam(name)

            plt.clf()

            filename = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")+".png"
            
            cur.execute("SELECT * FROM TURNS WHERE GAMENAME = ?",(game,))
            allTurns = cur.fetchall()
            objects = []
            j = 0
            performance = []
            for i in range(0,len(allTurns)):
                # name, time, turnNo, game 
                aName = allTurns[i][0]
                aTime = str2dt(allTurns[i][1])
                aTurnNo = allTurns[i][2]
                if aName == name:
                    try:
                        time = math.floor((str2dt(allTurns[i+1][1]) - aTime).total_seconds())
                        hours = time/60/60
                        objects.append(aTurnNo)
                        performance.append(0)
                        performance[j] = hours + performance[j-1]
                        j=j+1
                    except Exception as e:
                        print(e)
                        pass # for last turn
                    print()


            x = objects
            y = performance
            
            print(x)
            print(y)

            plt.plot(x, y, label = name, linestyle="-")
            plt.legend()
    
            plt.savefig(filename)
    

            with open(filename, 'rb') as f:
                picture = discord.File(f)
                await message.channel.send(file=picture)
            
            # delete file
            os.remove(filename)

client.run(discord_token)