from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import requests
import os
import json
import re
import time
from io import BytesIO
from datetime import datetime
import sqlite3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_KEY = os.getenv('API_KEY', 'WCjWLueQo596P03tFr8Q')
API_URL = os.getenv('API_URL', 'https://ulpcloud.site/url')
ADMIN_ID = int(os.getenv('ADMIN_ID', '1268314769'))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = update.message

    if not info:
        info = update.edited_message

    un = str(info.from_user.name)
    idc = info.chat.id
    id = info.from_user.id
    fname = info.from_user.first_name
    idm = info.message_id
    tipo = info.chat.type

    if tipo == 'private':
        adicionar_bot(id, fname, un)

    keyboard = [
        [InlineKeyboardButton("🔍 @ULP_Lookup_bot", url="https://t.me/ULP_Lookup_bot")],
        [InlineKeyboardButton("📊 @TUDOF_bot", url="https://t.me/TUDOF_bot")],
        [InlineKeyboardButton("➕ Adicionar ao Grupo", url="https://t.me/ULP_Lookup_bot?startgroup=true")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"""👋 <b>Bem-vindo, {fname}!</b>

🔍 <b>COMANDOS DISPONÍVEIS:</b>

🌐 <code>/url URL</code> - Buscar credenciais
🔗 <code>/ur URL</code> - Busca rápida
⚡ <code>/u URL</code> - Busca express

💬 <b>Ou simplesmente envie a URL direto!</b>

━━━━━━━━━━━━━━━━━━━━
<b>🤖 BOTS ATIVOS:</b>

🔹 @ULP_Lookup_bot - Database permanente
🔹 @TUDOF_bot - Atualizado semanalmente

━━━━━━━━━━━━━━━━━━━━
<i>💡 Dica: Envie qualquer URL e farei a busca automaticamente!</i></b>""",
        parse_mode='HTML',
        reply_markup=reply_markup,
        reply_to_message_id=idm
    )


def con():
    conn = sqlite3.connect("Bot_free.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY,
        nome TEXT,
        user TEXT,
        qtd INTEGER DEFAULT 0
    )
    """)
    conn.commit()

    return conn, cursor


def adicionar_bot(user_id, nome, username):
    conn, cursor = con()
    cursor.execute("SELECT id FROM usuarios WHERE id = ?", (user_id,))
    existe = cursor.fetchone()

    if not existe:
        cursor.execute(
            "INSERT INTO usuarios (id, nome, user, qtd) VALUES (?, ?, ?, ?)",
            (user_id, nome, username, 0)
        )
        conn.commit()

    conn.close()


async def tudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = update.message

    if not info:
        info = update.edited_message

    un = str(info.from_user.name)
    idc = info.chat.id
    id = info.from_user.id
    fname = info.from_user.first_name
    idm = info.message_id
    tipo = info.chat.type
    ung = str(info.chat.username)

    padrao = [[InlineKeyboardButton(" DELETA 🚮", callback_data='delete')]]
    enviap = InlineKeyboardMarkup(padrao)

    dois = [
        [InlineKeyboardButton("LOGIN:SENHA", callback_data='LOGIN')],
        [InlineKeyboardButton("URL:LOGIN:SENHA", callback_data='URL')],
        [InlineKeyboardButton(" DELETA 🚮", callback_data='delete')]
    ]
    doist = InlineKeyboardMarkup(dois)

    if tipo == 'private':
        adicionar_bot(id, fname, un)

    if tipo != 'private':
        if not re.match(r'/url|/ur|/u|^www\.|^https?://', info.text.lower()):
            return

    url = info.text.lower()

    url = re.sub(r'/url|/ur|/u|https?://|www\.', '', url).strip()
    url = re.sub(r'^www\.|^login\.', '', url).strip()
    url = re.sub(r':.*', '', url).strip()

    if len(url) < 3:
        await context.bot.send_message(
            chat_id=idc,
            text=f'''<b>
⚠️  3 CARACTERES É O MÍNIMO

❌  3 CHARACTERS IS THE MINIMUM
</b>''',
            parse_mode='HTML',
            reply_to_message_id=idm
        )
        return

    if url.count('/') > 0:
        url = url.split('/')[0]

    if len(url) > 55:
        if url.count('/') == 0:
            url = url[:55]

    anome = re.sub(r'\s+', ' ', url)
    prov = ''

    if len(anome.split(' ')) > 1:
        anome = ' '.join(anome.split(' ')[:2])
        anome, prov = anome.split(' ')
        if '@' not in prov:
            anome = f'{anome}_@{prov}'

    dd = datetime.now()
    now = time.time()

    print(f'URL: {url} Data: {dd.strftime("%d/%m/%Y, %H:%M:%S")} | {un} | {idc} | {ung}')

    if '_' not in anome:
        anome = f'{anome}_{prov}-'

    # Create files directory if it doesn't exist
    os.makedirs('files', exist_ok=True)

    ap = [ap for ap in os.listdir('files') if anome in ap]

    if len(ap) > 0 and len(ap) < 2:
        total = int(re.sub(r'\D', '', ap[0].split('_')[1]))

        await context.bot.send_message(
            chat_id=idc,
            text=f'''<b>=>
☑️  URL: <code>{url}</code>

🧵  LINHAS / ROWS: <code>{total:,}</code>

TEMPO: <code>{time.time() - now:.2f}</code>

FIXO: {ap[0]} | {idm}
</b>''',
            parse_mode='HTML',
            reply_to_message_id=idm,
            reply_markup=doist
        )
        return

    try:
        u = f'{API_URL}?k={API_KEY}&q={url}&t=1'
        he = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0'}

        now = time.time()

        r = requests.get(u, timeout=15, headers=he)

        if r.status_code == 200:
            try:
                nome = r.headers['Content-Disposition'].split('filename=')[1].replace('"', '')
            except:
                await context.bot.send_message(
                    chat_id=idc,
                    text=f'''<b>
🔎  URL: <code>{url}</code>

⚠️  NÃO ENCONTRADO
❌  SEARCH NOT FOUND

TEMPO: <code>{time.time() - now:.2f}</code>
</b>''',
                    parse_mode='HTML',
                    reply_to_message_id=idm
                )
                return

            total = int(re.sub(r'\D', '', nome.split('_')[1]))

            with open(f'files/{nome}', 'w', encoding='utf-8') as ss:
                ss.write(r.text)

            await context.bot.send_message(
                chat_id=idc,
                text=f'''<b>=>
☑️  URL: <code>{url}</code>

🧵  LINHAS / ROWS: <code>{total:,}</code>

TEMPO: <code>{time.time() - now:.2f}</code>

FIXO: {nome} | {idm}
</b>''',
                parse_mode='HTML',
                reply_to_message_id=idm,
                reply_markup=doist
            )

        elif r.status_code == 404:
            await context.bot.send_message(
                chat_id=idc,
                text=f'''<b>
🔎  URL: <code>{url}</code>

⚠️  NÃO ENCONTRADO
❌  SEARCH NOT FOUND

TEMPO: <code>{time.time() - now:.2f}</code>
</b>''',
                parse_mode='HTML',
                reply_to_message_id=idm
            )

    except Exception as e:
        print('Error', e)
        await context.bot.send_message(
            chat_id=idc,
            text=f'''<b>
⚠️  ERRO / ERROR

{str(e)}
</b>''',
            parse_mode='HTML',
            reply_to_message_id=idm
        )


async def Botoes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        info = update.callback_query
        id = info.from_user.id
        idc = info.message.chat.id
        typ = info.message.chat.type
        mtext = str(info.message.text)
        un = info.from_user.username

    except Exception as e:
        message = f"<b> ⚠️ BOT ONLINE !!!\n⚠️\n</b>"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='HTML')
        return

    padrao = [[InlineKeyboardButton(" DELETA 🚮", callback_data='delete')]]
    enviap = InlineKeyboardMarkup(padrao)

    option = info.data.split(' ')

    try:
        idx = str(info.message.reply_to_message.from_user.id)
    except Exception as e:
        if typ == 'private':
            idx = id
        else:
            await info.answer(
                text="""⚠️   VOCÊ NÃO ENVIOU DA MENSAGEM\n
⚠️  YOU DO NOT OWNER THE MESSAGE""",
                show_alert=True,
                cache_time=0
            )
            return

    if option[0] == 'URL':
        if int(idx) != int(id):
            await info.answer(
                text="""⚠️   VOCÊ NÃO ENVIOU DA MENSAGEM\n
⚠️  YOU DO NOT OWNER THE MESSAGE""",
                show_alert=True,
                cache_time=0
            )
            return

        try:
            await info.message.delete()
        except:
            return

        file, idm = mtext.split('FIXO: ')[1].split(' | ')
        mtext = '<b>' + mtext + '\n\nURL:LOGIN:SENHA</b>'

        try:
            await context.bot.send_document(
                chat_id=idc,
                caption=mtext,
                reply_markup=enviap,
                reply_to_message_id=idm,
                document=f'files/{file}',
                parse_mode='html',
                read_timeout=120,
                write_timeout=120
            )
        except Exception as e:
            message = f"<b>⚠️  Algum Erro !!!\n\n⚠️  Error file !!!\nURL:LOGIN:SENHA\n{e}</b>"
            with open('error_bot_free.txt', 'a', encoding='utf-8') as p:
                p.write(f'{e} | {file} \n')
            await context.bot.send_message(chat_id=idc, text=message, parse_mode='HTML')

    elif option[0] == 'LOGIN':
        if int(idx) != int(id):
            await info.answer(
                text="""⚠️   VOCÊ NÃO ENVIOU DA MENSAGEM\n
⚠️  YOU DO NOT OWNER THE MESSAGE""",
                show_alert=True,
                cache_time=0
            )
            return

        try:
            await info.message.delete()
        except:
            pass

        file, idm = mtext.split('FIXO: ')[1].split(' | ')
        mtext = '<b>' + mtext + '\n\nLOGIN:SENHA</b>'

        try:
            with open(f'files/{file}', 'r', errors='replace', encoding='utf-8') as dd:
                ff = list(filter(None,
                    (map(lambda x: f'{x.split(":")[1]}:{x.split(":")[2]}' if len(x.split(':')) == 3 else None, dd))
                ))

            fila = BytesIO(''.join(ff).encode('utf-8'))
            fila.name = file

            await context.bot.send_document(
                chat_id=idc,
                caption=mtext,
                reply_markup=enviap,
                reply_to_message_id=idm,
                document=fila,
                parse_mode='html',
                read_timeout=120,
                write_timeout=120
            )

        except Exception as e:
            with open('error_bot_free.txt', 'a', encoding='utf-8') as p:
                p.write(f'{e} | {file} \n')
            message = f"<b>⚠️  Algum Erro !!!\n\n⚠️  Error file !!!LOGIN:SENHA\n {e}</b>"
            await context.bot.send_message(chat_id=idc, text=message, parse_mode='HTML')

    elif option[0] == 'delete':
        if typ == 'private':
            idx = info.from_user.id

        if int(id) == ADMIN_ID or int(idx) == int(id):
            try:
                await info.message.delete()
                return
            except Exception as e:
                er = str(e)

                if 'Message to delete not found' in er:
                    message = f"<b>⚠️  Bot LIGADO !!!\n\n⚠️  Bot ON AGAIN !!!\n</b>"
                    await context.bot.send_message(chat_id=idc, text=message, parse_mode='HTML')
                    return

                return

        await info.answer(
            text="⚠️ Você Não Tem Permissão Para Deletar",
            show_alert=True,
            cache_time=0
        )


def main():
    if not BOT_TOKEN:
        print('❌ BOT_TOKEN não encontrado!')
        print('Por favor, configure o arquivo .env com seu token do bot.')
        print('Copie .env.example para .env e adicione seu token.')
        return

    # Create necessary directories
    os.makedirs('files', exist_ok=True)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("url", tudo))
    app.add_handler(CommandHandler("ur", tudo))
    app.add_handler(CommandHandler("u", tudo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tudo))
    app.add_handler(CallbackQueryHandler(Botoes))

    print("🤖 Bot rodando...")
    print(f"📊 Admin ID: {ADMIN_ID}")
    app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('\n👋 Bot parado pelo usuário')
    except Exception as e:
        print(f'❌ Erro: {e}')
        print('Reinicie o bot para tentar novamente')
