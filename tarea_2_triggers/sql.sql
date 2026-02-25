CREATE TABLE producto (
    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR2(100) NOT NULL,
    precio NUMBER(10,2) NOT NULL,
    stock_actual NUMBER DEFAULT 0
);

CREATE TABLE entrada (
    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producto_id NUMBER,
    cantidad NUMBER NOT NULL,
    fecha DATE DEFAULT SYSDATE,
    CONSTRAINT fk_entrada_producto
        FOREIGN KEY (producto_id)
        REFERENCES producto(id)
);

CREATE TABLE salida (
    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producto_id NUMBER,
    cantidad NUMBER NOT NULL,
    fecha DATE DEFAULT SYSDATE,
    CONSTRAINT fk_salida_producto
        FOREIGN KEY (producto_id)
        REFERENCES producto(id)
);

CREATE OR REPLACE PROCEDURE crear_producto (
    p_nombre IN VARCHAR2,
    p_precio IN NUMBER
)
AS
BEGIN
    INSERT INTO producto (nombre, precio)
    VALUES (p_nombre, p_precio);

    COMMIT;
END;
/

CREATE OR REPLACE PROCEDURE registrar_entrada (
    p_producto_id IN NUMBER,
    p_cantidad IN NUMBER
)
AS
BEGIN
    INSERT INTO entrada (producto_id, cantidad)
    VALUES (p_producto_id, p_cantidad);

    COMMIT;
END;
/

CREATE OR REPLACE PROCEDURE registrar_salida (
    p_producto_id IN NUMBER,
    p_cantidad IN NUMBER
)
AS
    v_stock NUMBER;
BEGIN

    SELECT stock_actual INTO v_stock
    FROM producto
    WHERE id = p_producto_id
    FOR UPDATE;

    IF v_stock < p_cantidad THEN
        RAISE_APPLICATION_ERROR(-20001, 'Stock insuficiente');
    END IF;

    INSERT INTO salida (producto_id, cantidad)
    VALUES (p_producto_id, p_cantidad);

    COMMIT;
END;
/

CREATE OR REPLACE TRIGGER trg_entrada_stock
AFTER INSERT ON entrada
FOR EACH ROW
BEGIN
    UPDATE producto
    SET stock_actual = stock_actual + :NEW.cantidad
    WHERE id = :NEW.producto_id;
END;
/

CREATE OR REPLACE TRIGGER trg_salida_stock
AFTER INSERT ON salida
FOR EACH ROW
BEGIN
    UPDATE producto
    SET stock_actual = stock_actual - :NEW.cantidad
    WHERE id = :NEW.producto_id;
END;
/