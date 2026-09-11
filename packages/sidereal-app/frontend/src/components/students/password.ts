// A password a tutor can read out loud without being asked "was that an i or an l?".
const ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789";
const LENGTH = 12;
// Bytes at or above this would wrap the alphabet and make its first letters likelier.
const LIMIT = 256 - (256 % ALPHABET.length);

export function generatePassword(): string {
  let password = "";
  const bytes = new Uint8Array(LENGTH);
  while (password.length < LENGTH) {
    crypto.getRandomValues(bytes);
    for (const byte of bytes) {
      if (byte < LIMIT && password.length < LENGTH) {
        password += ALPHABET.charAt(byte % ALPHABET.length);
      }
    }
  }
  return password;
}
