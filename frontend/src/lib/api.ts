export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const DEFAULT_API_BASE_URL = "http://localhost:8000";

function getApiBaseUrl() {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL;
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");

  if (response.ok) {
    if (!isJson) {
      throw new ApiError("Unexpected non-JSON response", response.status);
    }

    return (await response.json()) as T;
  }

  let detail = "Request failed";

  if (isJson) {
    const body = (await response.json()) as { detail?: string };
    if (typeof body.detail === "string" && body.detail.trim().length > 0) {
      detail = body.detail;
    }
  } else {
    const text = await response.text();
    if (text.trim().length > 0) {
      detail = text;
    }
  }

  throw new ApiError(detail, response.status);
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, headers, ...rest } = options;
  const requestHeaders = new Headers(headers);

  if (!requestHeaders.has("Content-Type") && rest.body) {
    if (!(rest.body instanceof FormData) && !(rest.body instanceof Blob)) {
      requestHeaders.set("Content-Type", "application/json");
    }
  }

  if (token) {
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${getApiBaseUrl()}${endpoint}`, {
    ...rest,
    headers: requestHeaders,
    cache: "no-store",
  });

  return parseResponse<T>(response);
}
