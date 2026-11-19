# Selector de intervención en mediciones manuales

Cierre funcional local, 18-11-2026. El panel compartido por cuba e incidente
permite registrar una medición vinculada a una intervención compatible.

- API de opciones paginada por proceso. En incidente incluye intervenciones sin
  alerta y las de ese incidente; excluye las de otros incidentes/procesos.
- Permisos de empresa/bodega aplicados también a las opciones. El POST mantiene
  la validación autoritativa, UUID de reintento y persistencia del vínculo.
- UI: selección opcional, estado/acción/ID visibles, carga por páginas de 50,
  actualización, error y reintento. Cambiar de proceso/incidente descarta opciones
  antiguas y respuestas tardías. No se declara respuesta biológica por vincular.
- SQLite: 19 aprobadas y 3 omitidas en 4,35 s. PostgreSQL 18.4: 22 aprobadas
  en 11,32 s; suite de mediciones manuales, incluidas concurrencia/inmutabilidad.
- Vite: compilación aprobada en 3,97 s.
- Edge headless con componente Vue real y API interceptada: cargar página 2,
  seleccionar #51, POST con ID numérico, mostrar vínculo tras recarga y reintentar
  consulta fallida; sin errores JavaScript. La persistencia real se comprobó en
  tests HTTP/base de datos, no en una sesión navegador→API real conjunta.
- Captura y script exploratorio locales ignorados por Git:
  `backend/artifacts/browser-check/selector.png` y `check.cjs`.

No se certifican accesibilidad integral, móvil ni carga. El reloj acelerado sigue
abierto y constituye el siguiente bloque técnico principal.
