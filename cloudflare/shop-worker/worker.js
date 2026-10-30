// Ingangspunt van de worker cohentra-shop.
// fetch: het publieke deel op shop-api.cohentra.digital.
// ShopService: RPC voor de licentie-worker (service binding SHOP). RPC-methoden zijn niet via internet aan te roepen,
// dus alleen de licentie-worker, die de sessie al heeft gecontroleerd, kan namens een klant of medewerker handelen.

import { WorkerEntrypoint } from "cloudflare:workers";
import { handlePublic, handleCustomer, handleAdmin, safely } from "./app.js";

export class ShopService extends WorkerEntrypoint {
  async customer(request, identity) { return await safely(() => handleCustomer(request, this.env, identity)); }
  async admin(request, actor) { return await safely(() => handleAdmin(request, this.env, actor)); }
}

export default {
  async fetch(request, env) { return await safely(() => handlePublic(request, env)); }
};
