import random
import asyncio
from queue import Queue
import telegram
from telegram import ext
import psycopg2
from constants import TOKEN, DBNAME, DBPASSWORD

'''
    Run this through manager.py if you're on working server
'''

BOTMESSAGES = {
    "en": {
        "/start": "/join to an existing list or /create a new one",
        "/join": "Successfully joined to a grocery list. Use /check to get it's content. "
                 "You can add new position by using /add, or just writing a message to me. Write several lines to add "
                 "several positions at once",
        "join_help": "Enter the code of the grocery list you want to connect to",
        "join_failed": "It seems there's no grocery list with such code",
        "join_wrong_args": "This command expects a code. Example: /join 123",
        "/create": "New grocery list created! Your list code is {code}. "
                   "You can add new position by using /add, or just writing a message to me. Write several lines to add"
                   " several positions at once",
        "create_failed": "It seems that there are no available codes at the moment. You should tell "
                         "<a href='tg://user?id=1039988481'>him</a>",
        "empty_list": "This list is currently empty.",
        "list_updated": "Your list is updated",
        "list_cleared": "Your grocery list is now empty",
        "removed_from_list": "This item has been removed from list",
        "remove_help": "Write the item you want to remove",
        "remove_failed": "Could not remove this item. Are you sure it exists?",
        "remove_wrong_args": "This command expects an item to remove. Example: /remove Milk"
    },
    "ru": {
        "/start": "Нажмите /join, чтобы присоединиться к существующему списку, или создайте новый с помощью /start",
        "/join": "Вы подключились к списку покупок. Используйте /check, чтобы узнать его содержимое. Вы можете добавить "
                 "новые предметы с помощью команды /add, или просто отправить сообщение с новым предметом. Если вы хотите"
                 " добавить сразу несколько предметов, напишите каждый из них на отдельной строке",
        "join_help": "Введите код списка, к которому вы хотите подключиться",
        "join_failed": "Кажется списка с таким кодом не существует",
        "join_wrong_args": "Вы должны указать код вместе с командой. Пример: /join 123",
        "/create": "Список покупок создан! Вот его код: {code}. Вы можете добавить "
                   "новые предметы с помощью команды /add, или просто отправить сообщение с новым предметом. Если вы хотите"
                   " добавить сразу несколько предметов, напишите каждый из них на отдельной строке",
        "create_failed": "Кажется сейчас не осталось свободного кода для нового списка. В этом виноват "
                         "<a href='tg://user?id=1039988481'>он</a>",
        "empty_list": "Этот список покупок пустой.",
        "list_updated": "Список обновлён",
        "list_cleared": "Список покупок очищен",
        "removed_from_list": "Этот предмет вычеркнут из списка",
        "remove_help": "Напишите, что вы хотите убрать",
        "remove_failed": "Не удалось убрать этот предмет. Он точно есть в вашем списке?",
        "remove_wrong_args": "Вы должны указать предмет, который хотите удалить. Пример: /remove Milk"
    }
}


class DBHandler:
    connection = None
    cursor = None

    @staticmethod
    def init(name, user, password):
        DBHandler.connection = psycopg2.connect(database=name, user=user, password=password, host='localhost')
        DBHandler.cursor = DBHandler.connection.cursor()

    @staticmethod
    def connect_to_empty_list(user: telegram.User):
        DBHandler.cursor.execute("SELECT * from grocerylists "
                                 "RIGHT JOIN groceryuser ON grocerylists.id != groceryuser.grocery_list")
        grocery_list = random.sample(DBHandler.cursor.fetchall(), 1)[0]

        DBHandler.cursor.execute("UPDATE grocerylists SET items = '{}' WHERE id = %s", [grocery_list[0]])

        DBHandler.cursor.execute("UPDATE groceryUser SET grocery_list = %s WHERE id = %s",
                                 (grocery_list[0], user.id))
        if DBHandler.cursor.statusmessage == "UPDATE 0":  # no rows were modified with UPDATE query
            DBHandler.cursor.execute("INSERT INTO groceryuser (id, grocery_list) VALUES (%s, %s)", (user.id, grocery_list[0]))
        DBHandler.connection.commit()
        return grocery_list[0]

    @staticmethod
    def connect_to_nonempty_list(user: telegram.User, grocery_list_id):
        DBHandler.cursor.execute("SELECT * from grocerylists "
                                 "RIGHT JOIN groceryuser ON grocerylists.id = groceryuser.grocery_list "
                                 "WHERE grocerylists.id = %s", [grocery_list_id])
        if DBHandler.cursor.rowcount > 0:
            DBHandler.cursor.execute("UPDATE groceryUser SET grocery_list = %s WHERE id = %s",
                                     (grocery_list_id, user.id))
            if DBHandler.cursor.statusmessage == "UPDATE 0":  # no rows were modified with UPDATE query
                DBHandler.cursor.execute("INSERT INTO groceryuser (id, grocery_list) VALUES (%s, %s)",
                                         (user.id, grocery_list_id))
            DBHandler.connection.commit()
        else:
            raise ValueError(f"Can't find a grocery list with {grocery_list_id} code")

    @staticmethod
    def get_grocery_items(user: telegram.User):
        DBHandler.cursor.execute("SELECT grocery_list from groceryuser WHERE id = %s ", [user.id])
        if DBHandler.cursor.rowcount != 1:
            return []
        grocery_list_id = DBHandler.cursor.fetchone()[0]
        DBHandler.cursor.execute("SELECT items from grocerylists where id = %s", [grocery_list_id])
        return DBHandler.cursor.fetchone()[0]

    @staticmethod
    def append_grocery_items(user: telegram.User, new_entry: str):
        DBHandler.cursor.execute("SELECT grocery_list from groceryuser WHERE id = %s ", [user.id])
        if DBHandler.cursor.rowcount != 1:
            return
        grocery_list_id = DBHandler.cursor.fetchone()[0]
        DBHandler.cursor.execute('''
            UPDATE grocerylists
            SET items = array_append(items, %s) WHERE id = %s
        ''', (new_entry, grocery_list_id))
        DBHandler.connection.commit()

    @staticmethod
    def clear_grocery_list(user: telegram.User):
        DBHandler.cursor.execute("SELECT grocery_list from groceryuser WHERE id = %s ", [user.id])
        if DBHandler.cursor.rowcount != 1:
            return
        grocery_list_id = DBHandler.cursor.fetchone()[0]
        DBHandler.cursor.execute("UPDATE grocerylists SET items = '{}' WHERE id = %s", [grocery_list_id])
        DBHandler.connection.commit()

    @staticmethod
    def remove_from_list(user: telegram.User, entry: str):
        DBHandler.cursor.execute("SELECT grocery_list from groceryuser WHERE id = %s ", [user.id])
        if DBHandler.cursor.rowcount != 1:
            return
        grocery_list_id = DBHandler.cursor.fetchone()[0]

        DBHandler.cursor.execute("SELECT * from grocerylists WHERE id = %s and %s <@ items", [grocery_list_id, [entry]])
        if DBHandler.cursor.rowcount == 0:
            raise ValueError("No such entry exists in grocery list")

        DBHandler.cursor.execute('''
                    UPDATE grocerylists
                    SET items = array_remove(items, %s) WHERE id = %s
        ''', (entry, grocery_list_id))
        DBHandler.connection.commit()


class UnfinishedCommand:
    def __init__(self, user, chat_id, command_type):
        self.user = user
        self.command_type = command_type
        self.chat_id = chat_id
        UnfinishedCommand.commands.append(self)

    def get_user_id(self):
        return self.user.id

    def finish(self, message):
        UnfinishedCommand.commands.remove(self)
        if self.command_type == "/join":
            try:
                grocery_list_id = int(message.text)
                join_grocery_list(bot, self.user, message.chat_id, grocery_list_id)
                return True
            except ValueError:
                return False
        elif self.command_type == "/remove":
            if is_command(message):
                return False
            else:
                remove_from_grocery_list(bot, self.user, message.chat_id, get_text(message))
                return True
        return False

    commands = []


def is_command(message: telegram.Message):
    for entity in message.entities:
        if entity.type == telegram.MessageEntity.BOT_COMMAND:
            return True
    return False


def get_command(message: telegram.Message):
    for entity in message.entities:
        if entity.type == telegram.MessageEntity.BOT_COMMAND:
            return message.parse_entity(entity)
    return None


def get_text(message: telegram.Message):
    if message.text is None:
        return ""

    if is_command(message):
        try:
            return message.text.split(maxsplit=1)[1]
        except IndexError:
            return ""
    else:
        return message.text


def get_entries(message: telegram.Message):
    return get_text(message).split("\n")


def bot_setup(bot):
    bot.set_my_commands([
        ("join", "Подключиться к списку покупок"),
        ("create", "Создать новый список")
    ], language_code="ru")
    bot.set_my_commands([
        ("join", "Join an existing grocery list"),
        ("create", "Create a new list")
    ], language_code="en")


def set_full_commands(bot, chat_id):
    bot.set_my_commands([
        ("clear", "Clear the grocery list"),
        ("remove", "Remove a specific product from the list"),
        ("check", "See the grocery list"),
        ("join", "Join an existing grocery list"),
        ("create", "Create a new list")
    ], language_code="en", scope=telegram.BotCommandScopeChat(chat_id))
    bot.set_my_commands([
        ("clear", "Очистить список покупок"),
        ("remove", "Убрать предмет из списка"),
        ("check", "Посмотреть список покупок"),
        ("join", "Подключиться к списку покупок"),
        ("create", "Создать новый список")
    ], language_code="ru", scope=telegram.BotCommandScopeChat(chat_id))


def create_grocery_list(bot: telegram.Bot, user, chat_id):
    try:
        grocery_list_code = DBHandler.connect_to_empty_list(user)
        bot.send_message(chat_id, BOTMESSAGES[user.language_code]["/create"].format(code=grocery_list_code))
        set_full_commands(bot, chat_id)
    except ValueError:
        bot.send_message(chat_id, BOTMESSAGES[user.language_code]["create_failed"], parse_mode=telegram.ParseMode.HTML)


def join_grocery_list(bot, user, chat_id, grocery_list_id):
    try:
        DBHandler.connect_to_nonempty_list(user, grocery_list_id)
        bot.send_message(chat_id, BOTMESSAGES[user.language_code]["/join"])
        set_full_commands(bot, chat_id)
    except ValueError:
        bot.send_message(chat_id, BOTMESSAGES[user.language_code]["join_failed"])


def check_grocery_list(bot, user, chat_id):
    items = DBHandler.get_grocery_items(user)
    if len(items) == 0:
        bot.send_message(chat_id, BOTMESSAGES[user.language_code]["empty_list"])
        return
    message_str = ""
    for item in items:
        message_str += item + "\n"
    bot.send_message(chat_id, message_str)


def update_grocery_list(bot, user, chat_id, new_entries):
    for entry in new_entries:
        DBHandler.append_grocery_items(user, entry)
    bot.send_message(chat_id, BOTMESSAGES[user.language_code]["list_updated"])


def clear_grocery_list(bot, user, chat_id):
    DBHandler.clear_grocery_list(user)
    bot.send_message(chat_id, BOTMESSAGES[user.language_code]["list_cleared"])


def remove_from_grocery_list(bot, user, chat_id, entry):
    if entry == "":
        bot.send_message(chat_id, BOTMESSAGES[user.language_code]["remove_wrong_args"])
        return
    try:
        DBHandler.remove_from_list(user, entry)
        bot.send_message(chat_id, BOTMESSAGES[user.language_code]["removed_from_list"])
    except ValueError:
        bot.send_message(chat_id, BOTMESSAGES[user.language_code]["remove_failed"])


async def run(bot):
    updater = ext.Updater(TOKEN)
    await handle_updates(bot, updater.start_polling(0.5))


async def handle_updates(bot: telegram.Bot, update_queue: Queue):
    print("Connected to bot")
    while True:
        update: telegram.Update = update_queue.get()

        if update.callback_query is not None:
            user: telegram.User = update.callback_query.from_user
            if update.callback_query.data == "join":
                bot.send_message(update.callback_query.message.chat_id, BOTMESSAGES[user.language_code]["join_help"])
                UnfinishedCommand(user, update.callback_query.message.chat_id, "/join")
            elif update.callback_query.data == "create":
                create_grocery_list(bot, user, update.callback_query.message.chat_id)
            continue

        if update.message is not None:
            user: telegram.User = update.message.from_user
            command_finished = False
            for unfinished_command in UnfinishedCommand.commands:
                print(unfinished_command.get_user_id())
                if unfinished_command.get_user_id() == user.id:
                    command_finished = unfinished_command.finish(update.message)
                    break
            if command_finished:
                continue

            if get_command(update.message) == "/start":
                inline_markup = telegram.InlineKeyboardMarkup([
                    [telegram.InlineKeyboardButton("/join", callback_data="join")],
                    [telegram.InlineKeyboardButton("/create", callback_data="create")]
                ])
                bot.send_message(update.message.chat_id, BOTMESSAGES[user.language_code]["/start"],
                                 reply_markup=inline_markup)
            elif get_command(update.message) == "/create":
                create_grocery_list(bot, user, update.message.chat_id)
            elif get_command(update.message) == "/join":
                if get_text(update.message) == "":  # perform command with two separate messages
                    bot.send_message(update.message.chat_id, BOTMESSAGES[user.language_code]["join_help"])
                    UnfinishedCommand(user, update.message.chat_id, "/remove")
                else:  # perform command with one message
                    try:
                        grocery_list_id = int(get_text(update.message))
                        join_grocery_list(bot, user, update.message.chat_id, grocery_list_id)
                    except ValueError:
                        bot.send_message(update.message.chat_id, BOTMESSAGES[user.language_code]["join_wrong_args"])
            elif get_command(update.message) == "/check":
                check_grocery_list(bot, user, update.message.chat_id)
            elif get_command(update.message) == "/clear":
                clear_grocery_list(bot, user, update.message.chat_id)
            elif get_command(update.message) == "/remove":
                if get_text(update.message) == "":  # perform command with two separate messages
                    bot.send_message(update.message.chat_id, BOTMESSAGES[user.language_code]["remove_help"])
                    UnfinishedCommand(user, update.message.chat_id, "/remove")
                else:  # perform command with one message
                    remove_from_grocery_list(bot, user, update.message.chat_id, get_text(update.message))
            elif get_text(update.message) != "":
                update_grocery_list(bot, user, update.message.chat_id, get_entries(update.message))


DBHandler.init(DBNAME, "postgres", DBPASSWORD)
bot = telegram.Bot(TOKEN)
asyncio.run(run(bot))

