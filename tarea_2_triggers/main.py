import oracledb


def get_connection():
    return oracledb.connect(
        user="alumno",
        password="Umg$2026",
        dsn="localhost:1521/umgXDB"
    )

def listar_productos():
    con = get_connection()
    cur = con.cursor()

    cur.execute("""
        SELECT id, nombre, precio, stock_actual
        FROM producto
        ORDER BY id
    """)

    productos = cur.fetchall()

    print("\n========== INVENTARIO ==========")
    if not productos:
        print("No hay productos registrados.")
    else:
        for p in productos:
            print(f"ID: {p[0]} | Nombre: {p[1]} | Precio: Q{p[2]} | Stock: {p[3]}")
    print("================================\n")

    cur.close()
    con.close()


def crear_producto(nombre, precio):
    con = get_connection()
    cur = con.cursor()

    try:
        cur.callproc("crear_producto", [nombre, precio])
        print("✅ Producto creado correctamente.")
    except Exception as e:
        print("❌ Error:", e)

    cur.close()
    con.close()


def registrar_entrada(producto_id, cantidad):
    con = get_connection()
    cur = con.cursor()

    try:
        cur.callproc("registrar_entrada", [producto_id, cantidad])
        print("✅ Entrada registrada correctamente.")
    except Exception as e:
        print("❌ Error:", e)

    cur.close()
    con.close()

    listar_productos()

def registrar_salida(producto_id, cantidad):
    con = get_connection()
    cur = con.cursor()

    try:
        cur.callproc("registrar_salida", [producto_id, cantidad])
        print("✅ Salida registrada correctamente.")
    except Exception as e:
        print("❌ Error:", e)

    cur.close()
    con.close()

    listar_productos() 

def menu():
    while True:
        print("\n========= SISTEMA DE INVENTARIO =========")
        print("1. Crear Producto")
        print("2. Registrar Entrada")
        print("3. Registrar Salida")
        print("4. Ver Inventario")
        print("5. Salir")

        op = input("Seleccione una opción: ")

        if op == "1":
            nombre = input("Nombre del producto: ")

            try:
                precio = float(input("Precio: "))
                crear_producto(nombre, precio)
            except ValueError:
                print("❌ Precio inválido.")

        elif op == "2":
            listar_productos()
            try:
                pid = int(input("Ingrese ID del producto: "))
                cant = int(input("Cantidad a ingresar: "))
                registrar_entrada(pid, cant)
            except ValueError:
                print("❌ Datos inválidos.")

        elif op == "3":
            listar_productos()
            try:
                pid = int(input("Ingrese ID del producto: "))
                cant = int(input("Cantidad a retirar: "))
                registrar_salida(pid, cant)
            except ValueError:
                print("❌ Datos inválidos.")

        elif op == "4":
            listar_productos()

        elif op == "5":
            print("Saliendo del sistema...")
            break

        else:
            print("❌ Opción inválida.")


if __name__ == "__main__":
    menu()
