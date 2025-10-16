from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import requests
import os
import re
import time
from io import BytesIO
from datetime import datetime, timedelta
import config
import database as db
import payments
import referral_commands
import admin_commands
import coupon_commands

# Initialize database
db.init_database()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = update.message if update.message else update.edited_message

    user_id = info.from_user.id
    username = str(info.from_user.username or info.from_user.name)
    fname = info.from_user.first_name
    chat_type = info.chat.type

    # Check rate limit
    is_blocked, seconds = db.check_rate_limit(user_id)
    if is_blocked:
        minutes = seconds // 60
        await update.message.reply_text(
            f"⏰ Você está temporariamente bloqueado por {minutes} minutos.\n\n"
            "Aguarde para usar comandos novamente."
        )
        return

    # Check for referral code in start parameter
    referred_by_code = None
    if context.args:
        referred_by_code = context.args[0].strip().upper()

    # Add user to database
    if chat_type == 'private':
        db.add_user(user_id, fname, username, referred_by_code)

    # Get user info
    user = db.get_user(user_id)

    # Check if banned
    if user and user['is_banned']:
        await update.message.reply_text("🚫 Sua conta está suspensa. Entre em contato com o suporte.")
        return

    credits = user['credits'] if user else 0
    free_searches = user['free_searches'] if user else 0

    keyboard = [
        [
            InlineKeyboardButton("💰 Comprar Créditos", callback_data='buy_credits'),
            InlineKeyboardButton("📊 Meu Saldo", callback_data='my_balance')
        ],
        [
            InlineKeyboardButton("🎁 Indicar Amigos", callback_data='referral_menu')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = config.WELCOME_MESSAGE.format(
        name=fname,
        credits=credits,
        free_searches=free_searches
    )

    await update.message.reply_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup,
        reply_to_message_id=info.message_id
    )


async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user balance"""
    info = update.message if update.message else update.edited_message
    user_id = info.from_user.id

    # Check rate limit
    is_blocked, seconds = db.check_rate_limit(user_id)
    if is_blocked:
        minutes = seconds // 60
        await update.message.reply_text(f"⏰ Bloqueado por {minutes} minutos.")
        return

    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("❌ Usuário não encontrado. Use /start primeiro.")
        return

    if user['is_banned']:
        await update.message.reply_text("🚫 Sua conta está suspensa.")
        return

    referral_stats = db.get_referral_stats(user_id)

    keyboard = [
        [InlineKeyboardButton("💳 Comprar Créditos", callback_data='buy_credits')],
        [InlineKeyboardButton("📊 Ver Histórico", callback_data='view_history')],
        [InlineKeyboardButton("🎁 Sistema de Indicação", callback_data='referral_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = f"""💰 <b>SEU SALDO</b>

━━━━━━━━━━━━━━━━━━━━

👤 <b>Nome:</b> {user['nome']}
🆔 <b>ID:</b> <code>{user['id']}</code>

━━━━━━━━━━━━━━━━━━━━

💎 <b>Créditos:</b> <code>{user['credits']}</code>
🎁 <b>Buscas grátis:</b> <code>{user['free_searches']}</code>
📊 <b>Total de buscas:</b> <code>{user['total_searches']}</code>

━━━━━━━━━━━━━━━━━━━━

🎁 <b>SISTEMA DE INDICAÇÃO</b>

👥 <b>Indicados:</b> {referral_stats['total_referred']}
💰 <b>Ganhos:</b> {user['total_referral_earnings']} créditos

━━━━━━━━━━━━━━━━━━━━

{'👑 <b>Status:</b> PREMIUM' if user['is_premium'] else ''}

<i>💡 Cada download custa 1 crédito</i>"""

    await update.message.reply_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show credit packages"""
    keyboard = []

    for pkg_id, pkg_data in config.PACKAGE_PRICES.items():
        total_credits = pkg_data['credits'] + pkg_data['bonus']
        bonus_text = f" +{pkg_data['bonus']} BÔNUS" if pkg_data['bonus'] > 0 else ""

        button_text = f"💎 {total_credits} créditos - ${pkg_data['price']:.2f}{bonus_text}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'package_{pkg_id}')])

    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data='cancel')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = """💳 <b>PACOTES DE CRÉDITOS</b>

Escolha um pacote abaixo:

💰 <b>Formas de pagamento:</b>
• Bitcoin (BTC)
• Ethereum (ETH)
• Litecoin (LTC)
• USDT (TRC20/ERC20)
• E muitas outras cryptos!

🎁 <b>Quanto mais compra, mais bônus você ganha!</b>

<i>💡 Pagamentos processados via NOWPayments.io</i>"""

    if update.callback_query:
        await update.callback_query.message.edit_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )


async def historico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user search history"""
    info = update.message if update.message else update.edited_message
    user_id = info.from_user.id

    history = db.get_user_history(user_id, limit=10)

    if not history:
        await update.message.reply_text("📭 Você ainda não fez nenhuma busca.")
        return

    message = "📊 <b>SEU HISTÓRICO DE BUSCAS</b>\n\n"

    for item in history:
        free_tag = "🎁 GRÁTIS" if item['is_free'] else f"💎 {item['credits_used']} crédito(s)"
        timestamp = datetime.fromisoformat(item['timestamp']).strftime("%d/%m/%Y %H:%M")

        message += f"🔹 <code>{item['url']}</code>\n"
        message += f"   📅 {timestamp} | {free_tag}\n"
        message += f"   📊 {item['lines']:,} linhas\n\n"

    await update.message.reply_text(message, parse_mode='HTML')


async def tudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main search handler"""
    info = update.message if update.message else update.edited_message

    user_id = info.from_user.id
    username = str(info.from_user.username or info.from_user.name)
    fname = info.from_user.first_name
    chat_id = info.chat.id
    message_id = info.message_id
    chat_type = info.chat.type

    # Add user if not exists
    db.add_user(user_id, fname, username)

    # Check if in group without command
    if chat_type != 'private':
        if not re.match(r'/url|/ur|/u|^www\.|^https?://', info.text.lower()):
            return

    # Extract URL
    url = info.text.lower()
    url = re.sub(r'/url|/ur|/u|https?://|www\.', '', url).strip()
    url = re.sub(r'^www\.|^login\.', '', url).strip()
    url = re.sub(r':.*', '', url).strip()

    # Validate URL length
    if len(url) < config.MIN_SEARCH_LENGTH:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>⚠️ Mínimo de {config.MIN_SEARCH_LENGTH} caracteres!</b>",
            parse_mode='HTML',
            reply_to_message_id=message_id
        )
        return

    if url.count('/') > 0:
        url = url.split('/')[0]

    if len(url) > config.MAX_URL_LENGTH:
        url = url[:config.MAX_URL_LENGTH]

    # Check user credits
    user = db.get_user(user_id)
    has_free = user['free_searches'] > 0
    has_credits = user['credits'] > 0

    if not has_free and not has_credits:
        keyboard = [[InlineKeyboardButton("💳 Comprar Créditos", callback_data='buy_credits')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = config.INSUFFICIENT_CREDITS.format(credits=user['credits'])

        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='HTML',
            reply_to_message_id=message_id,
            reply_markup=reply_markup
        )
        return

    # Process search
    anome = re.sub(r'\s+', ' ', url)
    prov = ''

    if len(anome.split(' ')) > 1:
        anome = ' '.join(anome.split(' ')[:2])
        anome, prov = anome.split(' ')
        if '@' not in prov:
            anome = f'{anome}_@{prov}'

    if '_' not in anome:
        anome = f'{anome}_{prov}-'

    # Create files directory
    os.makedirs('files', exist_ok=True)

    # Check cache
    ap = [ap for ap in os.listdir('files') if anome in ap]

    dois = [
        [InlineKeyboardButton("LOGIN:SENHA", callback_data='LOGIN')],
        [InlineKeyboardButton("URL:LOGIN:SENHA", callback_data='URL')],
        [InlineKeyboardButton(" DELETA 🚮", callback_data='delete')]
    ]
    doist = InlineKeyboardMarkup(dois)

    now = time.time()

    if len(ap) > 0 and len(ap) < 2:
        # Found in cache
        total = int(re.sub(r'\D', '', ap[0].split('_')[1]))

        # Don't deduct credits yet - only when user downloads
        user = db.get_user(user_id)

        message = config.SEARCH_SUCCESS.format(
            url=url,
            total=total,
            time=time.time() - now,
            credits=user['credits'],
            free_searches=user['free_searches']
        )

        message += f"\n\n⚠️ <i>Crédito será descontado apenas ao fazer o download</i>"
        message += f"\nFIXO: {ap[0]} | {message_id}"

        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='HTML',
            reply_to_message_id=message_id,
            reply_markup=doist
        )
        return

    # Search in API
    try:
        api_url = f"{config.API_URL}?k={config.API_KEY}&q={url}&t=1"
        headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0'}

        r = requests.get(api_url, timeout=15, headers=headers)

        if r.status_code == 200:
            try:
                nome = r.headers['Content-Disposition'].split('filename=')[1].replace('"', '')
            except:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"<b>🔎 URL: <code>{url}</code>\n\n⚠️ NÃO ENCONTRADO\n❌ SEARCH NOT FOUND</b>",
                    parse_mode='HTML',
                    reply_to_message_id=message_id
                )
                return

            total = int(re.sub(r'\D', '', nome.split('_')[1]))

            # Save to cache
            with open(f'files/{nome}', 'w', encoding='utf-8') as f:
                f.write(r.text)

            # Don't deduct credits yet - only when user downloads
            user = db.get_user(user_id)

            message = config.SEARCH_SUCCESS.format(
                url=url,
                total=total,
                time=time.time() - now,
                credits=user['credits'],
                free_searches=user['free_searches']
            )

            message += f"\n\n⚠️ <i>Crédito será descontado apenas ao fazer o download</i>"
            message += f"\nFIXO: {nome} | {message_id}"

            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='HTML',
                reply_to_message_id=message_id,
                reply_markup=doist
            )

        elif r.status_code == 404:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"<b>🔎 URL: <code>{url}</code>\n\n⚠️ NÃO ENCONTRADO\n❌ SEARCH NOT FOUND</b>",
                parse_mode='HTML',
                reply_to_message_id=message_id
            )

    except Exception as e:
        print(f'Error in search: {e}')
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>⚠️ ERRO / ERROR\n\n{str(e)}</b>",
            parse_mode='HTML',
            reply_to_message_id=message_id
        )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Show bot statistics"""
    user_id = update.message.from_user.id

    if user_id != config.ADMIN_ID:
        await update.message.reply_text("❌ Acesso negado.")
        return

    stats = db.get_stats()

    message = f"""📊 <b>ESTATÍSTICAS DO BOT</b>

👥 <b>Total de usuários:</b> {stats['total_users']}
🔍 <b>Total de buscas:</b> {stats['total_searches']}
📅 <b>Buscas hoje:</b> {stats['today_searches']}

💰 <b>Transações completadas:</b> {stats['total_transactions']}
💵 <b>Receita total:</b> ${stats['total_revenue']:.2f}

⏰ <b>Atualizado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"""

    await update.message.reply_text(message, parse_mode='HTML')


async def Botoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Check rate limit (except for admin)
    if user_id != config.ADMIN_ID:
        is_blocked, seconds = db.check_rate_limit(user_id)
        if is_blocked:
            minutes = seconds // 60
            await query.answer(f"⏰ Bloqueado por {minutes} minutos", show_alert=True)
            return

    # Check if banned
    user = db.get_user(user_id)
    if user and user['is_banned'] and user_id != config.ADMIN_ID:
        await query.answer("🚫 Conta suspensa", show_alert=True)
        return

    # Referral system callbacks
    if data == 'referral_menu':
        await referral_commands.referral_menu(update, context)
        return

    if data == 'view_referred':
        await referral_commands.view_referred(update, context)
        return

    if data == 'customize_code':
        await referral_commands.customize_code_start(update, context)
        return

    if data == 'back_to_main':
        await start(update, context)
        return

    # Admin callbacks
    if data == 'admin_panel':
        await admin_commands.admin_panel(update, context)
        return

    if data == 'admin_search_user':
        await admin_commands.admin_search_user_start(update, context)
        return

    if data == 'admin_add_credits':
        await admin_commands.admin_add_credits_start(update, context)
        return

    if data == 'admin_remove_credits':
        await admin_commands.admin_remove_credits_start(update, context)
        return

    if data == 'admin_toggle_ban':
        await admin_commands.admin_toggle_ban(update, context)
        return

    if data == 'admin_coupons':
        await admin_commands.admin_coupons_menu(update, context)
        return

    if data == 'admin_create_coupon':
        await admin_commands.admin_create_coupon_start(update, context)
        return

    if data == 'admin_blocked_users':
        await admin_commands.admin_blocked_users(update, context)
        return

    if data == 'admin_close':
        await admin_commands.admin_close(update, context)
        return

    # Buy credits menu
    if data == 'buy_credits':
        await comprar(update, context)
        return

    # Show balance
    if data == 'my_balance':
        user = db.get_user(user_id)
        if not user:
            await query.message.edit_text("❌ Usuário não encontrado. Use /start primeiro.")
            return

        keyboard = [
            [InlineKeyboardButton("💳 Comprar Créditos", callback_data='buy_credits')],
            [InlineKeyboardButton("🔙 Voltar", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = f"""💰 <b>SEU SALDO</b>

💎 <b>Créditos:</b> <code>{user['credits']}</code>
🎁 <b>Buscas grátis:</b> <code>{user['free_searches']}</code>
📊 <b>Total de buscas:</b> <code>{user['total_searches']}</code>"""

        await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)
        return

    # View history
    if data == 'view_history':
        history = db.get_user_history(user_id, limit=5)

        if not history:
            await query.message.edit_text("📭 Você ainda não fez nenhuma busca.")
            return

        message = "📊 <b>ÚLTIMAS BUSCAS</b>\n\n"

        for item in history:
            free_tag = "🎁" if item['is_free'] else "💎"
            timestamp = datetime.fromisoformat(item['timestamp']).strftime("%d/%m %H:%M")
            message += f"{free_tag} <code>{item['url']}</code> - {timestamp}\n"

        keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data='my_balance')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)
        return

    # Package selection
    if data.startswith('package_'):
        pkg_id = data.replace('package_', '')

        if pkg_id not in config.PACKAGE_PRICES:
            await query.message.edit_text("❌ Pacote inválido.")
            return

        # Check if user has pending payment
        pending_payment = db.get_pending_payment(user_id)
        if pending_payment:
            keyboard = [
                [InlineKeyboardButton("💳 Pagar Pedido Pendente", url=pending_payment['invoice_url'])],
                [InlineKeyboardButton("🔄 Verificar Pagamento", callback_data=f'check_payment_{pending_payment["payment_id"]}')],
                [InlineKeyboardButton("🔙 Voltar", callback_data='buy_credits')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.edit_text(
                f"""⚠️ <b>PAGAMENTO PENDENTE</b>

Você já tem um pagamento em andamento:

📦 <b>Pacote:</b> {pending_payment['credits']} créditos
💰 <b>Valor:</b> €{pending_payment['amount']:.2f} EUR
🔐 <b>ID:</b> <code>{pending_payment['payment_id']}</code>

<b>Complete este pagamento primeiro ou aguarde expirar (1 hora)</b>

Use "🔄 Verificar Pagamento" após pagar.""",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            return

        package = config.PACKAGE_PRICES[pkg_id]
        total_credits = package['credits'] + package['bonus']

        # Create payment via NOWPayments API
        try:
            print(f"[DEBUG] Creating payment for user {user_id}, package {pkg_id}")
            payment = payments.create_payment_for_package(user_id, pkg_id)
            print(f"[DEBUG] Payment result: {payment}")
        except Exception as e:
            print(f"[ERROR] Error creating payment: {e}")
            import traceback
            traceback.print_exc()
            payment = None

        if not payment:
            error_msg = f"""❌ <b>ERRO AO CRIAR PAGAMENTO</b>

Possíveis causas:
• API key do NOWPayments inválida
• Problema de conexão com NOWPayments
• Configuração incorreta

<b>Detalhes técnicos:</b>
API Key configurada: {'✅ Sim' if config.NOWPAYMENTS_API_KEY else '❌ Não'}

Entre em contato com o administrador."""

            await query.message.edit_text(
                error_msg,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data='buy_credits')]])
            )
            return

        # Get invoice URL from payment response (NOWPayments returns it directly)
        invoice_url = payment.get('invoice_url') or payments.get_payment_link(payment.get('id'))

        # Save payment to database
        db.add_payment(
            user_id,
            payment['id'],
            float(payment['price_amount']),
            str(payment['price_currency']).upper(),
            total_credits,
            payment.get('id'),
            invoice_url
        )

        keyboard = [
            [InlineKeyboardButton("💳 Pagar Agora", url=invoice_url)],
            [InlineKeyboardButton("🔄 Verificar Pagamento", callback_data=f'check_payment_{payment["id"]}')],
            [InlineKeyboardButton("🔙 Voltar", callback_data='buy_credits')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = f"""💳 <b>PAGAMENTO CRIADO</b>

📦 <b>Pacote:</b> {total_credits} créditos
💰 <b>Valor:</b> €{float(payment['price_amount']):.2f} EUR

🔐 <b>ID do Pagamento:</b>
<code>{payment['id']}</code>

<b>Instruções:</b>
1. Clique em "💳 Pagar Agora"
2. Escolha sua criptomoeda preferida
3. Envie o pagamento
4. Clique em "🔄 Verificar Pagamento" após pagar
5. Seus créditos serão adicionados automaticamente!

⏰ <i>Pagamento válido por 1 hora</i>"""

        await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)
        return

    # Check payment status
    if data.startswith('check_payment_'):
        invoice_id = data.replace('check_payment_', '')

        try:
            print(f"[DEBUG] Checking payment status for invoice: {invoice_id}")

            # Get invoice status from NOWPayments
            np = payments.NOWPayments()
            invoice_status = np.get_invoice_status(invoice_id)

            print(f"[DEBUG] Invoice status response: {invoice_status}")

            if not invoice_status:
                print(f"[ERROR] Failed to get invoice status for {invoice_id}")
                await query.answer("❌ Erro ao verificar pagamento. Tente novamente.", show_alert=True)
                return

            status = invoice_status.get('payment_status', 'waiting')
            print(f"[DEBUG] Payment status: {status}")

            if status == 'finished':
                # Payment completed - update database and add credits
                payment_data = db.get_payment(invoice_id)
                print(f"[DEBUG] Payment data from DB: {payment_data}")

                if payment_data and payment_data['status'] != 'finished':
                    print(f"[INFO] Processing payment completion for user {user_id}")
                    print(f"[INFO] Adding {payment_data['credits']} credits to user {user_id}")

                    # Update payment status FIRST
                    db.update_payment_status(invoice_id, 'finished')

                    # Then add credits
                    db.update_user_credits(user_id, payment_data['credits'])

                    # Process referral commission (10%)
                    db.process_referral_commission(invoice_id, user_id, payment_data['credits'])

                    print(f"[SUCCESS] Credits added successfully to user {user_id}")

                    # Notify user
                    await query.message.edit_text(
                        f"✅ <b>PAGAMENTO CONFIRMADO!</b>\n\n"
                        f"💎 <b>{payment_data['credits']} créditos</b> foram adicionados à sua conta!\n\n"
                        f"Use /saldo para verificar seu saldo.",
                        parse_mode='HTML'
                    )

                    # Check if someone referred this user and notify them
                    user = db.get_user(user_id)
                    if user and user['referred_by']:
                        commission = int(payment_data['credits'] * 0.1)
                        if commission >= 1:
                            try:
                                await context.bot.send_message(
                                    chat_id=user['referred_by'],
                                    text=f"🎁 <b>COMISSÃO RECEBIDA!</b>\n\n"
                                         f"Seu indicado acabou de depositar créditos!\n\n"
                                         f"💎 <b>Você ganhou: {commission} créditos</b>\n\n"
                                         f"Use /referral para ver suas estatísticas.",
                                    parse_mode='HTML'
                                )
                            except:
                                pass
                else:
                    print(f"[INFO] Payment already processed for invoice {invoice_id}")
                    await query.answer("✅ Pagamento já processado!", show_alert=True)

            elif status in ['confirming', 'sending', 'partially_paid']:
                print(f"[INFO] Payment {invoice_id} is being processed")
                await query.answer(
                    "⏳ Pagamento em processamento...\n\n"
                    "Aguarde alguns minutos e clique novamente.",
                    show_alert=True
                )

            elif status in ['failed', 'refunded', 'expired']:
                print(f"[WARNING] Payment {invoice_id} status: {status}")
                db.update_payment_status(invoice_id, status)
                await query.answer(
                    f"❌ Pagamento {status}.\n\n"
                    "Entre em contato com o suporte se precisar de ajuda.",
                    show_alert=True
                )

            else:  # waiting
                print(f"[INFO] Payment {invoice_id} is waiting")
                await query.answer(
                    "⏰ Aguardando pagamento...\n\n"
                    "Complete o pagamento e clique novamente.",
                    show_alert=True
                )

        except Exception as e:
            print(f"[ERROR] Error checking payment: {e}")
            import traceback
            traceback.print_exc()
            await query.answer("❌ Erro ao verificar pagamento. Tente novamente.", show_alert=True)

        return

    # Cancel
    if data == 'cancel':
        await query.message.delete()
        return

    # Format buttons (LOGIN, URL, delete)
    try:
        mtext = str(query.message.text)

        try:
            idx = str(query.message.reply_to_message.from_user.id)
        except:
            if query.message.chat.type == 'private':
                idx = user_id
            else:
                await query.answer("⚠️ VOCÊ NÃO ENVIOU A MENSAGEM", show_alert=True)
                return

        if data == 'URL':
            if int(idx) != int(user_id):
                await query.answer("⚠️ VOCÊ NÃO ENVIOU A MENSAGEM", show_alert=True)
                return

            # Check and deduct credits before download
            user = db.get_user(user_id)
            has_free = user['free_searches'] > 0
            has_credits = user['credits'] > 0

            if not has_free and not has_credits:
                await query.answer("❌ Sem créditos! Use /comprar para adicionar.", show_alert=True)
                return

            # Deduct credits
            is_free = db.deduct_credits(user_id, 1)
            user = db.get_user(user_id)

            try:
                await query.message.delete()
            except:
                pass

            file, idm = mtext.split('FIXO: ')[1].split(' | ')

            # Extract URL and total from message for history
            try:
                url_match = re.search(r'URL: <code>(.+?)</code>', mtext)
                total_match = re.search(r'LINHAS / ROWS: <code>([\d,]+)</code>', mtext)

                if url_match and total_match:
                    url = url_match.group(1)
                    total = int(total_match.group(1).replace(',', ''))
                    db.add_search_history(user_id, url, total, 0 if is_free else 1, is_free)
            except:
                pass

            credit_info = "🎁 GRÁTIS" if is_free else f"💎 -1 crédito (Saldo: {user['credits']})"
            mtext = '<b>' + mtext.split('⚠️')[0] + f'\n{credit_info}\n\nURL:LOGIN:SENHA</b>'

            padrao = [[InlineKeyboardButton(" DELETA 🚮", callback_data='delete')]]
            enviap = InlineKeyboardMarkup(padrao)

            try:
                await context.bot.send_document(
                    chat_id=query.message.chat.id,
                    caption=mtext,
                    reply_markup=enviap,
                    reply_to_message_id=int(idm),
                    document=f'files/{file}',
                    parse_mode='html',
                    read_timeout=120,
                    write_timeout=120
                )
            except Exception as e:
                print(f"Error sending document: {e}")

            return

        if data == 'LOGIN':
            if int(idx) != int(user_id):
                await query.answer("⚠️ VOCÊ NÃO ENVIOU A MENSAGEM", show_alert=True)
                return

            # Check and deduct credits before download
            user = db.get_user(user_id)
            has_free = user['free_searches'] > 0
            has_credits = user['credits'] > 0

            if not has_free and not has_credits:
                await query.answer("❌ Sem créditos! Use /comprar para adicionar.", show_alert=True)
                return

            # Deduct credits
            is_free = db.deduct_credits(user_id, 1)
            user = db.get_user(user_id)

            try:
                await query.message.delete()
            except:
                pass

            file, idm = mtext.split('FIXO: ')[1].split(' | ')

            # Extract URL and total from message for history
            try:
                url_match = re.search(r'URL: <code>(.+?)</code>', mtext)
                total_match = re.search(r'LINHAS / ROWS: <code>([\d,]+)</code>', mtext)

                if url_match and total_match:
                    url = url_match.group(1)
                    total = int(total_match.group(1).replace(',', ''))
                    db.add_search_history(user_id, url, total, 0 if is_free else 1, is_free)
            except:
                pass

            credit_info = "🎁 GRÁTIS" if is_free else f"💎 -1 crédito (Saldo: {user['credits']})"
            mtext = '<b>' + mtext.split('⚠️')[0] + f'\n{credit_info}\n\nLOGIN:SENHA</b>'

            padrao = [[InlineKeyboardButton(" DELETA 🚮", callback_data='delete')]]
            enviap = InlineKeyboardMarkup(padrao)

            try:
                with open(f'files/{file}', 'r', errors='replace', encoding='utf-8') as dd:
                    ff = list(filter(None,
                        (map(lambda x: f'{x.split(":")[1]}:{x.split(":")[2]}' if len(x.split(':')) == 3 else None, dd))
                    ))

                fila = BytesIO(''.join(ff).encode('utf-8'))
                fila.name = file

                await context.bot.send_document(
                    chat_id=query.message.chat.id,
                    caption=mtext,
                    reply_markup=enviap,
                    reply_to_message_id=int(idm),
                    document=fila,
                    parse_mode='html',
                    read_timeout=120,
                    write_timeout=120
                )
            except Exception as e:
                print(f"Error processing LOGIN format: {e}")

            return

        if data == 'delete':
            if query.message.chat.type == 'private':
                idx = user_id

            if int(user_id) == config.ADMIN_ID or int(idx) == int(user_id):
                try:
                    await query.message.delete()
                except:
                    pass
            else:
                await query.answer("⚠️ Você não tem permissão para deletar", show_alert=True)

            return

    except Exception as e:
        print(f"Error in button handler: {e}")


async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    # Check if awaiting input for referral code
    if context.user_data.get('awaiting_referral_code'):
        await referral_commands.process_custom_code(update, context)
        return

    # Check if awaiting input for admin user search
    if context.user_data.get('awaiting_user_id'):
        await admin_commands.admin_process_user_search(update, context)
        return

    # Check if awaiting credits adjustment
    if context.user_data.get('awaiting_credits_amount'):
        await admin_commands.admin_process_credits_adjustment(update, context)
        return

    # Check if awaiting coupon creation
    if context.user_data.get('awaiting_coupon_data'):
        await admin_commands.admin_process_coupon_creation(update, context)
        return

    # Otherwise, treat as search command
    await tudo(update, context)


async def setup_bot_commands(application: Application):
    """Setup bot commands for users and admin"""
    from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

    # Commands for regular users
    user_commands = [
        BotCommand("start", "Iniciar o bot"),
        BotCommand("saldo", "Ver seu saldo e estatísticas"),
        BotCommand("comprar", "Comprar créditos"),
        BotCommand("historico", "Ver histórico de buscas"),
        BotCommand("referral", "Sistema de indicação"),
        BotCommand("meusindicados", "Ver seus indicados"),
        BotCommand("cupom", "Usar um cupom"),
        BotCommand("url", "Buscar credenciais por URL"),
    ]

    # Commands for admin (all user commands + admin commands)
    admin_commands = user_commands + [
        BotCommand("admin", "Painel administrativo"),
        BotCommand("stats", "Estatísticas do bot"),
    ]

    try:
        # Set default commands for all users
        await application.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

        # Set admin commands for admin user
        await application.bot.set_my_commands(
            admin_commands,
            scope=BotCommandScopeChat(chat_id=config.ADMIN_ID)
        )

        print("✅ Comandos do bot configurados com sucesso!")
        print(f"   • Usuários: {len(user_commands)} comandos")
        print(f"   • Admin (ID {config.ADMIN_ID}): {len(admin_commands)} comandos")
    except Exception as e:
        print(f"⚠️ Erro ao configurar comandos: {e}")


def main():
    if not config.BOT_TOKEN:
        print('❌ BOT_TOKEN não encontrado!')
        print('Configure o arquivo .env com seu token.')
        return

    # Create necessary directories
    os.makedirs('files', exist_ok=True)

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("comprar", comprar))
    app.add_handler(CommandHandler("historico", historico))
    app.add_handler(CommandHandler("stats", admin_stats))

    # New command handlers
    app.add_handler(CommandHandler("referral", referral_commands.referral_menu))
    app.add_handler(CommandHandler("meusindicados", referral_commands.view_referred))
    app.add_handler(CommandHandler("cupom", coupon_commands.use_coupon_command))
    app.add_handler(CommandHandler("admin", admin_commands.admin_panel))

    # Search handlers
    app.add_handler(CommandHandler("url", tudo))
    app.add_handler(CommandHandler("ur", tudo))
    app.add_handler(CommandHandler("u", tudo))

    # Message handler (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    # Callback handler
    app.add_handler(CallbackQueryHandler(Botoes))

    print("🤖 Bot Premium rodando...")
    print(f"📊 Admin ID: {config.ADMIN_ID}")
    print(f"💰 Preço por busca: €{config.PRICE_PER_SEARCH} EUR")
    print(f"✅ SQLite: Conectado (Bot_premium.db)")
    print(f"🎁 Sistema de Referral: Ativo")
    print(f"🎟️ Sistema de Cupons: Ativo")
    print(f"🚫 Anti-Spam: Ativo")
    print("")

    # Setup commands on startup
    async def post_init(application: Application):
        await setup_bot_commands(application)

    app.post_init = post_init

    app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('\n👋 Bot parado pelo usuário')
    except Exception as e:
        print(f'❌ Erro: {e}')
