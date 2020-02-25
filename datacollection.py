import datetime
import securityclass
import sqlite3
import shelve

insert_sql = "INSERT INTO histories VALUES (?, ?, ?, ?, ?)"
insert_chain_sql = "INSERT INTO chains VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
chain_update_sql = "UPDATE chains SET sequence = sequence + 1"
delete_sql = "DELETE FROM chains WHERE sequence > 15"

db = sqlite3.connect('GEXHISTORICAL.sqlite')
cursor = db.cursor()


def collect():
    date = str(datetime.date.today())
    MSFT = securityclass.Security('MSFT')
    SPX = securityclass.Security('$SPX.X')

    try:
        cursor.execute(insert_sql, (date, str(MSFT.price), int(round(MSFT.gex)), int(round(MSFT.dollar_gamma)), 2))
        cursor.execute(insert_sql, (date, str(SPX.price), int(round(SPX.gex)), int(round(SPX.dollar_gamma)), 1))
    except sqlite3.IntegrityError:
        print('Unique Constraint Failed - Data has already been entered for this date.')

    return MSFT, SPX


def collect_chains(msft, spx):
    def update():
        cursor.execute(chain_update_sql)
        cursor.execute(delete_sql)
    update()
    date = str(datetime.date.today())
    securities = [msft, spx]
    for security in securities:
        for item in security.expirations:
            contract_obj = security.expirations[item]
            for strike in contract_obj.calls:
                call_obj = contract_obj.calls[strike]
                cdg = call_obj.gex * float(security.price)
                put_obj = contract_obj.puts[strike]
                pdg = put_obj.gex * float(security.price)

                sym = security.symbol
                num = 1
                if sym == 'MSFT':
                    num = 2

                try:
                    cursor.execute(insert_chain_sql, (num, call_obj.symbol, date, 'CALL', contract_obj.date, call_obj.strike_price, int(round(cdg)), int(call_obj.volume), 0))
                    cursor.execute(insert_chain_sql, (num, put_obj.symbol, date, 'PUT', contract_obj.date, put_obj.strike_price, int(round(pdg)), int(put_obj.volume), 0))
                except sqlite3.IntegrityError:
                    print('Unique Constraint Failed - Data has already been entered for this date.')


MSFT, SPX = collect()

cursor.execute('SELECT * FROM histories ORDER BY date')
for row in cursor:
    print(row)
user = input('Commit? (y/n): ')
if user == 'y':
    cursor.connection.commit()
    print('COMMITTED')
else:
    cursor.close()
    print('NOT COMMITTED')
cursor = db.cursor()
collect_chains(MSFT, SPX)
cursor.execute('SELECT * FROM chains ORDER BY sequence')

for row in cursor:
    print(row)
user = input('Commit? (y/n): ')
if user == 'y':
    cursor.connection.commit()
    print('COMMITTED')
else:
    print('NOT COMMITTED')

cursor.close()
db.close()



















