/**
 * GitHub OAuth Callback Page
 * Handles redirect from GitHub after user authorization
 */
'use client';

import { useEffect, useState, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useOAuth } from '@/hooks/useOAuth';

function GitHubCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { handleOAuthCallback } = useOAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const validationDoneRef = useRef(false);

  useEffect(() => {
    // Guard against React Strict Mode double-execution
    if (validationDoneRef.current) {
      return;
    }
    validationDoneRef.current = true;

    (async () => {
      try {
        const code = searchParams.get('code');
        const state = searchParams.get('state');
        
        // Check if we just reloaded after storing token
        const redirectAfterReload = sessionStorage.getItem('oauth_redirect_after_reload_github');
        const token = window.localStorage.getItem('consilience_access_token');
        
        if (token && redirectAfterReload) {
          // We have a token and a stored redirect path from before reload
          console.log('[GitHub Callback] Post-reload redirect to', redirectAfterReload);
          sessionStorage.removeItem('oauth_redirect_after_reload_github');
          router.push(redirectAfterReload);
          setLoading(false);
          return;
        }

        if (!code) {
          setError('No authorization code received from GitHub');
          setLoading(false);
          return;
        }

        // Validate state token for CSRF protection
        const storedState = sessionStorage.getItem('oauth_state_github');
        if (!state || !storedState || state !== storedState) {
          setError('State mismatch or missing - possible CSRF attack');
          setLoading(false);
          // Clear the stored state
          sessionStorage.removeItem('oauth_state_github');
          return;
        }

        // Clear the stored state after validation (single-use)
        sessionStorage.removeItem('oauth_state_github');

        const success = await handleOAuthCallback('github', code);

        if (!success) {
          setError('Failed to authenticate with GitHub');
          setLoading(false);
        } else {
          // Successfully authenticated - token is now in localStorage
          // Store the next path, then reload to reinitialize AuthContext
          const nextPath = sessionStorage.getItem('oauth_next_github') || '/';
          sessionStorage.removeItem('oauth_next_github');
          sessionStorage.setItem('oauth_redirect_after_reload_github', nextPath);
          setLoading(false);
          
          // Reload page to reinitialize AuthContext with fresh token from localStorage
          console.log('[GitHub Callback] Token stored, reloading to reinitialize auth');
          window.location.reload();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error occurred');
        setLoading(false);
      }
    })();
  }, [searchParams, handleOAuthCallback]);

  if (loading && !error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-800 mx-auto mb-4"></div>
          <p className="text-gray-600">Authenticating with GitHub...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={() => router.push('/login')}
            className="px-4 py-2 border border-[var(--border-strong)] text-[var(--text-primary)] rounded hover:bg-[var(--bg-hover)]"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return null;
}

export default function GitHubCallbackPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--text-primary)] mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    }>
      <GitHubCallbackContent />
    </Suspense>
  );
}
