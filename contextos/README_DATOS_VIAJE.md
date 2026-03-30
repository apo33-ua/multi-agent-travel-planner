# Uso de Agentes de Vuelos y Hoteles (live/cache)

## Variables de entorno
- `TRAVEL_DATA_MODE`: `cache` (por defecto) o `live`
- `SERPAPI_API_KEY`: necesaria solo en modo `live`
- `TRAVEL_CACHE_TTL_FLIGHTS_SECONDS`: TTL cache vuelos (por defecto 43200)
- `TRAVEL_CACHE_TTL_HOTELS_SECONDS`: TTL cache hoteles (por defecto 86400)

## Estrategia
1. `cache`: primero intenta leer cache local. Si no existe, usa `mock_data`.
2. `live`: consulta SerpApi en tiempo real y guarda la respuesta en `data/cache`.

## Pruebas rapidas
### Vuelos
```bash
/Users/alexpalomares/Documents/SEGUNDO-CUATRI/TFG/tfg_env/bin/python agente_vuelos.py
```

### Hoteles
```bash
/Users/alexpalomares/Documents/SEGUNDO-CUATRI/TFG/tfg_env/bin/python agente_hoteles.py
```

## Flujo recomendado para TFG
1. Desarrollo diario con `TRAVEL_DATA_MODE=cache`.
2. Hacer algunas consultas `live` para poblar cache.
3. Demo final con `TRAVEL_DATA_MODE=live` y fallback natural al cache si falla la API.

Cache
TRAVEL_DATA_MODE=cache /Users/alexpalomares/Documents/SEGUNDO-CUATRI/TFG/tfg_env/bin/python agente_vuelos.py

Live
TRAVEL_DATA_MODE=live /Users/alexpalomares/Documents/SEGUNDO-CUATRI/TFG/tfg_env/bin/python agente_vuelos.py
