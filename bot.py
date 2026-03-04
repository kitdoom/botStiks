import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler
from telegram.utils.helpers import mention_html

# --- НАСТРОЙКИ (ЗАПОЛНИ ЭТИ ПЕРЕМЕННЫЕ) ---
BOT_TOKEN = "ТВОЙ_ТОКЕН_БОТА"  # Вставь токен от @BotFather
ADMIN_ID = 123456789  # Вставь свой цифровой ID
MODERATION_CHAT_ID = ADMIN_ID  # Сюда приходят заявки
# ------------------------------------------

# Состояния для разговора
AWAITING_LINK, AWAITING_DESCRIPTION, AWAITING_SIGNATURE = range(3)

# Временное хранилище
user_data = {}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Команда START ---
def start(update: Update, context):
    user = update.effective_user
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Ты хочешь попасть со своими стикерами в наш канал? Круто!\n\n"
        "📎 Отправь мне **ссылку на свой набор** стикеров или эмодзи\n"
        "(например, https://t.me/addstickers/durov)\n\n"
        "🖼 Или просто пришли **любой стикер/эмодзи** из этого набора"
    )
    update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    return AWAITING_LINK

# --- Принимаем ссылку или стикер ---
def receive_content(update: Update, context):
    user_id = update.effective_user.id
    
    if update.message.sticker:
        sticker = update.message.sticker
        set_name = sticker.set_name if sticker.set_name else "Неизвестный набор"
        user_data[user_id] = {
            'type': 'sticker',
            'file_id': sticker.file_id,
            'set_name': set_name,
            'emoji': sticker.emoji
        }
        reply_text = f"✅ Стикер из набора: **{set_name}**"
        
    elif update.message.text and 't.me/addstickers/' in update.message.text:
        link = update.message.text.strip()
        if not link.startswith('https://t.me/addstickers/'):
            update.message.reply_text("❌ Неверная ссылка. Нужна вида https://t.me/addstickers/... Попробуй ещё раз.")
            return AWAITING_LINK
            
        user_data[user_id] = {
            'type': 'link',
            'link': link
        }
        reply_text = f"✅ Ссылка принята!"
    else:
        update.message.reply_text("❌ Пожалуйста, отправь ссылку на набор или сам стикер.")
        return AWAITING_LINK

    # Спрашиваем про описание (необязательно)
    update.message.reply_text(
        f"{reply_text}\n\n"
        "📝 Теперь можешь добавить **короткое описание** своего набора (например, о чём стикеры, настроение, тематика).\n"
        "Это необязательно — просто отправь /skip, чтобы пропустить."
    )
    return AWAITING_DESCRIPTION

# --- Принимаем описание (или пропуск) ---
def receive_description(update: Update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if text == '/skip':
        description = None
        update.message.reply_text("⏩ Ок, пропускаем описание.")
    else:
        description = text
        update.message.reply_text("✅ Описание сохранено!")
    
    if user_id in user_data:
        user_data[user_id]['description'] = description
    else:
        update.message.reply_text("Ошибка, начни заново /start")
        return ConversationHandler.END
    
    # Спрашиваем про подпись (обязательно)
    update.message.reply_text(
        "✍️ **Как тебя подписать в посте?**\n\n"
        "1. Отправь свой **ник** (например, @nickname)\n"
        "2. Отправь **имя** (например, Анна)\n"
        "3. Или напиши **0** / **анонимно**, если хочешь без подписи"
    )
    return AWAITING_SIGNATURE

# --- Пропуск описания (обработчик команды /skip) ---
def skip_description(update: Update, context):
    user_id = update.effective_user.id
    if user_id in user_data:
        user_data[user_id]['description'] = None
    update.message.reply_text("⏩ Пропускаем описание.")
    
    # Сразу спрашиваем подпись
    update.message.reply_text(
        "✍️ **Как тебя подписать в посте?**\n\n"
        "1. Отправь свой **ник** (например, @nickname)\n"
        "2. Отправь **имя** (например, Анна)\n"
        "3. Или напиши **0** / **анонимно**, если хочешь без подписи"
    )
    return AWAITING_SIGNATURE

# --- Принимаем подпись и отправляем заявку админу ---
def receive_signature(update: Update, context):
    user_id = update.effective_user.id
    signature_input = update.message.text.strip()
    
    # Определяем подпись
    if signature_input.lower() in ['анонимно', '0', 'нет']:
        signature = None
        signature_text = "Автор пожелал остаться анонимным"
    else:
        signature = signature_input
        signature_text = f"Подпись: {signature}"
    
    if user_id in user_data:
        user_data[user_id]['signature'] = signature
    else:
        update.message.reply_text("Ошибка, начни заново /start")
        return ConversationHandler.END
    
    # --- Отправка заявки админу ---
    user = update.effective_user
    user_link = mention_html(user.id, user.first_name)
    
    # Формируем текст заявки
    if user_data[user_id]['type'] == 'link':
        content_info = f"📎 **Ссылка на набор:** {user_data[user_id]['link']}"
    else:
        content_info = f"🖼 **Стикер из набора:** {user_data[user_id]['set_name']}\nЭмодзи: {user_data[user_id]['emoji']}"
    
    # Добавляем описание, если оно есть
    description = user_data[user_id].get('description')
    description_info = f"📝 **Описание:** {description}" if description else "📝 Описание: не указано"
    
    text_for_admin = (
        f"📬 **Новая заявка на публикацию!**\n\n"
        f"👤 От: {user_link}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"{content_info}\n"
        f"{description_info}\n"
        f"✍️ {signature_text}\n\n"
        f"👇 Контент:"
    )
    
    # Кнопки для модерации (просто для отметки, уведомлений автору НЕ будет)
    keyboard = [[
        InlineKeyboardButton("✅ Одобрено (отметка)", callback_data=f"mark_{user_id}"),
        InlineKeyboardButton("❌ Отклонено (отметка)", callback_data=f"mark_{user_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем админу
    if user_data[user_id]['type'] == 'sticker':
        context.bot.send_sticker(
            chat_id=MODERATION_CHAT_ID,
            sticker=user_data[user_id]['file_id'],
            caption=text_for_admin,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    else:
        context.bot.send_message(
            chat_id=MODERATION_CHAT_ID,
            text=text_for_admin,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=False
        )
    
    # Сообщаем пользователю, что заявка отправлена
    update.message.reply_text(
        "✨ Спасибо! Твоя заявка отправлена администратору.\n"
        "Если твой набор подойдёт для канала, с тобой свяжутся (или ты увидишь его в канале)."
    )
    
    # Очищаем данные (по желанию можно оставить до получения отметки)
    if user_id in user_data:
        del user_data[user_id]
    
    return ConversationHandler.END

# --- Обработчик кнопок (просто отметка для админа) ---
def moderation_callback(update: Update, context):
    query = update.callback_query
    query.answer()
    
    admin_id = query.from_user.id
    if admin_id != ADMIN_ID:
        query.edit_message_text("⛔️ Нет прав")
        return
    
    # Просто меняем текст, никаких уведомлений пользователю
    query.edit_message_text(
        text=query.message.text + "\n\n✅ Отмечено",
        parse_mode=ParseMode.HTML
    )

# --- Отмена диалога ---
def cancel(update: Update, context):
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    update.message.reply_text("Действие отменено. Чтобы начать заново, введи /start")
    return ConversationHandler.END

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            AWAITING_LINK: [MessageHandler(Filters.sticker | Filters.text & ~Filters.command, receive_content)],
            AWAITING_DESCRIPTION: [
                MessageHandler(Filters.text & ~Filters.command, receive_description),
                CommandHandler('skip', skip_description)
            ],
            AWAITING_SIGNATURE: [MessageHandler(Filters.text & ~Filters.command, receive_signature)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    dp.add_handler(conv_handler)
    dp.add_handler(CallbackQueryHandler(moderation_callback, pattern='^mark_'))
    
    updater.start_polling()
    logger.info("Бот запущен!")
    updater.idle()

if __name__ == '__main__':
    main()