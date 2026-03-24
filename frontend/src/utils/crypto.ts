/**
 * Cryptographic utilities for client-side operations
 */

/**
 * Generate a cryptographically secure random string using the Web Crypto API
 * 
 * Handles large requests by chunking into 65536-byte segments to avoid
 * QuotaExceededError in browsers. Also chunks String.fromCharCode conversion
 * to avoid RangeError on large arrays.
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
  const randomChunkSize = 65536; // Maximum random values per iteration
  
  // Populate buffer in chunks to avoid QuotaExceededError
  for (let i = 0; i < length; i += randomChunkSize) {
    const end = Math.min(i + randomChunkSize, length);
    crypto.getRandomValues(buffer.subarray(i, end));
  }
  
  // Convert to base64url using chunked String.fromCharCode to avoid RangeError
  // Browser JS engines have limits on function argument count (typically 65536)
  const stringChunkSize = 8192;  // Safe chunk size for String.fromCharCode
  let binaryString = '';
  
  for (let i = 0; i < length; i += stringChunkSize) {
    const end = Math.min(i + stringChunkSize, length);
    const chunk = buffer.subarray(i, end);
    binaryString += String.fromCharCode(...Array.from(chunk));
  }
  
  // Apply base64url encoding
  return btoa(binaryString)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}
