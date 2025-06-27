# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------
# RafutBot - Versão 19.0 - Edição Manager
# ----------------------------------------------------------------------
# Esta versão corrige a falha no comando --confrontar e adiciona um
# sistema completo de personalização de nome e tag dos times.
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
from datetime import datetime, timedelta

# --- CONFIGURAÇÕES GERAIS ---
BOT_PREFIX = "--"
PASTEBIN_URL = "https://pastebin.com/raw/YpjKyzdw"
USER_DATA_FILE = "/data/rafutbot_user_data.json"
CONTRACTED_PLAYERS_FILE = "/data/rafutbot_contracted_players.json"
GLOBAL_STATS_FILE = "/data/rafutbot_global_stats.json"
INITIAL_MONEY = 1000000000
SALE_PERCENTAGE = 0.5
DAILY_REWARD = 25000000

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

def load_data(filename, default_data=None):
    if default_data is None: default_data = {}
    if not os.path.exists(filename): return default_data
    try:
        with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return default_data

def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

async def get_user_data(user_id):
    user_data = load_data(USER_DATA_FILE, {})
    user_id_str = str(user_id)
    # Tenta obter o nome de usuário. Pode falhar se o bot estiver iniciando e o cache não estiver pronto.
    display_name = "Técnico"
    try:
        user_obj = bot.get_user(int(user_id_str)) or await bot.fetch_user(int(user_id_str))
        if user_obj: display_name = user_obj.display_name
    except (discord.NotFound, discord.HTTPException):
        pass # Usa o nome padrão se o usuário não for encontrado

    if user_id_str not in user_data:
        user_data[user_id_str] = {
            "squad": [], "team": [None] * 11, "wins": 0, "money": INITIAL_MONEY,
            "last_daily": "2000-01-01T00:00:00", "player_stats": {},
            "team_name": f"Time de {display_name}",
            "team_tag": "TFC"
        }
    # Garante que usuários antigos tenham os novos campos
    if "team_name" not in user_data[user_id_str]:
        user_data[user_id_str]["team_name"] = f"Time de {display_name}"
    if "team_tag" not in user_data[user_id_str]:
        user_data[user_id_str]["team_tag"] = "TFC" # Team Football Club
    return user_data

def get_global_stats():
    return load_data(GLOBAL_STATS_FILE, default_data={"top_scorers": []})

def save_global_stats(data):
    save_data(GLOBAL_STATS_FILE, data)

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
    except Exception as e: print(f"Erro na API Gemini: {e}"); return fallback_text

async def generate_team_image(team_players, user_name, team_name, team_tag):
    try:
        background_url = "https://i.ibb.co/5W8Rvh2F/uaaaa.png"
        background_response = requests.get(background_url); background_response.raise_for_status()
        field_img = Image.open(BytesIO(background_response.content)).convert("RGBA")
    except Exception as e:
        print(f"Erro ao carregar imagem de fundo: {e}. Usando fallback."); field_img = Image.new("RGB", (700, 900), color=(8, 43, 27))

    draw = ImageDraw.Draw(field_img)
    width, height = field_img.size

    try:
        title_font = ImageFont.truetype("arialbd.ttf", 42)
        player_name_font = ImageFont.truetype("arialbd.ttf", 18)
        player_pos_font = ImageFont.truetype("arial.ttf", 16)
        player_stats_font = ImageFont.truetype("arialbd.ttf", 15)
        team_stats_font = ImageFont.truetype("arialbd.ttf", 24)
        coach_font = ImageFont.truetype("arial.ttf", 18)
    except IOError:
        title_font = player_name_font = player_pos_font = player_stats_font = team_stats_font = coach_font = ImageFont.load_default()

    title_text = f"[{team_tag}] {team_name}"
    draw.text((width/2, 38), title_text, font=title_font, fill=(0,0,0,120), anchor="mt", stroke_width=2)
    draw.text((width/2, 35), title_text, font=title_font, fill="#FFFFFF", anchor="mt")

    total_overall = 0; total_value = 0
    img_size = (120, 156)

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
                except Exception: player_img = Image.new('RGBA', img_size, color='grey')
            
            await asyncio.sleep(0.05)
            player_img.thumbnail(img_size, Image.Resampling.LANCZOS)
            paste_x = x - player_img.width // 2; paste_y = y - player_img.height // 2
            field_img.paste(player_img, (paste_x, paste_y), player_img)
            
            base_text_y = y + (img_size[1] // 2) + 5
            player_name_text = player['name'].split(' ')[-1]
            draw.text((x, base_text_y + 2), player_name_text, font=player_name_font, fill="black", anchor="mt", stroke_width=2)
            draw.text((x, base_text_y), player_name_text, font=player_name_font, fill="white", anchor="mt")

            player_pos_text = player['position']
            draw.text((x, base_text_y + 22), player_pos_text, font=player_pos_font, fill="black", anchor="mt", stroke_width=1)
            draw.text((x, base_text_y + 21), player_pos_text, font=player_pos_font, fill="#CCCCCC", anchor="mt")

            player_stats_text = f"OVR {player['overall']}"
            draw.text((x, base_text_y + 42), player_stats_text, font=player_stats_font, fill="black", anchor="mt", stroke_width=2)
            draw.text((x, base_text_y + 41), player_stats_text, font=player_stats_font, fill="yellow", anchor="mt")
        else:
            draw.rectangle((x - 40, y - 40, x + 40, y + 40), outline=(255,255,255,100), width=2)
            draw.text((x, y), "?", fill=(255,255,255,100), font=title_font, anchor="mm")

    stats_overall_text = f"⭐ Overall Total: {total_overall}"; stats_value_text = f"💰 Valor de Mercado: R$ {total_value:,}"
    coach_text = f"Técnico: {user_name}"
    
    draw.text((35, height - 78), stats_overall_text, font=team_stats_font, fill="black", anchor="ls", stroke_width=2)
    draw.text((35, height - 80), stats_overall_text, font=team_stats_font, fill="white", anchor="ls")
    draw.text((35, height - 48), stats_value_text, font=team_stats_font, fill="black", anchor="ls", stroke_width=2)
    draw.text((35, height - 50), stats_value_text, font=team_stats_font, fill="#39FF14", anchor="ls")
    draw.text((35, height - 18), coach_text, font=coach_font, fill="black", anchor="ls", stroke_width=1)
    draw.text((35, height - 20), coach_text, font=coach_font, fill="#FFFFFF", anchor="ls")

    img_byte_arr = BytesIO()
    field_img.save(img_byte_arr, format='PNG'); img_byte_arr.seek(0)
    return img_byte_arr

# --- VIEWS DE INTERAÇÃO ---
class ConfirmationView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60.0)
        self.value = None; self.author = author
    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return await interaction.response.send_message("Apenas o autor do comando pode confirmar.", ephemeral=True)
        self.value = True; self.stop()
    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return await interaction.response.send_message("Apenas o autor do comando pode cancelar.", ephemeral=True)
        self.value = False; self.stop()

class PaginatedEmbedView(discord.ui.View):
    def __init__(self, ctx, pages):
        super().__init__(timeout=120)
        self.ctx = ctx; self.pages = pages; self.current_page = 0; self.message = None
    async def start(self):
        self.update_buttons()
        self.message = await self.ctx.send(embed=self.pages[self.current_page], view=self)
    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1
    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return await interaction.response.send_message("Apenas quem executou o comando pode navegar.", ephemeral=True)
        self.current_page -= 1; self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    @discord.ui.button(label="Próximo ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return await interaction.response.send_message("Apenas quem executou o comando pode navegar.", ephemeral=True)
        self.current_page += 1; self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    async def on_timeout(self):
        if self.message:
            for item in self.children: item.disabled = True
            await self.message.edit(view=self)

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
            contracted = load_data(CONTRACTED_PLAYERS_FILE, []); contracted = [p for p in contracted if p != self.player['name']]
            save_data(USER_DATA_FILE, user_data); save_data(CONTRACTED_PLAYERS_FILE, contracted)
        await interaction.message.edit(content=f"💰 Você vendeu **{self.player['name']}** e ganhou **R$ {sale_price:,}**!", view=None)
    async def on_timeout(self):
        if not self.decision_made and self.message:
            try:
                sale_price = int(self.player['value'] * SALE_PERCENTAGE)
                async with data_lock:
                    user_data = await get_user_data(self.author.id)
                    user_data[str(self.author.id)]["money"] += sale_price
                    contracted = load_data(CONTRACTED_PLAYERS_FILE, [])
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
            contracted_check = load_data(CONTRACTED_PLAYERS_FILE, [])
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
    def __init__(self, ctx, results, action_callback, action_name, **kwargs):
        super().__init__(timeout=120)
        self.ctx = ctx; self.results = results; self.action_callback = action_callback
        self.action_name = action_name; self.current_index = 0; self.kwargs = kwargs
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
        await self.action_callback(self.ctx, player_to_act_on, **self.kwargs)
        for item in self.children: item.disabled = True
        try:
             await interaction.response.edit_message(view=self)
             await self.message.delete(delay=1)
        except discord.NotFound: pass

class TradeConfirmationView(discord.ui.View):
    def __init__(self, proposer, target, offered_player, requested_player):
        super().__init__(timeout=300)
        self.proposer = proposer; self.target = target; self.offered_player = offered_player
        self.requested_player = requested_player; self.decision = None
    @discord.ui.button(label="Aceitar Troca", style=discord.ButtonStyle.green, emoji="🤝")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target: return await interaction.response.send_message("Apenas o destinatário da proposta pode aceitar.", ephemeral=True)
        self.decision = True
        for item in self.children: item.disabled = True
        async with data_lock:
            all_data = load_data(USER_DATA_FILE, {})
            prop_id, targ_id = str(self.proposer.id), str(self.target.id)
            all_data[prop_id]['squad'] = [p for p in all_data[prop_id]['squad'] if p['name'] != self.offered_player['name']]
            all_data[prop_id]['squad'].append(self.requested_player)
            for i, p in enumerate(all_data[prop_id]['team']):
                if p and p['name'] == self.offered_player['name']: all_data[prop_id]['team'][i] = None
            all_data[targ_id]['squad'] = [p for p in all_data[targ_id]['squad'] if p['name'] != self.requested_player['name']]
            all_data[targ_id]['squad'].append(self.offered_player)
            for i, p in enumerate(all_data[targ_id]['team']):
                if p and p['name'] == self.requested_player['name']: all_data[targ_id]['team'][i] = None
            save_data(USER_DATA_FILE, all_data)
        await interaction.response.edit_message(content=f"✅ **Troca Aceita!** **{self.proposer.display_name}** e **{self.target.display_name}** trocaram seus jogadores.", embed=None, view=self)
        self.stop()
    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.red)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target and interaction.user != self.proposer: return await interaction.response.send_message("Você não pode cancelar esta proposta.", ephemeral=True)
        self.decision = False
        for item in self.children: item.disabled = True
        reason = "recusada" if interaction.user == self.target else "cancelada"
        await interaction.response.edit_message(content=f"❌ **Proposta de troca {reason}.**", embed=None, view=self)
        self.stop()
    async def on_timeout(self):
        if self.decision is None and self.message:
            for item in self.children: item.disabled = True
            await self.message.edit(content="⏰ **Tempo esgotado!** A proposta de troca expirou.", embed=None, view=self)

class RocketView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=90.0); self.author = author; self.decision = None
    @discord.ui.button(label="Retirar!", style=discord.ButtonStyle.green, emoji="💸")
    async def cash_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: await interaction.response.send_message("Não é a sua aposta!", ephemeral=True); return
        self.decision = "cashed_out"; button.disabled = True; await interaction.response.edit_message(view=self); self.stop()

# --- COMANDOS (em ordem lógica) ---

# Comandos de Recompensa e Personalização
@bot.command(name='daily')
@commands.cooldown(1, 5, commands.BucketType.user)
async def daily(ctx):
    user_id = str(ctx.author.id)
    async with data_lock:
        user_data = await get_user_data(user_id)
        last_daily_str = user_data[user_id].get("last_daily", "2000-01-01T00:00:00")
        last_daily_time = datetime.fromisoformat(last_daily_str)
        if datetime.utcnow() > last_daily_time + timedelta(hours=22):
            user_data[user_id]["money"] += DAILY_REWARD
            user_data[user_id]["last_daily"] = datetime.utcnow().isoformat()
            save_data(USER_DATA_FILE, user_data)
            await ctx.send(f"☀️ {ctx.author.mention}, você coletou sua recompensa diária de **R$ {DAILY_REWARD:,}**!")
        else:
            remaining = (last_daily_time + timedelta(hours=22)) - datetime.utcnow()
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            await ctx.send(f"⏳ Você já coletou sua recompensa hoje. Tente novamente em aproximadamente **{hours}h e {minutes}m**.")

# Comandos de Ranking e Competição
@bot.command(name='ranking')
async def ranking(ctx):
    user_data = load_data(USER_DATA_FILE, {})
    if not user_data: return await ctx.send("Ainda não há dados.")
    sorted_users = sorted([(uid, data.get('wins', 0)) for uid, data in user_data.items() if data.get('wins', 0) > 0], key=lambda i: i[1], reverse=True)
    if not sorted_users: return await ctx.send("🏆 **Ranking de Vitórias Vazio!** Ninguém venceu ainda.")
    embed = discord.Embed(title="🏆 Ranking de Vitórias - Top 10 🏆", color=discord.Color.purple())
    desc = []; medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, wins) in enumerate(sorted_users[:10]):
        try: user = await bot.fetch_user(int(user_id)); user_name = user.display_name
        except (discord.NotFound, ValueError): user_name = f"Usuário Desconhecido ({user_id})"
        medal = medals[i] if i < 3 else "🔹"; desc.append(f"{medal} **{user_name}** - `{wins}` vitórias")
    embed.description = "\n".join(desc); await ctx.send(embed=embed)

@bot.command(name='rankingovr')
async def ranking_overall(ctx):
    user_data = load_data(USER_DATA_FILE, {});
    if not user_data: return await ctx.send("Ainda não há dados para gerar um ranking.")
    user_overalls = []
    for uid, data in user_data.items():
        team = data.get('team', [None] * 11)
        if any(p for p in team): overall = sum(p['overall'] for p in team if p); user_overalls.append((uid, overall))
    if not user_overalls: return await ctx.send("⭐ **Ranking de Overall Vazio!** Ninguém montou um time ainda.")
    sorted_users = sorted(user_overalls, key=lambda i: i[1], reverse=True)
    embed = discord.Embed(title="⭐ Ranking de Overall do Time - Top 10 ⭐", color=discord.Color.gold())
    desc = []; medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, overall) in enumerate(sorted_users[:10]):
        try: user = await bot.fetch_user(int(user_id)); user_name = user.display_name
        except (discord.NotFound, ValueError): user_name = f"Usuário Desconhecido ({user_id})"
        medal = medals[i] if i < 3 else "🔹"; desc.append(f"{medal} **{user_name}** - Overall: `{overall}`")
    embed.description = "\n".join(desc); await ctx.send(embed=embed)

@bot.command(name='artilheiros')
async def artilheiros(ctx):
    global_stats = get_global_stats()
    top_scorers = global_stats.get("top_scorers", [])
    if not top_scorers: return await ctx.send("⚽ **Ninguém marcou gols ainda!** As redes estão virgens.")
    sorted_scorers = sorted(top_scorers, key=lambda x: x['goals'], reverse=True)
    embed = discord.Embed(title="🏆 Artilharia do Servidor 🏆", color=discord.Color.red())
    desc = []; medals = ["🥇", "🥈", "🥉"]
    for i, scorer in enumerate(sorted_scorers[:10]):
        medal = medals[i] if i < 3 else "⚽"
        desc.append(f"{medal} **{scorer['name']}** ({scorer['owner_name']}) - `{scorer['goals']}` gols")
    embed.description = "\n".join(desc)
    await ctx.send(embed=embed)

# Comandos de Economia e Mercado
@bot.command(name='saldo')
async def balance(ctx):
    user_data = await get_user_data(ctx.author.id); money = user_data[str(ctx.author.id)]['money']
    await ctx.send(f"💰 {ctx.author.mention}, seu saldo é de **R$ {money:,}**.")

@bot.command(name='mercado')
async def market(ctx, pos: str = None, sort_by: str = 'valor'):
    contracted = load_data(CONTRACTED_PLAYERS_FILE, [])
    available_players = [p for p in ALL_PLAYERS if p["name"] not in contracted]
    if not available_players: return await ctx.send("🤯 **Mercado Vazio!** Todos os jogadores foram contratados.")
    if pos:
        results = [p for p in available_players if pos.upper() in p['position'].split('/')]
        if not results: return await ctx.send(f"😥 Nenhum jogador disponível encontrado para a posição: `{pos.upper()}`")
    else: results = available_players
    valid_sorts = ['valor', 'overall', 'nome']; sort_by = sort_by.lower()
    if sort_by not in valid_sorts: return await ctx.send(f"Opção de ordenação inválida. Use: `{'`, `'.join(valid_sorts)}`.")
    reverse_sort = True if sort_by != 'nome' else False
    sort_key = 'value' if sort_by == 'valor' else sort_by
    results.sort(key=lambda p: p[sort_key], reverse=reverse_sort)
    pages = []
    chunk_size = 10
    for i in range(0, len(results), chunk_size):
        chunk = results[i:i + chunk_size]
        embed = discord.Embed(title=f"🛒 Mercado (Pág. {len(pages) + 1})", description=f"Filtrando por: `{pos.upper() if pos else 'Todos'}` | Ordenado por: `{sort_by.capitalize()}`", color=discord.Color.dark_teal())
        for p in chunk: embed.add_field(name=f"{p['name']} ({p['position']})", value=f"**OVR:** {p['overall']} | **Preço:** R$ {p['value']:,}", inline=False)
        embed.set_footer(text=f"Total de {len(results)} jogadores encontrados.")
        pages.append(embed)
    if not pages: return await ctx.send("Nenhum resultado encontrado com esses filtros.")
    view = PaginatedEmbedView(ctx, pages); await view.start()

@bot.command(name='destaques')
async def destaques(ctx):
    contracted = load_data(CONTRACTED_PLAYERS_FILE, [])
    available_players = [p for p in ALL_PLAYERS if p["name"] not in contracted]
    if not available_players: return await ctx.send("🤯 **Mercado Vazio!**")
    top_5_available = sorted(available_players, key=lambda p: p['overall'], reverse=True)[:5]
    embed = discord.Embed(title="🔥 Destaques do Mercado (Top 5 Livres) 🔥", color=discord.Color.orange())
    for player in top_5_available: embed.add_field(name=f"💎 {player['name']} (OVR: {player['overall']})", value=f"**Pos:** {player['position']} | **Preço:** R$ {player['value']:,}", inline=False)
    embed.set_footer(text=f"Use {BOT_PREFIX}contratar <nome> para fazer uma proposta!")
    await ctx.send(embed=embed)

@bot.command(name='valorizacao')
async def valorizacao(ctx):
    top_10_valuable = sorted(ALL_PLAYERS, key=lambda p: p['value'], reverse=True)[:10]
    embed = discord.Embed(title="💎 Top 10 Jogadores Mais Valiosos 💎", color=discord.Color.from_rgb(255, 215, 0))
    desc = []; medals = ["🥇", "🥈", "🥉"]
    for i, player in enumerate(top_10_valuable):
        medal = medals[i] if i < 3 else "🔹"
        desc.append(f"{medal} **{player['name']}** - `R$ {player['value']:,}`")
    embed.description = "\n".join(desc)
    await ctx.send(embed=embed)

@bot.command(name='doar')
async def doar(ctx, target: discord.Member, amount: int):
    proposer = ctx.author
    if proposer == target: return await ctx.send("Você não pode doar para si mesmo.")
    if target.bot: return await ctx.send("Não doe dinheiro para bots.")
    if amount <= 0: return await ctx.send("A quantia deve ser positiva.")
    async with data_lock:
        all_data = await get_user_data(proposer.id)
        if all_data[str(proposer.id)]['money'] < amount: return await ctx.send(f"💸 Você não tem **R$ {amount:,}** para doar.")
        all_data.update(await get_user_data(target.id))
        all_data[str(proposer.id)]['money'] -= amount
        all_data[str(target.id)]['money'] += amount
        save_data(USER_DATA_FILE, all_data)
    await ctx.send(f"🎁 {proposer.mention} doou **R$ {amount:,}** para {target.mention}!")

# Comandos de Gestão e Informação
@bot.command(name='obter')
@commands.cooldown(1, 300, commands.BucketType.user)
async def get_player(ctx):
    async with data_lock:
        contracted = load_data(CONTRACTED_PLAYERS_FILE, [])
        available = [p for p in ALL_PLAYERS if p["name"] not in contracted]
        if not available: return await ctx.send("🤯 **Mercado Vazio!**")
        player = random.choice(available); contracted.append(player["name"]); save_data(CONTRACTED_PLAYERS_FILE, contracted)
    sale_price = int(player['value'] * SALE_PERCENTAGE)
    embed = discord.Embed(title="🃏 Você tirou uma carta!", color=discord.Color.blue()); embed.set_image(url=player["image"])
    embed.add_field(name=player['name'], value=f"**Overall:** {player['overall']} | **Posição:** {player['position']}")
    embed.add_field(name="Valor de Venda Rápida", value=f"R$ {sale_price:,}")
    view = KeepOrSellView(ctx.author, player); message = await ctx.send(embed=embed, view=view); view.message = message

@bot.command(name='buscar')
async def buscar(ctx, *, query: str):
    search_query = normalize_str(query)
    results = [p for p in ALL_PLAYERS if search_query in normalize_str(p['name'])]
    if not results: return await ctx.send(f"🔎 Nenhum jogador encontrado no universo com o nome: `{query}`")
    results = results[:5]
    embed = discord.Embed(title=f"🔎 Resultados da Busca Global por '{query}'", color=discord.Color.dark_magenta())
    for player in results: embed.add_field(name=f"{player['name']} (OVR: {player['overall']})", value=f"**Pos:** {player['position']} | **Valor:** R$ {player['value']:,}", inline=False)
    await ctx.send(embed=embed)

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

@bot.command(name='elenco')
async def squad_command(ctx):
    user_data = await get_user_data(ctx.author.id); squad_players = user_data[str(ctx.author.id)]["squad"]
    if not squad_players: return await ctx.send(f"텅 **Elenco Vazio!**")
    embed = discord.Embed(title=f"🎽 Elenco de {ctx.author.display_name} 🎽", color=ctx.author.color)
    embed.description = "\n".join([f"**{p['name']}** | `{p['position']}` | Overall: **{p['overall']}**" for p in sorted(squad_players, key=lambda p: p['name'])])
    await ctx.send(embed=embed)

@bot.command(name='limparelenco')
async def limparelenco(ctx):
    async with data_lock:
        all_data = await get_user_data(ctx.author.id)
        user_id = str(ctx.author.id)
        squad = all_data[user_id].get('squad', [])
        team_player_names = {p['name'] for p in all_data[user_id].get('team', []) if p}
        benched_players = [p for p in squad if p['name'] not in team_player_names]
        if not benched_players: return await ctx.send("Você não tem jogadores no banco para vender.")
        total_value = sum(int(p['value'] * SALE_PERCENTAGE) for p in benched_players)
        view = ConfirmationView(ctx.author)
        msg = await ctx.send(f"Você tem certeza que quer vender **{len(benched_players)}** jogadores do banco por um total de **R$ {total_value:,}**? Esta ação não pode ser desfeita.", view=view)
        await view.wait()
        if view.value is True:
            all_data[user_id]['money'] += total_value
            all_data[user_id]['squad'] = [p for p in squad if p['name'] in team_player_names]
            contracted = load_data(CONTRACTED_PLAYERS_FILE, [])
            benched_player_names = {p['name'] for p in benched_players}
            new_contracted = [name for name in contracted if name not in benched_player_names]
            save_data(USER_DATA_FILE, all_data)
            save_data(CONTRACTED_PLAYERS_FILE, new_contracted)
            await msg.edit(content=f"💰 Jogadores vendidos! Você ganhou **R$ {total_value:,}**.", view=None)
        else: await msg.edit(content="Ação cancelada.", view=None)

# Comandos de Partida
async def perform_escalar(ctx, player, **kwargs):
    async with data_lock:
        all_data = await get_user_data(ctx.author.id); user_id = str(ctx.author.id)
        team = all_data[user_id]['team']
        if any(p and p['name'] == player['name'] for p in team): return await ctx.send(f"**{player['name']}** já está escalado.")
        positions = player['position'].split('/'); empty_slot = -1; chosen_pos = ""
        for pos in positions:
            if pos in SLOT_MAPPING:
                valid_slots = SLOT_MAPPING[pos]
                slot_found = next((i for i in valid_slots if team[i] is None), -1)
                if slot_found != -1: empty_slot = slot_found; chosen_pos = pos; break
        if empty_slot != -1:
            team[empty_slot] = player; save_data(USER_DATA_FILE, all_data)
            await ctx.send(f"✅ **{player['name']}** foi escalado como **{chosen_pos}**!")
        else: await ctx.send(f"🚫 **Posição Cheia!** Vagas de **{player['position']}** ocupadas.")

@bot.command(name='escalar')
async def set_player(ctx, *, query: str):
    search_query = normalize_str(query); user_data = await get_user_data(ctx.author.id)
    squad = user_data[str(ctx.author.id)]['squad']
    results = [p for p in squad if search_query in normalize_str(p['name'])]
    if not results: return await ctx.send(f"Nenhum jogador encontrado no seu elenco com o nome: `{query}`")
    if len(results) == 1: await perform_escalar(ctx, results[0])
    else: view = ActionView(ctx, results, perform_escalar, "Escalar"); embed = await view.create_embed(); view.message = await ctx.send(embed=embed, view=view)

@bot.command(name='timealeatorio')
async def timealeatorio(ctx):
    async with data_lock:
        all_data = await get_user_data(ctx.author.id)
        user_id = str(ctx.author.id)
        squad = all_data[user_id].get('squad', [])
        team = all_data[user_id].get('team', [None] * 11)
        team_player_names = {p['name'] for p in team if p}
        available_squad = [p for p in squad if p['name'] not in team_player_names]
        if not available_squad: return await ctx.send("Não há jogadores disponíveis no seu elenco para escalar.")
        filled_count = 0
        for i, slot in enumerate(team):
            if slot is None:
                pos_needed = [key for key, val in SLOT_MAPPING.items() if i in val][0]
                candidates = [p for p in available_squad if pos_needed in p['position'].split('/')]
                if candidates:
                    chosen_player = random.choice(candidates)
                    team[i] = chosen_player
                    available_squad.remove(chosen_player)
                    filled_count += 1
        if filled_count > 0:
            all_data[user_id]['team'] = team
            save_data(USER_DATA_FILE, all_data)
            await ctx.send(f"🎲 Time preenchido! **{filled_count}** jogadores foram escalados aleatoriamente.")
        else: await ctx.send("Não foi possível encontrar jogadores no seu elenco para as posições vagas.")

# ... (outros comandos como `banco`, `vender`, etc. estão aqui) ...
async def perform_banco(ctx, player, **kwargs):
    async with data_lock:
        all_data = await get_user_data(ctx.author.id); user_id = str(ctx.author.id)
        team = all_data[user_id]['team']
        idx = next((i for i, p in enumerate(team) if p and p['name'] == player['name']), -1)
        if idx == -1: return
        player_name_unset = team[idx]['name']; team[idx] = None; save_data(USER_DATA_FILE, all_data)
        await ctx.send(f"❌ **{player_name_unset}** foi para o banco de reservas.")

@bot.command(name='banco')
async def unset_player(ctx, *, query: str):
    search_query = normalize_str(query); user_data = await get_user_data(ctx.author.id)
    team = user_data[str(ctx.author.id)]['team']
    results = [p for p in team if p and search_query in normalize_str(p['name'])]
    if not results: return await ctx.send(f"Nenhum jogador encontrado no seu time titular com o nome: `{query}`")
    if len(results) == 1: await perform_banco(ctx, results[0])
    else: view = ActionView(ctx, results, perform_banco, "Mandar para o Banco"); embed = await view.create_embed(); view.message = await ctx.send(embed=embed, view=view)

async def perform_vender(ctx, player, **kwargs):
    async with data_lock:
        user_data = await get_user_data(ctx.author.id); user_id = str(ctx.author.id)
        team = user_data[user_id]['team']
        for i, p_team in enumerate(team):
            if p_team and p_team['name'] == player['name']: team[i] = None; break
        sale_price = int(player['value'] * SALE_PERCENTAGE)
        user_data[user_id]['money'] += sale_price
        user_data[user_id]['squad'] = [p for p in user_data[user_id]['squad'] if p['name'] != player['name']]
        contracted = load_data(CONTRACTED_PLAYERS_FILE, []); contracted = [p_name for p_name in contracted if p_name != player['name']]
        save_data(USER_DATA_FILE, user_data); save_data(CONTRACTED_PLAYERS_FILE, contracted)
    await ctx.send(f"💰 Você vendeu **{player['name']}** por **R$ {sale_price:,}**!")

@bot.command(name='vender')
async def sell_player(ctx, *, query: str):
    search_query = normalize_str(query); user_data = await get_user_data(ctx.author.id)
    squad = user_data[str(ctx.author.id)]['squad']
    results = [p for p in squad if search_query in normalize_str(p['name'])]
    if not results: return await ctx.send(f"Nenhum jogador encontrado no seu elenco com o nome: `{query}`")
    if len(results) == 1: await perform_vender(ctx, results[0])
    else: view = ActionView(ctx, results, perform_vender, "Vender"); embed = await view.create_embed(); view.message = await ctx.send(embed=embed, view=view)

# ... (outros comandos de aposta, admin, etc.) ...
@bot.command(name='tigrinho')
async def tigrinho_game(ctx, bet: int):
    user_id = str(ctx.author.id)
    async with data_lock:
        user_data = await get_user_data(user_id); user_money = user_data[user_id]['money']
        if bet <= 0: return await ctx.send("A aposta deve ser um valor positivo, né?")
        if user_money < bet: return await ctx.send(f"💸 Você não tem dinheiro suficiente! Seu saldo é de R$ {user_money:,}.")
        user_data[user_id]['money'] -= bet; save_data(USER_DATA_FILE, user_data)
    emojis = ["🍒", "🍋", "🍊", "🍉", "⭐", "💎", "🐯"]; msg = await ctx.send(f"Você apostou R$ {bet:,}. Girando o tigrinho...\n\n| 🎰 | 🎰 | 🎰 |")
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
    final_balance = user_data[str(ctx.author.id)]['money']; embed.set_footer(text=f"Seu novo saldo é de R$ {final_balance:,}")
    await msg.edit(content="", embed=embed)

@bot.command(name='rocket')
async def rocket_game(ctx, bet: int):
    user_id = str(ctx.author.id)
    async with data_lock:
        user_data = await get_user_data(user_id); user_money = user_data[user_id]['money']
        if bet <= 0: return await ctx.send("A aposta deve ser um valor positivo.")
        if user_money < bet: return await ctx.send(f"💸 Você não tem dinheiro suficiente! Seu saldo é de R$ {user_money:,}.")
        user_data[user_id]['money'] -= bet; save_data(USER_DATA_FILE, user_data)
    view = RocketView(ctx.author); embed = discord.Embed(title="🚀 Jogo do Foguete 🚀", color=discord.Color.purple())
    embed.description = f"Apostou: **R$ {bet:,}**\nMultiplicador atual: **1.00x**"; embed.set_footer(text="Clique em 'Retirar!' antes que exploda!")
    message = await ctx.send(embed=embed, view=view)
    multiplier = 1.0; crash_point = random.uniform(1.1, 15.0)
    while multiplier < crash_point:
        await asyncio.sleep(1.5); increment = 0.10 + (multiplier * 0.05); multiplier += increment
        embed.description = f"Apostou: **R$ {bet:,}**\nMultiplicador atual: **{multiplier:.2f}x**"; await message.edit(embed=embed)
        if view.decision == "cashed_out":
            winnings = int(bet * multiplier)
            async with data_lock:
                user_data = await get_user_data(user_id)
                user_data[user_id]['money'] += winnings; save_data(USER_DATA_FILE, user_data)
            embed.title = "🎉 Você Ganhou! 🎉"; embed.description = f"Você retirou em **{multiplier:.2f}x** e ganhou **R$ {winnings:,}**!"
            embed.color = discord.Color.green(); await message.edit(embed=embed, view=None); return
    embed.title = "💥 EXPLODIU! 💥"; embed.description = f"O foguete explodiu em **{multiplier:.2f}x**. Você perdeu sua aposta de **R$ {bet:,}**."
    embed.color = discord.Color.red(); await message.edit(embed=embed, view=None)

# --- Comandos de Admin ---
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
            if os.path.exists(USER_DATA_FILE): os.remove(USER_DATA_FILE); files_deleted.append(os.path.basename(USER_DATA_FILE))
            if os.path.exists(CONTRACTED_PLAYERS_FILE): os.remove(CONTRACTED_PLAYERS_FILE); files_deleted.append(os.path.basename(CONTRACTED_PLAYERS_FILE))
            if os.path.exists(GLOBAL_STATS_FILE): os.remove(GLOBAL_STATS_FILE); files_deleted.append(os.path.basename(GLOBAL_STATS_FILE))
        except Exception as e: return await msg.edit(content=f"❌ Erro ao apagar arquivos: {e}")
    await msg.edit(content=f"🗑️ Arquivos `{', '.join(files_deleted)}` foram apagados.\n\n✅ **RESET TOTAL CONCLUÍDO.**\nÉ altamente recomendável que você **reinicie o bot agora**.")

@bot.command(name='bestteam')
@commands.has_permissions(administrator=True)
async def best_team(ctx, user: discord.Member):
    if user.bot: return await ctx.send("Bots não podem ter times.")
    await ctx.send(f"🤖 Montando o time dos sonhos para {user.mention}... Isso pode levar um momento.")
    async with data_lock:
        all_user_data = await get_user_data(user.id)
        contracted_players = load_data(CONTRACTED_PLAYERS_FILE, [])
        target_user_id = str(user.id)
        current_squad_names = {p['name'] for p in all_user_data[target_user_id].get("squad", [])}
        contracted_players = [p_name for p_name in contracted_players if p_name not in current_squad_names]
        all_user_data[target_user_id]['squad'] = []
        all_user_data[target_user_id]['team'] = [None] * 11
        new_team = [None] * 11
        formation_slots = {0: "GOL", 1: "ZAG", 2: "ZAG", 3: "LE", 4: "LD", 5: "VOL", 6: "MC", 7: "MEI", 8: "PE", 9: "PD", 10: "CA"}
        used_player_names_for_team = set()
        for slot_index, position in formation_slots.items():
            candidates = [p for p in ALL_PLAYERS if p['position'] == position and p['name'] not in contracted_players and p['name'] not in used_player_names_for_team]
            candidates.sort(key=lambda p: p['overall'], reverse=True)
            if candidates:
                best_player = candidates[0]; new_team[slot_index] = best_player
                contracted_players.append(best_player['name']); used_player_names_for_team.add(best_player['name'])
        all_user_data[target_user_id]['team'] = new_team
        all_user_data[target_user_id]['squad'] = [p for p in new_team if p]
        save_data(USER_DATA_FILE, all_user_data)
        save_data(CONTRACTED_PLAYERS_FILE, contracted_players)
    await ctx.send(f"✅ Time dos sonhos montado para {user.mention}! Use `{BOT_PREFIX}meutime` para ver o resultado.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return # Ignora silenciosamente comandos que não existem
    # Adicione outros tratamentos de erro aqui se desejar
    print(f"Ocorreu um erro no comando {ctx.command}: {error}")


# --- EXECUÇÃO DO BOT ---
if __name__ == "__main__":
    TOKEN = os.environ.get('DISCORD_TOKEN')
    keep_alive() 
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERRO: Token do Discord não encontrado nas variáveis de ambiente.")
