import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '1268314769'))

# API Configuration
API_KEY = os.getenv('API_KEY', 'WCjWLueQo596P03tFr8Q')
API_URL = os.getenv('API_URL', 'https://ulpcloud.site/url')

# NOWPayments Configuration
NOWPAYMENTS_API_KEY = os.getenv('NOWPAYMENTS_API_KEY', '')
NOWPAYMENTS_IPN_SECRET = os.getenv('NOWPAYMENTS_IPN_SECRET', '')
NOWPAYMENTS_API_URL = 'https://api.nowpayments.io/v1'

# Pricing Configuration (em USD)
PRICE_PER_SEARCH = float(os.getenv('PRICE_PER_SEARCH', '0.10'))  # $0.10 por busca
PACKAGE_PRICES = {
    '10': {'credits': 10, 'price': 1.00, 'bonus': 0},      # $1 = 10 buscas
    '50': {'credits': 50, 'price': 4.50, 'bonus': 5},      # $4.50 = 50 + 5 bônus
    '100': {'credits': 100, 'price': 8.00, 'bonus': 15},   # $8 = 100 + 15 bônus
    '500': {'credits': 500, 'price': 35.00, 'bonus': 100}, # $35 = 500 + 100 bônus
}

# Bot Settings
MIN_SEARCH_LENGTH = 3
MAX_URL_LENGTH = 55
FREE_SEARCHES_PER_USER = 3  # Buscas grátis para novos usuários

# Messages
WELCOME_MESSAGE = """👋 <b>Bem-vindo, {name}!</b>

🔍 <b>COMANDOS DISPONÍVEIS:</b>

🌐 <code>/url URL</code> - Buscar credenciais
🔗 <code>/ur URL</code> - Busca rápida
⚡ <code>/u URL</code> - Busca express
💰 <code>/saldo</code> - Ver seu saldo
💳 <code>/comprar</code> - Comprar créditos
📊 <code>/historico</code> - Ver histórico

💬 <b>Ou simplesmente envie a URL direto!</b>

━━━━━━━━━━━━━━━━━━━━
<b>🤖 BOTS ATIVOS:</b>

🔹 @ULP_Lookup_bot - Database permanente
🔹 @TUDOF_bot - Atualizado semanalmente

━━━━━━━━━━━━━━━━━━━━
💎 <b>Seu saldo: {credits} créditos</b>
🎁 <b>Buscas grátis restantes: {free_searches}</b>

<i>💡 Dica: Cada busca custa 1 crédito!</i>"""

INSUFFICIENT_CREDITS = """⚠️ <b>SALDO INSUFICIENTE</b>

Você precisa de créditos para fazer buscas!

💰 Saldo atual: <code>{credits}</code> créditos
💳 Use /comprar para adicionar créditos

🎁 Ou aguarde o reset mensal de buscas grátis!"""

SEARCH_SUCCESS = """<b>=>
☑️  URL: <code>{url}</code>

🧵  LINHAS / ROWS: <code>{total:,}</code>

TEMPO: <code>{time:.2f}s</code>

💰 Saldo restante: <code>{credits}</code> créditos
</b>"""
