import { apiRequest } from "@/lib/api";

export type LoginPayload = {
  email: string;
  password: string;
};

export type RegisterPayload = {
  email: string;
  password: string;
  full_name?: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type UsageResponse = {
  user_id: string;
  period: string;
  standard_research: { used: number; quota: number; remaining: number };
  deep_research: { used: number; quota: number; remaining: number; available: boolean };
  tokens_this_month: number;
  cost_this_month_usd: number;
  subscription_tier: string;
};

export type HealthResponse = {
  status: string;
  service: string;
  version: string;
  database: string;
  authenticated: boolean;
};

async function tryAuthEndpoints<T>(
  endpointSuffix: string,
  payload: unknown
): Promise<T> {
  // Direct auth endpoint call
  return await apiRequest<T>(`/api/auth${endpointSuffix}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  return tryAuthEndpoints<TokenResponse>("/login", payload);
}

export async function register(payload: RegisterPayload) {
  return tryAuthEndpoints("/register", payload);
}

export async function getUsage(token: string): Promise<UsageResponse> {
  return apiRequest<UsageResponse>("/api/users/usage", {
    method: "GET",
    token,
  });
}

export async function validateSession(token: string): Promise<boolean> {
  const response = await apiRequest<HealthResponse>("/health", {
    method: "GET",
    token,
  });

  return response.authenticated;
}
