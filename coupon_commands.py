from telegram import Update
from telegram.ext import ContextTypes
import database as db


async def use_coupon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cupom command"""
    user_id = update.message.from_user.id

    # Check rate limit
    is_blocked, seconds = db.check_rate_limit(user_id)
    if is_blocked:
        minutes = seconds // 60
        await update.message.reply_text(
            f"⏰ Você está temporariamente bloqueado por {minutes} minutos.\n\n"
            "Aguarde para usar comandos novamente."
        )
        return

    # Check if user is banned
    user = db.get_user(user_id)
    if user and user['is_banned']:
        await update.message.reply_text("🚫 Sua conta está suspensa. Entre em contato com o suporte.")
        return

    # Check if code was provided
    if not context.args:
        await update.message.reply_text(
            "🎟️ <b>USAR CUPOM</b>\n\n"
            "Para usar um cupom, envie:\n"
            "<code>/cupom CODIGO</code>\n\n"
            "<b>Exemplo:</b>\n"
            "<code>/cupom PROMO100</code>",
            parse_mode='HTML'
        )
        return

    code = context.args[0].strip().upper()

    # Get user IP (try to get from update)
    ip_address = "unknown"
    try:
        # Telegram doesn't provide IP directly, use user_id as identifier
        ip_address = f"telegram_{user_id}"
    except:
        pass

    # Try to use coupon
    success, message = db.use_coupon(user_id, code, ip_address)

    if success:
        user = db.get_user(user_id)
        await update.message.reply_text(
            f"✅ <b>{message}</b>\n\n"
            f"💎 <b>Saldo atual:</b> {user['credits']} créditos\n"
            f"🎁 <b>Buscas grátis:</b> {user['free_searches']}",
            parse_mode='HTML'
        )

        # Log for admin
        db.log_activity(user_id, 'coupon_redeemed', {'code': code, 'success': True})
    else:
        await update.message.reply_text(f"❌ {message}")
        db.log_activity(user_id, 'coupon_attempt_failed', {'code': code, 'reason': message})
