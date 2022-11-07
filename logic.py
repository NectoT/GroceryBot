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
        "remove_wrong_args": "This command expects an item to remove. Example: /remove Milk",
        "forgot_current_list": "This list won't be shown to you anymore",
        "forgot_list": "List {identifier} won't be shown to you anymore",
        "forget_wrong_list": "It seems there's no list with such name",
        "no_lists": "You don't have any lists",
        "moved_to": "You've moved to list {identifier}",
        "numeric_name": "Grocery list's name can't be a number",
        "name_help": "Type in a new name for this list",
        "named_list": "This list's name has been set",
        "current_lists": "Here are your current lists"
    },
    "ru": {
        "/start": "Нажмите /join, чтобы присоединиться к существующему списку, или создайте новый с помощью /start",
        "/join": "Вы подключились к списку покупок. Используйте /check, чтобы узнать его содержимое. Вы можете добавить "
                 "новые предметы с помощью команды /add, или просто отправить сообщение с новым предметом. Если вы хотите"
                 " добавить сразу несколько предметов, напишите каждый из них на отдельной строке",
        "join_help": "Введите код списка, к которому вы хотите подключиться",
        "join_failed": "Кажется, списка с таким кодом не существует",
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
        "remove_wrong_args": "Вы должны указать предмет, который хотите удалить. Пример: /remove Milk",
        "forgot_current_list": "Вам больше не будет показываться этот список",
        "forgot_list": "Вам больше не будет показываться список {identifier}",
        "forget_wrong_list": "Кажется, такого списка не существует",
        "no_lists": "You don't have any lists",
        "moved_to": "Вы перешли в список {identifier}",
        "numeric_name": "Имя списка покупок не может быть числом",
        "name_help": "Введите новое имя для этого списка",
        "named_list": "Вы успешно назначили имя этому списку",
        "current_lists": "Вот ваши текущие списки"
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
    def user_exists(user: telegram.User):
        DBHandler.cursor.execute("SELECT * from groceryuser WHERE id = %s ", [user.id])
        return DBHandler.cursor.rowcount == 1

    @staticmethod
    def update_user_last_message(user: telegram.User, date):
        if not DBHandler.user_exists(user):
            return
        DBHandler.cursor.execute("UPDATE groceryuser SET last_message = %s WHERE id = %s", [date, user.id])

    @staticmethod
    def connect_to_empty_list(user: telegram.User):
        DBHandler.cursor.execute(
            "SELECT * from grocerylists WHERE grocerylists.id NOT IN (SELECT list_id from lists_user)")
        grocery_list = random.sample(DBHandler.cursor.fetchall(), 1)[0]

        DBHandler.cursor.execute("UPDATE grocerylists SET items = '{}' WHERE id = %s", [grocery_list[0]])

        DBHandler.cursor.execute("SELECT * from groceryuser WHERE id = %s", [user.id])
        if DBHandler.cursor.rowcount == 0:
            DBHandler.cursor.execute("INSERT INTO groceryuser (id, current_list) VALUES (%s, %s)",
                                     (user.id, grocery_list[0]))
        else:
            DBHandler.cursor.execute("UPDATE groceryUser SET current_list = %s WHERE id = %s",
                                     (grocery_list[0], user.id))
        DBHandler.cursor.execute("INSERT INTO lists_user (user_id, list_id) VALUES (%s, %s)",
                                 (user.id, grocery_list[0]))
        DBHandler.connection.commit()
        return grocery_list[0]

    @staticmethod
    def connect_to_nonempty_list(user: telegram.User, grocery_list_id):
        DBHandler.cursor.execute("SELECT * from grocerylists WHERE id = %s and id IN (SELECT list_id from lists_user)",
                                 [grocery_list_id])
        if DBHandler.cursor.rowcount == 0:
            raise ValueError(f"Can't find a grocery list with {grocery_list_id} code")

        DBHandler.cursor.execute("SELECT * from groceryuser WHERE id = %s", [user.id])
        if DBHandler.cursor.rowcount == 0:
            DBHandler.cursor.execute("INSERT INTO groceryuser (id, current_list) VALUES (%s, %s)",
                                     (user.id, grocery_list_id))
        else:
            DBHandler.cursor.execute("UPDATE groceryUser SET current_list = %s WHERE id = %s",
                                     (grocery_list_id, user.id))
        DBHandler.cursor.execute("SELECT * from lists_user WHERE user_id = %s and list_id = %s",
                                 (user.id, grocery_list_id))
        if DBHandler.cursor.rowcount == 0:  # check that this user wasn't already in this grocery list
            DBHandler.cursor.execute("INSERT INTO lists_user (user_id, list_id) VALUES (%s, %s)",
                                    (user.id, grocery_list_id))
        DBHandler.connection.commit()

    @staticmethod
    def forget_list(user: telegram.User, grocery_list_id=None, grocery_list_alias=None):
        if not DBHandler.user_exists(user):
            raise ReferenceError("User doesn't have any lists")
        if grocery_list_id is None and grocery_list_alias is None:
            raise KeyError("Insufficient arguments provided")

        if grocery_list_id is None:
            DBHandler.cursor.execute("SELECT list_id from lists_user WHERE user_id = %s and list_name = %s",
                                     (user.id, grocery_list_alias))
            if DBHandler.cursor.rowcount == 0:
                raise ValueError("No lists found with such name")
            grocery_list_id = DBHandler.cursor.fetchone()[0]

        DBHandler.cursor.execute("SELECT current_list from groceryuser WHERE id = %s", [user.id])
        current_list = DBHandler.cursor.fetchone()[0]
        if current_list == grocery_list_id:
            DBHandler.forget_current_list(user)
        else:
            DBHandler.cursor.execute('''
                            DELETE FROM lists_user WHERE user_id = %s and list_id = %s
                        ''', (user.id, grocery_list_id))
            DBHandler.connection.commit()

    @staticmethod
    def forget_current_list(user: telegram.User):
        if not DBHandler.user_exists(user):
            raise ReferenceError("User doesn't have any lists")
        DBHandler.cursor.execute("SELECT current_list FROM groceryuser WHERE id = %s", [user.id])
        list_id = DBHandler.cursor.fetchone()[0]
        DBHandler.cursor.execute('''
                        DELETE FROM lists_user WHERE user_id = %s and list_id = %s ''', (user.id, list_id))
        DBHandler.cursor.execute("SELECT * FROM lists_user WHERE user_id = %s", [user.id])
        if DBHandler.cursor.rowcount == 0:
            DBHandler.cursor.execute("DELETE FROM groceryuser WHERE id = %s", [user.id])
        DBHandler.connection.commit()

    @staticmethod
    def move_to_list(user: telegram.User, grocery_list_id=None, grocery_list_alias=None):
        if grocery_list_id is None and grocery_list_alias is None:
            raise KeyError("Insufficient arguments provided")
        if grocery_list_id is None:
            DBHandler.cursor.execute("SELECT list_id from lists_user WHERE user_id = %s and list_name = %s",
                                     (user.id, grocery_list_alias))
            if DBHandler.cursor.rowcount == 0:
                raise ValueError("User is not connected to this list")
            grocery_list_id = DBHandler.cursor.fetchone()[0]

        DBHandler.cursor.execute("SELECT list_id from lists_user WHERE user_id = %s and list_id = %s",
                                 (user.id, grocery_list_id))
        if DBHandler.cursor.rowcount == 0:
            raise ValueError("User is not connected to this list")
        DBHandler.cursor.execute('''
            UPDATE groceryuser SET current_list = %s WHERE id = %s
        ''', (grocery_list_id, user.id))
        DBHandler.connection.commit()

    @staticmethod
    def name_current_list(user: telegram.User, grocery_list_alias):
        if not DBHandler.user_exists(user):
            return
        DBHandler.cursor.execute("SELECT current_list from groceryuser WHERE id = %s", [user.id])
        grocery_list_id = DBHandler.cursor.fetchone()[0]
        DBHandler.cursor.execute("UPDATE lists_user SET list_name = %s WHERE user_id = %s and list_id = %s",
                                 (grocery_list_alias, user.id, grocery_list_id))
        DBHandler.connection.commit()

    @staticmethod
    def get_users_lists(user: telegram.User):  # returns a tuple of list_id, list_alias
        if not DBHandler.user_exists(user):
            return []
        DBHandler.cursor.execute("SELECT * from lists_user WHERE user_id = %s", [user.id])
        rows = DBHandler.cursor.fetchall()
        return [(row[0], row[2]) for row in rows]

    @staticmethod
    def get_grocery_items(user: telegram.User):
        DBHandler.cursor.execute("SELECT current_list from groceryuser WHERE id = %s ", [user.id])
        if DBHandler.cursor.rowcount != 1:
            return []
        grocery_list_id = DBHandler.cursor.fetchone()[0]
        DBHandler.cursor.execute("SELECT items from grocerylists where id = %s", [grocery_list_id])
        return DBHandler.cursor.fetchone()[0]

    @staticmethod
    def append_grocery_items(user: telegram.User, new_entry: str):
        DBHandler.cursor.execute("SELECT current_list from groceryuser WHERE id = %s ", [user.id])
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
        DBHandler.cursor.execute("SELECT current_list from groceryuser WHERE id = %s ", [user.id])
        if DBHandler.cursor.rowcount != 1:
            return
        grocery_list_id = DBHandler.cursor.fetchone()[0]
        DBHandler.cursor.execute("UPDATE grocerylists SET items = '{}' WHERE id = %s", [grocery_list_id])
        DBHandler.connection.commit()

    @staticmethod
    def remove_from_list(user: telegram.User, entry: str):
        DBHandler.cursor.execute("SELECT current_list from groceryuser WHERE id = %s ", [user.id])
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
        if is_command(message):
            return False
        if self.command_type == "/join":
            try:
                grocery_list_id = int(message.text)
                join_grocery_list(bot, self.user, message.chat_id, grocery_list_id)
                return True
            except ValueError:
                return False
        elif self.command_type == "/remove":
            remove_from_grocery_list(bot, self.user, message.chat_id, get_text(message))
            return True
        elif self.command_type == "/name":
            name_grocery_list(bot, self.user, message.chat_id, get_text(message))
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
        ("create", "Create a new list"),
        ("forget", "Forget the current list, or forget another list if you provide its name or code"),  # leave
        ("show", "Show all the lists you have"),
        ("name", "Name your current list"),
    ], language_code="en", scope=telegram.BotCommandScopeChat(chat_id))
    bot.set_my_commands([
        ("clear", "Очистить список покупок"),
        ("remove", "Убрать предмет из списка"),
        ("check", "Посмотреть список покупок"),
        ("join", "Подключиться к списку покупок"),
        ("create", "Создать новый список"),
        ("forget", "Забыть об этом списке, или другом, если вы укажете его имя или номер"),
        ("show", "Показать все списки, которые у вас есть"),
        ("name", "Назвать текущий список")
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


def move_to_list(bot, user, chat_id, grocery_list_identifier: str):
    try:
        if grocery_list_identifier.isnumeric():
            DBHandler.move_to_list(user, grocery_list_id=int(grocery_list_identifier))
            bot.send_message(chat_id, BOTMESSAGES[user.language_code]["moved_to"].format(
                identifier=grocery_list_identifier))
        else:
            DBHandler.move_to_list(user, grocery_list_alias=grocery_list_identifier)
            bot.send_message(chat_id, BOTMESSAGES[user.language_code]["moved_to"].format(
                identifier="'" + grocery_list_identifier + "'"))
        check_grocery_list(bot, user, chat_id)
    except ValueError:
        pass  # silently ignore this error: from user's perspective an old button just won't work, which is fine


def forget_grocery_list(bot, user, chat_id, grocery_list_identifier: str):
    try:
        if grocery_list_identifier == "":
            DBHandler.forget_current_list(user)
            bot.send_message(chat_id, BOTMESSAGES[user.language_code]["forgot_current_list"])

            user_lists = DBHandler.get_users_lists(user)
            if len(user_lists) > 0:
                if user_lists[0][1] is not None:
                    move_to_list(bot, user, chat_id, grocery_list_identifier=user_lists[0][1])
                else:
                    move_to_list(bot, user, chat_id, grocery_list_identifier=str(user_lists[0][0]))
        elif grocery_list_identifier.isnumeric():
            DBHandler.forget_list(user, grocery_list_id=int(grocery_list_identifier))
            bot.send_message(chat_id, BOTMESSAGES[user.language_code]["forgot_list"].format(
                identifier="#" + grocery_list_identifier))
        else:
            DBHandler.forget_list(user, grocery_list_alias=grocery_list_identifier)
            bot.send_message(chat_id, BOTMESSAGES[user.language_code]["forgot_list"].format(
                identifier="'" + grocery_list_identifier + "'"))
    except ReferenceError:
        bot.send_message(chat_id, BOTMESSAGES[user.language_code]["no_lists"])
    except ValueError:
        bot.send_message(chat_id, BOTMESSAGES[user.language_code]["forget_wrong_list"])


def name_grocery_list(bot, user, chat_id, grocery_list_alias: str):
    if grocery_list_alias.isnumeric():
        bot.send_message(chat_id, BOTMESSAGES[user.language_code]["numeric_name"])
        return
    DBHandler.name_current_list(user, grocery_list_alias)
    bot.send_message(chat_id, BOTMESSAGES[user.language_code]["named_list"])


def get_lists(bot, user, chat_id):
    markup_rows = []
    lists = DBHandler.get_users_lists(user)
    for grocery_list in lists:
        if grocery_list[1] is None:
            button_text = str(grocery_list[0])
            data = "/move " + str(grocery_list[0])
        else:
            button_text = grocery_list[1] + " (" + str(grocery_list[0]) + ")"
            data = "/move " + grocery_list[1]
        markup_rows.append([telegram.InlineKeyboardButton(button_text, callback_data=data)])
    inline_markup = telegram.InlineKeyboardMarkup(markup_rows)
    bot.send_message(chat_id, BOTMESSAGES[user.language_code]["current_lists"],
                     reply_markup=inline_markup)


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
            DBHandler.update_user_last_message(user, update.callback_query.message.date)
            if update.callback_query.data == "join":
                bot.send_message(update.callback_query.message.chat_id, BOTMESSAGES[user.language_code]["join_help"])
                UnfinishedCommand(user, update.callback_query.message.chat_id, "/join")
            elif update.callback_query.data == "create":
                create_grocery_list(bot, user, update.callback_query.message.chat_id)
            elif update.callback_query.data.split()[0] == "/move":
                move_to_list(bot, user,
                             update.callback_query.message.chat_id, update.callback_query.data.split(maxsplit=1)[1])
            continue

        if update.message is not None:
            user: telegram.User = update.message.from_user
            DBHandler.update_user_last_message(user, update.message.date)
            command_finished = False
            for unfinished_command in UnfinishedCommand.commands:
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
                    UnfinishedCommand(user, update.message.chat_id, "/join")
                else:  # perform command with one message
                    try:
                        grocery_list_id = int(get_text(update.message))
                        join_grocery_list(bot, user, update.message.chat_id, grocery_list_id)
                    except ValueError:
                        bot.send_message(update.message.chat_id, BOTMESSAGES[user.language_code]["join_wrong_args"])
            elif get_command(update.message) == "/forget":
                forget_grocery_list(bot, user, update.message.chat_id, get_text(update.message))
            elif get_command(update.message) == "/show":
                get_lists(bot, user, update.message.chat_id)
            elif get_command(update.message) == "/name":
                if get_text(update.message) == "":  # perform command with two separate messages
                    bot.send_message(update.message.chat_id, BOTMESSAGES[user.language_code]["name_help"])
                    UnfinishedCommand(user, update.message.chat_id, "/name")
                else:  # perform command with one message
                    name_grocery_list(bot, user, update.message.chat_id, get_text(update.message))
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

