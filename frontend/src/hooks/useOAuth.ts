/**
 * OAuth authentication hook
 * Handles Google and GitHub OAuth flows
 */
import { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { generateRandomString } from '@/utils/crypto';

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
    async (provider: 'google' | 'github', nextPath?: string): Promise<string | null> => {
      try {
        // Generate a cryptographically secure random state token
        const state = generateRandomString(32);
        
        // Store state in sessionStorage for validation on callback
        const storageKey = `oauth_state_${provider}`;
        sessionStorage.setItem(storageKey, state);
        
        // Store nextPath if provided for post-auth redirect
        if (nextPath) {
          sessionStorage.setItem(`oauth_next_${provider}`, nextPath);
        }

        // Request auth URL with state parameter
        const response = await fetch(
          `${API_BASE_URL}/api/auth/oauth/authorize/${provider}?state=${encodeURIComponent(state)}`
        );
        
        if (!response.ok) {
          throw new Error(`Failed to get ${provider} auth URL`);
        }
        
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
    async (provider: 'google' | 'github', nextPath?: string) => {
      const authUrl = await getAuthorizationUrl(provider, nextPath);
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
   * Note: State validation is handled by callback pages, not here
   * SECURITY: Tokens are stored in HttpOnly cookies set by backend, not localStorage
   */
  const handleOAuthCallback = useCallback(
    async (provider: 'google' | 'github', code: string): Promise<boolean> => {
      try {
        // Exchange code for token
        const response = await fetch(`${API_BASE_URL}/api/auth/oauth/callback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',  // Include cookies for HttpOnly cookie storage
          body: JSON.stringify({ code, provider }),
        });

        if (!response.ok) {
          // Read response body only once - save for fallback use
          let errorMessage = `${provider} authentication failed`;
          try {
            const data = await response.json();
            errorMessage = data.detail || errorMessage;
          } catch {
            // If JSON parsing fails, try text
            try {
              const text = await response.text();
              errorMessage = text || `HTTP ${response.status}`;
            } catch {
              // Fall back to status info
              errorMessage = `HTTP ${response.status}`;
            }
          }
          throw new Error(errorMessage);
        }

        const data: OAuthToken = await response.json();

        // SECURITY NOTE: Token is now available in HttpOnly cookie set by backend
        // We do NOT store sensitive tokens in localStorage due to XSS vulnerability
        // The backend should return success confirmation, not the token itself
        
        return true;
      } catch (error) {
        console.error(`OAuth callback failed for ${provider}:`, error);
        return false;
      }
    },
    []
  );

  return {
    startOAuthFlow,
    handleOAuthCallback,
    getAuthorizationUrl,
  };
}
