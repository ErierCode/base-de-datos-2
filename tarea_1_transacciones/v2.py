import oracledb
from datetime import datetime

def get_connection():
    return oracledb.connect(
        user="alumno",
        password="Umg$2026",
        dsn="localhost:1521/umgXDB"
    )

def listar_alumnos(cursor):
    cursor.execute("SELECT id, nombre, saldo_semestre FROM alumno ORDER BY id")
    return cursor.fetchall()

def listar_meses(cursor):
    cursor.execute("""
        SELECT id, nombre_mes 
        FROM mes 
        ORDER BY numero_mes
    """)
    return cursor.fetchall()

def pagar_mensualidad(alumno_id, mes_id, monto):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT saldo_semestre, nombre
            FROM alumno
            WHERE id = :1
            FOR UPDATE
        """, [alumno_id])

        row = cursor.fetchone()

        if not row:
            raise Exception("Alumno no existe")

        saldo_actual = row[0]
        nombre = row[1]

        if saldo_actual < monto:
            raise Exception("Saldo insuficiente")

        cursor.execute("""
            UPDATE alumno
            SET saldo_semestre = saldo_semestre - :1
            WHERE id = :2
        """, [monto, alumno_id])

        cursor.execute("""
            INSERT INTO pago (id, alumno_id, mes_id, monto, fecha_pago)
            VALUES (pago_seq.NEXTVAL, :1, :2, :3, :4)
        """, [alumno_id, mes_id, monto, datetime.now()])

        connection.commit()

        saldo_restante = saldo_actual - monto

        print("\n===== RESUMEN DE PAGO =====")
        print(f"Alumno: {nombre}")
        print(f"Monto pagado: Q{monto}")
        print(f"Saldo restante: Q{saldo_restante}")
        print("============================\n")

    except Exception as e:
        connection.rollback()
        print("Error:", e)

    finally:
        cursor.close()
        connection.close()


# -----------------------
# PROGRAMA PRINCIPAL
# -----------------------

connection = get_connection()
cursor = connection.cursor()

print("\n=== LISTA DE ALUMNOS ===")
alumnos = listar_alumnos(cursor)

for alumno in alumnos:
    print(f"{alumno[0]} - {alumno[1]} (Saldo: Q{alumno[2]})")

alumno_id = int(input("\nIngrese el ID del alumno: "))

print("\n=== LISTA DE MESES ===")
meses = listar_meses(cursor)

for mes in meses:
    print(f"{mes[0]} - {mes[1]}")

mes_id = int(input("\nIngrese el ID del mes a pagar: "))
monto = float(input("Ingrese el monto a pagar: "))

cursor.close()
connection.close()

pagar_mensualidad(alumno_id, mes_id, monto)