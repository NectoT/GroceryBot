import psycopg2
from constants import DBNAME, DBPASSWORD

connection = psycopg2.connect("dbname={0} user=postgres password={1}".format(DBNAME, DBPASSWORD))
cursor = connection.cursor()
cursor.execute(
    '''CREATE TABLE groceryLists (
        id integer PRIMARY KEY,
        items text[] DEFAULT array[]::text[]
    );

    CREATE TABLE groceryUser (
        id integer PRIMARY KEY,
        grocery_list integer REFERENCES groceryLists (id) ON DELETE CASCADE
    );'''
)

for i in range(1000, 10000):
    cursor.execute('INSERT INTO groceryLists (id) VALUES (%s);', [i])

connection.commit()
cursor.close()
connection.close()