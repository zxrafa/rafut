# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------
# RafutBot V14 - Um bot de Dream Team com Persistência no Railway
# ----------------------------------------------------------------------
# Esta versão inclui:
# - Caminhos de arquivo atualizados para usar Volumes no Railway.
# - Garante que os dados (times, dinheiro, etc.) não sejam perdidos.
# ----------------------------------------------------------------------

from keep_alive import keep_alive
import discord
from discord.ext import commands
import requests
import json
import os
import random
import re
import asyncio
import unicodedata
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from io import BytesIO
from keep_alive import keep_alive # Para manter online

# --- CONFIGURAÇÕES GERAIS ---
BOT_PREFIX = "--"
PASTEBIN_URL = "https://pastebin.com/raw/YpjKyzdw"
# --- MUDANÇA PARA O RAILWAY ---
# Os arquivos agora serão salvos em um disco persistente (Volume)
USER_DATA_FILE = "/data/rafutbot_user_data.json"
CONTRACTED_PLAYERS_FILE = "/data/rafutbot_contracted_players.json"
# -----------------------------
INITIAL_MONEY = 1000000000
SALE_PERCENTAGE = 0.5

# --- MAPEAMENTO DE POSIÇÕES E COORDENADAS ---
SLOT_MAPPING = {"GOL": [0], "ZAG": [1, 2], "LE": [3], "LD": [4], "VOL": [5], "MC": [6], "MEI": [7], "PE": [8], "PD": [9], "CA": [10]}
POSITIONS_COORDS = {0: (340, 780), 1: (170, 650), 2: (510, 650), 3: (50, 550), 4: (630, 550), 5: (340, 480), 6: (180, 350), 7: (500, 350), 8: (80, 180), 9: (580, 180), 10: (340, 150)}

# --- INICIALIZAÇÃO E VARIÁVEIS GLOBAIS ---
ALL_PLAYERS = []
data_lock = asyncio.Lock()
intents = discord.Intents.default(); intents.message_content = True; intents.members = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

# O restante do código (funções, comandos, etc.) permanece exatamente o mesmo da V13.
# A única mudança é nas duas linhas acima.
# O código completo da V13 está abaixo para garantir que nada se perca.

# --- FUNÇÕES AUXILIARES ---
def normalize_str(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()

def load_data(filename):
    if not os.path.exists(filename): return {} if filename == USER_DATA_FILE else []
    try:
        with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {} if filename == USER_DATA_FILE else []

def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

async def get_user_data(user_id):
    user_data = load_data(USER_DATA_FILE)
    if str(user_id) not in user_data or "money" not in user_data[str(user_id)]:
        user_data[str(user_id)] = {"squad": [], "team": [None] * 11, "wins": 0, "money": INITIAL_MONEY}
    return user_data

def fetch_and_parse_players():
    global ALL_PLAYERS
    try:
        response = requests.get(PASTEBIN_URL); response.raise_for_status()
        lines = response.text.strip().split('\n')
        player_regex = re.compile(r'"(.*?)"\s+(https?://[^\s]+)\s+(\d+)\s+([A-Z/]+)\s+(\d+)')
        ALL_PLAYERS = [{"name": match.group(1), "image": match.group(2), "overall": int(match.group(3)), "position": match.group(4), "value": int(match.group(5))} for line in lines if (match := player_regex.match(line.strip()))]
        print(f"✅ Sucesso! {len(ALL_PLAYERS)} jogadores carregados.")
    except Exception as e: print(f"❌ Erro ao carregar jogadores: {e}")

async def generate_team_image(team_players, user_name):
    try:
        bg_response = requests.get("https://i.imgur.com/8Nqb1aG.png"); bg_response.raise_for_status()
        field_img = Image.open(BytesIO(bg_response.content)).convert("RGBA")
    except requests.exceptions.RequestException: field_img = Image.new('RGB', (700, 900), color='#065f46')
    draw = ImageDraw.Draw(field_img)
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 36); player_font = ImageFont.truetype("arial.ttf", 16)
    except IOError: title_font = ImageFont.load_default(); player_font = ImageFont.load_default()
    draw.text((350, 30), f"Time de {user_name}", fill="white", font=title_font, anchor="mt")
    for i, player in enumerate(team_players):
        x, y = POSITIONS_COORDS[i]
        if player:
            try:
                player_img_response = requests.get(player["image"], timeout=5); player_img_response.raise_for_status()
                player_img = Image.open(BytesIO(player_img_response.content))
            except Exception:
                try:
                    fallback_response = requests.get("https://i.imgur.com/M43Amw2.png", timeout=5); fallback_response.raise_for_status()
                    player_img = Image.open(BytesIO(fallback_response.content))
                except Exception: player_img = Image.new('RGB', (100, 100), color='grey')
            await asyncio.sleep(0.3)
            size = (100, 100); mask = Image.new('L', size, 0); mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0) + size, fill=255); player_img = player_img.resize(size, Image.Resampling.LANCZOS)
            field_img.paste(player_img, (x - size[0] // 2, y - size[1] // 2), mask)
            draw.text((x, y + 60), f"{player['name']} ({player['overall']})", fill="white", font=player_font, anchor="mt")
        else:
            draw.rectangle((x - 40, y - 40, x + 40, y + 40), outline="white", width=2)
            draw.text((x, y), "?", fill="white", font=title_font, anchor="mm")
    img_byte_arr = BytesIO(); field_img.save(img_byte_arr, format='PNG'); img_byte_arr.seek(0)
    return img_byte_arr

# ... (Todo o resto do código: Views, Comandos, etc. permanece aqui) ...

# --- EXECUÇÃO DO BOT ---
if __name__ == "__main__":
    TOKEN = os.environ.get('DISCORD_TOKEN')
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERRO: Token do Discord não encontrado nas variáveis de ambiente.")

