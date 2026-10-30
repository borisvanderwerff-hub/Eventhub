// Node-loader voor lokale tests: vervangt de Cloudflare-runtimemodules door eenvoudige stubs.
export async function resolve(specifier, context, next) {
  if (specifier.startsWith("cloudflare:")) return { url: "cfstub:" + specifier.slice(11), shortCircuit: true };
  return next(specifier, context);
}

export async function load(url, context, next) {
  if (url.startsWith("cfstub:")) {
    return {
      format: "module", shortCircuit: true,
      source: "export function connect() { throw new Error('sockets zijn niet beschikbaar in tests'); }\nexport class WorkerEntrypoint { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }"
    };
  }
  return next(url, context);
}
