# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------
# RafutBot - Versão Definitiva Completa e Corrigida
# ----------------------------------------------------------------------
# Esta versão inclui todas as funcionalidades e correções para
# hospedagem persistente e todos os comandos.
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
# Caminhos de arquivo para persistência no Railway/Render (Volume)
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
                    save_data(USER_DATA_FILE, user_data)
                    save_data(CONTRACTED_PLAYERS_FILE, contracted)
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

@bot.command(name='noticias')
async def news(ctx):
    if not gemini_model: return await ctx.send("O serviço de notícias (IA) está indisponível no momento.")
    user_data = await get_user_data(ctx.author.id)
    squad = user_data[str(ctx.author.id)].get('squad')
    if not squad: return await ctx.send("Você precisa ter jogadores no elenco para gerar notícias!")
    player = random.choice(squad)
    prompt = f"Crie uma manchete de notícia de futebol curta, criativa e engraçada sobre o jogador {player['name']}. Pode ser sobre um lance bizarro, uma declaração polêmica ou algo do dia a dia. Seja criativo. Apenas a manchete."
    msg = await ctx.send(f"📰 Buscando as últimas fofocas sobre **{player['name']}** nos arquivos da IA...")
    headline = await generate_ai_narration(prompt, f" manchete sobre {player['name']} não encontrada.")
    embed = discord.Embed(title="🗞️ PLANTÃO RAFUTNEWS 🗞️", description=f"## \"{headline}\"", color=discord.Color.blurple())
    embed.set_image(url=player['image'])
    embed.set_footer(text=f"Uma fonte totalmente confiável, com certeza.")
    await msg.edit(content="", embed=embed)

@bot.command(name='info')
async def info(ctx, *, query: str):
    search_query = normalize_str(query)
    user_data = await get_user_data(ctx.author.id)
    squad = user_data[str(ctx.author.id)]['squad']
    target_player = next((p for p in squad if search_query in normalize_str(p['name'])), None)
    if not target_player: return await ctx.send(f"Jogador `{query}` não encontrado no seu elenco.")
    embed = discord.Embed(title=f"Ficha Técnica - {target_player['name']}", color=discord.Color.dark_green())
    embed.set_image(url=target_player['image'])
    embed.add_field(name="Overall", value=f"**{target_player['overall']}** ⭐", inline=True)
    embed.add_field(name="Posição", value=f"**{target_player['position']}**", inline=True)
    embed.add_field(name="Valor de Mercado", value=f"**R$ {target_player['value']:,}** 💸", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='comparar')
async def compare(ctx, *, query: str):
    try:
        name1, name2 = [normalize_str(n.strip()) for n in query.split(',')]
    except ValueError:
        return await ctx.send(f"Formato inválido. Use: `{BOT_PREFIX}comparar <nome1>, <nome2>`")
    user_data = await get_user_data(ctx.author.id)
    squad = user_data[str(ctx.author.id)]['squad']
    p1 = next((p for p in squad if name1 in normalize_str(p['name'])), None)
    p2 = next((p for p in squad if name2 in normalize_str(p['name'])), None)
    if not p1 or not p2: return await ctx.send("Um ou ambos os jogadores não foram encontrados no seu elenco.")
    embed = discord.Embed(title=f"🆚 Comparação: {p1['name']} vs {p2['name']}", color=discord.Color.dark_orange())
    def get_stat_comparison(stat_name, val1, val2):
        if val1 > val2: return f"**{val1}** > {val2}"
        elif val2 > val1: return f"{val1} < **{val2}**"
        else: return f"{val1} = {val2}"
    embed.add_field(name="Overall", value=get_stat_comparison("Overall", p1['overall'], p2['overall']), inline=False)
    embed.add_field(name="Valor", value=get_stat_comparison("Valor", p1['value'], p2['value']), inline=False)
    embed.add_field(name=p1['name'], value=f"**Pos:** {p1['position']}", inline=True)
    embed.add_field(name=p2['name'], value=f"**Pos:** {p2['position']}", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='contratar', aliases=['comprar'])
async def contract_player(ctx, *, query: str):
    search_query = normalize_str(query)
    contracted = load_data(CONTRACTED_PLAYERS_FILE)
    available_players = [p for p in ALL_PLAYERS if p["name"] not in contracted]
    results = [p for p in available_players if search_query in normalize_str(p['name']) or search_query.upper() == p['position']]
    if not results: return await ctx.send(f"😥 Nenhum jogador disponível encontrado para a busca: `{query}`")
    results.sort(key=lambda p: p['value'], reverse=True)
    view = ContractView(ctx, results)
    embed = await view.create_embed(); view.message = await ctx.send(embed=embed, view=view)

@bot.command(name='obter')
@commands.cooldown(1, 300, commands.BucketType.user)
async def get_player(ctx):
    async with data_lock:
        contracted = load_data(CONTRACTED_PLAYERS_FILE)
        available = [p for p in ALL_PLAYERS if p["name"] not in contracted]
        if not available: return await ctx.send("🤯 **Mercado Vazio!**")
        player = random.choice(available); contracted.append(player["name"]); save_data(CONTRACTED_PLAYERS_FILE, contracted)
    sale_price = int(player['value'] * SALE_PERCENTAGE)
    embed = discord.Embed(title="🃏 Você tirou uma carta!", color=discord.Color.blue())
    embed.set_image(url=player["image"])
    embed.add_field(name=player['name'], value=f"**Overall:** {player['overall']} | **Posição:** {player['position']}")
    embed.add_field(name="Valor de Venda Rápida", value=f"R$ {sale_price:,}")
    view = KeepOrSellView(ctx.author, player); message = await ctx.send(embed=embed, view=view); view.message = message

@get_player.error
async def get_player_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown): await ctx.send(f"⏳ **Acalme-se!** Tente novamente em **{int(error.retry_after)} segundos**.")

@bot.command(name='saldo')
async def balance(ctx):
    user_data = await get_user_data(ctx.author.id); money = user_data[str(ctx.author.id)]['money']
    await ctx.send(f"💰 {ctx.author.mention}, seu saldo é de **R$ {money:,}**.")

@bot.command(name='loja')
async def shop(ctx):
    contracted = load_data(CONTRACTED_PLAYERS_FILE); available = [p for p in ALL_PLAYERS if p["name"] not in contracted]
    if not available: return await ctx.send("🤯 **Mercado Vazio!**")
    results = sorted(available, key=lambda p: p['value'], reverse=True)[:10]
    description = "\n".join([f"**{p['name']}** ({p['position']}) - `R$ {p['value']:,}`" for p in results])
    embed = discord.Embed(title="🛒 Top 10 Jogadores da Loja 🛒", description=description, color=discord.Color.dark_gold())
    embed.set_footer(text=f"Use {BOT_PREFIX}contratar <nome> para buscar e comprar.")
    await ctx.send(embed=embed)

async def perform_escalar(ctx, player):
    async with data_lock:
        all_data = await get_user_data(ctx.author.id); user_id = str(ctx.author.id)
        team = all_data[user_id]['team']
        if any(p and p['name'] == player['name'] for p in team): return await ctx.send(f"**{player['name']}** já está escalado.")
        position = player['position']
        if position not in SLOT_MAPPING: return await ctx.send(f"Posição `{position}` inválida.")
        valid_slots = SLOT_MAPPING[position]; empty_slot = next((i for i in valid_slots if team[i] is None), -1)
        if empty_slot != -1:
            team[empty_slot] = player; save_data(USER_DATA_FILE, all_data)
            await ctx.send(f"✅ **{player['name']}** foi escalado como **{position}**!")
        else: await ctx.send(f"🚫 **Posição Cheia!** Vagas de **{position}** ocupadas.")

@bot.command(name='escalar')
async def set_player(ctx, *, query: str):
    search_query = normalize_str(query)
    user_data = await get_user_data(ctx.author.id)
    squad = user_data[str(ctx.author.id)]['squad']
    results = [p for p in squad if search_query in normalize_str(p['name'])]
    if not results: return await ctx.send(f"Nenhum jogador encontrado no seu elenco com o nome: `{query}`")
    if len(results) == 1: await perform_escalar(ctx, results[0])
    else:
        view = ActionView(ctx, results, perform_escalar, "Escalar")
        embed = await view.create_embed(); view.message = await ctx.send(embed=embed, view=view)

async def perform_banco(ctx, player):
    async with data_lock:
        all_data = await get_user_data(ctx.author.id); user_id = str(ctx.author.id)
        team = all_data[user_id]['team']
        idx = next((i for i, p in enumerate(team) if p and p['name'] == player['name']), -1)
        if idx == -1: return
        player_name_unset = team[idx]['name']; team[idx] = None; save_data(USER_DATA_FILE, all_data)
        await ctx.send(f"❌ **{player_name_unset}** foi para o banco de reservas.")

@bot.command(name='banco')
async def unset_player(ctx, *, query: str):
    search_query = normalize_str(query)
    user_data = await get_user_data(ctx.author.id)
    team = user_data[str(ctx.author.id)]['team']
    results = [p for p in team if p and search_query in normalize_str(p['name'])]
    if not results: return await ctx.send(f"Nenhum jogador encontrado no seu time titular com o nome: `{query}`")
    if len(results) == 1: await perform_banco(ctx, results[0])
    else:
        view = ActionView(ctx, results, perform_banco, "Mandar para o Banco")
        embed = await view.create_embed(); view.message = await ctx.send(embed=embed, view=view)

async def perform_vender(ctx, player):
    async with data_lock:
        user_data = await get_user_data(ctx.author.id); user_id = str(ctx.author.id)
        team = user_data[user_id]['team']
        for i, p_team in enumerate(team):
            if p_team and p_team['name'] == player['name']: team[i] = None; break
        sale_price = int(player['value'] * SALE_PERCENTAGE)
        user_data[user_id]['money'] += sale_price
        user_data[user_id]['squad'] = [p for p in user_data[user_id]['squad'] if p['name'] != player['name']]
        contracted = load_data(CONTRACTED_PLAYERS_FILE); contracted = [p_name for p_name in contracted if p_name != player['name']]
        save_data(USER_DATA_FILE, user_data); save_data(CONTRACTED_PLAYERS_FILE, contracted)
    await ctx.send(f"💰 Você vendeu **{player['name']}** por **R$ {sale_price:,}**!")

@bot.command(name='vender')
async def sell_player(ctx, *, query: str):
    search_query = normalize_str(query)
    user_data = await get_user_data(ctx.author.id)
    squad = user_data[str(ctx.author.id)]['squad']
    results = [p for p in squad if search_query in normalize_str(p['name'])]
    if not results: return await ctx.send(f"Nenhum jogador encontrado no seu elenco com o nome: `{query}`")
    if len(results) == 1: await perform_vender(ctx, results[0])
    else:
        view = ActionView(ctx, results, perform_vender, "Vender")
        embed = await view.create_embed(); view.message = await ctx.send(embed=embed, view=view)

@bot.command(name='elenco')
async def squad(ctx):
    user_data = await get_user_data(ctx.author.id); squad_players = user_data[str(ctx.author.id)]["squad"]
    if not squad_players: return await ctx.send(f"텅 **Elenco Vazio!**")
    embed = discord.Embed(title=f"🎽 Elenco de {ctx.author.display_name} 🎽", color=ctx.author.color)
    embed.description = "\n".join([f"**{p['name']}** | `{p['position']}` | Overall: **{p['overall']}**" for p in sorted(squad_players, key=lambda p: p['name'])])
    await ctx.send(embed=embed)

@bot.command(name='limpartime')
async def clear_team(ctx):
    async with data_lock:
        all_data = await get_user_data(ctx.author.id)
        all_data[str(ctx.author.id)]['team'] = [None] * 11; save_data(USER_DATA_FILE, all_data)
    await ctx.send("🗑️ **Time Limpo!**")

@bot.command(name='meutime')
async def my_team(ctx):
    user_data = await get_user_data(ctx.author.id); team = user_data[str(ctx.author.id)]["team"]
    if not any(team): return await ctx.send(f"Você não escalou ninguém!")
    msg = await ctx.send("⚙️ Montando a imagem do time..."); image_file = await generate_team_image(team, ctx.author.display_name)
    await ctx.send(file=discord.File(image_file, 'meutime.png')); await msg.delete()

@bot.command(name='ranking')
async def ranking(ctx):
    user_data = load_data(USER_DATA_FILE)
    if not user_data: return await ctx.send("Ainda não há dados.")
    sorted_users = sorted([(uid, data['wins']) for uid, data in user_data.items() if data.get('wins', 0) > 0], key=lambda i: i[1], reverse=True)
    if not sorted_users: return await ctx.send("🏆 **Ranking Vazio!**")
    embed = discord.Embed(title="🏆 Ranking de Vitórias - Top 10 🏆", color=discord.Color.purple())
    desc = []
    medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, wins) in enumerate(sorted_users[:10]):
        try: user = await bot.fetch_user(int(user_id)); user_name = user.display_name
        except (discord.NotFound, ValueError): user_name = "Usuário Desconhecido"
        medal = medals[i] if i < 3 else "🔹"
        desc.append(f"{medal} **{user_name}** - `{wins}` vitórias")
    embed.description = "\n".join(desc); await ctx.send(embed=embed)

@bot.command(name='resetar')
async def reset_account(ctx):
    embed = discord.Embed(title="⚠️ ATENÇÃO: Resetar Conta ⚠️", description=f"Tem certeza, {ctx.author.mention}?\n\nIsso apagará tudo. **Não pode ser desfeito.**\n\nDigite `sim` para confirmar.", color=discord.Color.red())
    await ctx.send(embed=embed)
    def check(m): return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == 'sim'
    try: await bot.wait_for('message', timeout=30.0, check=check)
    except asyncio.TimeoutError: return await ctx.send("Reset cancelado.")
    async with data_lock:
        user_data = load_data(USER_DATA_FILE); contracted_players = load_data(CONTRACTED_PLAYERS_FILE)
        user_id = str(ctx.author.id)
        if user_id in user_data:
            players_to_release = {p['name'] for p in user_data[user_id].get("squad", [])}
            contracted_players = [name for name in contracted_players if name not in players_to_release]
            del user_data[user_id]
            save_data(USER_DATA_FILE, user_data); save_data(CONTRACTED_PLAYERS_FILE, contracted_players)
            await ctx.send("✅ **Conta resetada!**")
        else: await ctx.send("Você não possui dados para resetar.")

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
    async def logic(ctx, bet):
        crash_point = round(random.uniform(1.1, 10.0), 2)
        view = RocketView(ctx, bet, crash_point)
        message = await ctx.send("O foguete vai decolar!", view=view)
        view.message = message
        await view.rocket_loop()
    await generic_bet_handler(ctx, bet, logic)

@bot.command(name='double')
async def double_game(ctx, bet: int, color: str):
    valid_colors = {"vermelho": "🔴", "preto": "⚫", "branco": "⚪"}
    color_choice = color.lower()
    if color_choice not in valid_colors:
        return await ctx.send("Cor inválida! Escolha entre `vermelho`, `preto` ou `branco`.")
    async def logic(ctx, bet):
        outcome_color_key = random.choices(["vermelho", "preto", "branco"], weights=[47.5, 47.5, 5], k=1)[0]
        outcome_emoji = valid_colors[outcome_color_key]
        msg = await ctx.send(f"A roleta está girando... 🌀")
        await asyncio.sleep(2)
        winnings = 0; result_title = "Você Perdeu!"; result_color = discord.Color.red()
        if color_choice == outcome_color_key:
            multiplier = 14 if color_choice == "branco" else 2
            winnings = bet * multiplier
            result_title = "Você Ganhou!"; result_color = discord.Color.green()
            final_balance = await handle_winnings(ctx.author.id, winnings)
        else:
            user_data = await get_user_data(ctx.author.id)
            final_balance = user_data[str(ctx.author.id)]['money']
        embed = discord.Embed(title=result_title, color=result_color)
        embed.add_field(name="Resultado", value=f"A cor sorteada foi: {outcome_emoji} **{outcome_color_key.upper()}**")
        if winnings > 0:
            embed.add_field(name="Prêmio", value=f"Você ganhou **R$ {winnings:,}**!", inline=False)
        embed.set_footer(text=f"Seu novo saldo é de R$ {final_balance:,}")
        await msg.edit(content="", embed=embed)
    await generic_bet_handler(ctx, bet, logic)

@bot.command(name='penalty')
async def penalty_game(ctx, bet: int):
    class PenaltyView(discord.ui.View):
        def __init__(self, author):
            super().__init__(timeout=30)
            self.author = author; self.choice = None
        @discord.ui.button(label="Esquerda", style=discord.ButtonStyle.secondary, emoji="⬅️")
        async def left_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author: return
            self.choice = "esquerda"; self.stop(); await interaction.response.defer()
        @discord.ui.button(label="Meio", style=discord.ButtonStyle.secondary, emoji="⬆️")
        async def middle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author: return
            self.choice = "meio"; self.stop(); await interaction.response.defer()
        @discord.ui.button(label="Direita", style=discord.ButtonStyle.secondary, emoji="➡️")
        async def right_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author: return
            self.choice = "direita"; self.stop(); await interaction.response.defer()
    async def logic(ctx, bet):
        view = PenaltyView(ctx.author)
        msg = await ctx.send("⚽ **HORA DO PÊNALTI!** Escolha o canto para chutar:", view=view)
        await view.wait()
        if not view.choice: await msg.edit(content="Você demorou para chutar e o juiz apitou o fim! Aposta perdida.", view=None); return
        goalkeeper_choice = random.choice(["esquerda", "meio", "direita"])
        if view.choice == goalkeeper_choice:
            user_data = await get_user_data(ctx.author.id); final_balance = user_data[str(ctx.author.id)]['money']
            embed = discord.Embed(title="🧤 DEFENDEU!", description=f"O goleiro pulou no canto certo e pegou! Você perdeu R$ {bet:,}.", color=discord.Color.red())
        else:
            winnings = bet * 2; final_balance = await handle_winnings(ctx.author.id, winnings)
            embed = discord.Embed(title="⚽ GOOOOL!", description=f"Você cobrou com categoria e ganhou **R$ {winnings:,}**!", color=discord.Color.green())
        embed.set_footer(text=f"Seu novo saldo é de R$ {final_balance:,}")
        await msg.edit(content="", embed=embed, view=None)
    await generic_bet_handler(ctx, bet, logic)

@bot.command(name='raposa')
async def fox_game(ctx, bet: int):
    options = ["1️⃣", "2️⃣", "3️⃣"]
    class FoxView(discord.ui.View):
        def __init__(self, author):
            super().__init__(timeout=30)
            self.author = author; self.choice = None
            for emoji in options:
                self.add_item(discord.ui.Button(label=f"Toca {emoji}", style=discord.ButtonStyle.secondary, custom_id=emoji))
        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user != self.author: await interaction.response.send_message("Essa aposta não é sua!", ephemeral=True); return False
            self.choice = interaction.data['custom_id']; self.stop(); await interaction.response.defer()
            return True
    async def logic(ctx, bet):
        view = FoxView(ctx.author)
        msg = await ctx.send("🦊 **Jogo da Raposa!** Onde a raposa do Cruzeiro vai sair? Escolha uma toca:", view=view)
        await view.wait()
        if not view.choice: await msg.edit(content="A raposa se cansou de esperar e foi embora! Aposta perdida.", view=None); return
        correct_hole = random.choice(options)
        if view.choice == correct_hole:
            winnings = bet * 3; final_balance = await handle_winnings(ctx.author.id, winnings)
            embed = discord.Embed(title="🦊 Você Achou a Raposa!", description=f"Ela saiu na toca **{correct_hole}**! Você ganhou **R$ {winnings:,}**!", color=discord.Color.blue())
        else:
            user_data = await get_user_data(ctx.author.id); final_balance = user_data[str(ctx.author.id)]['money']
            embed = discord.Embed(title="A Raposa te Enganou!", description=f"Você escolheu a toca {view.choice}, mas ela saiu na **{correct_hole}**! Você perdeu R$ {bet:,}.", color=discord.Color.red())
        embed.set_footer(text=f"Seu novo saldo é de R$ {final_balance:,}"); await msg.edit(content="", embed=embed, view=None)
    await generic_bet_handler(ctx, bet, logic)

@bot.command(name='drible')
async def neymar_drible(ctx, bet: int):
    async def logic(ctx, bet):
        msg = await ctx.send("🕺 O Adulto Ney parte pra cima do zagueiro... Será que ele vai entortar o coitado?")
        await asyncio.sleep(2)
        if random.random() < 0.55:
            winnings = int(bet * 1.8); final_balance = await handle_winnings(ctx.author.id, winnings)
            embed = discord.Embed(title="🕺 OLHA O DRIBLE!", description=f"QUE CANETA! O zagueiro tá procurando a bola até agora! Você ganhou **R$ {winnings:,}**!", color=discord.Color.green())
        else:
            user_data = await get_user_data(ctx.author.id); final_balance = user_data[str(ctx.author.id)]['money']
            embed = discord.Embed(title="🧱 PAREDÃO!", description=f"O zagueiro deu um bote certeiro e desarmou o Adulto Ney! Você perdeu R$ {bet:,}.", color=discord.Color.red())
        embed.set_footer(text=f"Seu novo saldo é de R$ {final_balance:,}"); await msg.edit(content="", embed=embed)
    await generic_bet_handler(ctx, bet, logic)

@bot.command(name='confrontar')
async def confront(ctx, opponent: discord.Member):
    author = ctx.author
    if author == opponent: return await ctx.send("😑 Você não pode se desafiar.")
    if opponent.bot: return await ctx.send("🤖 Você não pode desafiar um bot.")
    async with data_lock:
        all_data = load_data(USER_DATA_FILE)
        author_id, opp_id = str(author.id), str(opponent.id)
        if not (author_id in all_data and opp_id in all_data): return await ctx.send("Um dos jogadores não tem dados.")
        author_team = all_data[author_id].get("team", []); opp_team = all_data[opp_id].get("team", [])
        if None in author_team or None in opp_team: return await ctx.send("⚠️ **Times Incompletos!** Ambos precisam ter 11 jogadores escalados.")
    def get_team_sector(team, positions): return [p for p in team if p and p['position'] in positions]
    teams = {
        author.id: {"user": author, "players": author_team, "attack": get_team_sector(author_team, ['PE', 'PD', 'CA', 'MEI']), "mid": get_team_sector(author_team, ['MC', 'VOL']), "def": get_team_sector(author_team, ['ZAG', 'LE', 'LD']), "keeper": get_team_sector(author_team, ['GOL'])[0]},
        opponent.id: {"user": opponent, "players": opp_team, "attack": get_team_sector(opp_team, ['PE', 'PD', 'CA', 'MEI']), "mid": get_team_sector(opp_team, ['MC', 'VOL']), "def": get_team_sector(opp_team, ['ZAG', 'LE', 'LD']), "keeper": get_team_sector(opp_team, ['GOL'])[0]}
    }
    score = {author.id: 0, opponent.id: 0}; goalscorers = {author.id: [], opponent.id: []}; match_log = ["🎙️ **Narrador:** Começa o jogo! Uma grande partida nos espera!"]
    embed = discord.Embed(title=f"🔵 {author.display_name} vs {opponent.display_name} 🔴", color=discord.Color.greyple())
    embed.add_field(name="Placar", value=f"0 - 0", inline=False).add_field(name="Ao Vivo 🔴", value="```\n" + "\n".join(match_log) + "\n```", inline=False)
    match_message = await ctx.send(embed=embed)
    ball_holder = None; possession_team_id = random.choice([author.id, opponent.id])
    for minute in range(1, 92):
        await asyncio.sleep(1.5)
        mid_battle = sum(p['overall'] for p in teams[author.id]["mid"]) - sum(p['overall'] for p in teams[opponent.id]["mid"])
        if random.random() < (0.5 + mid_battle / 250): possession_team_id = author.id
        else: possession_team_id = opponent.id
        attacker_id = possession_team_id; defender_id = opponent.id if possession_team_id == author.id else author.id
        event_chance = (sum(p['overall'] for p in teams[attacker_id]["attack"]) / len(teams[attacker_id]["attack"])) / 250.0
        if random.random() > event_chance:
            if not ball_holder: ball_holder = random.choice(teams[attacker_id]["mid"])
            new_ball_holder = random.choice(teams[attacker_id]["players"])
            log_entry = f"{minute}' - **{teams[attacker_id]['user'].display_name}** com a posse. **{ball_holder['name']}** toca para **{new_ball_holder['name']}**."
            ball_holder = new_ball_holder
        else:
            playmaker = random.choice(teams[attacker_id]["mid"]); attacker = random.choice(teams[attacker_id]["attack"]); defender = random.choice(teams[defender_id]["def"]); keeper = teams[defender_id]["keeper"]
            log_entry = f"⚡ {minute}' - **{playmaker['name']}** inicia o ataque! Ele lança para **{attacker['name']}**..."
            match_log.append(log_entry); embed.set_field_at(1, name="Ao Vivo 🔴", value="```\n" + "\n".join(match_log[-5:]) + "\n```"); await match_message.edit(embed=embed)
            await asyncio.sleep(2)
            dribble_success = (attacker['overall'] - defender['overall']) > random.randint(-25, 25)
            if not dribble_success:
                log_entry = f"🧱 **{defender['name']}** chega junto e corta a jogada! Que categoria do zagueirão."
            else:
                log_entry = f"🏃‍♂️ **{attacker['name']}** passa por **{defender['name']}** e fica de frente pro gol! VAI CHUTAR..."
                match_log.append(log_entry); embed.set_field_at(1, name="Ao Vivo 🔴", value="```\n" + "\n".join(match_log[-5:]) + "\n```"); await match_message.edit(embed=embed)
                await asyncio.sleep(2.5)
                shot_power = attacker['overall'] + random.randint(-10, 10); save_power = keeper['overall'] + random.randint(-15, 15)
                outcome = random.choices(['goal', 'save', 'post', 'miss', 'penalty'], weights=[35, 30, 10, 15, 10], k=1)[0]
                if shot_power < save_power and outcome == 'goal': outcome = 'save'
                if outcome == 'goal':
                    if random.random() < 0.15:
                        await asyncio.sleep(2); log_entry = f"⚠️ {minute}' - O VAR está checando um possível impedimento..."
                        embed.set_field_at(1, name="Ao Vivo 🔴", value="```\n" + "\n".join(match_log + [log_entry]) + "\n```"); await match_message.edit(embed=embed)
                        await asyncio.sleep(4)
                        if random.random() < 0.3: log_entry = f"❌ {minute}' - GOL ANULADO! O VAR pegou impedimento de {attacker['name']}!"
                        else: score[attacker_id] += 1; goalscorers[attacker_id].append(f"{attacker['name']} ({playmaker['name']}) {minute}'"); log_entry = f"✅ {minute}' - GOL CONFIRMADO! É bola na rede!"
                    else:
                        score[attacker_id] += 1; goalscorers[attacker_id].append(f"{attacker['name']} ({playmaker['name']}) {minute}'")
                        prompt = f"Você é um narrador de futebol brasileiro, como Cleber Machado ou Galvão Bueno. Narre um gol de forma empolgante. Marcador do Gol: {attacker['name']}. Jogador que deu a assistência: {playmaker['name']}. Seja criativo e use gírias de futebol."
                        log_entry = await generate_ai_narration(prompt, f"⚽ GOOOOL! {attacker['name']} marca!")
                elif outcome == 'save':
                    prompt = f"Você é um narrador de futebol brasileiro. Narre uma defesa muito difícil e espetacular. Goleiro: {keeper['name']}. Atacante que chutou: {attacker['name']}. Seja criativo."
                    log_entry = await generate_ai_narration(prompt, f"🧤 QUE DEFESA! {keeper['name']} faz um milagre!")
                elif outcome == 'post': log_entry = f"💥 NO POSTE! {attacker['name']} carimba a trave! Quase o gol!"
                elif outcome == 'penalty':
                    log_entry = f"🚨 PÊNALTI! {defender['name']} derruba {attacker['name']} na área!"; await asyncio.sleep(2)
                    penalty_shot = attacker['overall'] + random.randint(-5, 5); penalty_save = keeper['overall'] + random.randint(-15, 15)
                    if penalty_shot > penalty_save:
                        score[attacker_id] += 1; goalscorers[attacker_id].append(f"{attacker['name']} (P) {minute}'"); log_entry += f"\n⚽ GOOOOL DE PÊNALTI! {attacker['name']} cobra com perfeição!"
                    else: log_entry += f"\n🧤 DEFENDEU {keeper['name'].upper()}! O goleiro pega o pênalti!"
                else: log_entry = f"🤦‍♂️ PRA FORA! Que chance perdida por **{attacker['name']}**! Ele isolou a bola!"
        match_log.append(log_entry)
        embed.set_field_at(0, name="Placar", value=f"🔵 {score[author.id]} - {score[opponent.id]} 🔴")
        embed.set_field_at(1, name="Ao Vivo 🔴", value="```\n" + "\n".join(match_log[-5:]) + "\n```")
        if minute == 45: match_log.append("\n⏸️ **FIM DO PRIMEIRO TEMPO!**\n")
        await match_message.edit(embed=embed)
    await asyncio.sleep(3)
    winner = None
    if score[author.id] > score[opponent.id]: winner = author
    elif score[opponent.id] > score[author.id]: winner = opponent
    final_embed = discord.Embed(title="🏁 FIM DE JOGO 🏁", color=discord.Color.gold())
    final_embed.add_field(name="Resultado Final", value=f"**{author.display_name} {score[author.id]} x {score[opponent.id]} {opponent.display_name}**", inline=False)
    if winner:
        final_embed.description = f"🏆 O grande vencedor é **{winner.mention}**! 🏆"
        async with data_lock:
            winner_data = await get_user_data(winner.id)
            winner_data[str(winner.id)]["wins"] += 1; save_data(USER_DATA_FILE, winner_data)
    else: final_embed.description = "🤝 A partida terminou em empate! 🤝"
    author_scorers = ", ".join(goalscorers[author.id]) or "Ninguém"; opp_scorers = ", ".join(goalscorers[opponent.id]) or "Ninguém"
    final_embed.add_field(name=f"Gols de {author.display_name}", value=author_scorers, inline=True)
    final_embed.add_field(name=f"Gols de {opponent.display_name}", value=opp_scorers, inline=True)
    await match_message.edit(embed=final_embed)

# --- COMANDOS DE ADMINISTRADOR ---
@bot.command(name='money')
@commands.has_permissions(administrator=True)
async def give_money(ctx, user: discord.Member, amount: int):
    if user.bot: return await ctx.send("Você não pode dar dinheiro para um bot.")
    if amount == 0: return await ctx.send("A quantia não pode ser zero.")
    async with data_lock:
        all_data = await get_user_data(user.id)
        user_id = str(user.id); all_data[user_id]['money'] += amount; save_data(USER_DATA_FILE, all_data)
    verb = "adicionados" if amount > 0 else "removidos"; new_balance = all_data[str(user.id)]['money']
    await ctx.send(f"✅ Sucesso! **R$ {abs(amount):,}** foram {verb} para a conta de {user.mention}.\nSaldo atual: R$ {new_balance:,}.")

@give_money.error
async def give_money_error(ctx, error):
    if isinstance(error, commands.MissingPermissions): await ctx.send("🚫 Você não tem permissão para usar este comando.")
    elif isinstance(error, commands.BadArgument): await ctx.send("Uso incorreto. Formato: `--money @usuario <quantia>`")
    elif isinstance(error, commands.MissingRequiredArgument): await ctx.send("Faltam argumentos. Formato: `--money @usuario <quantia>`")

@bot.command(name='fullreset')
@commands.has_permissions(administrator=True)
async def full_reset(ctx):
    embed = discord.Embed(title="🚨 ALERTA MÁXIMO - RESET TOTAL 🚨", description="**Esta ação é irreversível e apagará TUDO.**\nPara confirmar, digite `EU TENHO CERTEZA E QUERO RESETAR O BOT`.", color=discord.Color.from_rgb(255, 0, 0))
    await ctx.send(embed=embed)
    def check(m): return m.author == ctx.author and m.channel == ctx.channel and m.content == "EU TENHO CERTEZA E QUERO RESETAR O BOT"
    try: await bot.wait_for('message', timeout=60.0, check=check)
    except asyncio.TimeoutError: return await ctx.send("Tempo esgotado. O reset total foi cancelado.")
    msg = await ctx.send("💥 **Confirmado.** Iniciando reset total...")
    async with data_lock:
        files_deleted = []
        try:
            if os.path.exists(USER_DATA_FILE): os.remove(USER_DATA_FILE); files_deleted.append(USER_DATA_FILE)
            if os.path.exists(CONTRACTED_PLAYERS_FILE): os.remove(CONTRACTED_PLAYERS_FILE); files_deleted.append(CONTRACTED_PLAYERS_FILE)
        except Exception as e: return await msg.edit(content=f"❌ Erro ao apagar arquivos: {e}")
    await msg.edit(content=f"🗑️ Arquivos `{', '.join(files_deleted)}` foram apagados.\n\n✅ **RESET TOTAL CONCLUÍDO.**\nÉ altamente recomendável que você **reinicie o bot agora**.")

@full_reset.error
async def full_reset_error(ctx, error):
    if isinstance(error, commands.MissingPermissions): await ctx.send("🚫 Você não tem permissão para usar este comando.")

@bot.command(name='bestteam')
@commands.has_permissions(administrator=True)
async def best_team(ctx, user: discord.Member):
    if user.bot: return await ctx.send("Bots não podem ter times.")
    await ctx.send(f"🤖 Montando o time dos sonhos para {user.mention}... Isso pode levar um momento.")
    async with data_lock:
        all_user_data = load_data(USER_DATA_FILE)
        contracted_players = load_data(CONTRACTED_PLAYERS_FILE)
        target_user_id = str(user.id)
        if target_user_id not in all_user_data:
            all_user_data[target_user_id] = {"squad": [], "team": [None] * 11, "wins": 0, "money": INITIAL_MONEY}
        current_squad_names = {p['name'] for p in all_user_data[target_user_id].get("squad", [])}
        contracted_players = [p_name for p_name in contracted_players if p_name not in current_squad_names]
        all_user_data[target_user_id]['squad'] = []
        all_user_data[target_user_id]['team'] = [None] * 11
        new_team = [None] * 11
        formation_slots = {
            0: "GOL", 1: "ZAG", 2: "ZAG", 3: "LE", 4: "LD", 5: "VOL", 
            6: "MC", 7: "MEI", 8: "PE", 9: "PD", 10: "CA"
        }
        used_player_names_for_team = set()
        for slot_index, position in formation_slots.items():
            candidates = [p for p in ALL_PLAYERS if p['position'] == position and p['name'] not in contracted_players and p['name'] not in used_player_names_for_team]
            candidates.sort(key=lambda p: p['overall'], reverse=True)
            if candidates:
                best_player = candidates[0]
                new_team[slot_index] = best_player
                contracted_players.append(best_player['name'])
                used_player_names_for_team.add(best_player['name'])
        all_user_data[target_user_id]['team'] = new_team
        all_user_data[target_user_id]['squad'] = [p for p in new_team if p]
        save_data(USER_DATA_FILE, all_user_data)
        save_data(CONTRACTED_PLAYERS_FILE, contracted_players)
    await ctx.send(f"✅ Time dos sonhos montado para {user.mention}! Use `{BOT_PREFIX}meutime` para ver o resultado.")

@best_team.error
async def best_team_error(ctx, error):
    if isinstance(error, commands.MissingPermissions): await ctx.send("🚫 Você não tem permissão para usar este comando.")
    elif isinstance(error, commands.MissingRequiredArgument): await ctx.send("Uso incorreto. Formato: `--bestteam @usuario`")

# --- EXECUÇÃO DO BOT ---
if __name__ == "__main__":
    TOKEN = os.environ.get('DISCORD_TOKEN')
    keep_alive() 
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERRO: Token do Discord não encontrado nas variáveis de ambiente.")
