# MOSTO

Plataforma de monitoreo de fermentación vitivinícola del proyecto APT de Duoc UC. El repositorio organiza las evidencias académicas por fase. El código de la aplicación y los archivos de Docker están en [Fase 2 → Evidencias de sistema → Aplicación](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20sistema/Aplicacion/README.md).

## Montar la demo local

Con Docker Desktop iniciado o Docker Engine con Compose disponible, ejecuta desde la raíz del repositorio:

```sh
cd "Fase 2/Evidencias Proyecto/Evidencias de sistema/Aplicacion"
docker compose --profile demo up -d --build
```

Abre el [dashboard](http://localhost:5173), selecciona **Admin** en el acceso rápido de demostración e inicia sesión. La [guía de la aplicación](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20sistema/Aplicacion/README.md) explica cómo verificar los servicios, ver las lecturas y detener la demo conservando su historial.

## Equipo

Carlos Cartes · Matías González · Geraldine Silva
