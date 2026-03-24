/**
 * OAuth authentication hook
 * Handles Google and GitHub OAuth flows
 */
import { useCallback } from 'react';
import { useRouter } from 'next/navigation';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface OAuthToken {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export function useOAuth() {
  const router = useRouter();

  /**
   * Get authorization URL for the given provider
   */
  const getAuthorizationUrl = useCallback(
    async (provider: 'google' | 'github'): Promise<string | null> => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/auth/oauth/authorize/${provider}`
        );
        if (!response.ok) throw new Error(`Failed to get ${provider} auth URL`);
        const data = await response.json();
        return data.auth_url;
      } catch (error) {
        console.error(`Failed to get ${provider} authorization URL:`, error);
        return null;
      }
    },
    []
  );

  /**
   * Start OAuth flow by redirecting to provider
   */
  const startOAuthFlow = useCallback(
    async (provider: 'google' | 'github') => {
      const authUrl = await getAuthorizationUrl(provider);
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        console.error(`${provider} OAuth is not configured`);
      }
    },
    [getAuthorizationUrl]
  );

  /**
   * Handle OAuth callback from provider
   * Extract code from URL and exchange for token
   */
  const handleOAuthCallback = useCallback(
    async (provider: 'google' | 'github', code: string): Promise<boolean> => {
      try {
        // Exchange code for token
        const response = await fetch(`${API_BASE_URL}/api/auth/oauth/callback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, provider }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || `${provider} authentication failed`);
        }

        const data: OAuthToken = await response.json();

        // Store token
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('token_type', data.token_type);

        // Redirect to dashboard
        router.push('/dashboard');
        return true;
      } catch (error) {
        console.error(`OAuth callback failed for ${provider}:`, error);
        return false;
      }
    },
    [router]
  );

  return {
    startOAuthFlow,
    handleOAuthCallback,
    getAuthorizationUrl,
  };
}
