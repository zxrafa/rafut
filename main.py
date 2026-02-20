# -*- coding: utf-8 -*-
"""
RafutBot - Versão 20.0 (Completa e Funcional - Supabase + Render Fix)
----------------------------------------------------------------------
Sem IA, Embeds Bonitos, `.env` configurado e 100% dos comandos originais.
"""

import discord
from discord.ext import commands
import requests
import json
import os
import random
import re
import asyncio
import unicodedata
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from datetime import datetime, timedelta

# --- CARREGAMENTO DO .ENV ---
from dotenv import load_dotenv
load_dotenv()

# --- KEEP ALIVE PARA RENDER ---
# Aqui foi tirado o try/except para forçar a Render a executar o arquivo
from keep_alive import keep_alive

# --- CONEXÃO SUPABASE ---
URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")
if URL and KEY:
    supabase = create_client(URL, KEY)
else:
    print("❌ ERRO: Variáveis SUPABASE_URL ou SUPABASE_KEY não encontradas no .env!")

# --- CONFIGURAÇÕES GERAIS ---
BOT_PREFIX = "--"
PASTEBIN_URL = "https://pastebin.com/raw/YpjKyzdw"
INITIAL_MONEY = 1000000000
SALE_PERCENTAGE = 0.5
DAILY_REWARD = 25000000

SLOT_MAPPING = {"GOL": [0], "ZAG": [1, 2], "LE": [3], "LD": [4], "VOL": [5], "MC": [6], "MEI": [7], "PE": [8], "PD": [9], "CA": [10]}
POSITIONS_COORDS = {0: (350, 780), 1: (180, 650), 2: (520, 650), 3: (60, 550), 4: (640, 550), 5: (350, 500), 6: (220, 370), 7: (480, 370), 8: (90, 200), 9: (610, 200), 10: (350, 160)}
ALL_PLAYERS = []
data_lock = asyncio.Lock()

# --- INICIALIZAÇÃO DO BOT ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

# --- SISTEMA DE NARRAÇÃO SEM IA ---
NEWS_TEMPLATES = [
    "🚨 BOMBA! {player} foi flagrado comendo um x-tudo completo antes do treino decisivo!",
    "📰 POLÊMICA: {player} afirma em entrevista que a bola oficial do campeonato é 'muito redonda'.",
    "🤣 INACREDITÁVEL! {player} tentou dar uma carretilha, tropeçou na própria perna e virou meme.",
    "🔥 NOVO CORTE! {player} aparece no treino com o cabelo platinado e diz: 'Agora eu corro mais'.",
    "👀 MERCADO DA BOLA: Rumores indicam que {player} gastou todo seu salário comprando skins de joguinho."
]
GOAL_NARRATIONS = [
    "⚽ GOOOOLAAAAÇO! {attacker} mandou uma bomba do meio da rua! O goleiro nem viu a cor da bola!",
    "⚽ É REDE! {attacker} dribla dois zagueiros, deixa o goleiro no chão e empurra pro gol vazio! Gênio!",
    "⚽ GOOOOL! {attacker} recebe cruzamento na medida e testa firme pro fundo das redes! Que testada!"
]
SAVE_NARRATIONS = [
    "🧤 MILAAAAGRE! {keeper} voa como um gato no ângulo e espalma a bola pra escanteio! Defesaça!",
    "🧤 INCRÍVEL! O atacante bateu à queima-roupa, mas {keeper} salvou no reflexo com os pés!",
    "🧱 PAREDE! {keeper} fecha o ângulo e defende a bomba de peito! É um monstro na pequena área!"
]

ACHIEVEMENTS = {
    "primeira_vitoria": {"name": "Primeira Vitória", "desc": "Vença sua primeira partida.", "emoji": "🏆"},
    "bom_de_bola": {"name": "Bom de Bola", "desc": "Vença 10 partidas.", "emoji": "🏅"},
    "invencivel": {"name": "Invencível", "desc": "Vença 50 partidas.", "emoji": "👑"},
    "primeiro_milhao": {"name": "Magnata", "desc": "Acumule R$ 1.500.000.000.", "emoji": "🤑"},
    "time_galactico": {"name": "Time Galáctico", "desc": "Monte um time titular com overall 950+.", "emoji": "✨"},
    "lenda": {"name": "Lenda em Campo", "desc": "Tenha um jogador com overall 99.", "emoji": "🐐"},
    "sorte_de_tigre": {"name": "Sorte de Tigre", "desc": "Ganhe o Jackpot no Tigrinho.", "emoji": "🐯"},
}

DAILY_CHALLENGES = [
    {"id": "vencer_partida", "desc": "Vença uma partida contra outro jogador.", "reward": 15000000},
    {"id": "marcar_gol", "desc": "Marque pelo menos um gol em uma partida.", "reward": 5000000},
    {"id": "jogar_partida", "desc": "Jogue uma partida, ganhando ou perdendo.", "reward": 7500000},
    {"id": "contratar_jogador", "desc": "Contrate um novo jogador no mercado.", "reward": 4000000},
]

# --- FUNÇÕES DE EMBED (Beleza e Padronização) ---
def create_embed(title, description="", color=discord.Color.blurple(), ctx=None):
    embed = discord.Embed(title=title, description=description, color=color)
    if ctx:
        embed.set_footer(text=f"Requisitado por {ctx.author.display_name} • RafutBot V20", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
    else:
        embed.set_footer(text="RafutBot V20 • Central Administrativa")
    return embed

def create_error_embed(message, ctx=None):
    return create_embed("❌ Erro na Operação", f"> {message}", discord.Color.red(), ctx)

def create_success_embed(title, message, ctx=None):
    return create_embed(f"✅ {title}", f"> {message}", discord.Color.green(), ctx)

# --- FUNÇÕES DE BANCO DE DADOS (SUPABASE) ---
async def get_user_data(user_id):
    uid = str(user_id)
    res = supabase.table("jogadores").select("data").eq("id", uid).execute()
    
    if not res.data:
        initial = {
            "money": INITIAL_MONEY, "squad": [], "team": [None] * 11, "wins": 0,
            "last_daily": "2000-01-01T00:00:00", "club_name": None, "club_logo": None, 
            "stadium_level": 1, "match_history": [], "achievements": [], "contracted_players": []
        }
        supabase.table("jogadores").insert({"id": uid, "data": initial}).execute()
        return initial
    
    data = res.data[0]["data"]
    # Atualiza perfis antigos caso falte chaves novas
    for key, val in [("stadium_level", 1), ("club_name", None), ("club_logo", None), ("achievements", []), ("match_history", []), ("contracted_players", [])]:
        if key not in data: data[key] = val
    return data

async def save_user_data(user_id, data):
    uid = str(user_id)
    supabase.table("jogadores").update({"data": data}).eq("id", uid).execute()

# --- FUNÇÕES AUXILIARES ---
def normalize_str(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()

def get_player_effective_overall(player):
    return player.get('overall', 0) + player.get('training_level', 0)

def add_player_defaults(player):
    if 'nickname' not in player: player['nickname'] = None
    if 'training_level' not in player: player['training_level'] = 0
    return player

async def check_and_grant_achievement(user_id, achievement_id, ctx=None):
    async with data_lock:
        data = await get_user_data(user_id)
        if achievement_id not in data["achievements"]:
            data["achievements"].append(achievement_id)
            await save_user_data(user_id, data)
            if ctx:
                ach_info = ACHIEVEMENTS[achievement_id]
                embed = create_success_embed(f"{ach_info['emoji']} Conquista: {ach_info['name']}", ach_info['desc'], ctx)
                embed.color = discord.Color.gold()
                await ctx.send(embed=embed)

def fetch_and_parse_players():
    global ALL_PLAYERS
    try:
        response = requests.get(PASTEBIN_URL); response.raise_for_status()
        lines = response.text.strip().split('\n')
        player_regex = re.compile(r'"(.*?)"\s+(https?://[^\s]+)\s+(\d+)\s+([A-Z/]+)\s+(\d+)')
        ALL_PLAYERS = [{"name": match.group(1), "image": match.group(2), "overall": int(match.group(3)), "position": match.group(4), "value": int(match.group(5))} for line in lines if (match := player_regex.match(line.strip()))]
        print(f"✅ Sucesso! {len(ALL_PLAYERS)} jogadores carregados.")
    except Exception as e: print(f"❌ Erro ao carregar jogadores: {e}")

# --- GERADOR DE IMAGEM DO TIME ---
def create_team_image_sync(team_players, club_name, club_logo_url):
    try:
        bg_res = requests.get("https://i.ibb.co/5W8Rvh2F/uaaaa.png", timeout=5)
        field_img = Image.open(BytesIO(bg_res.content)).convert("RGBA")
    except:
        field_img = Image.new("RGB", (700, 900), color=(8, 43, 27))

    draw = ImageDraw.Draw(field_img)
    width, height = field_img.size

    try:
        title_font = ImageFont.truetype("arialbd.ttf", 42)
        p_name_font = ImageFont.truetype("arialbd.ttf", 18)
        p_pos_font = ImageFont.truetype("arial.ttf", 16)
        p_stat_font = ImageFont.truetype("arialbd.ttf", 15)
        stats_font = ImageFont.truetype("arialbd.ttf", 24)
    except:
        title_font = p_name_font = p_pos_font = p_stat_font = stats_font = ImageFont.load_default()

    draw.text((width/2, 38), club_name or "Meu Clube", font=title_font, fill=(0,0,0,120), anchor="mt", stroke_width=2)
    draw.text((width/2, 35), club_name or "Meu Clube", font=title_font, fill="#FFFFFF", anchor="mt")

    if club_logo_url:
        try:
            logo_res = requests.get(club_logo_url, timeout=5)
            logo_img = Image.open(BytesIO(logo_res.content)).convert("RGBA")
            logo_img.thumbnail((80, 80), Image.Resampling.LANCZOS)
            field_img.paste(logo_img, (25, 25), logo_img)
        except: pass

    total_overall = total_value = 0
    img_size = (120, 156)

    for i, player in enumerate(team_players):
        x, y = POSITIONS_COORDS[i]
        if player:
            player = add_player_defaults(player)
            effective_ovr = get_player_effective_overall(player)
            total_overall += effective_ovr
            total_value += player['value']
            
            try:
                p_img_res = requests.get(player["image"], timeout=5)
                p_img = Image.open(BytesIO(p_img_res.content)).convert("RGBA")
            except:
                p_img = Image.new('RGBA', img_size, color='grey')
            
            p_img.thumbnail(img_size, Image.Resampling.LANCZOS)
            field_img.paste(p_img, (x - p_img.width // 2, y - p_img.height // 2), p_img)
            
            base_y = y + (img_size[1] // 2) + 5
            disp_name = player.get('nickname') or player['name'].split(' ')[-1]
            draw.text((x, base_y + 2), disp_name, font=p_name_font, fill="black", anchor="mt", stroke_width=2)
            draw.text((x, base_y), disp_name, font=p_name_font, fill="white", anchor="mt")
            draw.text((x, base_y + 22), player['position'], font=p_pos_font, fill="black", anchor="mt", stroke_width=1)
            draw.text((x, base_y + 21), player['position'], font=p_pos_font, fill="#CCCCCC", anchor="mt")
            
            color = "lime" if player.get('training_level', 0) > 0 else "yellow"
            draw.text((x, base_y + 42), f"OVR {effective_ovr}", font=p_stat_font, fill="black", anchor="mt", stroke_width=2)
            draw.text((x, base_y + 41), f"OVR {effective_ovr}", font=p_stat_font, fill=color, anchor="mt")
        else:
            draw.rectangle((x - 40, y - 40, x + 40, y + 40), outline=(255,255,255,100), width=2)
            draw.text((x, y), "?", fill=(255,255,255,100), font=title_font, anchor="mm")

    draw.text((35, height - 48), f"⭐ Overall Total: {total_overall}", font=stats_font, fill="black", anchor="ls", stroke_width=2)
    draw.text((35, height - 50), f"⭐ Overall Total: {total_overall}", font=stats_font, fill="white", anchor="ls")
    draw.text((35, height - 18), f"💰 Valor de Mercado: R$ {total_value:,}", font=stats_font, fill="black", anchor="ls", stroke_width=2)
    draw.text((35, height - 20), f"💰 Valor de Mercado: R$ {total_value:,}", font=stats_font, fill="#39FF14", anchor="ls")
    
    buffer = BytesIO()
    field_img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

async def generate_team_image(team_players, user):
    user_data = await get_user_data(user.id)
    club_name = user_data.get('club_name') or f"Time de {user.display_name}"
    club_logo = user_data.get('club_logo')
    return await asyncio.to_thread(create_team_image_sync, team_players, club_name, club_logo)


# --- VIEWS (BOTÕES INTERATIVOS) ---
class KeepOrSellView(discord.ui.View):
    def __init__(self, author, player):
        super().__init__(timeout=60); self.author = author; self.player = player; self.decision_made = False
    @discord.ui.button(label="Manter no Elenco", style=discord.ButtonStyle.green)
    async def keep_button(self, inter: discord.Interaction, btn: discord.ui.Button):
        if inter.user != self.author: return await inter.response.send_message("Negado.", ephemeral=True)
        self.decision_made = True
        async with data_lock:
            data = await get_user_data(self.author.id)
            data["squad"].append(add_player_defaults(self.player))
            data["contracted_players"].append(self.player['name'])
            await save_user_data(self.author.id, data)
        embed = inter.message.embeds[0]
        embed.color = discord.Color.green()
        await inter.message.edit(content=f"✅ **{self.player['name']}** adicionado ao elenco!", embed=embed, view=None)
    @discord.ui.button(label="Vender", style=discord.ButtonStyle.red)
    async def sell_button(self, inter: discord.Interaction, btn: discord.ui.Button):
        if inter.user != self.author: return await inter.response.send_message("Negado.", ephemeral=True)
        self.decision_made = True; price = int(self.player['value'] * SALE_PERCENTAGE)
        async with data_lock:
            data = await get_user_data(self.author.id)
            data["money"] += price
            await save_user_data(self.author.id, data)
        await inter.message.edit(content=f"💰 Vendido por **R$ {price:,}**!", embed=None, view=None)

class ContractView(discord.ui.View):
    def __init__(self, ctx, results):
        super().__init__(timeout=120); self.ctx = ctx; self.results = results; self.index = 0
    async def create_embed(self, inter: discord.Interaction = None):
        p = self.results[self.index]
        emb = create_embed(f"🔎 Mercado: {p['name']}", color=discord.Color.blue(), ctx=self.ctx)
        emb.set_thumbnail(url=p['image'])
        emb.add_field(name="Posição", value=f"`{p['position']}`", inline=True)
        emb.add_field(name="Overall", value=f"⭐ **{p['overall']}**", inline=True)
        emb.add_field(name="Preço", value=f"💰 **R$ {p['value']:,}**", inline=False)
        emb.set_footer(text=f"Jogador {self.index + 1}/{len(self.results)}")
        self.children[0].disabled = (self.index == 0)
        self.children[1].disabled = (self.index == len(self.results) - 1)
        self.children[2].label = f"Comprar por R$ {p['value']:,}"
        if inter: await inter.response.edit_message(embed=emb, view=self)
        else: return emb
    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.grey, emoji="⬅️")
    async def prev(self, inter: discord.Interaction, btn):
        if inter.user != self.ctx.author: return
        self.index -= 1; await self.create_embed(inter)
    @discord.ui.button(label="Próximo", style=discord.ButtonStyle.grey, emoji="➡️")
    async def next(self, inter: discord.Interaction, btn):
        if inter.user != self.ctx.author: return
        self.index += 1; await self.create_embed(inter)
    @discord.ui.button(label="Comprar", style=discord.ButtonStyle.green, emoji="💸")
    async def buy(self, inter: discord.Interaction, btn):
        if inter.user != self.ctx.author: return await inter.response.send_message("Negado.", ephemeral=True)
        p = self.results[self.index]
        async with data_lock:
            data = await get_user_data(self.ctx.author.id)
            if p['name'] in data.get("contracted_players", []): return await inter.response.send_message("❌ Jogador já foi contratado!", ephemeral=True)
            if data['money'] < p['value']: return await inter.response.send_message("💸 Dinheiro insuficiente!", ephemeral=True)
            
            data['money'] -= p['value']
            data['squad'].append(add_player_defaults(p))
            data['contracted_players'].append(p['name'])
            await save_user_data(self.ctx.author.id, data)
            
        for c in self.children: c.disabled = True
        emb = await self.create_embed()
        emb.color = discord.Color.green(); emb.title = "✅ Contratado com Sucesso!"
        await inter.response.edit_message(embed=emb, view=self)
        await self.ctx.send(f"🎉 Parabéns {self.ctx.author.mention}, **{p['name']}** é do seu time!")
        await check_and_grant_achievement(self.ctx.author.id, "contratar_jogador", self.ctx)

class ActionView(discord.ui.View):
    def __init__(self, ctx, results, callback, action_name, **kwargs):
        super().__init__(timeout=120); self.ctx = ctx; self.results = results; self.callback = callback; self.action_name = action_name; self.index = 0; self.kwargs = kwargs
        self.children[2].label = action_name
    async def create_embed(self, inter: discord.Interaction = None):
        p = add_player_defaults(self.results[self.index])
        eff_ovr = get_player_effective_overall(p)
        emb = create_embed(f"Ação: {self.action_name}", color=discord.Color.orange(), ctx=self.ctx)
        emb.set_thumbnail(url=p['image'])
        emb.add_field(name="Jogador", value=f"**{p.get('nickname') or p['name']}**", inline=False)
        emb.add_field(name="Posição", value=f"`{p['position']}`", inline=True)
        emb.add_field(name="Overall", value=f"⭐ **{eff_ovr}**", inline=True)
        emb.set_footer(text=f"Opção {self.index + 1}/{len(self.results)}")
        self.children[0].disabled = (self.index == 0)
        self.children[1].disabled = (self.index == len(self.results) - 1)
        if inter: await inter.response.edit_message(embed=emb, view=self)
        else: return emb
    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.grey, emoji="⬅️")
    async def prev(self, inter: discord.Interaction, btn):
        if inter.user != self.ctx.author: return
        self.index -= 1; await self.create_embed(inter)
    @discord.ui.button(label="Próximo", style=discord.ButtonStyle.grey, emoji="➡️")
    async def next(self, inter: discord.Interaction, btn):
        if inter.user != self.ctx.author: return
        self.index += 1; await self.create_embed(inter)
    @discord.ui.button(style=discord.ButtonStyle.primary)
    async def action(self, inter: discord.Interaction, btn):
        if inter.user != self.ctx.author: return await inter.response.send_message("Negado.", ephemeral=True)
        await self.callback(self.ctx, self.results[self.index], **self.kwargs)
        for c in self.children: c.disabled = True
        try:
            await inter.response.edit_message(view=self)
            await self.message.delete(delay=1)
        except: pass

class RocketView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=90.0); self.author = author; self.decision = None
    @discord.ui.button(label="Retirar AGORA!", style=discord.ButtonStyle.green, emoji="💸")
    async def cash_out(self, inter: discord.Interaction, btn: discord.ui.Button):
        if inter.user != self.author: return await inter.response.send_message("Não é sua aposta!", ephemeral=True)
        self.decision = "cashed_out"; btn.disabled = True
        await inter.response.edit_message(view=self); self.stop()

# --- EVENTOS ---
@bot.event
async def on_ready():
    print(f'🚀 {bot.user.name} V20.0 está no ar com SUPABASE e FLASK!')
    fetch_and_parse_players()
    await bot.change_presence(activity=discord.Game(name=f"Use {BOT_PREFIX}help"))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): pass
    elif isinstance(error, commands.CommandOnCooldown): 
        await ctx.send(embed=create_error_embed(f"⏳ Habilidade em recarga! Tente em **{int(error.retry_after)}s**.", ctx))
    elif isinstance(error, commands.MissingRequiredArgument): 
        await ctx.send(embed=create_error_embed(f"⚠️ Faltam informações! Verifique o comando.", ctx))
    else: print(f"Erro detectado: {error}")

# --- COMANDOS CORE ---
@bot.command(name='help')
async def help_command(ctx):
    embed = create_embed("📜 Central de Comandos RafutBot 📜", "Seu guia definitivo para dominar os campos.", discord.Color.gold(), ctx)
    embed.add_field(name="💰 Dinheiro & Recompensas", value=f"`{BOT_PREFIX}daily`, `{BOT_PREFIX}saldo`, `{BOT_PREFIX}doar`, `{BOT_PREFIX}estadio`", inline=False)
    embed.add_field(name="🛒 Mercado da Bola", value=f"`{BOT_PREFIX}contratar`, `{BOT_PREFIX}mercadolivre`, `{BOT_PREFIX}destaques`, `{BOT_PREFIX}obter`", inline=False)
    embed.add_field(name="📋 Gestão do Clube", value=f"`{BOT_PREFIX}escalar`, `{BOT_PREFIX}elenco`, `{BOT_PREFIX}meutime`", inline=False)
    embed.add_field(name="⚽ Confrontos & Rankings", value=f"`{BOT_PREFIX}confrontar`, `{BOT_PREFIX}perfil`", inline=False)
    embed.add_field(name="🎲 Cassino & Sorte", value=f"`{BOT_PREFIX}tigrinho`, `{BOT_PREFIX}rocket`, `{BOT_PREFIX}noticias`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='perfil')
async def perfil(ctx, user: discord.Member = None):
    user = user or ctx.author
    async with data_lock:
        data = await get_user_data(user.id)

    team_ovr = sum(get_player_effective_overall(p) for p in data['team'] if p)
    matches_played = len(data['match_history'])
    win_rate = (data['wins'] / matches_played * 100) if matches_played > 0 else 0

    embed = create_embed(f"👤 Perfil de {user.display_name}", color=user.color, ctx=ctx)
    if user.avatar: embed.set_thumbnail(url=user.avatar.url)
    
    embed.add_field(name="👑 Nome do Clube", value=f"> **{data.get('club_name') or 'Sem Clube'}**", inline=False)
    embed.add_field(name="💰 Saldo", value=f"`R$ {data['money']:,}`", inline=True)
    embed.add_field(name="🏆 Vitórias", value=f"`{data['wins']} ({win_rate:.1f}%)`", inline=True)
    embed.add_field(name="⭐ Overall do Time", value=f"`{team_ovr}`", inline=True)
    embed.add_field(name="🎽 Tamanho do Elenco", value=f"`{len(data['squad'])} atletas`", inline=True)
    embed.add_field(name="🏟️ Nível do Estádio", value=f"`{data.get('stadium_level', 1)}`", inline=True)
    
    last_match = data['match_history'][-1] if data['match_history'] else "Nenhuma partida jogada."
    embed.add_field(name="📜 Última Partida", value=f"> {last_match}", inline=False)
    await ctx.send(embed=embed)

# --- COMANDOS DE ECONOMIA ---
@bot.command(name='saldo')
async def balance(ctx):
    data = await get_user_data(ctx.author.id)
    money = data['money']
    await ctx.send(embed=create_embed("Extrato Bancário", f"💰 Você possui **R$ {money:,}** na sua conta.", discord.Color.green(), ctx))

@bot.command(name='daily')
@commands.cooldown(1, 5, commands.BucketType.user)
async def daily(ctx):
    uid = str(ctx.author.id)
    async with data_lock:
        data = await get_user_data(uid)
        last_dt = datetime.fromisoformat(data.get("last_daily", "2000-01-01T00:00:00"))
        
        if datetime.utcnow() > last_dt + timedelta(hours=22):
            bonus = 500000 * data.get('stadium_level', 1)
            total = DAILY_REWARD + bonus
            data["money"] += total
            data["last_daily"] = datetime.utcnow().isoformat()
            await save_user_data(uid, data)
            emb = create_success_embed("Patrocínio Recebido!", f"Você coletou **R$ {DAILY_REWARD:,}**\nBônus do Estádio: **R$ {bonus:,}**\n\nTotal: **R$ {total:,}**", ctx)
            await ctx.send(embed=emb)
        else:
            rem = (last_dt + timedelta(hours=22)) - datetime.utcnow()
            h, r = divmod(int(rem.total_seconds()), 3600)
            await ctx.send(embed=create_error_embed(f"O patrocínio ainda não caiu. Volte em **{h}h e {r//60}m**.", ctx))

@bot.command(name='doar')
async def doar(ctx, target: discord.Member, amount: int):
    if ctx.author == target: return await ctx.send(embed=create_error_embed("Não pode doar para si mesmo.", ctx))
    if amount <= 0: return await ctx.send(embed=create_error_embed("Valor inválido.", ctx))
    async with data_lock:
        data_s = await get_user_data(ctx.author.id)
        if data_s['money'] < amount: return await ctx.send(embed=create_error_embed("Saldo insuficiente.", ctx))
        data_t = await get_user_data(target.id) 
        data_s['money'] -= amount
        data_t['money'] += amount
        await save_user_data(ctx.author.id, data_s)
        await save_user_data(target.id, data_t)
    await ctx.send(embed=create_success_embed("Transferência PIX Concluída", f"💸 **{ctx.author.display_name}** enviou **R$ {amount:,}** para **{target.display_name}**!", ctx))

# --- COMANDOS DE MERCADO ---
@bot.command(name='mercadolivre')
async def free_agents(ctx):
    data = await get_user_data(ctx.author.id)
    livres = [p for p in ALL_PLAYERS if p['value'] <= 1000000 and p['name'] not in data.get("contracted_players", [])]
    if not livres: return await ctx.send(embed=create_error_embed("Não há jogadores baratos disponíveis.", ctx))
    random.shuffle(livres)
    emb = create_embed("🛒 Mercado Livre - Jogadores Básicos", "Reforços baratos para começar:", discord.Color.light_grey(), ctx)
    for p in livres[:5]:
        emb.add_field(name=p['name'], value=f"`{p['position']}` | OVR: {p['overall']} | R$ {p['value']:,}", inline=False)
    await ctx.send(embed=emb)

@bot.command(name='destaques')
async def destaques(ctx):
    top5 = sorted(ALL_PLAYERS, key=lambda p: p['overall'], reverse=True)[:5]
    emb = create_embed("🔥 Destaques Globais", "Os 5 melhores jogadores do jogo:", discord.Color.orange(), ctx)
    for p in top5:
        emb.add_field(name=f"💎 {p['name']} (OVR {p['overall']})", value=f"Pos: `{p['position']}` | Preço: `R$ {p['value']:,}`", inline=False)
    await ctx.send(embed=emb)

@bot.command(name='contratar', aliases=['comprar'])
async def contract_player(ctx, *, query: str):
    sq = normalize_str(query)
    data = await get_user_data(ctx.author.id)
    livres = [p for p in ALL_PLAYERS if p["name"] not in data.get("contracted_players", [])]
    res = [p for p in livres if sq in normalize_str(p['name']) or sq.upper() in p['position'].split('/')]
    if not res: return await ctx.send(embed=create_error_embed(f"Nenhum jogador livre encontrado para `{query}`", ctx))
    res.sort(key=lambda p: p['value'], reverse=True)
    view = ContractView(ctx, res); emb = await view.create_embed()
    view.message = await ctx.send(embed=emb, view=view)

@bot.command(name='obter')
@commands.cooldown(1, 300, commands.BucketType.user)
async def get_player(ctx):
    async with data_lock:
        data = await get_user_data(ctx.author.id)
        livres = [p for p in ALL_PLAYERS if p["name"] not in data.get("contracted_players", [])]
        if not livres: return await ctx.send(embed=create_error_embed("Mercado Vazio!", ctx))
        p = random.choice(livres)
    emb = create_embed("🃏 Carta Sorteada!", color=discord.Color.purple(), ctx=ctx)
    emb.set_thumbnail(url=p["image"])
    emb.add_field(name=p['name'], value=f"> Overall: **{p['overall']}**\n> Posição: **{p['position']}**\n> Venda Rápida: **R$ {int(p['value']*SALE_PERCENTAGE):,}**")
    view = KeepOrSellView(ctx.author, p)
    view.message = await ctx.send(embed=emb, view=view)

# --- COMANDOS DE TIME ---
@bot.command(name='elenco')
async def squad_command(ctx):
    data = await get_user_data(ctx.author.id); squad = data["squad"]
    if not squad: return await ctx.send(embed=create_error_embed("Seu elenco está vazio!", ctx))
    emb = create_embed(f"🎽 Elenco de {ctx.author.display_name}", color=ctx.author.color, ctx=ctx)
    lines = []
    for p in sorted(squad, key=lambda p: p['name']):
        p = add_player_defaults(p)
        lines.append(f"**{p.get('nickname') or p['name']}** | `{p['position']}` | OVR: **{get_player_effective_overall(p)}**")
    emb.description = "\n".join(lines[:20]) # Limitado para n estourar o chat
    await ctx.send(embed=emb)

@bot.command(name='meutime')
async def my_team(ctx):
    data = await get_user_data(ctx.author.id); team = data["team"]
    if not any(team): return await ctx.send(embed=create_error_embed("Você não escalou ninguém!", ctx))
    msg = await ctx.send("⚙️ Desenhando a prancheta tática...")
    try:
        img_file = await generate_team_image(team, ctx.author)
        await ctx.send(file=discord.File(img_file, 'meutime.png')); await msg.delete()
    except Exception as e: await msg.edit(content=f"❌ Erro ao gerar imagem: {e}")

async def perform_escalar(ctx, player, **kwargs):
    async with data_lock:
        data = await get_user_data(ctx.author.id); team = data['team']
        if any(p and p['name'] == player['name'] for p in team): return await ctx.send(embed=create_error_embed("Jogador já escalado.", ctx))
        empty_slot, chosen_pos = -1, ""
        for pos in player['position'].split('/'):
            if pos in SLOT_MAPPING:
                found = next((i for i in SLOT_MAPPING[pos] if team[i] is None), -1)
                if found != -1: empty_slot = found; chosen_pos = pos; break
        if empty_slot != -1:
            team[empty_slot] = player; await save_user_data(ctx.author.id, data)
            await ctx.send(embed=create_success_embed("Escalação", f"**{player.get('nickname') or player['name']}** escalado como **{chosen_pos}**!", ctx))
        else: await ctx.send(embed=create_error_embed(f"Vagas de **{player['position']}** estão ocupadas.", ctx))

@bot.command(name='escalar')
async def set_player(ctx, *, query: str):
    sq = normalize_str(query); data = await get_user_data(ctx.author.id); squad = data['squad']
    res = [p for p in squad if sq in normalize_str(p.get('nickname') or p['name'])]
    if not res: return await ctx.send(embed=create_error_embed(f"Nenhum jogador encontrado com `{query}`", ctx))
    if len(res) == 1: await perform_escalar(ctx, res[0])
    else:
        view = ActionView(ctx, res, perform_escalar, "Escalar Titular"); emb = await view.create_embed()
        view.message = await ctx.send(embed=emb, view=view)

# --- COMANDOS DE DIVERSÃO / CASSINO ---
@bot.command(name='noticias')
async def news(ctx):
    data = await get_user_data(ctx.author.id); squad = data.get('squad', [])
    if not squad: return await ctx.send(embed=create_error_embed("Você precisa ter jogadores para gerar notícias!", ctx))
    p = random.choice(squad)
    headline = random.choice(NEWS_TEMPLATES).format(player=p.get('nickname') or p['name'])
    emb = create_embed("🗞️ PLANTÃO RAFUTNEWS 🗞️", f"> ## \"{headline}\"", discord.Color.blurple(), ctx)
    emb.set_thumbnail(url=p['image'])
    await ctx.send(embed=emb)

@bot.command(name='tigrinho')
async def tigrinho_game(ctx, bet: int):
    uid = str(ctx.author.id)
    async with data_lock:
        data = await get_user_data(uid); money = data['money']
        if bet <= 0: return await ctx.send(embed=create_error_embed("Aposta inválida.", ctx))
        if money < bet: return await ctx.send(embed=create_error_embed(f"Saldo insuficiente! Você tem R$ {money:,}", ctx))
        data['money'] -= bet; await save_user_data(uid, data)
    
    emojis = ["🍒", "🍋", "🍊", "🍉", "⭐", "💎", "🐯"]
    msg = await ctx.send(f"🎰 Girando... (Apostou R$ {bet:,})")
    await asyncio.sleep(1.5)
    
    reels = [random.choice(emojis) for _ in range(3)]
    mult, title = 0, "PERDEU!"
    if reels.count("🐯") == 3: mult = 50; title = "JACKPOT! 🐯🐯🐯"; await check_and_grant_achievement(ctx.author.id, "sorte_de_tigre", ctx)
    elif reels.count(reels[0]) == 3: mult = 10 if reels[0] != "🍒" else 5; title = "GRANDE PRÊMIO!"
    elif reels.count("🐯") == 2: mult = 5; title = "QUASE O JACKPOT!"
    elif reels.count(reels[0]) == 2 or reels.count(reels[1]) == 2: mult = 2; title = "PRÊMIO PEQUENO!"
    
    win = int(bet * mult)
    if win > 0:
        async with data_lock:
            data = await get_user_data(uid); data['money'] += win; await save_user_data(uid, data)
            
    emb = create_embed(title, f"| {reels[0]} | {reels[1]} | {reels[2]} |\n\nRetorno: **R$ {win:,}**", discord.Color.green() if win > 0 else discord.Color.red(), ctx)
    await msg.edit(content="", embed=emb)

@bot.command(name='rocket')
async def rocket_game(ctx, bet: int):
    uid = str(ctx.author.id)
    async with data_lock:
        data = await get_user_data(uid); money = data['money']
        if bet <= 0 or money < bet: return await ctx.send(embed=create_error_embed("Aposta inválida ou saldo insuficiente.", ctx))
        data['money'] -= bet; await save_user_data(uid, data)
        
    view = RocketView(ctx.author)
    emb = create_embed("🚀 Jogo do Foguete", f"Apostou: **R$ {bet:,}**\nMultiplicador: **1.00x**", discord.Color.purple(), ctx)
    msg = await ctx.send(embed=emb, view=view)
    
    mult, crash = 1.0, random.uniform(1.1, 15.0)
    while mult < crash:
        await asyncio.sleep(1.5); mult += 0.10 + (mult * 0.05)
        emb.description = f"Apostou: **R$ {bet:,}**\nMultiplicador: **{mult:.2f}x**"
        await msg.edit(embed=emb)
        if view.decision == "cashed_out":
            win = int(bet * mult)
            async with data_lock:
                d = await get_user_data(uid); d['money'] += win; await save_user_data(uid, d)
            emb.title = "🎉 Retirou a tempo!"; emb.color = discord.Color.green(); emb.description = f"Retirou em **{mult:.2f}x**\nGanhou **R$ {win:,}**!"
            return await msg.edit(embed=emb, view=None)
            
    emb.title = "💥 EXPLODIU!"; emb.color = discord.Color.red(); emb.description = f"Crash em **{mult:.2f}x**\nPerdeu **R$ {bet:,}**."
    await msg.edit(embed=emb, view=None)

# --- PARTIDAS E CONFRONTOS ---
@bot.command(name='confrontar')
async def confront(ctx, opp: discord.Member):
    if ctx.author == opp or opp.bot: return await ctx.send(embed=create_error_embed("Oponente inválido.", ctx))
    async with data_lock:
        d1 = await get_user_data(ctx.author.id); d2 = await get_user_data(opp.id)
        t1_raw = d1.get("team", []); t2_raw = d2.get("team", [])
        
    if None in t1_raw or None in t2_raw: return await ctx.send(embed=create_error_embed("Ambos precisam de 11 titulares!", ctx))
    
    t1 = [add_player_defaults(p) for p in t1_raw]; t2 = [add_player_defaults(p) for p in t2_raw]
    def get_sec(team, pos): return [p for p in team if p and any(x in p['position'] for x in pos)]
    
    p1 = {"name": ctx.author.display_name, "att": get_sec(t1, ['PE', 'PD', 'CA', 'MEI']), "def": get_sec(t1, ['ZAG', 'LE', 'LD']), "gk": get_sec(t1, ['GOL'])[0], "score": 0}
    p2 = {"name": opp.display_name, "att": get_sec(t2, ['PE', 'PD', 'CA', 'MEI']), "def": get_sec(t2, ['ZAG', 'LE', 'LD']), "gk": get_sec(t2, ['GOL'])[0], "score": 0}

    log = ["🎙️ **O juiz apita! Rola a bola!**"]
    emb = create_embed(f"🔵 {p1['name']} vs {p2['name']} 🔴", color=discord.Color.greyple(), ctx=ctx)
    emb.add_field(name="Placar", value="0 - 0", inline=False)
    emb.add_field(name="Ao Vivo 🔴", value="```\n" + log[0] + "\n```", inline=False)
    msg = await ctx.send(embed=emb)

    for minute in [15, 30, 45, 60, 75, 90]:
        await asyncio.sleep(2.5)
        atk, dfn = (p1, p2) if random.random() > 0.5 else (p2, p1)
        
        if not atk["att"] or not dfn["def"]: continue
        
        attacker = random.choice(atk["att"]); defender = random.choice(dfn["def"]); gk = dfn["gk"]
        att_name = attacker.get('nickname') or attacker['name']; gk_name = gk.get('nickname') or gk['name']

        if get_player_effective_overall(attacker) + random.randint(-15, 15) > get_player_effective_overall(defender):
            if get_player_effective_overall(attacker) + random.randint(-10, 10) > get_player_effective_overall(gk):
                log.append(f"{minute}' " + random.choice(GOAL_NARRATIONS).format(attacker=att_name))
                atk["score"] += 1
            else: log.append(f"{minute}' " + random.choice(SAVE_NARRATIONS).format(keeper=gk_name, attacker=att_name))
        else: log.append(f"{minute}' 🧱 Zaga sólida! O ataque de {atk['name']} parou na defesa.")
        
        emb.set_field_at(0, name="Placar", value=f"**{p1['score']} - {p2['score']}**", inline=False)
        emb.set_field_at(1, name="Ao Vivo 🔴", value="```\n" + "\n".join(log[-3:]) + "\n```", inline=False)
        await msg.edit(embed=emb)

    await asyncio.sleep(2)
    win_str = f"🏆 Vitória de **{p1['name'] if p1['score'] > p2['score'] else p2['name']}**!" if p1["score"] != p2["score"] else "🤝 Empate Técnico!"
    
    async with data_lock:
        data1 = await get_user_data(ctx.author.id); data2 = await get_user_data(opp.id)
        data1["match_history"].append(f"{p1['score']}x{p2['score']} vs {p2['name']}")
        data2["match_history"].append(f"{p2['score']}x{p1['score']} vs {p1['name']}")
        if p1["score"] > p2["score"]: data1["wins"] += 1
        elif p2["score"] > p1["score"]: data2["wins"] += 1
        await save_user_data(ctx.author.id, data1); await save_user_data(opp.id, data2)

    final_emb = create_embed("🏁 FIM DE JOGO 🏁", f"### {p1['name']} {p1['score']} x {p2['score']} {p2['name']}\n\n> {win_str}", discord.Color.gold(), ctx)
    await msg.edit(embed=final_emb)

# --- INICIAR BOT ---
if __name__ == "__main__":
    # ESSA É A LINHA MÁGICA QUE SALVA O BOT NA RENDER
    keep_alive() 
    
    token = os.getenv("DISCORD_TOKEN")
    if token: 
        bot.run(token)
    else: 
        print("❌ ERRO: DISCORD_TOKEN não encontrado!")
