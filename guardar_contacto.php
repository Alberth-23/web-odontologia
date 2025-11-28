<?php
$conexion = new mysqli("localhost", "root", "", "clinica");

if ($conexion->connect_error) {
    die("Error de conexión: " . $conexion->connect_error);
}

$nombre = $_POST['nombre'];
$correo = $_POST['correo'];
$asunto = $_POST['asunto'];
$mensaje = $_POST['mensaje'];

$sql = "INSERT INTO contactos (nombre, correo, asunto, mensaje, fecha)
        VALUES ('$nombre', '$correo', '$asunto', '$mensaje', NOW())";

if ($conexion->query($sql)) {
    echo "OK";
} else {
    echo "Error: " . $conexion->error;
}

$conexion->close();
?>
