from flask import Flask, request, redirect, jsonify, session
import requests
import os
from urllib.parse import urlencode
import discord
from discord.ext import commands
import asyncio
import threading

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Chave secreta para sessões

# Configurações do Discord
DISCORD_CLIENT_ID = "1410041223317815326"
DISCORD_CLIENT_SECRET = "AAn09cOYRlFaeQ2UnltvPqAjM74kkrXk"
DISCORD_REDIRECT_URI = "https://rbx-api-zk4m.onrender.com/callback"
DISCORD_BOT_TOKEN = "MTQxMDA0MTIyMzMxNzgxNTMyNg.GMRJSn.qowNLXPpAtLiROOIbm2PhXWg1EtCxAtbWUqdKs"
DISCORD_CHANNEL_ID = 1410037654216773745  # ID do canal

# Armazenamento temporário (use banco de dados em produção)
player_data = {}  # {roblox_user_id: {"id": int, "username": str}}
available_ids = list(range(1, 1001))  # IDs de 1 a 1000

# Configurar bot do Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Função para atribuir ID único
def assign_id():
    if available_ids:
        return available_ids.pop(0)
    return None

# Comando !login no Discord
@bot.command()
async def login(ctx, roblox_user_id: str):
    if not roblox_user_id.isdigit():
        await ctx.send("Por favor, forneça um UserId válido do Roblox.")
        return
    
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "state": roblox_user_id  # Passar UserId como state
    }
    auth_url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    await ctx.send(f"Logue no Discord clicando aqui: {auth_url}")

# Rota de callback do Discord
@app.route('/callback')
def callback():
    code = request.args.get('code')
    roblox_user_id = request.args.get('state')
    
    if not code or not roblox_user_id:
        return jsonify({"error": "Código ou UserId inválido"}), 400

    # Trocar código por token
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    
    if response.status_code != 200:
        return jsonify({"error": "Falha na autenticação"}), 400

    token = response.json().get("access_token")
    
    # Obter informações do usuário
    headers = {"Authorization": f"Bearer {token}"}
    user_response = requests.get("https://discord.com/api/users/@me", headers=headers)
    
    if user_response.status_code != 200:
        return jsonify({"error": "Falha ao obter dados do usuário"}), 400

    discord_user = user_response.json()
    discord_username = discord_user.get("username")
    
    # Atribuir ID único
    player_id = assign_id()
    if not player_id:
        return jsonify({"error": "Sem IDs disponíveis"}), 400

    # Armazenar dados
    player_data[roblox_user_id] = {"id": player_id, "username": discord_username}

    # Enviar mensagem ao canal do Discord
    async def send_discord_message():
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            await channel.send(f"Jogador com ID {player_id} (UserId {roblox_user_id}) logou com Discord: {discord_username}")

    asyncio.run_coroutine_threadsafe(send_discord_message(), bot.loop)
    
    return jsonify({"status": "success", "id": player_id, "username": discord_username})

# Rota para consultar dados do jogador
@app.route('/get_player/<roblox_user_id>')
def get_player(roblox_user_id):
    data = player_data.get(roblox_user_id, {"id": 0, "username": "Não logado"})
    return jsonify(data)

# Rota para alterar nome
@app.route('/change_name/<int:player_id>/<new_name>')
def change_name(player_id, new_name):
    if not (1 <= player_id <= 1000):
        return jsonify({"error": "ID inválido"}), 400
    if len(new_name) > 20:
        return jsonify({"error": "Nome muito longo"}), 400
    
    for roblox_user_id, data in player_data.items():
        if data["id"] == player_id:
            data["username"] = new_name
            async def send_discord_message():
                channel = bot.get_channel(DISCORD_CHANNEL_ID)
                if channel:
                    await channel.send(f"Nome do jogador com ID {player_id} alterado para: {new_name}")
            asyncio.run_coroutine_threadsafe(send_discord_message(), bot.loop)
            return jsonify({"status": "success", "new_name": new_name})
    
    return jsonify({"error": "ID não encontrado"}), 404

# Função para rodar o bot do Discord
def run_bot():
    bot.run(DISCORD_BOT_TOKEN)

# Função para rodar Flask
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    # Iniciar bot do Discord em uma thread separada
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True  # Encerrar thread quando o programa principal terminar
    bot_thread.start()
    
    # Iniciar Flask
    run_flask()
