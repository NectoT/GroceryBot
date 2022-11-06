import psycopg2
from psycopg2.errors import UndefinedTable
from constants import DBNAME, DBPASSWORD


VALID_ID = 1  # increment if changes to db needs to be made


def valid():
    connection = psycopg2.connect("dbname={0} user=postgres host='localhost' password={1}".format(DBNAME, DBPASSWORD))
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT id from valid where id = %s", [VALID_ID])
        cursor.close()
        connection.close()

        return cursor.rowcount == 1
    except UndefinedTable:
        cursor.close()
        connection.close()
        return False


# Use this to tell manager what needs to be updated in the server database
# (You can update your database manually just fine, this function exists for manager auto updating from GitHub)
def update():
    connection = psycopg2.connect("dbname={0} user=postgres host='localhost' password={1}".format(DBNAME, DBPASSWORD))
    cursor = connection.cursor()
    cursor.execute('''
        UPDATE valid SET id = 1;
    
        ALTER TABLE groceryUser RENAME COLUMN grocery_list TO current_list;
        ALTER TABLE groceryUser ADD COLUMN last_message date;
        UPDATE groceryUser SET last_message = CURRENT_DATE;
        
        CREATE TABLE lists_user (
            list_id integer REFERENCES groceryLists (id) ON DELETE CASCADE,
            user_id integer REFERENCES groceryUser (id),
            list_name text
        );
    ''', [VALID_ID])
    connection.commit()
    cursor.close()
    connection.close()


if __name__ == "main":
    connection = psycopg2.connect("dbname={0} user=postgres host='localhost' password={1}".format(DBNAME, DBPASSWORD))
    cursor = connection.cursor()

    # deleting old version if existed
    cursor.execute('''
        DROP TABLE IF EXISTS groceryLists;
        DROP TABLE IF EXISTS groceryUser;
        DROP TABLE IF EXISTS valid;
    ''')

    cursor.execute(
        '''CREATE TABLE groceryLists (
            id integer PRIMARY KEY,
            items text[] DEFAULT array[]::text[]
        );
    
        CREATE TABLE groceryUser (
            id integer PRIMARY KEY,
            last_message date,
            current_list integer REFERENCES groceryLists (id)
        );
        
        CREATE TABLE lists_user (
            list_id integer REFERENCES groceryLists (id) ON DELETE CASCADE,
            user_id integer REFERENCES groceryUser (id),
            list_name text
        );
        
        CREATE TABLE valid {
            id integer PRIMARY KEY
        };
        
        INSERT INTO valid VALUES (%s)''', [VALID_ID]
    )

    for i in range(1000, 10000):
        cursor.execute('INSERT INTO groceryLists (id) VALUES (%s);', [i])

    connection.commit()
    cursor.close()
    connection.close()