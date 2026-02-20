from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "RafutBot está Online e operando no Supabase!"

def run():
    # Pega a porta da Render ou força a 8080
    port = int(os.environ.get('PORT', 8080))
    print(f"🌐 Ligando servidor Web na porta {port} para a Render...")
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True  # Impede que a thread seja sufocada
    t.start()
