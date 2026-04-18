import { getBackendBaseURL } from "../config";

import type { Model } from "./types";

export async function loadModels() {
  try {
    const res = await fetch(`${getBackendBaseURL()}/api/models`);
    if (!res.ok) {
      console.warn(`Failed to load models: ${res.status} ${res.statusText}`);
      return [];
    }
    const data = (await res.json()) as { models?: Model[] };
    return data.models ?? [];
  } catch (error) {
    console.error("Error loading models:", error);
    return [];
  }
}
