import logging
import sqlite3
import datetime
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = "8529101257:AAHVI1e-scNY1nMNyGprmTHzyWCC4U5W00s"

def init_db():
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            user_id TEXT UNIQUE,
            username TEXT,
            name TEXT,
            balance REAL DEFAULT 0,
            total_cards INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (str(user_id),))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username, name):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, username, name, balance)
        VALUES (?, ?, ?, ?)
    ''', (str(user_id), username, name, 0.0))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, str(user_id)))
    conn.commit()
    conn.close()

def add_card_purchased(user_id):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET total_cards = total_cards + 1 WHERE user_id = ?", (str(user_id),))
    conn.commit()
    conn.close()

CARDS_DB = {
    "CLASSIC - R$ 15": {"bin": "406669", "bank": "ITAU", "type": "VISA", "price": 15, "card": "406669******1234|12/26|123|NOME"},
    "GOLD - R$ 17": {"bin": "544828", "bank": "ITAU", "type": "MASTERCARD", "price": 17, "card": "544828******5555|04/27|555|NOME"},
    "PLATINUM - R$ 25": {"bin": "536519", "bank": "NUBANK", "type": "MASTERCARD", "price": 25, "card": "536519******9999|10/27|333|NOME"},
    "BLACK - R$ 75": {"bin": "518924", "bank": "ITAU", "type": "MASTERCARD", "price": 75, "card": "518924******1111|12/27|999|NOME"},
    "AMEX - R$ 75": {"bin": "376449", "bank": "BRADESCO", "type": "AMEX", "price": 75, "card": "376449******10001|08/27|1234|NOME"},
    "PREPAID - R$ 10": {"bin": "539393", "bank": "PREPAID", "type": "MASTERCARD", "price": 10, "card": "539393******0000|12/27|444|NOME"},
    "SIGNATURE - R$ 30": {"bin": "545301", "bank": "BRADESCO", "type": "MASTERCARD", "price": 30, "card": "545301******3434|08/27|666|NOME"},
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "sem_username"
    name = update.effective_user.first_name
    
    user = get_user(user_id)
    if not user:
        create_user(user_id, username, name)
    
    keyboard = [
        [InlineKeyboardButton("💳 COMPRAR CC", callback_data="buy_menu")],
        [InlineKeyboardButton("🔍 BUSCAR BIN", callback_data="search_bin")],
        [InlineKeyboardButton("💰 ADICIONAR SALDO", callback_data="add_pix")],
        [InlineKeyboardButton("🎁 AFILIADOS", callback_data="affiliate")],
        [InlineKeyboardButton("📊 MINHA CONTA", callback_data="my_account")],
    ]
    
    welcome = (
        f"👋 *Bem-vindo(a) à ¥7|STORE!*\n\n"
        f"📌 *CCs em qualidade extraordinária*\n"
        f"📌 *Material testado no ato da compra*\n"
        f"📌 *Prazo de solicitação: 10 minutos*\n\n"
        f"✅ *Sem CHK na compra! (100% VIRGEM)*\n"
        f"✅ *Trocas ativas no BOT! (ZERO-AUTH)*\n\n"
        f"🔗 *APP PARA VERIFICAÇÃO (LIVE)*\n"
        f"GPAY: payments.google.com/gp/w/u/0/home/paymentmethods\n\n"
        f"👤 *Suporte:* @¥7Suporte"
    )
    
    await update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Use /start primeiro")
        return
    
    text = (
        f"📊 *SUAS INFORMAÇÕES*\n\n"
        f"👤 *Nome:* {user[3]}\n"
        f"🆔 *User:* @{user[2]}\n"
        f"💰 *Saldo:* R$ {user[4]:.2f}\n"
        f"💳 *Cartões comprados:* {user[5]}\n"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "buy_menu":
        keyboard = []
        for cat, card in CARDS_DB.items():
            keyboard.append([InlineKeyboardButton(cat, callback_data=f"buy_{cat}")])
        keyboard.append([InlineKeyboardButton("« voltar", callback_data="back")])
        await query.edit_message_text("📌 *Escolha um CC:*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("buy_"):
        cat = data.replace("buy_", "")
        card = CARDS_DB[cat]
        text = (
            f"💳 *{cat}*\n\n"
            f"🏦 *Banco:* {card['bank']}\n"
            f"💳 *Tipo:* {card['type']}\n"
            f"💰 *Preço:* R$ {card['price']}\n"
            f"🔢 *BIN:* {card['bin']}\n\n"
            f"✅ *Cartão 100% VIRGEM*\n"
            f"⚠️ *Prazo: 10 minutos*"
        )
        keyboard = [
            [InlineKeyboardButton("🛒 COMPRAR", callback_data=f"confirm_{cat}")],
            [InlineKeyboardButton("« voltar", callback_data="buy_menu")]
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("confirm_"):
        cat = data.replace("confirm_", "")
        card = CARDS_DB[cat]
        user_id = query.from_user.id
        user = get_user(user_id)
        
        if user[4] < card["price"]:
            text = f"❌ *SALDO INSUFICIENTE!*\n\n💰 Preço: R$ {card['price']}\n💳 Saldo: R$ {user[4]:.2f}"
            await query.edit_message_text(text, parse_mode='Markdown')
            return
        
        update_balance(user_id, -card["price"])
        add_card_purchased(user_id)
        
        card_data = card["card"].split("|")
        text = (
            f"✅ *COMPRA REALIZADA!*\n\n"
            f"🔢 *Número:* {card_data[0]}\n"
            f"📅 *Validade:* {card_data[1]}\n"
            f"🔐 *CVV:* {card_data[2]}\n"
            f"👤 *Nome:* {card_data[3]}\n\n"
            f"⚠️ *Você tem 10 minutos para testar!*\n"
            f"👤 *Suporte:* @¥7Suporte"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "search_bin":
        await query.edit_message_text("🔍 *BUSCA POR BIN*\n\nUse: /bin 406669\n\nExemplo: /bin 406669", parse_mode='Markdown')
    
    elif data == "add_pix":
        await query.edit_message_text("💰 *ADIÇÃO DE SALDO*\n\nUse: /pix valor\nEx: /pix 20\n\nChave: ¥7store@pix.com", parse_mode='Markdown')
    
    elif data == "affiliate":
        user_id = query.from_user.id
        await query.edit_message_text(f"🎁 *AFILIADOS*\n\nGanhe 25% de comissão!\n\n🔗 t.me/StoreBot?start={user_id}", parse_mode='Markdown')
    
    elif data == "my_account":
        user = get_user(query.from_user.id)
        text = f"📊 *MINHA CONTA*\n\n💰 Saldo: R$ {user[4]:.2f}\n💳 Cartões: {user[5]}"
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "back":
        keyboard = [
            [InlineKeyboardButton("💳 COMPRAR CC", callback_data="buy_menu")],
            [InlineKeyboardButton("🔍 BUSCAR BIN", callback_data="search_bin")],
            [InlineKeyboardButton("💰 ADICIONAR SALDO", callback_data="add_pix")],
            [InlineKeyboardButton("🎁 AFILIADOS", callback_data="affiliate")],
            [InlineKeyboardButton("📊 MINHA CONTA", callback_data="my_account")],
        ]
        await query.edit_message_text("👋 *Menu Principal - ¥7|STORE*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def pix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Use: /pix valor\nExemplo: /pix 20")
        return
    
    try:
        amount = float(context.args[0])
        if amount < 10:
            await update.message.reply_text("❌ Valor mínimo: R$ 10,00")
            return
        
        code = str(random.randint(100000, 999999))
        text = (
            f"💰 *TRANSAÇÃO CRIADA!*\n\n"
            f"💳 *Valor:* R$ {amount:.2f}\n"
            f"🔑 *Código:* {code}\n"
            f"💳 *Chave Pix:* ¥7store@pix.com\n\n"
            f"✅ *Após pagar, use:* `/confirmar {code}`"
        )
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except:
        await update.message.reply_text("❌ Valor inválido!")

async def confirm_pix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        update_balance(update.effective_user.id, 20)
        await update.message.reply_text("✅ *PAGAMENTO CONFIRMADO!*\n\n💰 R$20 adicionados ao seu saldo!", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith("/pix"):
        await pix_command(update, context)
    elif text.startswith("/confirmar"):
        await confirm_pix(update, context)
    elif text.startswith("/bin"):
        await update.message.reply_text("🔍 BIN recebida! Use o menu para comprar.")
    else:
        await update.message.reply_text("❓ Use /start para começar")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("minhaconta", my_account))
    app.add_handler(CommandHandler("pix", pix_command))
    app.add_handler(CommandHandler("confirmar", confirm_pix))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot ¥7|STORE rodando!")
    app.run_polling()

if __name__ == "__main__":
    main()