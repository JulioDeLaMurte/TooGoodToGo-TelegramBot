import re
import configparser
import asyncio
from _thread import start_new_thread

from telebot import types
from telebot.async_telebot import AsyncTeleBot

from TooGoodToGo import TooGoodToGo

import tgtg.exceptions

config = configparser.ConfigParser()
config.read('config.ini')
token = config['Telegram']['token']
bot = AsyncTeleBot(token)
tooGoodToGo = TooGoodToGo(token, config['Configuration'])

def log_command(chat_id: int, command: str, log: str = ''):
    print(f"[{chat_id}] /{command}{f': {log}' if log else ''}")

# Handle '/start' and '/help'
@bot.message_handler(commands=['help', 'start'])
async def send_welcome(message):
    chat_id = str(message.chat.id)
    log_command(chat_id, 'help')
    await bot.send_message(chat_id,
                           """
*Salut, bienvenue sur le bot TGTG :*

Le bot vous notifiera dès que de nouveaux sacs de vos favoris seront disponibles.

*❗️Obligatoire si vous voulez utiliser le bot❗️*
🔑 Pour vous connecter à votre compte TooGoodToGo, entrez 
*/login email@example.com*
_Vous recevrez alors un email avec un lien de confirmation.
Vous n'avez pas besoin d'entrer de mot de passe._

⚙️ Avec */settings*, vous pouvez définir quand vous voulez être notifié. 

ℹ️ Avec */info*, vous pouvez afficher tous les magasins de vos favoris où des sacs sont actuellement disponibles.

_🌐 Vous pouvez trouver plus d'informations sur Too Good To Go_ [ici](https://www.toogoodtogo.com/).

*🌍 LUTTONS ensemble contre le gaspillage alimentaire 🌎*
""", parse_mode="Markdown")


@bot.message_handler(commands=['info'])
async def send_info(message):
    chat_id = str(message.chat.id)
    log_command(chat_id, 'info')
    credentials = tooGoodToGo.find_credentials_by_telegramUserID(chat_id)
    if credentials is None:
        await bot.send_message(chat_id=chat_id,
                               text="🔑 Vous devez d'abord vous connecter avec votre email !\nVeuillez entrer */login email@example.com*\n*❗️️C'est nécessaire si vous voulez utiliser le bot❗️*",
                               parse_mode="Markdown")
        return None
    tooGoodToGo.send_available_favourite_items_for_one_user(chat_id)


@bot.message_handler(commands=['login'])
async def send_login(message):
    chat_id = str(message.chat.id)

    try:
        if tooGoodToGo.update_credentials(chat_id, refresh=True):
            log_command(chat_id, 'login', 'Logged in')
            await bot.send_message(chat_id=chat_id, text="👍 Vous êtes connecté !")
            return None
    except tgtg.exceptions.TgtgAPIError as err:
        tooGoodToGo.handle_api_error(err, chat_id)
        bot.send_message(chat_id, "❌ Erreur lors de la connection. Ré-essayez plus tard.")
        return None
        
    email = message.text.replace('/login', '').strip()

    if re.match(r"[^@]+@[^@]+\.[^@]+", email):
        log_command(chat_id, 'login', email)
        telegram_username = message.from_user.username
        start_new_thread(tooGoodToGo.new_user, (chat_id, telegram_username, email))
    else:
        log_command(chat_id, 'login', f'{email} (Invalid)')
        await bot.send_message(chat_id=chat_id,
                               text="*⚠️ Adresse email non valide ⚠️*"
                                    "\nVeuillez entrer */login email@example.com*"
                                    "\n_Vous receverez par la suie un email avec un lien de confirmation."
                                    "\nVous n'avez pas besoin d'entrer de mot de passe._",
                               parse_mode="Markdown")


def inline_keyboard_markup(chat_id):
    inline_keyboard = types.InlineKeyboardMarkup(
        keyboard=[
            [
                types.InlineKeyboardButton(
                    text=('🟢' if tooGoodToGo.users_settings_data[chat_id]['sold_out'] else '🔴') + ' ' + tooGoodToGo.format_status('sold_out'),
                    callback_data='sold_out'
                ),
                types.InlineKeyboardButton(
                    text=('🟢' if tooGoodToGo.users_settings_data[chat_id]['new_stock'] else '🔴') + ' ' + tooGoodToGo.format_status('new_stock'),
                    callback_data='new_stock'
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=("🟢" if tooGoodToGo.users_settings_data[chat_id]['stock_reduced'] else '🔴') + ' ' + tooGoodToGo.format_status('stock_reduced'),
                    callback_data='stock_reduced'
                ),
                types.InlineKeyboardButton(
                    text=("🟢" if tooGoodToGo.users_settings_data[chat_id]['stock_increased'] else '🔴') + ' ' + tooGoodToGo.format_status('stock_increased'),
                    callback_data='stock_increased'
                )
            ],
            [
                types.InlineKeyboardButton(
                    text='✅ Tout activer ✅',
                    callback_data='activate_all'
                )
            ],

            [
                types.InlineKeyboardButton(
                    text='❌ Tous désactiver ❌',
                    callback_data='disable_all'
                )
            ]
        ])
    return inline_keyboard


@bot.message_handler(commands=['settings'])
async def send_settings(message):
    chat_id = str(message.chat.id)
    log_command(chat_id, 'settings')
    credentials = tooGoodToGo.find_credentials_by_telegramUserID(chat_id)
    if credentials is None:
        await bot.send_message(chat_id=chat_id,
                               text="🔑 Vous devez d'abord vous connecter avec votre adresse email!\nVeuillez entrer */login email@example.com*\n*❗️️Cela est necessaire pour le fonctionnement du bot❗️*",
                               parse_mode="Markdown")
        return None

    await bot.send_message(chat_id, "🟢 = Activer | 🔴 = Désactiver  \n*Activer les alertes si :*", parse_mode="markdown",
                           reply_markup=inline_keyboard_markup(chat_id))


@bot.callback_query_handler(func=lambda c: c.data == 'sold_out')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    settings = tooGoodToGo.users_settings_data[chat_id]["sold_out"]
    tooGoodToGo.users_settings_data[chat_id]["sold_out"] = 0 if settings else 1
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))
    tooGoodToGo.save_users_settings_data_to_txt()


@bot.callback_query_handler(func=lambda c: c.data == 'new_stock')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    settings = tooGoodToGo.users_settings_data[chat_id]["new_stock"]
    tooGoodToGo.users_settings_data[chat_id]["new_stock"] = 0 if settings else 1
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))
    tooGoodToGo.save_users_settings_data_to_txt()


@bot.callback_query_handler(func=lambda c: c.data == 'stock_reduced')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    settings = tooGoodToGo.users_settings_data[chat_id]["stock_reduced"]
    tooGoodToGo.users_settings_data[chat_id]["stock_reduced"] = 0 if settings else 1
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))
    tooGoodToGo.save_users_settings_data_to_txt()


@bot.callback_query_handler(func=lambda c: c.data == 'stock_increased')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    settings = tooGoodToGo.users_settings_data[chat_id]["stock_increased"]
    tooGoodToGo.users_settings_data[chat_id]["stock_increased"] = 0 if settings else 1
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))
    tooGoodToGo.save_users_settings_data_to_txt()


@bot.callback_query_handler(func=lambda c: c.data == 'activate_all')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    for key in tooGoodToGo.users_settings_data[chat_id].keys():
        tooGoodToGo.users_settings_data[chat_id][key] = 1
    tooGoodToGo.save_users_settings_data_to_txt()
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))


@bot.callback_query_handler(func=lambda c: c.data == 'disable_all')
async def back_callback(call: types.CallbackQuery):
    chat_id = str(call.message.chat.id)
    for key in tooGoodToGo.users_settings_data[chat_id].keys():
        tooGoodToGo.users_settings_data[chat_id][key] = 0
    tooGoodToGo.save_users_settings_data_to_txt()
    await bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                        reply_markup=inline_keyboard_markup(chat_id))

print('TooGoodToGo bot started')

asyncio.run(bot.polling())
