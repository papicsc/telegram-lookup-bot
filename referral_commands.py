from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
import config
import database as db


async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show referral menu with user's code and stats"""
    query = update.callback_query if update.callback_query else None
    user_id = query.from_user.id if query else update.message.from_user.id

    # Check rate limit
    is_blocked, seconds = db.check_rate_limit(user_id)
    if is_blocked:
        minutes = seconds // 60
        text = f"⏰ Você está temporariamente bloqueado por {minutes} minutos. Aguarde."
        if query:
            await query.answer(text, show_alert=True)
        else:
            await update.message.reply_text(text)
        return

    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("❌ Usuário não encontrado. Use /start primeiro.")
        return

    stats = db.get_referral_stats(user_id)

    # Create referral link
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start={user['referral_code']}"

    message = f"""🎁 <b>SISTEMA DE INDICAÇÃO</b>

━━━━━━━━━━━━━━━━━━━━

👤 <b>SEU CÓDIGO:</b>
<code>{user['referral_code']}</code>

🔗 <b>SEU LINK:</b>
<code>{referral_link}</code>

━━━━━━━━━━━━━━━━━━━━

📊 <b>ESTATÍSTICAS</b>

👥 <b>Total de indicados:</b> {stats['total_referred']}
💰 <b>Total ganho:</b> {user['total_referral_earnings']} créditos

━━━━━━━━━━━━━━━━━━━━

💡 <b>COMO FUNCIONA?</b>

1️⃣ Compartilhe seu link ou código
2️⃣ Amigo se cadastra usando seu código
3️⃣ Quando ele depositar créditos, você ganha 10%
4️⃣ Exemplo: ele deposita 100 → você ganha 10

<i>💎 Ganhe créditos ilimitados indicando amigos!</i>"""

    keyboard = [
        [InlineKeyboardButton("👥 Ver Meus Indicados", callback_data='view_referred')],
        [InlineKeyboardButton("✏️ Personalizar Código", callback_data='customize_code')],
        [InlineKeyboardButton("🔙 Menu Principal", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)


async def view_referred(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of referred users"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # Check rate limit
    is_blocked, seconds = db.check_rate_limit(user_id)
    if is_blocked:
        minutes = seconds // 60
        await query.answer(f"⏰ Bloqueado por {minutes} minutos", show_alert=True)
        return

    stats = db.get_referral_stats(user_id)

    if stats['total_referred'] == 0:
        message = """📭 <b>NENHUM INDICADO AINDA</b>

Compartilhe seu link de indicação para começar a ganhar créditos!

Use /referral para ver seu link."""

        keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data='referral_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)
        return

    message = f"""👥 <b>MEUS INDICADOS</b>

━━━━━━━━━━━━━━━━━━━━

📊 <b>Total:</b> {stats['total_referred']} pessoas
💰 <b>Total ganho:</b> {stats['total_earned']} créditos

━━━━━━━━━━━━━━━━━━━━

<b>LISTA DE INDICADOS:</b>

"""

    for idx, referred in enumerate(stats['referred_users'][:10], 1):
        nome = referred['nome']
        username = f"@{referred['username']}" if referred.get('username') else 'Sem username'
        date = datetime.fromisoformat(referred['created_at']).strftime('%d/%m/%Y')
        message += f"{idx}. {nome} ({username})\n   📅 {date}\n\n"

    if stats['total_referred'] > 10:
        message += f"\n<i>... e mais {stats['total_referred'] - 10} indicados</i>"

    keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data='referral_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)


async def customize_code_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start code customization process"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # Check rate limit
    is_blocked, seconds = db.check_rate_limit(user_id)
    if is_blocked:
        minutes = seconds // 60
        await query.answer(f"⏰ Bloqueado por {minutes} minutos", show_alert=True)
        return

    user = db.get_user(user_id)

    message = f"""✏️ <b>PERSONALIZAR CÓDIGO</b>

━━━━━━━━━━━━━━━━━━━━

<b>Código atual:</b> <code>{user['referral_code']}</code>

━━━━━━━━━━━━━━━━━━━━

Para personalizar seu código, envie o novo código desejado.

<b>Regras:</b>
• Apenas letras e números
• Mínimo 4 caracteres
• Máximo 15 caracteres
• Código único (não pode estar em uso)

<i>Envie o novo código ou clique em Cancelar</i>"""

    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data='referral_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)

    # Set state for conversation
    context.user_data['awaiting_referral_code'] = True


async def process_custom_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process custom referral code from user"""
    if not context.user_data.get('awaiting_referral_code'):
        return

    user_id = update.message.from_user.id
    new_code = update.message.text.strip().upper()

    # Check rate limit
    is_blocked, seconds = db.check_rate_limit(user_id)
    if is_blocked:
        minutes = seconds // 60
        await update.message.reply_text(f"⏰ Você está temporariamente bloqueado por {minutes} minutos.")
        return

    # Validate code
    if not new_code.isalnum():
        await update.message.reply_text("❌ Código inválido! Use apenas letras e números.")
        return

    if len(new_code) < 4 or len(new_code) > 15:
        await update.message.reply_text("❌ Código deve ter entre 4 e 15 caracteres.")
        return

    # Try to update
    success = db.update_referral_code(user_id, new_code)

    if success:
        bot_username = context.bot.username
        referral_link = f"https://t.me/{bot_username}?start={new_code}"

        message = f"""✅ <b>CÓDIGO ATUALIZADO!</b>

<b>Novo código:</b> <code>{new_code}</code>

<b>Novo link:</b>
<code>{referral_link}</code>

Use /referral para ver seu painel de indicações."""

        await update.message.reply_text(message, parse_mode='HTML')
    else:
        await update.message.reply_text("❌ Este código já está em uso. Escolha outro.")

    # Clear state
    context.user_data['awaiting_referral_code'] = False
