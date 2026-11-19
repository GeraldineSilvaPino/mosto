# Rama B — UI operacional y documentación de uso

Rama exclusiva: `codex/mosto-ui-delivery`. Leer PLAN_PARALELO y CONTRATO_COORDINACION.
Estado editable: ESTADO_B; API necesaria: SOLICITUDES_B. No editar backend ni docs
maestros. Backend actual sirve como referencia congelada hasta recibir adiciones A.

## B1. Auditoría de controles y navegación

Revisar todas las vistas, componentes y servicios. Matriz control→endpoint→rol→
resultado persistido→prueba. Priorizar DashboardView, CubaDetailView, DevicesView,
AlertsView/AlertsAuditView, ThresholdsView, BinnacleView, UsersView y CompanyConfigView.
Eliminar cifras/acciones ficticias y distinguir desconocido, vacío, error, carga,
sin permiso y proceso cerrado. No cambiar semántica backend desde el cliente.

Conservar selector manual y exportación JSON ya hechos. Completar y verificar
ProcessHistoryView: enlaces profundos y recarga, ida/vuelta al estado actual de
cuba, proceso cerrado como principal, cambios rápidos sin evidencia de otro proceso.
Listado actual GET /api/procesos es completo no paginado: no fingir paginación
servidor. Pedir contrato A si el volumen lo exige; filtros locales deben declararse.

## B2. Sistema visual y experiencia integral

Implementar coherencia entre pantallas con tokens/componentes existentes o nuevos;
dirección visual del informe original sección 4, sin rehacer reglas de negocio.
Overview útil con prioridades operativas, procedencia y frescura separadas de salud.
Curvas con unidades/método, calidad, huecos y evidencia; ML/forecast N/D mientras
backend no esté validado. Sin recomendaciones causales inventadas.
Formularios completos de dispositivo/calibración usando API existente. Acciones
destructivas con contexto, errores recuperables, validación y persistencia real.
Accesibilidad: labels, teclado, foco de diálogos, contraste medido, no solo color;
móvil 360/390 px y desktop sin desbordamientos ni controles inaccesibles.

## B3. Integración del reloj en presentación

No bloquear B1/B2 esperando A. Con contrato confirmado mostrar factor, dominio de
observación, recepción real, edad/frescura, procedencia y condiciones del ensayo.
No calcular conversión por cuenta propia ni usar Date.now para inventar tiempo
simulado. Mientras API no lo habilite, UI no debe ofrecer arranque acelerado.
Adaptar comparación/exportación y paneles a campos aditivos, conservando 1x.
Validar con API real de A durante integración, además de fixtures versionadas.

## B4. Pruebas y manual

Crear E2E portable en frontend (dependencias y scripts en sus package/lock), con
configuración explícita de API demo/test. Casos: login, roles, error/vacío, IDs
altos, incidente/notas/atención/resolución, intervenciones, medición/anulación,
vínculo manual, perfil/override, histórico, comparación y descarga. Diferenciar
test con red interceptada de E2E real; no probar contra Supabase.
Añadir workflow UI propio solo si aporta validación real; no editar checks.yml.
Documentar instalación frontend y manual de usuario en frontend/docs. Matriz UI
y evidencia en backend/docs/paralelo/evidencias-b. No incluir secretos/capturas
de datos reales. Verificar build limpio y accesibilidad/móvil con resultados.

## B5. Entrega

Push de rama B, estado completo con hashes y comandos, lista de endpoints nuevos
requeridos, contratos consumidos y limitaciones. No merge a A ni develop; A integra.
Seguir trabajando en bloques independientes si una API está pendiente. No marcar
el plan total completo: B cierra solo sus criterios comprobados.
