const API_BASE = import.meta.env.VITE_API_URL ?? "";

function headers(): HeadersInit {
  const h: HeadersInit = { "Content-Type": "application/json" };
  const t = localStorage.getItem("dcc_token");
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

export async function login(user: string, pass: string) {
  const r = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: user, password: pass }),
  });
  if (!r.ok) throw new Error("Login fallido");
  return r.json();
}

async function httpErrorMessage(r: Response): Promise<string> {
  const text = (await r.text()).trim();
  if (r.status === 401) {
    return "Sesión expirada o token inválido. Pulsa Salir e inicia sesión de nuevo.";
  }
  if (!text) return `Error HTTP ${r.status}`;
  try {
    const j = JSON.parse(text) as { message?: string; title?: string };
    return j.message || j.title || text;
  } catch {
    return text;
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { headers: headers() });
  if (!r.ok) throw new Error(await httpErrorMessage(r));
  return r.json();
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const text = await r.text();
    try {
      const j = JSON.parse(text) as { message?: string; title?: string };
      const msg = j.message || j.title;
      if (msg) throw new Error(msg);
    } catch (e) {
      if (e instanceof Error && e.message !== text) throw e;
    }
    throw new Error(text || `Error HTTP ${r.status}`);
  }
  return r.json();
}

export async function apiDelete(path: string) {
  const r = await fetch(`${API_BASE}${path}`, { method: "DELETE", headers: headers() });
  if (!r.ok && r.status !== 204) throw new Error(await r.text());
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
