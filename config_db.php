<?php
declare(strict_types=1);

// ==============================================
// CONEXIÓN DIRECTA A ferrestock
// ==============================================

$DB_HOST = '127.0.0.1';
$DB_NAME = 'ferrestock';
$DB_USER = 'root';
$DB_PASS = '';
$DB_PORT = '3306';

try {
    $dsn = "mysql:host={$DB_HOST};port={$DB_PORT};dbname={$DB_NAME};charset=utf8mb4";

    $pdo = new PDO($dsn, $DB_USER, $DB_PASS, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);

} catch (PDOException $e) {
    http_response_code(500);
    exit("Error de conexión a la base de datos.");
}

// ==============================================
// FUNCIÓN PARA OBTENER PDO
// ==============================================

function getPDO(): PDO {
    global $pdo;
    return $pdo;
}

// ==============================================
// CREAR ADMIN POR DEFECTO SI NO EXISTE
// ==============================================

function ensureDefaultAdmin(): void {
    $pdo = getPDO();

    $stmt = $pdo->query("SELECT COUNT(*) AS total FROM usuarios");
    $row = $stmt->fetch();

    if ($row && $row['total'] == 0) {

        $hash = password_hash('123456', PASSWORD_DEFAULT);

        $insert = $pdo->prepare("
            INSERT INTO usuarios (nombre, usuario, clave, rol)
            VALUES (?, ?, ?, ?)
        ");

        $insert->execute([
            'Administrador',
            'admin',
            $hash,
            'admin'
        ]);
    }
}

// ==============================================
// PROBAR CONEXIÓN
// ==============================================

function testConnection(): bool {
    try {
        $pdo = getPDO();
        $pdo->query("SELECT 1");
        return true;
    } catch (Exception $e) {
        return false;
    }
}
