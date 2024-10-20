from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


class BaseConstructor:
    def __init__(self, locals_text: dict) -> None:
        self.locals_text = locals_text

    def construct_local_text(self, *levels: str) -> str:
        """
        Construct text from locals.yaml file,
        wich represent a template text for the bot.
        Pass the dictionary levels as string arguments.
        - construct_local_text("command", "start")
        """
        copy_locals_text = {**self.locals_text}
        stack = list(levels[::-1])

        while stack:
            level = stack.pop()
            copy_locals_text = copy_locals_text[level]
        
        text = copy_locals_text
        return str(text)

class TextConstructor(BaseConstructor):
    pass

class KeyboardConstructor(BaseConstructor):

    def construct_keyboard(self, call_backs: list[str]) -> InlineKeyboardMarkup:
        """
        Construct InlineKeyboardMarkup from list of strings.
        One string is one call_back name.
        Text for button is stored in locals.yaml file.
        Order of string defines the order of the buttons.
        """
        buttons = []
        for call_back_name in call_backs:
            text = super().construct_local_text("call_back", call_back_name)
            button = InlineKeyboardButton(text, callback_data=call_back_name)
            buttons.append(button)
        
        keyboard = []
        # linup buttons in a rows by 2
        while buttons:
            first_button = buttons.pop(0)
            if buttons:
                second_button = buttons.pop(0)
                group = [first_button, second_button]
                keyboard.append(group)
            else:
                group = [first_button]
                keyboard.append(group)
    
        return InlineKeyboardMarkup(keyboard)

    def user_bot_keyboard(self, call_backs: list[str]) -> InlineKeyboardMarkup:
        """
        Construct InlineKeyboardMarkup from list of strings.
        One string is one call_back name.
        Text for button is user bot name.
        Text and callback_data, name must be the same.
        """
        buttons = []
        for call_back_name in call_backs:
            text = call_back_name
            button = InlineKeyboardButton(text, callback_data=call_back_name)
            buttons.append(button)
        
        keyboard = []
        # linup buttons in a rows by 2
        while buttons:
            first_button = buttons.pop(0)
            if buttons:
                second_button = buttons.pop(0)
                group = [first_button, second_button]
                keyboard.append(group)
            else:
                group = [first_button]
                keyboard.append(group)
    
        return InlineKeyboardMarkup(keyboard)

class CallbackConstructor:
    async def user_bot_details(self,
                                    user_bot_details: Update,
                                    context: ContextTypes.DEFAULT_TYPE, call_backs: list[str]):
        reply_markup = None
        message_text = None


        async def user_bot_details_inner(update, context):
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(text=message_text, reply_markup=reply_markup)
            ...
        return user_bot_details_inner