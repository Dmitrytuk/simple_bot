import os
import re
import logging
import json
import asyncio
import aiohttp
from enum import Enum

from attr import dataclass
import yaml
import aiofiles
from dotenv import load_dotenv

from telegram import (
                        BotCommand,
                        Update,
                        InlineKeyboardButton,
                        InlineKeyboardMarkup,
                        InlineQueryResultArticle,
                        InputTextMessageContent,
                    )
from telegram.constants import ParseMode
from telegram.ext import (
                            ConversationHandler,
                            filters, 
                            MessageHandler,
                            Application,
                            ApplicationBuilder,
                            ContextTypes,
                            CommandHandler,
                            InlineQueryHandler,
                            CallbackQueryHandler
                        )

from telegram.constants import ChatAction

from constructors import (
                            TextConstructor,
                            KeyboardConstructor,
                            CallbackConstructor
                        )


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    # level=logging.DEBUG
    level=logging.INFO    
    # level=logging.ERROR
)


load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

class Db:
    @staticmethod
    def db_read() -> dict: # leave it syncronous, later it will be async db call
        with open('statics/users.json') as f:
            users = json.load(f)
            return users

    @staticmethod
    def db_write(data, level: str):
        exisitng_json = Db.db_read()
        exisitng_json[level].append(data)
        with open('statics/users.json', 'w') as f:
           json.dump(exisitng_json, f, indent=4)


class UserStatus(Enum):
    OWNER = 'owner of bot'
    ACTIVE_USER = 'active user'
    NOT_ACTIVE_USER = 'not active user'
    NEW_USER = 'new user'


async def read_locals() -> dict:
    async with aiofiles.open('statics/locals.yaml', 'r') as f:
        data = await f.read()
        locals_yaml = yaml.load(data, Loader=yaml.loader.SafeLoader)
        return locals_yaml

async def token_getme_request_tg(token: str) -> dict:
    url = 'https://api.telegram.org/bot{}/getMe'.format(token)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data
@dataclass
class UserModel:
        id: int
        active: bool
        first_name: str
        last_name: str
        username: str
        is_bot: bool
        language_code: str


class User:
    def __init__(self, user_chat: Update):
        self._db_conn = Db.db_read()
        self._tg_user = user_chat.effective_user
        self._user_model = None

    @property
    def data(self):
        if not self._user_model:
            user_data = self._get_user_data()
            self._user_model = self._create_user_model(user_data) if user_data else None
            return self._user_model
        else:
            return self._user_model

    def _get_user_data(self) -> dict | None:
        try:
            return [user for user in self._db_conn["users"] if self._tg_user.id == user["id"]][0]
        except IndexError:
            return None

    def _create_user_model(self, user_data):
        return UserModel(**user_data)

    def create_new_user(self):
        data = self._tg_user.to_dict()
        data["active"] = True
        Db.db_write(data, "users")
        self._db_conn = Db.db_read()
        return self.data

    def _is_user_owner(self):
        owner = self._db_conn["owner"]
        return owner["id"] == self._tg_user.id

    @property
    def status(self):
        if self.data is not None:
            if self.data.active == True:
                return UserStatus.ACTIVE_USER
            elif self.data.active == False:
                return UserStatus.NOT_ACTIVE_USER
            else:
                print("-=-=------>", self.data.id)
        elif self._is_user_owner():
            return UserStatus.OWNER
        elif self.data is None:
            return UserStatus.NEW_USER


@dataclass
class BotModel:
        id: int
        token: str
        is_bot: bool
        can_join_groups: bool
        can_read_all_group_messages: bool
        supports_inline_queries: bool
        can_connect_to_business: bool
        has_main_web_app: bool
        first_name: str
        username: str
        user_bot_owner: int


class UserBotController:
    def __init__(self,
                user: User,
                msg_token: str | None = None,
                bot_result: dict | None = None,
                ):
        self._db_conn = Db.db_read()
        self.user = user
        self.msg_token = msg_token
        self._bot_result = bot_result
        self._bot_model = None

    @property
    def data(self):
        if not self._bot_model:
            bot_data = self._get_bot_data()
            self._bot_model = self._create_bot_model(bot_data) if bot_data else None
            return self._bot_model
        else:
            return self._bot_model

    def _get_bot_data(self) -> dict | None:
        try:
            return [bot for bot in self._db_conn["user_bot"] if self._bot_result["id"] == bot["id"]][0]
        except IndexError:
            return None

    def _create_bot_model(self, user_bot_data):
        return BotModel(**user_bot_data)

    def create_new_bot(self):
        data = self._bot_result
        data["token"] = self.msg_token
        data["user_bot_owner"] = self.user.data.id
        Db.db_write(data, "user_bot")
        self._db_conn = Db.db_read()
        return self.data

    @property
    def get_user_bots(self):
        return [bot for bot in self._db_conn["user_bot"] if bot["user_bot_owner"] == self.user.data.id]


## end of utils

#BOT 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = User(update)

    reply_markup = None

    if user.status == UserStatus.NEW_USER:
        user.create_new_user()

    locals_text = await read_locals()
    text_constructor = TextConstructor(locals_text)
    message_text = text_constructor.construct_local_text("command", "start")
    message_text = message_text.format(first_name=user.data.first_name)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


# START converstation of Create bot. create_bot_conv

VALIDATE_BOT_TOKEN = range(1)
END = ConversationHandler.END

async def create_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = User(update)
    if user.status == UserStatus.NEW_USER:
        user.create_new_user()
    
    locals_text = await read_locals()
    text_constructor = TextConstructor(locals_text)
    message_text = text_constructor.construct_local_text("command", "create_bot")
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    context.user_data["user"] = user
    context.user_data["text_constructor"] = text_constructor
    
    return VALIDATE_BOT_TOKEN


async def token_valid_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_token = str(update.message.text)
    user = context.user_data["user"]
    text_constructor = context.user_data["text_constructor"]
    

    response = await token_getme_request_tg(msg_token)
    # todo: add patch to prevent adding mainbot to userbot
    match response:
        case {"ok": False}:
            text = text_constructor.construct_local_text("message", "token_is_not_valid")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            return VALIDATE_BOT_TOKEN
        case {"ok": True}:
            bot_controller = UserBotController(
                                                user,
                                                msg_token,
                                                response.get("result"),
                                            )
            if bot_controller.data:
                text = text_constructor.construct_local_text("message", "bot_already_exists")
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
                return VALIDATE_BOT_TOKEN
            else:
                text = text_constructor.construct_local_text("message", "new_bot_created")
                bot_controller.create_new_bot()
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
                return END

async def stop_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    logging.info("------------------Выход из conversation-----------------")
    return END

    
# END converstation of Create bot. create_bot_conv



# START converstation of Manage my bots. /my_bots

BOT_DETAILS, BOT_DELETE, BOT_PAYMENT, MANAGE = range(4)
END = ConversationHandler.END

async def my_bots_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = User(update)
    bot_controller = UserBotController(user)
    user_bots = bot_controller.get_user_bots
    # button_callback = CallbackConstructor().user_bot_details()
    context.user_data["user_bots"] = user_bots
    
    bots_list = [str(bot["username"]) for bot in user_bots]


    locals_text = await read_locals()
    text_constructor = TextConstructor(locals_text)
    keyboard_constructor = KeyboardConstructor(locals_text).user_bot_keyboard(bots_list)

    message_text = text_constructor.construct_local_text("command", "my_bots_command")
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=keyboard_constructor)

    return BOT_DETAILS


async def user_bot_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    locals_text = await read_locals()

    message_text = None
    reply_markup = None
    user_bot = None

    for bot in context.user_data["user_bots"]:
        if bot["username"] == query.data:
            message_text = f"Информация о боте {bot['username']}"

            context.user_data.clear()
            context.user_data["user_bot_name"] = bot["username"]
    
    reply_markup = KeyboardConstructor(locals_text).construct_keyboard(["pay_for_user_bot", "delete_user_bot"])

    await query.edit_message_text(text=message_text, reply_markup=reply_markup)

        # как то перейти на стейт в зависимости от нажатой кнопки
    return MANAGE
    

async def user_bot_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(text=f"Удаление бота...{context.user_data["user_bot_name"]}")

    return END

async def pay_for_user_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(text=f"Оплата бота... {context.user_data["user_bot_name"]}")

    return END

# async def stop_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data.clear()
#     logging.info("------------------Выход из conversation-----------------")
#     return END

# END converstation of Manage my bots. /my_bots




async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Мне не известна эта команда...")

async def create_command_menu(context: Application):
    # await context.bot.delete_my_commands()
    await context.bot.set_my_commands([
        BotCommand("start", "Start the bot")
        ])




def main():

    application = ApplicationBuilder().token(BOT_TOKEN).post_init(create_command_menu).build()
    start_handler = CommandHandler('start', start)
    create_bot_handler = CommandHandler('create_bot_command', create_bot_command)
    my_bots_handler = CommandHandler('my_bots', my_bots_command)
    # unknown_handler = MessageHandler(filters.COMMAND, unknown)

    # create_bot conversation
    create_bot_conv = ConversationHandler(
        entry_points=[create_bot_handler],
        states={
            VALIDATE_BOT_TOKEN: [
            MessageHandler(filters.TEXT & (~ filters.COMMAND), token_valid_msg),
            ],
        },
        fallbacks=[
            MessageHandler(filters.COMMAND, stop_conversation),
        ],
        allow_reentry=True,
    )

    # bot manage conversation
    manage_user_bot_conv = ConversationHandler(
        entry_points=[my_bots_handler],
        states= {
                BOT_DETAILS: [CallbackQueryHandler(user_bot_details)],
                MANAGE: [
                    CallbackQueryHandler(user_bot_delete, pattern="delete_user_bot"),
                    CallbackQueryHandler(pay_for_user_bot, pattern="pay_for_user_bot"),
                ],
        },
        fallbacks= [
                MessageHandler(filters.COMMAND, stop_conversation),
        ],
        allow_reentry=True,
    )


    application.add_handler(start_handler, 1)
    application.add_handler(create_bot_conv, 2)
    application.add_handler(manage_user_bot_conv, 3)
    # application.add_handler(my_bots, 3)
    # application.add_handler(user_bot_details_handler, 3)
    # application.add_handler(user_bot_delete_handler, 4)
    # application.add_handler(unknown_handler, 1) # make explicit command list
    application.run_polling()

if __name__ == '__main__':
    main()
