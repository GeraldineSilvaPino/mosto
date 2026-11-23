# Evidencia local: cinética causal y ML, 16-11-2026

Windows, Python 3.11.4. Resultado **sintético experimental**, sin validación real,
sin cambios en Supabase, migraciones remotas ni despliegue. Rama de partida
`codex/mosto-safe-foundation`, commit `8bda568`; trabajo de este cierre sin commit.

## Verificación de software

- SQLite temporal: **157 aprobadas, 8 omitidas**, 103,60 s; 89 warnings heredados.
  [Salida de pytest](causal-v1-sqlite-final.txt).
- Vite 6.4.5: build correcto, 1.673 módulos, 23,62 s. No se cambió la UI ni se
  ejecutó un nuevo flujo de navegador. La consulta cinética aún no se presenta en Vue.
- PostgreSQL no reejecutado: no se encontraron binarios en PATH/ruta estándar en
  este equipo. Las 139 pruebas PostgreSQL del 15-11 son evidencia histórica de la
  entrega anterior, no validación PostgreSQL del código nuevo.
- Versiones del entorno: `backend/requirements-tested-windows-py311.txt`;
  manifiestos ML registran versiones y hashes de código. No es un lock portable.
- Pruebas nuevas: disponibilidad por ambos relojes, recepción tardía vía HTTP,
  otro proceso, cambios de calibración, duplicados, calidad por canal, huecos,
  invariancia de tasas a 5/10 min, autorización entre empresas, límites del
  horizonte/anticipación/censura, semillas independientes y contaminación de
  test que no cambia entrenamiento, escalador, calibrador ni umbral.
- CSV y pickle legacy preservados. El pipeline no importa la configuración de
  base de datos y sus artefactos no se cargan en la API.

## Experimento reservado

100 trayectorias completas de 240 h, cinco escenarios, semilla maestra 2026;
7.300 ventanas. Semillas/procesos disjuntos: 55 train, 15 calibration,
15 validation, 15 test. El evento sintético se adjudica por persistencia futura
latente, sin consultar el nombre del escenario. Todos los escenarios están
representados en cada split: no es un ensayo de mecanismos desconocidos.

Test: 1.095 ventanas con features elegibles (100 % porque esta generación no
inyecta fallas), 564 ventanas elegibles de riesgo (31 positivas), nueve eventos
y 975 targets de forecast. Ventanas posteriores al primer evento, sin suficiente
anticipación o seguimiento se excluyen del riesgo; no se cuentan como negativas.

| Riesgo futuro a 12 h | Brier ↓ | PR-AUC ↑ | Eventos anticipados | Ventanas falsas positivas |
| --- | ---: | ---: | ---: | ---: |
| Prevalencia de train | 0,05195 | 0,05496 | 0/9 | 0 |
| Regla cinética | 0,05142 | 0,11593 | 1/9 | 0 |
| Logística, umbral 0,5 | 0,04022 | 0,46135 | 3/9 | 0 |
| Logística calibrada, umbral de validación | 0,04021 | 0,46135 | 4/9 | 2 |

Umbral congelado en validación: 0,218887088. Modelo calibrado: ROC-AUC 0,91158,
recall por ventana 19,35 %, precisión 75 %, detección por evento 44,44 %.
Anticipación mediana **entre los cuatro detectados**: 5,5 h (11, 3, 3 y 8 h).
Dos ventanas falsas positivas / 70,5 días elegibles = 0,02837 por día. La unidad
es ventana a cadencia de 3 h, **no** incidente deduplicado ni día calendario total.
Los umbrales distintos impiden atribuir el cambio en recall solo a calibración.

Por escenario: calor 3/3, frío 1/3 con dos falsos positivos, agotamiento simulado
0/3. Sano/lento no contienen eventos ni falsas alarmas en este test. **El fallo
completo ante agotamiento simulado es una limitación conocida**, no evidencia de
que pueda identificarse una causa nutricional a partir de sensores.

La calibración sigmoide apenas cambia Brier y empeora ECE de diez bins de 0,01294
a 0,01453. No se afirma mejora de calibración por el mero hecho de ajustar un
calibrador. No se reajustaron hiperparámetros ni umbral tras ver este test.

| Forecast de Brix aparente a 24 h | MAE (°Bx) | RMSE (°Bx) |
| --- | ---: | ---: |
| Persistencia de media reciente | 1,47784 | 2,69955 |
| Extrapolación de pendiente 6 h | 0,62213 | 1,18821 |
| Ridge | 0,32089 | 0,51013 |

No hay intervalos de predicción calibrados. Los resultados incluyen ventanas
solapadas y tramos posteriores al evento para forecast; no se interpretan como
975 fermentaciones independientes ni como error esperado en vino real.

## Trazabilidad y siguiente paso

[Reporte JSON resumido](cinetica-ml-evaluation.json): métricas globales,
calibración, escenarios/procesos, IDs de particiones, versiones y hashes.
Dataset SHA-256: `29a9747d4e39a995ff44fe49a53e244d029aa489d0e8c0cf6479e76ea1dc1039`.

Artefactos locales regenerables bajo `backend/artifacts/causal-v1-final-*`:
recetas y ventanas, modelo experimental, informe completo y predicciones por
fila. [Contrato y comandos](../CINETICA_Y_PIPELINE_ML.md). Se hizo una segunda
generación con el código final y conservó el mismo dataset y las mismas métricas.

Mantener `NO_VALIDADO`, riesgo null y sin alertas/forecast ML operacionales.
Próximo bloque: perfiles/episodios cinéticos persistentes y UI de evidencia,
robustez ante datos defectuosos, evaluación por mecanismos reservados y etiquetas
reales. Antes de promover modelos, resolver los fallos conocidos y validar en
lotes independientes; conservar este test para trazabilidad, no para ajuste.
