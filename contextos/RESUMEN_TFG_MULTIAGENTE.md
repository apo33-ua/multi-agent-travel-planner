# Resumen del estado actual del TFG (multiagente de viajes)

## 1. Objetivo del proyecto (fase actual)
Se ha comenzado la implementacion del primer bloque del sistema multiagente: el modulo de clima para recomendaciones de viaje.

La idea es que, dado un destino y un contexto de viaje, el sistema:
- consulte clima real en OpenWeather,
- genere recomendaciones de ropa y actividades,
- y sea robusto aunque falle el proveedor LLM.

## 2. Tecnologias usadas hasta ahora
- Python
- OpenWeather API (datos de clima en tiempo real)
- LangChain + langchain_google_genai (conexion con Gemini)
- Logica de fallback local (sin LLM) para garantizar respuesta siempre

Archivo principal actual:
- agente_clima.py

## 3. Lo que se ha implementado

### 3.1. Entrada por consola
El script pide:
- Ciudad destino
- Contexto del viaje (opcional)

### 3.2. Consulta real de clima
Se implemento una funcion que llama a OpenWeather y obtiene:
- descripcion del clima
- temperatura
- sensacion termica
- humedad
- viento

Con esto se genera un resumen textual de clima para el resto del flujo.

### 3.3. Recomendacion con LLM (Gemini)
Se implemento un flujo que intenta usar Gemini para devolver:
- ropa recomendada
- actividades adecuadas
- alternativas si llueve
- consejo de seguridad

Tambien muestra claramente cuando el LLM esta activo con una cabecera del tipo:
[LLM activo: nombre_modelo]

### 3.4. Fallback robusto sin LLM
Si Gemini falla (cuota, timeout, modelo no disponible, etc.), el sistema no se cae.
En su lugar:
- aplica reglas locales segun temperatura y descripcion del clima,
- devuelve recomendaciones utiles,
- e incluye diagnostico tecnico resumido de por que fallo Gemini.

Esto permite seguir haciendo demos funcionales incluso con incidencias de API.

## 4. Variables de entorno configurables
El script usa estas variables:
- GOOGLE_API_KEY
- OPENWEATHER_API_KEY
- GEMINI_MODEL
- GEMINI_MODEL_CANDIDATES
- GEMINI_TIMEOUT_SECONDS
- GEMINI_RETRIES

## 5. Problemas encontrados y como se resolvieron

1. Claves hardcodeadas en codigo
- Se eliminaron y se paso a variables de entorno.

2. Deprecaciones y cambios de modelos
- Se actualizaron modelos candidatos y la estrategia de seleccion.

3. Errores Gemini frecuentes
- 429 RESOURCE_EXHAUSTED (cuota)
- 404 NOT_FOUND (modelo no disponible para endpoint/proyecto)
- 504 DEADLINE_EXCEEDED (timeout)

4. Resultado
- El script ahora captura estos errores y responde con fallback sin romper ejecucion.

## 6. Como funciona el flujo actual (resumen simple)
1. Usuario introduce ciudad y contexto.
2. Se consulta OpenWeather.
3. Se construye resumen de clima.
4. Se intenta generar respuesta con Gemini.
5. Si Gemini responde, salida con LLM activo.
6. Si Gemini falla, salida por reglas locales + diagnostico de error.

## 7. Estado actual del proyecto
Estado: Fase 1 funcional completada para modulo de clima.

Actualmente ya se dispone de:
- un agente/clase de comportamiento util para clima,
- integracion real con API externa,
- manejo de errores robusto,
- y base reutilizable para conectar un supervisor multiagente.

## 8. Siguientes pasos recomendados
1. Separar codigo por modulos (clima, recomendador, supervisor).
2. Construir supervisor con LangGraph para enrutar tareas.
3. Añadir agente RAG con destinos de ejemplo (Madrid, Paris, Roma).
4. Estandarizar salida en JSON para encadenar agentes.
5. Crear tests basicos (clima OK, clima error, LLM OK, LLM fallback).

## 9. Mensaje breve para tutor
Se ha completado un primer prototipo robusto del modulo de clima del planificador de viajes, integrando OpenWeather y Gemini con mecanismos de tolerancia a fallos. El sistema ya produce recomendaciones utiles con y sin LLM, y esta preparado para evolucionar a una arquitectura multiagente con supervisor y RAG en las siguientes iteraciones.
