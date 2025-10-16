from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import requests
import os
import re
import time
from io import BytesIO
from datetime import datetime
import config
import database as db
import payments

# Initialize database
db.init_database()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = update.message if update.message else update.edited_message

    user_id = info.from_user.id
    username = str(info.from_user.username or info.from_user.name)
    fname = info.from_user.first_name
    chat_type = info.chat.type

    # Add user to database
    if chat_type == 'private':
        db.add_user(user_id, fname, username)

    # Get user info
    user = db.get_user(user_id)
    credits = user['credits'] if user else 0
    free_searches = user['free_searches'] if user else 0

    keyboard = [
        [InlineKeyboardButton("🔍 @ULP_Lookup_bot", url="https://t.me/ULP_Lookup_bot")],
        [InlineKeyboardButton("📊 @TUDOF_bot", url="https://t.me/TUDOF_bot")],
        [
            InlineKeyboardButton("💰 Comprar Créditos", callback_data='buy_credits'),
            InlineKeyboardButton("📊 Meu Saldo", callback_data='my_balance')
        ],
        [InlineKeyboardButton("➕ Adicionar ao Grupo", url="https://t.me/ULP_Lookup_bot?startgroup=true")]
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

    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("❌ Usuário não encontrado. Use /start primeiro.")
        return

    keyboard = [
        [InlineKeyboardButton("💳 Comprar Créditos", callback_data='buy_credits')],
        [InlineKeyboardButton("📊 Ver Histórico", callback_data='view_history')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = f"""💰 <b>SEU SALDO</b>

👤 <b>Nome:</b> {user['nome']}
🆔 <b>ID:</b> <code>{user['id']}</code>

💎 <b>Créditos:</b> <code>{user['credits']}</code>
🎁 <b>Buscas grátis:</b> <code>{user['free_searches']}</code>
📊 <b>Total de buscas:</b> <code>{user['total_searches']}</code>

{'👑 <b>Status:</b> PREMIUM' if user['is_premium'] else ''}

<i>💡 Cada busca custa 1 crédito</i>"""

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

        # Deduct credits
        is_free = db.deduct_credits(user_id, 1)
        user = db.get_user(user_id)

        # Add to history
        db.add_search_history(user_id, url, total, 0 if is_free else 1, is_free)

        message = config.SEARCH_SUCCESS.format(
            url=url,
            total=total,
            time=time.time() - now,
            credits=user['credits']
        )

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

            # Deduct credits
            is_free = db.deduct_credits(user_id, 1)
            user = db.get_user(user_id)

            # Add to history
            db.add_search_history(user_id, url, total, 0 if is_free else 1, is_free)

            message = config.SEARCH_SUCCESS.format(
                url=url,
                total=total,
                time=time.time() - now,
                credits=user['credits']
            )

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

        package = config.PACKAGE_PRICES[pkg_id]
        total_credits = package['credits'] + package['bonus']

        # Create payment (mock for now)
        payment = payments.create_mock_payment(user_id, pkg_id)

        if not payment:
            await query.message.edit_text("❌ Erro ao criar pagamento. Tente novamente.")
            return

        # Save payment to database
        db.add_payment(
            user_id,
            payment['id'],
            payment['price_amount'],
            payment['price_currency'].upper(),
            total_credits,
            payment.get('invoice_id')
        )

        keyboard = [
            [InlineKeyboardButton("💳 Pagar Agora", url=payment['invoice_url'])],
            [InlineKeyboardButton("🔙 Voltar", callback_data='buy_credits')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = f"""💳 <b>PAGAMENTO CRIADO</b>

📦 <b>Pacote:</b> {total_credits} créditos
💰 <b>Valor:</b> ${payment['price_amount']:.2f} USD

🔐 <b>ID do Pagamento:</b>
<code>{payment['id']}</code>

<b>Instruções:</b>
1. Clique em "Pagar Agora"
2. Escolha sua criptomoeda preferida
3. Envie o pagamento
4. Seus créditos serão adicionados automaticamente!

⏰ <i>Pagamento válido por 60 minutos</i>"""

        await query.message.edit_text(message, parse_mode='HTML', reply_markup=reply_markup)
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

            try:
                await query.message.delete()
            except:
                return

            file, idm = mtext.split('FIXO: ')[1].split(' | ')
            mtext = '<b>' + mtext + '\n\nURL:LOGIN:SENHA</b>'

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

            try:
                await query.message.delete()
            except:
                pass

            file, idm = mtext.split('FIXO: ')[1].split(' | ')
            mtext = '<b>' + mtext + '\n\nLOGIN:SENHA</b>'

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

    # Search handlers
    app.add_handler(CommandHandler("url", tudo))
    app.add_handler(CommandHandler("ur", tudo))
    app.add_handler(CommandHandler("u", tudo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tudo))

    # Callback handler
    app.add_handler(CallbackQueryHandler(Botoes))

    print("🤖 Bot Premium rodando...")
    print(f"📊 Admin ID: {config.ADMIN_ID}")
    print(f"💰 Preço por busca: ${config.PRICE_PER_SEARCH}")
    app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('\n👋 Bot parado pelo usuário')
    except Exception as e:
        print(f'❌ Erro: {e}')
