/**
 * Cryptographic utilities for client-side operations
 */

/**
 * Generate a cryptographically secure random string using the Web Crypto API
 * 
 * @param length - Length of the random string to generate
 * @returns Base64url-encoded random string
 */
export function generateRandomString(length: number): string {
  const buffer = new Uint8Array(length);
  crypto.getRandomValues(buffer);
  
  // Convert to base64url (used by OAuth specs)
  return btoa(String.fromCharCode(...buffer))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}
