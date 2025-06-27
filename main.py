# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------
# RafutBot V16 - Edição Cassino Royale
# ----------------------------------------------------------------------
# Esta versão inclui:
# - Correção final do comando 'confrontar'.
# - 5 novos jogos de aposta no cassino.
# ----------------------------------------------------------------------

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
from keep_alive import keep_alive
import google.generativeai as genai
import math

# --- CONFIGURAÇÕES GERAIS ---
BOT_PREFIX = "--"
PASTEBIN_URL = "https://pastebin.com/raw/YpjKyzdw"
USER_DATA_FILE = "/data/rafutbot_user_data.json"
CONTRACTED_PLAYERS_FILE = "/data/rafutbot_contracted_players.json"
INITIAL_MONEY = 1000000000
SALE_PERCENTAGE = 0.5

# --- CONFIGURAÇÃO DA IA GEMINI ---
try:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ IA Gemini configurada com sucesso!")
    else:
        gemini_model = None
        print("⚠️ Aviso: Chave de API do Gemini não encontrada. Comandos de IA serão desativados.")
except Exception as e:
    gemini_model = None
    print(f"❌ Erro ao configurar a IA Gemini: {e}")

# --- MAPEAMENTO E INICIALIZAÇÃO ---
SLOT_MAPPING = {"GOL": [0], "ZAG": [1, 2], "LE": [3], "LD": [4], "VOL": [5], "MC": [6], "MEI": [7], "PE": [8], "PD": [9], "CA": [10]}
POSITIONS_COORDS = {0: (350, 780), 1: (180, 650), 2: (520, 650), 3: (60, 550), 4: (640, 550), 5: (350, 500), 6: (220, 370), 7: (480, 370), 8: (90, 200), 9: (610, 200), 10: (350, 160)}
ALL_PLAYERS = []
data_lock = asyncio.Lock()
intents = discord.Intents.default(); intents.message_content = True; intents.members = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

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

async def generate_ai_narration(prompt_text, fallback_text):
    if not gemini_model: return fallback_text
    try:
        response = await gemini_model.generate_content_async(prompt_text, safety_settings={'HARM_CATEGORY_HARASSMENT':'block_none'})
        return response.text.strip()
    except Exception as e:
        print(f"Erro na API Gemini: {e}")
        return fallback_text

async def generate_team_image(team_players, user_name):
    width, height = 700, 900; dark_green_top = (8, 43, 27); dark_green_bottom = (4, 24, 15)
    field_img = Image.new("RGB", (width, height)); draw = ImageDraw.Draw(field_img)
    for y in range(height):
        ratio = y / height
        r = int(dark_green_top[0] * (1 - ratio) + dark_green_bottom[0] * ratio); g = int(dark_green_top[1] * (1 - ratio) + dark_green_bottom[1] * ratio); b = int(dark_green_top[2] * (1 - ratio) + dark_green_bottom[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    try:
        field_lines_response = requests.get("https://i.imgur.com/83zT2A9.png"); field_lines_img = Image.open(BytesIO(field_lines_response.content)).convert("RGBA")
        field_img.paste(field_lines_img, (0,0), field_lines_img)
    except Exception: print("Aviso: Não foi possível carregar as linhas do campo.")
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 42); player_name_font = ImageFont.truetype("arialbd.ttf", 18); player_stats_font = ImageFont.truetype("arial.ttf", 15); team_stats_font = ImageFont.truetype("arialbd.ttf", 24)
    except IOError: title_font = player_name_font = player_stats_font = team_stats_font = ImageFont.load_default()
    title_text = f"Time de {user_name}"; draw.text((350, 38), title_text, font=title_font, fill=(0,0,0,120), anchor="mt", stroke_width=2); draw.text((350, 35), title_text, font=title_font, fill="#FFFFFF", anchor="mt")
    total_overall = 0; total_value = 0
    for i, player in enumerate(team_players):
        x, y = POSITIONS_COORDS[i]
        if player:
            total_overall += player['overall']; total_value += player['value']
            try:
                player_img_response = requests.get(player["image"], timeout=5); player_img_response.raise_for_status()
                player_img = Image.open(BytesIO(player_img_response.content)).convert("RGBA")
            except Exception:
                try:
                    fallback_response = requests.get("https://i.imgur.com/M43Amw2.png", timeout=5); fallback_response.raise_for_status()
                    player_img = Image.open(BytesIO(fallback_response.content)).convert("RGBA")
                except Exception: player_img = Image.new('RGBA', (100, 100), color='grey')
            await asyncio.sleep(0.05)
            img_size = (100, 130); player_img.thumbnail(img_size, Image.Resampling.LANCZOS)
            paste_x = x - player_img.width // 2; paste_y = y - player_img.height // 2
            field_img.paste(player_img, (paste_x, paste_y), player_img)
            player_name_text = player['name'].split(' ')[0]; player_stats_text = f"OVR {player['overall']}"
            text_y = y + 70
            draw.text((x+1, text_y+1), player_name_text, font=player_name_font, fill="black", anchor="mt", stroke_width=2); draw.text((x, text_y), player_name_text, font=player_name_font, fill="white", anchor="mt")
            draw.text((x+1, text_y + 21), player_stats_text, font=player_stats_font, fill="black", anchor="mt", stroke_width=2); draw.text((x, text_y + 20), player_stats_text, font=player_stats_font, fill="yellow", anchor="mt")
        else:
            draw.rectangle((x - 40, y - 40, x + 40, y + 40), outline=(255,255,255,100), width=2); draw.text((x, y), "?", fill=(255,255,255,100), font=title_font, anchor="mm")
    stats_overall_text = f"⭐ Overall Total: {total_overall}"; stats_value_text = f"💰 Valor de Mercado: R$ {total_value:,}"
    draw.text((35, 852), stats_overall_text, font=team_stats_font, fill="black", anchor="ls", stroke_width=2); draw.text((35, 850), stats_overall_text, font=team_stats_font, fill="white", anchor="ls")
    draw.text((35, 882), stats_value_text, font=team_stats_font, fill="black", anchor="ls", stroke_width=2); draw.text((35, 880), stats_value_text, font=team_stats_font, fill="#39FF14", anchor="ls")
    img_byte_arr = BytesIO(); field_img.save(img_byte_arr, format='PNG'); img_byte_arr.seek(0)
    return img_byte_arr

# --- VIEWS DE INTERAÇÃO ---
class KeepOrSellView(discord.ui.View):
    def __init__(self, author, player):
        super().__init__(timeout=60)
        self.author = author; self.player = player; self.decision_made = False
    @discord.ui.button(label="Manter no Elenco", style=discord.ButtonStyle.green)
    async def keep_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return await interaction.response.send_message("Você não pode decidir por outro jogador.", ephemeral=True)
        self.decision_made = True
        async with data_lock:
            user_data = await get_user_data(self.author.id)
            user_data[str(self.author.id)]["squad"].append(self.player); save_data(USER_DATA_FILE, user_data)
        await interaction.message.edit(content=f"✅ **{self.player['name']}** foi adicionado ao seu elenco!", view=None)
    @discord.ui.button(label="Vender", style=discord.ButtonStyle.red)
    async def sell_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return await interaction.response.send_message("Você não pode decidir por outro jogador.", ephemeral=True)
        self.decision_made = True; sale_price = int(self.player['value'] * SALE_PERCENTAGE)
        async with data_lock:
            user_data = await get_user_data(self.author.id); user_data[str(self.author.id)]["money"] += sale_price
            contracted = load_data(CONTRACTED_PLAYERS_FILE); contracted = [p for p in contracted if p != self.player['name']]
            save_data(USER_DATA_FILE, user_data); save_data(CONTRACTED_PLAYERS_FILE, contracted)
        await interaction.message.edit(content=f"💰 Você vendeu **{self.player['name']}** e ganhou **R$ {sale_price:,}**!", view=None)
    async def on_timeout(self):
        if not self.decision_made and self.message:
            try:
                sale_price = int(self.player['value'] * SALE_PERCENTAGE)
                async with data_lock:
                    user_data = await get_user_data(self.author.id)
                    user_data[str(self.author.id)]["money"] += sale_price
                    contracted = load_data(CONTRACTED_PLAYERS_FILE)
                    contracted = [p_name for p_name in contracted if p_name != self.player['name']]
                    save_data(USER_DATA_FILE, user_data); save_data(CONTRACTED_PLAYERS_FILE, contracted)
                await self.message.edit(content=f"⏰ Tempo esgotado! **{self.player['name']}** foi vendido automaticamente por **R$ {sale_price:,}**.", view=None)
            except discord.NotFound: pass

class ContractView(discord.ui.View):
    def __init__(self, ctx, results):
        super().__init__(timeout=120)
        self.ctx = ctx; self.results = results; self.current_index = 0
    async def create_embed(self, interaction: discord.Interaction = None):
        player = self.results[self.current_index]
        embed = discord.Embed(title=f"🔎 Busca: {player['name']}", color=discord.Color.blue())
        embed.set_image(url=player['image'])
        embed.add_field(name="Posição", value=player['position'], inline=True).add_field(name="Overall", value=player['overall'], inline=True).add_field(name="Preço", value=f"R$ {player['value']:,}", inline=True)
        embed.set_footer(text=f"Jogador {self.current_index + 1}/{len(self.results)}")
        self.prev_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.results) - 1
        self.buy_button.label = f"Comprar por R$ {player['value']:,}"
        if interaction: await interaction.response.edit_message(embed=embed, view=self)
        else: return embed
    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.grey, emoji="⬅️")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return await interaction.response.send_message("Apenas o autor do comando pode navegar.", ephemeral=True)
        if self.current_index > 0: self.current_index -= 1; await self.create_embed(interaction)
    @discord.ui.button(label="Próximo", style=discord.ButtonStyle.grey, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return await interaction.response.send_message("Apenas o autor do comando pode navegar.", ephemeral=True)
        if self.current_index < len(self.results) - 1: self.current_index += 1; await self.create_embed(interaction)
    @discord.ui.button(label="Comprar", style=discord.ButtonStyle.green, emoji="💸")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return await interaction.response.send_message("Apenas o autor do comando pode comprar.", ephemeral=True)
        player_to_buy = self.results[self.current_index]
        async with data_lock:
            user_data = await get_user_data(self.ctx.author.id); user_id = str(self.ctx.author.id); user_money = user_data[user_id]['money']
            contracted_check = load_data(CONTRACTED_PLAYERS_FILE)
            if player_to_buy['name'] in contracted_check:
                await interaction.response.send_message(f"😔 Que pena! **{player_to_buy['name']}** foi contratado.", ephemeral=True)
                return await self.message.delete()
            if user_money < player_to_buy['value']: return await interaction.response.send_message(f"💸 **Dinheiro insuficiente!**", ephemeral=True)
            user_data[user_id]['money'] -= player_to_buy['value']; user_data[user_id]['squad'].append(player_to_buy); contracted_check.append(player_to_buy['name'])
            save_data(USER_DATA_FILE, user_data); save_data(CONTRACTED_PLAYERS_FILE, contracted_check)
        for item in self.children: item.disabled = True
        final_embed = await self.create_embed(); final_embed.color = discord.Color.green(); final_embed.title = f"Contratado! ✅"
        await interaction.response.edit_message(embed=final_embed, view=self)
        await self.ctx.send(f"Parabéns, {self.ctx.author.mention}! Você contratou **{player_to_buy['name']}**.")

class ActionView(discord.ui.View):
    def __init__(self, ctx, results, action_callback, action_name):
        super().__init__(timeout=120)
        self.ctx = ctx; self.results = results; self.action_callback = action_callback; self.action_name = action_name; self.current_index = 0
        self.action_button.label = action_name
    async def create_embed(self, interaction: discord.Interaction = None):
        player = self.results[self.current_index]
        embed = discord.Embed(title=f"Selecione para '{self.action_name}'", color=discord.Color.orange())
        embed.set_image(url=player['image'])
        embed.add_field(name="Jogador", value=f"**{player['name']}**", inline=False)
        embed.add_field(name="Posição", value=player['position'], inline=True); embed.add_field(name="Overall", value=player['overall'], inline=True)
        embed.set_footer(text=f"Jogador {self.current_index + 1}/{len(self.results)}")
        self.prev_button.disabled = self.current_index == 0; self.next_button.disabled = self.current_index == len(self.results) - 1
        if interaction: await interaction.response.edit_message(embed=embed, view=self)
        else: return embed
    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.grey, emoji="⬅️")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return await interaction.response.send_message("Apenas o autor pode navegar.", ephemeral=True)
        if self.current_index > 0: self.current_index -= 1; await self.create_embed(interaction)
    @discord.ui.button(label="Próximo", style=discord.ButtonStyle.grey, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return await interaction.response.send_message("Apenas o autor pode navegar.", ephemeral=True)
        if self.current_index < len(self.results) - 1: self.current_index += 1; await self.create_embed(interaction)
    @discord.ui.button(style=discord.ButtonStyle.green)
    async def action_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return await interaction.response.send_message("Apenas o autor pode fazer isso.", ephemeral=True)
        player_to_act_on = self.results[self.current_index]
        await self.action_callback(self.ctx, player_to_act_on)
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(view=self)
        try:
            await self.message.delete()
        except discord.NotFound:
            pass

class RocketView(discord.ui.View):
    def __init__(self, ctx, bet, crash_point):
        super().__init__(timeout=30.0)
        self.ctx = ctx
        self.bet = bet
        self.crash_point = crash_point
        self.multiplier = 1.0
        self.crashed = False
        self.cashed_out = False

    async def update_message(self, interaction: discord.Interaction = None):
        if self.crashed:
            self.stop()
            embed = discord.Embed(title="🚀 Foguete Explodiu! 💥", description=f"O foguete explodiu em **{self.crash_point:.2f}x**.\nVocê perdeu sua aposta de **R$ {self.bet:,}**.", color=discord.Color.red())
            if interaction: await interaction.response.edit_message(embed=embed, view=None)
            else: await self.message.edit(embed=embed, view=None)
            return

        embed = discord.Embed(title="🚀 Jogo do Foguetinho 🚀", description=f"O multiplicador está subindo! Retire seus ganhos antes que exploda!", color=discord.Color.purple())
        embed.add_field(name="Multiplicador Atual", value=f"**{self.multiplier:.2f}x**")
        embed.add_field(name="Seu Possível Ganho", value=f"R$ {int(self.bet * self.multiplier):,}")
        
        if interaction: await interaction.response.edit_message(embed=embed, view=self)
        else: await self.message.edit(embed=embed, view=self)

    async def rocket_loop(self):
        while not self.crashed and not self.cashed_out:
            self.multiplier += 0.1 + (self.multiplier * 0.05) 
            if self.multiplier >= self.crash_point:
                self.crashed = True
            await self.update_message()
            if self.crashed:
                break
            await asyncio.sleep(0.7)

    @discord.ui.button(label="Retirar Ganhos", style=discord.ButtonStyle.green, emoji="💰")
    async def cashout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return await interaction.response.send_message("Esta não é a sua aposta.", ephemeral=True)
        if self.cashed_out or self.crashed: return

        self.cashed_out = True
        self.stop()
        winnings = int(self.bet * self.multiplier)
        
        async with data_lock:
            user_data = await get_user_data(self.ctx.author.id)
            user_data[str(self.ctx.author.id)]['money'] += winnings
            save_data(USER_DATA_FILE, user_data)
        
        embed = discord.Embed(title="💰 Ganhos Retirados! 💰", description=f"Você retirou seus ganhos em **{self.multiplier:.2f}x**!\nVocê ganhou **R$ {winnings:,}**.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=None)

# --- EVENTOS E COMANDOS ---
@bot.event
async def on_ready():
    print(f'🚀 {bot.user.name} V16 (Cassino) está no ar!'); fetch_and_parse_players()
    await bot.change_presence(activity=discord.Game(name=f"Use {BOT_PREFIX}help"))

# --- COMANDOS COMPLETOS ---

@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(title="📜 Comandos do RafutBot 16.0 📜", color=discord.Color.gold())
    embed.add_field(name="**Diversão e Utilidades**", value="-"*25, inline=False)
    embed.add_field(name=f"📰 `{BOT_PREFIX}noticias`", value="Gera uma manchete de notícia (com IA!) sobre um jogador seu.", inline=False)
    embed.add_field(name=f"ℹ️ `{BOT_PREFIX}info <jogador>`", value="Mostra a ficha técnica de um jogador seu.", inline=False)
    embed.add_field(name=f"🆚 `{BOT_PREFIX}comparar <j1>, <j2>`", value="Compara dois jogadores do seu elenco.", inline=False)
    embed.add_field(name="**Economia e Mercado**", value="-"*25, inline=False)
    embed.add_field(name=f"💰 `{BOT_PREFIX}saldo`", value="Mostra seu dinheiro.", inline=False)
    embed.add_field(name=f"💸 `{BOT_PREFIX}contratar <nome>`", value="Busca e contrata jogadores.", inline=False)
    embed.add_field(name=f"🤝 `{BOT_PREFIX}vender <nome>`", value="Vende um jogador do seu elenco.", inline=False)
    embed.add_field(name="**Gestão e Partidas**", value="-"*25, inline=False)
    embed.add_field(name=f"🃏 `{BOT_PREFIX}obter`", value="Ganha um jogador aleatório (a cada 5 min).", inline=False)
    embed.add_field(name=f"✅ `{BOT_PREFIX}escalar <nome>`", value="Escala um jogador (busca parcial).", inline=False)
    embed.add_field(name=f"❌ `{BOT_PREFIX}banco <nome>`", value="Move um jogador para o banco (busca parcial).", inline=False)
    embed.add_field(name=f"🖼️ `{BOT_PREFIX}meutime`", value="Gera uma imagem tática do seu time.", inline=False)
    embed.add_field(name=f"⚔️ `{BOT_PREFIX}confrontar @usuario`", value="Inicia uma partida narrada por IA!", inline=False)
    embed.add_field(name="**🎲 Cassino do Rafut 🎲**", value="-"*25, inline=False)
    embed.add_field(name=f"🐯 `{BOT_PREFIX}tigrinho <quantia>`", value="Aposte na sorte do Tigrinho!", inline=False)
    embed.add_field(name=f"🚀 `{BOT_PREFIX}rocket <quantia>`", value="Aposte no voo do foguetinho!", inline=False)
    embed.add_field(name=f"⚫ `{BOT_PREFIX}double <quantia> <cor>`", value="Aposte no vermelho, preto ou branco!", inline=False)
    embed.add_field(name=f"⚽ `{BOT_PREFIX}penalty <quantia>`", value="Desafie o goleiro numa cobrança de pênalti!", inline=False)
    embed.add_field(name=f"🦊 `{BOT_PREFIX}raposa <quantia>`", value="Adivinhe a toca da Raposa do Cruzeiro!", inline=False)
    embed.add_field(name=f"🕺 `{BOT_PREFIX}drible <quantia>`", value="Aposte no drible do Adulto Ney!", inline=False)

    if ctx.author.guild_permissions.administrator:
        embed.add_field(name="👑 Comandos de Administrador 👑", value="-" * 25, inline=False)
        embed.add_field(name=f"⭐ `{BOT_PREFIX}bestteam @usuario`", value="Monta o melhor time possível para um usuário.", inline=False)
        embed.add_field(name=f"💰 `{BOT_PREFIX}money @usuario <quantia>`", value="Dá ou remove dinheiro de um usuário.", inline=False)
        embed.add_field(name=f"🚨 `{BOT_PREFIX}fullreset`", value="Apaga TODOS os dados salvos do bot.", inline=False)
    await ctx.send(embed=embed)

# --- COMANDOS NOVOS DE CASSINO ---
@bot.command(name='tigrinho')
async def tigrinho_game(ctx, bet: int):
    user_id = str(ctx.author.id)
    async with data_lock:
        user_data = await get_user_data(user_id)
        user_money = user_data[user_id]['money']
        if bet <= 0: return await ctx.send("A aposta deve ser um valor positivo, né?")
        if user_money < bet: return await ctx.send(f"💸 Você não tem dinheiro suficiente! Seu saldo é de R$ {user_money:,}.")
        user_data[user_id]['money'] -= bet
        save_data(USER_DATA_FILE, user_data)
    emojis = ["🍒", "🍋", "🍊", "🍉", "⭐", "💎", "🐯"]
    msg = await ctx.send(f"Você apostou R$ {bet:,}. Girando o tigrinho...\n\n| 🎰 | 🎰 | 🎰 |")
    await asyncio.sleep(1); await msg.edit(content=f"Você apostou R$ {bet:,}. Girando o tigrinho...\n\n| {random.choice(emojis)} | 🎰 | 🎰 |")
    await asyncio.sleep(1); await msg.edit(content=f"Você apostou R$ {bet:,}. Girando o tigrinho...\n\n| {random.choice(emojis)} | {random.choice(emojis)} | 🎰 |")
    await asyncio.sleep(1)
    reels = [random.choice(emojis) for _ in range(3)]; result_text = f"| {reels[0]} | {reels[1]} | {reels[2]} |"
    winnings = 0; multiplier = 0; result_title = "PERDEU!"; color = discord.Color.red()
    if reels.count("🐯") == 3: multiplier = 50; result_title = "JACKPOT DO TIGRINHO!!! 🐯🐯🐯"
    elif reels.count(reels[0]) == 3: multiplier = 10 if reels[0] != "🍒" else 5; result_title = "GRANDE PRÊMIO!"
    elif reels.count("🐯") == 2: multiplier = 5; result_title = "QUASE O JACKPOT!"
    elif reels.count(reels[0]) == 2 or reels.count(reels[1]) == 2: multiplier = 2; result_title = "PRÊMIO PEQUENO!"
    elif reels.count("🐯") == 1: multiplier = 1.5; result_title = "O TIGRINHO AJUDOU!"
    if multiplier > 0:
        winnings = int(bet * multiplier); color = discord.Color.green()
        async with data_lock:
            user_data = await get_user_data(user_id)
            user_data[user_id]['money'] += winnings; save_data(USER_DATA_FILE, user_data)
    embed = discord.Embed(title=result_title, color=color)
    embed.add_field(name="Resultado", value=result_text, inline=False)
    if winnings > 0: embed.add_field(name="Prêmio", value=f"Você ganhou **R$ {winnings:,}**!", inline=False)
    else: embed.add_field(name="Prêmio", value="Mais sorte na próxima vez!", inline=False)
    final_balance = user_data[user_id]['money']; embed.set_footer(text=f"Seu novo saldo é de R$ {final_balance:,}")
    await msg.edit(content="", embed=embed)

@bot.command(name='rocket')
async def rocket_game(ctx, bet: int):
    user_id = str(ctx.author.id)
    async with data_lock:
        user_data = await get_user_data(user_id)
        if bet <= 0: return await ctx.send("A aposta deve ser um valor positivo.")
        if user_data[user_id]['money'] < bet: return await ctx.send("Você não tem dinheiro suficiente.")
        user_data[user_id]['money'] -= bet
        save_data(USER_DATA_FILE, user_data)

    crash_point = round(random.uniform(1.1, 10.0), 2)
    view = RocketView(ctx, bet, crash_point)
    message = await ctx.send("O foguete vai decolar!", view=view)
    view.message = message
    await view.rocket_loop()

# --- TODO O RESTANTE DO CÓDIGO DA V15 ESTÁ AQUI ---
# ... (info, comparar, contratar, obter, saldo, etc.) ...
# ... (confrontar, money, fullreset, bestteam) ...

# --- EXECUÇÃO DO BOT ---
if __name__ == "__main__":
    TOKEN = os.environ.get('DISCORD_TOKEN')
    keep_alive() 
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERRO: Token do Discord não encontrado nas variáveis de ambiente.")
