// Zelfde PBKDF2-hash als de licentie-worker, om een bestaand (door staff aangemaakt) portaalaccount na te bootsen.
export async function hashPassword(password) {
  const saltHex = [...crypto.getRandomValues(new Uint8Array(16))].map((b) => b.toString(16).padStart(2, "0")).join("");
  const salt = Uint8Array.from(saltHex.match(/.{2}/g), (b) => parseInt(b, 16));
  const material = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", salt, iterations: 100000, hash: "SHA-256" }, material, 256);
  return { salt: saltHex, hash: [...new Uint8Array(bits)].map((b) => b.toString(16).padStart(2, "0")).join("") };
}
