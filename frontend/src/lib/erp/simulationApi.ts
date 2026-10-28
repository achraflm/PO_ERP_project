import { apiFetch, throwApiError } from "./api";

export interface SavedSimulation {
  simulation_id: number;
  target_date: string;
  created_at: string;
  is_feasible: boolean;
  simulation_mode: string;
  safety_coefficient: string;
  mtg_minutes_document_id: number;
  fgpns: { po_number: string; fgpn_code: string; quantity: string; launchable_quantity: string }[];
  allocations: { stock_unit_id: number; quantity: string; source: string; status: string }[];
}

export async function readSimulationApi<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await apiFetch(path, { signal });
  if (!response.ok) await throwApiError(response);
  return response.json();
}
