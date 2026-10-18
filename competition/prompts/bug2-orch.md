Orquesta esto con subagent-pool (procede sin project-context; el proyecto no tiene .claude/project-context.md):

Hola, tengo un problema con kuNNA y necesito que lo arregles.

Desde hace un par de días, el mapa de conexiones de la vista SCADA ya no muestra cómo hablan mis servicios. Casi todos los enlaces aparecen como "Internet / LAN" o "Este equipo", y ningún servicio aparece conectado a otro. Antes veía el frontend hablando con el backend y el backend con la base de datos.

Lo que sí funciona: el dashboard carga, la lista de servicios responde, puedo arrancar y parar contenedores, y el panel de avisos sigue activo. Así que los servicios están bien; solo el mapa de conexiones está mal.

No sé qué cambió exactamente. Revisa el código del proyecto, encuentra la causa y arréglala. Haz el cambio mínimo que deje el mapa como debe ser, y añade o ajusta las pruebas que correspondan.

Cuando termines, dime qué causaba el problema y qué cambiaste. No hagas push ni despliegues nada: solo deja los cambios en el árbol de trabajo.
