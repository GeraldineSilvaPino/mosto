# Trazabilidad del prototipo con los documentos

Fuentes analizadas: `Modelo Relacional.png`, `Historias de Usuario.docx`, `Épicas.docx`, `Backlog Priorizado.docx`, `2_4_GuiaEstudiante_Fase_2_DesarrolloProyecto_APT_completada.docx`, y guía de definición de Fase 1.

| HU/Épica | Evidencia en este prototipo | Alcance / advertencia |
|---|---|---|
| E01, HU-01 | Login de Supabase en Vue/FastAPI | Demo no solicita login; en live se verifican JWT por Auth |
| HU-02, HU-03 | Formularios de empresa y asignación de rol | En producción, alta de empresa solo por administrador plataforma |
| HU-06 a HU-08 | CRUD parcial bodegas/cubas + cambio de estado | Demo valida cuba activa; live requiere RLS y triggers |
| HU-10 a HU-12 | Registrar, asignar, desasignar nodos | Demo guarda historial; live RPC pendiente de validar |
| HU-15, HU-16, HU-18 | Perfiles, catálogos y lectura de límites | Ajustes HU-17 se muestran en lectura, edición pendiente |
| HU-19 a HU-21 | Iniciar, cerrar y consultar fermentaciones | Demo aplica reglas; live requiere transacciones SQL |
| HU-23 y HU-24 | Endpoints de prueba IoT con claves sintéticas | Solo demo; NO habilitar producción con este mecanismo |
| HU-25 | Monitor de temperatura, pH, °Brix y densidad | Refresco 30 s; no es WebSocket; no inventa datos en live |
| HU-27 a HU-29 | Alertas demo automáticas, atención, resolución | Temperatura, pH, caída diaria Brix si hay histórico comparable |
| HU-31, HU-32 | Registro y consulta de intervenciones | En live RPC evita autor falsificado; permisos a verificar |
| HU-34, HU-36 | Gráficos históricos y CSV básico | Son Should/Could; export limita a 5000 registros |
| HU-37 | Lecturas PostgREST con JWT del usuario | RLS multiempresa por bodega **no implementado aquí**: depende del proyecto Supabase y auditoría |
| HU-38 | Reglas de integridad en demo | Parcial; validaciones completas deben imponerse en PostgreSQL |
| HU-39 | Denegación explícita de ingesta real | Pendiente credenciales revocables reales |
| E09/CRISP-DM | Sección de informes básicos | Sin entrenamiento de ML ni predicciones ficticias |

**Estado real:** interfaz demostrativa y API para presentar flujos, no producto terminado. Para evaluar el MVP académico se deben mostrar dispositivos reales, políticas RLS, validación de telemetría real y evidencias de pruebas.
