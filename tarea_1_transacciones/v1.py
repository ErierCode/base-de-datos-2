import oracledb
from datetime import datetime

def pagar_mensualidad(alumno_id, mes_id, monto):

    connection = oracledb.connect(
        user="alumno",
        password="Umg$2026",
        dsn="localhost:1521/umgXDB"
    )

    cursor = connection.cursor()

    try:
        # Bloquear fila
        cursor.execute("""
            SELECT saldo_semestre
            FROM alumno
            WHERE id = :1
            FOR UPDATE
        """, [alumno_id])

        row = cursor.fetchone()

        if not row:
            raise Exception("Alumno no existe")

        saldo = row[0]

        if saldo < monto:
            raise Exception("Saldo insuficiente")

        # Actualizar saldo
        cursor.execute("""
            UPDATE alumno
            SET saldo_semestre = saldo_semestre - :1
            WHERE id = :2
        """, [monto, alumno_id])

        # Insertar pago
        cursor.execute("""
            INSERT INTO pago (id, alumno_id, mes_id, monto, fecha_pago)
            VALUES (pago_seq.NEXTVAL, :1, :2, :3, :4)
        """, [alumno_id, mes_id, monto, datetime.now()])

        connection.commit()
        print("Pago realizado correctamente")

    except Exception as e:
        connection.rollback()
        print("Error:", e)

    finally:
        cursor.close()
        connection.close()


pagar_mensualidad(1, 2, 1000)