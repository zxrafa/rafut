# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------
# RafutBot - Versão Definitiva com Visual Moderno
# ----------------------------------------------------------------------
# Esta versão inclui todas as funcionalidades, novo prefixo e
# melhorias visuais nos comandos (imagem retangular).
# NOVOS COMANDOS: mercado, rankingovr, trocar
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

# --- FUNÇÃO MEUTIME ATUALIZADA ---
async def generate_team_image(team_players, user_name):
    """Gera a imagem do time com o novo fundo, cartas maiores e posição visível."""
    try:
        background_url = "https://i.ibb.co/wh0Fdcjx/mermao.png"
        background_response = requests.get(background_url)
        background_response.raise_for_status()
        field_img = Image.open(BytesIO(background_response.content)).convert("RGBA")
    except Exception as e:
        print(f"Erro ao carregar imagem de fundo: {e}. Usando fallback.")
        field_img = Image.new("RGB", (700, 900), color=(8, 43, 27))

    draw = ImageDraw.Draw(field_img)
    width, height = field_img.size

    try:
        title_font = ImageFont.truetype("arialbd.ttf", 42)
        player_name_font = ImageFont.truetype("arialbd.ttf", 18)
        player_pos_font = ImageFont.truetype("arial.ttf", 16) # Fonte para a posição
        player_stats_font = ImageFont.truetype("arialbd.ttf", 15)
        team_stats_font = ImageFont.truetype("arialbd.ttf", 24)
    except IOError:
        title_font = player_name_font = player_pos_font = player_stats_font = team_stats_font = ImageFont.load_default()

    title_text = f"Time de {user_name}"
    draw.text((width/2, 38), title_text, font=title_font, fill=(0,0,0,120), anchor="mt", stroke_width=2)
    draw.text((width/2, 35), title_text, font=title_font, fill="#FFFFFF", anchor="mt")

    total_overall = 0; total_value = 0
    img_size = (120, 156) # --- TAMANHO DA CARTA AUMENTADO ---

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
            
            paste_x = x - player_img.width // 2
            paste_y = y - player_img.height // 2
            field_img.paste(player_img, (paste_x, paste_y), player_img)
            
            # --- POSICIONAMENTO DO TEXTO AJUSTADO ---
            base_text_y = y + (img_size[1] // 2) + 5 # Posição inicial do texto abaixo da carta

            # NOME DO JOGADOR
            player_name_text = player['name'].split(' ')[-1] # Pega o último nome
            draw.text((x, base_text_y + 2), player_name_text, font=player_name_font, fill="black", anchor="mt", stroke_width=2)
            draw.text((x, base_text_y), player_name_text, font=player_name_font, fill="white", anchor="mt")

            # POSIÇÃO DO JOGADOR (NOVO)
            player_pos_text = player['position']
            draw.text((x, base_text_y + 22), player_pos_text, font=player_pos_font, fill="black", anchor="mt", stroke_width=1)
            draw.text((x, base_text_y + 21), player_pos_text, font=player_pos_font, fill="#CCCCCC", anchor="mt")

            # STATS (OVERALL)
            player_stats_text = f"OVR {player['overall']}"
            draw.text((x, base_text_y + 42), player_stats_text, font=player_stats_font, fill="black", anchor="mt", stroke_width=2)
            draw.text((x, base_text_y + 41), player_stats_text, font=player_stats_font, fill="yellow", anchor="mt")

        else:
            draw.rectangle((x - 40, y - 40, x + 40, y + 40), outline=(255,255,255,100), width=2)
            draw.text((x, y), "?", fill=(255,255,255,100), font=title_font, anchor="mm")

    stats_overall_text = f"⭐ Overall Total: {total_overall}"
    stats_value_text = f"💰 Valor de Mercado: R$ {total_value:,}"
    draw.text((35, height - 48), stats_overall_text, font=team_stats_font, fill="black", anchor="ls", stroke_width=2)
    draw.text((35, height - 50), stats_overall_text, font=team_stats_font, fill="white", anchor="ls")
    draw.text((35, height - 18), stats_value_text, font=team_stats_font, fill="black", anchor="ls", stroke_width=2)
    draw.text((35, height - 20), stats_value_text, font=team_stats_font, fill="#39FF14", anchor="ls")
    
    img_byte_arr = BytesIO()
    field_img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

# --- VIEWS DE INTERAÇÃO (EXISTENTES E NOVAS) ---

class PaginatedEmbedView(discord.ui.View):
    """View para navegar em embeds paginados (usado em --mercado)."""
    def __init__(self, ctx, pages):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.pages = pages
        self.current_page = 0
        self.message = None

    async def start(self):
        self.update_buttons()
        self.message = await self.ctx.send(embed=self.pages[self.current_page], view=self)

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1

    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Apenas quem executou o comando pode navegar.", ephemeral=True)
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="Próximo ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Apenas quem executou o comando pode navegar.", ephemeral=True)
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
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
    def __init__(self, ctx, results, action_callback, action_name, **kwargs):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.results = results
        self.action_callback = action_callback
        self.action_name = action_name
        self.current_index = 0
        self.kwargs = kwargs
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
        
        # Passa os kwargs para o callback
        await self.action_callback(self.ctx, player_to_act_on, **self.kwargs)
        
        for item in self.children: item.disabled = True
        try:
             await interaction.response.edit_message(view=self)
             await self.message.delete(delay=1)
        except discord.NotFound:
            pass

class TradeConfirmationView(discord.ui.View):
    def __init__(self, proposer, target, offered_player, requested_player):
        super().__init__(timeout=300)
        self.proposer = proposer
        self.target = target
        self.offered_player = offered_player
        self.requested_player = requested_player
        self.decision = None

    @discord.ui.button(label="Aceitar Troca", style=discord.ButtonStyle.green, emoji="🤝")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target:
            return await interaction.response.send_message("Apenas o destinatário da proposta pode aceitar.", ephemeral=True)
        
        self.decision = True
        for item in self.children:
            item.disabled = True

        async with data_lock:
            all_data = load_data(USER_DATA_FILE)
            prop_id, targ_id = str(self.proposer.id), str(self.target.id)

            # Remover jogador oferecido do Proposer e adicionar o requisitado
            all_data[prop_id]['squad'] = [p for p in all_data[prop_id]['squad'] if p['name'] != self.offered_player['name']]
            all_data[prop_id]['squad'].append(self.requested_player)
            # Atualizar time titular se necessário
            for i, p in enumerate(all_data[prop_id]['team']):
                if p and p['name'] == self.offered_player['name']:
                    all_data[prop_id]['team'][i] = None # Ou pode tentar encaixar o novo jogador
            
            # Remover jogador requisitado do Target e adicionar o oferecido
            all_data[targ_id]['squad'] = [p for p in all_data[targ_id]['squad'] if p['name'] != self.requested_player['name']]
            all_data[targ_id]['squad'].append(self.offered_player)
            # Atualizar time titular se necessário
            for i, p in enumerate(all_data[targ_id]['team']):
                if p and p['name'] == self.requested_player['name']:
                    all_data[targ_id]['team'][i] = None

            save_data(USER_DATA_FILE, all_data)
        
        await interaction.response.edit_message(content=f"✅ **Troca Aceita!** **{self.proposer.display_name}** e **{self.target.display_name}** trocaram seus jogadores.", embed=None, view=self)
        self.stop()

    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.red)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target and interaction.user != self.proposer:
            return await interaction.response.send_message("Você não pode cancelar esta proposta.", ephemeral=True)
        
        self.decision = False
        for item in self.children:
            item.disabled = True
        
        reason = "recusada" if interaction.user == self.target else "cancelada"
        await interaction.response.edit_message(content=f"❌ **Proposta de troca {reason}.**", embed=None, view=self)
        self.stop()
    
    async def on_timeout(self):
        if self.decision is None:
            for item in self.children:
                item.disabled = True
            await self.message.edit(content="⏰ **Tempo esgotado!** A proposta de troca expirou.", embed=None, view=self)

# --- EVENTOS E COMANDOS ---
@bot.event
async def on_ready():
    print(f'🚀 {bot.user.name} V16 (Novos Comandos) está no ar!'); fetch_and_parse_players()
    await bot.change_presence(activity=discord.Game(name=f"Use {BOT_PREFIX}help"))

# --- COMANDO HELP ATUALIZADO ---
@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(title="📜 Comandos do RafutBot 16.0 📜", color=discord.Color.gold())
    embed.add_field(name="**Diversão e Utilidades**", value="-"*25, inline=False)
    embed.add_field(name=f"📰 `{BOT_PREFIX}noticias`", value="Gera uma manchete de notícia (com IA!) sobre um jogador seu.", inline=False)
    embed.add_field(name=f"ℹ️ `{BOT_PREFIX}info <jogador>`", value="Mostra a ficha técnica de um jogador seu.", inline=False)
    embed.add_field(name=f"🆚 `{BOT_PREFIX}comparar <j1>, <j2>`", value="Compara dois jogadores do seu elenco.", inline=False)
    embed.add_field(name=f"🏆 `{BOT_PREFIX}ranking`", value="Exibe o ranking de vitórias.", inline=False)
    embed.add_field(name=f"⭐ `{BOT_PREFIX}rankingovr`", value="Exibe o ranking de overall do time titular.", inline=False)
    
    embed.add_field(name="**Economia e Mercado**", value="-"*25, inline=False)
    embed.add_field(name=f"💰 `{BOT_PREFIX}saldo`", value="Mostra seu dinheiro.", inline=False)
    embed.add_field(name=f"💸 `{BOT_PREFIX}contratar <nome>`", value="Busca e contrata jogadores.", inline=False)
    embed.add_field(name=f"🛒 `{BOT_PREFIX}mercado [pos] [ordem]`", value="Busca avançada no mercado. Ordem: valor, overall, nome.", inline=False)
    embed.add_field(name=f"🤝 `{BOT_PREFIX}vender <nome>`", value="Vende um jogador do seu elenco.", inline=False)
    embed.add_field(name=f"🔄 `{BOT_PREFIX}trocar @usuario`", value="Inicia uma troca de jogadores com outro usuário.", inline=False)

    embed.add_field(name="**Gestão e Partidas**", value="-"*25, inline=False)
    embed.add_field(name=f"🃏 `{BOT_PREFIX}obter`", value="Ganha um jogador aleatório (a cada 5 min).", inline=False)
    embed.add_field(name=f"✅ `{BOT_PREFIX}escalar <nome>`", value="Escala um jogador (busca parcial).", inline=False)
    embed.add_field(name=f"❌ `{BOT_PREFIX}banco <nome>`", value="Move um jogador para o banco (busca parcial).", inline=False)
    embed.add_field(name=f"🖼️ `{BOT_PREFIX}meutime`", value="Gera uma imagem tática do seu time.", inline=False)
    embed.add_field(name=f"⚔️ `{BOT_PREFIX}confrontar @usuario`", value="Inicia uma partida narrada por IA!", inline=False)
    
    embed.add_field(name="**🎲 Jogos de Aposta 🎲**", value="-"*25, inline=False)
    embed.add_field(name=f"🐯 `{BOT_PREFIX}tigrinho <quantia>`", value="Aposte sua grana no jogo do tigrinho!", inline=False)
    embed.add_field(name=f"🚀 `{BOT_PREFIX}rocket <quantia>`", value="Aposte e retire antes que o foguete exploda!", inline=False)

    if ctx.author.guild_permissions.administrator:
        embed.add_field(name="👑 Comandos de Administrador 👑", value="-" * 25, inline=False)
        embed.add_field(name=f"⭐ `{BOT_PREFIX}bestteam @usuario`", value="Monta o melhor time possível para um usuário.", inline=False)
        embed.add_field(name=f"💰 `{BOT_PREFIX}money @usuario <quantia>`", value="Dá ou remove dinheiro de um usuário.", inline=False)
        embed.add_field(name=f"🚨 `{BOT_PREFIX}fullreset`", value="Apaga TODOS os dados salvos do bot.", inline=False)
    await ctx.send(embed=embed)


# --- COMANDOS EXISTENTES (sem alterações, omitidos para brevidade) ---
# ... (noticias, info, comparar, contratar, obter, saldo, etc...)
# Mantive apenas os comandos novos e os que precisaram de alteração para a lógica de troca.

@bot.command(name='ranking')
async def ranking(ctx):
    user_data = load_data(USER_DATA_FILE)
    if not user_data: return await ctx.send("Ainda não há dados.")
    
    # Filtra usuários que têm a chave 'wins' e o valor é maior que 0
    sorted_users = sorted(
        [(uid, data.get('wins', 0)) for uid, data in user_data.items() if data.get('wins', 0) > 0],
        key=lambda i: i[1],
        reverse=True
    )

    if not sorted_users: return await ctx.send("🏆 **Ranking de Vitórias Vazio!** Ninguém venceu ainda.")
    
    embed = discord.Embed(title="🏆 Ranking de Vitórias - Top 10 🏆", color=discord.Color.purple())
    desc = []
    medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, wins) in enumerate(sorted_users[:10]):
        try:
            user = await bot.fetch_user(int(user_id))
            user_name = user.display_name
        except (discord.NotFound, ValueError):
            user_name = f"Usuário Desconhecido ({user_id})"
        medal = medals[i] if i < 3 else "🔹"
        desc.append(f"{medal} **{user_name}** - `{wins}` vitórias")
    
    embed.description = "\n".join(desc)
    await ctx.send(embed=embed)


# --- NOVOS COMANDOS ÚTEIS ---

@bot.command(name='rankingovr')
async def ranking_overall(ctx):
    """Exibe o ranking de overall do time titular."""
    user_data = load_data(USER_DATA_FILE)
    if not user_data:
        return await ctx.send("Ainda não há dados para gerar um ranking.")

    # Calcula o overall de cada usuário que tem um time
    user_overalls = []
    for uid, data in user_data.items():
        team = data.get('team', [None] * 11)
        if any(p for p in team): # Apenas considera times com pelo menos 1 jogador
            overall = sum(p['overall'] for p in team if p)
            user_overalls.append((uid, overall))
    
    if not user_overalls:
        return await ctx.send("⭐ **Ranking de Overall Vazio!** Ninguém montou um time ainda.")

    # Ordena os usuários pelo overall
    sorted_users = sorted(user_overalls, key=lambda i: i[1], reverse=True)

    embed = discord.Embed(title="⭐ Ranking de Overall do Time - Top 10 ⭐", color=discord.Color.gold())
    desc = []
    medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, overall) in enumerate(sorted_users[:10]):
        try:
            user = await bot.fetch_user(int(user_id))
            user_name = user.display_name
        except (discord.NotFound, ValueError):
            user_name = f"Usuário Desconhecido ({user_id})"
        medal = medals[i] if i < 3 else "🔹"
        desc.append(f"{medal} **{user_name}** - Overall: `{overall}`")
    
    embed.description = "\n".join(desc)
    await ctx.send(embed=embed)


@bot.command(name='mercado')
async def market(ctx, pos: str = None, sort_by: str = 'valor'):
    """Busca avançada de jogadores no mercado."""
    contracted = load_data(CONTRACTED_PLAYERS_FILE)
    available_players = [p for p in ALL_PLAYERS if p["name"] not in contracted]

    if not available_players:
        return await ctx.send("🤯 **Mercado Vazio!** Todos os jogadores foram contratados.")

    # Filtra por posição, se especificado
    if pos:
        results = [p for p in available_players if pos.upper() in p['position'].split('/')]
        if not results:
            return await ctx.send(f"😥 Nenhum jogador disponível encontrado para a posição: `{pos.upper()}`")
    else:
        results = available_players

    # Ordena os resultados
    valid_sorts = ['valor', 'overall', 'nome']
    sort_by = sort_by.lower()
    if sort_by not in valid_sorts:
        return await ctx.send(f"Opção de ordenação inválida. Use: `{'`, `'.join(valid_sorts)}`.")
    
    reverse_sort = True if sort_by != 'nome' else False
    sort_key = 'value' if sort_by == 'valor' else sort_by
    results.sort(key=lambda p: p[sort_key], reverse=reverse_sort)

    # Cria embeds paginados
    pages = []
    chunk_size = 10
    for i in range(0, len(results), chunk_size):
        chunk = results[i:i + chunk_size]
        embed = discord.Embed(
            title=f"🛒 Mercado (Pág. {len(pages) + 1})",
            description=f"Filtrando por: `{pos.upper() if pos else 'Todos'}` | Ordenado por: `{sort_by.capitalize()}`",
            color=discord.Color.dark_teal()
        )
        for p in chunk:
            embed.add_field(
                name=f"{p['name']} ({p['position']})",
                value=f"**OVR:** {p['overall']} | **Preço:** R$ {p['value']:,}",
                inline=False
            )
        embed.set_footer(text=f"Total de {len(results)} jogadores encontrados.")
        pages.append(embed)
    
    if not pages:
        return await ctx.send("Nenhum resultado encontrado com esses filtros.")

    view = PaginatedEmbedView(ctx, pages)
    await view.start()

# --- LÓGICA DE TROCA ---

async def send_trade_request(ctx, requested_player, **kwargs):
    """Função chamada após o proposer escolher o jogador do alvo."""
    proposer = ctx.author
    offered_player = kwargs.get('offered_player')
    target_user = kwargs.get('target_user')

    embed = discord.Embed(
        title="🔄 Proposta de Troca 🔄",
        description=f"**{target_user.mention}**, o usuário **{proposer.mention}** quer fazer uma troca!",
        color=discord.Color.blue()
    )
    embed.add_field(name=f"Ele oferece:", value=f"**{offered_player['name']}** (OVR: {offered_player['overall']})", inline=False)
    embed.add_field(name=f"Ele quer em troca:", value=f"**{requested_player['name']}** (OVR: {requested_player['overall']})", inline=False)
    embed.set_footer(text="Você tem 5 minutos para aceitar ou recusar.")

    view = TradeConfirmationView(proposer, target_user, offered_player, requested_player)
    message = await ctx.send(content=target_user.mention, embed=embed, view=view)
    view.message = message


async def proposer_selected_player(ctx, offered_player, **kwargs):
    """Função chamada após o proposer escolher o próprio jogador."""
    target_user = kwargs.get('target_user')
    await ctx.message.delete() # Limpa a mensagem anterior

    target_data = await get_user_data(target_user.id)
    target_squad = target_data[str(target_user.id)].get('squad', [])

    if not target_squad:
        return await ctx.send(f"**{target_user.display_name}** não tem jogadores no elenco para trocar.")

    msg = await ctx.send(f"Agora, selecione o jogador que você quer de **{target_user.display_name}**:")
    
    # Prepara os kwargs para o próximo passo
    next_kwargs = {'offered_player': offered_player, 'target_user': target_user}
    
    view = ActionView(ctx, target_squad, send_trade_request, "Pedir em Troca", **next_kwargs)
    embed = await view.create_embed()
    view.message = await ctx.send(embed=embed, view=view)
    await msg.delete()


@bot.command(name='trocar')
async def trade(ctx, target_user: discord.Member):
    """Inicia uma troca de jogadores com outro usuário."""
    proposer = ctx.author
    if proposer == target_user:
        return await ctx.send("Você não pode trocar jogadores consigo mesmo.")
    if target_user.bot:
        return await ctx.send("Você não pode trocar com um bot.")

    proposer_data = await get_user_data(proposer.id)
    proposer_squad = proposer_data[str(proposer.id)].get('squad', [])

    if not proposer_squad:
        return await ctx.send("Você não tem jogadores no seu elenco para trocar.")
    
    msg = await ctx.send("Primeiro, selecione o jogador do seu elenco que você quer oferecer na troca:")
    
    # Inicia o primeiro passo, passando o target_user como kwarg
    view = ActionView(ctx, proposer_squad, proposer_selected_player, "Oferecer", target_user=target_user)
    embed = await view.create_embed()
    view.message = await ctx.send(embed=embed, view=view)
    await msg.delete()

# --- RESTANTE DO CÓDIGO (mantido como estava) ---

@bot.command(name='meutime')
async def my_team(ctx):
    user_data = await get_user_data(ctx.author.id); team = user_data[str(ctx.author.id)]["team"]
    if not any(team): return await ctx.send(f"Você não escalou ninguém!")
    msg = await ctx.send("⚙️ Montando a imagem do time..."); image_file = await generate_team_image(team, ctx.author.display_name)
    await ctx.send(file=discord.File(image_file, 'meutime.png')); await msg.delete()

# ... (todos os outros comandos de `noticias` a `best_team_error` permanecem aqui)
# Para evitar uma resposta excessivamente longa, eles não foram colados novamente, 
# mas devem estar presentes no seu arquivo final.

# --- EXECUÇÃO DO BOT ---
if __name__ == "__main__":
    # Carregue o resto dos seus comandos aqui.
    # Exemplo de como o código se parece:
    # @bot.command(name='noticias') ...
    # @bot.command(name='info') ...
    # etc.
    
    TOKEN = os.environ.get('DISCORD_TOKEN')
    keep_alive() 
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERRO: Token do Discord não encontrado nas variáveis de ambiente.")
