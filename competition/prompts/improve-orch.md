Orquesta esto con subagent-pool (procede sin project-context; el proyecto no tiene .claude/project-context.md):

Hola, quiero mejorar la seguridad del login de kuNNA antes de exponerlo fuera de mi red.

Ahora mismo el login por código de Google Authenticator (`POST /api/auth/login`) acepta intentos sin límite: si alguien prueba códigos de 6 dígitos, cada fallo solo espera 1 segundo y puede seguir probando. Quiero que tras unos pocos fallos seguidos el login se bloquee un rato.

Lo que necesito:

- Después de como máximo 10 intentos fallidos seguidos, el login responde 429 en vez de 401, y el bloqueo dura al menos 1 minuto.
- Durante el bloqueo, ni siquiera un código correcto abre sesión: sigue respondiendo 429.
- El bloqueo es temporal: cuando pase el tiempo, el login con el código correcto vuelve a funcionar.
- Un login correcto normal (y 2 o 3 fallos aislados) no debe bloquear nada.
- No cambies la duración de la sesión de 12 h ni el resto de la autenticación (X-Kunna-Key, sesiones, rutas exentas).

Además, revisa que la comparación de la clave `X-Kunna-Key` y de los códigos sea de tiempo constante, y corrige lo que no lo sea.

Ajusta o añade las pruebas que correspondan. Mantén el cambio pequeño: solo el backend de autenticación y sus pruebas. No hagas push ni despliegues nada: deja los cambios en el árbol de trabajo y dime qué cambiaste y cómo lo verificaste.
