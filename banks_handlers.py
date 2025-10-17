from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from telegram.error import BadRequest
import banks
import database as db
import config


async def bancos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bank categories"""
    categories = banks.get_all_categories()

    if not categories:
        await update.message.reply_text(
            "⚠️ Nenhuma categoria de bancos disponível no momento.",
            parse_mode='HTML'
        )
        return

    keyboard = []
    for category in categories:
        icon = category.get('icon', '🏦')
        button_text = f"{icon} {category['name']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'bank_cat_{category["id"]}')])

    keyboard.append([InlineKeyboardButton("❌ Fechar", callback_data='cancel')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = """🏦 <b>CATÁLOGO DE BANCOS</b>

Escolha uma categoria abaixo para ver os bancos disponíveis:

💡 <i>Cada solicitação de abertura de conta custa créditos</i>"""

    await update.message.reply_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def show_subcategories(query, category_id: str):
    """Show subcategories for a category"""
    category = banks.get_category_by_id(category_id)
    if not category:
        await query.message.edit_text("❌ Categoria não encontrada.")
        return

    subcategories = banks.get_subcategories_by_category(category_id)

    if not subcategories:
        await query.message.edit_text("⚠️ Nenhuma subcategoria disponível nesta categoria.")
        return

    keyboard = []
    for subcat in subcategories:
        icon = subcat.get('icon', '📍')
        button_text = f"{icon} {subcat['name']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'bank_subcat_{subcat["id"]}')])

    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data='bank_back_categories')])
    keyboard.append([InlineKeyboardButton("❌ Fechar", callback_data='cancel')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    icon = category.get('icon', '🏦')
    message = f"""<b>{icon} {category['name']}</b>

Escolha uma região/tipo:"""

    await query.message.edit_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def show_banks_list(query, subcategory_id: str):
    """Show list of banks in a subcategory"""
    subcategory = banks.get_subcategory_by_id(subcategory_id)
    if not subcategory:
        await query.message.edit_text("❌ Subcategoria não encontrada.")
        return

    bank_list = banks.get_banks_by_subcategory(subcategory_id)

    if not bank_list:
        await query.message.edit_text(
            f"⚠️ Nenhum banco disponível em <b>{subcategory['name']}</b> no momento.",
            parse_mode='HTML'
        )
        return

    if len(bank_list) > 0:
        await show_bank_carousel(query, bank_list, 0, subcategory_id)


async def show_bank_carousel(query, bank_list: list, index: int, subcategory_id: str):
    """Show bank with carousel navigation"""
    if index < 0:
        index = len(bank_list) - 1
    elif index >= len(bank_list):
        index = 0

    bank = bank_list[index]
    message = banks.format_bank_message(bank, index, len(bank_list))

    keyboard = []

    nav_buttons = []
    if len(bank_list) > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ Anterior", callback_data=f'bank_prev_{subcategory_id}_{index}'))
        nav_buttons.append(InlineKeyboardButton("▶️ Próximo", callback_data=f'bank_next_{subcategory_id}_{index}'))
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton(f"💳 Solicitar Abertura ({bank.get('credits_cost', 1)} créditos)", callback_data=f'bank_request_{bank["id"]}')])
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data=f'bank_subcat_{subcategory_id}')])
    keyboard.append([InlineKeyboardButton("❌ Fechar", callback_data='cancel')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if bank.get('screenshot_url') or bank.get('logo_url'):
        image_url = bank.get('screenshot_url') or bank.get('logo_url')
        try:
            if query.message.photo:
                await query.message.edit_media(
                    media=InputMediaPhoto(media=image_url, caption=message, parse_mode='HTML'),
                    reply_markup=reply_markup
                )
            else:
                await query.message.delete()
                await query.message.reply_photo(
                    photo=image_url,
                    caption=message,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
        except BadRequest:
            await query.message.edit_text(
                message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
    else:
        try:
            await query.message.edit_text(
                message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except BadRequest:
            pass


async def handle_bank_request(query, context, user_id: int, bank_id: str):
    """Handle bank account opening request"""
    user = db.get_user(user_id)
    if not user:
        await query.answer("❌ Usuário não encontrado. Use /start primeiro.", show_alert=True)
        return

    bank = banks.get_bank_by_id(bank_id)
    if not bank:
        await query.answer("❌ Banco não encontrado.", show_alert=True)
        return

    credits_needed = bank.get('credits_cost', 1)

    if user['credits'] < credits_needed:
        keyboard = [[InlineKeyboardButton("💳 Comprar Créditos", callback_data='buy_credits')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            f"""⚠️ <b>CRÉDITOS INSUFICIENTES</b>

Você precisa de <b>{credits_needed} créditos</b> para solicitar este banco.

💰 Saldo atual: <code>{user['credits']}</code> créditos

Use o botão abaixo para comprar créditos.""",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        return

    if db.deduct_credits(user_id, credits_needed):
        if banks.create_bank_request(user_id, bank_id, credits_needed):
            user = db.get_user(user_id)

            message = f"""✅ <b>SOLICITAÇÃO ENVIADA!</b>

🏦 <b>Banco:</b> {bank['name']}
{('🏢' if bank.get('account_type') == 'Empresa' else '👤')} <b>Tipo:</b> {bank.get('account_type', 'Pessoal')}
💰 <b>Valor:</b> €{float(bank.get('price', 0)):.2f}

💎 <b>Créditos utilizados:</b> {credits_needed}
💳 <b>Saldo restante:</b> {user['credits']} créditos

📋 Sua solicitação foi registrada e será processada em breve.
Você será notificado quando estiver pronta!

<i>Use /minhas_solicitacoes para ver todas as suas solicitações</i>"""

            await query.message.edit_text(message, parse_mode='HTML')

            try:
                admin_message = f"""🔔 <b>NOVA SOLICITAÇÃO DE BANCO</b>

👤 <b>Usuário:</b> {user['nome']} (<code>{user_id}</code>)
🏦 <b>Banco:</b> {bank['name']}
{('🏢' if bank.get('account_type') == 'Empresa' else '👤')} <b>Tipo:</b> {bank.get('account_type', 'Pessoal')}
💰 <b>Valor:</b> €{float(bank.get('price', 0)):.2f}
💎 <b>Créditos:</b> {credits_needed}"""

                await context.bot.send_message(
                    chat_id=config.ADMIN_ID,
                    text=admin_message,
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f"Error notifying admin: {e}")
        else:
            db.update_user_credits(user_id, credits_needed)
            await query.answer("❌ Erro ao criar solicitação. Créditos reembolsados.", show_alert=True)
    else:
        await query.answer("❌ Erro ao processar créditos.", show_alert=True)


async def minhas_solicitacoes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's bank requests"""
    user_id = update.message.from_user.id

    requests = banks.get_user_bank_requests(user_id, limit=10)

    if not requests:
        await update.message.reply_text(
            "📭 Você ainda não fez nenhuma solicitação de banco.",
            parse_mode='HTML'
        )
        return

    message = "📋 <b>MINHAS SOLICITAÇÕES DE BANCOS</b>\n\n"

    for req in requests:
        bank_name = req.get('banks', {}).get('name', 'Desconhecido') if isinstance(req.get('banks'), dict) else 'Desconhecido'
        status = req.get('status', 'pending')

        status_emoji = {
            'pending': '⏳',
            'processing': '🔄',
            'completed': '✅',
            'cancelled': '❌'
        }.get(status, '❓')

        status_text = {
            'pending': 'Pendente',
            'processing': 'Processando',
            'completed': 'Concluída',
            'cancelled': 'Cancelada'
        }.get(status, status)

        message += f"{status_emoji} <b>{bank_name}</b>\n"
        message += f"   Status: {status_text}\n"
        message += f"   💎 Créditos: {req.get('credits_used', 0)}\n"
        message += f"   📅 {req.get('created_at', '')[:10]}\n\n"

    await update.message.reply_text(message, parse_mode='HTML')


async def admin_bancos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel for bank management"""
    user_id = update.message.from_user.id

    if user_id != config.ADMIN_ID:
        await update.message.reply_text("❌ Acesso negado.")
        return

    stats = banks.get_bank_stats()

    keyboard = [
        [InlineKeyboardButton("➕ Adicionar Banco", callback_data='admin_add_bank')],
        [InlineKeyboardButton("✏️ Editar Banco", callback_data='admin_edit_bank')],
        [InlineKeyboardButton("📋 Ver Solicitações Pendentes", callback_data='admin_view_requests')],
        [InlineKeyboardButton("➕ Adicionar Subcategoria", callback_data='admin_add_subcat')],
        [InlineKeyboardButton("❌ Fechar", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = f"""⚙️ <b>PAINEL ADMIN - BANCOS</b>

📊 <b>Estatísticas:</b>
🏦 Categorias: {stats['total_categories']}
💳 Bancos ativos: {stats['total_banks']}
📋 Total de solicitações: {stats['total_requests']}
⏳ Solicitações pendentes: {stats['pending_requests']}

Escolha uma opção:"""

    await update.message.reply_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def admin_view_requests(query):
    """Show pending bank requests to admin"""
    requests = banks.get_all_bank_requests(status='pending', limit=20)

    if not requests:
        await query.message.edit_text("✅ Nenhuma solicitação pendente!")
        return

    message = "📋 <b>SOLICITAÇÕES PENDENTES</b>\n\n"

    for req in requests:
        bank_info = req.get('banks', {})
        bank_name = bank_info.get('name', 'Desconhecido') if isinstance(bank_info, dict) else 'Desconhecido'

        message += f"🔹 <b>{bank_name}</b>\n"
        message += f"   👤 User ID: <code>{req.get('user_id')}</code>\n"
        message += f"   💎 Créditos: {req.get('credits_used', 0)}\n"
        message += f"   📅 {req.get('created_at', '')[:10]}\n"
        message += f"   🆔 Request ID: <code>{req.get('id')}</code>\n\n"

    keyboard = [
        [InlineKeyboardButton("🔙 Voltar", callback_data='admin_bancos_back')],
        [InlineKeyboardButton("❌ Fechar", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)


async def handle_bank_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all bank-related callbacks"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id

    if data == 'bank_back_categories':
        categories = banks.get_all_categories()
        keyboard = []
        for category in categories:
            icon = category.get('icon', '🏦')
            button_text = f"{icon} {category['name']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f'bank_cat_{category["id"]}')])

        keyboard.append([InlineKeyboardButton("❌ Fechar", callback_data='cancel')])
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = """🏦 <b>CATÁLOGO DE BANCOS</b>

Escolha uma categoria abaixo:"""

        await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)
        return

    if data.startswith('bank_cat_'):
        category_id = data.replace('bank_cat_', '')
        await show_subcategories(query, category_id)
        return

    if data.startswith('bank_subcat_'):
        subcategory_id = data.replace('bank_subcat_', '')
        await show_banks_list(query, subcategory_id)
        return

    if data.startswith('bank_prev_') or data.startswith('bank_next_'):
        parts = data.split('_')
        direction = parts[1]
        subcategory_id = parts[2]
        current_index = int(parts[3])

        bank_list = banks.get_banks_by_subcategory(subcategory_id)

        if direction == 'prev':
            new_index = current_index - 1
        else:
            new_index = current_index + 1

        await show_bank_carousel(query, bank_list, new_index, subcategory_id)
        return

    if data.startswith('bank_request_'):
        bank_id = data.replace('bank_request_', '')
        await handle_bank_request(query, context, user_id, bank_id)
        return

    if data == 'admin_view_requests':
        await admin_view_requests(query)
        return

    if data == 'admin_bancos_back':
        await admin_bancos_command(update, context)
        return
