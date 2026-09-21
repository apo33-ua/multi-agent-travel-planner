#!/usr/bin/env python3
"""Genera la presentación del TFG (.pptx) con 9 diapositivas numeradas.
Estilo sobrio, listo para importar a Canva / Google Slides y reestilizar."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# --- Paleta ---
AZUL = RGBColor(0x1A, 0x73, 0xE8)      # azul UA / acento
OSCURO = RGBColor(0x20, 0x24, 0x2B)    # texto principal
GRIS = RGBColor(0x5F, 0x66, 0x70)      # texto secundario
BLANCO = RGBColor(0xFF, 0xFF, 0xFF)
AZUL_FONDO = RGBColor(0x0B, 0x5F, 0xD4)

prs = Presentation()
prs.slide_width = Inches(13.333)   # 16:9
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]

def add_textbox(slide, left, top, width, height):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tb.text_frame.word_wrap = True
    return tb

def set_para(p, text, size, color, bold=False, align=PP_ALIGN.LEFT,
             space_after=10, bullet=False, level=0):
    p.text = text
    p.alignment = align
    p.level = level
    p.space_after = Pt(space_after)
    for run in p.runs:
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.bold = bold
        run.font.name = "Calibri"
    return p

def numero(slide, n):
    """Número de transparencia abajo a la derecha."""
    tb = add_textbox(slide, SW - Inches(1.1), SH - Inches(0.6),
                     Inches(0.8), Inches(0.4))
    p = tb.text_frame.paragraphs[0]
    set_para(p, str(n), 14, GRIS, align=PP_ALIGN.RIGHT, space_after=0)

def barra_titulo(slide, titulo):
    """Franja de acento + título de sección."""
    # franja vertical de acento
    bar = slide.shapes.add_shape(1, Inches(0.6), Inches(0.55),
                                 Inches(0.12), Inches(0.75))
    bar.fill.solid(); bar.fill.fore_color.rgb = AZUL
    bar.line.fill.background()
    tb = add_textbox(slide, Inches(0.9), Inches(0.45), SW - Inches(2), Inches(1.0))
    p = tb.text_frame.paragraphs[0]
    set_para(p, titulo, 30, OSCURO, bold=True, space_after=0)

def bullets(slide, items, top=Inches(1.8), left=Inches(0.9),
            width=None, size=20, gap=14):
    width = width or (SW - Inches(1.8))
    tb = add_textbox(slide, left, top, width, SH - top - Inches(0.8))
    tf = tb.text_frame
    for i, item in enumerate(items):
        if isinstance(item, tuple):
            txt, lvl = item
        else:
            txt, lvl = item, 0
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        prefix = "•  " if lvl == 0 else "–  "
        set_para(p, prefix + txt, size - (lvl * 2), OSCURO if lvl == 0 else GRIS,
                 space_after=gap, level=lvl)

# ============================================================
# SLIDE 1 — Portada
# ============================================================
s = prs.slides.add_slide(BLANK)
fondo = s.shapes.add_shape(1, 0, 0, SW, SH)
fondo.fill.solid(); fondo.fill.fore_color.rgb = AZUL_FONDO
fondo.line.fill.background()
fondo.shadow.inherit = False

tb = add_textbox(s, Inches(0.9), Inches(1.6), SW - Inches(1.8), Inches(2.6))
tf = tb.text_frame
set_para(tf.paragraphs[0], "Orquestador multiagente", 44, BLANCO, bold=True, space_after=2)
set_para(tf.add_paragraph(), "de planificación de viajes", 44, BLANCO, bold=True, space_after=18)
set_para(tf.add_paragraph(), "Trabajo Fin de Grado · Grado en Ingeniería Informática", 20, BLANCO, space_after=0)

tb2 = add_textbox(s, Inches(0.9), Inches(4.9), SW - Inches(1.8), Inches(2.0))
tf2 = tb2.text_frame
set_para(tf2.paragraphs[0], "Autor: Alejandro Palomares Ortega", 20, BLANCO, bold=True, space_after=6)
set_para(tf2.add_paragraph(), "Tutores: David Tomás Díaz · José Luis Vicedo González", 18, BLANCO, space_after=6)
set_para(tf2.add_paragraph(), "Escuela Politécnica Superior · Universidad de Alicante · Junio 2026", 16, BLANCO, space_after=0)
numero(s, 1)

# ============================================================
# SLIDE 2 — Índice
# ============================================================
s = prs.slides.add_slide(BLANK)
barra_titulo(s, "Índice")
bullets(s, [
    "1.  ¿En qué consiste el proyecto?",
    "2.  Conceptos: LLM y agentes",
    "3.  Herramientas y tecnologías",
    "4.  Arquitectura del sistema",
    "5.  Demo",
    "6.  Conclusiones y trabajo futuro",
], top=Inches(2.0), size=24, gap=18)
numero(s, 2)

# ============================================================
# SLIDE 3 — Qué he hecho
# ============================================================
s = prs.slides.add_slide(BLANK)
barra_titulo(s, "¿En qué consiste el proyecto?")
bullets(s, [
    "Planificar un viaje obliga a saltar entre Skyscanner, Booking, Google Maps y el tiempo, y cuadrarlo todo a mano. No hay nada que lo integre.",
    "Solución: un backend que recibe una petición en lenguaje natural y devuelve un itinerario completo.",
    ("Vuelos + hoteles + previsión meteorológica + plan turístico", 1),
    "Coordina varios agentes especializados mediante un grafo de orquestación.",
    "Toma decisiones explícitas: activa o desactiva agentes según el viaje y filtra las opciones por presupuesto.",
], top=Inches(1.9), size=20, gap=16)
numero(s, 3)

# ============================================================
# SLIDE 4 — LLM y agentes
# ============================================================
s = prs.slides.add_slide(BLANK)
barra_titulo(s, "Conceptos: LLM y agentes")
bullets(s, [
    "LLM (Large Language Model): modelo que genera y razona sobre lenguaje natural. Aquí, Google Gemini.",
    "Agente: combina el LLM con herramientas externas (APIs) para resolver una tarea concreta.",
    "Sistema multiagente: varios agentes cooperan sobre un estado compartido, coordinados por un supervisor.",
    "Idea central del diseño: separar la decisión determinista (Python) de la generación (LLM).",
    ("Los precios los calcula Python, no el LLM → resultados reales, sin alucinaciones.", 1),
], top=Inches(1.9), size=20, gap=16)
numero(s, 4)

# ============================================================
# SLIDE 5 — Herramientas: stack
# ============================================================
s = prs.slides.add_slide(BLANK)
barra_titulo(s, "Herramientas y tecnologías — stack")
bullets(s, [
    "Lenguaje: Python 3.14",
    "Orquestación: LangGraph (grafo de estados) + LangChain (capa de modelo)",
    "LLM: Google Gemini (2.5 Flash / Flash-Lite / Pro)",
    "APIs externas: SerpApi (Google Flights / Hotels) · OpenWeather (clima)",
    "Backend: FastAPI (endpoint REST /plan) · Frontend: Next.js",
    "Pruebas: pytest (58 tests)",
], top=Inches(1.9), size=20, gap=15)
numero(s, 5)

# ============================================================
# SLIDE 6 — Herramientas: decisiones de diseño
# ============================================================
s = prs.slides.add_slide(BLANK)
barra_titulo(s, "Herramientas y tecnologías — diseño")
bullets(s, [
    "Patrón Live / Caché / Mock: desarrollar y demostrar sin gastar cuota ni depender de la red.",
    "Resiliencia: reintentos con backoff exponencial + fallback en cascada entre modelos.",
    "Credenciales fuera del código, en variables de entorno.",
    "Validación presupuestaria 100 % determinista: los números los calcula Python, no el LLM.",
], top=Inches(1.9), size=20, gap=16)
numero(s, 6)

# ============================================================
# SLIDE 7 — Arquitectura
# ============================================================
s = prs.slides.add_slide(BLANK)
barra_titulo(s, "Arquitectura del sistema")
# placeholder para el diagrama (Figura 7.1)
ph = s.shapes.add_shape(1, Inches(0.9), Inches(1.8), SW - Inches(1.8), Inches(3.4))
ph.fill.solid(); ph.fill.fore_color.rgb = RGBColor(0xEF, 0xF2, 0xF6)
ph.line.color.rgb = RGBColor(0xCC, 0xD2, 0xDA)
ph.shadow.inherit = False
ptf = ph.text_frame; ptf.word_wrap = True
set_para(ptf.paragraphs[0],
         "[ Inserta aquí la Figura 7.1 de la memoria: diagrama del orquestador ]",
         18, GRIS, align=PP_ALIGN.CENTER)
ptf.vertical_anchor = MSO_ANCHOR.MIDDLE
tb = add_textbox(s, Inches(0.9), Inches(5.4), SW - Inches(1.8), Inches(1.4))
p = tb.text_frame.paragraphs[0]
set_para(p, "Enrutador → Agente Turístico → Fetch (fan-out: Vuelos ∥ Hoteles) → "
            "Nodo Presupuestario (fan-in) → Agente Climático → Síntesis → Itinerario en Markdown",
         16, OSCURO, space_after=0)
numero(s, 7)

# ============================================================
# SLIDE 8 — DEMO
# ============================================================
s = prs.slides.add_slide(BLANK)
fondo = s.shapes.add_shape(1, 0, 0, SW, SH)
fondo.fill.solid(); fondo.fill.fore_color.rgb = AZUL_FONDO
fondo.line.fill.background(); fondo.shadow.inherit = False
tb = add_textbox(s, Inches(1), Inches(3.0), SW - Inches(2), Inches(1.5))
p = tb.text_frame.paragraphs[0]
set_para(p, "Demo", 54, BLANCO, bold=True, align=PP_ALIGN.CENTER, space_after=8)
p2 = tb.text_frame.add_paragraph()
set_para(p2, "Ejemplo: Roma · 20–24 mayo · MAD · 800 € · \"viaje cultural\"",
         20, BLANCO, align=PP_ALIGN.CENTER, space_after=0)
numero(s, 8)

# ============================================================
# SLIDE 9 — Conclusiones y trabajo futuro
# ============================================================
s = prs.slides.add_slide(BLANK)
barra_titulo(s, "Conclusiones y trabajo futuro")
tb = add_textbox(s, Inches(0.9), Inches(1.8), SW - Inches(1.8), Inches(0.5))
set_para(tb.text_frame.paragraphs[0], "Conclusiones", 20, AZUL, bold=True, space_after=0)
bullets(s, [
    "Backend funcional que integra cuatro dominios en un único itinerario.",
    "Enrutamiento dinámico: cada petición sigue su propio camino en el grafo.",
    "Precios reales y trazables; arquitectura modular y extensible.",
], top=Inches(2.3), size=18, gap=10)
tb2 = add_textbox(s, Inches(0.9), Inches(4.4), SW - Inches(1.8), Inches(0.5))
set_para(tb2.text_frame.paragraphs[0], "Trabajo futuro", 20, AZUL, bold=True, space_after=0)
bullets(s, [
    "Multi-ciudad y búsqueda con fechas flexibles.",
    "Persistencia y perfiles de usuario.",
    "Nuevos agentes (trenes, restauración) y monetización por afiliación.",
], top=Inches(4.9), size=18, gap=10)
numero(s, 9)

# ============================================================
# SLIDE 10 — Cierre
# ============================================================
s = prs.slides.add_slide(BLANK)
fondo = s.shapes.add_shape(1, 0, 0, SW, SH)
fondo.fill.solid(); fondo.fill.fore_color.rgb = AZUL_FONDO
fondo.line.fill.background(); fondo.shadow.inherit = False
tb = add_textbox(s, Inches(1), Inches(2.4), SW - Inches(2), Inches(2.8))
tf = tb.text_frame
set_para(tf.paragraphs[0], "¡Gracias por su atención!", 40, BLANCO, bold=True,
         align=PP_ALIGN.CENTER, space_after=24)
set_para(tf.add_paragraph(), "Orquestador multiagente de planificación de viajes",
         24, BLANCO, align=PP_ALIGN.CENTER, space_after=10)
set_para(tf.add_paragraph(), "Alejandro Palomares Ortega",
         20, BLANCO, align=PP_ALIGN.CENTER, space_after=6)
set_para(tf.add_paragraph(), "github.com/apo33-ua/TFG",
         16, BLANCO, align=PP_ALIGN.CENTER, space_after=0)
numero(s, 10)

out = "Presentacion-TFG-Alejandro-Palomares.pptx"
prs.save(out)
print("Generado:", out, "·", len(prs.slides._sldIdLst), "diapositivas")
