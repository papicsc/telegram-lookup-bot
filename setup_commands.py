"""
Script para configurar os comandos do bot no Telegram

Execute este script uma vez para registrar os comandos no BotFather.
Os comandos ficarão visíveis no menu do bot para os usuários.
"""

import asyncio
from telegram import Bot, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
import config


async def setup_commands():
    """Configura os comandos do bot"""
    bot = Bot(token=config.BOT_TOKEN)

    # Comandos para usuários normais
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

    # Comandos para admin (incluindo todos os comandos de usuário + admin)
    admin_commands = user_commands + [
        BotCommand("admin", "Painel administrativo"),
        BotCommand("stats", "Estatísticas do bot"),
    ]

    try:
        # Define comandos padrão para todos os usuários
        await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
        print("✅ Comandos de usuário configurados com sucesso!")

        # Define comandos específicos para o admin
        await bot.set_my_commands(
            admin_commands,
            scope=BotCommandScopeChat(chat_id=config.ADMIN_ID)
        )
        print(f"✅ Comandos de admin configurados para o ID: {config.ADMIN_ID}")

        print("\n📋 Comandos configurados:")
        print("\n👥 Usuários:")
        for cmd in user_commands:
            print(f"  /{cmd.command} - {cmd.description}")

        print("\n👑 Admin (adicional):")
        for cmd in admin_commands[len(user_commands):]:
            print(f"  /{cmd.command} - {cmd.description}")

    except Exception as e:
        print(f"❌ Erro ao configurar comandos: {e}")
        raise


if __name__ == "__main__":
    print("🔧 Configurando comandos do bot...\n")
    asyncio.run(setup_commands())
    print("\n✨ Configuração concluída!")
    print("\n💡 Os comandos agora aparecem no menu do Telegram!")
    print("   • Usuários verão apenas comandos básicos")
    print(f"   • Admin (ID {config.ADMIN_ID}) verá todos os comandos incluindo /admin")
