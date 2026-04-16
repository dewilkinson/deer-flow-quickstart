import { getBackendBaseURL } from "@/core/config";


export async function loadMCPConfig() {
  const response = await fetch(`${getBackendBaseURL()}/api/mcp/config`);
  return response.json() as Promise<any>;
}

export async function updateMCPConfig(config: any) {
  const response = await fetch(`${getBackendBaseURL()}/api/mcp/config`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(config),
    },
  );
  return response.json();
}
