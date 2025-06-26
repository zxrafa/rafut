# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------
# RafutBot V13 - Um bot de Dream Team com Narração Completa
# ----------------------------------------------------------------------
# Esta versão inclui:
# - Sistema de confronto com narração minuto a minuto.
# - Narrador e Comentarista com diálogos dinâmicos.
# - Lógica de jogadas detalhadas: passe, drible, finalização.
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
from keep_alive import keep_alive

# --- CONFIGURAÇÕES GERAIS ---
BOT_PREFIX = "R!"
PASTEBIN_URL = "https://pastebin.com/raw/YpjKyzdw"
USER_DATA_FILE = "rafutbot_user_data.json"
CONTRACTED_PLAYERS_FILE = "rafutbot_contracted_players.json"
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
    # ... (código da função generate_team_image)
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

# --- VIEWS DE INTERAÇÃO (sem alterações) ---
# ... (Cole aqui as classes KeepOrSellView, ContractView e ActionView da V9)

# --- EVENTOS E COMANDOS ---
@bot.event
async def on_ready():
    print(f'🚀 {bot.user.name} V13 (Narração Completa) está no ar!'); fetch_and_parse_players()
    await bot.change_presence(activity=discord.Game(name=f"Use {BOT_PREFIX}help"))

@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(title="📜 Comandos do RafutBot 13.0 📜", color=discord.Color.gold())
    # ... (código do help, sem mudanças na lista de comandos)
    await ctx.send(embed=embed)

# --- COMANDOS COMUNS (sem alterações) ---
# ... (Cole aqui os comandos obter, saldo, escalar, banco, vender, etc. da V9/V12)

# --- NOVO MOTOR DE CONFRONTO HIPER-REALISTA V13 ---
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

    # --- NARRATIVE ENGINE ---
    commentator_phrases = {
        "good_play": ["Que categoria!", "Esse sabe o que faz com a bola, narrador!", "Jogada de gênio!"],
        "bad_play": ["Faltou capricho aí, hein?", "Era pra ter feito melhor...", "Desperdiçou uma boa chance."],
        "great_save": ["Um verdadeiro paredão esse goleiro!", "Buscou no cantinho! Que defesaça!", "Salvou o time agora!"]
    }

    # --- Lógica da Simulação ---
    def get_team_sector(team, positions):
        return [p for p in team if p and p['position'] in positions]

    teams = {
        author.id: {"user": author, "players": author_team, "attack": get_team_sector(author_team, ['PE', 'PD', 'CA', 'MEI']), "mid": get_team_sector(author_team, ['MC', 'VOL']), "def": get_team_sector(author_team, ['ZAG', 'LE', 'LD']), "keeper": get_team_sector(author_team, ['GOL'])[0]},
        opponent.id: {"user": opponent, "players": opp_team, "attack": get_team_sector(opp_team, ['PE', 'PD', 'CA', 'MEI']), "mid": get_team_sector(opp_team, ['MC', 'VOL']), "def": get_team_sector(opp_team, ['ZAG', 'LE', 'LD']), "keeper": get_team_sector(opp_team, ['GOL'])[0]}
    }
    
    # --- Início da Partida ---
    score = {author.id: 0, opponent.id: 0}
    goalscorers = {author.id: [], opponent.id: []}
    match_log = ["🎙️ **Narrador:** Começa o jogo! Uma grande partida nos espera!"]
    
    embed = discord.Embed(title=f"🔵 {author.display_name} vs {opponent.display_name} 🔴", color=discord.Color.greyple())
    embed.add_field(name="Placar", value=f"0 - 0", inline=False)
    embed.add_field(name="Ao Vivo 🔴", value="```\n" + "\n".join(match_log) + "\n```", inline=False)
    match_message = await ctx.send(embed=embed)

    ball_holder = None
    possession_team_id = random.choice([author.id, opponent.id])

    for minute in range(1, 92):
        await asyncio.sleep(1.5)

        # Determina quem tem a bola e o que acontece
        mid_battle = sum(p['overall'] for p in teams[author.id]["mid"]) - sum(p['overall'] for p in teams[opponent.id]["mid"])
        if random.random() < (0.5 + mid_battle / 250):
            possession_team_id = author.id
        else:
            possession_team_id = opponent.id
            
        attacker_id = possession_team_id
        defender_id = opponent.id if possession_team_id == author.id else author.id

        event_chance = (sum(p['overall'] for p in teams[attacker_id]["attack"]) / len(teams[attacker_id]["attack"])) / 250.0
        
        if random.random() > event_chance:
            if not ball_holder:
                ball_holder = random.choice(teams[attacker_id]["mid"])
            new_ball_holder = random.choice(teams[attacker_id]["players"])
            log_entry = f"{minute}' - **{teams[attacker_id]['user'].display_name}** com a posse. **{ball_holder['name']}** toca para **{new_ball_holder['name']}**."
            ball_holder = new_ball_holder
        else:
            # JOGADA OFENSIVA!
            playmaker = random.choice(teams[attacker_id]["mid"])
            attacker = random.choice(teams[attacker_id]["attack"])
            defender = random.choice(teams[defender_id]["def"])
            keeper = teams[defender_id]["keeper"]

            log_entry = f"⚡ {minute}' - **{playmaker['name']}** inicia o ataque! Ele lança para **{attacker['name']}**..."
            match_log.append(log_entry)
            embed.set_field_at(1, name="Ao Vivo 🔴", value="```\n" + "\n".join(match_log[-7:]) + "\n```")
            await match_message.edit(embed=embed)
            await asyncio.sleep(2)

            dribble_success = (attacker['overall'] - defender['overall']) > random.randint(-25, 25)
            if not dribble_success:
                log_entry = f"🧱 **{defender['name']}** chega junto e corta a jogada! Que categoria do zagueirão."
            else:
                log_entry = f"🏃‍♂️ **{attacker['name']}** passa por **{defender['name']}** e fica de frente pro gol! VAI CHUTAR..."
                match_log.append(log_entry)
                embed.set_field_at(1, name="Ao Vivo 🔴", value="```\n" + "\n".join(match_log[-7:]) + "\n```")
                await match_message.edit(embed=embed)
                await asyncio.sleep(2.5)

                shot_power = attacker['overall'] + random.randint(-10, 10)
                save_power = keeper['overall'] + random.randint(-15, 15)
                
                outcome = random.choices(['goal', 'save', 'post', 'miss', 'penalty'], weights=[35, 30, 10, 15, 10], k=1)[0]
                if shot_power < save_power and outcome == 'goal': outcome = 'save'

                if outcome == 'goal':
                    log_entry = f"⚽ **GOOOOOOOOOOOOOOOOOOOOL! É DE {teams[attacker_id]['user'].display_name.upper()}!** **{attacker['name']}** não perdoa e manda pra rede!"
                    score[attacker_id] += 1
                    goalscorers[attacker_id].append(f"{attacker['name']} ({playmaker['name']}) {minute}'")
                    # Chance de comentário
                    if random.random() < 0.5:
                        log_entry += f"\n🎙️ **Comentarista:** {random.choice(commentator_phrases['good_play'])}"
                elif outcome == 'save':
                    log_entry = f"🧤 **ESPAAAAAALMA {keeper['name'].upper()}!** Que defesa espetacular! Salva o time!"
                    if random.random() < 0.5:
                        log_entry += f"\n🎙️ **Comentarista:** {random.choice(commentator_phrases['great_save'])}"
                elif outcome == 'post':
                    log_entry = f"💥 **NA TRAVE!** A bola explode no poste! Inacreditável!"
                elif outcome == 'penalty':
                    log_entry = f"🚨 **PÊNALTI MÁXIMO!** {defender['name']} comete a falta em {attacker['name']} dentro da área!"
                    await match_message.edit(content=log_entry)
                    await asyncio.sleep(3)
                    penalty_shot = attacker['overall'] + random.randint(-5, 5); penalty_save = keeper['overall'] + random.randint(-15, 15)
                    if penalty_shot > penalty_save:
                        score[attacker_id] += 1; goalscorers[attacker_id].append(f"{attacker['name']} (P) {minute}'")
                        log_entry = f"⚽ **GOL!** {attacker['name']} cobra com frieza e marca de pênalti!"
                    else:
                        log_entry = f"🧤 **PEGOUUUU!** **{keeper['name']}** adivinha o canto e faz a defesa!"
                else: # miss
                    log_entry = f"🤦‍♂️ **PRA FORA!** Que chance perdida por **{attacker['name']}**! Ele isolou a bola!"
                    if random.random() < 0.5:
                        log_entry += f"\n🎙️ **Comentarista:** {random.choice(commentator_phrases['bad_play'])}"
        
        match_log.append(log_entry)
        
        # Atualiza a mensagem
        embed.set_field_at(0, name="Placar", value=f"🔵 {score[author.id]} - {score[opponent.id]} 🔴")
        embed.set_field_at(1, name="Ao Vivo 🔴", value="```\n" + "\n".join(match_log[-6:]) + "\n```") # Mostra os últimos eventos
        if minute == 45:
            match_log.append("\n⏸️ **FIM DO PRIMEIRO TEMPO!**\n")
        
        await match_message.edit(embed=embed)

    # --- Fim de Jogo ---
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
    author_scorers = ", ".join(goalscorers[author.id]) or "Ninguém"
    opp_scorers = ", ".join(goalscorers[opponent.id]) or "Ninguém"
    final_embed.add_field(name=f"Gols de {author.display_name}", value=author_scorers, inline=True)
    final_embed.add_field(name=f"Gols de {opponent.display_name}", value=opp_scorers, inline=True)
    
    await match_message.edit(embed=final_embed)

# --- EXECUÇÃO DO BOT ---
if __name__ == "__main__":
    # Cole aqui o restante dos seus comandos (saldo, tigrinho, admin, etc.) para garantir que tudo funcione.
    # O código foi omitido para focar na mudança principal, mas eles são necessários para rodar.
    TOKEN = os.environ.get('DISCORD_TOKEN') 
    keep_alive() 
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERRO: Token do Discord não encontrado nas variáveis de ambiente.")
