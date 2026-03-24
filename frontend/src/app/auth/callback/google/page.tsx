/**
 * Google OAuth Callback Page
 * Handles redirect from Google after user authorization
 */
'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useOAuth } from '@/hooks/useOAuth';

export default function GoogleCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { handleOAuthCallback } = useOAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const code = searchParams.get('code');
        const state = searchParams.get('state');

        if (!code) {
          setError('No authorization code received from Google');
          setLoading(false);
          return;
        }

        // Validate state token for CSRF protection
        const storedState = sessionStorage.getItem('oauth_state_google');
        if (!state || !storedState || state !== storedState) {
          setError('State mismatch or missing - possible CSRF attack');
          setLoading(false);
          // Clear the stored state
          sessionStorage.removeItem('oauth_state_google');
          return;
        }

        // Clear the stored state after validation (single-use)
        sessionStorage.removeItem('oauth_state_google');

        const success = await handleOAuthCallback('google', code);

        if (!success) {
          setError('Failed to authenticate with Google');
          setLoading(false);
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
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Authenticating with Google...</p>
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
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return null;
}
