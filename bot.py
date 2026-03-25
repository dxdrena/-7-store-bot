import logging
import sqlite3
import datetime
import random
import json
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Configuração
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8529101257:AAHig90c-LE74VKNwAkZ9GvMpa-wtr9Pxaw"

# ==================== BANCO DE DADOS ====================
def init_db():
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            user_id TEXT UNIQUE,
            username TEXT,
            name TEXT,
            register_date TEXT,
            wallet_id TEXT,
            balance REAL DEFAULT 0,
            total_cards INTEGER DEFAULT 0,
            total_pix_recharges INTEGER DEFAULT 0,
            total_gift_recharges INTEGER DEFAULT 0,
            total_recharge_value REAL DEFAULT 0,
            can_view_cpf INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bin TEXT,
            bank TEXT,
            type TEXT,
            level TEXT,
            price REAL,
            card_data TEXT,
            used INTEGER DEFAULT 0,
            sold_to TEXT,
            sold_date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pix_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            amount REAL,
            status TEXT,
            created_at TEXT,
            paid_at TEXT,
            transaction_code TEXT UNIQUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            amount REAL,
            gift_code TEXT,
            status TEXT,
            created_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS affiliates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            referrer_id TEXT,
            points INTEGER DEFAULT 0,
            total_earned REAL DEFAULT 0,
            referral_link TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# ==================== FUNÇÕES AUXILIARES ====================
def get_user(user_id):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (str(user_id),))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username, name, referrer_id=None):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    
    register_date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    wallet_id = str(random.randint(1000000000, 9999999999))
    
    cursor.execute('''
        INSERT INTO users (user_id, username, name, register_date, wallet_id, balance)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (str(user_id), username, name, register_date, wallet_id, 0.0))
    
    if referrer_id and referrer_id != str(user_id):
        cursor.execute('''
            INSERT INTO affiliates (user_id, referrer_id, points, referral_link)
            VALUES (?, ?, ?, ?)
        ''', (str(user_id), referrer_id, 0, f"t.me/¥7StoreBot?start={user_id}"))
    
    conn.commit()
    conn.close()
    return wallet_id

def update_balance(user_id, amount):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, str(user_id)))
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (str(user_id),))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def add_card_purchased(user_id):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET total_cards = total_cards + 1 WHERE user_id = ?", (str(user_id),))
    conn.commit()
    conn.close()

def add_pix_recharge(user_id, amount):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET total_pix_recharges = total_pix_recharges + 1, total_recharge_value = total_recharge_value + ? WHERE user_id = ?", (amount, str(user_id)))
    conn.commit()
    conn.close()
    
    cursor.execute("SELECT total_recharge_value FROM users WHERE user_id = ?", (str(user_id),))
    total = cursor.fetchone()[0]
    if total >= 100:
        cursor.execute("UPDATE users SET can_view_cpf = 1 WHERE user_id = ?", (str(user_id),))
        conn.commit()
    conn.close()

def add_gift_recharge(user_id, amount):
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET total_gift_recharges = total_gift_recharges + 1, total_recharge_value = total_recharge_value + ? WHERE user_id = ?", (amount, str(user_id)))
    conn.commit()
    conn.close()
    
    cursor.execute("SELECT total_recharge_value FROM users WHERE user_id = ?", (str(user_id),))
    total = cursor.fetchone()[0]
    if total >= 100:
        cursor.execute("UPDATE users SET can_view_cpf = 1 WHERE user_id = ?", (str(user_id),))
        conn.commit()
    conn.close()

def add_affiliate_commission(referrer_id, amount):
    commission = amount * 0.25
    update_balance(referrer_id, commission)
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE affiliates SET total_earned = total_earned + ? WHERE user_id = ?", (commission, str(referrer_id)))
    conn.commit()
    conn.close()

# ==================== BANCO DE CARTÕES ====================
CARDS_DB = {
    "R$ 15": [
        {"bin": "406669", "bank": "ITAU", "type": "VISA", "level": "CLASSIC", "price": 15, "card": "406669******1234|12/26|123|NOME"},
        {"bin": "516320", "bank": "BRADESCO", "type": "MASTERCARD", "level": "CLASSIC", "price": 15, "card": "516320******5678|10/26|456|NOME"},
    ],
    "AMEX - R$ 75": [
        {"bin": "376449", "bank": "BRADESCO", "type": "AMEX", "level": "AMEX", "price": 75, "card": "376449******10001|08/27|1234|NOME"},
    ],
    "AWARD - R$ 15": [
        {"bin": "534055", "bank": "BRADESCO", "type": "MASTERCARD", "level": "AWARD", "price": 15, "card": "534055******4321|05/26|789|NOME"},
    ],
    "B2B - R$ 15": [
        {"bin": "547844", "bank": "BRADESCO", "type": "MASTERCARD", "level": "B2B", "price": 15, "card": "547844******8765|03/27|321|NOME"},
    ],
    "BLACK - R$ 75": [
        {"bin": "518924", "bank": "ITAU", "type": "MASTERCARD", "level": "BLACK", "price": 75, "card": "518924******1111|12/27|999|NOME"},
    ],
    "BUSINESS - R$ 30": [
        {"bin": "537334", "bank": "SANTANDER", "type": "MASTERCARD", "level": "BUSINESS", "price": 30, "card": "537334******2222|09/26|444|NOME"},
    ],
    "CLASSIC - R$ 15": [
        {"bin": "453905", "bank": "BRADESCO", "type": "VISA", "level": "CLASSIC", "price": 15, "card": "453905******3333|06/27|777|NOME"},
    ],
    "ELO - R$ 30": [
        {"bin": "636297", "bank": "ELO", "type": "ELO", "level": "ELO", "price": 30, "card": "636297******4444|01/28|888|NOME"},
    ],
    "GOLD - R$ 17": [
        {"bin": "544828", "bank": "ITAU", "type": "MASTERCARD", "level": "GOLD", "price": 17, "card": "544828******5555|04/27|555|NOME"},
    ],
    "INFINITE - R$ 75": [
        {"bin": "543069", "bank": "SANTANDER", "type": "MASTERCARD", "level": "INFINITE", "price": 75, "card": "543069******6666|07/27|666|NOME"},
    ],
    "NANJING - R$ 75": [
        {"bin": "603488", "bank": "NANJING", "type": "CHINA UNION", "level": "NANJING", "price": 75, "card": "603488******7777|02/28|111|NOME"},
    ],
    "NUBANK BUSINESS - R$ 12": [
        {"bin": "408688", "bank": "NUBANK", "type": "MASTERCARD", "level": "BUSINESS", "price": 12, "card": "408688******8888|11/26|222|NOME"},
    ],
    "NUBANK PLATINUM - R$ 25": [
        {"bin": "536519", "bank": "NUBANK", "type": "MASTERCARD", "level": "PLATINUM", "price": 25, "card": "536519******9999|10/27|333|NOME"},
    ],
    "PREPAID - R$ 10": [
        {"bin": "539393", "bank": "PREPAID", "type": "MASTERCARD", "level": "PREPAID", "price": 10, "card": "539393******0000|12/27|444|NOME"},
    ],
    "PREPAID ELECTRON - R$ 25": [
        {"bin": "402288", "bank": "PREPAID", "type": "VISA", "level": "ELECTRON", "price": 25, "card": "402288******1212|09/26|555|NOME"},
    ],
    "SIGNATURE - R$ 30": [
        {"bin": "545301", "bank": "BRADESCO", "type": "MASTERCARD", "level": "SIGNATURE", "price": 30, "card": "545301******3434|08/27|666|NOME"},
    ],
    "STANDARD - R$ 15": [
        {"bin": "517417", "bank": "SANTANDER", "type": "MASTERCARD", "level": "STANDARD", "price": 15, "card": "517417******5656|07/28|777|NOME"},
    ]
}

# ==================== COMANDOS PRINCIPAIS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "sem_username"
    name = update.effective_user.first_name
    
    referrer_id = None
    if context.args and len(context.args) > 0:
        referrer_id = context.args[0]
    
    user = get_user(user_id)
    if not user:
        create_user(user_id, username, name, referrer_id)
    
    keyboard = [
        [InlineKeyboardButton("💳 COMPRAR CC", callback_data="buy_menu")],
        [InlineKeyboardButton("🔍 BUSCAR BIN", callback_data="search_bin"),
         InlineKeyboardButton("🏦 BUSCAR BANCO", callback_data="search_bank")],
        [InlineKeyboardButton("💰 ADICIONAR SALDO VIA PIX", callback_data="add_pix")],
        [InlineKeyboardButton("🎁 SISTEMA DE AFILIADOS", callback_data="affiliate")],
        [InlineKeyboardButton("📊 MINHA CONTA", callback_data="my_account")],
        [InlineKeyboardButton("❓ AJUDA", callback_data="help_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
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
    
    await update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=reply_markup)

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        await update.message.reply_text("❌ Usuário não encontrado. Use /start para se registrar.")
        return
    
    text = (
        f"📊 *SUAS INFORMAÇÕES*\n\n"
        f"👤 *Nome:* {user[4]}\n"
        f"🆔 *User:* @{user[3]}\n"
        f"📅 *Data de cadastro:* {user[5]}\n\n"
        f"💳 *ID da carteira:* {user[6]}\n"
        f"💰 *Saldo:* R$ {user[7]:.2f}\n\n"
        f"💳 *Cartões comprados:* {user[8]}\n"
        f"📱 *Recargas com Pix's:* {user[9]}\n"
        f"🎁 *Recargas por GIFT:* {user[10]}\n"
    )
    
    if user[12] == 1:
        text += f"\n✅ *CPF ANTECIPADO LIBERADO!*"
    else:
        text += f"\n⚠️ *CPF ANTECIPADO:* Deposite R$100 mensal para liberar"
    
    keyboard = [
        [InlineKeyboardButton("💰 Recargas Pix", callback_data="add_pix"),
         InlineKeyboardButton("🎁 Recargas por GIFT", callback_data="add_gift")],
        [InlineKeyboardButton("📜 Histórico de CC's", callback_data="history")],
        [InlineKeyboardButton("« volta", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📌 *Escolha um nível para continuar sua compra*\n\n"
        f"🎴 *{len(CARDS_DB)} categorias disponíveis*\n"
        f"📦 *Total de cartões:* {sum(len(cards) for cards in CARDS_DB.values())}\n\n"
    )
    
    keyboard = []
    for category in CARDS_DB.keys():
        keyboard.append([InlineKeyboardButton(category, callback_data=f"select_category_{category}")])
    keyboard.append([InlineKeyboardButton("« volta", callback_data="back_to_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def search_bin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"🔍 *BUSCA POR BIN*\n\n"
        f"Você pode buscar por cartões em nossa base pela **BIN** 😊\n\n"
        f"📌 *Use o comando:* `/bin 406669`\n"
        f"*ou simplesmente envie a bin para o bot.*\n\n"
        f"💡 *Exemplo:* /bin 406669\n\n"
        f"*BIN = primeiros 6 dígitos do cartão*"
    )
    keyboard = [[InlineKeyboardButton("« volta", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def search_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"🏦 *BUSCA POR BANCO*\n\n"
        f"💡 Caso esteja procurando por um cartão de um banco específico, use a busca por banco 😊\n\n"
        f"📌 *Exemplo de uso:* `/bank banco do brasil`\n"
        f"*ou simplesmente envie o nome do banco para o bot.*\n\n"
        f"*Bancos disponíveis:* ITAU, BRADESCO, SANTANDER, NUBANK, ELO, PREPAID, NANJING"
    )
    keyboard = [[InlineKeyboardButton("« volta", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def add_pix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"💰 *ADIÇÃO DE SALDO VIA PIX*\n\n"
        f"tornou-se mais fácil! agora os seus pagamentos serão processados de forma automática pelo bot. 😊\n\n"
        f"📌 *para criar uma transação pelo bot use:*\n"
        f"`/pix valor`\n\n"
        f"📌 *exemplo:* `/pix 20`\n\n"
        f"✅ *o seu saldo estará disponível em até 30 minutos após o pagamento!*\n\n"
        f"💳 *Chave Pix:* ¥7store@pix.com\n"
        f"💰 *Valor mínimo:* R$ 10,00"
    )
    keyboard = [
        [InlineKeyboardButton("💳 GERAR QR CODE", callback_data="generate_pix")],
        [InlineKeyboardButton("« volta", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def pix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Use: /pix valor\nExemplo: /pix 20")
        return
    
    try:
        amount = float(context.args[0])
        if amount < 10:
            await update.message.reply_text("❌ Valor mínimo: R$ 10,00")
            return
        
        user_id = update.effective_user.id
        transaction_code = str(random.randint(100000, 999999))
        
        text = (
            f"💰 *TRANSAÇÃO CRIADA!*\n\n"
            f"💳 *Valor:* R$ {amount:.2f}\n"
            f"🔑 *Código:* {transaction_code}\n"
            f"💳 *Chave Pix:* ¥7store@pix.com\n\n"
            f"✅ *Após o pagamento, envie o código para o bot:*\n"
            f"`/confirmar {transaction_code}`\n\n"
            f"⏱️ *Prazo:* 30 minutos"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Use: /pix 20")

async def confirm_pix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Use: /confirmar CODIGO")
        return
    
    code = context.args[0]
    user_id = update.effective_user.id
    
    await update.message.reply_text(
        f"✅ *PAGAMENTO CONFIRMADO!*\n\n"
        f"💰 R$ 20,00 adicionado ao seu saldo!\n"
        f"💳 *Novo saldo:* R$ {get_balance(user_id) + 20:.2f}\n\n"
        f"✨ *Aproveite suas compras na ¥7|STORE!*"
    )
    
    update_balance(user_id, 20)
    add_pix_recharge(user_id, 20)

async def affiliate_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('store.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM affiliates WHERE user_id = ?", (str(user_id),))
    aff = cursor.fetchone()
    conn.close()
    
    text = (
        f"🎁 *SISTEMA DE AFILIADOS ¥7|STORE*\n\n"
        f"Ganhe bônus ao indicar a store para seus amigos!\n\n"
        f"📌 *Cada amigo que usa seu link você irá ganhar 0 de pontos*\n"
        f"📌 *Quando seu amigo fizer uma recarga você ganhará 25% (saldo) do valor recarregado!*\n"
        f"📌 *A cada 0 pontos você ira receber 0 de saldo*\n\n"
        f"🔗 *Seu link:* t.me/¥7StoreBot?start={user_id}\n\n"
    )
    
    if aff:
        text += f"📊 *Pontos:* {aff[3]}\n"
        text += f"💰 *Ganhos totais:* R$ {aff[4]:.2f}\n"
    
    keyboard = [
        [InlineKeyboardButton("📤 Compartilhar", callback_data="share_link")],
        [InlineKeyboardButton("🔄 Trocar pontos", callback_data="exchange_points")],
        [InlineKeyboardButton("« volta", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def cpf_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user[12] == 1:
        text = (
            f"🔓 *CPF ANTECIPADO LIBERADO*\n\n"
            f"✅ Você já pode visualizar os CPFs das FULL antes da compra!\n\n"
            f"📌 *Para ver o CPF, use:* `/cpf bin`\n"
            f"*Exemplo:* `/cpf 406669`"
        )
    else:
        text = (
            f"🔒 *CPF ANTECIPADO BLOQUEADO*\n\n"
            f"⚠️ Para visualizar o CPF das FULL antes da compra, é necessário um depósito mínimo de R$ 100 no mês.\n\n"
            f"📌 *Exemplo:* Quando inicia um novo mês, o sistema reseta e você precisa adicionar um total de R$ 100 para visualizar novamente.\n\n"
            f"✅ *A LIBERAÇÃO É IMEDIATA E AUTOMÁTICA APÓS ATINGIR O VALOR DE R$ 100 MENSAL.*"
        )
    
    keyboard = [[InlineKeyboardButton("« volta", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_bin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text.strip()
    bin_number = message.replace("/bin", "").strip()
    
    if not bin_number:
        await update.message.reply_text("❌ Envie uma BIN válida.\nExemplo: /bin 406669")
        return
    
    results = []
    for category, cards in CARDS_DB.items():
        for card in cards:
            if card["bin"].startswith(bin_number[:6]):
                results.append(card)
                break
    
    if results:
        text = f"🔍 *RESULTADOS PARA BIN {bin_number}*\n\n"
        for card in results:
            text += f"🏦 *{card['bank']}* - {card['type']} {card['level']}\n"
            text += f"💰 Preço: R$ {card['price']}\n"
            text += f"🎴 BIN: {card['bin']}\n"
            text += f"📌 Use /comprar {card['level'].lower()} para comprar\n\n"
        
        keyboard = [[InlineKeyboardButton("🛒 Comprar", callback_data=f"buy_{card['level']}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text("❌ Nenhum cartão encontrado para essa BIN.")

async def handle_bank_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text.strip()
    bank_name = message.replace("/bank", "").strip().lower()
    
    if not bank_name:
        await update.message.reply_text("❌ Envie um banco válido.\nExemplo: /bank itau")
        return
    
    results = []
    for category, cards in CARDS_DB.items():
        for card in cards:
            if bank_name in card["bank"].lower():
                results.append(card)
    
    if results:
        text = f"🏦 *RESULTADOS PARA {bank_name.upper()}*\n\n"
        for card in results[:10]:
            text += f"💳 {card['type']} {card['level']} - R$ {card['price']}\n"
        text += f"\n📌 Total: {len(results)} cartões encontrados"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Nenhum cartão encontrado para o banco {bank_name}.")

async def buy_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = get_balance(user_id)
    
    if not context.args:
        await update.message.reply_text("❌ Use: /comprar [categoria]\nExemplo: /comprar classic")
        return
    
    level = context.args[0].upper()
    
    selected_card = None
    selected_category = None
    for category, cards in CARDS_DB.items():
        if level in category.upper():
            for card in cards:
                if not card.get("used"):
                    selected_card = card
                    selected_category = category
                    break
            if selected_card:
                break
    
    if not selected_card:
        await update.message.reply_text("❌ Categoria não encontrada ou sem estoque.")
        return
    
    if balance < selected_card["price"]:
        await update.message.reply_text(
            f"❌ *SALDO INSUFICIENTE!*\n\n"
            f"💰 Preço: R$ {selected_card['price']}\n"
            f"💳 Seu saldo: R$ {balance:.2f}\n\n"
            f"Use /pix para adicionar saldo",
            parse_mode='Markdown'
        )
        return
    
    update_balance(user_id, -selected_card["price"])
    add_card_purchased(user_id)
    
    card_data = selected_card["card"].split("|")
    text = (
        f"✅ *COMPRA REALIZADA COM SUCESSO!*\n\n"
        f"🏦 *Banco:* {selected_card['bank']}\n"
        f"💳 *Tipo:* {selected_card['type']} {selected_card['level']}\n"
        f"💰 *Valor:* R$ {selected_card['price']}\n\n"
        f"📌 *DADOS DO CARTÃO:*\n"
        f"🔢 *Número:* {card_data[0]}\n"
        f"📅 *Validade:* {card_data[1]}\n"
        f"🔐 *CVV:* {card_data[2]}\n"
        f"👤 *Nome:* {card_data[3]}\n\n"
        f"⚠️ *ATENÇÃO:* Você tem 10 minutos para testar e solicitar suporte!\n"
        f"👤 *Suporte:* @¥7Suporte"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"❓ *COMANDOS DISPONÍVEIS - ¥7|STORE*\n\n"
        f"/start - Iniciar bot\n"
        f"/minhaconta - Ver informações\n"
        f"/comprar - Comprar CC\n"
        f"/bin [bin] - Buscar por BIN\n"
        f"/bank [banco] - Buscar por banco\n"
        f"/pix [valor] - Adicionar saldo via PIX\n"
        f"/cpf - Ver status CPF antecipado\n"
        f"/afiliado - Sistema de afiliados\n"
        f"/help - Este menu\n\n"
        f"👤 *Suporte:* @¥7Suporte"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# ==================== CALLBACKS ====================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "back_to_menu":
        keyboard = [
            [InlineKeyboardButton("💳 COMPRAR CC", callback_data="buy_menu")],
            [InlineKeyboardButton("🔍 BUSCAR BIN", callback_data="search_bin"),
             InlineKeyboardButton("🏦 BUSCAR BANCO", callback_data="search_bank")],
            [InlineKeyboardButton("💰 ADICIONAR SALDO VIA PIX", callback_data="add_pix")],
            [InlineKeyboardButton("🎁 SISTEMA DE AFILIADOS", callback_data="affiliate")],
            [InlineKeyboardButton("📊 MINHA CONTA", callback_data="my_account")],
            [InlineKeyboardButton("❓ AJUDA", callback_data="help_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "👋 *Bem-vindo(a) à ¥7|STORE!*\n\nUse os botões abaixo para navegar:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data == "buy_menu":
        text = f"📌 *Escolha um nível para continuar sua compra*\n\n🎴 *{len(CARDS_DB)} categorias disponíveis*\n"
        keyboard = []
        for category in CARDS_DB.keys():
            keyboard.append([InlineKeyboardButton(category, callback_data=f"select_category_{category}")])
        keyboard.append([InlineKeyboardButton("« volta", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    
    elif data.startswith("select_category_"):
        category = data.replace("select_category_", "")
        cards = CARDS_DB.get(category, [])
        
        if not cards:
            await query.edit_message_text("❌ Categoria sem estoque no momento.")
            return
            
            card = cards[0]
        text = (
            f"💳 *{category}*\n\n"
            f"🏦 *Banco:* {card['bank']}\n"
            f"💳 *Tipo:* {card['type']} {card['level']}\n"
            f"💰 *Preço:* R$ {card['price']}\n"
            f"🔢 *BIN:* {card['bin']}\n\n"
            f"✅ *Cartão 100% VIRGEM*\n"
            f"✅ *Trocas ativas (ZERO-AUTH)*\n\n"
            f"⚠️ *Prazo para solicitar suporte: 10 minutos*\n\n"
            f"🔗 *APP PARA VERIFICAÇÃO:*\n"
            f"http://payments.google.com/gp/w/u/0/home/paymentmethods\n\n"
            f"✅ *Faça vídeo tentando vincular a forma de pagamento*"
        )
        keyboard = [
            [InlineKeyboardButton("🛒 COMPRAR AGORA", callback_data=f"confirm_buy_{category}")],
            [InlineKeyboardButton("« voltar", callback_data="buy_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    
    elif data.startswith("confirm_buy_"):
        category = data.replace("confirm_buy_", "")
        user_id = query.from_user.id
        balance = get_balance(user_id)
        
        cards = CARDS_DB.get(category, [])
        if not cards:
            await query.edit_message_text("❌ Produto esgotado!")
            return
        
        card = cards[0]
        
        if balance < card["price"]:
            text = (
                f"❌ *SALDO INSUFICIENTE!*\n\n"
                f"💰 Preço: R$ {card['price']}\n"
                f"💳 Seu saldo: R$ {balance:.2f}\n\n"
                f"Use /pix para adicionar saldo"
            )
            keyboard = [[InlineKeyboardButton("💰 Adicionar Saldo", callback_data="add_pix")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
            return
        
        update_balance(user_id, -card["price"])
        add_card_purchased(user_id)
        
        card_data = card["card"].split("|")
        text = (
            f"✅ *COMPRA REALIZADA COM SUCESSO!*\n\n"
            f"🏦 *Banco:* {card['bank']}\n"
            f"💳 *Tipo:* {card['type']} {card['level']}\n"
            f"💰 *Valor:* R$ {card['price']}\n\n"
            f"📌 *DADOS DO CARTÃO:*\n"
            f"🔢 *Número:* {card_data[0]}\n"
            f"📅 *Validade:* {card_data[1]}\n"
            f"🔐 *CVV:* {card_data[2]}\n"
            f"👤 *Nome:* {card_data[3]}\n\n"
            f"⚠️ *ATENÇÃO:* Você tem 10 minutos para testar e solicitar suporte!\n"
            f"👤 *Suporte:* @¥7Suporte"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "search_bin":
        text = (
            f"🔍 *BUSCA POR BIN*\n\n"
            f"Use: `/bin 406669`\n"
            f"*ou simplesmente envie a bin para o bot.*\n\n"
            f"💡 *Exemplo:* /bin 406669"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "search_bank":
        text = (
            f"🏦 *BUSCA POR BANCO*\n\n"
            f"Use: `/bank banco do brasil`\n\n"
            f"*Bancos:* ITAU, BRADESCO, SANTANDER, NUBANK, ELO"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "add_pix":
        text = (
            f"💰 *ADIÇÃO DE SALDO VIA PIX*\n\n"
            f"Use: `/pix valor`\n"
            f"Exemplo: `/pix 20`\n\n"
            f"✅ *Saldo disponível em até 30 minutos!*\n"
            f"💳 *Chave Pix:* ¥7store@pix.com"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "affiliate":
        user_id = query.from_user.id
        text = (
            f"🎁 *SISTEMA DE AFILIADOS ¥7|STORE*\n\n"
            f"Ganhe 25% de comissão nas recargas dos seus indicados!\n\n"
            f"🔗 *Seu link:* t.me/¥7StoreBot?start={user_id}\n\n"
            f"💰 *Comissão:* 25% do valor recarregado"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "my_account":
        user = get_user(query.from_user.id)
        if user:
            text = (
                f"📊 *SUAS INFORMAÇÕES*\n\n"
                f"👤 *Nome:* {user[4]}\n"
                f"🆔 *User:* @{user[3]}\n"
                f"💳 *ID da carteira:* {user[6]}\n"
                f"💰 *Saldo:* R$ {user[7]:.2f}\n"
                f"💳 *Cartões comprados:* {user[8]}\n"
                f"📱 *Recargas Pix:* {user[9]}\n"
                f"🎁 *Recargas GIFT:* {user[10]}"
            )
            await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "help_menu":
        text = (
            f"❓ *AJUDA - ¥7|STORE*\n\n"
            f"/start - Iniciar\n"
            f"/minhaconta - Minha conta\n"
            f"/comprar - Comprar CC\n"
            f"/bin [bin] - Buscar BIN\n"
            f"/bank [banco] - Buscar banco\n"
            f"/pix [valor] - Adicionar saldo\n"
            f"/cpf - CPF antecipado\n"
            f"/afiliado - Afiliados\n\n"
            f"👤 Suporte: @¥7Suporte"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "add_gift":
        text = (
            f"🎁 *RECARGA POR GIFT CARD*\n\n"
            f"Envie o código da sua Gift Card para recarregar saldo.\n\n"
            f"💰 *Valor mínimo:* R$ 10,00\n"
            f"📌 *Formato:* CÓDIGO|VALOR\n"
            f"Exemplo: `GIFT-ABC123|50`\n\n"
            f"✅ *Recarga automática após validação*"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "history":
        user_id = query.from_user.id
        user = get_user(user_id)
        text = (
            f"📜 *HISTÓRICO DE CC's*\n\n"
            f"💰 *Total de cartões comprados:* {user[8]}\n\n"
            f"Para ver detalhes das compras, entre em contato com o suporte."
        )
        keyboard = [[InlineKeyboardButton("« volta", callback_data="my_account")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    
    elif data == "generate_pix":
        text = (
            f"💳 *QR CODE PIX*\n\n"
            f"Chave Pix: ¥7store@pix.com\n\n"
            f"💰 *Valor:* Informe o valor com /pix\n\n"
            f"*Após pagamento, use /confirmar [código]*"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "share_link":
        user_id = query.from_user.id
        text = (
            f"📤 *COMPARTILHE SEU LINK*\n\n"
            f"🔗 t.me/¥7StoreBot?start={user_id}\n\n"
            f"💰 *Ganhe 25% de comissão em cada recarga!*"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "exchange_points":
        text = (
            f"🔄 *TROCAR PONTOS*\n\n"
            f"💰 *100 pontos = R$ 1,00 de saldo*\n\n"
            f"Use: `/trocar [quantidade]`\n"
            f"Exemplo: `/trocar 1000`"
        )
        await query.edit_message_text(text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text.startswith("/bin"):
        await handle_bin_search(update, context)
    elif text.startswith("/bank"):
        await handle_bank_search(update, context)
    elif text.startswith("/pix"):
        await pix_command(update, context)
    elif text.startswith("/confirmar"):
        await confirm_pix(update, context)
    elif text.startswith("/comprar") or text.startswith("/buy"):
        await buy_card(update, context)
    elif text.startswith("/minhaconta"):
        await my_account(update, context)
    elif text.startswith("/cpf"):
        await cpf_info(update, context)
    elif text.startswith("/afiliado"):
        await affiliate_system(update, context)
    elif text.startswith("/help"):
        await help_command(update, context)
    else:
        if re.match(r'^\d{6}$', text):
            await handle_bin_search(update, context)
        else:
            await update.message.reply_text(
                "❓ Comando não reconhecido.\n"
                "Use /help para ver os comandos disponíveis."
            )

# ==================== MAIN ====================
def main():
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("minhaconta", my_account))
    application.add_handler(CommandHandler("comprar", buy_card))
    application.add_handler(CommandHandler("buy", buy_card))
    application.add_handler(CommandHandler("bin", handle_bin_search))
    application.add_handler(CommandHandler("bank", handle_bank_search))
    application.add_handler(CommandHandler("pix", pix_command))
    application.add_handler(CommandHandler("confirmar", confirm_pix))
    application.add_handler(CommandHandler("cpf", cpf_info))
    application.add_handler(CommandHandler("afiliado", affiliate_system))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot ¥7|STORE iniciado com sucesso!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
