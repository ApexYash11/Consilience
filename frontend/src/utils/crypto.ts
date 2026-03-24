/**
 * Cryptographic utilities for client-side operations
 */

/**
 * Generate a cryptographically secure random string using the Web Crypto API
 * 
 * Handles large requests by chunking into 65536-byte segments to avoid
 * QuotaExceededError in browsers. Input is validated to prevent misuse.
 * 
 * @param length - Length of the random string to generate
 * @returns Base64url-encoded random string
 * @throws {RangeError} if length is not a positive integer or exceeds 1MB
 */
export function generateRandomString(length: number): string {
  // Input validation
  if (!Number.isInteger(length) || length <= 0) {
    throw new RangeError('Length must be a positive integer');
  }
  if (length > 1_000_000) {
    throw new RangeError('Length must not exceed 1MB (1,000,000 bytes)');
  }

  const buffer = new Uint8Array(length);
  const chunkSize = 65536; // Maximum random values per iteration
  
  // Populate buffer in chunks to avoid QuotaExceededError
  for (let i = 0; i < length; i += chunkSize) {
    const end = Math.min(i + chunkSize, length);
    crypto.getRandomValues(buffer.subarray(i, end));
  }
  
  // Convert to base64url (used by OAuth specs)
  return btoa(String.fromCharCode(...buffer))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}
