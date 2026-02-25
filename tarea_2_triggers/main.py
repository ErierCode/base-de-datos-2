import oracledb


def get_connection():
    return oracledb.connect(
        user="alumno",
        password="Umg$2026",
        dsn="localhost:1521/umgXDB"
    )


def crear_producto(nombre, precio):
    con = get_connection()
    cur = con.cursor()
    cur.callproc("crear_producto", [nombre, precio])
    print("Producto creado correctamente")
    cur.close()
    con.close()


def registrar_entrada(producto_id, cantidad):
    con = get_connection()
    cur = con.cursor()
    cur.callproc("registrar_entrada", [producto_id, cantidad])
    print("Entrada registrada")
    cur.close()
    con.close()


def registrar_salida(producto_id, cantidad):
    con = get_connection()
    cur = con.cursor()
    try:
        cur.callproc("registrar_salida", [producto_id, cantidad])
        print("Salida registrada")
    except Exception as e:
        print("Error:", e)
    cur.close()
    con.close()


def menu():
    while True:
        print("\n1. Crear Producto")
        print("2. Registrar Entrada")
        print("3. Registrar Salida")
        print("4. Salir")

        op = input("Seleccione: ")

        if op == "1":
            nombre = input("Nombre: ")
            precio = float(input("Precio: "))
            crear_producto(nombre, precio)

        elif op == "2":
            pid = int(input("ID Producto: "))
            cant = int(input("Cantidad: "))
            registrar_entrada(pid, cant)

        elif op == "3":
            pid = int(input("ID Producto: "))
            cant = int(input("Cantidad: "))
            registrar_salida(pid, cant)

        elif op == "4":
            break


if __name__ == "__main__":
    menu()
