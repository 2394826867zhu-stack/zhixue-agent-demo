const INTERNAL_EMAIL_DOMAIN = "zhiyao.app";

export function normalizeLoginIdentity(value: string) {
  const identity = value.trim();
  return identity.includes("@") ? identity : `${identity}@${INTERNAL_EMAIL_DOMAIN}`;
}

