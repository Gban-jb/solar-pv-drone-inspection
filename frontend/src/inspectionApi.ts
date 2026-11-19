export type Box = [number, number, number, number];
export type FileRole = 'rgb' | 'thermal' | 'temperature_grids' | 'scada';
export type Source = 'field_unverified' | 'public_research' | 'synthetic';

export interface Inspection {
  id: string;
  name: string;
  read_only: boolean;
  provenance: Source;
  source: string;
}

export interface InspectionFile {
  path: string;
  kind: 'rgb' | 'thermal' | 'scada';
  status: 'ok' | 'warning' | 'error';
  width: number | null;
  height: number | null;
  format: string | null;
  camera_model?: string | null;
  capture_time_raw?: string | null;
  row_count?: number | null;
  missing_fields: string[];
  error: string | null;
}

export interface Pair {
  pair_id: string;
  rgb_path: string;
  thermal_path: string;
  temperature_path: string;
  alignment_reviewed: boolean;
  basis: string;
  limits: [number, number] | null;
  error: string | null;
}

export interface Annotation {
  annotation_id: string;
  image_path: string;
  target_type: 'panel' | 'row' | 'region';
  asset_id: string;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  review_status: 'provisional' | 'confirmed';
  linked_asset_id: string;
  mapping_status: string;
  observation_category: string;
  finding_status: string;
  severity: string;
  observation_note: string;
  thermal_region_bounds: string;
  thermal_reference_bounds: string;
  modified_at_utc: string;
}

export interface Finding {
  record_id: string;
  annotation_id: string;
  asset_id: string;
  pair_id: string;
  rgb_image_path: string;
  thermal_image_path: string;
  candidate: boolean;
  median_temperature_c: number | null;
  reference_temperature_c: number | null;
  delta_t_c: number | null;
  measurement_basis: string;
  observation_category: string;
  finding_status: string;
  severity: string;
  observation_note: string;
  data_quality_flags: string[];
}

export interface Workspace {
  inspection: Inspection;
  files: InspectionFile[];
  temperature_sources: string[];
  pairs: Pair[];
  annotations: Annotation[];
  findings: Finding[];
  pair_issues: {pair_id: string; reason: string}[];
}

export interface RegionStats {
  minimum: number;
  maximum: number;
  mean: number;
  median: number;
  sample_count: number;
  excluded_count: number;
  unit: string;
}

export type Measurements = {selected: RegionStats; reference: RegionStats | null; delta: number | null};
export const roles: Record<FileRole, string> = {rgb: 'RGB photos', thermal: 'Thermal previews', temperature_grids: 'Temperature grids', scada: 'Meter CSV'};
export const sources: Record<Source, string> = {synthetic: 'Synthetic sample', public_research: 'Public research', field_unverified: 'Unverified field data'};
export const statuses: Record<string, string> = {draft: 'Draft', needs_verification: 'Needs verification', reviewed: 'Reviewed', resolved: 'Resolved'};
export const categories: Record<string, string> = {
  unclassified: 'Unclassified', localized_heating: 'Apparent localized heating',
  uneven_appearance: 'Uneven appearance', possible_shading: 'Possible shading',
  possible_soiling_or_obstruction: 'Possible soiling or obstruction', other_irregularity: 'Other irregularity',
  no_visible_anomaly: 'No visible anomaly',
};

export const basename = (path: string) => path.split('/').pop() ?? path;
export const formatLabel = (value: string) => value.replace(/_/g, ' ');
export const boxOf = (row: Annotation): Box => [row.x_min, row.y_min, row.x_max, row.y_max];
export const apiPath = (id: string, route = '') => '/api/inspections/' + encodeURIComponent(id) + route;
export const imageUrl = (id: string, path: string, size = 'viewer') => apiPath(id, '/image?') + new URLSearchParams({path, size});
export const canMeasure = (pair?: Pair) => ['synthetic_numeric_demo', 'calibrated_numeric'].includes(pair?.basis ?? '');
export const describeTemperature = (value: number | null | undefined, signed = false) =>
  value == null ? 'Unavailable' : `${signed && value > 0 ? '+' : ''}${value.toFixed(2)} °C`;

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    const detail = result?.detail;
    const message = typeof detail === 'string' ? detail : detail?.message ?? (Array.isArray(detail) ? detail[0]?.msg : null);
    const error = new Error(message ?? `Request failed (${response.status}). Try again.`);
    if (detail?.details) Object.assign(error, {cause: detail.details});
    throw error;
  }
  return response.status === 204 ? undefined as T : response.json();
}

export function jsonRequest(method: string, payload: unknown): RequestInit {
  return {method, body: JSON.stringify(payload), headers: {'Content-Type': 'application/json'}};
}

export function inspectionLink(screen: 'upload' | 'inspect' | 'findings', id: string, image?: string, annotation?: string, pair?: string) {
  const query = new URLSearchParams({inspection: id});
  if (image) query.set('image', image);
  if (annotation) query.set('annotation', annotation);
  if (pair) query.set('pair', pair);
  return `/workspace/${screen}?${query}`;
}
