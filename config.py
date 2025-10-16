import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8288405144'))

# API Configuration
API_KEY = os.getenv('API_KEY', 'WCjWLueQo596P03tFr8Q')
API_URL = os.getenv('API_URL', 'https://ulpcloud.site/url')

# NOWPayments Configuration
NOWPAYMENTS_API_KEY = os.getenv('NOWPAYMENTS_API_KEY', '')
NOWPAYMENTS_IPN_SECRET = os.getenv('NOWPAYMENTS_IPN_SECRET', '')
NOWPAYMENTS_API_URL = 'https://api.nowpayments.io/v1'

# Pricing Configuration (em EUR)
PRICE_PER_SEARCH = float(os.getenv('PRICE_PER_SEARCH', '1.00'))  # €1.00 por busca
PRICE_CURRENCY = 'EUR'  # Moeda padrão

PACKAGE_PRICES = {
    '10': {'credits': 10, 'price': 10.00, 'bonus': 0},      # €10 = 10 buscas
    '25': {'credits': 25, 'price': 25.00, 'bonus': 0},      # €25 = 25 buscas
    '50': {'credits': 50, 'price': 50.00, 'bonus': 5},      # €50 = 50 + 5 bônus
    '100': {'credits': 100, 'price': 100.00, 'bonus': 15},  # €100 = 100 + 15 bônus
}

# Bot Settings
MIN_SEARCH_LENGTH = 3
MAX_URL_LENGTH = 55
FREE_SEARCHES_PER_USER = 1  # Apenas 1 busca grátis (download) para novos usuários

# Messages
WELCOME_MESSAGE = """👋 <b>Bem-vindo, {name}!</b>

━━━━━━━━━━━━━━━━━━━━

🔍 <b>COMANDOS DISPONÍVEIS:</b>

🌐 <code>/url URL</code> - Buscar credenciais
🔗 <code>/ur URL</code> - Busca rápida
⚡ <code>/u URL</code> - Busca express

💰 <code>/saldo</code> - Ver seu saldo
💳 <code>/comprar</code> - Comprar créditos
📊 <code>/historico</code> - Ver histórico

🎁 <code>/referral</code> - Sistema de indicação
🎟️ <code>/cupom CODIGO</code> - Usar cupom

💬 <b>Ou simplesmente envie a URL direto!</b>

━━━━━━━━━━━━━━━━━━━━

💎 <b>Seu saldo: {credits} créditos</b>
🎁 <b>Buscas grátis: {free_searches}</b>

━━━━━━━━━━━━━━━━━━━━

<i>💡 Cada download custa 1 crédito!</i>
<i>🎁 Indique amigos e ganhe 10% dos depósitos deles!</i>"""

INSUFFICIENT_CREDITS = """⚠️ <b>SALDO INSUFICIENTE</b>

Você precisa de créditos para fazer buscas!

💰 Saldo atual: <code>{credits}</code> créditos
💳 Use /comprar para adicionar créditos

<i>💡 Cada download custa 1 crédito</i>"""

SEARCH_SUCCESS = """<b>=>
☑️  URL: <code>{url}</code>

🧵  LINHAS / ROWS: <code>{total:,}</code>

TEMPO: <code>{time:.2f}s</code>

💰 Saldo atual: <code>{credits}</code> créditos
🎁 Buscas grátis: <code>{free_searches}</code>
</b>"""
