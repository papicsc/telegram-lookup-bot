from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import config
import database as db


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id == config.ADMIN_ID


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main admin panel"""
    query = update.callback_query if update.callback_query else None
    user_id = query.from_user.id if query else update.message.from_user.id

    if not is_admin(user_id):
        text = "❌ Acesso negado."
        if query:
            await query.answer(text, show_alert=True)
        else:
            await update.message.reply_text(text)
        return

    stats = db.get_stats()

    message = f"""👑 <b>PAINEL ADMINISTRATIVO</b>

━━━━━━━━━━━━━━━━━━━━

📊 <b>ESTATÍSTICAS GERAIS</b>

👥 <b>Total de usuários:</b> {stats['total_users']}
🔍 <b>Total de buscas:</b> {stats['total_searches']}
📅 <b>Buscas hoje:</b> {stats['today_searches']}

💰 <b>Transações:</b> {stats['total_transactions']}
💵 <b>Receita total:</b> €{stats['total_revenue']:.2f}

━━━━━━━━━━━━━━━━━━━━

⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"""

    keyboard = [
        [
            InlineKeyboardButton("👤 Buscar Usuário", callback_data='admin_search_user'),
            InlineKeyboardButton("👥 Top Usuários", callback_data='admin_top_users')
        ],
        [
            InlineKeyboardButton("🎟️ Gerenciar Cupons", callback_data='admin_coupons'),
            InlineKeyboardButton("💳 Ver Pagamentos", callback_data='admin_payments')
        ],
        [
            InlineKeyboardButton("📊 Ver Logs", callback_data='admin_logs'),
            InlineKeyboardButton("🚫 Usuários Bloqueados", callback_data='admin_blocked_users')
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data='admin_broadcast')
        ],
        [InlineKeyboardButton("❌ Fechar", callback_data='admin_close')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)


async def admin_search_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start user search"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.answer("❌ Acesso negado", show_alert=True)
        return

    message = """🔍 <b>BUSCAR USUÁRIO</b>

━━━━━━━━━━━━━━━━━━━━

Envie o <b>ID do Telegram</b> do usuário que deseja buscar.

<i>Exemplo: 123456789</i>"""

    keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data='admin_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)

    context.user_data['awaiting_user_id'] = True


async def admin_process_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process user ID search"""
    if not context.user_data.get('awaiting_user_id'):
        return

    admin_id = update.message.from_user.id
    if not is_admin(admin_id):
        return

    try:
        search_user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ ID inválido. Envie apenas números.")
        return

    user = db.get_user(search_user_id)

    if not user:
        await update.message.reply_text("❌ Usuário não encontrado.")
        context.user_data['awaiting_user_id'] = False
        return

    referral_stats = db.get_referral_stats(search_user_id)
    referred_by_name = "Ninguém"
    if user['referred_by']:
        referrer = db.get_user(user['referred_by'])
        if referrer:
            referred_by_name = f"{referrer['nome']} (ID: {referrer['id']})"

    message = f"""👤 <b>PERFIL DO USUÁRIO</b>

━━━━━━━━━━━━━━━━━━━━

<b>Nome:</b> {user['nome']}
<b>Username:</b> @{user['username'] if user.get('username') else 'N/A'}
<b>ID:</b> <code>{user['id']}</code>

━━━━━━━━━━━━━━━━━━━━

💎 <b>Créditos:</b> {user['credits']}
🎁 <b>Buscas grátis:</b> {user['free_searches']}
📊 <b>Total de buscas:</b> {user['total_searches']}

━━━━━━━━━━━━━━━━━━━━

🎁 <b>REFERRAL</b>

<b>Código:</b> <code>{user['referral_code']}</code>
<b>Indicado por:</b> {referred_by_name}
<b>Total indicados:</b> {referral_stats['total_referred']}
<b>Ganhos com referral:</b> {user['total_referral_earnings']} créditos

━━━━━━━━━━━━━━━━━━━━

{'🚫 <b>BANIDO</b>' if user['is_banned'] else '✅ <b>ATIVO</b>'}
{'👑 <b>PREMIUM</b>' if user['is_premium'] else ''}

<b>Cadastro:</b> {datetime.fromisoformat(user['created_at']).strftime('%d/%m/%Y %H:%M')}"""

    context.user_data['selected_user_id'] = search_user_id

    keyboard = [
        [
            InlineKeyboardButton("➕ Adicionar Créditos", callback_data='admin_add_credits'),
            InlineKeyboardButton("➖ Remover Créditos", callback_data='admin_remove_credits')
        ],
        [
            InlineKeyboardButton("🎁 Ajustar Buscas Grátis", callback_data='admin_adjust_free_searches')
        ],
        [
            InlineKeyboardButton("🚫 Banir" if not user['is_banned'] else "✅ Desbanir",
                               callback_data='admin_toggle_ban')
        ],
        [InlineKeyboardButton("🔙 Voltar", callback_data='admin_panel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)

    context.user_data['awaiting_user_id'] = False


async def admin_add_credits_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding credits"""
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if not is_admin(admin_id):
        await query.answer("❌ Acesso negado", show_alert=True)
        return

    selected_user_id = context.user_data.get('selected_user_id')
    if not selected_user_id:
        await query.answer("❌ Nenhum usuário selecionado", show_alert=True)
        return

    message = """➕ <b>ADICIONAR CRÉDITOS</b>

━━━━━━━━━━━━━━━━━━━━

Envie a quantidade de créditos a adicionar.

<i>Exemplo: 100</i>"""

    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data='admin_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)

    context.user_data['awaiting_credits_amount'] = 'add'


async def admin_remove_credits_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start removing credits"""
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if not is_admin(admin_id):
        await query.answer("❌ Acesso negado", show_alert=True)
        return

    selected_user_id = context.user_data.get('selected_user_id')
    if not selected_user_id:
        await query.answer("❌ Nenhum usuário selecionado", show_alert=True)
        return

    message = """➖ <b>REMOVER CRÉDITOS</b>

━━━━━━━━━━━━━━━━━━━━

Envie a quantidade de créditos a remover (número positivo).

<i>Exemplo: 50</i>"""

    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data='admin_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)

    context.user_data['awaiting_credits_amount'] = 'remove'


async def admin_process_credits_adjustment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process credits adjustment"""
    if not context.user_data.get('awaiting_credits_amount'):
        return

    admin_id = update.message.from_user.id
    if not is_admin(admin_id):
        return

    selected_user_id = context.user_data.get('selected_user_id')
    action = context.user_data.get('awaiting_credits_amount')

    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("❌ Quantidade deve ser maior que zero.")
            return
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Envie apenas números.")
        return

    if action == 'remove':
        amount = -amount

    success = db.admin_adjust_credits(selected_user_id, amount, admin_id, "Ajuste manual pelo admin")

    if success:
        user = db.get_user(selected_user_id)
        await update.message.reply_text(
            f"✅ Créditos {'adicionados' if amount > 0 else 'removidos'} com sucesso!\n\n"
            f"<b>Novo saldo:</b> {user['credits']} créditos",
            parse_mode='HTML'
        )

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=selected_user_id,
                text=f"{'💎 Você recebeu' if amount > 0 else '⚠️ Foram removidos'} <b>{abs(amount)} créditos</b> da sua conta.\n\n"
                     f"<b>Saldo atual:</b> {user['credits']} créditos",
                parse_mode='HTML'
            )
        except:
            pass
    else:
        await update.message.reply_text("❌ Erro ao ajustar créditos.")

    context.user_data['awaiting_credits_amount'] = None


async def admin_toggle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban/unban user"""
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if not is_admin(admin_id):
        await query.answer("❌ Acesso negado", show_alert=True)
        return

    selected_user_id = context.user_data.get('selected_user_id')
    if not selected_user_id:
        await query.answer("❌ Nenhum usuário selecionado", show_alert=True)
        return

    user = db.get_user(selected_user_id)

    if user['is_banned']:
        success = db.unban_user(selected_user_id, admin_id)
        action = "desbanido"
    else:
        success = db.ban_user(selected_user_id, admin_id, "Banimento manual pelo admin")
        action = "banido"

    if success:
        await query.answer(f"✅ Usuário {action} com sucesso!", show_alert=True)

        # Notify user
        try:
            if user['is_banned']:
                await context.bot.send_message(
                    chat_id=selected_user_id,
                    text="✅ Sua conta foi reativada! Você pode usar o bot novamente."
                )
            else:
                await context.bot.send_message(
                    chat_id=selected_user_id,
                    text="🚫 Sua conta foi suspensa. Entre em contato com o suporte."
                )
        except:
            pass

        # Refresh user info
        await admin_process_user_search(update, context)
    else:
        await query.answer("❌ Erro ao processar ação", show_alert=True)


async def admin_coupons_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show coupons management menu"""
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if not is_admin(admin_id):
        await query.answer("❌ Acesso negado", show_alert=True)
        return

    coupons = db.get_all_coupons()

    message = f"""🎟️ <b>GERENCIAR CUPONS</b>

━━━━━━━━━━━━━━━━━━━━

<b>Total de cupons:</b> {len(coupons)}
<b>Ativos:</b> {sum(1 for c in coupons if c['is_active'])}

━━━━━━━━━━━━━━━━━━━━

<b>ÚLTIMOS CUPONS:</b>

"""

    for coupon in coupons[:5]:
        status = "✅" if coupon['is_active'] else "❌"
        type_emoji = "💎" if coupon['type'] == 'credits' else "🎁"
        usage = f"{coupon['current_uses']}/{coupon['max_uses'] if coupon['max_uses'] > 0 else '∞'}"

        message += f"{status} {type_emoji} <code>{coupon['code']}</code>\n"
        message += f"   Valor: {coupon['value']} | Usos: {usage}\n\n"

    keyboard = [
        [InlineKeyboardButton("➕ Criar Cupom", callback_data='admin_create_coupon')],
        [InlineKeyboardButton("📋 Ver Todos os Cupons", callback_data='admin_view_all_coupons')],
        [InlineKeyboardButton("🔙 Voltar", callback_data='admin_panel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)


async def admin_create_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start coupon creation"""
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if not is_admin(admin_id):
        await query.answer("❌ Acesso negado", show_alert=True)
        return

    message = """➕ <b>CRIAR CUPOM</b>

━━━━━━━━━━━━━━━━━━━━

Envie os dados do cupom no formato:

<code>CODIGO|TIPO|VALOR|MAX_USOS|DIAS_VALIDADE</code>

<b>TIPO:</b> credits ou free_searches
<b>MAX_USOS:</b> 0 = ilimitado
<b>DIAS_VALIDADE:</b> 0 = sem expiração

<b>Exemplo:</b>
<code>PROMO100|credits|100|50|30</code>

Isso cria um cupom de 100 créditos, máximo 50 usos, válido por 30 dias."""

    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data='admin_coupons')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)

    context.user_data['awaiting_coupon_data'] = True


async def admin_process_coupon_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process coupon creation"""
    if not context.user_data.get('awaiting_coupon_data'):
        return

    admin_id = update.message.from_user.id
    if not is_admin(admin_id):
        return

    try:
        parts = update.message.text.strip().split('|')
        if len(parts) != 5:
            await update.message.reply_text("❌ Formato inválido. Use: CODIGO|TIPO|VALOR|MAX_USOS|DIAS_VALIDADE")
            return

        code, coupon_type, value, max_uses, days = parts

        if coupon_type not in ['credits', 'free_searches']:
            await update.message.reply_text("❌ Tipo inválido. Use 'credits' ou 'free_searches'")
            return

        value = int(value)
        max_uses = int(max_uses)
        days = int(days)

        if value <= 0:
            await update.message.reply_text("❌ Valor deve ser maior que zero")
            return

        expires_at = None
        if days > 0:
            expires_at = datetime.now() + timedelta(days=days)

        success = db.create_coupon(code, coupon_type, value, max_uses, expires_at, admin_id)

        if success:
            await update.message.reply_text(
                f"✅ <b>Cupom criado com sucesso!</b>\n\n"
                f"<b>Código:</b> <code>{code.upper()}</code>\n"
                f"<b>Tipo:</b> {coupon_type}\n"
                f"<b>Valor:</b> {value}\n"
                f"<b>Max usos:</b> {max_uses if max_uses > 0 else 'Ilimitado'}\n"
                f"<b>Validade:</b> {expires_at.strftime('%d/%m/%Y') if expires_at else 'Sem expiração'}",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Erro ao criar cupom. Código pode já existir.")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")

    context.user_data['awaiting_coupon_data'] = False


async def admin_blocked_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show blocked users"""
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if not is_admin(admin_id):
        await query.answer("❌ Acesso negado", show_alert=True)
        return

    blocked = db.get_blocked_users()

    if not blocked:
        message = "✅ Nenhum usuário bloqueado no momento."
    else:
        message = f"""🚫 <b>USUÁRIOS BLOQUEADOS</b>

━━━━━━━━━━━━━━━━━━━━

<b>Total:</b> {len(blocked)}

"""
        for item in blocked:
            user = db.get_user(item['user_id'])
            if user:
                blocked_until = datetime.fromisoformat(item['blocked_until'])
                remaining = int((blocked_until - datetime.now()).total_seconds() / 60)
                message += f"👤 {user['nome']} (ID: {user['id']})\n"
                message += f"   ⏰ Libera em: {remaining} minutos\n\n"

    keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data='admin_panel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)


async def admin_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close admin panel"""
    query = update.callback_query
    await query.answer()

    await query.message.delete()
