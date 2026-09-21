export interface PlanRequest {
  ciudad: string;
  contexto_viaje?: string;
  objetivo_usuario?: string;
  fecha_inicio?: string;
  fecha_fin?: string;
  origen_iata?: string;
  destino_iata?: string;
  presupuesto_total_eur?: number;
  adultos?: number;
}

export interface FlightOption {
  airline?: string;
  price?: string | number;
  duration?: number;
  stops?: unknown[];
  [key: string]: unknown;
}

export interface HotelOption {
  name?: string;
  rating?: number;
  price_per_night?: string | number;
  total_rate?: string | number;
  type?: string;
  [key: string]: unknown;
}

export interface BudgetCombination {
  flight_id?: string | number;
  hotel_id?: string | number;
  flight_price?: number;
  hotel_price?: number;
  total_estimated?: number;
  fits_budget?: boolean;
  excluded_by_budget?: boolean;
  budget_gap?: number;
  [key: string]: unknown;
}

export interface PlanResponse {
  contexto: {
    ciudad: string;
    origen_iata: string;
    destino_iata: string;
    fecha_inicio: string;
    fecha_fin: string;
    presupuesto_total_eur: number;
    adultos: number;
  };
  routing: {
    modo_planificacion?: string;
    horizonte_dias?: number | null;
    usar_clima?: boolean;
    usar_vuelos_hoteles?: boolean;
    usar_turismo?: boolean;
    motivo_ruta?: string;
  };
  turismo: string;
  clima: {
    consultado: boolean;
    reporte: string;
  };
  vuelos: FlightOption[];
  hoteles: HotelOption[];
  presupuesto: {
    auditoria: {
      decision?: string;
      n_validas?: number;
      n_excluidas?: number;
      total_evaluadas?: number;
    };
    combinaciones_validas: BudgetCombination[];
    combinaciones_excluidas: BudgetCombination[];
    acciones_sugeridas?: string[];
  };
  respuesta_markdown: string;
  supervisor_modelo?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function generatePlan(request: PlanRequest): Promise<PlanResponse> {
  const response = await fetch(`${API_URL}/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `Error ${response.status}`);
  }

  return response.json();
}
