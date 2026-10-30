import { handleCustomerAuthExtra, handleCustomerAccountShop } from "./accounts-shop.js";
import { loadEffectiveEntitlement, audit } from "../shared/entitlements.js";
import { CUSTOMER_PORTAL_HTML } from "./customer-portal.js";
import { injectShopAdmin } from "./admin-shop-ui.js";
import { connect } from "cloudflare:sockets";

const SUPPORT_HTML = String.raw`<!doctype html>
<html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cohentra | Support</title><style>
:root{color-scheme:light;--ink:#17283a;--muted:#66788b;--line:#dce5ec;--blue:#1768a6;--pale:#f3f7fa;--red:#a33333}*{box-sizing:border-box}body{margin:0;background:#f1f5f8;color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}.top{background:linear-gradient(120deg,#102c44,#1768a6);color:white;padding:22px max(22px,calc((100vw - 1200px)/2));display:flex;justify-content:space-between;align-items:center}.brand{font-size:22px;font-weight:800;letter-spacing:.12em}.brand span{font-weight:400;letter-spacing:.03em}.top p{margin:3px 0 0;color:#d2e5f3}.wrap{max-width:1200px;margin:30px auto;padding:0 20px}.card{background:white;border:1px solid var(--line);border-radius:12px;padding:22px;margin:16px 0;box-shadow:0 3px 14px #16314c0b}h1{font-size:25px;margin:0}h2{font-size:19px;margin:0 0 12px}.muted{color:var(--muted)}label{display:block;font-weight:600;margin:12px 0 5px}input{font:inherit;width:100%;padding:10px 12px;border:1px solid #bdcbd8;border-radius:7px}button,select{font:inherit;border:0;border-radius:7px;padding:9px 12px;background:var(--blue);color:white;cursor:pointer;font-weight:650}button.secondary{background:#e5edf4;color:var(--ink)}select{background:white;color:var(--ink);border:1px solid #bdcbd8}.actions{display:flex;gap:9px;align-items:center;margin-top:14px}.error{color:var(--red);margin-top:8px}.hidden{display:none!important}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;min-width:950px}th,td{text-align:left;border-bottom:1px solid var(--line);padding:10px;vertical-align:top}th{font-size:13px;color:var(--muted)}.status-cell{display:flex;gap:6px}.message{white-space:pre-wrap;overflow-wrap:anywhere;max-width:480px;font-size:14px}.split{display:flex;justify-content:space-between;align-items:center;gap:12px}.icon-button{width:38px;height:38px;padding:0;border-radius:50%;background:#ffffff20;color:white;font-size:21px}.icon-button:hover{background:#ffffff35}.dialog{width:min(440px,calc(100% - 28px));border:1px solid var(--line);border-radius:12px;padding:24px;box-shadow:0 18px 60px #102c4440}.dialog::backdrop{background:#102c4470}.dialog-head{display:flex;justify-content:space-between;align-items:center}.close-button{background:transparent;color:var(--muted);font-size:24px;padding:0 6px}.dialog input{display:block}@media(max-width:600px){.wrap{padding:0 12px}.card{padding:16px}.top{padding:16px 18px}}
</style></head><body><header class="top"><div><div class="brand">COHENTRA <span>digital</span></div><p>Support inbox</p></div><button id="settingsButton" class="icon-button hidden" type="button" aria-label="Instellingen" title="Instellingen">⚙</button></header><main class="wrap">
<section id="login" class="card" style="max-width:460px;margin:46px auto"><h1>Support aanmelden</h1><p class="muted">Gebruik je Cohentra-supportaccount en authenticatorcode.</p><form id="credentialsForm"><label for="username">Gebruikersnaam</label><input id="username" autocomplete="username" required><label for="password">Wachtwoord</label><input id="password" type="password" autocomplete="current-password" required><div class="actions"><button id="loginButton">Verder</button></div><div id="loginError" class="error" role="alert"></div></form><form id="mfaForm" class="hidden"><label for="mfaCode">Authenticator- of herstelcode</label><input id="mfaCode" inputmode="numeric" autocomplete="one-time-code" placeholder="123456" required><div class="actions"><button id="verifyButton">Aanmelden</button><button type="button" class="secondary" id="backButton">Terug</button></div><div id="mfaError" class="error" role="alert"></div></form></section>
<section id="firstPassword" class="card hidden" style="max-width:460px;margin:46px auto"><h1>Tijdelijk wachtwoord vervangen</h1><p class="muted">Kies een eigen wachtwoord om verder te gaan naar de supportinbox.</p><form id="firstPasswordForm"><label for="firstNewPassword">Nieuw wachtwoord</label><input id="firstNewPassword" type="password" autocomplete="new-password" required><label for="firstConfirmPassword">Herhaal nieuw wachtwoord</label><input id="firstConfirmPassword" type="password" autocomplete="new-password" required><div class="actions"><button id="firstPasswordButton">Wachtwoord opslaan</button></div><div id="firstPasswordError" class="error" role="alert"></div></form></section>
<section id="dashboard" class="hidden"><section class="card"><div class="split"><div><h1>Supportaanvragen</h1><p class="muted">Tickets van klanten in Cohentra.</p></div><button class="secondary" id="logout">Afmelden</button></div></section><section class="card"><div class="split"><h2>Inbox</h2><button class="secondary" id="refresh">Vernieuwen</button></div><div class="table-wrap"><table><thead><tr><th>Referentie</th><th>Klant</th><th>Onderwerp / bericht</th><th>Categorie</th><th>Aangemaakt</th><th>Status</th></tr></thead><tbody id="tickets"><tr><td colspan="6" class="muted">Laden…</td></tr></tbody></table></div><div id="ticketError" class="error" role="alert"></div></section></section></main>
<dialog id="settingsDialog" class="dialog"><div class="dialog-head"><h2>Instellingen</h2><button class="close-button" id="closeSettings" type="button" aria-label="Sluiten">×</button></div><section><h3>Profiel</h3><p class="muted">Stel je naam in. Je voornaam wordt gebruikt in de afsluiting van supportmails.</p><form id="profileForm"><label for="profileName">Volledige naam</label><input id="profileName" maxlength="80" autocomplete="name" required><label for="profileFirstName">Voornaam in e-mailhandtekening</label><input id="profileFirstName" maxlength="40" autocomplete="given-name" required><div class="actions"><button id="profileButton">Profiel opslaan</button></div><div id="profileMessage" class="error" role="status"></div></form></section><hr><p class="muted">Wijzig ook hier je wachtwoord.</p><form id="passwordForm"><label for="currentPassword">Huidig wachtwoord</label><input id="currentPassword" type="password" autocomplete="current-password" required><label for="newPassword">Nieuw wachtwoord</label><input id="newPassword" type="password" autocomplete="new-password" required><label for="confirmPassword">Herhaal nieuw wachtwoord</label><input id="confirmPassword" type="password" autocomplete="new-password" required><div class="actions"><button id="passwordButton">Wachtwoord wijzigen</button><button class="secondary" id="cancelSettings" type="button">Annuleren</button></div><div id="passwordMessage" class="error" role="status"></div></form></dialog>
<script>
const $=id=>document.getElementById(id);let token=sessionStorage.getItem('cohentra-support-token')||'',challenge='',passwordChangeToken='';function safe(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}function showLogin(message=''){$('login').classList.remove('hidden');$('firstPassword').classList.add('hidden');$('dashboard').classList.add('hidden');$('settingsButton').classList.add('hidden');$('credentialsForm').classList.remove('hidden');$('mfaForm').classList.add('hidden');$('loginError').textContent=message}function headers(value=token){return {'Authorization':'Bearer '+value,'Content-Type':'application/json'}}async function api(path,options={}){const r=await fetch(path,{...options,headers:{...headers(),...(options.headers||{})}});let d={};try{d=await r.json()}catch{}if(r.status===401){token='';sessionStorage.removeItem('cohentra-support-token');showLogin('Je sessie is verlopen. Meld opnieuw aan.')}if(!r.ok)throw Error(d.error||'De aanvraag is mislukt.');return d}const statuses={new:'Nieuw',in_progress:'In behandeling',waiting_customer:'Wacht op klant',closed:'Afgerond'};function category(v,source,requestType){if(source==='website'){const names={maatwerksoftware:'Software op maat',procesautomatisering:'Procesautomatisering',website:'Website op maat',overig:'Verkennend gesprek'};return 'Websiteformulier · '+(names[requestType]||'Aanvraag')}return ({eventhub:'EventHub gebruiken',license:'Licentie',account:'Account / toegang',other:'Anders'})[v]||v}async function loadTickets(){const d=await api('/api/support/tickets');$('tickets').innerHTML=d.tickets.length?d.tickets.map(t=>'<tr><td><strong>'+safe(t.reference)+'</strong></td><td>'+safe(t.customer_name)+(t.source==='website'&&t.organization?'<br><span class="muted">'+safe(t.organization)+'</span>':'')+'<br><a href="mailto:'+encodeURIComponent(t.contact_email||'')+'">'+safe(t.contact_email||'Geen e-mailadres')+'</a></td><td><strong>'+safe(t.subject)+'</strong><div class="message">'+safe(t.message)+'</div></td><td>'+safe(category(t.category,t.source,t.request_type))+'</td><td>'+safe(new Date(t.created_at).toLocaleString('nl-NL'))+'</td><td><div class="status-cell"><select data-status="'+safe(t.id)+'">'+Object.entries(statuses).map(([k,v])=>'<option value="'+k+'" '+(t.status===k?'selected':'')+'>'+v+'</option>').join('')+'</select><button data-save="'+safe(t.id)+'">Opslaan</button></div></td></tr>').join(''):'<tr><td colspan="6" class="muted">Er zijn nog geen supportaanvragen.</td></tr>'}async function enter(){const [me]=await Promise.all([api('/api/admin/me'),loadTickets()]);$('profileName').value=me.name||'';$('profileFirstName').value=me.first_name||'';$('login').classList.add('hidden');$('firstPassword').classList.add('hidden');$('dashboard').classList.remove('hidden');$('settingsButton').classList.remove('hidden')}async function responseJson(r){let d={};try{d=await r.json()}catch{}if(!r.ok)throw Error(d.error||'De aanvraag is mislukt.');return d}
$('credentialsForm').onsubmit=async e=>{e.preventDefault();$('loginButton').disabled=true;$('loginError').textContent='';try{const d=await responseJson(await fetch('/api/auth/challenge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:$('username').value.trim(),password:$('password').value})}));if(!d.challenge_token)throw Error('Aanmelden met MFA is vereist.');challenge=d.challenge_token;$('credentialsForm').classList.add('hidden');$('mfaForm').classList.remove('hidden');$('mfaCode').focus()}catch(err){$('loginError').textContent=err.message}finally{$('loginButton').disabled=false}};
$('mfaForm').onsubmit=async e=>{e.preventDefault();$('verifyButton').disabled=true;$('mfaError').textContent='';try{const code=$('mfaCode').value.trim().replace(/[\s-]/g,'');const body={challenge_token:challenge,mfa_code:/^\d{6}$/.test(code)?code:'',recovery_code:/^\d{6}$/.test(code)?'':$('mfaCode').value.trim()};const d=await responseJson(await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}));if(d.password_change_required){passwordChangeToken=d.password_change_token;$('login').classList.add('hidden');$('firstPassword').classList.remove('hidden');$('firstNewPassword').focus();return}token=d.session_token;sessionStorage.setItem('cohentra-support-token',token);await enter()}catch(err){$('mfaError').textContent=err.message}finally{$('verifyButton').disabled=false}};
$('firstPasswordForm').onsubmit=async e=>{e.preventDefault();$('firstPasswordButton').disabled=true;$('firstPasswordError').textContent='';try{const d=await responseJson(await fetch('/api/auth/password/first-change',{method:'POST',headers:headers(passwordChangeToken),body:JSON.stringify({new_password:$('firstNewPassword').value,confirm_password:$('firstConfirmPassword').value})}));token=d.session_token;sessionStorage.setItem('cohentra-support-token',token);passwordChangeToken='';$('firstPasswordForm').reset();await enter()}catch(err){$('firstPasswordError').textContent=err.message}finally{$('firstPasswordButton').disabled=false}};
$('backButton').onclick=()=>{challenge='';$('mfaCode').value='';showLogin()};$('tickets').onclick=async e=>{const id=e.target.dataset.save;if(!id)return;const status=$('tickets').querySelector('[data-status="'+CSS.escape(id)+'"]').value;e.target.disabled=true;$('ticketError').textContent='';try{await api('/api/support/tickets/'+encodeURIComponent(id),{method:'PATCH',body:JSON.stringify({status})});await loadTickets()}catch(err){$('ticketError').textContent=err.message}finally{e.target.disabled=false}};$('refresh').onclick=()=>loadTickets().catch(e=>$('ticketError').textContent=e.message);$('settingsButton').onclick=()=>{$('sidebarAccountMenu').open=false;$('passwordForm').reset();$('passwordMessage').textContent='';$('profileMessage').textContent='';$('settingsDialog').showModal()};$('closeSettings').onclick=$('cancelSettings').onclick=()=>$('settingsDialog').close();$('settingsDialog').onclick=e=>{if(e.target===$('settingsDialog'))$('settingsDialog').close()};$('profileForm').onsubmit=async e=>{e.preventDefault();$('profileButton').disabled=true;$('profileMessage').textContent='';try{const d=await api('/api/admin/me',{method:'PATCH',body:JSON.stringify({name:$('profileName').value.trim(),first_name:$('profileFirstName').value.trim()})});$('profileName').value=d.name;$('profileFirstName').value=d.first_name;$('profileMessage').textContent='Profiel opgeslagen.'}catch(err){$('profileMessage').textContent=err.message}finally{$('profileButton').disabled=false}};$('passwordForm').onsubmit=async e=>{e.preventDefault();$('passwordButton').disabled=true;$('passwordMessage').textContent='';try{await api('/api/support/account/password',{method:'POST',body:JSON.stringify({current_password:$('currentPassword').value,new_password:$('newPassword').value,confirm_password:$('confirmPassword').value})});$('passwordForm').reset();$('passwordMessage').textContent='Wachtwoord gewijzigd.';setTimeout(()=>$('settingsDialog').close(),800)}catch(err){$('passwordMessage').textContent=err.message}finally{$('passwordButton').disabled=false}};$('logout').onclick=async()=>{$('sidebarAccountMenu').open=false;token='';sessionStorage.removeItem('cohentra-support-token');showLogin()};if(token)enter().catch(e=>showLogin(e.message));else showLogin();
</script></body></html>`;

const ADMIN_HTML = String.raw`<!doctype html>
<html lang="nl"><head><meta charset="utf-8"><link rel="icon" type="image/png" href="/brand/cohentra-beeldmerk.png"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cohentra | Medewerkersportaal</title>
<style>
:root{color-scheme:light;--ink:#122337;--muted:#66778a;--line:#dce4eb;--blue:#145da0;--pale:#f3f7fa;--red:#a33333}*{box-sizing:border-box}body{margin:0;background:#eef3f7;color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}.wrap{max-width:960px;margin:40px auto;padding:0 20px}.head{margin-bottom:22px}.head h1{margin:0;font-size:28px}.head p{margin:4px 0;color:var(--muted)}.card{background:white;border:1px solid var(--line);border-radius:12px;padding:22px;margin:16px 0;box-shadow:0 3px 14px #16314c0b}h2{font-size:19px;margin:0 0 14px}label{display:block;font-weight:600;margin:12px 0 5px}input{font:inherit;width:100%;padding:10px 12px;border:1px solid #bdcbd8;border-radius:7px}button{font:inherit;border:0;border-radius:7px;padding:10px 15px;background:var(--blue);color:white;cursor:pointer;font-weight:650}button.secondary{background:#e5edf4;color:var(--ink)}button.danger{background:#fff1f0;color:var(--red);padding:7px 10px}button:disabled{opacity:.6;cursor:wait}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.actions{display:flex;gap:10px;align-items:center;margin-top:16px}.error{color:var(--red);margin-top:8px}.notice{background:#edf7ef;border:1px solid #bfdcc5;border-radius:8px;padding:14px;margin:14px 0;overflow-wrap:anywhere}.key{font:700 18px ui-monospace,monospace;letter-spacing:.04em}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:650px}th,td{text-align:left;border-bottom:1px solid var(--line);padding:10px 8px;vertical-align:middle}th{font-size:13px;color:var(--muted)}.muted{color:var(--muted)}.hidden{display:none!important}.topline{display:flex;justify-content:space-between;align-items:center;gap:12px}@media(max-width:600px){.wrap{margin:22px auto}.row{grid-template-columns:1fr}.card{padding:17px}}
.ticket-subject{background:transparent;color:var(--ink);padding:0;text-align:left;font-weight:750}.ticket-subject:hover{text-decoration:underline}.ticket-dialog{width:min(860px,calc(100% - 28px));max-height:88vh;overflow:auto;border:1px solid var(--line);border-radius:14px;padding:24px;box-shadow:0 18px 60px #102c4440}.ticket-dialog::backdrop{background:#102c4470}.conversation{display:grid;gap:12px;max-height:42vh;overflow:auto;margin:18px 0}.conversation-message{padding:14px 16px;border:1px solid var(--line);border-radius:10px;background:var(--pale)}.support-message{background:#f1f6ff;border-color:#cbdcf5}.conversation-meta{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:13px}.conversation-text{white-space:pre-wrap;overflow-wrap:anywhere;margin-top:8px}.sent-label{color:#18794e;font-size:12px;margin:8px 0 0}.ticket-dialog textarea{font:inherit;width:100%;min-height:130px;resize:vertical;padding:12px;border:1px solid #bdcbd8;border-radius:8px}.ticket-dialog .dialog-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}</style><style>.key-table-wrap{max-height:300px;overflow:auto;margin:12px 0}.key-table{min-width:520px;width:100%;table-layout:fixed}.key-table th:first-child{width:150px}.key-table td{overflow-wrap:anywhere}.key-table .key-value{font:600 14px ui-monospace,monospace;word-break:break-all}.key-copy{white-space:nowrap}.actions-menu{position:relative;display:inline-block}.actions-menu summary{list-style:none;cursor:pointer;display:grid;place-items:center;width:34px;height:32px;border:1px solid var(--line);border-radius:7px;font-size:22px;line-height:1}.actions-menu summary::-webkit-details-marker{display:none}.menu-items{position:absolute;right:0;top:calc(100% + 4px);z-index:10;min-width:160px;padding:6px;display:grid;gap:4px;background:white;border:1px solid var(--line);border-radius:8px;box-shadow:0 6px 20px #12233724}.menu-items button{background:transparent;color:var(--ink);text-align:left;padding:8px 10px;font-weight:500;white-space:nowrap}.menu-items button:hover{background:var(--pale)}.menu-items button.menu-danger{color:var(--red)}.license-group{border:1px solid var(--line);border-radius:8px;margin:10px 0;overflow:visible}.license-group>summary{cursor:pointer;padding:12px 14px;font-weight:700;background:var(--pale);border-radius:8px}.license-group[open]>summary{border-radius:8px 8px 0 0}.license-group .table-wrap{padding:0 8px 8px}.license-group table{min-width:820px}.bulk-controls{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:14px 0;padding:12px;background:var(--pale);border:1px solid var(--line);border-radius:8px}.bulk-controls select{font:inherit;width:auto;min-width:180px;padding:9px;border:1px solid #bdcbd8;border-radius:7px;background:white}.license-select{width:18px;height:18px;vertical-align:middle}dialog{width:min(440px,calc(100vw - 32px));border:1px solid var(--line);border-radius:12px;padding:22px;color:var(--ink);box-shadow:0 18px 60px #12233755}dialog::backdrop{background:#10233788}dialog h2{margin:0 0 8px}dialog p{margin:0;color:var(--muted)}dialog .dialog-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:18px}</style>
<style>
body{background:#f3f6f9}
.app-wrap{width:100%;max-width:none;margin:0;padding:0}
.app-wrap>.head{width:min(560px,calc(100% - 40px));margin:40px auto 22px}
.app-wrap>#login,.app-wrap>#loginMfa,.app-wrap>#bootstrap,.app-wrap>#mfaSetup{width:min(560px,calc(100% - 40px));margin:16px auto}
.app-shell{display:grid;grid-template-columns:246px minmax(0,1fr);min-height:100vh}
.sidebar{position:sticky;top:0;align-self:start;height:100vh;height:100dvh;min-height:0;overflow:hidden;background:#112439;color:#f4f8fb;padding:25px 15px 18px;display:flex;flex-direction:column;gap:18px}
.brand{display:flex;align-items:center;gap:11px;padding:0 10px}.brand-mark{width:38px;height:38px;display:grid;place-items:center;background:#1b6eae;border-radius:11px;color:white;font-size:20px;font-weight:800}.brand strong,.brand small{display:block}.brand strong{font-size:16px;letter-spacing:.02em}.brand small{font-size:12px;color:#aebdcb;margin-top:1px}
.nav-list{display:grid;gap:5px;flex:0 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain}.nav-item{display:flex;align-items:center;gap:12px;width:100%;padding:11px 12px;border:1px solid transparent;border-radius:8px;background:transparent;color:#cbd7e2;text-align:left;font-weight:600}.nav-item:hover{background:#1b344b;color:white}.nav-item.active{background:#214969;border-color:#315c7a;color:#fff}.nav-icon{width:20px;text-align:center;font-size:18px;line-height:1}
.sidebar-spacer{flex:1 1 auto;min-height:0}.profile-nav,.sidebar-user,.sidebar-logout{flex:0 0 auto}.sidebar-logout{width:100%;background:transparent;color:#d8e2eb;border:1px solid #354b60;text-align:left}.sidebar-logout:hover{background:#1b344b}
.main-area{width:100%;max-width:1440px;min-width:0;margin:0 auto;padding:40px clamp(22px,4vw,58px) 64px}
.page-heading{margin:0 0 25px}.page-heading h1{margin:3px 0 5px;font-size:32px;line-height:1.2}.page-heading p{margin:0 0 15px;color:var(--muted)}.eyebrow{color:var(--blue);font-size:11px;font-weight:800;letter-spacing:.12em}
.overview-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.stat-card{background:white;border:1px solid var(--line);border-radius:12px;padding:19px 20px;box-shadow:0 3px 14px #16314c0b}.stat-label{display:block;color:var(--muted);font-size:13px;font-weight:600}.stat-value{display:block;margin-top:7px;font-size:30px;line-height:1.1;font-weight:750;letter-spacing:-.03em}.overview-actions{margin-top:18px}.quick-actions{display:flex;flex-wrap:wrap;gap:10px}.quick-actions button{min-height:42px}
.mobile-topbar{display:none}.mobile-menu-backdrop{display:none;position:fixed;inset:0;z-index:40;padding:0;border:0;border-radius:0;background:#0b1c2db0}.admin-view{min-width:0}
.email-template-layout{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px}.email-template-layout>.card{min-width:0}.email-template-layout select,.email-template-layout input[type="text"]{font:inherit;width:100%;padding:10px 12px;border:1px solid #bdcbd8;border-radius:7px;background:white;color:var(--ink)}.email-template-layout textarea{font:inherit;width:100%;min-height:92px;resize:vertical;padding:10px 12px;border:1px solid #bdcbd8;border-radius:7px}.email-template-layout input[type="color"]{width:64px;height:42px;padding:4px}.email-template-layout iframe{display:block}
@media(max-width:820px){.app-shell{display:block}.sidebar{position:fixed;inset:0 auto 0 0;z-index:41;width:min(280px,85vw);height:100dvh;transform:translateX(-105%);transition:transform .22s ease;box-shadow:12px 0 36px #07192b2b}.sidebar.sidebar-open{transform:translateX(0)}.mobile-menu-backdrop.open{display:block}.mobile-topbar{position:sticky;top:0;z-index:20;display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:12px;margin:-24px -16px 24px;padding:12px 16px;background:#fff;border-bottom:1px solid var(--line)}.mobile-topbar strong{font-size:15px}.mobile-topbar span{color:var(--muted);font-size:13px}.mobile-topbar button{padding:8px 11px}.main-area{padding:24px 16px 46px}.overview-grid{grid-template-columns:1fr}.page-heading h1{font-size:28px}}
@media(prefers-reduced-motion:reduce){.sidebar{transition:none}}
</style>
<style>
:root{--ink:#152039;--muted:#73809a;--line:#e2e7f0;--canvas:#f5f7fb;--card:#fff;--navy:#10152a;--purple:#2d64d4;--purple2:#586add;--cyan:#5b8ff0;--green:#138a66;--amber:#a86706;--red:#be4054;--shadow:0 12px 34px #14244b0c}
*{box-sizing:border-box}body{margin:0;background:var(--canvas);color:var(--ink);font:14px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}button,input,select,textarea{font:inherit}button{cursor:pointer}.shell{min-height:100vh;display:grid;grid-template-columns:248px minmax(0,1fr)}.sidebar{background:var(--navy);color:#e9edff;padding:24px 16px;display:flex;flex-direction:column;gap:28px}.brand{display:flex;align-items:center;padding:2px 10px 14px}.brand strong{font-size:22px;letter-spacing:-.6px}.brand strong span{font-weight:400;color:#b6c1df}.brand small{display:block;color:#8793b4;font-size:12px;margin-top:2px}.brandmark{width:40px;height:40px;margin-right:11px;border-radius:13px;background:linear-gradient(135deg,#3268d5,#2cc7e5);display:grid;place-items:center;color:#fff;font-weight:900;font-size:23px;box-shadow:0 5px 18px #2d64d466}.group-label{padding:0 12px;color:#7884a6;font-size:10px;letter-spacing:1.8px;font-weight:800;margin-bottom:8px}.nav{display:grid;gap:5px}.nav button{border:0;background:transparent;color:#b2bdd8;text-align:left;padding:11px 12px;border-radius:10px;font-weight:600;display:flex;align-items:center;gap:11px}.nav button:hover{background:#ffffff0b;color:#fff}.nav button.active{background:#28264a;color:#fff;box-shadow:inset 0 0 0 1px #2e65d4}.ico{width:21px;text-align:center;color:#678fe0;font-size:17px}.side-bottom{margin-top:auto}.user{border-top:1px solid #ffffff16;padding:17px 10px 0;display:flex;align-items:center;gap:10px}.avatar{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#e3eaf9;color:#2452ac;font-weight:800}.user small{display:block;color:#8d98b8;font-size:11px}.user strong{font-size:12px}.main{min-width:0}.topbar{height:74px;background:#ffffffd9;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 34px;position:sticky;top:0;z-index:4;backdrop-filter:blur(16px)}.crumb{color:var(--muted);font-size:12px}.top-actions{display:flex;align-items:center;gap:11px}.preview-tag{font-size:11px;font-weight:800;letter-spacing:.5px;color:#2759be;background:#e8eefa;border:1px solid #ccdaf5;border-radius:999px;padding:7px 10px}.iconbtn{width:36px;height:36px;border:1px solid var(--line);background:#fff;border-radius:10px;color:#54617a}.content{max-width:1500px;margin:0 auto;padding:29px 34px 50px}.heading{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin-bottom:22px}.heading h1{margin:0;font-size:27px;letter-spacing:-.8px}.heading p{margin:5px 0 0;color:var(--muted)}.actions{display:flex;gap:9px;align-items:center}.btn{border:1px solid var(--line);border-radius:9px;padding:10px 14px;background:#fff;color:var(--ink);font-weight:700}.btn:hover{border-color:#9bb6eb;background:#f9fafe}.btn.primary{border:0;color:#fff;background:linear-gradient(110deg,var(--purple),var(--purple2));box-shadow:0 5px 13px #2d64d42a}.btn.primary:hover{filter:brightness(1.05)}.btn.small{padding:7px 10px;font-size:12px}.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:20px}.stat,.panel{background:var(--card);border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow)}.stat{padding:17px 18px}.stat-top{display:flex;justify-content:space-between;align-items:center;color:var(--muted);font-weight:650;font-size:12px}.stat-number{font-size:27px;font-weight:800;letter-spacing:-1px;margin-top:8px}.stat-foot{font-size:11px;color:var(--muted);margin-top:2px}.stat-icon{width:33px;height:33px;border-radius:10px;background:#e8eefa;color:#2d64d4;display:grid;place-items:center;font-size:17px}.filters{display:flex;gap:9px;align-items:center;padding:13px;border-bottom:1px solid var(--line);flex-wrap:wrap}.search{position:relative;flex:1;min-width:220px}.search input{width:100%;padding:10px 12px 10px 36px;border:1px solid var(--line);border-radius:9px;background:#fbfcfe;outline:0;color:var(--ink)}.search input:focus,select:focus,input:focus,textarea:focus{border-color:#6f95e1;box-shadow:0 0 0 3px #2d64d41a;outline:0}.search:before{content:'⌕';position:absolute;left:12px;top:7px;font-size:20px;color:#929db1}.select{padding:9px 11px;border:1px solid var(--line);border-radius:9px;background:#fff;color:#46536d}.layout{display:grid;grid-template-columns:minmax(420px,1.05fr) minmax(400px,.95fr);gap:16px}.panel{overflow:hidden}.panel-head{display:flex;justify-content:space-between;align-items:center;padding:17px 18px 12px}.panel-head h2{font-size:15px;margin:0}.panel-head p{margin:3px 0 0;color:var(--muted);font-size:12px}.queue-count{color:#74809b;font-size:11px}.ticket-list{display:grid}.ticket{border-top:1px solid #eef0f5;padding:15px 18px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px;cursor:pointer;border-left:3px solid transparent}.ticket:hover{background:#fafaff}.ticket.selected{background:#f3f6fd;border-left-color:var(--purple)}.ticket-title{font-size:13px;font-weight:760;display:flex;gap:8px;align-items:center;flex-wrap:wrap}.ticket-sub{font-size:11px;color:var(--muted);margin-top:4px}.ticket-preview{font-size:12px;color:#54617a;margin-top:7px;max-width:510px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ticket-time{text-align:right;font-size:11px;color:#8792a8;white-space:nowrap}.badge{display:inline-flex;align-items:center;border-radius:99px;padding:4px 8px;font-size:10px;font-weight:800;white-space:nowrap}.badge.new{background:#fff2df;color:#9a5b00}.badge.progress{background:#e6ecfa;color:#2859bd}.badge.waiting{background:#e8f5fa;color:#28768f}.badge.closed{background:#e4f5ee;color:#177253}.badge.source{background:#f0f2f6;color:#68748a}.detail{min-height:610px;display:flex;flex-direction:column}.detail-top{padding:17px 19px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.detail-top h2{margin:0;font-size:17px}.detail-meta{color:var(--muted);font-size:11px;margin-top:5px}.detail-body{padding:18px 19px;overflow:auto;flex:1;max-height:440px}.thread-item{margin-bottom:16px;max-width:93%}.thread-item.reply{margin-left:auto}.thread-meta{font-size:11px;color:var(--muted);margin:0 3px 5px;display:flex;justify-content:space-between;gap:12px}.bubble{padding:12px 13px;border-radius:12px;background:#f1f3f8;color:#34415b;white-space:pre-wrap;line-height:1.6}.reply .bubble{background:#e8eefa;color:#1b263a}.reply-form{border-top:1px solid var(--line);padding:14px 17px;background:#fcfcfe}.reply-form label{font-size:11px;font-weight:800;color:#4d5872}.reply-form textarea{width:100%;height:92px;resize:vertical;padding:11px 12px;border:1px solid var(--line);border-radius:9px;margin:7px 0 10px;color:var(--ink);line-height:1.5}.reply-bottom{display:flex;justify-content:space-between;align-items:center;gap:10px}.reply-note{font-size:10px;color:#8590a5}.empty{padding:70px 20px;text-align:center;color:var(--muted)}.empty .big{font-size:30px;margin-bottom:9px;color:#7ea1e5}.view{display:none}.view.active{display:block}.admin-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:16px}.table{width:100%;border-collapse:collapse}.table th,.table td{border-top:1px solid #eef0f5;text-align:left;padding:12px 16px;font-size:12px}.table th{color:#8490a6;font-size:10px;letter-spacing:.7px;text-transform:uppercase;background:#fafbfe}.table td strong{font-size:12px}.table .muted{color:var(--muted);font-size:11px}.product-card{padding:20px}.product-logo{width:43px;height:43px;border-radius:13px;background:linear-gradient(135deg,#2d64d4,#21bfd8);display:grid;place-items:center;color:white;font-weight:900;font-size:21px}.product-row{display:flex;gap:13px;align-items:center}.product-row h3{margin:0;font-size:15px}.product-row p{margin:3px 0 0;font-size:11px;color:var(--muted)}.progressbar{height:7px;background:#edeff5;border-radius:20px;overflow:hidden;margin-top:14px}.progressbar i{display:block;width:62%;height:100%;background:linear-gradient(90deg,#2d64d4,#24c3dc);border-radius:20px}.staff-row{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-top:1px solid #eef0f5;gap:10px}.staff-name{display:flex;align-items:center;gap:10px}.status-dot{width:7px;height:7px;border-radius:100%;background:#1ca478;display:inline-block;margin-right:5px}.status-pill{font-size:10px;font-weight:750;color:#177253;background:#e4f5ee;padding:5px 8px;border-radius:99px}.admin-notice{padding:13px 15px;border:1px solid #dbe5f8;background:#f7f9fd;border-radius:11px;color:#61557f;font-size:12px;margin-top:14px}.mobile-nav{display:none}.dialog-bg{position:fixed;inset:0;background:#10152a80;z-index:10;display:none;place-items:center;padding:20px}.dialog-bg.open{display:grid}.dialog{background:#fff;border-radius:17px;padding:22px;width:min(430px,100%);box-shadow:0 24px 80px #0b12354d}.dialog h2{margin:0 0 6px}.dialog p{color:var(--muted);font-size:12px}.dialog label{display:block;font-size:11px;font-weight:750;margin:13px 0 5px}.dialog input{width:100%;padding:10px;border:1px solid var(--line);border-radius:8px}.dialog-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:18px}.toast{position:fixed;right:24px;bottom:24px;background:#17203a;color:#fff;border-radius:10px;padding:12px 16px;box-shadow:var(--shadow);z-index:20;opacity:0;transform:translateY(10px);transition:.2s;pointer-events:none}.toast.show{opacity:1;transform:translateY(0)}.warning{font-size:10px;color:#8d789e;margin-top:10px}.preview-switch{display:flex;align-items:center;gap:7px;color:#65708a;font-size:11px;font-weight:700}.preview-switch select{border:1px solid #dedfeb;border-radius:8px;background:#fff;padding:7px 9px;color:#28334d;font-weight:700}.permission-list{display:grid}.permission-group{font-size:10px;letter-spacing:1.1px;color:#8993a8;font-weight:850;margin:16px 0 5px}.permission{padding:11px 0;border-top:1px solid #eef0f5;display:flex;align-items:center;justify-content:space-between;gap:10px;cursor:pointer}.permission strong{font-size:12px}.permission small{display:block;color:var(--muted);font-size:10px;margin-top:3px}.permission input{accent-color:var(--purple);width:17px;height:17px}.staff-row{cursor:pointer}.staff-row.selected{background:#f3f6fd}.access-empty{padding:24px;background:#f8f9fc;border-radius:11px;text-align:center;color:var(--muted);font-size:12px}
@media(max-width:1120px){.layout{grid-template-columns:1fr}.detail{min-height:520px}.admin-grid{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}}
@media(max-width:720px){.topbar{height:auto;min-height:62px;padding:10px 14px;gap:8px}.topbar .crumb{display:none}.top-actions{gap:5px}.preview-switch{font-size:9px;gap:4px}.preview-switch select{max-width:125px;padding:6px}.shell{grid-template-columns:1fr}.sidebar{display:none}.topbar{height:62px;padding:0 16px}.content{padding:22px 14px 38px}.heading{align-items:flex-start;flex-direction:column}.heading h1{font-size:24px}.heading .actions{width:100%}.heading .actions .btn{flex:1}.stats{gap:9px}.stat{padding:13px}.stat-number{font-size:23px}.filters{padding:10px}.filters .select{flex:1}.layout{grid-template-columns:minmax(0,1fr)}.panel-head{padding:14px}.ticket{padding:13px 12px}.detail{min-height:560px}.detail-body{max-height:360px}.mobile-nav{display:flex;position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid var(--line);z-index:5;padding:8px 12px calc(8px + env(safe-area-inset-bottom));justify-content:space-around;box-shadow:0 -4px 20px #10152a0c}.mobile-nav button{border:0;background:none;color:#77819a;font-size:10px;display:grid;justify-items:center;gap:3px}.mobile-nav button.active{color:var(--purple);font-weight:800}.mobile-nav b{font-size:17px}.warning{margin-bottom:67px}}

.hidden{display:none!important}body{background:var(--canvas);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}.app-wrap{width:100%;max-width:none;margin:0;padding:0}.app-shell{min-height:100vh;display:grid;grid-template-columns:248px minmax(0,1fr)}.sidebar{position:sticky;top:0;align-self:start;height:100vh;height:100dvh;min-height:0;overflow:hidden;padding:24px 16px;gap:18px}.brand{gap:0;padding:2px 10px 14px}.brand-mark{width:40px;height:40px;flex:0 0 40px;margin-right:11px;border-radius:13px;background:linear-gradient(135deg,#3268d5,#2cc7e5);box-shadow:0 5px 18px #2d64d466;font-size:23px}.brand strong{font-size:22px;letter-spacing:-.6px}.brand small{display:block;color:#8793b4;font-size:12px;margin-top:2px}.group-label{padding:0 12px;color:#7884a6;font-size:10px;letter-spacing:1.8px;font-weight:800;margin-bottom:8px}.nav-list{display:grid;gap:5px;flex:0 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain}.nav-item{border:0;background:transparent;color:#b2bdd8;text-align:left;padding:11px 12px;border-radius:10px;font-weight:600;display:flex;align-items:center;gap:11px}.nav-item:hover{background:#ffffff0b;color:#fff}.nav-item.active{background:#28264a;color:#fff;box-shadow:inset 0 0 0 1px #2e65d4;border-color:transparent}.nav-icon{width:21px;text-align:center;color:#678fe0;font-size:17px}.main-area{min-width:0;max-width:none;margin:0;padding:0}.desktop-topbar{height:74px;background:#ffffffd9;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 34px;position:sticky;top:0;z-index:4;backdrop-filter:blur(16px)}.desktop-topbar>div:first-child strong{font-size:15px}.desktop-topbar>div:first-child span{display:block;color:var(--muted);font-size:12px}.topbar-right{display:flex;align-items:center;gap:11px}.preview-label{font-size:11px;font-weight:800;letter-spacing:.5px;color:#2759be;background:#e8eefa;border:1px solid #ccdaf5;border-radius:999px;padding:7px 10px}.topbar-gear{width:36px;height:36px;border:1px solid var(--line);background:#fff;border-radius:10px;color:#54617a;padding:0}.mobile-topbar{display:none}.admin-view{min-width:0;max-width:1500px;margin:0 auto;padding:29px 34px 50px}.page-heading{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin-bottom:22px}.page-heading h1{margin:0;font-size:27px;letter-spacing:-.8px}.page-heading p{margin:5px 0 0;color:var(--muted)}.eyebrow{display:none}.overview-grid,.support-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:20px}.stat,.stat-card,.card,.panel,.inbox-panel,.ticket-detail-panel{background:var(--card);border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow)}.stat,.stat-card{padding:17px 18px}.stat-label,.stat-top{color:var(--muted);font-weight:650;font-size:12px}.stat-number,.stat-value,.support-stat>strong{font-size:27px;font-weight:800;letter-spacing:-1px;margin-top:8px}.stat-foot,.support-stat>small{font-size:11px;color:var(--muted);margin-top:2px}.stat-value{display:block}.stat-icon{width:33px;height:33px;border-radius:10px;background:#e8eefa;color:#2d64d4;display:grid;place-items:center;font-size:17px}.admin-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:16px}.card,.overview-actions{padding:20px;margin:0 0 16px}.table,.admin-view table{width:100%;border-collapse:collapse;min-width:0}.table th,.table td,.admin-view table th,.admin-view table td{border-top:1px solid #eef0f5;text-align:left;padding:12px 16px;font-size:12px}.table th,.admin-view table th{color:#8490a6;font-size:10px;letter-spacing:.7px;text-transform:uppercase;background:#fafbfe}.table td strong,.admin-view table td strong{font-size:12px}.table .muted,.admin-view table .muted{color:var(--muted);font-size:11px}.table-wrap{max-width:100%;overflow:auto}.admin-view input:not([type=checkbox]),.admin-view select,.dialog input{font:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink);max-width:100%}.admin-view input[type=checkbox]{accent-color:var(--purple)}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.actions{display:flex;gap:9px;align-items:center}.admin-view label{font-size:11px;font-weight:750;color:#4d5872}.admin-view button:not(.nav-item),.dialog button{border-radius:9px}.admin-view button:not(.nav-item):not(.btn),.dialog button:not(.btn){border:1px solid var(--line);padding:10px 14px;background:#fff;color:var(--ink);font-weight:700}.admin-view button:not(.nav-item):not(.btn):not(.secondary):not(.danger),.dialog button.primary{border:0;color:#fff;background:linear-gradient(110deg,var(--purple),var(--purple2));box-shadow:0 5px 13px #2d64d42a}.admin-view button.secondary{background:#fff;color:var(--ink)}.admin-view button.danger{background:#fff2f2;color:var(--red)}.support-workspace{grid-template-columns:minmax(420px,1.05fr) minmax(400px,.95fr);gap:16px}.support-workspace>.panel{min-width:0}.inbox-panel,.ticket-detail-panel{overflow:hidden}.inbox-panel-head,.ticket-detail-head{display:flex;justify-content:space-between;align-items:flex-start;padding:17px 18px 12px;gap:10px}.inbox-panel h2,.ticket-detail-panel h2{font-size:15px;margin:0}.inbox-panel-head p{margin:3px 0 0;color:var(--muted);font-size:12px}.inbox-filters{display:flex;gap:9px;align-items:center;padding:13px;border-bottom:1px solid var(--line);flex-wrap:wrap}.inbox-filters .search{position:relative;flex:1;min-width:220px}.inbox-filters input{width:100%;padding:10px 12px 10px 36px;border:1px solid var(--line);border-radius:9px;background:#fbfcfe}.inbox-filters select,.reply-actions select{padding:9px 11px;border:1px solid var(--line);border-radius:9px;background:#fff;color:#46536d}.ticket-list{display:grid}.ticket-row{border-top:1px solid #eef0f5;padding:15px 18px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:9px;cursor:pointer;border-left:3px solid transparent;background:#fff;color:var(--ink);text-align:left;width:100%}.ticket-row:hover{background:#fafaff}.ticket-row.selected{background:#f3f6fd;border-left-color:var(--purple)}.ticket-row-title{font-size:13px;font-weight:760;display:flex;gap:8px;align-items:center;flex-wrap:wrap}.ticket-row-meta{font-size:11px;color:var(--muted);margin-top:4px;display:block}.ticket-row-snippet{font-size:12px;color:#54617a;margin-top:7px;max-width:510px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}.ticket-row-side{text-align:right;font-size:11px;color:#8792a8;white-space:nowrap}.status-badge{display:inline-flex;align-items:center;border-radius:99px;padding:4px 8px;font-size:10px;font-weight:800;white-space:nowrap}.status-new{background:#fff2df;color:#9a5b00}.status-in_progress{background:#e6ecfa;color:#2859bd}.status-waiting_customer{background:#e8f5fa;color:#28768f}.status-closed{background:#e4f5ee;color:#177253}.source-badge{background:#f0f2f6;color:#68748a}.detail{min-height:610px;display:flex;flex-direction:column}.ticket-detail-head{padding:17px 19px;border-bottom:1px solid var(--line)}.ticket-detail-head h2{margin:0;font-size:17px}.ticket-detail-head p{color:var(--muted);font-size:11px;margin-top:5px}.conversation{padding:18px 19px;overflow:auto;flex:1;max-height:440px}.conversation-message{margin-bottom:16px;max-width:93%}.conversation-message.support-message{margin-left:auto}.conversation-meta{font-size:11px;color:var(--muted);margin:0 3px 5px;display:flex;justify-content:space-between;gap:12px}.conversation-text{padding:12px 13px;border-radius:12px;background:#f1f3f8;color:#34415b;white-space:pre-wrap;line-height:1.6;overflow-wrap:anywhere}.conversation-message.support-message .conversation-text{background:#e8eefa;color:#1b263a}.reply-composer{border-top:1px solid var(--line);padding:14px 17px;background:#fcfcfe}.reply-composer label{font-size:11px;font-weight:800;color:#4d5872}.reply-composer textarea{width:100%;height:92px;resize:vertical;padding:11px 12px;border:1px solid var(--line);border-radius:9px;margin:7px 0 10px;color:var(--ink);line-height:1.5}.reply-actions{display:flex;justify-content:space-between;align-items:center;gap:10px}.reply-actions>span{font-size:10px;color:#8590a5}.empty{padding:46px 20px;text-align:center;color:var(--muted)}.empty .big{font-size:30px;margin-bottom:9px;color:#7ea1e5}.profile-disclosure{background:#fff;border:1px solid var(--line);border-radius:15px;padding:16px 20px;margin:16px 0}.profile-disclosure summary{cursor:pointer;font-weight:700}.profile-fields{max-width:560px}.mfa-required-label{display:inline-flex;margin:0 0 10px;padding:6px 10px;border-radius:999px;background:#e8eefa;color:#2759be;font-size:11px;font-weight:800}.pf-avatar-row{display:flex;align-items:center;gap:16px;margin:4px 0 22px;padding:14px;background:#f8f9fc;border:1px solid #edf0f6;border-radius:12px}.pf-avatar{width:76px;height:76px;flex:0 0 76px;border-radius:50%;display:grid;place-items:center;overflow:hidden;background:#e3eaf9;color:#2452ac;font-size:23px;font-weight:850}.pf-avatar img,.user-avatar img{width:100%;height:100%;object-fit:cover}.pf-avatar-controls{min-width:0}.pf-avatar-controls>strong{font-size:13px}.pf-avatar-controls p{margin:3px 0 9px;font-size:11px}.pf-avatar-actions{display:flex;gap:8px;flex-wrap:wrap}.pf-avatar-actions button{padding:7px 10px!important;font-size:12px}.pf-avatar-actions input{display:none}.pf-avatar-row .avatar-message{min-height:16px;margin:6px 0 0;font-size:11px}.user-avatar{position:relative;overflow:hidden}.user-avatar img{position:absolute;inset:0;border-radius:inherit}.product-card{padding:20px}.product-logo{width:43px;height:43px;border-radius:13px;background:linear-gradient(135deg,#2d64d4,#21bfd8);display:grid;place-items:center;color:white;font-weight:900;font-size:21px}.product-row{display:flex;gap:13px;align-items:center}.product-row h3{margin:0;font-size:15px}.product-row p{margin:3px 0 0;font-size:11px;color:var(--muted)}.status-pill{font-size:10px;font-weight:750;color:#177253;background:#e4f5ee;padding:5px 8px;border-radius:99px}.admin-notice{padding:13px 15px;border:1px solid #dbe5f8;background:#f7f9fd;border-radius:11px;color:#61557f;font-size:12px;margin-top:14px}.permission-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.permission-choice{padding:11px 10px;border-top:1px solid #eef0f5;display:flex!important;align-items:center;justify-content:space-between;gap:10px}.staff-functions{display:flex;flex-wrap:wrap;gap:7px;min-width:180px}.staff-function-choice{display:flex!important;align-items:center;gap:6px;margin:4px 0!important;white-space:nowrap}.staff-function-choice input{width:16px!important;height:16px;margin:0!important}.sidebar-logout{margin-top:8px;width:100%;border:1px solid #ffffff25!important;background:transparent!important;color:#d8e2eb!important;text-align:left}.mobile-menu-backdrop{display:none}.error{color:var(--red);margin:8px 16px}.notice{padding:13px 15px;border:1px solid #dbe5f8;background:#f7f9fd;border-radius:11px;color:#61557f;font-size:12px;margin-top:14px;overflow-wrap:anywhere}.key{font:700 15px ui-monospace,monospace;word-break:break-all}
@media(max-width:1120px){.support-workspace{grid-template-columns:1fr}.detail{min-height:520px}.admin-grid{grid-template-columns:1fr}.overview-grid,.support-stats{grid-template-columns:repeat(2,1fr)}}
@media(max-width:720px){.app-shell{grid-template-columns:1fr}.sidebar{display:none}.desktop-topbar{height:62px;padding:0 16px}.desktop-topbar .preview-label{display:none}.main-area{padding:0}.admin-view{padding:22px 14px 90px}.page-heading{align-items:flex-start;flex-direction:column}.page-heading h1{font-size:24px}.page-heading .actions{width:100%}.page-heading .actions .btn{flex:1}.overview-grid,.support-stats{gap:9px}.stat,.stat-card{padding:13px}.stat-number,.stat-value,.support-stat>strong{font-size:23px}.inbox-filters{padding:10px}.support-workspace{grid-template-columns:minmax(0,1fr)}.panel-head{padding:14px}.ticket-row{padding:13px 12px}.detail{min-height:560px}.conversation{max-height:360px}.mobile-nav{display:flex;position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid var(--line);z-index:5;padding:8px 12px calc(8px + env(safe-area-inset-bottom));justify-content:space-around;box-shadow:0 -4px 20px #10152a0c}.mobile-nav button{border:0;background:none;color:#77819a;font-size:10px;display:grid;justify-items:center;gap:3px;padding:4px}.mobile-nav button.active{color:var(--purple);font-weight:800}.mobile-nav b{font-size:17px}.row{grid-template-columns:1fr}.permission-grid{grid-template-columns:1fr}.admin-view table{min-width:700px}.table-wrap{overflow:auto}.ticket-list .empty{padding:25px 12px}}
.support-heading-actions{display:flex;gap:9px;align-items:center}.support-sync-status{font-size:12px!important;min-height:18px}.support-workspace{display:grid;grid-template-columns:minmax(420px,1.05fr) minmax(400px,.95fr);align-items:stretch}.admin-view button.ticket-row{display:grid;width:100%;text-align:left;background:#fff!important;background-image:none!important;color:var(--ink)!important;border:0;border-top:1px solid #eef0f5;border-left:3px solid transparent;border-radius:0;box-shadow:none!important;padding:15px 18px}.admin-view button.ticket-row:hover{background:#fafaff!important}.admin-view button.ticket-row.selected{background:#f3f6fd!important;border-left-color:var(--purple)}.admin-view button.ticket-row .ticket-row-meta{color:var(--muted)!important}.admin-view button.ticket-row .ticket-row-snippet{color:#54617a!important}.permission-grid{grid-template-columns:1fr;gap:0}.admin-view label.permission-choice{display:flex!important;align-items:center;justify-content:flex-start!important;gap:12px;width:100%;padding:12px 6px;white-space:normal}.permission-choice input[type=checkbox]{width:16px;min-width:16px;height:16px;flex:0 0 16px}.permission-choice span{flex:1;text-align:left;white-space:normal}.sidebar-user{display:flex;align-items:center;gap:10px;padding:13px 10px 2px;border-top:1px solid #ffffff18;color:#f2f4ff}.sidebar-user strong{display:block;font-size:12px;max-width:155px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sidebar-user small{display:block;color:#8d98b8;font-size:11px;margin-top:2px}.user-avatar{width:34px;height:34px;flex:0 0 34px;border-radius:50%;display:grid;place-items:center;background:#e3eaf9;color:#2452ac;font-weight:850;font-size:12px}.account-label{margin:0 0 -18px}.profile-nav{width:100%}.desktop-topbar #topbarUser{color:#65708a;font-size:12px;font-weight:700}.mobile-nav{display:none}
@media(max-width:720px){.support-heading-actions{width:100%;flex-wrap:wrap}.support-heading-actions button{flex:1}.support-sync-status{min-height:0}}
@media(max-width:720px){.mobile-nav{display:flex}.sidebar-user{margin-top:6px}.admin-view table{min-width:700px}}
/* Compact portal navigation: a single sticky top bar with focused dropdowns. */
.app-shell{display:block;min-height:100vh}.sidebar{display:none!important}.main-area{min-height:100vh}.desktop-topbar{gap:16px;padding:0 24px}.portal-menu,.account-menu{position:relative}.portal-menu>summary,.account-menu>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:9px;white-space:nowrap;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--ink);padding:8px 11px;font-size:12px;font-weight:700}.portal-menu>summary::-webkit-details-marker,.account-menu>summary::-webkit-details-marker{display:none}.portal-menu>summary:hover,.account-menu>summary:hover{border-color:#b1c6ef;background:#f9fafe}.portal-menu[open]>summary,.account-menu[open]>summary{border-color:#9ab5ea;box-shadow:0 0 0 3px #2d64d415}.portal-menu-panel,.account-menu-panel{position:absolute;z-index:50;top:calc(100% + 8px);right:0;min-width:220px;padding:6px;background:#fff;border:1px solid var(--line);border-radius:12px;box-shadow:0 14px 36px #14244b20}.portal-menu-panel{left:0;right:auto}.portal-menu-panel button,.account-menu-panel button{display:flex;align-items:center;gap:10px;width:100%;padding:9px 10px;border:0;border-radius:8px;background:transparent;color:var(--ink);text-align:left;font-size:13px;font-weight:600}.portal-menu-panel button:hover,.account-menu-panel button:hover,.portal-menu-panel button:focus-visible,.account-menu-panel button:focus-visible{background:#f0f4fc;outline:none}.portal-menu-panel button.active{background:#e8eefa;color:#2657ba}.menu-link-icon{width:20px;color:var(--purple);text-align:center}.topbar-right{min-width:0}.topbar-right .preview-label{font-size:10px}.account-menu>summary{padding:5px 9px 5px 6px}.account-menu .user-avatar{width:30px;height:30px;flex-basis:30px}.account-menu .user-avatar img{position:absolute;inset:0}.account-menu-name{max-width:180px;overflow:hidden;text-overflow:ellipsis}.account-menu-panel{min-width:190px}.account-menu-panel button:last-child{color:var(--red)}.account-menu-separator{height:1px;background:var(--line);margin:5px 4px}.mobile-topbar,.mobile-nav,.mobile-menu-backdrop{display:none!important}.pf-avatar img[hidden],.user-avatar img[hidden],.sx-agent-avatar img[hidden]{display:none!important}
.avatar-crop-dialog{width:min(520px,calc(100vw - 28px));max-height:min(90vh,760px);overflow:auto;border:1px solid var(--line);border-radius:18px;padding:22px;background:#fff;color:var(--ink);box-shadow:0 22px 70px #10152a40}.avatar-crop-dialog::backdrop{background:#10152a88;backdrop-filter:blur(3px)}.avatar-crop-dialog h2{margin:0;font-size:19px}.avatar-crop-dialog p{margin:5px 0 15px;color:var(--muted);font-size:13px}.avatar-crop-stage{width:min(320px,70vw);aspect-ratio:1;margin:14px auto;overflow:hidden;border-radius:50%;background:#e3eaf9;touch-action:none;cursor:grab;box-shadow:0 0 0 1px #dfe3ee,0 0 0 8px #f3f5fa}.avatar-crop-stage:active{cursor:grabbing}.avatar-crop-stage canvas{display:block;width:100%;height:100%}.avatar-crop-zoom{max-width:420px;margin:20px auto 4px}.avatar-crop-zoom label{display:flex;justify-content:space-between;gap:10px;margin-bottom:8px;font-size:12px;font-weight:700}.avatar-crop-zoom input{width:100%;accent-color:var(--purple)}.avatar-crop-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:18px}.avatar-crop-actions button{min-width:90px}
@media(max-width:820px){.desktop-topbar{height:64px;padding:0 14px;gap:8px}.desktop-topbar>div:first-child span,.topbar-right .preview-label{display:none}.desktop-topbar>div:first-child strong{font-size:14px}.topbar-right{gap:7px}.portal-menu>summary,.account-menu>summary{padding:7px 8px;font-size:11px}.account-menu-name{max-width:100px}.admin-view{padding:22px 16px 40px}.portal-menu-panel{position:fixed;top:60px;left:12px;right:12px;min-width:0}.account-menu-panel{right:0;min-width:185px}}
@media(max-width:430px){.desktop-topbar{padding:0 10px}.desktop-topbar>div:first-child strong{max-width:90px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.portal-menu>summary{gap:5px}.portal-menu-label{display:none}.account-menu-name{max-width:75px}.admin-view{padding-left:12px;padding-right:12px}}

/* Keep staff pages readable at high browser zoom and give avatar images a real crop frame. */
.desktop-topbar{height:64px;padding:0 clamp(16px,2.4vw,32px);background:#fffffff2}
.admin-view{max-width:1360px;padding:24px 28px 38px}
.user-avatar{position:relative;overflow:hidden}
.account-menu .user-avatar img{position:absolute;inset:0;object-fit:cover}
.user-avatar>img:not([hidden]),.pf-avatar>img:not([hidden]){display:block!important}
#view-support .sx-work,#view-customers .cx-work{max-width:1220px;height:clamp(420px,calc(100dvh - 220px),760px);min-height:420px;margin-left:auto;margin-right:auto}
@media(min-width:901px){#view-support .sx-work{height:clamp(540px,calc(100dvh - 160px),900px);min-height:0}}
@media(max-width:820px){.desktop-topbar{height:60px;padding:0 12px}.admin-view{padding:19px 14px 32px}#view-support .sx-work,#view-customers .cx-work{height:auto;min-height:0;max-height:none}}
@media(max-width:430px){.portal-menu-label{display:inline}.account-menu-name{max-width:82px}}

#view-support{--sx-new:#2d64d4;--sx-new-bg:#e8eefa;--sx-prog:#2477c9;--sx-prog-bg:#e7f1fb;--sx-wait:#a86706;--sx-wait-bg:#fdf3e1;--sx-done:#138a66;--sx-done-bg:#e5f5ee;--sx-note:#fff8e3;--sx-note-line:#ecd28b;--sx-note-ink:#6e4a07}
.sx-s-new{--c:var(--sx-new);--b:var(--sx-new-bg)}.sx-s-in_progress{--c:var(--sx-prog);--b:var(--sx-prog-bg)}.sx-s-waiting_customer{--c:var(--sx-wait);--b:var(--sx-wait-bg)}.sx-s-closed{--c:var(--sx-done);--b:var(--sx-done-bg)}
#view-support .sx-head{display:flex;align-items:center;gap:12px;margin:0 0 14px}#view-support .sx-head h1{margin:0;font-size:24px;line-height:1.2}.sx-sync{font-size:12px;color:var(--muted)}.sx-spacer{flex:1}
#view-support .sx-icon{width:36px;height:36px;padding:0;display:grid;place-items:center;background:#fff;color:var(--ink);border:1px solid var(--line);box-shadow:none;font-size:17px;line-height:1}#view-support .sx-icon.spinning span{display:inline-block;animation:sxspin 1s linear infinite}@keyframes sxspin{to{transform:rotate(360deg)}}
.sx-work{display:grid;grid-template-columns:minmax(260px,340px) minmax(0,1fr);height:calc(100vh - 190px);min-height:540px;background:var(--card);border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow)}
.sx-list-pane{display:flex;flex-direction:column;min-height:0;min-width:0;border-right:1px solid var(--line)}.sx-tools{padding:12px;display:grid;gap:8px;border-bottom:1px solid var(--line)}#view-support .sx-tools input{width:100%;padding:8px 11px;font-size:13px;background:#fbfcfe}.sx-tools-row{display:flex;align-items:center;justify-content:space-between;gap:8px}.sx-hint{font-size:11px;color:var(--muted)}
.sx-tickets{overflow:auto;flex:1;min-height:0;border-radius:0 0 0 15px}
#view-support .sx-row{display:block;width:100%;text-align:left;background:#fff;color:var(--ink);border:0;border-bottom:1px solid #eef0f5;border-left:3px solid transparent;border-radius:0;box-shadow:none;padding:11px 14px 11px 13px;font-weight:400}#view-support .sx-row:hover{background:#fafaff}#view-support .sx-row.selected{background:#f0f4fc;border-left-color:var(--purple)}
.sx-row-top{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.sx-row-name{font-weight:700;font-size:13px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:flex;align-items:center;gap:6px}.sx-row-when{font-size:11px;color:var(--muted);white-space:nowrap}.sx-row-when.late{color:var(--red);font-weight:700}
.sx-row-subject{display:block;font-size:13px;margin:2px 0 4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sx-row-foot{font-size:11px;color:var(--muted);display:flex;align-items:center;gap:6px;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sx-unread{width:7px;height:7px;border-radius:50%;background:var(--purple);flex:none}.sx-dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex:none;background:var(--c,currentColor)}
#view-support .sx-pill{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:4px 10px 4px 9px;font-size:12px;font-weight:600;border:1px solid var(--line);background:#fff;color:var(--ink);box-shadow:none;white-space:nowrap}#view-support .sx-status{background:var(--b);color:var(--c);border-color:transparent}#view-support .sx-status[data-readonly]{cursor:default}
.sx-count{color:var(--muted);font-weight:500;font-size:12px}.sx-caret{font-size:10px;opacity:.75}.sx-pop{position:relative}
.sx-menu{position:absolute;z-index:30;min-width:200px;padding:4px;background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:0 12px 30px #14244b1f;top:calc(100% + 4px);left:0}.sx-menu-right{left:auto;right:0}.sx-menu-up{top:auto;bottom:calc(100% + 6px);left:auto;right:0}
#view-support .sx-menu button{display:flex;align-items:center;gap:9px;width:100%;text-align:left;background:transparent;color:var(--ink);border:0;box-shadow:none;padding:7px 9px;border-radius:7px;font-size:13px;font-weight:500}#view-support .sx-menu button:hover,#view-support .sx-menu button:focus-visible{background:#f4f5fa;outline:none}
.sx-menu-label{flex:1}.sx-menu-label small{display:block;font-size:11px;color:var(--muted);font-weight:400}.sx-menu-check{color:var(--purple);font-weight:800}.sx-menu-title{font-size:11px;color:var(--muted);padding:5px 9px 3px}.sx-sep{height:1px;background:var(--line);margin:4px 6px}.sx-menu-icon{width:8px;flex:none}
.sx-detail{display:flex;flex-direction:column;min-width:0;min-height:0}.sx-detail-head{padding:14px 18px;border-bottom:1px solid var(--line)}.sx-title-row{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}#view-support .sx-detail-head h2{margin:0;font-size:17px;overflow-wrap:anywhere}.sx-meta{margin:3px 0 0;font-size:11px;color:var(--muted)}
.sx-facts{display:flex;flex-wrap:wrap;gap:4px 16px;margin-top:9px;font-size:12px;color:#54617a}.sx-facts:empty{display:none}.sx-facts a{color:var(--purple)}#view-support .sx-link{background:none;border:0;box-shadow:none;padding:0;color:var(--purple);font-weight:600;font-size:12px;text-decoration:underline}
.sx-conv{flex:1;min-height:0;overflow:auto;padding:16px 18px;display:flex;flex-direction:column;gap:12px;background:#fcfcfe}.sx-day{align-self:center;font-size:11px;color:var(--muted);background:#f0f2f7;border-radius:999px;padding:2px 10px}
.sx-msg{max-width:78%;align-self:flex-start}.sx-msg.out{align-self:flex-end}.sx-msg-meta{font-size:11px;color:var(--muted);margin:0 3px 4px}.sx-msg.out .sx-msg-meta{text-align:right}
.sx-msg-author{display:inline-flex;align-items:center;gap:6px;vertical-align:middle}.sx-agent-avatar{position:relative;display:inline-grid;place-items:center;width:22px;height:22px;flex:0 0 22px;border-radius:50%;overflow:visible;background:#e3eaf9;color:#2452ac;font-size:8px;font-weight:850;text-align:center;cursor:default;vertical-align:middle}.sx-agent-avatar>span,.sx-agent-avatar>img{position:absolute;inset:0;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;object-fit:cover}.sx-agent-avatar::after{content:attr(data-name);position:absolute;z-index:8;left:50%;bottom:calc(100% + 7px);transform:translate(-50%,3px);padding:5px 8px;border-radius:6px;background:#10152a;color:#fff;font-size:10px;font-weight:650;white-space:nowrap;opacity:0;pointer-events:none;transition:opacity .14s,transform .14s}.sx-agent-avatar:hover::after,.sx-agent-avatar:focus-visible::after{opacity:1;transform:translate(-50%,0)}.sx-agent-avatar:focus-visible{outline:2px solid var(--purple);outline-offset:2px}
.sx-bubble{padding:9px 12px;border-radius:12px;background:#eef0f5;color:#2c3850;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55}.sx-msg.out .sx-bubble{background:#e8eefa;color:#1b263a}.sx-msg.note .sx-bubble{background:var(--sx-note);color:var(--sx-note-ink);border:1px dashed var(--sx-note-line)}.sx-msg.failed .sx-bubble{border:1px solid #f1c3ca}.sx-failed{color:var(--red);font-weight:700}
.sx-empty{margin:auto;padding:24px 16px;color:var(--muted);text-align:center;font-size:13px}
.sx-composer{border-top:1px solid var(--line);padding:10px 16px 12px;background:#fff;border-radius:0 0 15px 0}.sx-composer-top{display:flex;justify-content:space-between;align-items:center;gap:10px}.sx-to{font-size:12px;color:#54617a;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sx-switch{position:relative;display:inline-flex;align-items:center;gap:7px;font-size:12px;color:#54617a;cursor:pointer;white-space:nowrap;user-select:none}.sx-switch input{position:absolute;opacity:0;width:1px;height:1px;margin:0}
.sx-track{position:relative;width:28px;height:16px;border-radius:999px;background:#d5dae5;transition:background .15s}.sx-track::after{content:"";position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;background:#fff;transition:left .15s;box-shadow:0 1px 2px #0003}.sx-switch input:checked+.sx-track{background:#e0a526}.sx-switch input:checked+.sx-track::after{left:14px}.sx-switch input:focus-visible+.sx-track{outline:2px solid var(--purple);outline-offset:2px}.sx-switch input:disabled+.sx-track{opacity:.6}
#view-support .sx-composer textarea{display:block;width:100%;height:84px;resize:vertical;margin:7px 0 0;padding:10px 12px;border:1px solid var(--line);border-radius:9px;font:inherit;line-height:1.5;color:var(--ink);background:#fff}#view-support .sx-composer.note textarea{background:var(--sx-note);border-color:var(--sx-note-line)}
.sx-field-error{margin:5px 0 0;font-size:12px;color:var(--red)}.sx-actions{position:relative;display:flex;justify-content:flex-end;align-items:center;gap:10px;margin-top:9px}.sx-after{font-size:11px;color:var(--muted);display:inline-flex;align-items:center;gap:5px}.sx-split{display:inline-flex}
#view-support .sx-split button{border-radius:9px 0 0 9px;padding:8px 14px;font-size:13px}#view-support .sx-split button+button{border-radius:0 9px 9px 0;padding:8px 10px;border-left:1px solid #ffffff66}
#view-support .sx-composer.note .sx-split button+button,#view-support .sx-composer.note .sx-after,#view-support .sx-composer.no-status .sx-split button+button,#view-support .sx-composer.no-status .sx-after{display:none}#view-support .sx-composer.note .sx-split button,#view-support .sx-composer.no-status .sx-split button{border-radius:9px}
.sx-confirm{margin-top:9px;padding:11px 13px;border-radius:10px;background:#fdf3e1;color:#6e4a07;font-size:12.5px;border:1px solid #f1d9a6}.sx-confirm p{margin:0;line-height:1.5}.sx-confirm div{display:flex;justify-content:flex-end;gap:8px;margin-top:9px}#view-support .sx-confirm button{padding:7px 12px;font-size:12px}
.sx-nav-badge{margin-left:auto;min-width:19px;height:19px;padding:0 6px;border-radius:999px;background:var(--purple);color:#fff;font-size:11px;font-weight:800;display:inline-grid;place-items:center}
@media(max-width:900px){.sx-work{grid-template-columns:minmax(0,1fr);height:auto;min-height:0}.sx-list-pane{border-right:0;border-bottom:1px solid var(--line)}.sx-tickets{max-height:300px}.sx-conv{max-height:460px}.sx-msg{max-width:92%}}
#view-customers,#view-team,#view-profile{--cx-warn:#a86706;--cx-warn-bg:#fdf3e1;--cx-ok:#138a66;--cx-ok-bg:#e5f5ee;--cx-danger-bg:#fdecee}
#view-customers .cx-head{display:flex;align-items:center;gap:12px;margin:0 0 14px}#view-customers .cx-head h1{margin:0;font-size:24px;line-height:1.2}.cx-sub{font-size:12px;color:var(--muted)}.cx-spacer{flex:1}
.cx-work{display:grid;grid-template-columns:minmax(250px,320px) minmax(0,1fr);height:calc(100vh - 190px);min-height:540px;background:var(--card);border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow)}
.cx-list-pane{display:flex;flex-direction:column;min-height:0;min-width:0;border-right:1px solid var(--line)}.cx-tools{padding:12px;display:grid;gap:8px;border-bottom:1px solid var(--line)}#view-customers .cx-tools input{width:100%;padding:8px 11px;font-size:13px;background:#fbfcfe}.cx-tools-row{display:flex;align-items:center;justify-content:space-between;gap:8px}
.cx-list{overflow:auto;flex:1;min-height:0;border-radius:0 0 0 15px}
#view-customers .cx-row{display:block;width:100%;text-align:left;background:#fff;color:var(--ink);border:0;border-bottom:1px solid #eef0f5;border-left:3px solid transparent;border-radius:0;box-shadow:none;padding:11px 14px 11px 13px;font-weight:400}#view-customers .cx-row:hover{background:#fafaff}#view-customers .cx-row.selected{background:#f0f4fc;border-left-color:var(--purple)}
.cx-row-top{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.cx-row-name{font-weight:700;font-size:13px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cx-row-sub{display:block;font-size:11px;color:var(--muted);margin:2px 0 6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cx-chips{display:flex;gap:4px;flex-wrap:wrap}.cx-chip{font-size:11px;color:#54617a;border:1px solid var(--line);border-radius:999px;padding:0 7px;white-space:nowrap}.cx-chip.full{color:var(--cx-warn);border-color:#f1d9a6}.cx-tag{font-size:10px;font-weight:700;border-radius:999px;padding:1px 7px;white-space:nowrap}.cx-tag.paused{background:var(--cx-warn-bg);color:var(--cx-warn)}.cx-tag.dup{background:#f0f2f7;color:#54617a}
.cx-detail{overflow:auto;min-width:0;min-height:0;border-radius:0 15px 15px 0}
.cx-sec{padding:14px 18px;border-bottom:1px solid var(--line)}.cx-sec:last-child{border-bottom:0}.cx-sec-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:9px}.cx-sec-title{font-size:11px;font-weight:800;letter-spacing:.06em;color:var(--muted)}
.cx-title{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}#view-customers .cx-title h2{margin:0;font-size:19px;overflow-wrap:anywhere}.cx-meta{margin:3px 0 0;font-size:12px;color:var(--muted)}.cx-title-actions{display:flex;align-items:center;gap:8px}
.cx-pill{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:4px 10px 4px 9px;font-size:12px;font-weight:600;white-space:nowrap}.cx-pill.active{background:var(--cx-ok-bg);color:var(--cx-ok)}.cx-pill.paused{background:var(--cx-warn-bg);color:var(--cx-warn)}
.cx-dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex:none;background:currentColor}
#view-customers .cx-btn{display:inline-flex;align-items:center;gap:6px;padding:6px 11px;font-size:12px;font-weight:600;background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:8px;box-shadow:none}#view-customers .cx-btn:hover{background:#f6f7fb}
#view-customers .cx-btn.primary{background:linear-gradient(110deg,var(--purple),var(--purple2));color:#fff;border-color:transparent}#view-customers .cx-btn.danger{background:#c43d52;color:#fff;border-color:transparent}#view-customers .cx-btn.quiet{border-color:transparent;background:transparent;color:var(--muted);padding:3px 7px;font-size:12px;font-weight:600}#view-customers .cx-btn.quiet:hover{background:#f4f5fa;color:var(--ink)}#view-customers .cx-btn.link{border:0;background:none;padding:0;color:var(--purple);text-decoration:underline}
#view-customers .cx-icon{width:32px;height:30px;padding:0;display:grid;place-items:center;background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:8px;box-shadow:none;font-size:16px;line-height:1}
.cx-pop{position:relative}.cx-menu{position:absolute;z-index:30;right:0;top:calc(100% + 4px);min-width:220px;padding:4px;background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:0 12px 30px #14244b1f}
#view-customers .cx-menu button{display:flex;align-items:center;gap:9px;width:100%;text-align:left;background:transparent;color:var(--ink);border:0;box-shadow:none;padding:7px 9px;border-radius:7px;font-size:13px;font-weight:500}#view-customers .cx-menu button:hover,#view-customers .cx-menu button:focus-visible{background:#f4f5fa;outline:none}#view-customers .cx-menu button.danger{color:#b4364a}.cx-sep{height:1px;background:var(--line);margin:4px 6px}
.cx-kv{display:grid;grid-template-columns:130px minmax(0,1fr);gap:5px 12px;font-size:13px}.cx-kv>span:nth-child(odd){color:var(--muted)}.cx-kv a{color:var(--purple)}.cx-group{font-size:11px;color:var(--muted);margin:12px 0 5px;font-weight:700}.cx-none{color:#a0a9bb}
.cx-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 12px}.cx-form .full{grid-column:1/-1}.cx-form h4{grid-column:1/-1;margin:6px 0 0;font-size:11px;color:var(--muted);font-weight:700}
#view-customers .cx-form label{display:block;font-size:11px;color:var(--muted);font-weight:600;margin:0 0 3px}#view-customers .cx-form input:not([type=checkbox]),#view-customers .cx-form select,#view-customers .cx-form textarea{width:100%;padding:7px 10px;font-size:13px}
.cx-form-actions{grid-column:1/-1;display:flex;justify-content:flex-end;gap:8px;margin-top:4px}.cx-checks{display:flex;gap:16px;flex-wrap:wrap}#view-customers .cx-checks label{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--ink);font-weight:500;margin:0}
.cx-error{grid-column:1/-1;margin:0;font-size:12px;color:var(--red)}.cx-error:empty{display:none}
.cx-inset{padding:12px;border-radius:10px;background:#f7f8fb;border:1px solid var(--line);margin-top:10px}
.cx-product{border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:10px}.cx-product-head{display:flex;justify-content:space-between;align-items:center;gap:8px}.cx-product-name{font-weight:700;font-size:14px}
.cx-bar{height:7px;border-radius:999px;background:#e6e9f1;overflow:hidden;flex:1}.cx-bar>i{display:block;height:100%;border-radius:999px;background:var(--purple)}.cx-bar.full>i{background:#e0a526}.cx-usage{display:flex;align-items:center;gap:10px;margin:10px 0 4px;font-size:12px}
.cx-line{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:7px 0;border-top:1px solid #eef0f5;font-size:13px;position:relative}.cx-line-sub{color:var(--muted);font-size:12px}.cx-soon{color:var(--cx-warn)}.cx-expired{color:var(--red)}
.cx-key{display:flex;gap:8px;align-items:center;margin-top:8px}.cx-key code{flex:1;font:600 13px ui-monospace,monospace;background:#fff;border:1px solid var(--line);border-radius:7px;padding:6px 9px;overflow-wrap:anywhere}
.cx-ok{padding:10px 12px;border-radius:10px;background:var(--cx-ok-bg);color:#0f6b50;font-size:12.5px;margin-top:10px}.cx-warn{padding:10px 12px;border-radius:10px;background:var(--cx-warn-bg);color:#6e4a07;font-size:12.5px;border:1px solid #f1d9a6}.cx-danger{padding:12px;border-radius:10px;background:var(--cx-danger-bg);color:#8e2738;font-size:12.5px;border:1px solid #f3c4cc}
.cx-box-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:10px}
.cx-avatar{width:30px;height:30px;border-radius:50%;background:#e3eaf9;color:#2452ac;display:grid;place-items:center;font-size:11px;font-weight:800;flex:none}.cx-avatar.off{background:#eef0f5;color:#a0a9bb}
.cx-user{display:flex;align-items:center;gap:10px;min-width:0}.cx-user span{min-width:0}.cx-user strong,.cx-user small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cx-user small{color:var(--muted);font-size:12px}
.cx-state{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:#54617a;white-space:nowrap}.cx-state.ok{color:var(--cx-ok)}.cx-state.wait{color:var(--cx-warn)}.cx-state.off{color:#a0a9bb}
.cx-empty{color:var(--muted);font-size:13px}.cx-placeholder{margin:auto;padding:40px 20px;color:var(--muted);text-align:center}
#view-customers .cx-notes{width:100%;min-height:76px;resize:vertical;padding:9px 11px;border:1px solid var(--line);border-radius:9px;font:inherit;line-height:1.5}
.cx-toast{font-size:12px;color:var(--cx-ok);min-height:18px}.cx-toast.bad{color:var(--red)}
.cx-kv>span{min-width:0;overflow-wrap:anywhere}
@media(max-width:720px){#view-customers .cx-head{flex-wrap:wrap}#view-customers .cx-head h1{font-size:22px}.cx-toast{order:9;flex-basis:100%}.cx-title{flex-wrap:wrap}.cx-line{flex-wrap:wrap}.cx-sec{padding:12px 14px}}
@media(max-width:900px){.cx-work{grid-template-columns:minmax(0,1fr);height:auto;min-height:0}.cx-list-pane{border-right:0;border-bottom:1px solid var(--line)}.cx-list{max-height:300px}.cx-form{grid-template-columns:minmax(0,1fr)}.cx-kv{grid-template-columns:110px minmax(0,1fr)}}
#authScreen.au-screen{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:32px 16px;background:radial-gradient(1100px 560px at 8% -12%,#e4ebfa 0,transparent 60%),radial-gradient(900px 480px at 108% 112%,#e2f5f9 0,transparent 55%),var(--canvas)}
.au-card{width:100%;max-width:400px;background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:0 24px 60px #14244b14;padding:30px 28px}
.au-brand{display:flex;align-items:center;gap:11px;margin-bottom:24px}.au-mark{width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,var(--purple),var(--purple2));color:#fff;display:grid;place-items:center;font-weight:800;font-size:18px}.au-brand strong{display:block;font-size:15px}.au-brand small{display:block;font-size:12px;color:var(--muted)}
.au-card h1{margin:0 0 6px;font-size:22px;line-height:1.25}.au-sub{margin:0 0 18px;color:var(--muted);font-size:14px;line-height:1.5}
.au-label{display:block;font-size:12px;font-weight:700;color:#4d5872;margin:14px 0 6px}
#authScreen input:not([type=checkbox]){width:100%;padding:11px 13px;border:1px solid #d6dce8;border-radius:10px;font:inherit;font-size:14px;background:#fff;color:var(--ink)}#authScreen input:focus{outline:none;border-color:var(--purple);box-shadow:0 0 0 3px #2d64d426}
.au-pw{position:relative}#authScreen .au-pw input{padding-right:46px}#authScreen .au-eye{position:absolute;right:5px;top:50%;transform:translateY(-50%);width:34px;height:34px;padding:0;border:0;background:transparent;color:#7b869c;display:grid;place-items:center;border-radius:8px;box-shadow:none}#authScreen .au-eye:hover{color:var(--ink);background:#f3f5f9}
.au-row-end{display:flex;justify-content:flex-end;margin-top:7px}#authScreen .au-small{border:0;background:none;padding:0;font-size:12px;color:var(--muted);font-weight:500;box-shadow:none;cursor:pointer}#authScreen .au-small:hover{color:var(--purple);text-decoration:underline}
#authScreen .au-primary{width:100%;margin-top:20px;padding:12px 16px;border:0;border-radius:10px;background:linear-gradient(110deg,var(--purple),var(--purple2));color:#fff;font-weight:700;font-size:14px;box-shadow:0 8px 20px #2d64d433}#authScreen .au-primary:disabled{opacity:.6;cursor:wait}
#authScreen .au-secondary{padding:9px 14px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--ink);font-weight:600;font-size:13px;box-shadow:none}
.au-error{margin:12px 0 0;font-size:13px;color:var(--red)}.au-error:empty{display:none}.au-info{margin:0 0 16px;padding:10px 12px;border-radius:10px;background:#e5f5ee;color:#0f6b50;font-size:13px;line-height:1.45}.au-warn{margin:0 0 16px;padding:10px 12px;border-radius:10px;background:#fdf3e1;color:#6e4a07;font-size:13px;line-height:1.45}
.au-otp{display:flex;gap:8px;justify-content:center;margin:6px 0 2px}#authScreen .au-otp input{width:46px;height:54px;padding:0;text-align:center;font-size:22px;font-weight:700;border-radius:12px}.au-otp .au-gap{width:6px}.au-otp.shake{animation:aushake .3s}@keyframes aushake{25%{transform:translateX(-6px)}75%{transform:translateX(6px)}}
.au-links{display:flex;justify-content:space-between;gap:12px;margin-top:18px}
.au-qr{display:grid;place-items:center;margin:4px 0 12px}.au-qr svg{width:176px;height:176px;border:1px solid var(--line);border-radius:12px;background:#fff}
.au-secret{display:flex;gap:8px;align-items:center}.au-secret code,.au-codes code{font:600 13px ui-monospace,monospace;background:#f6f7fb;border:1px solid var(--line);border-radius:8px;padding:8px 10px;overflow-wrap:anywhere;letter-spacing:.03em}.au-secret code{flex:1}
.au-codes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin:4px 0 12px}.au-codes code{text-align:center;padding:7px 6px}.au-code-actions{display:flex;gap:8px}
.au-check{display:flex;gap:9px;align-items:flex-start;font-size:13px;margin-top:14px;color:var(--ink);cursor:pointer}.au-check input{width:16px;height:16px;margin-top:2px;accent-color:var(--purple)}
.au-note{font-size:12px;color:var(--muted);line-height:1.5;margin:14px 0 0}.au-steps{display:flex;gap:6px;margin:0 0 16px}.au-steps span{flex:1;height:4px;border-radius:999px;background:#e6e9f1}.au-steps span.on{background:var(--purple)}
.au-help{margin-top:16px;padding:12px;border-radius:10px;background:#f7f8fb;border:1px solid var(--line);font-size:12.5px;color:#4d5872;line-height:1.5}.au-help p{margin:0 0 6px}.au-help p:last-child{margin:0}
.au-foot{margin:18px 0 0;font-size:12px;color:var(--muted);text-align:center}
#view-team .cx-btn,#view-profile .cx-btn{display:inline-flex;align-items:center;gap:6px;padding:6px 11px;font-size:12px;font-weight:600;background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:8px;box-shadow:none}#view-team .cx-btn:hover,#view-profile .cx-btn:hover{background:#f6f7fb}
#view-team .cx-btn.primary,#view-profile .cx-btn.primary{background:linear-gradient(110deg,var(--purple),var(--purple2));color:#fff;border-color:transparent}#view-team .cx-btn.primary:disabled{opacity:.5;cursor:default}#view-team .cx-btn.danger,#view-profile .cx-btn.danger{background:#c43d52;color:#fff;border-color:transparent}#view-team .cx-btn.quiet{border-color:transparent;background:transparent;color:var(--muted);padding:3px 7px;white-space:nowrap}#view-team .cx-btn.quiet:hover{background:#f4f5fa;color:var(--ink)}#view-team .cx-btn.link{border:0;background:none;padding:0;color:var(--purple);text-decoration:underline}
#view-team .cx-icon{width:32px;height:30px;padding:0;display:grid;place-items:center;background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:8px;box-shadow:none;font-size:16px;line-height:1}
#view-team .cx-menu button{display:flex;align-items:center;gap:9px;width:100%;text-align:left;background:transparent;color:var(--ink);border:0;box-shadow:none;padding:7px 9px;border-radius:7px;font-size:13px;font-weight:500}#view-team .cx-menu button:hover,#view-team .cx-menu button:focus-visible{background:#f4f5fa;outline:none}#view-team .cx-menu button.danger{color:#b4364a}
#view-team .cx-head,#view-profile .cx-head{display:flex;align-items:center;gap:12px;margin:0 0 14px}#view-team .cx-head h1{margin:0;font-size:24px;line-height:1.2}
#view-team .cx-form label{display:block;font-size:11px;color:var(--muted);font-weight:600;margin:0 0 3px}#view-team .cx-form input:not([type=checkbox]){width:100%;padding:7px 10px;font-size:13px}#view-team .cx-checks label{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--ink);font-weight:500;margin:0}
.tm-card{background:var(--card);border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow);padding:16px 18px;margin-bottom:16px}.tm-card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:10px}.tm-card-head h2{margin:0 0 3px;font-size:16px}
.tm-row{border-top:1px solid #eef0f5}.tm-row:first-child{border-top:0}.tm-row .cx-line{border-top:0;padding:10px 0}.tm-row.revoked{opacity:.75}.tm-side{display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end}.tm-row>.cx-form,.tm-row>.cx-warn,.tm-row>.cx-danger,.tm-row>.cx-ok{margin:0 0 12px}
.tm-matrix-wrap{overflow:auto}.tm-matrix{width:100%;border-collapse:collapse;font-size:13px;min-width:480px}.tm-matrix th,.tm-matrix td{padding:8px 10px;border-bottom:1px solid #eef0f5;text-align:center}.tm-matrix th:first-child,.tm-matrix td:first-child{text-align:left}.tm-matrix tr.tm-group td{background:#f7f8fb;color:var(--muted);font-size:11px;font-weight:800;letter-spacing:.05em;text-transform:uppercase}
#view-team .tm-fname{width:100%;min-width:90px;padding:5px 7px;border:1px solid transparent;border-radius:7px;text-align:center;font-weight:700;background:transparent}#view-team .tm-fname:hover,#view-team .tm-fname:focus{border-color:var(--line);background:#fff}.tm-matrix input[type=checkbox]{width:17px;height:17px;accent-color:var(--purple)}
.pf-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:16px;align-items:start}
@media(max-width:720px){.au-card{padding:24px 18px}#authScreen .au-otp input{width:40px;height:50px}.tm-side{justify-content:flex-start}.tm-row .cx-line{flex-wrap:wrap}}
.tm-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 14px}#view-team .tm-tab{display:inline-flex;align-items:center;gap:7px;padding:7px 13px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--ink);font-size:13px;font-weight:600;box-shadow:none}#view-team .tm-tab:hover{background:#f6f7fb}#view-team .tm-tab.on{background:#e8eefa;border-color:#c0d1f2;color:#244a95}
.tm-tab-count{font-size:11px;font-weight:700;color:var(--muted);background:#f0f2f7;border-radius:999px;padding:0 6px}.tm-tab.on .tm-tab-count{background:#fff;color:#244a95}.tm-dirty{width:7px;height:7px;border-radius:50%;background:#e0a526}
.tm-fn-head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:14px}.tm-fn-name{display:flex;flex-direction:column;gap:4px;font-size:11px;font-weight:600;color:var(--muted)}#view-team .tm-fn-name input{width:240px;max-width:100%;padding:7px 10px;font-size:14px;font-weight:600}
.tm-groups{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,260px),1fr));gap:12px}.tm-group-card{border:1px solid var(--line);border-radius:12px;padding:6px 14px 4px}.tm-group-title{font-size:11px;font-weight:800;letter-spacing:.06em;color:var(--muted);text-transform:uppercase;padding:8px 0 4px}
.tm-perm{display:flex;align-items:center;gap:12px;padding:9px 0;border-top:1px solid #eef0f5;cursor:pointer;position:relative}.tm-group-title+.tm-perm{border-top:0}.tm-perm>span:first-child{flex:1;min-width:0}.tm-perm strong{display:block;font-size:13px;font-weight:600}#view-team .tm-perm small{display:block;font-size:12px;font-weight:400;color:var(--muted);line-height:1.35;margin-top:1px}#view-team .tm-perm{font-weight:400}#view-team .tm-fn-name{font-weight:600}@media(max-width:720px){.tm-savebar{bottom:84px}}
.tm-perm input{position:absolute;opacity:0;width:1px;height:1px}.tm-switch{position:relative;width:34px;height:20px;border-radius:999px;background:#d5dae5;flex:none;transition:background .15s}.tm-switch::after{content:"";position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:#fff;box-shadow:0 1px 2px #0003;transition:left .15s}.tm-perm input:checked+.tm-switch{background:var(--purple)}.tm-perm input:checked+.tm-switch::after{left:17px}.tm-perm input:focus-visible+.tm-switch{outline:2px solid var(--purple);outline-offset:2px}
.tm-savebar{position:sticky;bottom:12px;display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-top:14px;padding:10px 12px;border-radius:12px;background:#1a1f36;color:#fff;font-size:13px;box-shadow:0 10px 30px #14244b33}.tm-savebar span{flex:1}#view-team .tm-savebar .cx-btn:not(.primary){background:transparent;color:#fff;border-color:#ffffff44}
#view-customers .cx-icon.cx-dots{border-color:transparent;background:transparent;width:28px;height:26px;font-size:17px;color:#6b7690}#view-customers .cx-icon.cx-dots:hover,#view-customers .cx-icon.cx-dots[aria-expanded=true]{background:#f1f3f8;color:var(--ink)}
.cx-menu-title{font-size:11px;color:var(--muted);padding:6px 9px 2px;font-weight:600}
.cx-lic-tools{display:flex;align-items:center;gap:8px;margin:10px 0 2px}#view-customers .cx-filter{text-decoration:none;color:#54617a;font-weight:600}
.cx-bulk{display:flex;align-items:center;gap:8px;margin:8px 0 4px;padding:6px 6px 6px 12px;border-radius:9px;background:#e8eefa;color:#244a95;font-size:12px}
.cx-lic-group{margin-top:6px}.cx-lic-group-head{display:flex;align-items:center;gap:8px;padding:6px 0 4px}#view-customers .cx-group-toggle{text-decoration:none;color:var(--ink);font-weight:700;font-size:13px}
.cx-lic{display:grid;grid-template-columns:18px minmax(0,1fr) auto 28px;gap:10px;align-items:center;padding:7px 0 7px 2px;border-top:1px solid #eef0f5;font-size:13px}.cx-lic input[type=checkbox]{width:15px;height:15px;margin:0;accent-color:var(--purple)}.cx-lic.revoked .cx-lic-name{color:#a0a9bb}
.cx-lic-main{min-width:0;display:flex;flex-direction:column;gap:1px}.cx-lic-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cx-lic-date{white-space:nowrap}
.cx-lic+.cx-form,.cx-lic+.cx-warn,.cx-lic+.cx-danger{margin:2px 0 10px 28px}
.ov-exp-list{display:grid;gap:0;margin-top:6px}#view-overview .ov-exp{display:flex;justify-content:space-between;align-items:center;gap:12px;width:100%;text-align:left;padding:9px 4px;border:0;border-top:1px solid #eef0f5;border-radius:0;background:transparent;color:var(--ink);box-shadow:none;font-weight:400}#view-overview .ov-exp:hover{background:#fafaff}.ov-exp strong{display:block;font-size:13px}.ov-exp small{display:block;font-size:12px;color:var(--muted)}.ov-exp-date{text-align:right;white-space:nowrap;font-size:13px;color:#a86706;font-weight:600}
@media(max-width:720px){.cx-lic{grid-template-columns:18px minmax(0,1fr) 28px}.cx-lic-date{grid-column:2;grid-row:2}.cx-lic+.cx-form,.cx-lic+.cx-warn,.cx-lic+.cx-danger{margin-left:0}}
</style><style>
.au-strength{margin:8px 0 4px}.au-strength-track{height:6px;border-radius:999px;background:#e8eaf0;overflow:hidden}.au-strength-fill{height:100%;width:0;background:#c83f58;transition:width .18s ease,background .18s ease}.au-strength-label{display:block;margin-top:5px;color:var(--muted);font-size:12px}.au-strength[data-level="1"] .au-strength-fill{width:25%;background:#cf4854}.au-strength[data-level="2"] .au-strength-fill{width:50%;background:#e3a52f}.au-strength[data-level="3"] .au-strength-fill{width:75%;background:#328bce}.au-strength[data-level="4"] .au-strength-fill{width:100%;background:#22956b}
.session-timeout{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:20px;background:#11182788}.session-timeout.hidden{display:none!important}.session-timeout-card{width:min(460px,100%);padding:26px;border:1px solid var(--line);border-radius:16px;background:#fff;box-shadow:0 20px 70px #12233755}.session-timeout-card h2{margin:0 0 8px}.session-timeout-card p{margin:0;color:var(--muted)}.session-timeout-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:20px}.session-timeout-count{font-weight:750;color:var(--ink)}
</style><style>
/* Cohentra staff portal: polished fixed sidebar navigation */
.app-shell{display:grid!important;grid-template-columns:260px minmax(0,1fr)!important;min-height:100vh}
.sidebar{display:flex!important;position:sticky!important;top:0!important;align-self:start!important;width:260px;height:100vh;height:100dvh;min-height:0;overflow:hidden!important;background:#11152a!important;color:#e9edff;padding:25px 17px 17px!important;gap:18px!important}
.brand{padding:0 7px 24px!important;gap:12px!important}.brand-mark{width:43px;height:43px;flex:0 0 43px;border-radius:14px;background:linear-gradient(135deg,#3469d5,#5b8ff0)!important;box-shadow:0 7px 22px #285bc344;font-size:24px!important}.brand strong{font-size:20px!important;letter-spacing:-.8px!important}.brand small{color:#8793b3!important}.group-label{padding:0 12px!important;margin:0 0 9px!important;color:#7885a7!important;font-size:10px;letter-spacing:1.65px;font-weight:800}
.nav-list{display:grid;gap:5px;flex:0 0 auto;min-height:0;max-height:none;overflow:visible;overscroll-behavior:contain}.nav-item{height:44px;padding:0 12px!important;border-radius:10px!important;color:#b5bfd8!important;font-size:13px}.nav-item:hover{background:#ffffff0b!important;color:#fff!important}.nav-item.active{background:#28264b!important;box-shadow:inset 0 0 0 1px #3168d5!important;color:#fff!important}.nav-icon{color:#789ce3!important}.sidebar-spacer{flex:1 1 auto;min-height:18px}.sidebar-user{width:100%;min-width:0;display:flex;align-items:center;gap:10px;padding:13px 9px!important;border:0!important;border-top:1px solid #ffffff17!important;border-radius:10px!important;background:transparent!important;color:#f2f4ff!important;text-align:left;cursor:pointer}.sidebar-user:hover{background:#ffffff0b!important}.sidebar-user:focus-visible{outline:2px solid #7498e2;outline-offset:2px}.sidebar-user .user-avatar{width:38px;height:38px;flex:0 0 38px}.sidebar-identity{min-width:0;flex:1}.sidebar-user strong{display:block;font-size:12px;max-width:155px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sidebar-user small{display:block;color:#909bb8;font-size:11px}.sidebar-profile-arrow{color:#8793b3;font-size:20px;line-height:1}.sidebar{z-index:80!important}.sidebar-account{position:relative;z-index:81;width:100%;min-width:0;border-top:1px solid #ffffff17;padding-top:9px}.sidebar-account-menu{position:relative;display:block;width:100%;z-index:82}.sidebar-account-menu>summary{list-style:none}.sidebar-account-menu>summary::-webkit-details-marker{display:none}.sidebar-account-menu>.sidebar-user{width:100%;border-top:0!important;padding:7px 5px!important}.sidebar-account-menu>.sidebar-user:hover,.sidebar-account-menu[open]>.sidebar-user{background:#ffffff0b!important}.sidebar-account-panel{position:absolute;left:0;bottom:calc(100% + 9px);z-index:9999;width:100%;min-width:205px;padding:6px;border:1px solid #ffffff1c;border-radius:11px;background:#171d36;box-shadow:0 12px 32px #070b1a99}.sidebar-account-panel button{display:flex;align-items:center;gap:10px;width:100%;padding:10px 11px;border:0;border-radius:7px;background:transparent;color:#e9edff;text-align:left;font:inherit;font-size:13px;cursor:pointer}.sidebar-account-panel button:hover,.sidebar-account-panel button:focus-visible{background:#ffffff10;outline:none}.sidebar-account-panel button:last-child{color:#ffb8c0}.sidebar-account-panel button:last-child:hover{background:#a832451f}
.main-area{width:100%;max-width:none;min-width:0;margin:0;padding:0!important}.desktop-topbar{display:none!important}
.mobile-topbar{display:none!important}.mobile-nav{display:none!important}.nav-list::-webkit-scrollbar{display:none}
@media(max-width:820px){.app-shell{display:block!important}.sidebar{position:fixed!important;inset:0 auto 0 0!important;z-index:41;width:min(280px,85vw)!important;height:100dvh!important;transform:translateX(-105%);transition:transform .22s ease;box-shadow:12px 0 36px #07192b2b}.sidebar.sidebar-open{transform:translateX(0)}.sidebar .nav-list{flex:1 1 auto;overflow-y:auto;scrollbar-width:none}.sidebar .nav-list::-webkit-scrollbar{display:none}.mobile-menu-backdrop.open{display:block!important}.desktop-topbar{display:none!important}.mobile-topbar{display:grid!important;grid-template-columns:auto 1fr auto;align-items:center;gap:12px;margin:0!important;padding:12px 16px!important;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}.mobile-topbar strong{font-size:15px}.mobile-topbar span{color:var(--muted);font-size:13px}.mobile-topbar button{padding:8px 11px}.main-area{padding:0!important}.admin-view{padding:22px 16px 40px!important}.mobile-nav{display:none!important}}
@media(prefers-reduced-motion:reduce){.sidebar{transition:none}}
</style>
<style>/* Huisstijl 2026: logo zonder kader */.brand-mark{background:none!important;box-shadow:none!important;border-radius:0!important;object-fit:contain;display:block}.brand strong{letter-spacing:-.4px!important}.au-brand{flex-direction:column;align-items:flex-start;gap:4px}.au-logo{height:50px;width:auto;margin-left:-4px;display:block}.au-sub{color:#66727e;font-size:12px;letter-spacing:.04em}</style></head><body><main class="wrap app-wrap">
<div id="authScreen" class="au-screen"><div class="au-card" id="authCard" aria-live="polite"></div><p class="au-foot">Cohentra Digital · beveiligd met tweestapsverificatie</p></div>
<div id="sessionTimeout" class="session-timeout hidden" role="alertdialog" aria-modal="true" aria-labelledby="sessionTimeoutTitle" aria-describedby="sessionTimeoutText"><section class="session-timeout-card"><h2 id="sessionTimeoutTitle">Je sessie loopt bijna af</h2><p id="sessionTimeoutText">Je wordt over 2 minuten afgemeld wegens inactiviteit.</p><div class="session-timeout-actions"><button type="button" class="secondary" id="sessionTimeoutLogout">Uitloggen</button><button type="button" id="sessionTimeoutContinue">Doorgaan</button></div></section></div>
<div id="dashboard" class="hidden">
<dialog class="avatar-crop-dialog" id="avatarCropDialog" aria-labelledby="avatarCropTitle"><h2 id="avatarCropTitle">Profielfoto bijsnijden</h2><p>Sleep de foto om de uitsnede te verplaatsen en gebruik de zoom om het kader aan te passen.</p><div class="avatar-crop-stage" id="avatarCropStage"><canvas id="avatarCropCanvas" width="320" height="320" aria-label="Voorbeeld van de ronde uitsnede"></canvas></div><div class="avatar-crop-zoom"><label for="avatarCropZoom"><span>Zoomen</span><span id="avatarCropZoomValue">100%</span></label><input id="avatarCropZoom" type="range" min="1" max="3" step="0.01" value="1"></div><div class="avatar-crop-actions"><button type="button" class="secondary" id="cancelAvatarCrop">Annuleren</button><button type="button" id="saveAvatarCrop">Foto gebruiken</button></div></dialog>
<div class="app-shell">
<aside class="sidebar" id="sidebar" aria-label="Hoofdnavigatie">
<div class="brand"><img class="brand-mark" src="/brand/cohentra-beeldmerk.png" alt="" aria-hidden="true"><span><strong>Cohentra</strong><small>Medewerkersportaal</small></span></div>
<div class="group-label">MENU</div><nav class="nav-list" aria-label="Hoofdmenu">
<button type="button" class="nav-item active" data-view="overview" aria-current="page"><span class="nav-icon" aria-hidden="true">▦</span>Overzicht</button>
<button type="button" class="nav-item" data-view="customers" id="customersNav"><span class="nav-icon" aria-hidden="true">♙</span>Klanten</button>

<button type="button" class="nav-item hidden" id="supportNav" data-view="support"><span class="nav-icon" aria-hidden="true">✆</span>Support<span class="sx-nav-badge hidden" id="supportNavBadge" aria-label="tickets wachten op reactie"></span></button>
<button type="button" class="nav-item hidden" id="emailTemplatesNav" data-view="emailTemplates"><span class="nav-icon" aria-hidden="true">✉</span>E-mailtemplates</button>
<button type="button" class="nav-item hidden" id="staffNav" data-view="team"><span class="nav-icon" aria-hidden="true">♧</span>Medewerkers & rechten</button>
</nav>
<div class="sidebar-spacer"></div><div class="sidebar-account"><details class="sidebar-account-menu" id="sidebarAccountMenu"><summary class="sidebar-user" id="sidebarProfile" aria-label="Accountmenu openen" aria-controls="sidebarAccountPanel"><span class="user-avatar" id="userAvatar"><span id="userAvatarInitials">C</span><img id="userAvatarImage" alt="" hidden></span><span class="sidebar-identity"><strong id="sidebarUser">Medewerker</strong><small id="sidebarRole">Medewerker</small></span></summary><div class="sidebar-account-panel" id="sidebarAccountPanel"><button type="button" id="sidebarProfileAction">◉ <span>Profiel</span></button><button type="button" id="logout">↪ <span>Afmelden</span></button></div></details></div>
</aside>
<button type="button" class="mobile-menu-backdrop" id="menuBackdrop" aria-label="Menu sluiten"></button>
<div class="main-area">
<header class="desktop-topbar"><div><strong id="topbarTitle">Overzicht</strong><span>Cohentra medewerkersportaal</span></div><div class="topbar-right"><button type="button" class="topbar-gear" id="settingsButton" aria-label="Instellingen">⚙</button></div></header>
<div class="mobile-topbar"><button type="button" id="menuToggle" aria-expanded="false" aria-label="Menu openen">☰</button><strong>Cohentra</strong><span id="mobilePageTitle">Overzicht</span></div>
<section class="admin-view" id="view-overview"><div class="page-heading"><span class="eyebrow">STARTPUNT</span><h1 id="pageTitle">Overzicht</h1><p>Beheer klanten, licenties en support vanuit één plek.</p></div>
<div id="lowCodesNotice" class="cx-warn hidden" role="status" style="margin:0 0 16px"></div><div class="overview-grid"><div class="stat-card" id="statCustomersCard"><span class="stat-label">Klanten</span><strong class="stat-value" id="statCustomers">—</strong></div><div class="stat-card" id="statLicensesCard"><span class="stat-label">Actieve licenties</span><strong class="stat-value" id="statLicenses">—</strong></div><div class="stat-card" id="statGroupsCard"><span class="stat-label">Verlopen binnen 30 dagen</span><strong class="stat-value" id="statGroups">—</strong></div><div class="stat-card" id="statOpenTicketsCard"><span class="stat-label">Open supporttickets</span><strong class="stat-value" id="statOpenTickets">—</strong></div></div>
<section class="card overview-actions"><h2>Snel naar</h2><div class="quick-actions"><button type="button" class="secondary" data-go-view="customers">Klanten beheren</button><button type="button" class="secondary owner-shortcut hidden" data-go-view="support">Support</button></div></section><section class="card" id="expiringCard"><h2>Licenties die binnen 30 dagen verlopen</h2><p class="muted" style="margin:0">Klanten krijgen 14 dagen van tevoren automatisch een e-mail.</p><div id="expiringList" class="ov-exp-list"><p class="muted">Laden…</p></div></section></section>
<section class="admin-view hidden" id="view-customers">
<header class="cx-head"><h1>Klanten</h1><span class="cx-sub" id="customerSummary"></span><span class="cx-spacer"></span><span id="customerToast" class="cx-toast" role="status"></span></header>
<div class="cx-work"><section class="cx-list-pane" aria-label="Klantenlijst"><div class="cx-tools"><input id="customerSearch" type="search" placeholder="Zoek naam, plaats, e-mail of klantnummer" aria-label="Klanten zoeken"><div class="cx-tools-row"><div class="cx-pop"><button type="button" class="cx-btn" id="customerFilterButton" aria-haspopup="menu" aria-expanded="false"><span id="customerFilterLabel">Actief</span> <span class="cx-sub" id="customerFilterCount"></span> ▾</button><div class="cx-menu hidden" id="customerFilterMenu" role="menu" style="left:0;right:auto;min-width:180px"></div></div><button type="button" class="cx-btn quiet" id="addCustomer" title="Klant toevoegen" aria-label="Klant toevoegen">+ Nieuw</button></div></div><div id="customers" class="cx-list"><div class="cx-placeholder">Klanten laden…</div></div></section>
<section class="cx-detail" id="customerDetail" aria-live="polite"><div class="cx-placeholder">Selecteer een klant.</div></section></div>
</section>

<section class="admin-view hidden" id="view-support">
<header class="sx-head"><h1>Support</h1><span id="supportSyncStatus" class="sx-sync" role="status"></span><span class="sx-spacer"></span><button type="button" class="sx-icon" id="syncSupportInbox" aria-label="Mailbox nu ophalen" title="Mailbox nu ophalen"><span aria-hidden="true">↻</span></button></header>
<div id="supportMailIssues" class="cx-warn hidden" role="status"></div>
<div class="sx-work"><section class="sx-list-pane" aria-label="Tickets"><div class="sx-tools"><input id="supportSearch" type="search" placeholder="Zoek klant, onderwerp of CH-nummer" aria-label="Tickets zoeken"><div class="sx-tools-row"><div class="sx-pop"><button type="button" class="sx-pill" id="supportFilterButton" data-sx-menu-toggle aria-haspopup="menu" aria-expanded="false"><span id="supportFilterLabel">Open</span><span id="supportTicketCount" class="sx-count"></span><span class="sx-caret" aria-hidden="true">▾</span></button><div class="sx-menu hidden" id="supportFilterMenu" role="menu" aria-label="Tickets filteren"></div></div><span class="sx-hint">laatste activiteit eerst</span></div></div><div id="supportTicketError" class="error" role="alert"></div><div id="supportTickets" class="sx-tickets"><div class="sx-empty">Tickets laden…</div></div></section>
<section class="sx-detail" aria-label="Gesprek"><header class="sx-detail-head"><div class="sx-title-row"><div><h2 id="supportDetailTitle">Selecteer een ticket</h2><p id="supportDetailMeta" class="sx-meta">Kies links een ticket om het gesprek te openen.</p></div><div class="sx-pop"><button type="button" class="sx-pill sx-status hidden" id="supportStatusButton" data-sx-menu-toggle aria-haspopup="menu" aria-expanded="false"><span class="sx-dot"></span><span id="supportStatusLabel"></span><span class="sx-caret" aria-hidden="true">▾</span></button><div class="sx-menu sx-menu-right hidden" id="supportStatusMenu" role="menu" aria-label="Status wijzigen"></div></div></div><div id="supportDetailFacts" class="sx-facts"></div></header>
<div id="supportConversation" class="sx-conv" aria-live="polite"><div class="sx-empty">Selecteer links een ticket om het gesprek te bekijken.</div></div><div id="supportDetailError" class="error" role="alert"></div>
<form id="supportReplyForm" class="sx-composer hidden" novalidate><div class="sx-composer-top"><span id="supportReplyTo" class="sx-to"></span><label class="sx-switch"><input type="checkbox" id="supportNoteToggle"><span class="sx-track" aria-hidden="true"></span>Interne notitie</label></div><textarea id="supportReplyMessage" maxlength="6000" placeholder="Schrijf je antwoord…" aria-label="Bericht"></textarea><p id="supportReplyEmpty" class="sx-field-error hidden" role="alert">Schrijf eerst een bericht.</p>
<div class="sx-actions" id="supportReplyActions"><span id="supportAfterText" class="sx-after"></span><div class="sx-split"><button type="submit" id="supportReplyButton" title="Versturen (Ctrl+Enter)">Versturen</button><button type="button" id="supportAfterButton" data-sx-menu-toggle aria-label="Status na versturen kiezen" aria-haspopup="menu" aria-expanded="false">▾</button></div><div class="sx-menu sx-menu-up hidden" id="supportAfterMenu" role="menu" aria-label="Status na versturen"></div></div>
<div class="sx-confirm hidden" id="supportConfirm" role="alertdialog" aria-labelledby="supportConfirmText"><p id="supportConfirmText"></p><div><button type="button" class="secondary" id="supportConfirmCancel">Nog even niet</button><button type="button" id="supportConfirmSend">Ja, verstuur</button></div></div></form></section></div>
</section>
<section class="admin-view hidden" id="view-profile"><div class="page-heading"><span class="eyebrow">ACCOUNT</span><h1>Profiel en beveiliging</h1><p>Je gegevens en de beveiliging van je account.</p></div><div class="pf-grid"><section class="card" id="signaturePanel"><h2>Gegevens</h2><div class="pf-avatar-row"><div class="pf-avatar" id="profileAvatar"><img id="profileAvatarImage" alt="Profielfoto" hidden><span id="profileAvatarInitials">BV</span></div><div class="pf-avatar-controls"><strong>Profielfoto</strong><p class="muted">Optioneel. Wordt alleen in het medewerkersportaal en bij supportreacties getoond.</p><div class="pf-avatar-actions"><input id="profileAvatarFile" type="file" accept="image/jpeg,image/png,image/webp"><button type="button" id="chooseAvatar">Foto kiezen</button><button type="button" class="secondary" id="removeAvatar" hidden>Verwijderen</button></div><p class="avatar-message muted" id="avatarMessage" role="status"></p></div></div><div class="profile-fields"><label for="signatureName">Volledige naam</label><input id="signatureName" maxlength="80" autocomplete="name" placeholder="Bijvoorbeeld: Jamie de Wit"><label for="signatureFirstName">Voornaam</label><input id="signatureFirstName" maxlength="40" autocomplete="given-name" placeholder="Bijvoorbeeld: Jamie"><p class="muted">Je voornaam staat onder supportreacties en statusupdates aan klanten.</p><label for="profileEmail">E-mailadres</label><input id="profileEmail" type="email" maxlength="254" autocomplete="email" placeholder="naam@cohentra.digital"><p class="muted">Nodig om je wachtwoord zelf te kunnen herstellen.</p><button type="button" id="saveSignatureName">Opslaan</button><p id="signatureNameError" class="error" role="alert"></p><p id="profileSaved" class="muted" role="status"></p></div></section><section class="card" id="securityPanel"><h2>Beveiliging</h2><p class="mfa-required-label">MFA is verplicht voor alle medewerkers</p><p class="muted">Je meldt je aan met je wachtwoord en een code uit je authenticator-app. Herstelcodes gebruik je als je je telefoon niet bij je hebt.</p><div id="securityCodes"></div></section></div></section>
<section class="admin-view hidden" id="view-emailTemplates"><div class="page-heading"><span class="eyebrow">COMMUNICATIE</span><h1>E-mailtemplates</h1><p>Pas de teksten en accentkleur aan. Wijzigingen gelden voor nieuwe e-mails.</p></div><div class="email-template-layout"><section class="card"><div class="topline"><div><h2>Instellingen</h2><p class="muted">Gebruik <code>{{reference}}</code> in de statusmelding en <code>{{subject}}</code> in de interne melding.</p></div></div><label for="emailTemplateKind">Onderdeel</label><select id="emailTemplateKind"><option value="support">Supportmails</option><option value="auth">Uitnodigingen en wachtwoordherstel</option><option value="branding">Huisstijl</option></select><form id="emailTemplateForm"><div id="emailTemplateFields"></div><div class="actions"><button type="submit" id="saveEmailTemplate">Wijzigingen opslaan</button><button type="button" class="secondary" id="previewEmailTemplate">Voorbeeld vernieuwen</button></div><div id="emailTemplateMessage" class="notice hidden" role="status"></div><div id="emailTemplateError" class="error" role="alert"></div><p id="emailTemplateMeta" class="muted"></p></form></section><section class="card"><div class="topline"><div><h2>Voorbeeld</h2><p class="muted">Het voorbeeld gebruikt uitsluitend fictieve gegevens.</p></div><select id="emailTemplateVariant" aria-label="Type e-mailvoorbeeld"></select></div><iframe id="emailTemplatePreview" title="Voorbeeld van de e-mail" sandbox="" style="width:100%;height:620px;border:1px solid #dce4eb;border-radius:12px;background:#f1f3f7"></iframe></section></div></section><section class="admin-view hidden" id="view-team">
<header class="cx-head"><h1>Medewerkers &amp; rechten</h1><span class="cx-sub" id="teamSummary"></span><span class="cx-spacer"></span><span id="teamToast" class="cx-toast" role="status"></span></header>
<section class="tm-card"><div class="tm-card-head"><div><h2>Medewerkers</h2><p class="cx-sub">Medewerkers melden zich aan op staff.cohentra.digital. Bij de eerste keer koppelen ze zelf hun authenticator-app.</p></div><button type="button" class="cx-btn quiet" id="addStaff" aria-label="Medewerker toevoegen" title="Medewerker toevoegen">+ Nieuw</button></div><div id="teamCreate"></div><div id="staff"><div class="cx-placeholder">Laden…</div></div></section>
<section class="tm-card"><div class="tm-card-head"><div><h2>Functies en rechten</h2><p class="cx-sub">Een medewerker krijgt de rechten van al zijn functies samen.</p></div></div><div id="rightsMatrix"></div><p class="cx-error" id="rightsError" role="alert"></p><div class="tm-savebar hidden" id="rightsBar" role="status"><span id="rightsState"></span><button type="button" class="cx-btn" id="resetRights">Annuleren</button><button type="button" class="cx-btn primary" id="saveRights">Opslaan</button></div></section>
</section>

</div></section></div><nav class="mobile-nav" id="mobileNav" aria-label="Snelle navigatie"><button type="button" data-mobile-view="overview"><b>▦</b>Overzicht</button><button type="button" data-mobile-view="customers" id="mobileCustomers"><b>♙</b>Klanten</button><button type="button" data-mobile-view="support" id="mobileSupport"><b>✆</b>Support</button><button type="button" data-mobile-view="team" id="mobileTeam"><b>♧</b>Team</button></nav></div></div></main>
<script>
const $=id=>document.getElementById(id);
let token=sessionStorage.getItem('eventhub-admin-token')||'', pendingChallenge='', role='', portalPermissions=[], functionCatalog=[], customers=[], licenseSummary={licenses:0,groups:0}, supportTicketRows=[];
function can(permission){return role==='owner'||portalPermissions.includes('*')||portalPermissions.includes(permission)}
function today(){return new Date().toISOString().slice(0,10)}
function authHeaders(){return {'Authorization':'Bearer '+token,'Content-Type':'application/json'}}
const avatarObjectUrls=new Map();
function setAvatarImage(containerId,url){const box=$(containerId);if(!box)return;const img=box.querySelector('img'),fallback=box.querySelector('span');if(!img||!fallback)return;const showImage=()=>{img.hidden=false;fallback.hidden=true};const showFallback=()=>{img.hidden=true;img.removeAttribute('src');fallback.hidden=false};img.onload=()=>showImage();img.onerror=showFallback;if(url){fallback.hidden=false;img.hidden=true;img.src=url;if(img.complete&&img.naturalWidth>0)showImage();else if(typeof img.decode==='function')img.decode().then(showImage).catch(showFallback)}else{showFallback()}}
function clearAvatarObjectUrl(id){const url=avatarObjectUrls.get(String(id));if(url)URL.revokeObjectURL(url);avatarObjectUrls.delete(String(id))}
function clearAvatarObjectUrls(){for(const id of avatarObjectUrls.keys())clearAvatarObjectUrl(id)}
async function getAvatarObjectUrl(id){id=String(id);if(avatarObjectUrls.has(id))return avatarObjectUrls.get(id);const r=await fetch('/api/admin/avatar/'+encodeURIComponent(id),{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(r.status===404){avatarObjectUrls.set(id,null);return null;}if(!r.ok)throw Error('De profielfoto kon niet worden geladen ('+r.status+').');const responseBlob=await r.blob();if(!responseBlob.size||responseBlob.size>262144){avatarObjectUrls.set(id,null);throw Error('De opgeslagen profielfoto heeft een ongeldig formaat. Kies de foto opnieuw.')}const bytes=new Uint8Array(await responseBlob.arrayBuffer()),isJpeg=bytes[0]===0xff&&bytes[1]===0xd8&&bytes[2]===0xff,isPng=bytes[0]===0x89&&bytes[1]===0x50&&bytes[2]===0x4e&&bytes[3]===0x47&&bytes[4]===0x0d&&bytes[5]===0x0a&&bytes[6]===0x1a&&bytes[7]===0x0a,isWebp=bytes[0]===0x52&&bytes[1]===0x49&&bytes[2]===0x46&&bytes[3]===0x46&&bytes[8]===0x57&&bytes[9]===0x45&&bytes[10]===0x42&&bytes[11]===0x50,mime=isJpeg?'image/jpeg':isPng?'image/png':isWebp?'image/webp':'';if(!mime){avatarObjectUrls.set(id,null);throw Error('De opgeslagen profielfoto is beschadigd. Kies de foto opnieuw.')}const blob=new Blob([bytes],{type:mime}),url=URL.createObjectURL(blob);try{const image=new Image();image.src=url;await image.decode();if(!image.naturalWidth||!image.naturalHeight||image.naturalWidth>2048||image.naturalHeight>2048)throw Error('Ongeldige afbeelding')}catch{URL.revokeObjectURL(url);avatarObjectUrls.set(id,null);throw Error('De opgeslagen profielfoto is beschadigd. Kies de foto opnieuw.')}avatarObjectUrls.set(id,url);return url}
async function loadCurrentAvatar(me){const id=me.id||'owner';let url=null;try{url=me.has_avatar?await getAvatarObjectUrl(id):null;if(me.has_avatar&&!url)$('avatarMessage').textContent='Je profielfoto staat geregistreerd, maar kon niet worden opgehaald. Kies de foto opnieuw.';else if(!me.has_avatar)$('avatarMessage').textContent='Er is nog geen profielfoto ingesteld.'}catch(error){$('avatarMessage').textContent=error.message||'De profielfoto kon niet worden geladen.'}setAvatarImage('userAvatar',url);setAvatarImage('topbarUserAvatar',url);setAvatarImage('profileAvatar',url);$('removeAvatar').hidden=!url}
async function renderSupportAvatars(){const box=$('supportConversation');if(!box)return;const ids=[...new Set([...box.querySelectorAll('[data-avatar-id]')].map(el=>el.dataset.avatarId).filter(Boolean))];await Promise.all(ids.map(async id=>{try{const url=await getAvatarObjectUrl(id);if(!url)return;box.querySelectorAll('[data-avatar-id="'+CSS.escape(id)+'"]').forEach(el=>{const img=el.querySelector('img'),fallback=el.querySelector('span');if(img&&fallback){img.src=url;img.hidden=false;fallback.hidden=true}})}catch{}}))}
let avatarCropBitmap=null,avatarCropX=0,avatarCropY=0,avatarCropZoom=1,avatarCropPointer=null;
function drawAvatarCrop(){if(!avatarCropBitmap)return;const canvas=$('avatarCropCanvas'),ctx=canvas.getContext('2d'),side=Math.min(avatarCropBitmap.width,avatarCropBitmap.height),crop=side/avatarCropZoom;avatarCropX=Math.max(crop/2,Math.min(avatarCropBitmap.width-crop/2,avatarCropX));avatarCropY=Math.max(crop/2,Math.min(avatarCropBitmap.height-crop/2,avatarCropY));ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(avatarCropBitmap,avatarCropX-crop/2,avatarCropY-crop/2,crop,crop,0,0,canvas.width,canvas.height)}
function closeAvatarCrop(){if(avatarCropBitmap)avatarCropBitmap.close?.();avatarCropBitmap=null;avatarCropPointer=null;$('profileAvatarFile').value='';$('avatarCropDialog').close()}
async function openAvatarCrop(file){const message=$('avatarMessage');try{if(!file||!/^image\/(jpeg|png|webp)$/.test(file.type))throw Error('Kies een JPG-, PNG- of WebP-afbeelding.');if(file.size>10*1024*1024)throw Error('De afbeelding is groter dan 10 MB.');const bitmap=await createImageBitmap(file);if(!bitmap.width||!bitmap.height||bitmap.width>10000||bitmap.height>10000||bitmap.width*bitmap.height>30000000){bitmap.close?.();throw Error('Deze afbeelding kan niet veilig worden verwerkt.')}avatarCropBitmap=bitmap;avatarCropZoom=1;avatarCropX=bitmap.width/2;avatarCropY=bitmap.height/2;$('avatarCropZoom').value='1';$('avatarCropZoomValue').textContent='100%';drawAvatarCrop();$('avatarCropDialog').showModal();message.textContent=''}catch(error){message.textContent=error.message||'Deze afbeelding kan niet worden geopend.'}}
async function croppedAvatarBlob(){const source=$('avatarCropCanvas'),canvas=document.createElement('canvas');canvas.width=256;canvas.height=256;const ctx=canvas.getContext('2d',{alpha:false});ctx.drawImage(source,0,0,256,256);let blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.9));if(!blob)throw Error('De uitsnede kon niet worden verwerkt.');if(blob.size>262144)blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.72));if(!blob||blob.size>262144)throw Error('De bewerkte foto is te groot. Kies een kleinere uitsnede.');return blob}
async function uploadProfileAvatarBlob(blob){const message=$('avatarMessage');message.textContent='Foto opslaan…';try{const r=await fetch('/api/admin/me/avatar',{method:'PUT',headers:{Authorization:'Bearer '+token,'Content-Type':'image/jpeg'},body:blob});let d={};try{d=await r.json()}catch{}if(!r.ok)throw Error(d.error||'De foto kon niet worden opgeslagen.');const id=pfMe&&pfMe.id||'owner';clearAvatarObjectUrl(id);pfMe={...pfMe,has_avatar:true};await loadCurrentAvatar(pfMe);if(message.textContent.includes('beschadigd'))throw Error(message.textContent);message.textContent='Profielfoto opgeslagen.';if(currentSupportTicketId)renderSupportAvatars()}catch(err){message.textContent=err.message||'De foto kon niet worden opgeslagen.'}}
async function removeProfileAvatar(){const button=$('removeAvatar'),message=$('avatarMessage');button.disabled=true;message.textContent='Foto verwijderen…';try{const r=await fetch('/api/admin/me/avatar',{method:'DELETE',headers:{Authorization:'Bearer '+token}});let d={};try{d=await r.json()}catch{}if(!r.ok)throw Error(d.error||'De foto kon niet worden verwijderd.');const id=pfMe&&pfMe.id||'owner';clearAvatarObjectUrl(id);pfMe={...pfMe,has_avatar:false};await loadCurrentAvatar(pfMe);message.textContent='Profielfoto verwijderd.';if(currentSupportTicketId)renderSupportAvatars()}catch(err){message.textContent=err.message||'De foto kon niet worden verwijderd.'}finally{button.disabled=false}}
function prepareProfileAvatar(){const choose=$('chooseAvatar'),input=$('profileAvatarFile'),remove=$('removeAvatar');if(!choose||!input||!remove)return;choose.onclick=()=>input.click();input.onchange=()=>{if(input.files&&input.files[0])openAvatarCrop(input.files[0])};$('avatarCropZoom').oninput=()=>{avatarCropZoom=Number($('avatarCropZoom').value)||1;$('avatarCropZoomValue').textContent=Math.round(avatarCropZoom*100)+'%';drawAvatarCrop()};const stage=$('avatarCropStage');stage.onpointerdown=e=>{if(!avatarCropBitmap)return;stage.setPointerCapture(e.pointerId);avatarCropPointer={id:e.pointerId,x:e.clientX,y:e.clientY,cx:avatarCropX,cy:avatarCropY}};stage.onpointermove=e=>{if(!avatarCropPointer||avatarCropPointer.id!==e.pointerId)return;const crop=Math.min(avatarCropBitmap.width,avatarCropBitmap.height)/avatarCropZoom,rect=stage.getBoundingClientRect(),factor=crop/rect.width;avatarCropX=avatarCropPointer.cx-(e.clientX-avatarCropPointer.x)*factor;avatarCropY=avatarCropPointer.cy-(e.clientY-avatarCropPointer.y)*factor;drawAvatarCrop()};stage.onpointerup=stage.onpointercancel=()=>{avatarCropPointer=null};$('cancelAvatarCrop').onclick=closeAvatarCrop;$('avatarCropDialog').onclose=()=>{if(avatarCropBitmap){avatarCropBitmap.close?.();avatarCropBitmap=null}};$('saveAvatarCrop').onclick=async()=>{const button=$('saveAvatarCrop');button.disabled=true;try{const blob=await croppedAvatarBlob();closeAvatarCrop();await uploadProfileAvatarBlob(blob)}catch(error){$('avatarMessage').textContent=error.message||'De foto kon niet worden verwerkt.'}finally{button.disabled=false;input.value=''}};remove.onclick=removeProfileAvatar}
prepareProfileAvatar();
async function api(path,opts={}){const r=await fetch(path,{...opts,headers:{...authHeaders(),...(opts.headers||{})}});let d={};try{d=await r.json()}catch{}if(r.status===401){if(token){token='';sessionStorage.removeItem('eventhub-admin-token');stopSessionTimer();showLogin('Je sessie is verlopen. Meld opnieuw aan.')}throw Error(d.error||'Je sessie is verlopen. Meld opnieuw aan.')}if(!r.ok)throw Error(d.error||'De aanvraag is mislukt.');return d}
const STAFF_IDLE_MS=30*60*1000,STAFF_WARN_MS=2*60*1000;let staffLastActivity=0,staffTimer=0,staffPingAt=0,staffWarning=false;
function stopSessionTimer(){clearInterval(staffTimer);staffTimer=0;staffWarning=false;$('sessionTimeout')?.classList.add('hidden')}
function staffActivity(event){if(!token||!event.isTrusted||staffWarning||event.target?.closest?.('#sessionTimeout'))return;staffLastActivity=Date.now()}
function updateSessionTimer(){if(!token)return;const remaining=staffLastActivity+STAFF_IDLE_MS-Date.now();if(remaining<=0){const expiredToken=token;stopSessionTimer();token='';sessionStorage.removeItem('eventhub-admin-token');fetch('/api/auth/logout',{method:'POST',headers:{Authorization:'Bearer '+expiredToken}}).catch(()=>{});showLogin('Je bent afgemeld na 30 minuten inactiviteit. Meld opnieuw aan.');return}if(remaining<=STAFF_WARN_MS&&!staffWarning){staffWarning=true;$('sessionTimeout').classList.remove('hidden');$('sessionTimeoutText').innerHTML='Je wordt over <span class="session-timeout-count" id="sessionTimeoutCountdown">2 minuten</span> afgemeld wegens inactiviteit. Wil je doorgaan?'}if(staffWarning){const minutes=Math.max(1,Math.ceil(remaining/60000));$('sessionTimeoutCountdown').textContent=minutes+' '+(minutes===1?'minuut':'minuten')}if(Date.now()-staffPingAt>=60*1000&&Date.now()-staffLastActivity<2*60*1000){staffPingAt=Date.now();api('/api/admin/me').catch(()=>{})}}
function startSessionTimer(){stopSessionTimer();staffLastActivity=Date.now();staffPingAt=Date.now();staffTimer=setInterval(updateSessionTimer,1000)}
for(const eventName of ['pointerdown','keydown','input','scroll','touchstart'])document.addEventListener(eventName,staffActivity,{passive:true});
$('sessionTimeoutContinue').onclick=async()=>{const button=$('sessionTimeoutContinue');button.disabled=true;try{await api('/api/admin/me');staffLastActivity=Date.now();staffWarning=false;$('sessionTimeout').classList.add('hidden')}catch{showLogin('Je sessie is verlopen. Meld opnieuw aan.')}finally{button.disabled=false}};$('sessionTimeoutLogout').onclick=async()=>{const current=token;stopSessionTimer();token='';sessionStorage.removeItem('eventhub-admin-token');try{await fetch('/api/auth/logout',{method:'POST',headers:{Authorization:'Bearer '+current}})}catch{}showLogin()};
function safe(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function otpauthUri(account,secret){return 'otpauth://totp/'+encodeURIComponent('Cohentra:'+account)+'?secret='+encodeURIComponent(secret)+'&issuer=Cohentra'}
function qrSvg(text){
  const bytes=[...new TextEncoder().encode(text)],version=5,size=version*4+17,dataCount=108,eccCount=26;
  if(bytes.length>106)throw Error('De QR-inhoud is te lang. Gebruik de handmatige sleutel.');
  const bits=[],push=(value,length)=>{for(let i=length-1;i>=0;i--)bits.push((value>>>i)&1)};
  push(4,4);push(bytes.length,8);for(const b of bytes)push(b,8);for(let i=0;i<Math.min(4,dataCount*8-bits.length);i++)bits.push(0);while(bits.length%8)bits.push(0);
  const data=[];for(let i=0;i<bits.length;i+=8){let v=0;for(let j=0;j<8;j++)v=(v<<1)|bits[i+j];data.push(v)}for(let pad=0;data.length<dataCount;pad++)data.push(pad%2?0x11:0xec);
  const mul=(x,y)=>{let z=0;for(let i=7;i>=0;i--){z=(z<<1)^(((z>>>7)&1)*0x11d);z^=((y>>>i)&1)*x}return z};
  let gen=[1];for(let i=0;i<eccCount;i++){const next=Array(gen.length+1).fill(0),root=(()=>{let v=1;for(let j=0;j<i;j++)v=mul(v,2);return v})();for(let j=0;j<gen.length;j++){next[j]^=gen[j];next[j+1]^=mul(gen[j],root)}gen=next}
  const blocks=[];for(let start=0;start<data.length;start+=108){const part=data.slice(start,start+108),ecc=Array(eccCount).fill(0);for(const b of part){const factor=b^ecc.shift();ecc.push(0);for(let j=0;j<eccCount;j++)ecc[j]^=mul(gen[j+1],factor)}blocks.push({part,ecc})}
  const words=[];for(let i=0;i<108;i++)for(const block of blocks)words.push(block.part[i]);for(let i=0;i<eccCount;i++)for(const block of blocks)words.push(block.ecc[i]);
  const stream=[];for(const w of words)for(let i=7;i>=0;i--)stream.push((w>>>i)&1);
  const grid=Array.from({length:size},()=>Array(size).fill(false)),func=Array.from({length:size},()=>Array(size).fill(false));
  const set=(x,y,dark)=>{if(x>=0&&y>=0&&x<size&&y<size){grid[y][x]=!!dark;func[y][x]=true}};
  for(let i=0;i<size;i++){set(6,i,i%2===0);set(i,6,i%2===0)}
  const finder=(cx,cy)=>{for(let dy=-4;dy<=4;dy++)for(let dx=-4;dx<=4;dx++){const d=Math.max(Math.abs(dx),Math.abs(dy));set(cx+dx,cy+dy,d===3||d<=1)}};
  finder(3,3);finder(size-4,3);finder(3,size-4);
  // Version 5 has one alignment pattern: the other position pairs overlap finder patterns.
  for(const [cx,cy] of [[30,30]])for(let dy=-2;dy<=2;dy++)for(let dx=-2;dx<=2;dx++)set(cx+dx,cy+dy,Math.max(Math.abs(dx),Math.abs(dy))!==1);
  // Reserve both format-information areas before placing data modules.
  for(let i=0;i<=5;i++)set(8,i,false);set(8,7,false);set(8,8,false);set(7,8,false);for(let i=9;i<15;i++)set(14-i,8,false);
  for(let i=0;i<8;i++)set(size-1-i,8,false);for(let i=8;i<15;i++)set(8,size-15+i,false);
  const mask=0;let bit=0,up=true;
  for(let right=size-1;right>=1;right-=2){if(right===6)right=5;for(let k=0;k<size;k++){const y=up?size-1-k:k;for(let side=0;side<2;side++){const x=right-side;if(func[y][x])continue;let dark=bit<stream.length?stream[bit++]===1:false;if((x+y)%2===0)dark=!dark;grid[y][x]=dark}}up=!up}
  const formatData=(1<<3)|mask;let rem=formatData<<10;for(let i=14;i>=10;i--)if((rem>>>i)&1)rem^=0x537<<(i-10);const format=((formatData<<10)|rem)^0x5412;
  for(let i=0;i<=5;i++)set(8,i,(format>>>i)&1);set(8,7,(format>>>6)&1);set(8,8,(format>>>7)&1);set(7,8,(format>>>8)&1);for(let i=9;i<15;i++)set(14-i,8,(format>>>i)&1);
  for(let i=0;i<8;i++)set(size-1-i,8,(format>>>i)&1);for(let i=8;i<15;i++)set(8,size-15+i,(format>>>i)&1);set(8,size-8,true);
  let path='';for(let y=0;y<size;y++)for(let x=0;x<size;x++)if(grid[y][x])path+='M'+(x+4)+' '+(y+4)+'h1v1h-1z';
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+(size+8)+' '+(size+8)+'" width="360" height="360" shape-rendering="crispEdges" role="img" aria-label="Authenticator QR-code"><rect width="100%" height="100%" fill="#fff"/><path d="'+path+'" fill="#000"/></svg>';
}
function showQr(id,account,secret){$(id).innerHTML=qrSvg(otpauthUri(account,secret))}
function formatOtpInput(input){input.addEventListener('input',()=>{const value=input.value,digits=value.replace(/\D/g,'');if(/^[\d-]*$/.test(value)&&digits.length<=6&&digits.length>0)input.value=digits.length>3?digits.slice(0,3)+'-'+digits.slice(3):digits})}
function closeMobileMenu(){$('sidebar').classList.remove('sidebar-open');$('menuBackdrop').classList.remove('open');$('menuToggle').setAttribute('aria-expanded','false')}function setView(view){const names={overview:'Overzicht',customers:'Klanten',licenses:'Licenties',support:'Support inbox',emailTemplates:'E-mailtemplates',team:'Medewerkers & rechten',profile:'Profiel en beveiliging'},required={customers:'customers.view',licenses:'licenses.view',support:'support.view',emailTemplates:'email.templates.manage'},section=$('view-'+view);if(!section||required[view]&&!can(required[view])||view==='team'&&role!=='owner')return;document.querySelectorAll('.admin-view').forEach(item=>item.classList.toggle('hidden',item!==section));document.querySelectorAll('.nav-item[data-view],.menu-link[data-view]').forEach(button=>{const active=button.dataset.view===view;button.classList.toggle('active',active);if(active)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current')});$('pageTitle').textContent=names[view];$('mobilePageTitle').textContent=names[view];$('topbarTitle').textContent=names[view];document.querySelectorAll('[data-mobile-view]').forEach(button=>button.classList.toggle('active',button.dataset.mobileView===view));closeMobileMenu();document.querySelectorAll('.portal-menu,.account-menu,.sidebar-account-menu').forEach(menu=>menu.open=false);({top:0,behavior:'smooth'});if(view==='support')refreshSupportInbox().catch(e=>$('supportTicketError').textContent=e.message);if(view==='emailTemplates')loadEmailTemplates().catch(e=>$('emailTemplateError').textContent=e.message)}function updateOverview(){$('statCustomers').textContent=customers.length;$('statLicenses').textContent=licenseSummary.licenses;$('statGroups').textContent=licenseSummary.groups;$('statOpenTickets').textContent=supportTicketRows.filter(t=>t.status!=='closed').length}document.querySelectorAll('.nav-item[data-view],.menu-link[data-view]').forEach(button=>button.onclick=()=>setView(button.dataset.view));document.querySelectorAll('[data-mobile-view]').forEach(button=>button.onclick=()=>setView(button.dataset.mobileView));$('sidebarProfileAction').onclick=()=>setView('profile');document.querySelectorAll('[data-go-view]').forEach(button=>button.onclick=()=>setView(button.dataset.goView));$('menuToggle').onclick=()=>{const open=!$('sidebar').classList.contains('sidebar-open');$('sidebar').classList.toggle('sidebar-open',open);$('menuBackdrop').classList.toggle('open',open);$('menuToggle').setAttribute('aria-expanded',String(open))};$('menuBackdrop').onclick=closeMobileMenu;document.addEventListener('click',e=>{const active=e.target.closest('.sidebar-account-menu');document.querySelectorAll('.sidebar-account-menu[open]').forEach(menu=>{if(menu!==active)menu.open=false})});document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeMobileMenu();document.querySelectorAll('.portal-menu,.account-menu,.sidebar-account-menu').forEach(menu=>menu.open=false)}});
async function enterDashboard(){const me=await api('/api/admin/me');role=me.role;supportMeId=me.id||null;restoreSupportDrafts();portalPermissions=me.permissions||[];pfMe=me;pfState={};$('profileEmail').value=me.email||'';$('signatureFirstName').value=me.first_name||'';$('signatureName').value=me.name||''; $('sidebarUser').textContent=me.name||'Medewerker';const roleNames={owner:'Eigenaar',admin:'Beheer'};const functionNames=(me.functions||[]).map(x=>({beheer:'Beheer',support:'Support',sales:'Sales'}[x]||x));$('sidebarRole').textContent=roleNames[me.role]||(functionNames.join(' · ')||'Medewerker');const initials=(me.name||'Cohentra').trim().split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();$('userAvatarInitials').textContent=initials; $('profileAvatarInitials').textContent=initials;$('removeAvatar').hidden=!me.has_avatar;await loadCurrentAvatar(me);$('authScreen').classList.add('hidden');$('dashboard').classList.remove('hidden');$('addCustomer').classList.toggle('hidden',!can('customers.manage'));$('staffNav').classList.toggle('hidden',role!=='owner');document.querySelectorAll('.menu-team').forEach(item=>item.classList.toggle('hidden',role!=='owner'));$('mobileTeam').classList.toggle('hidden',role!=='owner');$('supportNav').classList.toggle('hidden',!can('support.view'));document.querySelectorAll('.menu-support').forEach(item=>item.classList.toggle('hidden',!can('support.view')));$('emailTemplatesNav').classList.toggle('hidden',!can('email.templates.manage'));document.querySelectorAll('.menu-email').forEach(item=>item.classList.toggle('hidden',!can('email.templates.manage')));$('mobileSupport').classList.toggle('hidden',!can('support.view'));$('customersNav').classList.toggle('hidden',!can('customers.view'));document.querySelectorAll('.menu-customers').forEach(item=>item.classList.toggle('hidden',!can('customers.view')));$('mobileCustomers').classList.toggle('hidden',!can('customers.view'));$('expiringCard').classList.toggle('hidden',!can('licenses.view'));document.querySelectorAll('.owner-shortcut').forEach(item=>item.classList.toggle('hidden',!can('support.view')));document.querySelectorAll('[data-go-view="customers"]').forEach(item=>item.classList.toggle('hidden',!can('customers.view')));$('statCustomersCard').classList.toggle('hidden',!can('customers.view'));$('statLicensesCard').classList.toggle('hidden',!can('licenses.view'));$('statGroupsCard').classList.toggle('hidden',!can('licenses.view'));tmForm='';tmResult=null;setView('overview');renderSecurity();pfLowCodes();const jobs=[];if(can('licenses.view'))jobs.push(loadLicenses());if(can('customers.view'))jobs.push(loadCustomers());if(can('support.view'))jobs.push(refreshSupportInbox());if(role==='owner'){await loadFunctionCatalog();jobs.push(loadStaff())}await Promise.all(jobs);startSessionTimer()}
var cxSelected='',cxFilter='active',cxDetail=null,cxMode='',cxForm='',cxMenu='',cxNewKey=null,cxNotesTimer=0,cxDetailsOpen=false;try{cxDetailsOpen=localStorage.getItem('cohentra-customer-details-open')==='1'}catch{}
const cxCountries=['Nederland','België','Duitsland','Luxemburg','Frankrijk','Verenigd Koninkrijk'];
function cxDate(v){if(!v)return '';const d=new Date(String(v).length===10?v+'T12:00:00':v);return isNaN(d)?String(v):d.toLocaleDateString('nl-NL',{day:'numeric',month:'short',year:'numeric'})}
function cxAgo(v){if(!v)return '';const days=Math.floor((Date.now()-new Date(v).getTime())/864e5);if(days<1)return 'vandaag';if(days<2)return 'gisteren';if(days<14)return days+' dagen geleden';if(days<60)return Math.floor(days/7)+' weken geleden';return Math.floor(days/30)+' maanden geleden'}
function cxInitials(n){return String(n||'?').trim().split(/\s+/).slice(0,2).map(x=>x[0]||'').join('').toUpperCase()||'?'}
function cxPlural(n,one,many){return n+' '+(n===1?one:many)}
function cxToast(text,bad){const t=$('customerToast');t.textContent=text||'';t.classList.toggle('bad',!!bad);clearTimeout(cxToast.timer);if(text)cxToast.timer=setTimeout(()=>{t.textContent=''},6000)}
function cxDuplicates(c){const n=String(c.name||'').trim().toLocaleLowerCase('nl-NL');return customers.filter(x=>x.id!==c.id&&String(x.name||'').trim().toLocaleLowerCase('nl-NL')===n)}
function cxMatches(c,f){return f==='all'||c.status===f}
function cxFiltered(){const q=$('customerSearch').value.trim().toLocaleLowerCase('nl-NL');return customers.filter(c=>cxMatches(c,cxFilter)&&(!q||[c.name,c.customer_number,c.contact_name,c.contact_email,c.city].some(v=>String(v||'').toLocaleLowerCase('nl-NL').includes(q))))}
function renderCustomerList(){const rows=cxFiltered(),active=customers.filter(c=>c.status==='active').length,paused=customers.length-active,labels={active:'Actief',paused:'Gepauzeerd',all:'Alle klanten'};$('customerSummary').textContent=cxPlural(active,'actieve klant','actieve klanten')+(paused?' · '+paused+' gepauzeerd':'');$('customerFilterLabel').textContent=labels[cxFilter];$('customerFilterCount').textContent=rows.length;
$('customers').innerHTML=cxInternRow()+(rows.length?rows.map(c=>{const used=Number(c.licenses_in_use||0),max=Number(c.max_licenses||0),full=max>0&&used>=max,open=Number(c.open_tickets||0);return '<button type="button" class="cx-row'+(c.id===cxSelected?' selected':'')+'" data-customer="'+safe(c.id)+'"><span class="cx-row-top"><span class="cx-row-name">'+safe(c.name)+'</span>'+(c.status!=='active'?'<span class="cx-tag paused">gepauzeerd</span>':cxDuplicates(c).length?'<span class="cx-tag dup">dubbele naam</span>':'')+'</span><span class="cx-row-sub">'+safe([c.customer_number,c.contact_name||c.contact_email,c.city].filter(Boolean).join(' · '))+'</span><span class="cx-chips">'+(c.product_id?'<span class="cx-chip'+(full?' full':'')+'">EventHub '+used+'/'+max+'</span>':'')+'<span class="cx-chip">'+cxPlural(Number(c.portal_users||0),'gebruiker','gebruikers')+'</span>'+(open&&can('support.view')?'<span class="cx-chip">'+cxPlural(open,'open ticket','open tickets')+'</span>':'')+'</span></button>'}).join(''):'<div class="cx-placeholder">Geen klanten in deze weergave.</div>')}
async function loadCustomers(opts={}){try{const d=await api('/api/admin/customers');customers=d.customers||[];updateOverview();if(cxSelected&&cxSelected!=='intern'&&!customers.some(c=>c.id===cxSelected)){cxSelected='';cxDetail=null}renderCustomerList();if(cxMode==='create')return;if(!cxSelected){const first=cxFiltered()[0];if(first)openCustomer(first.id);else renderCustomerDetail()}else if(opts.reloadDetail&&cxSelected!=='intern')await openCustomer(cxSelected,{keep:true})}catch(e){$('customers').innerHTML='<div class="cx-placeholder error">'+safe(e.message)+'</div>'}}
async function openCustomer(id,opts={}){if(!opts.keep){cxMode='';cxForm='';cxMenu='';cxNewKey=null;cxKeys=null;cxChecked.clear();cxLicFilter='active'}cxSelected=id;renderCustomerList();if(!opts.keep||!cxDetail)$('customerDetail').innerHTML='<div class="cx-placeholder">Klant laden…</div>';try{const scopeP=can('licenses.view')&&(id!=='intern'||role!=='support')?api('/api/admin/license-scope/'+encodeURIComponent(id)):Promise.resolve(null);let d;if(id==='intern'){d={intern:true,customer:{id:'intern',name:'Cohentra (intern)',status:'active'},products:[{product_id:'eventhub',name:'EventHub',enabled:1,product_active:1,allowed_license_types:['beta','admin']}],licenses:[],users:[],tickets:null,catalog:[]};d.scope=await scopeP}else{const both=await Promise.all([api('/api/admin/customers/'+encodeURIComponent(id)),scopeP]);d=both[0];d.scope=both[1]}if(cxSelected!==id)return;cxDetail=d;renderCustomerDetail()}catch(e){if(cxSelected===id)$('customerDetail').innerHTML='<div class="cx-placeholder error">'+safe(e.message)+'</div>'}}
function cxField(c,key,label,cls){const v=c?c[key]||'':'';const input=key==='country'?'<select id="cx_'+key+'">'+[...new Set([...cxCountries,v||'Nederland'])].map(x=>'<option'+(x===(v||'Nederland')?' selected':'')+'>'+safe(x)+'</option>').join('')+'</select>':'<input id="cx_'+key+'" value="'+safe(v)+'" maxlength="'+({name:120,contact_name:120,contact_email:254,invoice_email:254,street:160,website:200}[key]||80)+'"'+(key.includes('email')?' type="email"':'')+'>';return '<div class="'+(cls||'')+'"><label for="cx_'+key+'">'+label+'</label>'+input+'</div>'}
function cxDetailsForm(c){return '<form class="cx-form" data-cx-form="details"><h4>Bedrijf</h4>'+cxField(c,'name','Bedrijfsnaam *','full')+cxField(c,'kvk_number','KvK-nummer')+cxField(c,'vat_number','Btw-nummer')+cxField(c,'website','Website','full')+'<h4>Contactpersoon</h4>'+cxField(c,'contact_name','Naam')+cxField(c,'contact_role','Functie')+cxField(c,'contact_email','E-mailadres')+cxField(c,'phone','Telefoon')+'<h4>Adres en facturatie</h4>'+cxField(c,'street','Straat en huisnummer','full')+cxField(c,'postal_code','Postcode')+cxField(c,'city','Plaats')+cxField(c,'country','Land')+cxField(c,'invoice_email','Factuur-e-mail')+'<p class="cx-error" id="cxDetailsError" role="alert"></p><div class="cx-form-actions"><button type="button" class="cx-btn" data-cx-action="cancel-mode">Annuleren</button><button class="cx-btn primary">'+(cxMode==='create'?'Klant aanmaken':'Opslaan')+'</button></div></form>'}
function cxValue(v,html){return v?(html||safe(v)):'<span class="cx-none">—</span>'}
function cxDetailsView(c){const mail=v=>v?'<a href="mailto:'+encodeURIComponent(v)+'">'+safe(v)+'</a>':'',web=c.website?'<a href="'+safe(/^https?:\/\//i.test(c.website)?c.website:'https://'+c.website)+'" target="_blank" rel="noopener">'+safe(c.website)+'</a>':'';let h='<div class="cx-kv"><span>Contactpersoon</span><span>'+cxValue(c.contact_name,safe(c.contact_name)+(c.contact_role?' <span class="cx-line-sub">· '+safe(c.contact_role)+'</span>':''))+'</span><span>E-mail</span><span>'+cxValue(c.contact_email,mail(c.contact_email))+'</span><span>Telefoon</span><span>'+cxValue(c.phone,c.phone?'<a href="tel:'+safe(c.phone.replace(/[^+\d]/g,''))+'">'+safe(c.phone)+'</a>':'')+'</span><span>Plaats</span><span>'+cxValue(c.city)+'</span></div>';
if(cxDetailsOpen)h+='<div class="cx-group">Bedrijf</div><div class="cx-kv"><span>KvK-nummer</span><span>'+cxValue(c.kvk_number)+'</span><span>Btw-nummer</span><span>'+cxValue(c.vat_number)+'</span><span>Website</span><span>'+cxValue(c.website,web)+'</span></div><div class="cx-group">Adres en facturatie</div><div class="cx-kv"><span>Adres</span><span>'+(c.street||c.postal_code||c.city?safe(c.street)+(c.street?'<br>':'')+safe([c.postal_code,c.city].filter(Boolean).join(' '))+(c.country&&c.country!=='Nederland'?'<br>'+safe(c.country):''):'<span class="cx-none">—</span>')+'</span><span>Factuur-e-mail</span><span>'+cxValue(c.invoice_email,mail(c.invoice_email))+'</span></div>';
return h+'<p style="margin:10px 0 0"><button type="button" class="cx-btn link" data-cx-action="toggle-details" aria-expanded="'+cxDetailsOpen+'">'+(cxDetailsOpen?'Minder gegevens ▴':'Alle gegevens ▾')+'</button></p>'}
function cxLicenseLine(l){const until=l.valid_until,soon=until&&!l.expired&&(new Date(until+'T12:00:00')-Date.now())<30*864e5;return '<div class="cx-line"><span>'+safe(l.label||'Zonder naam')+' <span class="cx-line-sub">· '+safe(l.license_type)+'</span></span><span class="cx-line-sub '+(l.expired?'cx-expired':soon?'cx-soon':'')+'">'+(l.expired?'verlopen op '+cxDate(until):until?(soon?'⏱ ':'')+'tot '+cxDate(until):'onbeperkt')+'</span></div>'}
var cxLicFilter='active',cxChecked=new Set(),cxClosedGroups=new Set(),cxKeys=null,cxIssueGroup='';
function cxScope(){return cxDetail&&cxDetail.scope}
function cxLicOwner(){return cxDetail.intern?null:cxDetail.customer.id}
function cxLicStatus(l){if(l.revoked_at)return ['off','Ingetrokken'];if(l.expired)return ['off','Verlopen'];if(l.activated_at)return ['ok','Gekoppeld aan apparaat'+(l.last_seen_at?' · laatst online '+cxAgo(l.last_seen_at):'')];return ['wait','Nog niet gebruikt']}
function cxMenuHtml(key,label,items){const open=cxMenu==='lc:'+key;return '<span class="cx-pop"><button type="button" class="cx-icon cx-dots" data-cx-action="lc-menu" data-key="'+safe(key)+'" aria-haspopup="menu" aria-expanded="'+open+'" aria-label="'+safe(label)+'">⋯</button>'+(open?'<div class="cx-menu" role="menu">'+items.map(i=>i==='-'?'<div class="cx-sep" role="separator"></div>':i.title?'<div class="cx-menu-title">'+safe(i.title)+'</div>':'<button type="button" role="menuitem" class="'+(i.danger?'danger':'')+'" data-cx-action="'+i.a+'"'+Object.entries(i.data||{}).map(([k,v])=>' data-'+k+'="'+safe(v)+'"').join('')+'>'+safe(i.label)+'</button>').join('')+'</div>':'')+'</span>'}
function cxConfirm(kind,id,text,label,danger){return '<div class="'+(danger?'cx-danger':'cx-warn')+'">'+text+'<div class="cx-box-actions"><button type="button" class="cx-btn" data-cx-action="cancel-form">Annuleren</button><button type="button" class="cx-btn '+(danger?'danger':'primary')+'" data-cx-action="'+kind+'" data-id="'+safe(id||'')+'">'+label+'</button></div></div>'}
function cxExtendForm(kind,id,current,note){const today=new Date().toISOString().slice(0,10),base=current&&current>today?new Date(current+'T12:00:00'):new Date();base.setFullYear(base.getFullYear()+1);return '<form class="cx-form cx-inset" data-cx-form="'+kind+'" data-id="'+safe(id||'')+'"><div><label for="lcUntil">Nieuwe einddatum</label><input id="lcUntil" type="date" min="'+today+'" value="'+base.toISOString().slice(0,10)+'"></div><div class="cx-line-sub" style="align-self:end;padding-bottom:8px">'+safe(note||'')+'</div><p class="cx-error" id="lcError" role="alert"></p><div class="cx-form-actions"><button type="button" class="cx-btn" data-cx-action="cancel-form">Annuleren</button><button class="cx-btn primary">Verlengen</button></div></form>'}
function cxGroupForm(kind,id,name){return '<form class="cx-form cx-inset" data-cx-form="'+kind+'" data-id="'+safe(id||'')+'"><div class="full"><label for="lcGroupName">Groepsnaam</label><input id="lcGroupName" maxlength="60" value="'+safe(name||'')+'" placeholder="Bijvoorbeeld: Balie of Regio Noord"></div><p class="cx-error" id="lcError" role="alert"></p><div class="cx-form-actions"><button type="button" class="cx-btn" data-cx-action="cancel-form">Annuleren</button><button class="cx-btn primary">'+(kind==='lc-group-new'?'Groep toevoegen':'Opslaan')+'</button></div></form>'}
function cxIssueForm(p){const sc=cxScope(),types=cxDetail.intern?['beta','admin']:p.allowed_license_types,next=new Date();next.setFullYear(next.getFullYear()+1);return '<form class="cx-form cx-inset" data-cx-form="lc-issue"><div class="full"><label for="lcLabel">Naam of apparaat</label><input id="lcLabel" maxlength="80" placeholder="Bijvoorbeeld: Balie iPad"></div><div><label for="lcCount">Aantal</label><input id="lcCount" type="number" min="1" max="100" value="1"></div><div><label for="lcType">Type</label><select id="lcType">'+types.map(t=>'<option value="'+t+'">'+(t==='admin'?'Beheerder (onbeperkt)':'Gesloten beta')+'</option>').join('')+'</select></div><div><label for="lcGroup">Groep</label><select id="lcGroup"><option value="">Zonder groep</option>'+sc.groups.map(g=>'<option value="'+safe(g.id)+'"'+(g.id===cxIssueGroup?' selected':'')+'>'+safe(g.name)+'</option>').join('')+'</select></div><div id="lcUntilBox"><label for="lcIssueUntil">Geldig tot en met</label><input id="lcIssueUntil" type="date" value="'+next.toISOString().slice(0,10)+'"></div><p class="cx-line-sub full" style="margin:0">Bij meer dan één licentie krijgt elke licentie een volgnummer achter de naam.</p><p class="cx-error" id="lcError" role="alert"></p><div class="cx-form-actions"><button type="button" class="cx-btn" data-cx-action="cancel-form">Annuleren</button><button class="cx-btn primary">Uitgeven</button></div></form>'}
function cxLicRow(l){const sc=cxScope(),manage=can('licenses.manage'),st=cxLicStatus(l),id=safe(l.id),name=l.label||'Zonder naam',soon=!l.revoked_at&&!l.expired&&!l.unlimited&&l.valid_until&&(new Date(l.valid_until+'T12:00:00')-Date.now())<30*864e5;
const date=l.revoked_at?'ingetrokken '+cxDate(l.revoked_at):l.unlimited?'onbeperkt':l.expired?'verlopen op '+cxDate(l.valid_until):(soon?'⏱ ':'')+'tot '+cxDate(l.valid_until),items=[];
if(!l.revoked_at&&manage){items.push({a:'lc-rename',label:'Naam wijzigen',data:{id:l.id}});if(!l.unlimited)items.push({a:'lc-extend',label:'Verlengen',data:{id:l.id}});if(can('licenses.issue'))items.push({a:'lc-replace',label:'Nieuwe sleutel maken',data:{id:l.id}});const others=sc.groups.filter(g=>g.id!==l.group_id);if(others.length||l.group_id){items.push('-',{title:'Verplaatsen naar'});others.forEach(g=>items.push({a:'lc-move',label:g.name,data:{id:l.id,group:g.id}}));if(l.group_id)items.push({a:'lc-move',label:'Zonder groep',data:{id:l.id,group:''}})}items.push('-');if(l.activated_at)items.push({a:'lc-reset',label:'Loskoppelen van apparaat',data:{id:l.id}});items.push({a:'lc-revoke',label:'Intrekken',danger:true,data:{id:l.id}})}
let h='<div class="cx-lic'+(l.revoked_at?' revoked':'')+'">'+(manage?'<input type="checkbox" data-cx-check="'+id+'"'+(cxChecked.has(l.id)?' checked':'')+(l.revoked_at?' disabled':'')+' aria-label="Selecteer '+safe(name)+'">':'<span></span>')+'<span class="cx-lic-main"><span class="cx-lic-name">'+safe(name)+' <span class="cx-line-sub">· '+safe(l.license_type)+'</span></span><span class="cx-state '+st[0]+'"><span class="cx-dot"></span>'+safe(st[1])+'</span></span><span class="cx-line-sub cx-lic-date '+(l.expired?'cx-expired':soon?'cx-soon':'')+'">'+safe(date)+'</span>'+(items.length?cxMenuHtml('l:'+l.id,'Acties voor '+name,items):'<span></span>')+'</div>';
if(cxForm==='lc-rename:'+l.id)h+='<form class="cx-form cx-inset" data-cx-form="lc-rename" data-id="'+id+'"><div class="full"><label for="lcName">Naam of apparaat</label><input id="lcName" maxlength="80" value="'+safe(l.label||'')+'"></div><p class="cx-error" id="lcError" role="alert"></p><div class="cx-form-actions"><button type="button" class="cx-btn" data-cx-action="cancel-form">Annuleren</button><button class="cx-btn primary">Opslaan</button></div></form>';
if(cxForm==='lc-extend:'+l.id)h+=cxExtendForm('lc-extend',l.id,l.valid_until,'Nu: '+(l.expired?'verlopen op ':'tot ')+cxDate(l.valid_until));
if(cxForm==='lc-replace:'+l.id)h+=cxConfirm('lc-replace-confirm',l.id,'<strong>Nieuwe sleutel voor '+safe(name)+'?</strong> De huidige sleutel stopt direct met werken. Het apparaat activeert daarna opnieuw met de nieuwe sleutel. Naam, groep en geldigheid blijven gelijk.','Nieuwe sleutel maken',false);
if(cxForm==='lc-reset:'+l.id)h+=cxConfirm('lc-reset-confirm',l.id,'<strong>'+safe(name)+' loskoppelen?</strong> De licentie blijft geldig en kan daarna op een ander apparaat worden geactiveerd.','Loskoppelen',false);
if(cxForm==='lc-revoke:'+l.id)h+=cxConfirm('lc-revoke-confirm',l.id,'<strong>'+safe(name)+' intrekken?</strong> De licentie stopt direct met werken. Dit kun je niet ongedaan maken.','Intrekken',true);
return h}
function cxLicensesCard(p){const sc=cxScope(),intern=!!cxDetail.intern,c=cxDetail.customer,pid=p.product_id,manage=can('licenses.manage'),issueOk=!!sc&&can('licenses.issue')&&(intern||(c.status==='active'&&Number(p.enabled)===1&&Number(p.product_active)!==0)),max=intern?0:Number(p.max_licenses||0),used=intern?(sc?sc.licenses.filter(l=>!l.revoked_at&&!l.expired).length:0):Number(p.in_use||0),full=max>0&&used>=max;
const menu=[];if(issueOk)menu.push({a:'lc-issue',label:'Licenties uitgeven'});if(sc&&manage)menu.push({a:'lc-group-new',label:'Groep toevoegen'});if(!intern&&can('customers.manage'))menu.push(...(menu.length?['-']:[]),{a:'product-settings',label:'Productinstellingen',data:{product:pid}});
let h='<div class="cx-product"><div class="cx-product-head"><span class="cx-product-name">'+safe(p.name)+'</span>'+(menu.length?cxMenuHtml('sec','Acties voor '+p.name,menu):'')+'</div>';
if(!intern&&Number(p.enabled)!==1)h+='<p class="cx-empty" style="margin:8px 0 0">Uitgeschakeld voor deze klant. Licenties van dit product werken niet.</p>';
if(intern)h+='<p class="cx-line-sub" style="margin:6px 0 0">'+cxPlural(used,'actieve licentie','actieve licenties')+'</p>';
else h+='<div class="cx-usage"><div class="cx-bar'+(full?' full':'')+'"><i style="width:'+(max?Math.min(100,Math.round(used/max*100)):0)+'%"></i></div><span>'+used+' van '+max+' in gebruik</span></div><div class="cx-line-sub">Toegestaan: '+safe(p.allowed_license_types.map(t=>t==='admin'?'Beheerder':'Gesloten beta').join(', '))+(full?' · <span class="cx-soon">limiet bereikt</span>':'')+'</div>';
if(cxForm==='product:'+pid)h+=cxProductForm(p);
if(!sc)return h+'</div>';
if(cxKeys)h+='<div class="cx-ok"><strong>'+(cxKeys.length===1?'Sleutel aangemaakt.':cxPlural(cxKeys.length,'sleutel','sleutels')+' aangemaakt.')+'</strong> Kopieer '+(cxKeys.length===1?'hem':'ze')+' nu; sleutels worden maar één keer getoond.'+cxKeys.map(k=>'<div class="cx-key"><code>'+safe((k.label?k.label+': ':'')+k.key)+'</code></div>').join('')+'<div class="cx-box-actions"><button type="button" class="cx-btn" data-cx-action="lc-copy-keys">'+(cxKeys.length===1?'Kopiëren':'Alles kopiëren')+'</button><button type="button" class="cx-btn" data-cx-action="lc-keys-done">Sluiten</button></div></div>';
if(cxForm==='lc-issue')h+=cxIssueForm(p);
if(cxForm==='lc-group-new')h+=cxGroupForm('lc-group-new','','');
const lic=sc.licenses.filter(l=>(l.product_id||'eventhub')===pid),inView=l=>cxLicFilter==='all'||(cxLicFilter==='ended'?!!(l.revoked_at||l.expired):!(l.revoked_at||l.expired)),shown=lic.filter(inView),labels={active:'Actieve licenties',ended:'Verlopen en ingetrokken',all:'Alle licenties'};
h+='<div class="cx-lic-tools"><span class="cx-pop"><button type="button" class="cx-btn link cx-filter" data-cx-action="lc-menu" data-key="flt" aria-haspopup="menu" aria-expanded="'+(cxMenu==='lc:flt')+'">'+labels[cxLicFilter]+' ('+shown.length+') ▾</button>'+(cxMenu==='lc:flt'?'<div class="cx-menu" role="menu" style="left:0;right:auto">'+Object.entries(labels).map(([k,l])=>'<button type="button" role="menuitemradio" aria-checked="'+(k===cxLicFilter)+'" data-cx-action="lc-filter" data-filter="'+k+'"><span style="flex:1">'+l+'</span><span class="cx-sub">'+lic.filter(x=>k==='all'||(k==='ended'?!!(x.revoked_at||x.expired):!(x.revoked_at||x.expired))).length+'</span>'+(k===cxLicFilter?' ✓':'')+'</button>').join('')+'</div>':'')+'</span></div>';
const selected=[...cxChecked].filter(id=>lic.some(l=>l.id===id&&!l.revoked_at));
if(selected.length&&manage)h+='<div class="cx-bulk"><strong>'+cxPlural(selected.length,'licentie','licenties')+' geselecteerd</strong><span class="cx-spacer"></span>'+cxMenuHtml('bulk','Acties voor de selectie',[{title:'Verplaatsen naar'},...sc.groups.map(g=>({a:'lc-move-bulk',label:g.name,data:{group:g.id}})),{a:'lc-move-bulk',label:'Zonder groep',data:{group:''}},'-',{a:'lc-extend-bulk',label:'Verlengen'},{a:'lc-revoke-bulk',label:'Intrekken',danger:true}])+'<button type="button" class="cx-icon cx-dots" data-cx-action="lc-clear" aria-label="Selectie wissen" title="Selectie wissen">×</button></div>';
if(cxForm==='lc-extend-bulk')h+=cxExtendForm('lc-extend-bulk','',null,'Licenties met een onbeperkte geldigheid worden overgeslagen.');
if(cxForm==='lc-revoke-bulk')h+=cxConfirm('lc-revoke-bulk-confirm','','<strong>'+cxPlural(selected.length,'licentie','licenties')+' intrekken?</strong> Ze stoppen direct met werken. Dit kun je niet ongedaan maken.','Intrekken',true);
const known=new Set(sc.groups.map(g=>g.id)),groups=[...sc.groups.map(g=>({id:g.id,name:g.name})),{id:'',name:'Zonder groep'}];
h+=groups.map(g=>{const items=shown.filter(l=>g.id?l.group_id===g.id:!known.has(l.group_id||''));if(!g.id&&!items.length)return '';const open=!cxClosedGroups.has(g.id),gmenu=[];if(g.id&&issueOk)gmenu.push({a:'lc-issue',label:'Licenties uitgeven in deze groep',data:{group:g.id}});if(g.id&&manage)gmenu.push({a:'lc-group-rename',label:'Groep hernoemen',data:{group:g.id}},'-',{a:'lc-group-delete',label:'Groep verwijderen',danger:true,data:{group:g.id}});
let gh='<div class="cx-lic-group"><div class="cx-lic-group-head"><button type="button" class="cx-btn link cx-group-toggle" data-cx-action="lc-toggle-group" data-group="'+safe(g.id)+'" aria-expanded="'+open+'">'+(open?'▾ ':'▸ ')+safe(g.name)+'</button><span class="cx-chip">'+items.length+'</span><span class="cx-spacer"></span>'+(gmenu.length?cxMenuHtml('g:'+g.id,'Acties voor groep '+g.name,gmenu):'')+'</div>';
if(cxForm==='lc-group-rename:'+g.id)gh+=cxGroupForm('lc-group-rename',g.id,g.name);
if(cxForm==='lc-group-delete:'+g.id)gh+=cxConfirm('lc-group-delete-confirm',g.id,'<strong>Groep '+safe(g.name)+' verwijderen?</strong> De licenties blijven bestaan en komen onder Zonder groep.','Groep verwijderen',true);
if(open)gh+=items.length?items.map(cxLicRow).join(''):'<p class="cx-empty" style="margin:0 0 8px 18px;font-size:12px">Geen licenties in deze weergave.</p>';
return gh+'</div>'}).join('');
if(!lic.length)h+='<p class="cx-empty" style="margin:8px 0 0">Nog geen licenties uitgegeven.</p>';
return h+'</div>'}
function cxProductCard(p){return cxLicensesCard(p)}
function cxLicAfter(){const t=$('lcType');if(t)$('lcUntilBox').style.visibility=t.value==='admin'?'hidden':'visible';if(cxMenu){const b=$('customerDetail').querySelector('.cx-menu button');if(b)b.focus()}}
function cxRenderFocus(id){renderCustomerDetail();const el=id&&$(id);if(el){el.focus();if(el.select&&el.type!=='date')el.select()}const f=$('customerDetail').querySelector('form[data-cx-form^="lc-"],.cx-lic+.cx-warn,.cx-lic+.cx-danger,.cx-product>.cx-warn,.cx-product>.cx-danger');if(f)f.scrollIntoView({block:'nearest',behavior:'smooth'})}
async function cxReloadLicenses(){if(cxDetail&&cxDetail.intern)await openCustomer('intern',{keep:true});else await loadCustomers({reloadDetail:true});loadLicenses().catch(()=>{})}
async function cxLicAction(a,t,e){const id=t.dataset.id,group=t.dataset.group;
if(a==='lc-menu'){e.stopPropagation();const k='lc:'+t.dataset.key;cxMenu=cxMenu===k?'':k;return renderCustomerDetail()}
cxMenu='';
if(a==='lc-filter'){cxLicFilter=t.dataset.filter;cxChecked.clear();return renderCustomerDetail()}
if(a==='lc-toggle-group'){cxClosedGroups.has(group)?cxClosedGroups.delete(group):cxClosedGroups.add(group);return renderCustomerDetail()}
if(a==='lc-clear'){cxChecked.clear();if(cxForm==='lc-extend-bulk'||cxForm==='lc-revoke-bulk')cxForm='';return renderCustomerDetail()}
if(a==='lc-keys-done'){cxKeys=null;return renderCustomerDetail()}
if(a==='lc-copy-keys'){try{await navigator.clipboard.writeText(cxKeys.map(k=>(k.label?k.label+': ':'')+k.key).join('\n'));t.textContent='Gekopieerd'}catch{t.textContent='Selecteer en kopieer zelf'}return}
if(a==='lc-issue'){cxForm='lc-issue';cxIssueGroup=group||'';cxKeys=null;return cxRenderFocus('lcLabel')}
if(a==='lc-group-new'){cxForm='lc-group-new';return cxRenderFocus('lcGroupName')}
if(a==='lc-extend-bulk'||a==='lc-revoke-bulk'){cxForm=a;return cxRenderFocus(a==='lc-extend-bulk'?'lcUntil':null)}
if(['lc-rename','lc-extend','lc-replace','lc-reset','lc-revoke'].includes(a)){cxForm=a+':'+id;return cxRenderFocus(a==='lc-rename'?'lcName':a==='lc-extend'?'lcUntil':null)}
if(a==='lc-group-rename'||a==='lc-group-delete'){cxForm=a+':'+group;return cxRenderFocus(a==='lc-group-rename'?'lcGroupName':null)}
const run=(fn,msg)=>cxRun(t,async()=>{try{const r=await fn();cxForm='';cxToast(typeof msg==='function'?msg(r):msg);await cxReloadLicenses()}catch(err){cxToast(err.message,true)}});
if(a==='lc-move')return run(()=>api('/api/admin/licenses/group',{method:'POST',body:JSON.stringify({license_ids:[id],group_id:group||null})}),'Licentie verplaatst.');
if(a==='lc-move-bulk'){const ids=[...cxChecked];return run(async()=>{const r=await api('/api/admin/licenses/group',{method:'POST',body:JSON.stringify({license_ids:ids,group_id:group||null})});cxChecked.clear();return r},r=>cxPlural(Number(r.moved||0),'licentie','licenties')+' verplaatst.')}
if(a==='lc-replace-confirm')return run(async()=>{const r=await api('/api/admin/licenses/'+encodeURIComponent(id)+'/replace',{method:'POST',body:'{}'});cxKeys=[{label:r.label,key:r.license_key}];return r},'Nieuwe sleutel gemaakt. De oude sleutel werkt niet meer.');
if(a==='lc-reset-confirm')return run(()=>api('/api/admin/licenses/'+encodeURIComponent(id)+'/reset-activation',{method:'POST',body:'{}'}),'Licentie losgekoppeld. Hij kan nu op een ander apparaat worden geactiveerd.');
if(a==='lc-revoke-confirm')return run(()=>api('/api/admin/licenses/'+encodeURIComponent(id)+'/revoke',{method:'POST',body:'{}'}),'Licentie ingetrokken.');
if(a==='lc-revoke-bulk-confirm'){const ids=[...cxChecked];return run(async()=>{for(const x of ids)await api('/api/admin/licenses/'+encodeURIComponent(x)+'/revoke',{method:'POST',body:'{}'});cxChecked.clear();return ids.length},n=>cxPlural(n,'licentie','licenties')+' ingetrokken.')}
if(a==='lc-group-delete-confirm')return run(()=>api('/api/admin/groups/'+encodeURIComponent(id),{method:'DELETE'}),'Groep verwijderd. De licenties staan nu onder Zonder groep.')}
async function cxLicSubmit(kind,f,button){const err=m=>{const el=$('lcError');if(el)el.textContent=m},owner=cxLicOwner(),today=new Date().toISOString().slice(0,10);
return cxRun(button,async()=>{try{
if(kind==='lc-issue'){const label=$('lcLabel').value.trim(),count=Number($('lcCount').value),type=$('lcType').value,until=$('lcIssueUntil').value;if(!Number.isInteger(count)||count<1||count>100)return err('Kies een aantal tussen 1 en 100.');if(type!=='admin'&&(!until||until<today))return err('Kies een einddatum in de toekomst.');const d=await api('/api/admin/licenses',{method:'POST',body:JSON.stringify({label,license_type:type,valid_from:today,valid_until:type==='admin'?today:until,count,customer_id:owner,product_id:'eventhub',group_id:$('lcGroup').value||null})});cxForm='';cxKeys=d.licenses.map(x=>({label:x.label,key:x.license_key}));cxToast(cxPlural(d.licenses.length,'licentie','licenties')+' uitgegeven.');return cxReloadLicenses()}
if(kind==='lc-group-new'||kind==='lc-group-rename'){const name=$('lcGroupName').value.trim();if(!name)return err('Vul een groepsnaam in.');if(kind==='lc-group-new')await api('/api/admin/groups',{method:'POST',body:JSON.stringify({name,customer_id:owner})});else await api('/api/admin/groups/'+encodeURIComponent(f.dataset.id),{method:'PATCH',body:JSON.stringify({name})});cxForm='';cxToast(kind==='lc-group-new'?'Groep '+name+' toegevoegd.':'Groep hernoemd.');return cxReloadLicenses()}
if(kind==='lc-rename'){await api('/api/admin/licenses/'+encodeURIComponent(f.dataset.id)+'/label',{method:'POST',body:JSON.stringify({label:$('lcName').value.trim()})});cxForm='';cxToast('Naam opgeslagen.');return cxReloadLicenses()}
if(kind==='lc-extend'||kind==='lc-extend-bulk'){const until=$('lcUntil').value,ids=kind==='lc-extend'?[f.dataset.id]:[...cxChecked];if(!until||until<today)return err('Kies een einddatum vanaf vandaag.');const d=await api('/api/admin/licenses/extend',{method:'POST',body:JSON.stringify({license_ids:ids,valid_until:until})});cxForm='';if(kind==='lc-extend-bulk')cxChecked.clear();cxToast(cxPlural(Number(d.extended||0),'licentie','licenties')+' verlengd tot en met '+cxDate(until)+'.'+(d.skipped?' '+d.skipped+' overgeslagen (onbeperkt of ingetrokken).':''));return cxReloadLicenses()}
}catch(ex){err(ex.message)}})}
$('customerDetail').addEventListener('change',e=>{if(e.target.id==='lcType'){$('lcUntilBox').style.visibility=e.target.value==='admin'?'hidden':'visible';return}const c=e.target.closest('[data-cx-check]');if(c){if(c.checked)cxChecked.add(c.dataset.cxCheck);else cxChecked.delete(c.dataset.cxCheck);renderCustomerDetail()}});
function cxInternRow(){if(role!=='owner'||!can('licenses.view'))return '';const q=$('customerSearch').value.trim().toLocaleLowerCase('nl-NL');if(q&&!'cohentra (intern) eigen licenties'.includes(q))return '';return '<button type="button" class="cx-row'+(cxSelected==='intern'?' selected':'')+'" data-customer="intern"><span class="cx-row-top"><span class="cx-row-name">Cohentra (intern)</span></span><span class="cx-row-sub">Eigen licenties, demo’s en tests</span></button>'}
function cxProductForm(p,isNew){const types=p?p.allowed_license_types:['beta'];return '<form class="cx-form cx-inset" data-cx-form="product" data-product="'+safe(p?p.product_id:'')+'">'+(isNew?'<div><label for="cxProductId">Product</label><select id="cxProductId">'+cxDetail.catalog.filter(x=>!cxDetail.products.some(y=>y.product_id===x.id)).map(x=>'<option value="'+safe(x.id)+'">'+safe(x.name)+'</option>').join('')+'</select></div>':'')+'<div><label for="cxProductMax">Maximaal aantal licenties</label><input id="cxProductMax" type="number" min="0" max="10000" value="'+(p?Number(p.max_licenses):5)+'"></div><div class="full"><label>Toegestane licentietypes</label><div class="cx-checks"><label><input type="checkbox" id="cxTypeBeta"'+(types.includes('beta')?' checked':'')+'>Gesloten beta</label><label><input type="checkbox" id="cxTypeAdmin"'+(types.includes('admin')?' checked':'')+'>Beheerder</label>'+(isNew?'':'<label><input type="checkbox" id="cxProductEnabled"'+(Number(p.enabled)===1?' checked':'')+'>Product actief voor deze klant</label>')+'</div></div><p class="cx-error" id="cxProductError" role="alert"></p><div class="cx-form-actions"><button type="button" class="cx-btn" data-cx-action="cancel-form">Annuleren</button><button class="cx-btn primary">'+(isNew?'Koppelen':'Opslaan')+'</button></div></form>'}
function cxUserLine(u){const state=u.disabled_at?['off','Uitgeschakeld']:Number(u.active)===1?['ok','Actief'+(u.last_seen_at?' · '+cxAgo(u.last_seen_at):'')]:['wait','Uitgenodigd · nog niet geactiveerd'],uid=safe(u.id),items=[];if(!u.disabled_at)items.push(['user-resend',Number(u.active)===1?'Wachtwoordlink sturen':'Uitnodiging opnieuw sturen','']);items.push(u.disabled_at?['user-enable','Weer inschakelen','']:['user-disable','Toegang uitschakelen','danger']);return '<div class="cx-line"><span class="cx-user"><span class="cx-avatar'+(u.disabled_at?' off':'')+'">'+safe(cxInitials(u.name||u.email))+'</span><span><strong>'+safe(u.name||u.email||u.username)+'</strong><small>'+safe(u.email||u.username)+'</small></span></span><span style="display:flex;align-items:center;gap:8px"><span class="cx-state '+state[0]+'"><span class="cx-dot"></span>'+safe(state[1])+'</span>'+(can('customers.manage')?'<span class="cx-pop"><button type="button" class="cx-icon" data-cx-action="user-menu" data-user="'+uid+'" aria-haspopup="menu" aria-expanded="'+(cxMenu==='user:'+u.id)+'" aria-label="Acties voor '+safe(u.name||u.email)+'">⋯</button>'+(cxMenu==='user:'+u.id?'<div class="cx-menu" role="menu">'+items.map(i=>'<button type="button" role="menuitem" class="'+i[2]+'" data-cx-action="'+i[0]+'" data-user="'+uid+'">'+i[1]+'</button>').join('')+'</div>':'')+'</span>':'')+'</span></div>'}
function renderCustomerDetail(){const box=$('customerDetail');if(cxMode==='create'){box.innerHTML='<div class="cx-sec"><div class="cx-title"><div><h2>Nieuwe klant</h2><p class="cx-meta">EventHub wordt gekoppeld met 5 licenties (Gesloten beta). Dat pas je daarna aan bij het product.</p></div></div></div><div class="cx-sec">'+cxDetailsForm(null)+'</div>';$('cx_name').focus();return}
if(!cxDetail){box.innerHTML='<div class="cx-placeholder">'+(customers.length?'Selecteer een klant.':'Nog geen klanten. Voeg je eerste klant toe.')+'</div>';return}
if(cxDetail.intern){box.innerHTML='<div class="cx-sec"><div class="cx-title"><div><h2>Cohentra (intern)</h2><p class="cx-meta">Licenties zonder klant, voor eigen teams, demo’s en tests</p></div></div></div><div class="cx-sec"><div class="cx-sec-head"><span class="cx-sec-title">LICENTIES</span></div>'+cxLicensesCard(cxDetail.products[0])+'</div>';cxLicAfter();return}
const d=cxDetail,c=d.customer,paused=c.status!=='active',manage=can('customers.manage'),active=d.licenses.filter(l=>!l.expired).length,activeUsers=d.users.filter(u=>!u.disabled_at).length,dups=cxDuplicates(c),menu=[];
if(manage&&!paused)menu.push(['invite','Portaalgebruiker uitnodigen','']);if(can('support.reply'))menu.push(['ticket-new','Ticket aanmaken','']);if(manage)menu.push(['edit','Klantgegevens bewerken','']);const danger=[];if(manage)danger.push(paused?['resume','Klant hervatten','']:['pause-ask','Klant pauzeren','danger']);if(role==='owner')danger.push(['delete-ask','Klant verwijderen','danger']);
let h='';if(dups.length)h+='<div class="cx-sec" style="padding-bottom:0;border:0"><div class="cx-warn">Er '+(dups.length===1?'is':'zijn')+' nog '+(dups.length===1?'een klant':dups.length+' klanten')+' met de naam '+safe(c.name)+': '+dups.map(x=>'<button type="button" class="cx-btn link" data-cx-action="open-customer" data-id="'+safe(x.id)+'">'+safe(x.customer_number||'andere klant')+'</button>').join(', ')+'. Controleer of het om dezelfde klant gaat.</div></div>';
h+='<div class="cx-sec"><div class="cx-title"><div><h2>'+safe(c.name)+'</h2><p class="cx-meta">'+safe([c.customer_number,'klant sinds '+cxDate(c.created_at)].filter(Boolean).join(' · '))+'</p></div><div class="cx-title-actions"><span class="cx-pill '+(paused?'paused':'active')+'"><span class="cx-dot"></span>'+(paused?'Gepauzeerd':'Actief')+'</span>'+(menu.length||danger.length?'<span class="cx-pop"><button type="button" class="cx-icon" data-cx-action="menu" aria-haspopup="menu" aria-expanded="'+(cxMenu==='header')+'" aria-label="Meer acties">⋯</button>'+(cxMenu==='header'?'<div class="cx-menu" role="menu">'+menu.map(i=>'<button type="button" role="menuitem" data-cx-action="'+i[0]+'">'+i[1]+'</button>').join('')+(menu.length&&danger.length?'<div class="cx-sep" role="separator"></div>':'')+danger.map(i=>'<button type="button" role="menuitem" class="'+i[2]+'" data-cx-action="'+i[0]+'">'+i[1]+'</button>').join('')+'</div>':'')+'</span>':'')+'</div></div>';
if(cxForm==='pause')h+='<div class="cx-warn" style="margin-top:12px"><strong>'+(active?cxPlural(active,'licentie stopt','licenties stoppen')+' direct met werken':'Er zijn geen actieve licenties')+'</strong> en '+(activeUsers?cxPlural(activeUsers,'portaalgebruiker kan','portaalgebruikers kunnen'):'niemand kan')+' niet meer inloggen. Gegevens blijven bewaard; hervatten kan altijd.<div class="cx-box-actions"><button type="button" class="cx-btn" data-cx-action="cancel-form">Annuleren</button><button type="button" class="cx-btn danger" data-cx-action="pause-confirm">Pauzeren</button></div></div>';
if(cxForm==='delete'){const parts=[cxPlural(d.licenses.length,'licentie','licenties'),cxPlural(d.users.length,'portaalaccount','portaalaccounts'),d.tickets?cxPlural(d.tickets.length,'supportticket','supporttickets'):'alle supporttickets'];h+='<form class="cx-danger" style="margin-top:12px" data-cx-form="delete"><strong>'+safe(c.name)+' definitief verwijderen?</strong><br>Dit verwijdert de klant met '+safe(parts.join(', '))+'. Licenties worden ingetrokken en stoppen direct met werken. Dit kun je niet ongedaan maken. Wil je alleen tijdelijk blokkeren? Kies dan pauzeren.<label for="cxDeleteName" style="display:block;margin:10px 0 4px;font-size:12px">Typ <strong>'+safe(c.name)+'</strong> ter bevestiging</label><input id="cxDeleteName" autocomplete="off" style="width:100%;padding:7px 10px"><p class="cx-error" id="cxDeleteError" role="alert" style="margin-top:6px"></p><div class="cx-box-actions"><button type="button" class="cx-btn" data-cx-action="cancel-form">Annuleren</button><button class="cx-btn danger">Definitief verwijderen</button></div></form>'}
h+='</div><div class="cx-sec"><div class="cx-sec-head"><span class="cx-sec-title">KLANTGEGEVENS</span>'+(manage&&cxMode!=='edit'?'<button type="button" class="cx-btn" data-cx-action="edit">Bewerken</button>':'')+'</div>'+(cxMode==='edit'?cxDetailsForm(c):cxDetailsView(c))+'</div>';
const free=d.catalog.filter(x=>!d.products.some(y=>y.product_id===x.id));h+='<div class="cx-sec"><div class="cx-sec-head"><span class="cx-sec-title">PRODUCTEN EN LICENTIES</span>'+(manage&&free.length&&cxForm!=='link'?'<button type="button" class="cx-btn" data-cx-action="link">Product koppelen</button>':'')+'</div>'+(cxForm==='link'?cxProductForm(null,true):'')+(d.products.length?d.products.map(cxProductCard).join(''):cxForm==='link'?'':'<p class="cx-empty">Nog geen producten gekoppeld.</p>')+'</div>';
h+='<div class="cx-sec"><div class="cx-sec-head"><span class="cx-sec-title">PORTAALGEBRUIKERS</span>'+(manage&&!paused&&cxForm!=='invite'?'<button type="button" class="cx-btn" data-cx-action="invite">Uitnodigen</button>':'')+'</div>'+(cxForm==='invite'?'<form class="cx-form cx-inset" data-cx-form="invite" style="margin:0 0 10px"><div><label for="cxInviteName">Naam</label><input id="cxInviteName" maxlength="120" placeholder="Bijvoorbeeld: Sanne Vos"></div><div><label for="cxInviteEmail">E-mailadres</label><input id="cxInviteEmail" type="email" maxlength="254" placeholder="naam@bedrijf.nl"></div><p class="cx-line-sub full" style="margin:0">Deze persoon krijgt een link die één uur geldig is om een eigen wachtwoord te kiezen.</p><p class="cx-error" id="cxInviteError" role="alert"></p><div class="cx-form-actions"><button type="button" class="cx-btn" data-cx-action="cancel-form">Annuleren</button><button class="cx-btn primary">Uitnodiging sturen</button></div></form>':'')+(d.users.length?d.users.map(cxUserLine).join(''):cxForm==='invite'?'':'<p class="cx-empty">Nog niemand van deze klant heeft toegang tot het klantenportaal.</p>')+'</div>';
if(d.tickets)h+='<div class="cx-sec"><div class="cx-sec-head"><span class="cx-sec-title">SUPPORT</span>'+(can('support.reply')&&cxForm!=='ticket'?'<button type="button" class="cx-btn" data-cx-action="ticket-new">Nieuw ticket</button>':'')+'</div>'+(cxForm==='ticket'?'<form class="cx-form cx-inset" data-cx-form="ticket" style="margin:0 0 10px"><div class="full"><label for="cxTicketSubject">Onderwerp</label><input id="cxTicketSubject" maxlength="120" placeholder="Bijvoorbeeld: Telefonische vraag over licenties"></div><div class="full"><label for="cxTicketMessage">Omschrijving</label><textarea id="cxTicketMessage" maxlength="6000" rows="3" placeholder="Wat vraagt de klant?"></textarea></div><p class="cx-line-sub full" style="margin:0">Het ticket komt op jouw naam in Support te staan, met status In behandeling. De klant krijgt geen e-mail.</p><p class="cx-error" id="cxTicketError" role="alert"></p><div class="cx-form-actions"><button type="button" class="cx-btn" data-cx-action="cancel-form">Annuleren</button><button class="cx-btn primary">Ticket aanmaken</button></div></form>':'')+(d.tickets.length?d.tickets.map(t=>'<div class="cx-line" style="cursor:pointer" data-cx-action="ticket-open" data-ticket="'+safe(t.id)+'"><span>'+safe(t.subject)+' <span class="cx-line-sub">· '+safe(t.reference)+'</span></span><span class="cx-line-sub" style="display:inline-flex;align-items:center;gap:6px;white-space:nowrap"><span class="sx-dot '+supportStatusClass(t.status)+'"></span>'+safe(statusLabel(t.status))+' ›</span></div>').join(''):cxForm==='ticket'?'':'<p class="cx-empty">Geen tickets.</p>')+'</div>';
h+='<div class="cx-sec"><div class="cx-sec-head"><span class="cx-sec-title">NOTITIES</span><span class="cx-line-sub" id="cxNotesState"></span></div><textarea class="cx-notes" id="cxNotes" maxlength="2000" placeholder="'+(manage?'Alleen zichtbaar voor medewerkers':'Geen notities')+'"'+(manage?'':' readonly')+'>'+safe(c.notes||'')+'</textarea></div>';
box.innerHTML=h;cxLicAfter();const typeSel=$('cxIssueType');if(typeSel){const upd=()=>$('cxIssueUntilBox').style.visibility=typeSel.value==='admin'?'hidden':'visible';typeSel.onchange=upd;upd();$('cxIssueLabel').focus()}if($('cxInviteName'))$('cxInviteName').focus();if($('cxTicketSubject'))$('cxTicketSubject').focus();if($('cxDeleteName'))$('cxDeleteName').focus();if(cxMode==='edit'&&$('cx_name'))$('cx_name').focus();const menuBox=box.querySelector('.cx-menu button');if(menuBox&&cxMenu)menuBox.focus()}
function cxFormError(id,msg){const el=$(id);if(el)el.textContent=msg}
async function cxRun(button,fn){if(button)button.disabled=true;try{await fn()}finally{if(button&&button.isConnected)button.disabled=false}}
$('customerSearch').oninput=renderCustomerList;
$('customers').onclick=e=>{const b=e.target.closest('[data-customer]');if(b&&(b.dataset.customer!==cxSelected||cxMode==='create'))openCustomer(b.dataset.customer)};
$('addCustomer').onclick=()=>{cxMode='create';cxForm='';cxMenu='';cxSelected='';cxDetail=null;renderCustomerList();renderCustomerDetail()};
$('customerFilterButton').onclick=e=>{e.stopPropagation();const m=$('customerFilterMenu'),open=m.classList.contains('hidden');m.classList.toggle('hidden',!open);e.currentTarget.setAttribute('aria-expanded',String(open));if(open){m.innerHTML=[['active','Actief'],['paused','Gepauzeerd'],['all','Alle klanten']].map(([k,l])=>'<button type="button" role="menuitemradio" aria-checked="'+(k===cxFilter)+'" data-filter="'+k+'"><span style="flex:1">'+l+'</span><span class="cx-sub">'+customers.filter(c=>cxMatches(c,k)).length+'</span>'+(k===cxFilter?' ✓':'')+'</button>').join('');m.querySelector('[aria-checked="true"]').focus()}};
$('customerFilterMenu').onclick=e=>{const b=e.target.closest('[data-filter]');if(!b)return;cxFilter=b.dataset.filter;$('customerFilterMenu').classList.add('hidden');$('customerFilterButton').setAttribute('aria-expanded','false');renderCustomerList();if(!cxFiltered().some(c=>c.id===cxSelected)){const first=cxFiltered()[0];if(first)openCustomer(first.id)}};
document.addEventListener('click',e=>{if(!e.target.closest('#customerFilterMenu,#customerFilterButton'))$('customerFilterMenu').classList.add('hidden');if(cxMenu&&!e.target.closest('#customerDetail .cx-pop')){cxMenu='';if(cxDetail)renderCustomerDetail()}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&cxMenu){cxMenu='';renderCustomerDetail()}});
$('customerDetail').onclick=async e=>{const t=e.target.closest('[data-cx-action]');if(!t)return;const a=t.dataset.cxAction,c=cxDetail&&cxDetail.customer;
if(a.startsWith('lc-'))return cxLicAction(a,t,e);
if(a==='menu'){e.stopPropagation();cxMenu=cxMenu==='header'?'':'header';return renderCustomerDetail()}
if(a==='user-menu'){e.stopPropagation();cxMenu=cxMenu==='user:'+t.dataset.user?'':'user:'+t.dataset.user;return renderCustomerDetail()}
cxMenu='';
if(a==='toggle-details'){cxDetailsOpen=!cxDetailsOpen;try{localStorage.setItem('cohentra-customer-details-open',cxDetailsOpen?'1':'0')}catch{}return renderCustomerDetail()}
if(a==='edit'){cxMode='edit';cxForm='';return renderCustomerDetail()}
if(a==='cancel-mode'){if(cxMode==='create'){cxMode='';const first=cxFiltered()[0];if(first)return openCustomer(first.id);return renderCustomerDetail()}cxMode='';return renderCustomerDetail()}
if(a==='cancel-form'){cxForm='';return renderCustomerDetail()}
if(['pause-ask','invite','ticket-new','link','delete-ask'].includes(a)){cxForm={'pause-ask':'pause','delete-ask':'delete','ticket-new':'ticket'}[a]||a;cxNewKey=null;renderCustomerDetail();const target=$('customerDetail').querySelector('[data-cx-form="'+cxForm+'"],.cx-warn');if(target)target.scrollIntoView({block:'nearest',behavior:'smooth'});return}
if(a==='product-settings'){cxForm=cxForm==='product:'+t.dataset.product?'':'product:'+t.dataset.product;return renderCustomerDetail()}
if(a==='open-customer')return openCustomer(t.dataset.id);
if(a==='copy-key'){try{await navigator.clipboard.writeText(cxNewKey.key);t.textContent='Gekopieerd'}catch{const r=document.createRange();r.selectNodeContents($('cxNewKey'));const s=getSelection();s.removeAllRanges();s.addRange(r);t.textContent='Geselecteerd, druk op Ctrl+C'}return}
if(a==='ticket-open'){const id=t.dataset.ticket;supportFilter='all';setView('support');await loadSupportTickets();return openSupportTicket(id)}
if(a==='pause-confirm'||a==='resume')return cxRun(t,async()=>{try{await api('/api/admin/customers/'+encodeURIComponent(c.id)+'/'+(a==='resume'?'resume':'pause'),{method:'POST',body:'{}'});cxForm='';cxToast(a==='resume'?c.name+' is hervat.':c.name+' is gepauzeerd.');await loadCustomers({reloadDetail:true});loadLicenses().catch(()=>{})}catch(err){cxToast(err.message,true)}});
if(a.startsWith('user-')){const user=cxDetail.users.find(u=>u.id===t.dataset.user);if(!user)return;const act=a.slice(5);return cxRun(t,async()=>{try{const d=await api('/api/admin/portal-users/'+encodeURIComponent(user.id)+'/'+act,{method:'POST',body:'{}'});cxToast(act==='resend'?(d.purpose==='invite'?'Nieuwe uitnodiging':'Wachtwoordlink')+' verstuurd naar '+d.email+'.':act==='disable'?'Toegang van '+(user.name||user.email)+' is uitgeschakeld.':(user.name||user.email)+' kan weer inloggen.');await loadCustomers({reloadDetail:true})}catch(err){cxToast(err.message,true);renderCustomerDetail()}})}};
$('customerDetail').onsubmit=async e=>{const f=e.target.closest('[data-cx-form]');if(!f)return;e.preventDefault();const kind=f.dataset.cxForm,c=cxDetail&&cxDetail.customer,button=f.querySelector('button:not([type=button])');
if(kind.startsWith('lc-'))return cxLicSubmit(kind,f,button);
if(kind==='details'){const keys=['name','contact_name','contact_role','contact_email','phone','kvk_number','vat_number','website','invoice_email','street','postal_code','city','country'],body={};keys.forEach(k=>body[k]=$('cx_'+k).value.trim());if(!body.name)return cxFormError('cxDetailsError','Vul een bedrijfsnaam in.');if(body.kvk_number&&!/^\d{8}$/.test(body.kvk_number.replace(/\s+/g,'')))return cxFormError('cxDetailsError','Een KvK-nummer bestaat uit 8 cijfers.');
return cxRun(button,async()=>{try{if(cxMode==='create'){const d=await api('/api/admin/customers',{method:'POST',body:JSON.stringify(body)});cxMode='';cxSelected=d.customer.id;cxToast(body.name+' is aangemaakt.');await loadCustomers({reloadDetail:true})}else{await api('/api/admin/customers/'+encodeURIComponent(c.id),{method:'PATCH',body:JSON.stringify(body)});cxMode='';cxToast('Klantgegevens opgeslagen.');await loadCustomers({reloadDetail:true})}}catch(err){cxFormError('cxDetailsError',err.message)}})}
if(kind==='product'){const isNew=!f.dataset.product,product=isNew?$('cxProductId').value:f.dataset.product,max=Number($('cxProductMax').value),types=[];if($('cxTypeBeta').checked)types.push('beta');if($('cxTypeAdmin').checked)types.push('admin');if(!Number.isInteger(max)||max<0)return cxFormError('cxProductError','Vul een geldig aantal licenties in.');if(!types.length)return cxFormError('cxProductError','Kies minimaal één licentietype.');const enabled=isNew?true:$('cxProductEnabled').checked;
return cxRun(button,async()=>{try{await api('/api/admin/customers/'+encodeURIComponent(c.id)+'/products/'+encodeURIComponent(product),{method:'PUT',body:JSON.stringify({max_licenses:max,allowed_license_types:types,enabled})});cxForm='';cxToast(isNew?'Product gekoppeld.':'Productinstellingen opgeslagen.');await loadCustomers({reloadDetail:true})}catch(err){cxFormError('cxProductError',err.message)}})}
if(kind==='invite'){const name=$('cxInviteName').value.trim(),email=$('cxInviteEmail').value.trim().toLowerCase();if(!name)return cxFormError('cxInviteError','Vul een naam in.');if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))return cxFormError('cxInviteError','Vul een geldig e-mailadres in.');
return cxRun(button,async()=>{try{await api('/api/admin/customers/'+encodeURIComponent(c.id)+'/portal-users',{method:'POST',body:JSON.stringify({name,email})});cxForm='';cxToast('Uitnodiging verstuurd naar '+email+'.');await loadCustomers({reloadDetail:true})}catch(err){cxFormError('cxInviteError',err.message);if(/aangemaakt/.test(err.message)){cxForm='';await loadCustomers({reloadDetail:true});cxToast(err.message,true)}}})}
if(kind==='ticket'){const subject=$('cxTicketSubject').value.trim(),message=$('cxTicketMessage').value.trim();if(!subject||!message)return cxFormError('cxTicketError','Vul een onderwerp en omschrijving in.');
return cxRun(button,async()=>{try{const d=await api('/api/support/tickets',{method:'POST',body:JSON.stringify({customer_id:c.id,subject,message})});cxForm='';await loadCustomers({reloadDetail:true});loadSupportTickets().catch(()=>{});cxToast('Ticket '+d.reference+' aangemaakt.')}catch(err){cxFormError('cxTicketError',err.message)}})}
if(kind==='delete'){const typed=$('cxDeleteName').value.trim();if(typed!==c.name)return cxFormError('cxDeleteError','De naam klopt niet. Typ hem precies over.');
return cxRun(button,async()=>{try{await api('/api/admin/customers/'+encodeURIComponent(c.id),{method:'DELETE',body:JSON.stringify({confirm_name:typed})});cxForm='';cxSelected='';cxDetail=null;cxToast(c.name+' is verwijderd.');await loadCustomers();loadLicenses().catch(()=>{});loadSupportTickets().catch(()=>{})}catch(err){cxFormError('cxDeleteError',err.message)}})}};
$('customerDetail').oninput=e=>{if(e.target.id==='cxNotes'){const c=cxDetail.customer,value=e.target.value;$('cxNotesState').textContent='Opslaan…';clearTimeout(cxNotesTimer);cxNotesTimer=setTimeout(async()=>{try{await api('/api/admin/customers/'+encodeURIComponent(c.id)+'/notes',{method:'PUT',body:JSON.stringify({notes:value})});c.notes=value;if($('cxNotesState'))$('cxNotesState').textContent='Opgeslagen'}catch(err){if($('cxNotesState'))$('cxNotesState').textContent=err.message}},800);return}const err=e.target.closest('form')&&e.target.closest('form').querySelector('.cx-error');if(err)err.textContent=''};
var supportMeId=null,currentSupportTicketId='',supportFilter='open',supportAfterStatus='waiting_customer',supportDetail=null;const supportDrafts=new Map(),supportSending=new Set(),supportErrors=new Map();let supportComposerTicketId='',supportLoadSequence=0;const supportStatuses=[['new','Nieuw'],['in_progress','In behandeling','Stuurt de klant een korte bevestiging'],['waiting_customer','Wacht op klant'],['closed','Afgerond']];
function saveSupportDraft(){if(!supportComposerTicketId)return;supportDrafts.set(supportComposerTicketId,{message:$('supportReplyMessage').value,internal:$('supportNoteToggle').checked,status:supportAfterStatus});persistSupportDrafts()}
function persistSupportDrafts(){try{sessionStorage.setItem('cohentra-support-drafts',JSON.stringify({session:token,drafts:[...supportDrafts].filter(([,d])=>d.message)}))}catch{}}
function restoreSupportDrafts(){supportDrafts.clear();supportErrors.clear();supportComposerTicketId='';currentSupportTicketId='';supportDetail=null;try{const saved=JSON.parse(sessionStorage.getItem('cohentra-support-drafts')||'null');if(saved&&saved.session===token&&Array.isArray(saved.drafts)){for(const [id,d] of saved.drafts){if(typeof id==='string'&&d&&typeof d.message==='string')supportDrafts.set(id,d)}}}catch{}persistSupportDrafts()}
function paintSupportSending(){const busy=supportSending.has(currentSupportTicketId);$('supportReplyButton').disabled=busy;$('supportConfirmSend').disabled=busy}
function statusLabel(status){const s=supportStatuses.find(x=>x[0]===status);return s?s[1]:status}function sourceLabel(t){return t.created_by_staff_name?'Medewerker':t.source==='website'?'Website':'Portaal'}function supportStatusClass(status){return 'sx-s-'+String(status||'new').replace(/[^a-z_]/g,'')}
function supportAwaiting(t){return t.status==='new'||(t.status!=='closed'&&Number(t.customer_spoke_last)===1)}function supportMatches(t,f){if(f==='all')return true;if(f==='open')return t.status!=='closed';if(f==='mine')return Boolean(supportMeId)&&t.assigned_to===supportMeId&&t.status!=='closed';return t.status===f}function supportCount(f){return supportTicketRows.filter(t=>supportMatches(t,f)).length}
function supportFilterItems(){return [['open','Open'],...(supportMeId?[['mine','Mijn tickets']]:[]),'-',...supportStatuses.map(s=>[s[0],s[1]]),'-',['all','Alles']]}
function filteredSupportTickets(){const q=$('supportSearch').value.trim().toLocaleLowerCase('nl-NL');return supportTicketRows.filter(t=>supportMatches(t,supportFilter)&&(!q||[t.reference,t.subject,t.customer_name,t.organization,t.customer_org,t.contact_email,t.message].some(v=>String(v||'').toLocaleLowerCase('nl-NL').includes(q)))).sort((a,b)=>String(b.updated_at||b.created_at).localeCompare(String(a.updated_at||a.created_at)))}
function supportSameDay(a,b){return a.toDateString()===b.toDateString()}function supportWhen(value){const d=new Date(value),now=new Date(),y=new Date();y.setDate(now.getDate()-1);if(isNaN(d))return '';if(supportSameDay(d,now))return d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});if(supportSameDay(d,y))return 'gisteren';return d.toLocaleDateString('nl-NL',d.getFullYear()===now.getFullYear()?{day:'numeric',month:'short'}:{day:'numeric',month:'short',year:'numeric'})}
function supportDay(d){const now=new Date(),y=new Date();y.setDate(now.getDate()-1);if(supportSameDay(d,now))return 'Vandaag';if(supportSameDay(d,y))return 'Gisteren';return d.toLocaleDateString('nl-NL',d.getFullYear()===now.getFullYear()?{weekday:'long',day:'numeric',month:'long'}:{day:'numeric',month:'long',year:'numeric'})}
function supportWaitDays(t){if(!supportAwaiting(t))return 0;return Math.floor((Date.now()-new Date(t.updated_at||t.created_at).getTime())/864e5)}
function closeSupportMenus(){document.querySelectorAll('#view-support .sx-menu').forEach(m=>m.classList.add('hidden'));document.querySelectorAll('#view-support [data-sx-menu-toggle]').forEach(b=>b.setAttribute('aria-expanded','false'))}
function openSupportMenu(menuId,button,items,selected,onPick,options={}){const menu=$(menuId),wasOpen=!menu.classList.contains('hidden');closeSupportMenus();if(wasOpen)return;menu.innerHTML=(options.title?'<div class="sx-menu-title">'+safe(options.title)+'</div>':'')+items.map(item=>{if(item==='-')return '<div class="sx-sep" role="separator"></div>';const value=item[0],label=item[1],hint=item[2],isStatus=supportStatuses.some(s=>s[0]===value);return '<button type="button" role="menuitemradio" aria-checked="'+(value===selected)+'" data-value="'+safe(value)+'">'+(isStatus?'<span class="sx-dot '+supportStatusClass(value)+'"></span>':'<span class="sx-menu-icon"></span>')+'<span class="sx-menu-label">'+safe(label)+(hint&&options.hints?'<small>'+safe(hint)+'</small>':'')+'</span>'+(options.counts?'<span class="sx-count">'+options.counts(value)+'</span>':'')+(value===selected?'<span class="sx-menu-check" aria-hidden="true">✓</span>':'')+'</button>'}).join('');menu.onclick=e=>{const b=e.target.closest('[data-value]');if(!b)return;e.stopPropagation();closeSupportMenus();button.focus();onPick(b.dataset.value)};menu.classList.remove('hidden');button.setAttribute('aria-expanded','true');const focus=menu.querySelector('[aria-checked="true"]')||menu.querySelector('button');if(focus)focus.focus()}
document.addEventListener('click',e=>{if(!e.target.closest('#view-support .sx-menu,#view-support [data-sx-menu-toggle]'))closeSupportMenus()});document.addEventListener('keydown',e=>{const menu=e.target.closest&&e.target.closest('#view-support .sx-menu');if(e.key==='Escape')closeSupportMenus();if(menu&&(e.key==='ArrowDown'||e.key==='ArrowUp')){e.preventDefault();const items=[...menu.querySelectorAll('button')],i=items.indexOf(e.target);items[(i+(e.key==='ArrowDown'?1:-1)+items.length)%items.length].focus()}});
function renderSupportTickets(){const body=$('supportTickets'),rows=filteredSupportTickets(),item=supportFilterItems().find(x=>x!=='-'&&x[0]===supportFilter)||['open','Open'],waiting=supportTicketRows.filter(supportAwaiting).length;$('supportFilterLabel').textContent=item[1];$('supportTicketCount').textContent=supportCount(supportFilter);$('supportNavBadge').textContent=waiting;$('supportNavBadge').classList.toggle('hidden',!waiting);
body.innerHTML=rows.length?rows.map(t=>{const late=supportWaitDays(t),when=t.updated_at||t.created_at,org=t.organization||(t.customer_org&&t.customer_org!==t.customer_name?t.customer_org:'');return '<button type="button" class="sx-row'+(t.id===currentSupportTicketId?' selected':'')+'" data-open-ticket="'+safe(t.id)+'"'+(t.id===currentSupportTicketId?' aria-current="true"':'')+'><span class="sx-row-top"><span class="sx-row-name">'+(supportAwaiting(t)?'<span class="sx-unread" title="Wacht op een reactie van jullie"></span>':'')+safe(t.customer_name||'Onbekende klant')+'</span><span class="sx-row-when'+(late>=2?' late':'')+'" title="Laatste activiteit '+safe(new Date(when).toLocaleString('nl-NL'))+'">'+(late>=2?late+' dagen':safe(supportWhen(when)))+'</span></span><span class="sx-row-subject">'+safe(t.subject||'Zonder onderwerp')+'</span><span class="sx-row-foot"><span class="sx-dot '+supportStatusClass(t.status)+'"></span>'+safe(statusLabel(t.status))+' · '+safe(sourceLabel(t))+(org?' · '+safe(org):'')+'</span></button>'}).join(''):'<div class="sx-empty">Geen tickets in deze weergave.</div>';
if(currentSupportTicketId&&!rows.some(t=>t.id===currentSupportTicketId)){saveSupportDraft();currentSupportTicketId=''}if(!currentSupportTicketId){if(rows.length)openSupportTicket(rows[0].id);else resetSupportDetail()}}
function resetSupportDetail(){saveSupportDraft();supportComposerTicketId='';supportDetail=null;$('supportDetailTitle').textContent='Selecteer een ticket';$('supportDetailMeta').textContent='Kies links een ticket om het gesprek te openen.';$('supportDetailFacts').innerHTML='';$('supportStatusButton').classList.add('hidden');$('supportConversation').innerHTML='<div class="sx-empty">Selecteer links een ticket om het gesprek te bekijken.</div>';$('supportReplyForm').classList.add('hidden');$('supportDetailError').textContent=''}
function paintSupportStatus(status){const b=$('supportStatusButton'),editable=can('support.status');b.className='sx-pill sx-status '+supportStatusClass(status);$('supportStatusLabel').textContent=statusLabel(status);b.toggleAttribute('data-readonly',!editable);b.title=editable?'Status wijzigen':'Je hebt geen rechten om de status te wijzigen';b.querySelector('.sx-caret').classList.toggle('hidden',!editable)}
function paintSupportAfter(){$('supportAfterText').innerHTML='daarna <span class="sx-dot '+supportStatusClass(supportAfterStatus)+'"></span>'+safe(statusLabel(supportAfterStatus).toLocaleLowerCase('nl-NL'))}
function supportCanEmail(){return Boolean(supportDetail&&/^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(String(supportDetail.contact_email||'')))}
function setSupportNoteMode(on){const email=supportCanEmail();if(!email)on=true;$('supportNoteToggle').checked=on;$('supportNoteToggle').disabled=!email;$('supportReplyForm').classList.toggle('note',on);$('supportReplyTo').textContent=on?(email?'Alleen zichtbaar voor medewerkers':'Geen geldig e-mailadres bekend · alleen interne notities'):'✉ Aan '+supportDetail.contact_email;$('supportReplyMessage').placeholder=on?'Notitie voor collega’s…':'Schrijf je antwoord…';$('supportReplyButton').textContent=on?'Notitie opslaan':'Versturen';hideSupportConfirm()}
function hideSupportConfirm(){$('supportConfirm').classList.add('hidden');$('supportReplyActions').classList.remove('hidden')}
function resetSupportComposer(){const form=$('supportReplyForm'),draft=supportDrafts.get(currentSupportTicketId);supportComposerTicketId=currentSupportTicketId;$('supportReplyMessage').value=draft?.message||'';$('supportReplyEmpty').classList.add('hidden');supportAfterStatus=draft?.status||'waiting_customer';paintSupportAfter();form.classList.toggle('no-status',!can('support.status'));setSupportNoteMode(Boolean(draft?.internal));paintSupportSending()}
async function openSupportTicket(id,opts={}){const changed=id!==currentSupportTicketId||!supportDetail;if(changed)saveSupportDraft();currentSupportTicketId=id;renderSupportTickets();if(currentSupportTicketId!==id)return;const row=supportTicketRows.find(t=>t.id===id);if(changed){supportDetail=row?{...row}:{id,status:'new'};$('supportDetailError').textContent='';$('supportDetailTitle').textContent=row?.subject||'Supportticket';$('supportDetailMeta').textContent=row?row.reference:'';$('supportDetailFacts').innerHTML='';$('supportConversation').innerHTML='<div class="sx-empty">Gesprek laden…</div>'}paintSupportStatus(supportDetail.status);$('supportReplyForm').classList.toggle('hidden',!can('support.reply'));if(changed||!opts.keepComposer)resetSupportComposer();paintSupportSending();$('supportDetailError').textContent=supportErrors.get(id)||'';try{const d=await api('/api/support/tickets/'+encodeURIComponent(id));if(currentSupportTicketId!==id)return;const hadEmail=supportCanEmail();supportDetail=d.ticket;renderSupportDetail(d.ticket,d.replies||[]);if(!opts.keepComposer||hadEmail!==supportCanEmail())setSupportNoteMode($('supportNoteToggle').checked)}catch(err){if(currentSupportTicketId===id)$('supportConversation').innerHTML='<div class="sx-empty error">'+safe(err.message)+'</div>'}}
function renderSupportDetail(t,replies){$('supportDetailTitle').textContent=t.subject||'Supportticket';$('supportDetailMeta').textContent=t.reference+' · geopend '+new Date(t.created_at).toLocaleDateString('nl-NL',{day:'numeric',month:'short',year:'numeric'});paintSupportStatus(t.status);const facts=[],org=t.organization||(t.customer_org&&t.customer_org!==t.customer_name?t.customer_org:'');facts.push('<span>'+safe(t.customer_name||'Onbekende klant')+'</span>');if(org)facts.push('<span>'+(can('customers.view')&&t.source!=='website'?'<button type="button" class="sx-link" data-go-customers>'+safe(org)+'</button>':safe(org))+'</span>');facts.push(t.contact_email?'<span><a href="mailto:'+encodeURIComponent(t.contact_email)+'">'+safe(t.contact_email)+'</a></span>':'<span>Geen e-mailadres</span>');if(t.source!=='website'&&t.active_licenses!==undefined&&t.active_licenses!==null)facts.push('<span>'+Number(t.active_licenses)+' '+(Number(t.active_licenses)===1?'actieve licentie':'actieve licenties')+'</span>');if(t.assigned_name)facts.push('<span>Opgepakt door '+safe(t.assigned_name)+'</span>');facts.push('<span>Via '+safe(sourceLabel(t).toLocaleLowerCase('nl-NL'))+'</span>');$('supportDetailFacts').innerHTML=facts.join('');renderSupportReplies(t,replies)}
function renderSupportReplies(ticket,replies){const items=[{author_name:ticket.customer_name||'Klant',message:ticket.message,created_at:ticket.created_at,delivery_status:'received',first:true},...replies];let day='';const box=$('supportConversation');box.innerHTML=items.map(item=>{const d=new Date(item.created_at),inbound=item.delivery_status==='received',note=Number(item.is_internal)===1;let html='';if(d.toDateString()!==day){day=d.toDateString();html+='<div class="sx-day">'+safe(supportDay(d))+'</div>'}const time=d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'}),who=note?'Interne notitie · '+(item.author_name||'Medewerker'):inbound?(item.author_name||'Klant')+(item.first?(ticket.source==='website'?' · via website':' · via portaal'):' · per e-mail'):(item.author_name||'Cohentra Support'),state=note||inbound?'':item.delivery_status==='sent'?' · ✓ verstuurd':item.delivery_status==='failed'?' · <span class="sx-failed">niet verstuurd</span>':' · wordt verstuurd',author=item.author_name||'Medewerker',avatar=item.author_staff_id?'<span class="sx-msg-author"><span class="sx-agent-avatar" data-avatar-id="'+safe(item.author_staff_id)+'" data-name="'+safe(author)+'" role="img" tabindex="0" aria-label="Behandeld door '+safe(author)+'"><span>'+safe(cxInitials(author))+'</span><img alt="" hidden></span><span>'+safe(who)+'</span></span>':safe(who);return html+'<article class="sx-msg'+(!inbound&&!note?' out':'')+(note?' note':'')+(item.delivery_status==='failed'?' failed':'')+'"><p class="sx-msg-meta">'+avatar+' · '+safe(time)+state+'</p><div class="sx-bubble">'+safe(item.message)+'</div></article>'}).join('');box.scrollTop=box.scrollHeight;renderSupportAvatars()}
async function loadSupportTickets(){const body=$('supportTickets'),sequence=++supportLoadSequence,session=token;try{let cursor='',rows=[];const seen=new Set();do{const d=await api('/api/support/tickets'+(cursor?'?cursor='+encodeURIComponent(cursor):''));rows.push(...(d.tickets||[]));cursor=d.next_cursor||'';if(cursor&&seen.has(cursor))throw Error('De ticketlijst kon niet volledig worden opgehaald. Probeer opnieuw.');seen.add(cursor)}while(cursor);if(sequence!==supportLoadSequence||token!==session)return;supportTicketRows=[...new Map(rows.map(t=>[t.id,t])).values()];renderSupportTickets();updateOverview();$('supportTicketError').textContent=''}catch(e){if(sequence!==supportLoadSequence||token!==session)return;$('supportTicketError').textContent=e.message;if(!supportTicketRows.length)body.innerHTML=''}}
function renderSupportMailIssues(issues){const box=$('supportMailIssues');box.classList.toggle('hidden',!issues.length);box.innerHTML=issues.length?'<strong>Controleer grote e-mails in de STRATO-mailbox</strong><p>Deze berichten zijn groter dan 8 MB en niet in tickets overgenomen. Andere reacties zijn wel verwerkt.</p>'+issues.map(issue=>'<div>'+safe(issue.subject)+(can('support.reply')?' <button type="button" class="secondary" data-mail-issue="'+safe(issue.id)+'">Gecontroleerd</button>':'')+'</div>').join(''):''}
$('supportMailIssues').onclick=async e=>{const button=e.target.closest('[data-mail-issue]');if(!button)return;button.disabled=true;try{await api('/api/support/inbox/issues/'+encodeURIComponent(button.dataset.mailIssue)+'/resolve',{method:'POST',body:'{}'});await refreshSupportInbox()}catch(error){$('supportSyncStatus').textContent=error.message}finally{button.disabled=false}};
async function refreshSupportInbox(){const button=$('syncSupportInbox');if(button.dataset.busy)return;button.dataset.busy='1';button.classList.add('spinning');$('supportSyncStatus').textContent='Mailbox ophalen…';try{let linked=0,more=true,rounds=0;while(more&&rounds<3){const d=await api('/api/support/inbox/sync',{method:'POST',body:'{}'});linked+=d.linked||0;renderSupportMailIssues(d.issues||[]);more=Boolean(d.more);rounds+=1}const time=new Date().toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});$('supportSyncStatus').textContent=(linked?linked+(linked===1?' nieuwe reactie':' nieuwe reacties')+' opgehaald om ':'✓ Mailbox bijgewerkt om ')+time+(more?' · er staan nog berichten klaar':'');await loadSupportTickets();if(currentSupportTicketId)await openSupportTicket(currentSupportTicketId,{keepComposer:true})}catch(e){$('supportSyncStatus').textContent=e.message;await loadSupportTickets()}finally{delete button.dataset.busy;button.classList.remove('spinning')}}
async function changeSupportStatus(status){if(!supportDetail||status===supportDetail.status)return;const id=supportDetail.id,previous=supportDetail.status;supportDetail.status=status;paintSupportStatus(status);$('supportDetailError').textContent='';try{const d=await api('/api/support/tickets/'+encodeURIComponent(id),{method:'PATCH',body:JSON.stringify({status})});if(d.status_notice==='failed')$('supportDetailError').textContent='Status opgeslagen, maar de bevestiging aan de klant kon niet worden verstuurd.';await loadSupportTickets();if(currentSupportTicketId===id)await openSupportTicket(id,{keepComposer:true})}catch(err){if(supportDetail&&supportDetail.id===id){supportDetail.status=previous;paintSupportStatus(previous)}$('supportDetailError').textContent=err.message}}
async function sendSupportReply(payload){
const id=currentSupportTicketId,session=token;if(!id||supportSending.has(id))return;
saveSupportDraft();const submitted={...supportDrafts.get(id)};supportSending.add(id);supportErrors.delete(id);paintSupportSending();$('supportDetailError').textContent='';
try{await api('/api/support/tickets/'+encodeURIComponent(id)+'/replies',{method:'POST',body:JSON.stringify(payload)});
if(token!==session)return;if(supportComposerTicketId===id)saveSupportDraft();
const current=supportDrafts.get(id);if(current&&current.message===submitted.message&&current.internal===submitted.internal&&current.status===submitted.status){supportDrafts.delete(id);if(supportComposerTicketId===id)$('supportReplyMessage').value='';persistSupportDrafts()}
}catch(err){if(token===session){supportErrors.set(id,err.message);if(currentSupportTicketId===id)$('supportDetailError').textContent=err.message}}
finally{supportSending.delete(id);if(token===session){paintSupportSending();if(currentSupportTicketId===id)hideSupportConfirm();await loadSupportTickets();if(currentSupportTicketId===id)await openSupportTicket(id,{keepComposer:true})}}
}
$('supportSearch').oninput=renderSupportTickets;$('syncSupportInbox').onclick=refreshSupportInbox;$('supportTickets').onclick=e=>{const b=e.target.closest('[data-open-ticket]');if(b&&b.dataset.openTicket!==currentSupportTicketId)openSupportTicket(b.dataset.openTicket)};$('supportDetailFacts').onclick=e=>{if(e.target.closest('[data-go-customers]')&&supportDetail?.customer_id&&can('customers.view')){const id=supportDetail.customer_id;cxFilter='all';$('customerSearch').value='';setView('customers');openCustomer(id)}};
$('supportFilterButton').onclick=e=>openSupportMenu('supportFilterMenu',e.currentTarget,supportFilterItems(),supportFilter,v=>{supportFilter=v;renderSupportTickets()},{counts:supportCount});
$('supportStatusButton').onclick=e=>{if(!supportDetail||!can('support.status'))return;openSupportMenu('supportStatusMenu',e.currentTarget,supportStatuses,supportDetail.status,changeSupportStatus,{hints:true})};
$('supportAfterButton').onclick=e=>openSupportMenu('supportAfterMenu',e.currentTarget,supportStatuses,supportAfterStatus,v=>{supportAfterStatus=v;paintSupportAfter();saveSupportDraft()},{title:'Status na versturen'});
$('supportNoteToggle').onchange=e=>{setSupportNoteMode(e.target.checked);saveSupportDraft()};$('supportReplyMessage').oninput=()=>{$('supportReplyEmpty').classList.add('hidden');saveSupportDraft()};$('supportReplyMessage').onkeydown=e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();$('supportReplyForm').requestSubmit()}};
$('supportReplyForm').onsubmit=e=>{e.preventDefault();if(!currentSupportTicketId||!supportDetail||supportSending.has(currentSupportTicketId))return;const message=$('supportReplyMessage').value.trim();if(!message){$('supportReplyEmpty').classList.remove('hidden');$('supportReplyMessage').focus();return}if($('supportNoteToggle').checked){sendSupportReply({message,internal:true});return}$('supportConfirmText').innerHTML='Je verstuurt dit als e-mail naar <strong>'+safe(supportDetail.contact_email)+'</strong>.'+(can('support.status')?' Daarna staat het ticket op <strong>'+safe(statusLabel(supportAfterStatus).toLocaleLowerCase('nl-NL'))+'</strong>.':'')+' Een verstuurde mail kun je niet terughalen.';$('supportReplyActions').classList.add('hidden');$('supportConfirm').classList.remove('hidden');$('supportConfirmSend').focus()};
$('supportConfirmCancel').onclick=()=>{hideSupportConfirm();$('supportReplyMessage').focus()};$('supportConfirmSend').onclick=()=>{const message=$('supportReplyMessage').value.trim();if(!message){hideSupportConfirm();return}sendSupportReply(can('support.status')?{message,status:supportAfterStatus}:{message})};
setInterval(()=>{if(!document.hidden&&!$('view-support').classList.contains('hidden')&&Date.now()-staffLastActivity<2*60*1000)refreshSupportInbox().catch(e=>$('supportSyncStatus').textContent=e.message)},60000);
const permissionOptions=[['support.view','Support bekijken'],['support.reply','Antwoorden versturen'],['support.status','Ticketstatus wijzigen'],['customers.view','Klanten bekijken'],['customers.manage','Klanten beheren'],['licenses.view','Licenties bekijken'],['licenses.issue','Licenties uitgeven'],['licenses.manage','Licenties beheren'],['sales.view','Sales bekijken'],['sales.manage','Sales beheren'],['email.templates.manage','E-mailtemplates beheren'],['shop.view','Shop bekijken'],['shop.manage','Producten en prijzen beheren'],['billing.view','Betalingen en abonnementen bekijken'],['billing.manage','Licentie-uitzonderingen en abonnementen beheren']];
let emailTemplateData={},emailTemplateMeta={};
const emailTemplateLabels={reply_heading:'Kop bij een supportreactie',reply_closing:'Afsluiting bij een supportreactie',status_heading:'Kop bij statusupdate',status_body:'Melding bij statusupdate',status_closing:'Afsluiting bij statusupdate',new_heading:'Kop in nieuwe aanvraag aan support',new_button:'Knoptekst',invite_subject:'Onderwerp uitnodiging',invite_intro:'Uitleg uitnodiging',invite_button:'Knoptekst uitnodiging',reset_subject:'Onderwerp wachtwoordherstel',reset_intro:'Uitleg wachtwoordherstel',reset_button:'Knoptekst wachtwoordherstel',expiry_note:'Toelichting geldigheid link',accent:'Accentkleur'};
const emailTemplateMax={reply_heading:120,reply_closing:500,status_heading:120,status_body:500,status_closing:500,new_heading:160,new_button:80,invite_subject:160,invite_intro:600,invite_button:80,reset_subject:160,reset_intro:600,reset_button:80,expiry_note:600,accent:7};
function selectedEmailTemplate(){return $('emailTemplateKind').value}
function readEmailTemplateFields(){const key=selectedEmailTemplate(),settings={};$('emailTemplateFields').querySelectorAll('[data-email-template-field]').forEach(input=>settings[input.dataset.emailTemplateField]=input.value);return settings}
function renderEmailTemplateFields(){const key=selectedEmailTemplate(),settings=emailTemplateData[key]||{},variants=key==='support'?[['reply','Supportreactie'],['status','Statusupdate'],['new','Nieuwe supportaanvraag']]:key==='auth'?[['invite','Accountuitnodiging'],['reset','Wachtwoordherstel']]:[];$('emailTemplateVariant').innerHTML=variants.map(([value,label])=>'<option value="'+value+'">'+label+'</option>').join('');$('emailTemplateVariant').classList.toggle('hidden',!variants.length);$('emailTemplateFields').innerHTML=Object.entries(settings).map(([field,value])=>{const color=field==='accent',long=['reply_closing','status_body','status_closing','invite_intro','reset_intro','expiry_note'].includes(field),type=color?'color':'text',control=long?'<textarea id="emailTemplate_'+safe(field)+'" data-email-template-field="'+safe(field)+'" maxlength="'+emailTemplateMax[field]+'">'+safe(value)+'</textarea>':'<input id="emailTemplate_'+safe(field)+'" type="'+type+'" data-email-template-field="'+safe(field)+'" maxlength="'+emailTemplateMax[field]+'" value="'+safe(value)+'">';return '<label for="emailTemplate_'+safe(field)+'">'+safe(emailTemplateLabels[field]||field)+'</label>'+control}).join('');const meta=emailTemplateMeta[key];$('emailTemplateMeta').textContent=meta?.updated_at?'Laatst opgeslagen '+new Date(meta.updated_at).toLocaleString('nl-NL')+(meta.updated_by?' door '+meta.updated_by:''):'Nog geen aangepaste instellingen opgeslagen.';$('emailTemplateError').textContent='';$('emailTemplateMessage').classList.add('hidden')}
async function previewEmailTemplate(){const button=$('previewEmailTemplate');button.disabled=true;$('emailTemplateError').textContent='';try{const key=selectedEmailTemplate(),variant=$('emailTemplateVariant').value,body={key,variant,settings:readEmailTemplateFields(),brand:emailTemplateData.branding};const d=await api('/api/admin/email-templates/preview',{method:'POST',body:JSON.stringify(body)});$('emailTemplatePreview').srcdoc=d.html}catch(err){$('emailTemplateError').textContent=err.message}finally{button.disabled=false}}
async function loadEmailTemplates(){const d=await api('/api/admin/email-templates');emailTemplateData=d.templates||{};emailTemplateMeta=d.metadata||{};renderEmailTemplateFields();await previewEmailTemplate()}
$('emailTemplateKind').onchange=()=>{renderEmailTemplateFields();previewEmailTemplate()};$('emailTemplateVariant').onchange=previewEmailTemplate;$('previewEmailTemplate').onclick=previewEmailTemplate;
$('emailTemplateForm').onsubmit=async e=>{e.preventDefault();const button=$('saveEmailTemplate');button.disabled=true;$('emailTemplateError').textContent='';$('emailTemplateMessage').classList.add('hidden');try{const key=selectedEmailTemplate(),d=await api('/api/admin/email-templates/'+encodeURIComponent(key),{method:'PUT',body:JSON.stringify({settings:readEmailTemplateFields()})});emailTemplateData[key]=d.settings;emailTemplateMeta[key]={updated_at:d.updated_at,updated_by:d.updated_by};renderEmailTemplateFields();$('emailTemplateMessage').textContent='Wijzigingen opgeslagen. Nieuwe e-mails gebruiken deze versie.';$('emailTemplateMessage').classList.remove('hidden');await previewEmailTemplate()}catch(err){$('emailTemplateError').textContent=err.message}finally{button.disabled=false}};
var tmStaff=[],tmMenu='',tmForm='',tmResult=null,tmShowRevoked=false;
const tmGroups=[['Support',['support.view','support.reply','support.status']],['Klanten',['customers.view','customers.manage']],['Licenties',['licenses.view','licenses.issue','licenses.manage']],['Sales',['sales.view','sales.manage']],['Communicatie',['email.templates.manage']],['Shop en betalingen',['shop.view','shop.manage','billing.view','billing.manage']]];
function tmLabel(p){const x=permissionOptions.find(o=>o[0]===p);return x?x[1]:p}
function tmToast(text,bad){const t=$('teamToast');t.textContent=text||'';t.classList.toggle('bad',!!bad);clearTimeout(tmToast.timer);if(text)tmToast.timer=setTimeout(()=>{t.textContent=''},7000)}
function tmFunctionName(key){const f=functionCatalog.find(x=>x.function_key===key);return f?f.name:key}
function tmState(s){if(s.revoked_at)return ['off','Ingetrokken'];if(s.invitation_sent_at)return ['wait','Uitnodiging verstuurd · wacht op instellen'];if(!Number(s.mfa_enabled))return ['wait','Koppelt authenticator bij eerste aanmelding'];if(Number(s.must_change_password))return ['wait','Kiest nog een eigen wachtwoord'];return ['ok','Actief'+(s.last_seen_at?' · '+cxAgo(s.last_seen_at):'')]}
function tmFunctionChecks(selected){return '<div class="cx-checks">'+functionCatalog.map(f=>'<label><input type="checkbox" data-tm-fn="'+safe(f.function_key)+'"'+(selected.includes(f.function_key)?' checked':'')+'>'+safe(f.name)+'</label>').join('')+'</div>'}
function tmConfirm(kind,s,text,label,danger){return '<div class="'+(danger?'cx-danger':'cx-warn')+'">'+text+'<div class="cx-box-actions"><button type="button" class="cx-btn" data-tm="cancel">Annuleren</button><button type="button" class="cx-btn '+(danger?'danger':'primary')+'" data-tm="'+kind+'-confirm" data-id="'+safe(s.id)+'">'+label+'</button></div></div>'}
function tmRow(s){const st=tmState(s),id=safe(s.id),fns=s.function_keys.map(tmFunctionName),low=!s.revoked_at&&Number(s.mfa_enabled)&&Number(s.recovery_codes_left)<=2,first=safe(s.first_name||s.name);
const items=s.revoked_at?[['restore','Weer activeren',''],['delete','Account verwijderen','danger']]:[['edit','Gegevens bewerken',''],...(s.invitation_sent_at?[['resend-invite','Uitnodiging opnieuw versturen','']]:[]),['functions','Functies wijzigen',''],['reset-password','Tijdelijk wachtwoord maken',''],['reset-mfa','Authenticator opnieuw laten koppelen',''],['revoke','Account intrekken','danger'],['delete','Account verwijderen','danger']];
let h='<div class="tm-row'+(s.revoked_at?' revoked':'')+'"><div class="cx-line"><span class="cx-user"><span class="cx-avatar'+(s.revoked_at?' off':'')+'">'+safe(cxInitials(s.name))+'</span><span><strong>'+safe(s.name)+'</strong><small>'+safe(s.username)+' · '+(s.email?safe(s.email):'<span class="cx-soon">geen e-mailadres</span>')+'</small></span></span><span class="tm-side"><span class="cx-chips">'+(fns.length?fns.map(n=>'<span class="cx-chip">'+safe(n)+'</span>').join(''):'<span class="cx-chip full">Geen functie</span>')+(low?'<span class="cx-chip full" title="Herstelcodes bijna op">'+cxPlural(Number(s.recovery_codes_left),'herstelcode','herstelcodes')+'</span>':'')+'</span><span class="cx-state '+st[0]+'"><span class="cx-dot"></span>'+safe(st[1])+'</span><span class="cx-pop"><button type="button" class="cx-icon" data-tm="menu" data-id="'+id+'" aria-haspopup="menu" aria-expanded="'+(tmMenu===s.id)+'" aria-label="Acties voor '+safe(s.name)+'">⋯</button>'+(tmMenu===s.id?'<div class="cx-menu" role="menu">'+items.map((i,n)=>(i[2]==='danger'&&(n===0||items[n-1][2]!=='danger')?'<div class="cx-sep" role="separator"></div>':'')+'<button type="button" role="menuitem" class="'+i[2]+'" data-tm="'+i[0]+'" data-id="'+id+'">'+i[1]+'</button>').join('')+'</div>':'')+'</span></span></div>';
if(tmForm==='edit:'+s.id)h+='<form class="cx-form cx-inset" data-tm-form="edit" data-id="'+id+'"><div><label for="tmEditName">Volledige naam</label><input id="tmEditName" maxlength="80" value="'+safe(s.name)+'"></div><div><label for="tmEditFirst">Voornaam</label><input id="tmEditFirst" maxlength="40" value="'+safe(s.first_name||'')+'"></div><div class="full"><label for="tmEditEmail">E-mailadres</label><input id="tmEditEmail" type="email" maxlength="254" value="'+safe(s.email||'')+'" placeholder="naam@cohentra.digital"></div><p class="cx-line-sub full" style="margin:0">Met een e-mailadres kan '+first+' het wachtwoord zelf herstellen. De gebruikersnaam ('+safe(s.username)+') blijft hetzelfde.</p><p class="cx-error" id="tmFormError" role="alert"></p><div class="cx-form-actions"><button type="button" class="cx-btn" data-tm="cancel">Annuleren</button><button class="cx-btn primary">Opslaan</button></div></form>';
if(tmForm==='functions:'+s.id)h+='<form class="cx-form cx-inset" data-tm-form="functions" data-id="'+id+'"><div class="full"><label>Functies van '+first+'</label>'+tmFunctionChecks(s.function_keys)+'</div><p class="cx-error" id="tmFormError" role="alert"></p><div class="cx-form-actions"><button type="button" class="cx-btn" data-tm="cancel">Annuleren</button><button class="cx-btn primary">Opslaan</button></div></form>';
if(tmForm==='reset-mfa:'+s.id)h+=tmConfirm('reset-mfa',s,'<strong>Authenticator opnieuw laten koppelen?</strong> '+first+' wordt direct afgemeld en koppelt bij de volgende aanmelding een nieuwe authenticator-app. De oude herstelcodes vervallen.','Opnieuw laten koppelen',false);
if(tmForm==='reset-password:'+s.id)h+=tmConfirm('reset-password',s,'<strong>Tijdelijk wachtwoord maken?</strong> '+first+' wordt direct afgemeld. Met het tijdelijke wachtwoord meldt '+first+' zich aan en kiest daarna een eigen wachtwoord. De authenticator blijft gekoppeld.','Wachtwoord maken',false);
if(tmForm==='revoke:'+s.id)h+=tmConfirm('revoke',s,'<strong>Account van '+safe(s.name)+' intrekken?</strong> '+first+' kan zich direct niet meer aanmelden. Je kunt het account later weer activeren.','Intrekken',true);
if(tmForm==='delete:'+s.id)h+='<form class="cx-danger" data-tm-form="delete" data-id="'+id+'"><strong>Account van '+safe(s.name)+' definitief verwijderen?</strong> '+first+' kan zich direct niet meer aanmelden. Sessies, herstelcodes en functies worden gewist; toegewezen tickets komen op niet toegewezen te staan. Verstuurde antwoorden blijven met de naam van '+first+' in de gesprekken staan. Dit kun je niet ongedaan maken.'+(s.revoked_at?'':' Wil je alleen tijdelijk blokkeren? Kies dan intrekken.')+'<label for="tmDeleteName" style="display:block;margin:10px 0 4px;font-size:12px">Typ de gebruikersnaam <strong>'+safe(s.username)+'</strong> ter bevestiging</label><input id="tmDeleteName" autocomplete="off" style="width:100%;padding:7px 10px"><p class="cx-error" id="tmFormError" role="alert" style="margin-top:6px"></p><div class="cx-box-actions"><button type="button" class="cx-btn" data-tm="cancel">Annuleren</button><button class="cx-btn danger">Definitief verwijderen</button></div></form>';
if(tmResult&&tmResult.id===s.id)h+='<div class="cx-ok"><strong>Tijdelijk wachtwoord voor '+safe(s.name)+'.</strong> Geef het persoonlijk door; het wordt maar één keer getoond.<div class="cx-key"><code>'+safe(tmResult.password)+'</code><button type="button" class="cx-btn" data-tm="copy" data-copy="'+safe(tmResult.password)+'">Kopiëren</button></div><div class="cx-box-actions"><button type="button" class="cx-btn" data-tm="dismiss">Sluiten</button></div></div>';
return h+'</div>'}
function renderTeamCreate(){const box=$('teamCreate');if(tmResult&&tmResult.id==='new'){box.innerHTML='<div class="cx-ok" style="margin:0 0 12px"><strong>Account voor '+safe(tmResult.name)+' aangemaakt.</strong> We hebben een beveiligde instellink gestuurd naar <strong>'+safe(tmResult.email)+'</strong>. De link is eenmalig en 24 uur geldig. Bij de eerste aanmelding koppelt de medewerker zelf een authenticator-app.<div class="cx-box-actions"><button type="button" class="cx-btn" data-tm="dismiss">Sluiten</button></div></div>';return}
if(tmForm!=='create'){box.innerHTML='';return}
box.innerHTML='<form class="cx-form cx-inset" data-tm-form="create" style="margin:0 0 12px"><div><label for="tmName">Volledige naam</label><input id="tmName" maxlength="80" autocomplete="name" placeholder="Bijvoorbeeld: Jamie de Wit" required></div><div><label for="tmFirst">Voornaam</label><input id="tmFirst" maxlength="40" autocomplete="given-name" placeholder="Jamie" required></div><div><label for="tmUser">Gebruikersnaam</label><input id="tmUser" maxlength="254" autocomplete="username" placeholder="jamie" required></div><div><label for="tmEmail">E-mailadres</label><input id="tmEmail" type="email" maxlength="254" autocomplete="email" placeholder="jamie@cohentra.digital" required></div><div class="full"><label>Functies</label>'+tmFunctionChecks(['support'])+'</div><p class="cx-line-sub full" style="margin:0">We sturen een eenmalige beveiligde link om zelf een wachtwoord in te stellen. Het wachtwoord wordt niet met de beheerder gedeeld.</p><p class="cx-error" id="tmFormError" role="alert"></p><div class="cx-form-actions"><button type="button" class="cx-btn" data-tm="cancel">Annuleren</button><button class="cx-btn primary">Uitnodiging versturen</button></div></form>'}
function renderStaff(){const active=tmStaff.filter(s=>!s.revoked_at),revoked=tmStaff.filter(s=>s.revoked_at),me=$('sidebarUser').textContent;$('teamSummary').textContent=cxPlural(active.length,'actieve medewerker','actieve medewerkers');
let h='<div class="tm-row"><div class="cx-line"><span class="cx-user"><span class="cx-avatar">'+safe(cxInitials(me))+'</span><span><strong>'+safe(me)+'</strong><small>Eigenaar · alle rechten</small></span></span><span class="tm-side"><span class="cx-chip">Eigenaar</span></span></div></div>';
h+=active.map(tmRow).join('');
if(revoked.length)h+='<p style="margin:12px 0 0"><button type="button" class="cx-btn link" data-tm="toggle-revoked">'+(tmShowRevoked?'Ingetrokken accounts verbergen':'Ingetrokken accounts tonen ('+revoked.length+')')+'</button></p>'+(tmShowRevoked?revoked.map(tmRow).join(''):'');
$('staff').innerHTML=h;renderTeamCreate();if(functionCatalog.length&&$('rightsMatrix').querySelector('.tm-fn-head'))renderRights()}
async function loadStaff(){try{const d=await api('/api/admin/staff');tmStaff=d.staff||[];renderStaff()}catch(e){$('staff').innerHTML='<div class="cx-placeholder error">'+safe(e.message)+'</div>'}}
async function loadFunctionCatalog(){const d=await api('/api/admin/functions');functionCatalog=d.functions||[];tmDraft=null;renderRights();if(tmStaff.length)renderStaff()}
var tmRightsSel='',tmDraft=null;
const tmPermHelp={'support.view':'Tickets en gesprekken inzien','support.reply':'Klanten per e-mail antwoorden','support.status':'De status van tickets aanpassen','customers.view':'Klantgegevens en licentiegebruik inzien','customers.manage':'Klanten aanmaken, bewerken en pauzeren, en portaalgebruikers beheren','licenses.view':'Uitgegeven licenties inzien','licenses.issue':'Nieuwe licenties uitgeven','licenses.manage':'Licenties intrekken en groeperen','sales.view':'Het salesonderdeel inzien','sales.manage':'Gegevens in het salesonderdeel bijwerken','email.templates.manage':'Teksten en huisstijl van e-mails aanpassen','shop.view':'Producten, abonnementen en prijzen inzien','shop.manage':'Producten, prijzen, versies en downloads aanmaken, wijzigen en publiceren','billing.view':'Bestellingen, facturen, abonnementen en Stripe-status van klanten inzien','billing.manage':'Uitzonderingen op licenties vastleggen en abonnementen beëindigen'};
function tmDraftReset(){tmDraft={};functionCatalog.forEach(f=>{tmDraft[f.function_key]={name:f.name,perms:new Set(f.permissions)}})}
function tmDirtyKeys(){if(!tmDraft)return [];return functionCatalog.filter(f=>{const d=tmDraft[f.function_key];return d&&(d.name.trim()!==f.name||[...d.perms].sort().join()!==f.permissions.slice().sort().join())}).map(f=>f.function_key)}
function tmRightsChrome(){const dirty=tmDirtyKeys();const tabs=$('tmTabs');if(tabs)tabs.innerHTML=functionCatalog.map(f=>{const d=tmDraft[f.function_key],on=f.function_key===tmRightsSel;return '<button type="button" role="tab" aria-selected="'+on+'" class="tm-tab'+(on?' on':'')+'" data-fn-tab="'+safe(f.function_key)+'">'+safe(d.name.trim()||f.name)+'<span class="tm-tab-count" title="Aantal rechten">'+d.perms.size+'</span>'+(dirty.includes(f.function_key)?'<span class="tm-dirty" title="Niet opgeslagen"></span>':'')+'</button>'}).join('');$('rightsBar').classList.toggle('hidden',!dirty.length);$('rightsState').textContent=dirty.length?(dirty.length===1?'Wijzigingen in 1 functie zijn nog niet opgeslagen':'Wijzigingen in '+dirty.length+' functies zijn nog niet opgeslagen'):''}
function renderRights(){const w=$('rightsMatrix');if(!functionCatalog.length){w.innerHTML='<p class="cx-empty">Nog geen functies.</p>';$('rightsBar').classList.add('hidden');return}if(!tmDraft)tmDraftReset();if(!functionCatalog.some(f=>f.function_key===tmRightsSel))tmRightsSel=functionCatalog[0].function_key;const d=tmDraft[tmRightsSel],members=tmStaff.filter(s=>!s.revoked_at&&s.function_keys.includes(tmRightsSel)).length,grouped=tmGroups.flatMap(g=>g[1]),extra=permissionOptions.map(p=>p[0]).filter(p=>!grouped.includes(p)),groups=extra.length?[...tmGroups,['Overig',extra]]:tmGroups;
w.innerHTML='<div class="tm-tabs" id="tmTabs" role="tablist" aria-label="Functies"></div><div class="tm-fn-head"><label class="tm-fn-name">Naam van de functie<input id="tmFnName" maxlength="60" value="'+safe(d.name)+'"></label><span class="cx-line-sub">'+cxPlural(members,'actieve medewerker heeft','actieve medewerkers hebben')+' deze functie</span></div><div class="tm-groups">'+groups.map(([g,perms])=>'<div class="tm-group-card"><div class="tm-group-title">'+safe(g)+'</div>'+perms.map(p=>'<label class="tm-perm"><span><strong>'+safe(tmLabel(p))+'</strong><small>'+safe(tmPermHelp[p]||'')+'</small></span><input type="checkbox" data-perm="'+safe(p)+'"'+(d.perms.has(p)?' checked':'')+'><span class="tm-switch" aria-hidden="true"></span></label>').join('')+'</div>').join('')+'</div>';tmRightsChrome();$('rightsError').textContent=''}
$('rightsMatrix').addEventListener('click',e=>{const t=e.target.closest('[data-fn-tab]');if(t&&t.dataset.fnTab!==tmRightsSel){tmRightsSel=t.dataset.fnTab;renderRights();const tab=$('rightsMatrix').querySelector('[data-fn-tab="'+CSS.escape(tmRightsSel)+'"]');if(tab)tab.focus()}});
$('rightsMatrix').addEventListener('change',e=>{const c=e.target.closest('[data-perm]');if(!c)return;const d=tmDraft[tmRightsSel];if(c.checked)d.perms.add(c.dataset.perm);else d.perms.delete(c.dataset.perm);tmRightsChrome()});
$('rightsMatrix').addEventListener('input',e=>{if(e.target.id==='tmFnName'){tmDraft[tmRightsSel].name=e.target.value;tmRightsChrome()}});
$('resetRights').onclick=()=>{tmDraft=null;renderRights()};
$('saveRights').onclick=async()=>{const b=$('saveRights');b.disabled=true;$('rightsError').textContent='';try{for(const key of tmDirtyKeys()){const d=tmDraft[key];if(!d.name.trim())throw Error('Elke functie heeft een naam nodig.');await api('/api/admin/functions/'+encodeURIComponent(key),{method:'PATCH',body:JSON.stringify({name:d.name.trim(),permissions:[...d.perms]})})}tmDraft=null;await loadFunctionCatalog();await loadStaff();tmToast('Rechten opgeslagen. Ze gelden direct.')}catch(err){$('rightsError').textContent=err.message}finally{b.disabled=false}};
$('addStaff').onclick=()=>{tmForm=tmForm==='create'?'':'create';tmResult=null;tmMenu='';renderStaff();if($('tmName'))$('tmName').focus()};
document.addEventListener('click',e=>{if(tmMenu&&!e.target.closest('#staff .cx-pop')){tmMenu='';renderStaff()}});
$('view-team').addEventListener('click',async e=>{const t=e.target.closest('[data-tm]');if(!t)return;const a=t.dataset.tm,s=tmStaff.find(x=>x.id===t.dataset.id);
if(a==='menu'){e.stopPropagation();tmMenu=tmMenu===t.dataset.id?'':t.dataset.id;return renderStaff()}
tmMenu='';
if(a==='toggle-revoked'){tmShowRevoked=!tmShowRevoked;return renderStaff()}
if(a==='cancel'){tmForm='';return renderStaff()}
if(a==='dismiss'){tmResult=null;return renderStaff()}
if(a==='copy'){try{await navigator.clipboard.writeText(t.dataset.copy);t.textContent='Gekopieerd'}catch{t.textContent='Selecteer en kopieer zelf'}return}
if(['edit','functions','reset-mfa','reset-password','revoke','delete'].includes(a)){tmForm=a+':'+s.id;tmResult=null;renderStaff();const f=$('staff').querySelector('form input');if(f)f.focus();return}
const run=async(path,done)=>{t.disabled=true;try{const d=await api(path,{method:'POST',body:'{}'});tmForm='';done(d);await loadStaff()}catch(err){tmToast(err.message,true);t.disabled=false}};
if(a==='restore')return run('/api/admin/staff/'+encodeURIComponent(s.id)+'/restore',()=>tmToast(s.name+' kan zich weer aanmelden.'));
if(a==='resend-invite')return run('/api/admin/staff/'+encodeURIComponent(s.id)+'/invite',()=>tmToast('Nieuwe uitnodiging verstuurd naar '+s.email+'.'));
if(a==='revoke-confirm')return run('/api/admin/staff/'+encodeURIComponent(s.id)+'/revoke',()=>tmToast('Het account van '+s.name+' is ingetrokken.'));
if(a==='reset-mfa-confirm')return run('/api/admin/staff/'+encodeURIComponent(s.id)+'/reset-mfa',()=>tmToast(s.name+' koppelt bij de volgende aanmelding een nieuwe authenticator.'));
if(a==='reset-password-confirm')return run('/api/admin/staff/'+encodeURIComponent(s.id)+'/reset-password',d=>{tmResult={id:s.id,password:d.password}})});
$('view-team').addEventListener('submit',async e=>{const f=e.target.closest('[data-tm-form]');if(!f)return;e.preventDefault();const kind=f.dataset.tmForm,button=f.querySelector('button:not([type=button])'),err=m=>{$('tmFormError').textContent=m},fns=[...f.querySelectorAll('[data-tm-fn]:checked')].map(x=>x.dataset.tmFn);button.disabled=true;
try{if(kind==='create'){const body={name:$('tmName').value.trim(),first_name:$('tmFirst').value.trim(),username:$('tmUser').value.trim(),email:$('tmEmail').value.trim(),function_keys:fns};if(!body.name||!body.first_name||!body.username||!body.email)throw Error('Vul alle accountgegevens in.');if(!fns.length)throw Error('Kies minimaal één functie.');const d=await api('/api/admin/staff',{method:'POST',body:JSON.stringify(body)});tmForm='';tmResult={id:'new',name:d.name,email:d.email};await loadStaff();return}
const id=f.dataset.id;if(kind==='edit'){await api('/api/admin/staff/'+encodeURIComponent(id),{method:'PATCH',body:JSON.stringify({name:$('tmEditName').value.trim(),first_name:$('tmEditFirst').value.trim(),email:$('tmEditEmail').value.trim()})});tmForm='';tmToast('Gegevens opgeslagen.');await loadStaff();return}
if(kind==='delete'){const s=tmStaff.find(x=>x.id===id),typed=$('tmDeleteName').value.trim();if(!s||typed!==s.username)throw Error('De gebruikersnaam klopt niet. Typ hem precies over.');await api('/api/admin/staff/'+encodeURIComponent(id),{method:'DELETE',body:JSON.stringify({confirm_username:typed})});tmForm='';tmToast('Het account van '+s.name+' is verwijderd.');await loadStaff();return}
if(kind==='functions'){await api('/api/admin/staff/'+encodeURIComponent(id)+'/functions',{method:'PATCH',body:JSON.stringify({function_keys:fns})});tmForm='';tmToast('Functies opgeslagen. Ze gelden bij de volgende actie van de medewerker.');await loadStaff();return}}catch(ex){err(ex.message)}finally{if(button.isConnected)button.disabled=false}});
$('view-team').addEventListener('input',e=>{const el=$('tmFormError');if(el&&e.target.closest('[data-tm-form]'))el.textContent=''});
var pfMe=null,pfState={};
function renderSecurity(){const box=$('securityCodes');if(!box)return;const left=Number(pfMe&&pfMe.recovery_codes_left||0);
if(pfState.codes){box.innerHTML='<div class="cx-ok" style="margin:0 0 10px">Je nieuwe herstelcodes. Bewaar ze op een veilige plek; de oude werken niet meer.</div><div class="au-codes">'+pfState.codes.map(c=>'<code>'+safe(c)+'</code>').join('')+'</div><div class="actions"><button type="button" class="secondary" id="pfDownload">Downloaden</button><button type="button" class="secondary" id="pfCopy">Kopiëren</button><button type="button" id="pfDone">Klaar</button></div>';$('pfDownload').onclick=()=>auDownload(pfState.codes,pfMe&&pfMe.username);$('pfCopy').onclick=async e=>{try{await navigator.clipboard.writeText(pfState.codes.join('\n'));e.target.textContent='Gekopieerd'}catch{}};$('pfDone').onclick=()=>{pfState={};renderSecurity()};return}
if(pfState.ask){box.innerHTML='<label for="pfCode">Code uit je authenticator-app</label><input id="pfCode" inputmode="numeric" autocomplete="one-time-code" maxlength="7" placeholder="123456"><p class="muted">De oude herstelcodes werken daarna niet meer.</p><div class="actions"><button type="button" class="secondary" id="pfCancel">Annuleren</button><button type="button" id="pfMake">Nieuwe codes maken</button></div><p class="error" id="pfError" role="alert"></p>';$('pfCode').focus();$('pfCancel').onclick=()=>{pfState={};renderSecurity()};const make=async()=>{const code=$('pfCode').value.replace(/\D/g,'');if(code.length!==6){$('pfError').textContent='Vul de 6 cijfers uit je app in.';return}$('pfMake').disabled=true;try{const d=await api('/api/admin/me/recovery-codes',{method:'POST',body:JSON.stringify({code})});pfState={codes:d.recovery_codes};pfMe.recovery_codes_left=d.recovery_codes.length;pfLowCodes();renderSecurity()}catch(err){$('pfError').textContent=err.message;$('pfMake').disabled=false}};$('pfMake').onclick=make;$('pfCode').onkeydown=e=>{if(e.key==='Enter')make()};$('pfCode').oninput=()=>{if($('pfCode').value.replace(/\D/g,'').length===6)make()};return}
box.innerHTML=(left<=2?'<div class="cx-warn" style="margin:0 0 10px">Je hebt nog maar '+cxPlural(left,'herstelcode','herstelcodes')+'. Maak nieuwe aan zodat je niet buitengesloten raakt.</div>':'')+'<p>Je hebt nog <strong>'+left+' van 10</strong> herstelcodes.</p><div class="actions"><button type="button" class="secondary" id="pfNew">Nieuwe herstelcodes maken</button></div>';$('pfNew').onclick=()=>{pfState={ask:true};renderSecurity()}}
function pfLowCodes(){const n=$('lowCodesNotice');if(!n||!pfMe)return;const left=Number(pfMe.recovery_codes_left||0);n.classList.toggle('hidden',left>2);n.innerHTML='Je hebt nog maar '+cxPlural(left,'herstelcode','herstelcodes')+'. <button type="button" class="cx-btn link" id="lowCodesGo" style="border:0;background:none;padding:0;color:var(--purple);text-decoration:underline">Maak nieuwe aan in Profiel</button>';const go=$('lowCodesGo');if(go)go.onclick=()=>setView('profile')}
$('saveSignatureName').onclick=async()=>{const b=$('saveSignatureName');b.disabled=true;$('signatureNameError').textContent='';try{const result=await api('/api/admin/me',{method:'PATCH',body:JSON.stringify({name:$('signatureName').value.trim(),first_name:$('signatureFirstName').value.trim(),email:$('profileEmail').value.trim()})});$('signatureFirstName').value=result.first_name;$('signatureName').value=result.name;if(result.email!==undefined&&pfMe)pfMe.email=result.email;$('profileSaved').textContent='Opgeslagen.';setTimeout(()=>{$('profileSaved').textContent=''},4000)}catch(err){$('signatureNameError').textContent=err.message}finally{b.disabled=false}};

async function loadLicenses(){try{const d=await api('/api/admin/licenses/expiring');licenseSummary={licenses:d.active,groups:d.expiring.length};updateOverview();const box=$('expiringList');if(!box)return;box.innerHTML=d.expiring.length?d.expiring.map(l=>'<button type="button" class="ov-exp" data-exp-customer="'+safe(l.customer_id||'intern')+'"><span><strong>'+safe(l.label||'Zonder naam')+'</strong><small>'+safe((l.customer_name||'Cohentra (intern)')+(l.group_name?' · '+l.group_name:''))+'</small></span><span class="ov-exp-date">'+safe(cxDate(l.valid_until))+(l.expiry_notice_sent_at?'<small>klant gemaild</small>':'')+'</span></button>').join(''):'<p class="muted" style="margin:6px 0 0">Geen licenties die binnen 30 dagen verlopen.</p>'}catch(e){const box=$('expiringList');if(box)box.innerHTML='<p class="error">'+safe(e.message)+'</p>'}}
$('expiringList').onclick=e=>{const b=e.target.closest('[data-exp-customer]');if(!b)return;setView('customers');openCustomer(b.dataset.expCustomer)};
var authState={view:'login'},authUser='',authChallenge='',authAdminKey='',authLowCodes=-1;
const auEyeOpen='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
const auEyeShut='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 3l18 18"/><path d="M10.6 5.1A9.8 9.8 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4.1"/><path d="M6.6 6.6C3.8 8.4 2 12 2 12s3.6 7 10 7a9.7 9.7 0 0 0 5.4-1.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';
const auBrand='<div class="au-brand"><img class="au-logo" src="/brand/cohentra-logo.png" width="137" height="50" alt="Cohentra Digital"><small class="au-sub">Medewerkersportaal</small></div>';
function auPassword(id,label,auto,extra){return '<label class="au-label" for="'+id+'">'+label+'</label><div class="au-pw"><input id="'+id+'" type="password" autocomplete="'+auto+'" maxlength="512"><button type="button" class="au-eye" data-au-eye="'+id+'" aria-label="Wachtwoord tonen" aria-pressed="false" title="Wachtwoord tonen">'+auEyeOpen+'</button></div>'+(id==='auNew'?'<div class="au-strength" data-password-strength data-level="0" aria-live="polite"><div class="au-strength-track" aria-hidden="true"><div class="au-strength-fill"></div></div><span class="au-strength-label">Gebruik minimaal 12 tekens; een lange wachtzin werkt goed.</span></div>':'')+(extra||'')}
function passwordStrength(value){const v=String(value||''),lower=v.toLocaleLowerCase('nl-NL');if(!v)return {level:0,label:'Gebruik minimaal 12 tekens; een lange wachtzin werkt goed.'};if(/^(password|wachtwoord|welkom|qwerty|123456|admin|cohentra|eventhub)[\W_]*\d*$/i.test(v)||/(.)\1{5,}/.test(v))return {level:1,label:'Zwak — kies een langere, minder voorspelbare wachtzin.'};if(v.length<12)return {level:1,label:'Zwak — gebruik minimaal 12 tekens.'};let level=v.length>=22?4:v.length>=16?3:2;const words=lower.split(/[^a-z0-9]+/).filter(Boolean);if(words.length>=4&&v.length>=18)level=Math.max(level,4);if(/^(.)\1+$/.test(v)||/(0123|1234|2345|3456|4567|5678|6789|abcd|qwer|asdf)/i.test(v))level=Math.max(1,level-1);return {level,label:level>=4?'Sterk — dit is een goede lange wachtzin.':level===3?'Sterk — een lange wachtzin is lastig te raden.':'Redelijk — langer is nog beter.'}}
function updatePasswordStrength(input){const box=input?.closest('form')?.querySelector('[data-password-strength]');if(!box)return;const result=passwordStrength(input.value);box.dataset.level=String(result.level);box.querySelector('.au-strength-label').textContent=result.label}
function auOtp(){return '<div class="au-otp" data-au-otp>'+[0,1,2,3,4,5].map(i=>(i===3?'<span class="au-gap"></span>':'')+'<input inputmode="numeric" pattern="[0-9]*" maxlength="6" aria-label="Cijfer '+(i+1)+' van 6"'+(i===0?' autocomplete="one-time-code"':' autocomplete="off"')+'>').join('')+'</div>'}
function auSteps(n,total){return '<div class="au-steps" aria-hidden="true">'+Array.from({length:total},(_,i)=>'<span class="'+(i<n?'on':'')+'"></span>').join('')+'</div>'}
function auCodesHtml(codes){return '<div class="au-codes">'+codes.map(c=>'<code>'+safe(c)+'</code>').join('')+'</div><div class="au-code-actions"><button type="button" class="au-secondary" data-au-go="download">Downloaden</button><button type="button" class="au-secondary" data-au-go="copy-codes">Kopiëren</button></div>'}
function auDownload(codes,user){const text='Cohentra herstelcodes'+(user?' voor '+user:'')+'\r\nAangemaakt op '+new Date().toLocaleString('nl-NL')+'\r\n\r\n'+codes.join('\r\n')+'\r\n\r\nElke code werkt één keer. Bewaar dit bestand op een veilige plek.\r\n';const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'text/plain'}));a.download='cohentra-herstelcodes.txt';document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},500)}
function auView(){const s=authState,v=s.view;
if(v==='login')return (s.info?'<div class="au-info">'+safe(s.info)+'</div>':'')+'<h1>Welkom terug</h1><p class="au-sub">Meld je aan om verder te gaan.</p><form data-au="login" novalidate><label class="au-label" for="auUser">Gebruikersnaam</label><input id="auUser" autocomplete="username" maxlength="254" value="'+safe(authUser)+'">'+auPassword('auPass','Wachtwoord','current-password','<div class="au-row-end"><button type="button" class="au-small" data-au-go="forgot">Wachtwoord vergeten?</button></div>')+'<p class="au-error" id="auError" role="alert">'+safe(s.error||'')+'</p><button class="au-primary">Doorgaan</button></form>';
if(v==='mfa')return '<h1>Bevestig dat jij het bent</h1><p class="au-sub">Vul de 6 cijfers uit je authenticator-app in voor <strong>'+safe(authUser)+'</strong>.</p><form data-au="mfa" novalidate>'+auOtp()+'<p class="au-error" id="auError" role="alert" style="text-align:center"></p></form><div class="au-links"><button type="button" class="au-small" data-au-go="restart">← Ander account</button><button type="button" class="au-small" data-au-go="recovery">Herstelcode gebruiken</button></div>';
if(v==='recovery')return '<h1>Herstelcode</h1><p class="au-sub">Gebruik een van je eenmalige herstelcodes als je je telefoon niet bij je hebt.</p><form data-au="recovery" novalidate><label class="au-label" for="auRecovery">Herstelcode</label><input id="auRecovery" autocomplete="off" placeholder="ABCD-EF12-3456-7890" style="font-family:ui-monospace,monospace"><p class="au-error" id="auError" role="alert"></p><button class="au-primary">Aanmelden</button></form><div class="au-links"><button type="button" class="au-small" data-au-go="mfa">← Terug naar de code</button></div><div class="au-help"><p><strong>Telefoon én herstelcodes kwijt?</strong></p><p>Medewerkers: vraag de eigenaar om je authenticator opnieuw te laten koppelen.</p><p>Eigenaar: <button type="button" class="au-small" data-au-go="emergency" style="color:var(--purple)">gebruik noodherstel</button> met de Worker-sleutel uit Cloudflare.</p></div>';
if(v==='enroll'){const qr=(()=>{try{return qrSvg(otpauthUri(s.account,s.secret))}catch{return ''}})();return auSteps(1,3)+'<h1>Koppel je authenticator</h1><p class="au-sub">Scan de QR-code met Google Authenticator, Microsoft Authenticator of een andere app. Vul daarna de code in die de app toont.</p><div class="au-qr">'+qr+'</div><label class="au-label">Of vul deze sleutel handmatig in</label><div class="au-secret"><code id="auSecret">'+safe(String(s.secret).replace(/(.{4})/g,'$1 ').trim())+'</code><button type="button" class="au-secondary" data-au-go="copy-secret">Kopiëren</button></div><form data-au="enroll" novalidate><label class="au-label">Code uit de app</label>'+auOtp()+'<p class="au-error" id="auError" role="alert" style="text-align:center"></p></form><div class="au-links"><button type="button" class="au-small" data-au-go="restart">← Annuleren</button></div>'}
if(v==='codes')return auSteps(2,3)+'<h1>Bewaar je herstelcodes</h1><p class="au-sub">Met een herstelcode meld je je aan als je je telefoon niet bij je hebt. Elke code werkt één keer. Deze codes zie je maar één keer.</p>'+auCodesHtml(s.codes)+'<form data-au="codes" novalidate><label class="au-check"><input type="checkbox" id="auSaved"><span>Ik heb mijn herstelcodes op een veilige plek bewaard.</span></label><p class="au-error" id="auError" role="alert"></p><button class="au-primary">Verder</button></form>';
if(v==='password')return auSteps(3,3)+'<h1>Kies je eigen wachtwoord</h1><p class="au-sub">Je bent aangemeld met een tijdelijk wachtwoord. Kies nu een wachtwoord dat alleen jij kent.</p><form data-au="password" novalidate>'+auPassword('auNew','Nieuw wachtwoord','new-password','<p class="au-note" style="margin-top:6px">Minimaal 12 tekens. Een zin van een paar woorden werkt goed.</p>')+auPassword('auConfirm','Herhaal het wachtwoord','new-password')+'<p class="au-error" id="auError" role="alert"></p><button class="au-primary">Wachtwoord opslaan</button></form>';
if(v==='forgot')return '<h1>Wachtwoord vergeten</h1><p class="au-sub">Vul je gebruikersnaam of e-mailadres in. Als er een account bij hoort, sturen we een link om een nieuw wachtwoord te kiezen.</p><form data-au="forgot" novalidate><label class="au-label" for="auIdent">Gebruikersnaam of e-mailadres</label><input id="auIdent" autocomplete="username" maxlength="254" value="'+safe(authUser)+'"><p class="au-error" id="auError" role="alert"></p><button class="au-primary">Link versturen</button></form><div class="au-links"><button type="button" class="au-small" data-au-go="restart">← Terug naar aanmelden</button></div><p class="au-note">Geen e-mailadres ingesteld? Vraag de eigenaar om een tijdelijk wachtwoord.</p>';
if(v==='forgot-sent')return '<h1>Check je mail</h1><p class="au-sub">Als er een account bij hoort, staat er binnen een paar minuten een e-mail klaar. De link is 30 minuten geldig. Daarna meld je je aan met je nieuwe wachtwoord en je authenticatorcode.</p><button type="button" class="au-primary" data-au-go="restart">Terug naar aanmelden</button>';
if(v==='reset'){const setup=!!s.setup;return '<h1>'+(setup?'Stel je wachtwoord in':'Nieuw wachtwoord kiezen')+'</h1><p class="au-sub">'+(setup?'Kies je persoonlijke wachtwoord voor het medewerkersportaal. Daarna meld je je aan en koppel je je authenticator-app.':'Kies een nieuw wachtwoord voor je account. Daarna meld je je aan met dit wachtwoord en je authenticatorcode.')+'</p><form data-au="reset" novalidate>'+auPassword('auNew',setup?'Nieuw wachtwoord':'Nieuw wachtwoord','new-password','<p class="au-note" style="margin-top:6px">Minimaal 12 tekens. Een lange wachtzin werkt goed.</p>')+auPassword('auConfirm','Herhaal het wachtwoord','new-password')+'<p class="au-error" id="auError" role="alert"></p><button class="au-primary">Wachtwoord opslaan</button></form><div class="au-links"><button type="button" class="au-small" data-au-go="restart">← Terug naar aanmelden</button></div>'}
if(v==='bootstrap')return '<h1>Eerste installatie</h1><p class="au-sub">Dit eigenaarsaccount heeft nog geen authenticator. Vul de Worker-beheerderssleutel uit Cloudflare in om die eenmalig te koppelen.</p><form data-au="bootstrap" novalidate>'+auPassword('auKey','Worker-beheerderssleutel','off')+'<p class="au-error" id="auError" role="alert"></p><button class="au-primary">Authenticator koppelen</button></form><div class="au-links"><button type="button" class="au-small" data-au-go="restart">← Terug naar aanmelden</button></div>';
if(v==='emergency')return '<h1>Noodherstel eigenaar</h1><div class="au-warn">Gebruik dit alleen als je je authenticator én je herstelcodes kwijt bent. Je authenticator wordt losgekoppeld; daarna koppel je direct een nieuwe.</div><form data-au="emergency" novalidate>'+auPassword('auKey','Worker-beheerderssleutel (ADMIN_TOKEN)','off')+'<label class="au-label" for="auUser">Gebruikersnaam</label><input id="auUser" autocomplete="username" maxlength="254" value="'+safe(authUser)+'">'+auPassword('auPass','Wachtwoord','current-password')+'<p class="au-error" id="auError" role="alert"></p><button class="au-primary">Authenticator opnieuw koppelen</button></form><div class="au-links"><button type="button" class="au-small" data-au-go="restart">← Terug naar aanmelden</button></div><p class="au-note">De sleutel staat in Cloudflare bij de Worker eventhub-licenses onder Instellingen → Variabelen en secrets.</p>';
return ''}
function auShow(){$('authScreen').classList.remove('hidden');$('dashboard').classList.add('hidden');$('authCard').innerHTML=auBrand+auView();const first=$('authCard').querySelector('[data-au-otp] input')||$('authCard').querySelector('form input:not([type=checkbox])');if(first){if(first.id==='auUser'&&first.value&&$('auPass'))$('auPass').focus();else first.focus()}}
function showLogin(message=''){clearAvatarObjectUrls();authState={view:'login',error:message||''};auShow()}
function auError(msg){const e=$('auError');if(e)e.textContent=msg||''}
function auOtpValue(form){return [...form.querySelectorAll('[data-au-otp] input')].map(i=>i.value).join('')}
function auOtpReset(form){const box=form.querySelector('[data-au-otp]');if(!box)return;box.querySelectorAll('input').forEach(i=>{i.value='';i.disabled=false});box.classList.remove('shake');void box.offsetWidth;box.classList.add('shake');box.querySelector('input').focus()}
async function auPost(path,body,bearer){const headers={'Content-Type':'application/json'};if(bearer)headers.Authorization='Bearer '+bearer;const r=await fetch(path,{method:'POST',headers,body:JSON.stringify(body||{})});let d={};try{d=await r.json()}catch{}if(!r.ok)throw Error(d.error||'Er ging iets mis. Probeer het opnieuw.');return d}
async function auEnter(sessionToken){authChallenge='';authAdminKey='';token=sessionToken;sessionStorage.setItem('eventhub-admin-token',token);authState={view:'login'};await enterDashboard()}
function auAfterLogin(d){if(d.recovery_codes){const next={...d};delete next.recovery_codes;authState={view:'codes',codes:d.recovery_codes,next};return auShow()}if(d.password_change_required){authState={view:'password',token:d.password_change_token};return auShow()}authLowCodes=Number(d.recovery_codes_left);return auEnter(d.session_token)}
async function auSubmit(kind,form){const s=authState;
if(kind==='login'){const u=$('auUser').value.trim(),p=$('auPass').value;if(!u||!p)return auError('Vul je gebruikersnaam en wachtwoord in.');authUser=u;const d=await auPost('/api/auth/challenge',{username:u,password:p});if(d.enrollment_required){authState={view:'bootstrap',password:p};return auShow()}authChallenge=d.challenge_token;if(d.mfa_enrollment_required){const e=await auPost('/api/auth/mfa/enroll',{},authChallenge);authState={view:'enroll',mode:'staff',secret:e.secret,account:e.account||u};return auShow()}authState={view:'mfa'};return auShow()}
if(kind==='mfa'){const d=await auPost('/api/auth/login',{challenge_token:authChallenge,mfa_code:auOtpValue(form)});return auAfterLogin(d)}
if(kind==='recovery'){const code=$('auRecovery').value.trim();if(!code)return auError('Vul een herstelcode in.');const d=await auPost('/api/auth/login',{challenge_token:authChallenge,recovery_code:code});return auAfterLogin(d)}
if(kind==='enroll'){const code=auOtpValue(form);if(s.mode==='staff'){const d=await auPost('/api/auth/mfa/enroll/confirm',{code},authChallenge);return auAfterLogin(d)}const d=await auPost('/api/auth/mfa/confirm',{code},authAdminKey);authAdminKey='';authState={view:'codes',codes:d.recovery_codes,next:{owner:true}};return auShow()}
if(kind==='codes'){if(!$('auSaved').checked)return auError('Bevestig dat je de herstelcodes veilig hebt bewaard.');if(s.next.owner){authState={view:'login',info:'Je authenticator is gekoppeld. Meld je nu aan met je nieuwe code.'};return auShow()}return auAfterLogin(s.next)}
if(kind==='password'||kind==='reset'){const a=$('auNew').value,b=$('auConfirm').value;if(a.length<12)return auError('Kies een wachtwoord van minimaal 12 tekens.');if(passwordStrength(a).level<=1)return auError('Kies een minder voorspelbaar wachtwoord; maak het langer of gebruik een wachtzin.');if(a!==b)return auError('De wachtwoorden komen niet overeen.');if(kind==='password'){const d=await auPost('/api/auth/password/first-change',{new_password:a,confirm_password:b},s.token);return auEnter(d.session_token)}await auPost('/api/auth/password/reset',{token:s.resetToken,new_password:a,confirm_password:b});authState={view:'login',info:s.setup?'Je wachtwoord is ingesteld. Meld je aan en koppel je authenticator-app.':'Je wachtwoord is gewijzigd. Meld je aan met je nieuwe wachtwoord en je authenticatorcode.'};return auShow()}
if(kind==='forgot'){const id=$('auIdent').value.trim();if(!id)return auError('Vul je gebruikersnaam of e-mailadres in.');await auPost('/api/auth/password/forgot',{identifier:id});authState={view:'forgot-sent'};return auShow()}
if(kind==='bootstrap'){const key=$('auKey').value.trim();if(!key)return auError('Vul de Worker-beheerderssleutel in.');const d=await auPost('/api/auth/mfa/setup',{username:authUser,password:s.password},key);authAdminKey=key;authState={view:'enroll',mode:'owner',secret:d.secret,account:authUser};return auShow()}
if(kind==='emergency'){const key=$('auKey').value.trim(),u=$('auUser').value.trim(),p=$('auPass').value;if(!key||!u||!p)return auError('Vul de sleutel, je gebruikersnaam en je wachtwoord in.');await auPost('/api/auth/owner/recover',{username:u,password:p},key);const d=await auPost('/api/auth/mfa/setup',{username:u,password:p},key);authUser=u;authAdminKey=key;authState={view:'enroll',mode:'owner',secret:d.secret,account:u};return auShow()}}
$('authCard').addEventListener('submit',async e=>{const form=e.target.closest('[data-au]');if(!form)return;e.preventDefault();if(form.dataset.busy)return;form.dataset.busy='1';const button=form.querySelector('.au-primary');if(button)button.disabled=true;try{await auSubmit(form.dataset.au,form)}catch(err){if(form.isConnected){auError(err.message);auOtpReset(form)}else showLogin(err.message)}finally{delete form.dataset.busy;if(button&&button.isConnected)button.disabled=false}});
$('authCard').addEventListener('click',async e=>{const eye=e.target.closest('[data-au-eye]');if(eye){const input=$(eye.dataset.auEye),show=input.type==='password';input.type=show?'text':'password';eye.innerHTML=show?auEyeShut:auEyeOpen;eye.setAttribute('aria-pressed',String(show));eye.setAttribute('aria-label',show?'Wachtwoord verbergen':'Wachtwoord tonen');eye.title=eye.getAttribute('aria-label');input.focus();return}
const go=e.target.closest('[data-au-go]');if(!go)return;const g=go.dataset.auGo;
if(g==='forgot'){const u=$('auUser');if(u)authUser=u.value.trim();authState={view:'forgot'};return auShow()}
if(g==='restart'){if(authChallenge)fetch('/api/auth/logout',{method:'POST',headers:{'Authorization':'Bearer '+authChallenge}}).catch(()=>{});authChallenge='';authAdminKey='';return showLogin()}
if(g==='recovery'||g==='mfa'||g==='emergency'){authState={view:g};return auShow()}
if(g==='download')return auDownload(authState.codes,authUser);
if(g==='copy-codes'||g==='copy-secret'){const text=g==='copy-codes'?authState.codes.join('\n'):authState.secret;try{await navigator.clipboard.writeText(text);go.textContent='Gekopieerd'}catch{go.textContent='Kopiëren lukt niet; selecteer de tekst'}}});
$('authCard').addEventListener('input',e=>{const box=e.target.closest('[data-au-otp]');if(!box){if(e.target.id==='auNew')updatePasswordStrength(e.target);if(e.target.matches('input'))auError('');return}const inputs=[...box.querySelectorAll('input')],i=inputs.indexOf(e.target),digits=e.target.value.replace(/\D/g,'');if(digits.length>1){digits.slice(0,6-i).split('').forEach((d,j)=>{inputs[i+j].value=d})}else e.target.value=digits;const next=inputs.find(x=>!x.value);if(next&&digits)next.focus();auError('');if(inputs.every(x=>x.value)){const form=box.closest('form');inputs.forEach(x=>x.blur());form.requestSubmit()}});
$('authCard').addEventListener('keydown',e=>{const box=e.target.closest('[data-au-otp]');if(!box)return;const inputs=[...box.querySelectorAll('input')],i=inputs.indexOf(e.target);if(e.key==='Backspace'&&!e.target.value&&i>0){inputs[i-1].value='';inputs[i-1].focus();e.preventDefault()}if(e.key==='ArrowLeft'&&i>0)inputs[i-1].focus();if(e.key==='ArrowRight'&&i<5)inputs[i+1].focus()});
$('authCard').addEventListener('paste',e=>{const box=e.target.closest('[data-au-otp]');if(!box)return;const digits=(e.clipboardData.getData('text')||'').replace(/\D/g,'').slice(0,6);if(!digits)return;e.preventDefault();const inputs=[...box.querySelectorAll('input')];inputs.forEach((x,j)=>x.value=digits[j]||'');if(digits.length===6){inputs.forEach(x=>x.blur());box.closest('form').requestSubmit()}else inputs[digits.length].focus()});
const staffLogout=async()=>{stopSessionTimer();try{await fetch('/api/auth/logout',{method:'POST',headers:authHeaders()})}catch{}token='';role='';sessionStorage.removeItem('eventhub-admin-token');showLogin()};$('logout').onclick=staffLogout;
document.addEventListener('click',e=>{const current=e.target.closest('.actions-menu');document.querySelectorAll('.actions-menu[open]').forEach(menu=>{if(!menu.contains(e.target)||menu!==current)menu.open=false})});document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.actions-menu[open]').forEach(menu=>menu.open=false)});
const auParams=new URLSearchParams(location.search),auSetupToken=auParams.get('setup'),auResetToken=auParams.get('reset');if((auSetupToken||auResetToken)&&/^[0-9a-f]{64}$/i.test(auSetupToken||auResetToken)){history.replaceState(null,'',location.pathname);authState={view:'reset',resetToken:auSetupToken||auResetToken,setup:!!auSetupToken};auShow()}else if(token)enterDashboard().catch(e=>{token='';sessionStorage.removeItem('eventhub-admin-token');showLogin(e.message)});else showLogin();
</script></body></html>`;

const JSON_HEADERS = { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" };

// ---- Shop: accounts en licenties hier, betalen in de worker cohentra-shop (service binding SHOP) ----
const SHOP_CUSTOMER_ROUTES = [/^\/api\/customer\/shop\/summary$/, /^\/api\/customer\/shop\/prices\/[0-9a-f-]{36}$/i, /^\/api\/customer\/account\/billing$/, /^\/api\/customer\/checkout$/, /^\/api\/customer\/orders\/[0-9a-f-]{36}$/i, /^\/api\/customer\/subscriptions\/[0-9a-f-]{36}\/[a-z-]+$/i, /^\/api\/customer\/billing-portal$/, /^\/api\/customer\/downloads\/[0-9a-f-]{36}$/i];
const SHOP_ADMIN_ROUTES = [/^\/api\/admin\/shop\//, /^\/api\/admin\/customers\/[0-9a-f-]{36}\/(commerce|entitlements)$/i, /^\/api\/admin\/entitlements\//, /^\/api\/admin\/overrides\//, /^\/api\/admin\/subscriptions\//, /^\/api\/admin\/orders\//];
const ADMIN_PAGE_HTML = injectShopAdmin(ADMIN_HTML);

function shopIdentity(customer) {
  return { account_id: customer.account_id, customer_id: customer.customer_id, account_role: customer.account_role, customer_type: customer.customer_type, username: customer.username, account_name: customer.account_name, account_email: customer.account_email };
}

function accountHelpers() {
  return { json, readJson, digest, randomHex, hashPassword, issueCustomerSession, sendCustomerAuthEmail, recordCustomerAuthRequest, createLicenseKey, normalizedKey, renderAuthEmailHtml, loadEmailTemplateSettings, UNLIMITED_UNTIL };
}

function entitlementRefusal(entitlement) {
  const status = entitlement?.status;
  if (status === "expired") return "Het abonnement voor deze licentie is verlopen. Verleng het abonnement in het klantenportaal.";
  if (status === "suspended") return "Deze licentie is opgeschort, bijvoorbeeld door een onbetaalde factuur. Kijk in het klantenportaal of neem contact op met Cohentra.";
  if (status === "pending") return "De betaling voor deze licentie is nog niet bevestigd.";
  return "Deze licentie is ingetrokken.";
}

// Extra velden voor producten die functies per abonnement controleren. Oudere clients negeren ze.
function licenseRights(row, entitlement) {
  if (!entitlement) return { product_id: row.product_id, features: {}, limits: {}, recheck_after_seconds: 86400 };
  return {
    product_id: row.product_id, plan: entitlement.plan_name, entitlement_status: entitlement.status,
    features: entitlement.features, limits: { max_users: entitlement.max_users, max_activations: entitlement.max_activations },
    // De offline-bevestiging van de client wordt begrensd door deze datum; na verlenging controleert de client opnieuw online.
    valid_until: entitlement.valid_until ? entitlement.valid_until.slice(0, 10) : null,
    recheck_after_seconds: entitlement.status === "grace" ? 3600 : 86400
  };
}
const UNLIMITED_UNTIL = "9999-12-31";
const WEBSITE_CONTACT_CUSTOMER_ID = "cohentra-website-intake";
const CUSTOMER_DETAIL_COLUMNS = ["name", "contact_name", "contact_email", "contact_role", "phone", "kvk_number", "vat_number", "website", "invoice_email", "street", "postal_code", "city", "country"];

function customerDetailsFromBody(body) {
  const text = (key, max) => String(body?.[key] ?? "").trim().slice(0, max);
  const details = {
    name: text("name", 120), contact_name: text("contact_name", 120), contact_email: text("contact_email", 254).toLowerCase(),
    contact_role: text("contact_role", 80), phone: text("phone", 40), kvk_number: text("kvk_number", 20).replace(/\s+/g, ""),
    vat_number: text("vat_number", 30).replace(/\s+/g, "").toUpperCase(), website: text("website", 200), invoice_email: text("invoice_email", 254).toLowerCase(),
    street: text("street", 160), postal_code: text("postal_code", 12).toUpperCase(), city: text("city", 80), country: text("country", 60) || "Nederland"
  };
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!details.name) return { error: "Vul een bedrijfsnaam in." };
  if (details.contact_email && !emailPattern.test(details.contact_email)) return { error: "Vul een geldig e-mailadres in." };
  if (details.invoice_email && !emailPattern.test(details.invoice_email)) return { error: "Het factuur-e-mailadres is ongeldig." };
  if (details.kvk_number && !/^\d{8}$/.test(details.kvk_number)) return { error: "Een KvK-nummer bestaat uit 8 cijfers." };
  return { details };
}

const WEBSITE_REQUEST_TYPES = {
  maatwerksoftware: "Software op maat",
  procesautomatisering: "Procesautomatisering",
  website: "Website op maat",
  overig: "Verkennend gesprek"
};

function isIsoDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value)
    && Number.isFinite(Date.parse(`${value}T00:00:00Z`))
    && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: JSON_HEADERS });
}
function hasPermission(actor, permission) {
  return actor?.role === "owner" || actor?.permissions?.includes("*") || actor?.permissions?.includes(permission);
}
function permissionDenied(permission) {
  return json({ error: "Je account heeft geen toestemming voor deze actie.", required_permission: permission }, 403);
}
// Huisstijl 2026. Logo's worden door deze worker zelf geserveerd (/brand/...),
// zodat portalen en e-mails geen andere site nodig hebben.
const BRAND_ASSETS = {
  "cohentra-logo.png": "iVBORw0KGgoAAAANSUhEUgAAAZAAAACSCAMAAABc3mxBAAADAFBMVEUbY+ZfbZYRKFsTKFVdmPcqn/RZa+xon/EWJ2MaJyEtXGghVqRemfIkauIOLaNZYGlRWWooZNtkme8lYd5QWGogU6cYaB0OI1FUbvdNZ/Zq1Ps6R18dTaM3Rl5YYnIhUqYRFihbbo0JNpdaGyA4jPNeKGNqdIcLNpEKN5Oc5v0cJDpJZO4kKjx0gpiQlqGVofVxx/xokZYVIeQ0iu5xcQp6y/x4yvxudoWfpa6Pkp04iOsk4PSZnqgA/wCkaO6ZZa14gpOYdHuGy/pqqmr/f/9/H/+H0/za2tqAnPyE0vyAkvmBkfc+TGE/n58A/38AqlXEwsT/AFWNABwAAAAPGTEVJ0sWIjpvl/wiSYwpWKsaN21qpfwwaMprivxXdvxTavwCCyRLiPFPl/UXSq0cV8o2c9YuYroDAjM1eekAAP8mUZsLGDEKFS5NV2kaRJBYpPobUbkBBhpwtvwMFy8AAH19fn4QOowMFy4MFzAvN0w7g+wMFS1MWGkkQnkMFi8DCyQAAFIpaugCNzdNV2sECyxUVVYCCyRTWHIYMFwFJy0DCiY5RFpPV2p8fvs6OzsA//8kLEQDCikLHEMeQH0BCiVFe9YAf3////8XIzkAAhd3xPxES2JMWGsJGxw3OXIABBpaZHYIJkwmXMsEfvxWZHZLVWkIOnQAVVVZZHUOLGgABBgJGE5MV2gtN0wqOExMSmtIgtsuNUpiev0mJiyGtf1IXPtVqv9FSlpRZm9qc4MnJ02J1f0YIzkBVaovVXkrNUlnaXlrl/ciTqIgPXRTVf9Mpvlja3ppaHIZJDVpdYhZY3U8evxLmPk1RloBAxksN1A7e7r/AABsh/gZIjqBpPxETFyDyfw1SGgZIjhcsvwxADFFS2NwiPH/AP9VmvlSd/gEBhsjKTpQZvh/AAATJUsaJUc3AQFQmP8XNlFVVaonS44IGUpVivYXSKhRavktSHZDS1s3OlMzZmZXeHhbZHNLR1Q2R1APMm8rNEo7RFgcSqRYdvoHO5R///8wetNXdfj6qx4WAAABAHRSTlMYFWOgXhESGhsaExmeXRMiX5/X5JqbBNJemhleWZ7g2F3kXQZmCFyf2RLU3Zf3KRNXFgqXAtqYovCc5wVKAQQIYwurBAIDyw7/aJdB2QgCA6UDCQD9/v3+/v7+/v7+/v75/v7+/v7+Cv0B/hHP9/39/vv+TwID/Y0y+/6yrv5trAX+BSwsBM0R/gtt920DBAH6Tvr+i/4CAYqR/fzPCwWs9Q3+BCqTCgNt+9EQUa0rEP7T/gv8+gTuEfUK/XADB2ksDv/9BmrzCzEnzQZnMHFQBQGvSf+s+hCs/QVYEgFWLi34LwIxSwcPEAOwMg2I1KrIEQULqg8Tzo3Te64NAgzT1Q0ULwAAIWtJREFUeNrtnQdcU9f+wAl7DwVx1NXa3de+9vXtvf7v/fc4NwEC4gWLISZBQwIJDQSEALKHCKLIEMWtRds66qzW2lqrvg5b277u/drXPd5r+/6/c+4egWBF2s+7PyvUJPcmOd/zm+d37g1CmnyjJEgbAg2IJhoQDYgmGhANiCYaEA2IJhoQDYgmGhBNNCAaEE00IBoQhMJAtGH8hgAJC5s373sg80JDI36KkFkbzokDAoN/KijuJ3di+UnukiWTHghDXx7XxnOCgJixdsRNzr8zJxfLEiyTHojQhnNigLTA36/iJufl52ARkMSGTkeoqUUb1MsLJB4fFZeUlZ+Xn3/nnSwQlkls2PSftlyvjeplBGLu7ATtSMrKw0KA8EQwk0mgJNO/1JTkcgExdxLtmJwnBiJF8oPvgoZ8qQ3sZQGCcVyRsjQrKy/LL5H7nvzB9WZ0S5c2tOMOxOlEBwkOInkckTslRJYU3nffv/zr9ajrXm1sxxeI8yD6eUzKwoxFi8RE8mU6Ao599X0YyZdIC4LHE4h5CMKrlNlLMwAIh8QPkcIngch9v5mONKs1fkA2IvRF8KcFGUQ4IiyQfKnRWpK5+r4ngcn3pyPNao0TELMZDQWnGtMXL+aAyIhIHPuSwtVPrl69Goh0aRnJOGlIfPCnxnSQxVIVyWKBKIlgue8HLS2a1RoPIEHBIcYV6QSIHyIyN8IA+T4YLU1FLjWQDxCKDDES9ZASEUKtfAWRQhCM5LtoujbAlxTIfsARvNlYll5Wlu5XRfIVRJYUEgEgmlu/pECmQGiVCjyOlWFRVZE8NSIA5GlMJBQ1aWtWlxJIS2TIZuMxo9F4jAfi36+Lgt8lT2OZFBqhpSKXDogTW6tUvZGRkVVERIQFwq6NaHIJNcT8Soh+s9EoIiJxI2oqwusIwRERoVXhLyGQgWC93iiSMqVfz1IlAjxiQ3+KTuFSVldLV1NTU4vmSL4+kOAQvX650ShFIvEiitCXEAGJ/XMLaoLwyvxmE3c2XXi4NtJfB8hQfTvwkKoIEElXJ8JHWsAk/3vzfoqKzoKxaoIWlL88GxEx9fnnn38WoeNN2lhfPJA2Sk9EoiPHymTZYYYsFwEcSfPC0HOnAEfXUYQiQv807R9Y/j4tFDTkaymJyVTJBhsmk+mfDEgleru9Xa9CZAVHJF2qIryGTI4LMj93ahCsFajD0dBJ83nZdePUoyj8Ytu26tbinxUWEBOLZ0yHw3F1dRbTtxXIxq3lHA+p0RKASFWEBQI4Xg86BSjM9zZh7ZgvlT+Fghm7mLykAocYbd7PQqwgnqdcXocFMwn8BPU1+Miajm+tyQqmBCDL1ZyIUkWylgGOsK+CvoKAKuI4+oUCB5ZYCLxOXQwR9yorTRuI6PUURVtdjinIUhHY0dVopoGCIynrtxVIZAelVwfC1nzF+TrhkZU1OSlocEr0V53Yj/+iSRUHQfI6umVszr3CidrKaQoLpqHXw8hi8ThMASpJMyotIUA831YgZ1rFQKREFCrCuPWkoDCkexO0o+nZZ4/6xQEyCexW+JiQWDpYGiLBD9DlbmRqDgxIKwU68u3VEK9gsEZVERbHINOxhW4OHxEHcSVTx/DholCblcCQMKEYodsCcu4sEOrbCkSHOmi9XyIrCgpEkS+UT9YBDu4Uul/eHBE7f34aFubX/DQ1u/VswLEuqqcpTrADIf/xj9D1FZX7Rz1J7zgDaXY7sLT5xktDasulQBRECjiTtWhRRkZSXAxb+rrlaFMEjnTTFKK0W/cGzoMFgH/SILy+MET+F004EIuHfBZ7x8A4AalaIwOiVwOCNWTp0pS4QRZH09GIo+o4VIjMjw09FYgraaN5c0XRhvKO+vr6jhsMNCUoife1wEwWNX5ATB5mvrgqxxFI+2hGC3ikp6fwxqoL54HYeaSlBUYkJzbi+C/MoyBx13B+g6I99W/vh2/sjH7j7Xorb8Uoj2WCgVicoCHkI44bkPUKIBIiLJCCgpQrBvGiCSL7RW759z+Bv0jzK2rx1tHBU/eOgGSjqZxz5JS1vuIg/0TLQD2ZkvB4uS8gp85oVM14AKkzYQ253ECkOgI8CgreujIIdZo5HhH/ljaqyFQkJ2fSnyNQ2Jf+l4+xwWImHx73On6AIbLyWZnMYiuqkBZ9WJb7neLEkAMC5q2CfUmzU+UtK9ko2rlbnnM6OzvFb9DMBXdFt9dGEh+Cgax986rqB4vYZzqrqzfi37srFYUp2TkuCoh+ubBUdWxFgXH2lbehc05+e9stk9LSLoJILk7d/enIFFMN8RUGPVVuko77bhP2pMCpQvw4IebcaqmzyDN1Bghd89paPAgDljonW5CRuAJyvGlggPnttwywEY9oF/t89fuWLuRhrKdKZaa6jqxhTzGLlmExk4FK/7NCBYhNBQjv22GFffN1oB3Rg8KqU8SkTH7U/xgADz4qTpsESNSJvIy8jPMm+qEMYNZ67B0VsolncQevcrlcq0IOn4Rq5FpuFqMneCBX+Rwhq1bhF1hk1TDIMSvcZz6Dw103HT6JBI0sStzU2NiY2LgDP+Y+/NmqVTcdjuKerz2S2NhmZd2Zu3HTpk2JcOJPZjRugj8zqkBdfGc+C7nJ6xZ8jvsw8wkeewFXrr8WkOUEyebUK2FP29Ah4YBnY8ng5uSsBJmf9vgf/QJJmy/z+5mFQORWtZXeZks567ch/4tSecEL9eJvc+Fl5HZ52PBLr4diFzx7QQYEvea1MpAN8AKnNMJGr66y8iG2x8urWfRnDSUNJXtKPGiKw2UFfSXPO9g3n7mmhOLD8pKyNQ0lMPaJJXAEiA+562tISOJg6bsPeCi9ntF7q8utWiJVBUK+lYqK6I2pIfHYpAovb0J/ZnDctXIlFLWybgQk/rWE/cvxyCwsnDQdDaot8e6g2JywI6AioslbQ0mkvI39tjyQ8qg+8QtcJt6eXw0zuUN4hia1Ms4SunDyQ9HddV5afLSFnL6DpiXvSlOPIdTYaqfgT8n//NjKPGtnPkuFwyp5sdUVsIZQKkSWg4akzrwCXEa8+OVNR2Nz03IZHgAEcsWs+ZmPB+JTgEdm4d1PAhE1IAfYZGNLQBmwjy1AUqJi16OM2epkgcAA0FzGrzcQIpW8ZXfX0PzhXIrzMmMLV+HIQk8Nz4QhwYUC9gVgSGGmuIQInMK1T+rFOQCkhIZj7CU/6qcZf481xIksLop5kZ55fzxHfEodUXXq+NXtchz69pArTL+Ldso2rB9Ny8U8WAUBIEszbkx7HJA8/ngAQIBI7HQ1m8V91XJTAAsm3HgKo00mNXHUfJTFl4w5aC7OH6G2GpaV8JOi6plwCQOBPyWt7KEUf3YYCa+B4swcU4tujWSBwEMvcicFIJVOzANewH88ojp9JlNAiSElIwI42o1zvxODYnojkQzI61g/OAXBQDIWFmSszLz78bTHMzNH4UGAQMepyiCXswP4WQD1Q5NgCmi7nc/k7R2vmVggBg4Ho/sGA/nfNtZ/uLfwfkBvoLgkh2KsFtEQ5iExWKjbgMnzMobVwLGkXozigYhUzoEs1V5sc8h6jrgc14GGAgDCHiBy5+3L504qnHQLikGKSzrcm8sZLMZiYSkoyJh0990AJHNUIIVPro5VaaljfDp80cTReax1cQNOUw02W4Oo1gXBECSGeoqf+oaSEgPF/pPJ3SuRpY8b1XJXcLCrnBthK7GWcwxCvYBq5ee3gdoCTrmtvK+cHXZrebnH0/cURGibeCDkV6sBNKTLV0N4gMrDexzooDms7opRgexRAGnfvGhSYW5eig61KPfyhAGQu8QKAnI/pI5z0+6+O3MkJCyQ1YVqKgJpOhm4GjcKoOTFzjl734HEa3617UAf93WtvkonX37HPzoOzJgRXM4TaSPxq5flUTNnK1ihCpODyb31TGpxgFEPPHjd3sOHvR28G/fCvPGZLFymbrH43L7dG80osYHmK6J9Hd453nofit7O+Biqw4cJmHj/7hrVZCUoNSR95aS7Zi8uSIlBTqWGvC549Kwslsf9QKT4frBbmWmYCPPTD5DCu1f/QKkiTFpoCMSnW6wUO2/rLTjDh0fqhTGr4zQET3lmOloc3NOe5+rQyz7GYFE1PtT8Mam1rPUwxX7KxwPBvNpMpOuFSTzggb43SID+FLNCzI3scxiInkXsJa0VMGqWYKKalOsCgoJB1BRcqGM+QtSYTZYxY/aixVAuSX/rC1UgOSpAcHWlmEeSqaopHJDC1d+frpL4MZY7AA1po4lhxgkL+ANIxqLMJi5EheJjLwcEeHCHcESsJkjevew/fODdnYyTPwn5CrYv9SINqWnjFs0cjE2jSk6jQ6Y6y1MGSXGxC12DgRgoPX8Ilq2nzxxw1YhClO2sEkeNVUNg6WMxrrlD/cofELBYeXKLBVJsLMauJDNTFQnzGLeRRKWozQBxjMajcruBcbouUQJp8rBEHLDHhXPqLrSbi3PLOQivsd6KC6q4VVMGiCcSmVexR3vNomcZt/IqjPPA7qcYb++6wGkIAQI86Hr5LHtBFKH8mFlYNjw2Rg2BxUFm0bYg/a/x/oBwCsIBKWCAFBs3F2ek+SEiBhKqFvYa8CQr2TBqvdWKjQtMNZF3XIscNGez9vNhr0+5EulgivzY9Z7RPQR/dLqEI0eOfOhg4ufW/ci5isxkuuQZ4eRubCQZBaqrJEAk6yGMhkDNxyKvl8L0MW3V6dZXgfyQAUI5AgYCYW+7MT2D5YGBqPqQMAwkT2yxMtI5HlBoSS1emZaphkQEpFAFCBv+G0JGW/Fw15B0TeYd3y9h5rWnFnFArBfqhMIL+x0dxHwRH2ETpH/YY2BOCo0UDBB7/8+ECuFAiEGvF4Cw3lkKBJAEy5YB0PtnVrk8HpttzZ6Ghga25jI6EN5k6Q3tRjBXIg3p9QOE47FIDKS4ePPmuW8FB185LVbQEYEJ909/QA63sqbbN2IHnQnHWPjr45hHJHttFPEcqVE8EI8kZmActQCEYteIaVqc8bvRkIsBsudW4eg3tus5IBbLbg9zAgFIIgOkZJts5nhvaDVI6jOBAeE0RE9hHiAckIK/DqkCuTMnL09msTCRzca3gmN02F1ff0tobKY/wTyeVgESxfpShSFmS/DwUd4nFtmBgcCLD0g7A/rpkYBYrMyAEyB8xmcQdxzpmedZIFS36OgBAUhdXZTHIAOyiQChG6QpFFsV5monfHboCDBTB7tsJAPMqQgAUdeQ/HyOh0hDNhe/dWUMLAZcdfVBvGYD7Q+ZhX6JPP2AypBz1d4an2pH3I6QSET6rh0049OlGlJtYyx06m7BZEmA6MVAJLOWcQkcsErWh9ykk2gIF4RZAIjcZLFApBrSRtPMmaW9TAEAYWpZmEfG2IAs4oDcv7D4umvjg7qqzx8ikUkXvjJQxAhK8vQD/6VSvuWrC5bKtXJHjleorG0WtN+EHDVMXu2SPP8KkwwahqM2+gFCCigCEIgKqIYSNl2DX1YrEyjXsSbrOz8ThbACEJPF4uGrxzwQSgHkhS0UU6+BHg0KtxpbxwqE0mcwPlpwIjAnzX6AZImBFF93ZTyc9pBoTjU1obDQQj86krnkAeWVf6e42do1lKTkKznQReqyAyqPu9LERkkweBYuqoXxRnPYg2+C0ohKGxABoidA3KxTP+AL/vGPSYuVg+m0cjzmcFtQJQvkvVvFQAwUD8SkDgSqvSIglS7281ifaHO4iZAFuECiLFJ+F3hkcDzSjZ9GQpalCiRLZLEKZl8RD81BB2VVlgh0/W+eVEWyBID8RQGkSGiSoztAQ0yscpr3w7CbOpgKovWmVzotqaz5r4fR4VVEyENGBcIsWsH//gGZ/iCLUmHJdpXSh1i2k5I8TZy6CpASWg6Ey8utvgu8DbMbxgDEQKXzMRNHxGgMVpQmRUAWEQ1ZOPtvMTDdDypVydwUu7pQjQhcYktFQ2A7SB9PpM9tYraFkLXsAUc5X9F1oLpkrnDlBs2ocDovmHC5kR0AN85DSvwC8aLOOva1Vstvd976QQUuc6xFvnq3Ez4BWQ9hzi5OKga240f0eMXFVMGZrA4wlE6ydLeJXQ95RmKx8PcgkUcF/haWq11sEfmxwBaoNi/ifTQHZIUxJL6o15/J4nEMquEgUz42NzdTiWSJPyDIR3NFQNiA4H6DmYFbT7663cpVB2FRYmvRGS5EsnILq+4OO1e6c1b0jgQEePJ1FOyELBUVJlBHXw1tvcnNLlAxdRLxuowlhDwGQHALvoedNHx83qgEMocAsbcGmywbnU7YBca4LkMgmToB0p6et4jzCYLNMgabq4dkg23mgWRkzL4iBtz3IfVNt8dbYn+SdxdhogSifvU5L83XzWlq+LM26KANTh7m1jUMBhqmrcWJXHbetrWdjDrp9lp51fLh7oWP/JgsA9YQ6GDZwhFhSy+VDmxgaOuqF/wAqSMaYrA/Cm1ZvFOHdvzm9wd2fDICEJFdY5sAwRaNarJ0GIiRM0Fir14GRIZQhVkGJCcbm6yMpbPfwcaq098e6MHBlKylsH1hZY4UCQbyiCqQ3ZH1AhGxMDz0NImIo2B9ieY0ib5heFjIuewd8bi46AeIgQWC6jmgN8xxREW6HU8xyaHB3u1kfIgcyFamMAhATKYBtIqjb/38veHhHRiInQAR5SFRPHR35P43It1eKxP+6gPQEAIkPS9LqSGYCERa0ti3JSw7GzRk3VLogjcXxXf6r3GYU5YuxOdbl5UjyknIJbEf8bMhdAA7dmEvggSHgeaTeIddlZu93BRlGh3IRlMfr2JUKywncaspW15AHBC9DIiBAQZHD5gPG0SNDoaTPJDWZ2QNwOQzUcOffz5sYJqWCZBXAwBi0C/KE4WxIiIrjJ8GSxdxW77KycZ7RGC/57nOzhGrTikLsSxduvQOQEJIsD+XPOJvbXajgzc/ku0h+Ge5j+u96vTStACLw2LvIymlqsmqEwExIR9LxCBZ77a3IeRPQzgga9GAzm3lFxENHBD8bMkMcSXILqxq0twHpQICcsRGU8Y8kckSASGO5FOwW1P4vizz0WyMY7Dr9lHvVsEBueOOyXdk5QpERgAygNx9FC3frGPAX8tlEsrtU9q22MXmDI8nzfCANfXkVtXEkAFCasSEiIHdM8fxeJRkP1zYK3HqHJCBtRDY8a6ODLGDB9IqADFdsHTbKcmSPHRNMAe8OrpTt2OLJQIiJQJIQgBJJ6coryclxZ2F9qzRr5/xDq8h6+6YnJWzhCFCEkO/x1yA1U5AQouKQLiTwVDe5kTiOrCvjxKPKU1v4RrpAEiJYtNnnbWVDXuZor2pm+Z6dAhRu33LHCdpd/r5KlzWaqU8JvESDLSgQFNJdwVstq4wV3TY+WqkIQqHvWCyXpQ4dfwOdlqEg/bMuAGvb1D6UYFU2ez6xZJSiODWBVcSvNfMbfALOhtgXzejIURFAMm6nECAIEsvVFG6SyiuDAttJVRN9wFZcynMVG855sAUbeEVPq4tsBo9AeMLIu5+X7uFlHbBLXONi20dNXzJF7+Dmz0ccmzyyj6xhjyFH6Ht3YSm02x51MpWiu0U7lx8kbzfi4elYXx9DRxDXmQnq81bsPGy022j+pA1dv2i/Cz/KgKXoTFuPhby9lVjbbT/G6sgLBGiI6MCQTisO7fD29Hhwf2ZDTd0d5BWWdkyCfzzqse83VZ4zQ3lHd5XxNeZSiz//Knuvj5JN3R3OZZu0Wi87PZ2eEpKWksahru97uf4VtI5N9hS+8r7HhWHvXP6hlO7y/vm8GtiJ73dw3BoeTfuQT0zvAfLTa/Iu19hYkEB/sUX+1xuM7J0l9j22PZ4fKMBAd0SgCxSUZEVuOda354aPIAgybkYIHcQyVqWywF5ZOQD/480Ee48vQOkVqhqSAV3HMSf3xG5IzpaMcdiIg5NQeeQ6lXBJEX7HTsiIyNroUodxU+3L6On/GeEsBuCLQR9qDsbdZu4wtb1SVTUDuadzdFDQ19ED8XvVrzdgzuiHnvs5I69EGo0oy/PRgf1Rp8dfRfuoywQqYosFvkQLNCrFUICro0XCWRd1rL8XDb0/fMYsO4e+8aYC7VXvz+WmbNfupX0OZWXRH/88QhLmc21h3ZOUds7JCteVE85F8C26Da6PS8/S1K/FRNZwe4TKcG9pa8OoEMVYwKyUKQhy3Jyxw4E/dNdDQhKCXnyirrIjXBAyPWb2kPOwNQbukiTlZ+vAQnkWieP0hl35skWnfheh3QjDwT3NOpTg7eiocDswTsSBSFAGBXJ1YCMCMRXU5CbJyeyWCj6ioAQJQEkyBkYkKVL5UBwW2PuIxqHES9gFlzMNC7IiEiBbNYLSN7eGAgSDETQkHUskDQNyChAzPFbr83K5XutFEBWSIwWJqJPDXGPfudD8ztSF8IBgatmakBG1JB4pEvK4butFEVfAchyQUmwK0H7m0cCEiT1IQwQIAJAQlUPaWlpMfstyBSpXwvNXASifoTKAUWMdHV9w03Wmy0RsTk52Sv9AOGJLF8u7OmhUoMt6GX/19F783fxKf6B+L34SUtR9Vi+TRF/I9JLIGbnNwWIOei5iNDYlfkyIAoVMYqA6NupkOABp7+kpEn3bNx1QilLDASIzFNZD2nR1RbpanUPqp/vwSM61dJN7fqEqtqrVY/4UHGqWmixXX9Et7eo6EOVAzY2qyt8b+35lst+3V6YsV+FTs7j1malga9IRST7ECnw7n7mWlPTs1P/sa5YDQjeMjpPpzxmb/K+WSdmzZqbHK12xvUPz1U55qptD9vW2Ho2qBxS/cN918itVlUP9PGe6AdJflCuVUUo8YkZO9XeOuGJGb2X/0LKZqwnSayKyCuMPJHlsp26lLXjFdUrWJnDp2Zn+wWSO+9WlRF8r3/fw/375tp6tqmc8MiJfQmKB69OhB1ts3psa2YpidRusDXKB72qtKenf19//8MnPtqruN3v+vfKGqrUql+Je56IHMc7lfu/9vu9LWeDklQXDv0C0etpfYhjx3n5ucKf/3t2dg4HZKko7MVAMlWdevUsW9WHOt22DbY1M1CRCpCHFA5kRsN/zIg5HxM905Zcq1A4FSCdMTG115zoWa9iGKvRJts+2wa1e2tus5VWTwQQInCLbpW19QKOyHIlEWghKhk+Iz3L89PezeaBLJQDyVUH8vF7e8g8P9TYMFM5UxNmKYFUfd7wDLodD35jo8LYJKgAYZZ/SmvVvvnOUts1ts/fVwkbAMgHEwYE3/l2dobcq/NAjGqX4NDTQsc6/tx/mfqP7Oz5CiAkU8/GRNQTQwKkGr3fWz0ThlIViGxUGm0zz/v9HtWqQIoASE+tUgGr8bD/embDDEW+C77FVho/cUBidCgoJUPadj2CzSJtAjX1IhzhU/++axe5+E9OlhwI70T8ADkNAwNdI4lrks8FoCE7k2HIzyPdQw89dPPND7UEpCFFjIYogDgTSuHlMxpmKvo2ilDCxGoIfgFGIl0UKfMHBO/D8LGRFdEOgoMRFghvs0YGcv6JBgKkGT2zJrlaxYfIo6xDG2yJCAZ37ndASk0BA1HRkGp42FaFPvm87LQy+gIgMRMJBKIthK5IkbqRsjJVIOSqLWa8nmqOD7+N0w5/QLDNYlJDtWrvJ+8xQKqxhqgAmXVEHmPhIYfBTZ47d59tltwxTBmLhhQ9uAEebm5OXpMoD5Uxq4nVEBxZHESDDBK+ibFMNTWE6xpForV4Ka2pFmtHNvDYNRoQIKIG5Pz2htNwhTaIfzao+JAjJ04owt5t/aUfot6Xi3ToR/uS5fpzu38gO+VAYNB7+nv+OnNmj60nurNXCSSm6M2fFzkn8l64B6+CG6nPFreVHpN7dcBh9ToRvqCbLlyHcSzIzt4F/wlAChaqOZGcnDSVTtKWmx9uiEZFv0Z7N9lmKaOs9f0nFE59b4+t8QN85eGEubaZCYE79b1yINFoUz9coqOhYY2tbMZ/K4D0l34T7hYddA7FpMzmiShsVjvg2IrbxyEJbHozfOq0BdkABMsuOZCFvIawKhKrBNIVffOPhmdUVV3zq4/6bc+oZOr9/TrF+CbabMlVtdHbSm39yfLyyW/9AekpVQAp+qS0f1NVwunTVTPL/lrrbFYAqa2t1dV+MsH3U++FC8/EpCzOkALheVhxxwP2pE3Hfx8eOu3GBViyWcnJEZushWINwffRnadmJn/2ozIbJNLf2deTqFK+TZg1VwmkdltPPxxjs310IrkpYB+icOoQ85b1MKni6YaGGVKbRfz9ww/3PNyTvHNigYDdigG79Vb6YsLjmCQzTMVVrEqwqoOncB64YJeEByaSowpkGb4tT45a73vXzT8sxfLRpvVqn+VI8g9ValmoalNpT+mGbXsTlRcRaizdplqN3LBhryIL2VbaGP3hB83NtW8c3n5GHnInJJcyQKInGgjZ+hEPSBQWi+CA9hzzWZKWYxZiHCwRdSD5Od/7i9rYJliqdu7cuVeHJ6VSomsTfqlafa+tPT+Ibr9VWb7dufOQasE+IUFRu51yaCc7+3t3Xv2JvObbuxMsVm3Cxx/3TjwQ+DTPoZgrrks3HjsmLOSGvBJPdvGbm36Pwqa+u2BXtooIiSEPZBkD5CdhqCiANQ4U2N1byIf84FKNTjVC38j7qYsXmuAzxl9rZFL1zZuNetIuV0l2EULp690F2f4EgBSoAYm7V6f+VufMnX6X/5C/Vb6ios6xgS0yj9jRqBLcOpl1Ruc3AwhzU9b44JCQTz9NDQkJfoXtgh8MDxqMm7aAj61UgKxTAsnPXxY3GHC3NtLup+53sQR9MRQZPzTE7UkYPB4eHpc0WerJVYAUFAhAJmMgy+LC7g3TKHxNIMpF66CgoKR7FrAyIhCBCAYyOa4FaXfMvQRA5Gl10LTJPA9/SACIREUmT16WNKgBuPRAzEEvTbvnHjEPP0AyinkiCzGRpCBt+C89EDOKS7rnHhkQVSg59xcTIiyPyXHa4I8HkBYUh325goeCSE52QbFABG58iA5qoz8uGhI+eYG6SHHkrCzmgVz3Dryt5j/Gy6mH3zgqEGYFl5Nrg9C5IO2u9+Pm1IHIPaMQwUAyGBrXXQs1yi9itJEfPw1pQsen3TgiEMyDcSHXXXulGR3UvMf45iHhLQgi35GJzF9EjBXg6NRwjHtiCLeuv23qiEjm5xRgHLdBD7PmPMYfCHKG4w6sG/0CmT8/g8FRoeG4LECYu0W/NNWvb8+CKzHiq1BoA365gJC8YvClaWpAAElKzCXbR6MBCVhJoLHgOKwYwvhLibw7LfyshuPyAyGLhuBKGK0QJOn5UxqOiQHCiMhuQeCVFHRKG+WJBYKCXpo67V3oBNr1Llz5LwiFa9oxwUBwZhIe/tJLz4eHawP8DQGiiQZEA6KJBkQDookGRAOiiQZEEw2IBkQTDYgGRBMNiAZEEw3IP7P8P94MAbjLo+3JAAAAAElFTkSuQmCC",
  "cohentra-beeldmerk.png": "iVBORw0KGgoAAAANSUhEUgAAAGAAAABgCAMAAADVRocKAAADAFBMVEUdWtkcT6sfZNUlVJwiVKeHo/0lVKEyPnkVUcaDmv2P3/AcWdkVLtAADCqIk/961P9su/eZZmZnufxmsd4oQHUgQXscRHYdQX2In/8ZPoUPOo0SOYIAAKoPH0ANH0SW4Ptxxf1/v7//AAAA/38A/wAAAAAbOG1umPwUJ04jSYtrpfwqWKpXd/tOh/JYbPwxacoQGzZsifxPlvMaS6s4dNYvYrkoUpodVch+f/84eeggQXwZRJVttfwAAP8cULuGpP49g+pUqf4YMF12xf0BVashW9EAAFRUVf+BnP0DCygAf38oZ+gWPYcA//9Ee9ceQHtUpfUAVVUAAH8CPHw+fvwbRpYRID5///9YqfdIhNoAf/+K1f1Ohuj///8XN3FieP97vfxVVapVaf0XNm8gP3dOi/kTNXRnuP0SNHNpmPaV5P5UZ/pTZ/pUafuqqv9th/2Cyf0XRJMKFzYLLGwbRI5uivpRePdphvw/f78ABDROk/oTNncJFjRUh/ZadvxWaPwHEzQ/P79XaPxPavkAPz9ui/xTk+oONHqGtf5rufxpx/8AGGkTLmRvxPpTd/tXdfgEKmxSpu8QJ1QhPG4NJ1UNJFWq//9zpfg4hfAkWbE3hvAAFU4AVf9rhPx0lvIsZ8hvmP0qadJjk/x0lfwiVa4mV697kv0qdthyp/84jvBtrPhkiNUsatOO3P0gTqd/f3+N2/1IXPlasvsiTJYVQIohQHEINpIMOosXPoMYPIRLdq95xf0KP7QuZLoJFzQNKmQnWK4yZrRacvsoWa43fOkALItRqPZyyPoPGDRPlPVHhec2ZP9xiPsAKqpanP9PlNxam9cAD0hahv1ElPpMh/tVqqpQq/gQL2lbef9No/FcdPwSLmEPLmoOHDoTLFwPKl8IIEgVKlVLs/WC2/mF1vxetv9AbL9V//9KX/9mZv9ISOw/v/84k/lgd/lifvxpfv3/AP85gd6JwPsvc/c3ed09e9gDG0U5dLiL3f1mmcx2kP8ya8kHHFByqPtyo/lrofdod4K+AAABAHRSTlMfbmOsKdLhEqucEuQFHhcYaAXFtT9Gmc99zJBvA/+7U5sEAQIBAP7+/v7+/v7+/v79/f3+/v7+/gL+/v78Af/+/gT+/AX/AwP9QwL+/gH+/f4DAgYFzv8CJf4C/IQBbP8FA7LK/iJPJauI/SpIcgNs/jKzMqsvD5AECyKSkxnT0zAElxME0ost/ZAODtJyTDkP0NFiZlIDubKLRBIDrguTMtNptk0uxzUNKiv9dNj3AoRJ9IpKYhQyTbH/2AzUQU25bZXMwhmXXXTPewlOBh/9w2PJoVMDT/+spWCKYt+ghT8MGytYI/8DMAUOBC0tbYMBR6BAoWNC/7AFRbViUGSDnxxIqgAACdBJREFUeNq1mnV0HNcVxlemNJwyc+/MzszOzmoWNKvdsSwLK2slWQZFUiyDXJlr2bEtu4aaKcbUqSmGNGkbaLgNc9JwmZmZmeG+9wbewK7A8j06R/pj9f32u/fBffMmAuc5IkP8nNnU1WSeP0B1tfXLPC+ALpQ9XX1L9V78u2P0AV1zAU7sfEHX9cPf+Op7oLowuoAmlP/4MZ1GW1vb4SsB3lkYPYDZgPJ/Tk2apKqqhXj2hwAfHiWAid8+ciaVTfGEe+7Zfzl0dIwGoBZ/zmgpGgTAEHpbze1vB5hTOFcAkT+e1jAogHpgJvSaxX//0ZDzFCkqf02ZksbwEKw61CxefNdFQxyxoYCpBZjWM0PBoAQCyLoWkNHdvfj2Hw+NEAJobwLoe72U8QAsAgPoNd2IuAvePxKAidnp65UwLIKVo2yWs5Dv7+/vXvzcUOoQCSb/6oU5qbJSyrgAjQEmcSOJxl4oDBPQDnBovSBVtiKAJ1CAxwIFPAdzhgfYDtAjVAqCQPSDFjgCAvDnHcMDTMXs9Aok5luAgAWnznI+j4D9QyhzhNM/+S3BCSncgjMZ8jX5PQuGUAIHUA9w3T7BD/AQshaBpii/B9fVwtCHaT2c/K4g+AAeC5pjgQCeRfmfdRSqDaN6ujHXHBRQD3+NTo5O9gN8BMuCrn/p1wC/MgrV7pY6CKAdvh8lwREqOYDisTDp2C2oaJgGwJqXlw+cGvjt6i6AhlKAdrg0ygAuoVUKIRD9YydQvsvE4bNmoLxcLCexYzmAYZQCrIxGwy1IFoARstlnTlApTMm25ZY6CfHUQcTeWTRFm98aBLR6CdTADWOwB2iA6lnw0vIdrjyNU79BhBkKqIcN0eggFhRF024Y8xaySZNcvPyxRp8+xsDGsGpTB98JA3gJmjIG18HrwUCJf6I8RoBQvnwbbRMCgM2JmaEWXEJaKaslI8XA2q6+sbFKZBEgkGpjAr2Aengs4RJ4C60O4Pg4lDfJ0Dl7YWNVo+iGjyDuWO3LEwG8NxFuoZUSMtK9K3CfMAFzv/rCKiLPE3wIsXzRRjA6vCkigHALhLCKyaP+6Tc0oj4NsQRC/AifJ8tBIhFaZ0se9yHUXz0e5UMJokdfFI+edbvkEIBLqJzxAMo3kc/NMi4bT5NfVUUwfoLLIH/L8p6b7Uo4gJlBQm8fNr9N9nK2qErU1c7OlpZyRIjOSAoLWa55eIFFcACuBZvQcw3d5WgYcJko6whoSeGcJoiqqlIA3O4uZ1lyATN5QlRYz8ljKwr/zaMBtYUA0oqGmRLlKrkEoPvhOR2zigGi0YdeDTCNG81z4H+ySA1QgKL8FBGyLBcFIGEP3bGtYeolTMh374d/8NPFgEUWQGOAnNRCHMihEJn1BHvJ1HEdOFWo7GzrTD0Ja8HjYJHsZoiElJMekqkLOQRACVeQroZzwCwImXQmJwgf8mSIOuAzhPq5ZkG6jRH8FAvwKpgVBAgZiQ2hIMBngBCEzG1yCEFmhHw1EngAJolu9pWtAQfTYScBpHhAM/kiX1Pk3QEXskVYgF/MA4jiykYiFCASgGZniDjATC7s+cK9R3fvlj0+ZBtwpQ8QlRS2QFcKrZ/yA67SGSBtlyCXe7CPfebWo/k8h7D/yMsM4IyimRklkykFYBligDtyq3aRfnP7ugtwwv5nPGfCAfgdSPiPjIDte08owM6Qklt1P65T1kzHGXvzH/tDAN4aSJoDwAgDpBzA2BXuMkhiL1zU3T8IIMq824RectbxAmIMkFaeGOeVB9IGH67pz5cEKCy7GStJwuNwKNSB9vRNAXkSj6Y+hy19cYCQQkDasYADdRcU6v0OUhrpvZpqQzq4CcmkktK9gJ9wAMUZINZUkLDOMLWdB2SzqU9EAGpDe9AZuVwymUx3uuM0n7/VHaZRjabXtYDnTKH3cWdLWEtSlC0uTwCoPzFZoamuB26YCilGcOtMzoLCwqstxHR4UX9xOsCWomeNGUkCmFhRUaE6JjiAlGWTKM3NBbrofa+eIkzYiJ9cW+Io4wDqkGAtFwzQjq1jQgkAmAXc+b/dDk20FGtLHskoIEkAdZpNsB2sSyTS1iziLVgEYV8f6bzMQU58roM6TVM9AHL+IIAiFrDFWHh/8eKGAmI6WVT1DzDAdjiCgBZ7nvotYIchCOs/PRiCB6RiKlm2bQCYP4im9c6Uu1bagPmUQPY5QXjzZ8LmbzEHqs4DaqEvo3pzxFugnYAgvPGT3MQLxLs8gCwDvM8C4Dh8XSdbatL8bJaYhcms2RCaH1zhbZaKO8iqhOA4APgKjG1TA0XwWKB5Wr+LPnQIhGEYdwQB4mcdgDnrlTtVlS+Ct8xRh9EzLQyxBn5Xl3MAdVo25nNA4g/PxLgcZYI5Yohr/70OR7aHgQfDg+WKDaiwADJXA+txw19SKRcQtGB3ftded8iz1+B/HohxgIo6bUqWAEQPAOYWYNwZX468Fpz+MrHyeecZIq6AB7+OT5EoIMkAU6awIngB1ETkX5qmFCtzwo0NViHIM4WnYuUxtZwDVBQDQAFP0WWPakXL7OivZJ/Hj7+0LEbCC8AUkSrrAQA+iWiCR570LEjzOcJMS//5dVT+99DwzU2zY4xgASZaADLV1BAAlgLgo8dLWtiwjg19gKWbZlv6NoArAqZoDXYbwUfL5hZEPOFbU61xlIgmNlxKJoKB2Vk6L+ZGEKCKN7IDSPi1yk1P232qp8wrNxN58sRjybx4LB6PFwVkVTyQG8Ue72Mp7iuT+K2TWnjbY1QeLS7ZSuVtgDNMk0kXoG4sDqCL/31jCcLZ2HCC0VUCv31kWXx2PO4HcBYIQB+gD/IipW5YVox1x9G+I/VEv6EAlyz7YCzu11eV5lyOB0wqP31nofQdTjsiHljVSuvce+QkrS0ZOq68XQEPYKI1086CMeg1F9nBpo17bd9rLqCbhjV04mH6DiBpAf5kPekc5KKu1t4lt5sNhjN0vPo+AC3yxRH7GDzoVaM5tXaqtVP+fCsv7wNINuBiJIy5BB/vDfO69xdL53nlvRlScwjIMQevQNGuYd4nT4dluCrEiwJEtbmZESYS+evN4V5YG7AkHggOoGsCJSQnlLEHcMO+ETfg7lIANcMAZY+A2TWiK3ckNPhq7HGAh/Lm5jeF9H9DBgBb4MIBektzM+1pppkwYgDd70KmMQVk6Fml1hz5WwksTYhwFiJ3K1Dlv1H59nN57cHOkwm/tJZSFyB/HtvWpvZze6/CU4qtnoX0hStQvv5cX9zw3vPfPY9txij/xS+/u+TRYfgAVooDT21CwKarDpgl76BGBsDWA2W3rIlsM2AQ+ZECsBRDfRllpACsRaGrYI7e2zkjjv8DfcrSd/sHRf0AAAAASUVORK5CYII="
};
const EMAIL_LOGO_URL = "https://customer.cohentra.digital/brand/cohentra-logo.png";
// Een in de e-mailinstellingen opgeslagen paarse accentkleur van voor de nieuwe huisstijl telt als 'niet ingesteld'.
const LEGACY_EMAIL_ACCENTS = new Set(["#7152ff", "#7046f5", "#6047df", "#7052f5"]);

function brandAssetResponse(pathname) {
  const match = /^\/brand\/(cohentra-[a-z-]+\.png)$/.exec(pathname);
  const data = match && BRAND_ASSETS[match[1]];
  if (!data) return null;
  return new Response(Uint8Array.from(atob(data), (c) => c.charCodeAt(0)), {
    headers: { "Content-Type": "image/png", "Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*", "X-Content-Type-Options": "nosniff" }
  });
}

function emailAccent(brand) {
  const accent = String(brand?.accent || "").toLowerCase();
  return /^#[0-9a-f]{6}$/.test(accent) && !LEGACY_EMAIL_ACCENTS.has(accent) ? accent : EMAIL_TEMPLATE_DEFAULTS.branding.accent;
}

function emailLogoHeader(accent) {
  return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td style="background:#ffffff;padding:24px 28px 18px"><img src="' + EMAIL_LOGO_URL + '" width="164" height="60" alt="Cohentra Digital" style="display:block;border:0;outline:none;width:164px;height:auto;font-family:Arial,sans-serif;font-size:20px;font-weight:bold;color:#121e36"></td></tr><tr><td height="3" style="height:3px;background:' + accent + ';font-size:0;line-height:0">&nbsp;</td></tr></table>';
}

const EMAIL_TEMPLATE_DEFAULTS = {
  support: {
    reply_heading: "Een reactie van Cohentra Support",
    reply_closing: "Ik kijk graag met je mee als je nog vragen hebt.",
    status_heading: "We nemen je aanvraag in behandeling",
    status_body: "We hebben je supportaanvraag {{reference}} in behandeling genomen.",
    status_closing: "Ik help je graag verder.",
    new_heading: "{{subject}}",
    new_button: "Open de supportinbox"
  },
  auth: {
    invite_subject: "Je Cohentra klantenportaal instellen",
    invite_intro: "Er is een account voor je aangemaakt in het Cohentra klantenportaal. Stel via de beveiligde link je wachtwoord in.",
    invite_button: "Account instellen",
    reset_subject: "Wachtwoord herstellen voor Cohentra",
    reset_intro: "We hebben een verzoek ontvangen om het wachtwoord van je Cohentra klantenportaal te herstellen. Gebruik de beveiligde link om een nieuw wachtwoord te kiezen.",
    reset_button: "Wachtwoord herstellen",
    expiry_note: "De link is één uur geldig en kan één keer worden gebruikt. Heb je dit niet aangevraagd? Dan kun je deze e-mail negeren."
  },
  branding: { accent: "#2d64d4" }
};
const EMAIL_TEMPLATE_LIMITS = {
  support: { reply_heading: 120, reply_closing: 500, status_heading: 120, status_body: 500, status_closing: 500, new_heading: 160, new_button: 80 },
  auth: { invite_subject: 160, invite_intro: 600, invite_button: 80, reset_subject: 160, reset_intro: 600, reset_button: 80, expiry_note: 600 },
  branding: { accent: 7 }
};
function normalizeEmailTemplateSettings(key, input) {
  const defaults = EMAIL_TEMPLATE_DEFAULTS[key], limits = EMAIL_TEMPLATE_LIMITS[key];
  if (!defaults || !limits || !input || typeof input !== "object" || Array.isArray(input)) throw new Error("Ongeldig e-mailsjabloon.");
  const result = {};
  for (const field of Object.keys(defaults)) {
    let value = String(input[field] ?? defaults[field]).trim();
    if (field.endsWith("_subject")) value = value.replace(/[\r\n]+/g, " ").trim();
    if (!value || value.length > limits[field]) throw new Error("Controleer de lengte van de ingevulde velden.");
    if (key === "branding" && field === "accent" && !/^#[0-9a-f]{6}$/i.test(value)) throw new Error("Gebruik een hexkleur, bijvoorbeeld #396ed6.");
    result[field] = value;
  }
  return result;
}
async function loadEmailTemplateSettings(env, key) {
  const defaults = EMAIL_TEMPLATE_DEFAULTS[key];
  if (!defaults) throw new Error("Onbekend e-mailsjabloon.");
  try {
    const row = await env.DB.prepare("SELECT settings_json FROM email_template_settings WHERE template_key = ?").bind(key).first();
    if (!row) return { ...defaults };
    return normalizeEmailTemplateSettings(key, { ...defaults, ...JSON.parse(row.settings_json) });
  } catch (error) {
    console.error("email_template_settings_read_failed", { key, message: String(error?.message || error).slice(0, 160) });
    return { ...defaults };
  }
}
function templateText(value, variables = {}) {
  return String(value || "").replace(/\{\{\s*([a-z_]+)\s*\}\}/gi, (match, key) => String(variables[key] ?? ""));
}
function emailEscape(value) {
  return String(value ?? "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]));
}
function emailParagraphs(value) { return emailEscape(value).replace(/\n/g, "<br>"); }
function emailFrame(brand, content) {
  const accent = emailAccent(brand);
  const header = emailLogoHeader(accent);
  return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f1f3f7" style="width:100%;border-collapse:collapse;background:#f1f3f7"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" style="width:100%;max-width:640px;border:1px solid #dce2ef;border-collapse:collapse;background:#ffffff">' + header + '<tr><td style="padding:28px;font-family:Arial,sans-serif;color:#182033">' + content + '</td></tr></table></td></tr></table>';
}
function renderSupportEmailHtml({ ticket, agentReply, bodyText, firstName, settings, brand }) {
  const isStatus = agentReply?.kind === "status";
  const footer = '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:24px;border-collapse:collapse"><tr><td style="border-top:1px solid #e6e9f0;padding-top:14px;color:#64748b;font-family:Arial,sans-serif;font-size:12px;line-height:1.6">Cohentra Support · <a href="mailto:support@cohentra.digital" style="color:#285dc5;text-decoration:underline">support@cohentra.digital</a></td></tr></table>';
  if (agentReply) {
    const heading = isStatus ? settings.status_heading : settings.reply_heading;
    const closing = isStatus ? settings.status_closing : settings.reply_closing;
    return emailFrame(brand, '<div style="font-family:Arial,sans-serif;font-size:11px;line-height:1.5;letter-spacing:2px;font-weight:bold;color:#356ad6;text-transform:uppercase">' + (isStatus ? "STATUSUPDATE" : "COHENTRA SUPPORT") + '</div><h1 style="margin:8px 0 22px;color:#111827;font-family:Arial,sans-serif;font-size:24px;line-height:1.3">' + emailEscape(heading) + '</h1><p style="margin:0 0 16px;font-family:Arial,sans-serif;font-size:15px;line-height:1.7;color:#263247">Beste ' + emailEscape(ticket.customerName || ticket.customer_name || "klant") + ',</p><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f4f6fb" style="border-collapse:collapse;background:#f4f6fb"><tr><td style="padding:16px;font-family:Arial,sans-serif;font-size:15px;line-height:1.7;color:#263247">' + emailParagraphs(bodyText) + '</td></tr></table><p style="margin:18px 0 16px;font-family:Arial,sans-serif;font-size:15px;line-height:1.7;color:#263247">' + emailEscape(closing) + '</p><p style="margin:0;font-family:Arial,sans-serif;font-size:15px;line-height:1.7;color:#263247">Hartelijke groet,' + (firstName ? '<br><strong>' + emailEscape(firstName) + '</strong><br>' : '<br>') + 'Cohentra Support</p>' + footer);
  }
  const heading = templateText(settings.new_heading, { subject: ticket.subject || "Nieuwe aanvraag" });
  const message = ["Referentie: " + ticket.reference, "Klant: " + (ticket.customerName || ticket.customer_name || ""), "E-mailadres: " + (ticket.contactEmail || ticket.contact_email || ""), "Categorie: " + (ticket.category || ""), "Onderwerp: " + (ticket.subject || ""), "", ticket.message || ""].join("\n");
  const button = '<a href="https://support.cohentra.digital/" style="display:inline-block;background:' + emailAccent(brand) + ';color:#fff;padding:12px 18px;text-decoration:none;font-family:Arial,sans-serif;font-weight:bold">' + emailEscape(settings.new_button) + '</a>';
  return emailFrame(brand, '<div style="font-family:Arial,sans-serif;font-size:11px;line-height:1.5;letter-spacing:2px;font-weight:bold;color:#356ad6;text-transform:uppercase">NIEUWE SUPPORTAANVRAAG</div><h1 style="margin:8px 0 22px;color:#111827;font-family:Arial,sans-serif;font-size:24px;line-height:1.3">' + emailEscape(heading) + '</h1><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f4f6fb" style="border-collapse:collapse;background:#f4f6fb"><tr><td style="padding:16px;font-family:Arial,sans-serif;font-size:14px;line-height:1.7;color:#263247">' + emailParagraphs(message) + '</td></tr></table><p style="margin:20px 0 0">' + button + '</p>' + footer);
}
function renderAuthEmailHtml({ subject, intro, link, button, expiryNote, brand }) {
  const accent = emailAccent(brand);
  const header = emailLogoHeader(accent);
  return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f1f3f7" style="width:100%;border-collapse:collapse;background:#f1f3f7"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" style="width:100%;max-width:640px;border:1px solid #dce2ef;border-collapse:collapse;background:#ffffff">' + header + '<tr><td style="padding:28px;font-family:Arial,sans-serif;color:#182033"><div style="font-size:11px;line-height:1.5;letter-spacing:2px;font-weight:bold;color:#356ad6;text-transform:uppercase">KLANTENPORTAAL</div><h1 style="font-size:24px;line-height:1.3;margin:8px 0 18px;color:#111827;font-family:Arial,sans-serif">' + emailEscape(subject) + '</h1><p style="margin:0 0 18px;font-size:15px;line-height:1.7;color:#263247;font-family:Arial,sans-serif">' + emailEscape(intro) + '</p><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse"><tr><td bgcolor="' + accent + '" style="background:' + accent + ';padding:13px 20px"><a href="' + emailEscape(link) + '" style="color:#ffffff;text-decoration:none;font-weight:bold;font-family:Arial,sans-serif;font-size:15px">' + emailEscape(button) + '</a></td></tr></table><p style="margin:18px 0 0;font-size:14px;line-height:1.7;color:#475569;font-family:Arial,sans-serif">' + emailEscape(expiryNote) + '</p><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:24px;border-collapse:collapse"><tr><td style="border-top:1px solid #e6e9f0;padding-top:14px;color:#64748b;font-size:13px;line-height:1.6;font-family:Arial,sans-serif">Cohentra Digital · <a href="mailto:info@cohentra.digital" style="color:#285dc5;text-decoration:underline">info@cohentra.digital</a></td></tr></table></td></tr></table></td></tr></table>';
}
async function sendSupportTicketEmail(env, ticket, agentReply = null) {
  const username = String(agentReply ? env.STRATO_SUPPORT_SMTP_USER || "" : env.STRATO_SMTP_USER || "").trim();
  const password = String(agentReply ? env.STRATO_SUPPORT_SMTP_PASSWORD || "" : env.STRATO_SMTP_PASSWORD || "");
  if (!username || !password || !/^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(username)) return false;
  let socket;
  let smtpStage = "verbinden met STRATO";
  try {
    const isAgentReply = Boolean(agentReply);
    if (isAgentReply && username.toLowerCase() !== "support@cohentra.digital") {
      console.error("support_reply_email_not_configured", { reference: ticket.reference, reason: "STRATO_SUPPORT_SMTP_USER must be support@cohentra.digital" });
      return false;
    }
    const to = isAgentReply ? String(ticket.contactEmail || ticket.contact_email || "").trim() : "support@cohentra.digital";
    if (!/^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(to)) {
      return isAgentReply ? { sent: false, reason: "klantadres ontbreekt of is ongeldig" } : false;
    }
    const safeHeader = (value) => String(value || "").replace(/[\r\n]+/g, " ").trim();
    const firstName = String(agentReply?.staffFirstName || "").trim().split(/\s+/)[0];
    const [template, brand] = await Promise.all([loadEmailTemplateSettings(env, "support"), loadEmailTemplateSettings(env, "branding")]);
    const isStatusUpdate = isAgentReply && agentReply.kind === "status";
    const bodyText = isAgentReply
      ? (isStatusUpdate ? templateText(template.status_body, { reference: ticket.reference }) : agentReply.message)
      : ["Nieuwe supportaanvraag " + ticket.reference, "Bron: " + (ticket.source === "website" ? "Websiteformulier" : "Klantenportaal"), "Klant: " + (ticket.customerName || ticket.customer_name || ""), "E-mailadres: " + (ticket.contactEmail || ticket.contact_email || ""), "Categorie: " + (ticket.category || ""), "Onderwerp: " + (ticket.subject || ""), "", ticket.message || ""].join("\n");
    const text = isAgentReply
      ? ["Beste " + (ticket.customerName || ticket.customer_name || "klant") + ",", "", bodyText, "", isStatusUpdate ? template.status_closing : template.reply_closing, "", "Hartelijke groet,", ...(firstName ? [firstName, "Cohentra Support"] : ["Cohentra Support"]), "", "Referentie: " + ticket.reference].join("\n")
      : bodyText + "\n\nOpen de supportinbox: https://support.cohentra.digital/";
    const html = renderSupportEmailHtml({ ticket, agentReply: isAgentReply ? agentReply : null, bodyText, firstName, settings: template, brand });
    const replyTo = isAgentReply ? "support@cohentra.digital" : String(ticket.contactEmail || "").trim();
    const b64Utf8 = (value) => btoa(String.fromCharCode(...new TextEncoder().encode(value)));
    const encodeHeader = (value) => `=?UTF-8?B?${b64Utf8(value)}?=`;
    const wrapBase64 = (value) => value.match(/.{1,76}/g)?.join("\r\n") || "";
    const base64 = (value) => wrapBase64(b64Utf8(value));
    const subject = isAgentReply ? `Re: [${ticket.reference}] ${safeHeader(ticket.subject)}` : `[${ticket.reference}] ${safeHeader(ticket.subject)}`;
    const replyHeader = /^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(replyTo) ? `Reply-To: <${replyTo}>` : "";
    const boundary = "cohentra_" + crypto.randomUUID().replace(/-/g, "");
    const mime = [`From: ${encodeHeader("Cohentra Support")} <${username}>`, `To: <${to}>`, ...(replyHeader ? [replyHeader] : []), `Subject: ${encodeHeader(subject)}`, `Date: ${new Date().toUTCString()}`, `Message-ID: <${crypto.randomUUID()}@${username.split("@")[1]}>`, "MIME-Version: 1.0", 'Content-Type: multipart/alternative; boundary="' + boundary + '"', "", "--" + boundary, 'Content-Type: text/plain; charset="UTF-8"', "Content-Transfer-Encoding: base64", "", base64(text), "--" + boundary, 'Content-Type: text/html; charset="UTF-8"', "Content-Transfer-Encoding: base64", "", base64(html), "--" + boundary + "--", ""].join("\r\n");
    socket = connect({ hostname: "smtp.strato.de", port: 465 }, { secureTransport: "on" });
    const reader = socket.readable.getReader(), writer = socket.writable.getWriter(), decoder = new TextDecoder();
    let pending = "";
    const line = async () => { while (!pending.includes("\n")) { const chunk = await reader.read(); if (chunk.done) throw new Error("SMTP-verbinding gesloten."); pending += decoder.decode(chunk.value, { stream: true }); if (pending.length > 16384) throw new Error("SMTP-antwoord is te groot."); } const end = pending.indexOf("\n"), value = pending.slice(0, end).replace(/\r$/, ""); pending = pending.slice(end + 1); return value; };
    const reply = async (expected) => { let response = ""; for (let count = 0; count < 30; count += 1) { const current = await line(); response = current; const match = /^(\d{3})([ -])/.exec(current); if (!match) throw new Error("Ongeldig SMTP-antwoord."); if (match[2] === " ") { const status = Number(match[1]); if (!expected.includes(status)) throw new Error(`SMTP-server antwoordde met ${status}.`); return response; } } throw new Error("SMTP-server stuurde te veel antwoordregels."); };
    const command = async (value, expected) => { await writer.write(new TextEncoder().encode(`${value}\r\n`)); return reply(expected); };
    smtpStage = "SMTP-begroeting"; await reply([220]);
    smtpStage = "SMTP-server identificeren"; await command("EHLO eventhub.cohentra.digital", [250]);
    smtpStage = "SMTP aanmelden"; await command("AUTH LOGIN", [334]);
    smtpStage = "gebruikersnaam verifiëren"; await command(b64Utf8(username), [334]);
    smtpStage = "wachtwoord verifiëren"; await command(b64Utf8(password), [235]);
    smtpStage = "afzender accepteren"; await command(`MAIL FROM:<${username}>`, [250]);
    smtpStage = "klantadres accepteren"; await command(`RCPT TO:<${to}>`, [250, 251]);
    smtpStage = "bericht voorbereiden"; await command("DATA", [354]);
    const escapedMime = mime.replace(/(^|\r\n)\./g, "$1..");
    smtpStage = "bericht overdragen"; await writer.write(new TextEncoder().encode(`${escapedMime}\r\n.\r\n`)); await reply([250]);
    // A 250 response after DATA means STRATO accepted the message. QUIT is best effort
    // and must not turn an accepted email into a reported delivery failure.
    try { await command("QUIT", [221]); } catch {}
    writer.releaseLock(); reader.releaseLock(); return true;
  } catch (error) {
    const reason = `${smtpStage}: ${String(error?.message || error).slice(0, 160)}`;
    console.error("support_ticket_email_failed", { reference: ticket.reference, stage: smtpStage, message: String(error?.message || error).slice(0, 160) });
    return agentReply ? { sent: false, reason } : false;
  } finally { try { socket?.close(); } catch {} }
}

function imapHeaderMap(raw) {
  const headers = new Map();
  let current = "";
  for (const line of String(raw || "").split(/\r?\n/)) {
    if (/^[ \t]/.test(line) && current) {
      headers.set(current, (headers.get(current) || "") + " " + line.trim());
      continue;
    }
    const split = /^([^:]+):\s*(.*)$/.exec(line);
    if (!split) continue;
    current = split[1].toLowerCase();
    headers.set(current, split[2]);
  }
  return headers;
}

function decodeMimeHeader(value) {
  return new TextDecoder("utf-8").decode(Uint8Array.from(String(value || ""), char => char.charCodeAt(0) & 255)).replace(/(=\?[^?]+\?[bq]\?[^?]*\?=)[ \t\r\n]+(?==\?[^?]+\?[bq]\?)/gi, "$1").replace(/=\?([^?]+)\?([bq])\?([^?]*)\?=/gi, (_match, charset, encoding, data) => {
    try {
      if (encoding.toLowerCase() === "b") {
        const binary = atob(data.replace(/\s/g, ""));
        return new TextDecoder(charset).decode(Uint8Array.from(binary, char => char.charCodeAt(0)));
      }
      const bytes = [];
      const source = data.replace(/_/g, " ");
      for (let i = 0; i < source.length; i += 1) {
        if (source[i] === "=" && /^[0-9a-f]{2}$/i.test(source.slice(i + 1, i + 3))) {
          bytes.push(parseInt(source.slice(i + 1, i + 3), 16)); i += 2;
        } else bytes.push(source.charCodeAt(i));
      }
      return new TextDecoder(charset).decode(new Uint8Array(bytes));
    } catch { return data; }
  });
}

function decodeMailPart(body, transferEncoding, charset) {
  const encoding = String(transferEncoding || "").toLowerCase().trim();
  try {
    if (encoding === "base64") {
      const binary = atob(String(body).replace(/\s/g, ""));
      return new TextDecoder(charset || "utf-8").decode(Uint8Array.from(binary, char => char.charCodeAt(0)));
    }
    if (encoding === "quoted-printable") {
      const source = String(body).replace(/=\r?\n/g, "");
      const bytes = [];
      for (let i = 0; i < source.length; i += 1) {
        if (source[i] === "=" && /^[0-9a-f]{2}$/i.test(source.slice(i + 1, i + 3))) {
          bytes.push(parseInt(source.slice(i + 1, i + 3), 16)); i += 2;
        } else bytes.push(source.charCodeAt(i) & 255);
      }
      return new TextDecoder(charset || "utf-8").decode(new Uint8Array(bytes));
    }
  } catch {}
  try { return new TextDecoder(charset || "utf-8").decode(Uint8Array.from(String(body || ""), char => char.charCodeAt(0) & 255)); } catch { return String(body || ""); }
}

function extractMailText(raw, depth = 0) {
  if (depth > 5) return "";
  const separator = /\r?\n\r?\n/.exec(raw);
  if (!separator) return "";
  const headers = imapHeaderMap(raw.slice(0, separator.index));
  const body = raw.slice(separator.index + separator[0].length);
  const contentType = headers.get("content-type") || "text/plain";
  if (/multipart\//i.test(contentType)) {
    const boundary = /boundary\s*=\s*(?:"([^"]+)"|'([^']+)'|([^;\s]+))/i.exec(contentType);
    if (!boundary) return "";
    for (const part of body.split("--" + (boundary[1] || boundary[2] || boundary[3]))) {
      if (!part || /^--\s*$/.test(part.trim())) continue;
      const text = extractMailText(part.replace(/^\r?\n/, ""), depth + 1);
      if (text) return text;
    }
    return "";
  }
  if (/attachment/i.test(headers.get("content-disposition") || "")) return "";
  const charset = /charset\s*=\s*(?:"([^"]+)"|'([^']+)'|([^;\s]+))/i.exec(contentType);
  const decoded = decodeMailPart(body, headers.get("content-transfer-encoding"), charset?.[1] || charset?.[2] || charset?.[3] || "utf-8");
  if (/^text\/plain/i.test(contentType)) return decoded;
  if (/^text\/html/i.test(contentType)) return decoded.replace(/<br\s*\/?\s*>/gi, "\n").replace(/<\/(?:p|div|li|blockquote)\s*>/gi, "\n").replace(/<[^>]*>/g, " ").replace(/&nbsp;/gi, " ").replace(/&amp;/gi, "&").replace(/&lt;/gi, "<").replace(/&gt;/gi, ">").replace(/&#39;|&apos;/gi, "'").replace(/&quot;/gi, '"');
  return "";
}

function trimQuotedReply(value) {
  const lines = String(value || "").replace(/\r/g, "").split("\n");
  const quoteAt = lines.findIndex((line, index) => index > 0 && (/^\s*>/.test(line) || /^\s*(?:On .+wrote:|Op .+schreef .+:|Van:\s|From:\s|_{5,}|-{5,})/i.test(line)));
  const text = (quoteAt >= 0 ? lines.slice(0, quoteAt) : lines).join("\n").trim();
  return text.slice(0, 12000);
}

async function syncSupportMailbox(env) {
  const username = String(env.STRATO_SUPPORT_SMTP_USER || "").trim();
  const password = String(env.STRATO_SUPPORT_SMTP_PASSWORD || "");
  if (username.toLowerCase() !== "support@cohentra.digital" || !password) throw new Error("De STRATO-mailboxinstellingen voor support zijn niet beschikbaar.");
  if (/[\r\n]/.test(username + password)) throw new Error("De STRATO-mailboxinstellingen zijn ongeldig.");
  const socket = connect({ hostname: "imap.strato.de", port: 993 }, { secureTransport: "on" });
  const reader = socket.readable.getReader(), writer = socket.writable.getWriter(), encoder = new TextEncoder(), decoder = new TextDecoder("utf-8");
  let buffered = new Uint8Array(0), tagNumber = 0;
  const append = (part) => { const joined = new Uint8Array(buffered.length + part.length); joined.set(buffered); joined.set(part, buffered.length); buffered = joined; };
  const fill = async (size) => { while (buffered.length < size) { const chunk = await reader.read(); if (chunk.done) throw new Error("De verbinding met de STRATO-inbox is gesloten."); append(chunk.value); } };
  const line = async () => { for (;;) { const end = buffered.indexOf(10); if (end >= 0) { const bytes = buffered.slice(0, end); buffered = buffered.slice(end + 1); return decoder.decode(bytes).replace(/\r$/, ""); } if (buffered.length > 65536) throw new Error("De STRATO-inbox gaf een te lange antwoordregel."); await fill(buffered.length + 1); } };
  const literal = async (size) => {
    const oversized = size > 8 * 1024 * 1024, limit = oversized ? 65536 : size;
    let remaining = size, kept = 0, raw = "";
    while (remaining > 0) {
      if (!buffered.length) await fill(1);
      const length = Math.min(buffered.length, remaining), take = Math.min(length, limit - kept);
      for (let offset = 0; offset < take; offset += 8192) raw += String.fromCharCode(...buffered.subarray(offset, Math.min(offset + 8192, take)));
      kept += take; buffered = buffered.slice(length); remaining -= length;
    }
    return { raw, oversized };
  };
  const command = async (value) => {
    const tag = "C" + (++tagNumber);
    await writer.write(encoder.encode(tag + " " + value + "\r\n"));
    const lines = [], literals = [];
    for (let count = 0; count < 200; count += 1) {
      const responseLine = await line();
      lines.push(responseLine);
      const marker = /\{(\d+)\+?\}$/.exec(responseLine);
      if (marker) literals.push(await literal(Number(marker[1])));
      if (responseLine.startsWith(tag + " ")) {
        if (!/^C\d+ OK\b/i.test(responseLine)) throw new Error("STRATO heeft een inbox-opdracht geweigerd.");
        return { lines, literals };
      }
    }
    throw new Error("STRATO stuurde te veel antwoordregels.");
  };
  const quote = (value) => '"' + String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"';
  try {
    const greeting = await line();
    if (!/^\*\s+OK\b/i.test(greeting)) throw new Error("STRATO stuurde geen geldige IMAP-begroeting.");
    await command("LOGIN " + quote(username) + " " + quote(password));
    const selected = await command("SELECT INBOX");
    const validityLine = selected.lines.find(value => /\[UIDVALIDITY\s+\d+\]/i.test(value));
    const uidValidity = /\[UIDVALIDITY\s+(\d+)\]/i.exec(validityLine || "")?.[1];
    if (!uidValidity) throw new Error("De STRATO-inbox gaf geen UIDVALIDITY terug.");
    let state = await env.DB.prepare("SELECT uid_validity, last_uid FROM support_mail_sync_state WHERE mailbox = ?").bind(username.toLowerCase()).first();
    let nextUid;
    if (!state || state.uid_validity !== uidValidity) {
      const all = await command("UID SEARCH ALL");
      const searchLine = all.lines.find(value => /^\* SEARCH(?:\s|$)/i.test(value)) || "";
      const allUids = searchLine.replace(/^\* SEARCH\s*/i, "").trim().split(/\s+/).map(Number).filter(Number.isFinite);
      nextUid = Math.max(1, (allUids.at(-1) || 0) - 49);
      await env.DB.prepare("INSERT INTO support_mail_sync_state (mailbox, uid_validity, last_uid, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(mailbox) DO UPDATE SET uid_validity = excluded.uid_validity, last_uid = excluded.last_uid, updated_at = excluded.updated_at").bind(username.toLowerCase(), uidValidity, nextUid - 1, new Date().toISOString()).run();
      state = { uid_validity: uidValidity, last_uid: nextUid - 1 };
    } else nextUid = Number(state.last_uid || 0) + 1;
    const search = await command("UID SEARCH UID " + nextUid + ":*");
    const searchLine = search.lines.find(value => /^\* SEARCH(?:\s|$)/i.test(value)) || "";
    const uids = searchLine.replace(/^\* SEARCH\s*/i, "").trim().split(/\s+/).map(Number).filter(uid => Number.isInteger(uid) && uid >= nextUid).sort((a, b) => a - b).slice(0, 20);
    let linked = 0, skipped = 0;
    for (const uid of uids) {
      const fetched = await command("UID FETCH " + uid + " (UID BODY.PEEK[])");
      const mail = fetched.literals[0] || { raw: "", oversized: false };
      const raw = mail.raw;
      const headerEnd = /\r?\n\r?\n/.exec(raw);
      const headers = imapHeaderMap(headerEnd ? raw.slice(0, headerEnd.index) : "");
      const reference = /\bCH-\d{4}-[A-Z0-9]+\b/i.exec((decodeMimeHeader(headers.get("subject") || "")) + " " + (headers.get("references") || "") + " " + (headers.get("in-reply-to") || ""))?.[0]?.toUpperCase();
      let inserted = false;
      if (mail.oversized) {
        await env.DB.prepare("INSERT OR IGNORE INTO support_mail_sync_issues (id, mailbox, uid_validity, uid, subject, created_at) VALUES (?, ?, ?, ?, ?, ?)").bind(crypto.randomUUID(), username.toLowerCase(), uidValidity, uid, decodeMimeHeader(headers.get("subject") || "Zonder onderwerp").slice(0, 240), new Date().toISOString()).run();
      } else if (reference) {
        const ticket = await env.DB.prepare("SELECT t.id, t.reference, COALESCE(NULLIF(t.contact_email, ''), c.contact_email) AS contact_email FROM support_tickets t JOIN customers c ON c.id = t.customer_id WHERE upper(t.reference) = ?").bind(reference).first();
        const fromRaw = headers.get("from") || "";
        const fromEmail = (/<([^<>]+@[^<>]+)>/.exec(fromRaw)?.[1] || /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i.exec(fromRaw)?.[0] || "").trim().toLowerCase();
        const expectedEmail = String(ticket?.contact_email || "").trim().toLowerCase();
        const message = trimQuotedReply(extractMailText(raw));
        if (ticket && fromEmail && fromEmail === expectedEmail && message) {
          const senderName = decodeMimeHeader(fromRaw.replace(/<[^<>]*>/g, "").replace(/\s*"\s*/g, "").trim()) || fromEmail;
          const messageDate = Date.parse(headers.get("date") || "");
          const createdAt = Number.isFinite(messageDate) ? new Date(messageDate).toISOString() : new Date().toISOString();
          const externalId = uidValidity + ":" + uid;
          const result = await env.DB.prepare("INSERT OR IGNORE INTO support_ticket_messages (id, ticket_id, author_name, author_email, message, delivery_status, created_at, external_message_id) VALUES (?, ?, ?, ?, ?, 'sent', ?, ?)").bind(crypto.randomUUID(), ticket.id, senderName.slice(0, 120), fromEmail, message, createdAt, externalId).run();
          if (result.meta?.changes) {
            await env.DB.prepare("UPDATE support_tickets SET updated_at = ?, status = CASE WHEN status IN ('waiting_customer', 'closed') THEN 'in_progress' ELSE status END WHERE id = ?").bind(new Date().toISOString(), ticket.id).run();
            linked += 1;
          } else skipped += 1;
          inserted = true;
        }
      }
      if (!inserted) skipped += 1;
      await env.DB.prepare("UPDATE support_mail_sync_state SET last_uid = ?, updated_at = ? WHERE mailbox = ? AND uid_validity = ?").bind(uid, new Date().toISOString(), username.toLowerCase(), uidValidity).run();
    }
    await command("LOGOUT");
    const { results: issues } = await env.DB.prepare("SELECT id, subject FROM support_mail_sync_issues WHERE mailbox = ? AND resolved_at IS NULL ORDER BY created_at ASC LIMIT 20").bind(username.toLowerCase()).all();
    return { checked: uids.length, linked, skipped, more: uids.length === 20, issues };
  } finally {
    try { writer.releaseLock(); } catch {}
    try { reader.releaseLock(); } catch {}
    try { socket.close(); } catch {}
  }
}

function constantTimeEqual(left, right) {
  const a = new TextEncoder().encode(String(left || "")), b = new TextEncoder().encode(String(right || ""));
  if (a.length !== b.length) return false;
  let difference = 0;
  for (let i = 0; i < a.length; i += 1) difference |= a[i] ^ b[i];
  return difference === 0;
}

function normalizedKey(value) {
  return String(value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
}

async function digest(value) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function createLicenseKey() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  const raw = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("").toUpperCase();
  return `EH-${raw.match(/.{1,4}/g).join("-")}`;
}

async function readBoundedRequestBytes(request, maxBytes) {
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array();
  const chunks = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maxBytes) { await reader.cancel(); return null; }
    chunks.push(value);
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return bytes;
}

function jpegDimensions(bytes) {
  if (bytes.length < 12 || bytes[0] !== 0xff || bytes[1] !== 0xd8 || bytes[bytes.length - 2] !== 0xff || bytes[bytes.length - 1] !== 0xd9) return null;
  let offset = 2;
  while (offset + 4 < bytes.length) {
    while (offset < bytes.length && bytes[offset] !== 0xff) offset++;
    while (bytes[offset] === 0xff) offset++;
    const marker = bytes[offset++];
    if (marker === 0xd9 || marker === 0xda) break;
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    const length = (bytes[offset] << 8) | bytes[offset + 1];
    if (length < 2 || offset + length > bytes.length) return null;
    if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
      return { height: (bytes[offset + 3] << 8) | bytes[offset + 4], width: (bytes[offset + 5] << 8) | bytes[offset + 6] };
    }
    offset += length;
  }
  return null;
}

async function adminAuthorized(request, env) {
  const match = /^Bearer\s+(.+)$/i.exec(request.headers.get("Authorization") || "");
  if (!match) return null;
  const tokenHash = await digest(match[1]);
  const nowMs = Date.now();
  const session = await env.DB.prepare("SELECT ss.id, ss.staff_id, ss.actor_role AS role, ss.last_seen_at, ss.created_at, COALESCE(st.name, om.name) AS name, COALESCE(st.first_name, om.first_name) AS first_name FROM staff_sessions ss LEFT JOIN staff_access_tokens st ON st.id = ss.staff_id LEFT JOIN owner_mfa om ON ss.staff_id IS NULL AND om.id = 1 WHERE ss.token_hash = ? AND ss.mfa_verified = 1 AND ss.password_change_only = 0 AND ss.revoked_at IS NULL AND ss.expires_at > ? AND (ss.staff_id IS NULL OR st.revoked_at IS NULL)").bind(tokenHash, nowMs).first();
  if (!session) return null;
  const lastActivity = Date.parse(session.last_seen_at || session.created_at || "");
  if (!Number.isFinite(lastActivity) || nowMs - lastActivity >= 30 * 60 * 1000) {
    await env.DB.prepare("UPDATE staff_sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL").bind(new Date(nowMs).toISOString(), session.id).run();
    return null;
  }
  const now = new Date().toISOString();
  await env.DB.prepare("UPDATE staff_sessions SET last_seen_at = ? WHERE id = ?").bind(now, session.id).run();
  if (session.staff_id) await env.DB.prepare("UPDATE staff_access_tokens SET last_seen_at = ? WHERE id = ?").bind(now, session.staff_id).run();
  let permissions = ["*"];
  let functions = [];
  if (session.staff_id) {
    const { results } = await env.DB.prepare("SELECT f.function_key, f.permissions_json FROM staff_function_assignments a JOIN staff_functions f ON f.function_key = a.function_key WHERE a.staff_id = ?").bind(session.staff_id).all();
    functions = results.map((row) => row.function_key);
    permissions = [...new Set(results.flatMap((row) => { try { const value = JSON.parse(row.permissions_json); return Array.isArray(value) ? value : []; } catch { return []; } }))];
  }
  return { id: session.staff_id, session_id: session.id, role: session.role, name: session.name || "Cohentra beheerder", first_name: session.first_name || "", permissions, functions };
}

async function customerAuthorized(request, env) {
  const match = /^Bearer\s+(.+)$/i.exec(request.headers.get("Authorization") || "");
  if (!match) return null;
  const now = Date.now(), tokenHash = await digest(match[1]);
  const account = await env.DB.prepare("SELECT s.id AS session_id, a.id AS account_id, a.username, a.name AS account_name, a.email AS account_email, a.role AS account_role, a.customer_id, c.name AS customer_name, c.status AS customer_status, c.customer_type, cp.max_licenses, cp.allowed_license_types, cp.enabled AS product_enabled, p.active AS product_active FROM customer_sessions s JOIN customer_portal_accounts a ON a.id = s.customer_account_id JOIN customers c ON c.id = a.customer_id LEFT JOIN customer_products cp ON cp.customer_id = c.id AND cp.product_id = 'eventhub' LEFT JOIN products p ON p.id = cp.product_id WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ? AND a.active = 1 AND a.disabled_at IS NULL LIMIT 1").bind(tokenHash, now).first();
  if (!account || account.customer_status !== "active") return null;
  const timestamp = new Date().toISOString();
  await env.DB.batch([
    env.DB.prepare("UPDATE customer_sessions SET last_seen_at = ? WHERE id = ? AND revoked_at IS NULL").bind(timestamp, account.session_id),
    env.DB.prepare("UPDATE customer_portal_accounts SET last_seen_at = ? WHERE id = ? AND active = 1").bind(timestamp, account.account_id)
  ]);
  // legacy_licensing: de door Cohentra toegewezen EventHub-licentiequota (customer_products) staan aan voor deze klant.
  return { ...account, legacy_licensing: account.product_enabled === 1 && account.product_active === 1, allowed_license_types: allowedLicenseTypes(account.allowed_license_types) };
}

async function issueCustomerSession(env, accountId) {
  const token = randomHex(32), now = Date.now(), timestamp = new Date(now).toISOString();
  await env.DB.prepare("INSERT INTO customer_sessions (id, token_hash, customer_account_id, created_at, expires_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?)").bind(crypto.randomUUID(), await digest(token), accountId, timestamp, now + 12 * 60 * 60 * 1000, timestamp).run();
  return token;
}

async function sendCustomerAuthEmail(env, accountId, email, purpose) {
  if (!env.EMAIL) throw new Error("De e-mailservice is niet beschikbaar.");
  const rawToken = randomHex(32), now = Date.now(), expiresAt = now + 60 * 60 * 1000;
  const tokenHash = await digest(rawToken);
  await env.DB.batch([
    env.DB.prepare("UPDATE customer_auth_tokens SET consumed_at = ? WHERE customer_account_id = ? AND purpose = ? AND consumed_at IS NULL").bind(now, accountId, purpose),
    env.DB.prepare("INSERT INTO customer_auth_tokens (token_hash, customer_account_id, purpose, expires_at, created_at) VALUES (?, ?, ?, ?, ?)").bind(tokenHash, accountId, purpose, expiresAt, now)
  ]);
  const flow = purpose === "invite" ? "invite" : "reset";
  const link = "https://customer.cohentra.digital/?flow=" + flow + "&token=" + rawToken;
  const [template, brand] = await Promise.all([loadEmailTemplateSettings(env, "auth"), loadEmailTemplateSettings(env, "branding")]);
  const subject = purpose === "invite" ? template.invite_subject : template.reset_subject;
  const intro = purpose === "invite" ? template.invite_intro : template.reset_intro;
  const button = purpose === "invite" ? template.invite_button : template.reset_button;
  const html = renderAuthEmailHtml({ subject, intro, link, button, expiryNote: template.expiry_note, brand });
  const text = subject + "\n\n" + intro + "\n\nOpen deze beveiligde link (1 uur geldig, eenmalig): " + link + "\n\nHeb je dit niet aangevraagd? Negeer deze e-mail.\n\nCohentra Digital · info@cohentra.digital";
  await env.EMAIL.send({
    to: email,
    from: { email: "noreply@noreply.cohentra.digital", name: "Cohentra Digital" },
    replyTo: "info@cohentra.digital",
    subject,
    text,
    html
  });
}

async function recordCustomerAuthRequest(env, key, now) {
  await env.DB.prepare("INSERT INTO customer_auth_rate_limits (bucket_key, window_started_at, attempts) VALUES (?, ?, 1) ON CONFLICT(bucket_key) DO UPDATE SET attempts = CASE WHEN window_started_at <= ? THEN 1 ELSE attempts + 1 END, window_started_at = CASE WHEN window_started_at <= ? THEN excluded.window_started_at ELSE window_started_at END")
    .bind(key, now, now - 60 * 60 * 1000, now - 60 * 60 * 1000).run();
  const row = await env.DB.prepare("SELECT attempts FROM customer_auth_rate_limits WHERE bucket_key = ?").bind(key).first();
  return Number(row?.attempts || 0);
}

function allowedLicenseTypes(value) {
  try {
    const types = JSON.parse(String(value || "[]"));
    return Array.isArray(types) ? [...new Set(types.filter((type) => type === "beta" || type === "admin"))] : [];
  } catch {
    return [];
  }
}

const BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
function randomHex(bytes = 32) { return [...crypto.getRandomValues(new Uint8Array(bytes))].map((b) => b.toString(16).padStart(2, "0")).join(""); }
function encodeBase32(bytes) {
  let bits = 0, value = 0, output = "";
  for (const byte of bytes) { value = (value << 8) | byte; bits += 8; while (bits >= 5) { output += BASE32_ALPHABET[(value >>> (bits - 5)) & 31]; bits -= 5; } }
  if (bits) output += BASE32_ALPHABET[(value << (5 - bits)) & 31];
  return output;
}
function decodeBase32(value) {
  let bits = 0, buffer = 0; const output = [];
  for (const char of value.toUpperCase().replace(/=|\s/g, "")) { const digit = BASE32_ALPHABET.indexOf(char); if (digit < 0) throw new Error("Ongeldige TOTP-sleutel."); buffer = (buffer << 5) | digit; bits += 5; if (bits >= 8) { output.push((buffer >>> (bits - 8)) & 255); bits -= 8; } }
  return new Uint8Array(output);
}
async function encryptMfaSecret(secret, env) {
  if (!env.MFA_ENCRYPTION_KEY || env.MFA_ENCRYPTION_KEY.length < 32) throw new Error("De Worker-secret MFA_ENCRYPTION_KEY ontbreekt of is korter dan 32 tekens.");
  const keyBytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(env.MFA_ENCRYPTION_KEY));
  const key = await crypto.subtle.importKey("raw", keyBytes, "AES-GCM", false, ["encrypt"]);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, new TextEncoder().encode(secret));
  return `${[...iv].map((b) => b.toString(16).padStart(2, "0")).join("")}.${[...new Uint8Array(encrypted)].map((b) => b.toString(16).padStart(2, "0")).join("")}`;
}
async function decryptMfaSecret(value, env) {
  if (!env.MFA_ENCRYPTION_KEY || env.MFA_ENCRYPTION_KEY.length < 32) throw new Error("De Worker-secret MFA_ENCRYPTION_KEY ontbreekt of is korter dan 32 tekens.");
  const [ivHex, dataHex] = String(value || "").split(".");
  const fromHex = (hex) => Uint8Array.from(hex.match(/.{2}/g) || [], (b) => parseInt(b, 16));
  const keyBytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(env.MFA_ENCRYPTION_KEY));
  const key = await crypto.subtle.importKey("raw", keyBytes, "AES-GCM", false, ["decrypt"]);
  const plaintext = await crypto.subtle.decrypt({ name: "AES-GCM", iv: fromHex(ivHex) }, key, fromHex(dataHex));
  return new TextDecoder().decode(plaintext);
}
async function totpCounter(secret, code, now = Date.now(), lastCounter = -1) {
  if (!/^\d{6}$/.test(String(code || ""))) return null;
  const key = await crypto.subtle.importKey("raw", decodeBase32(secret), { name: "HMAC", hash: "SHA-1" }, false, ["sign"]);
  const current = Math.floor(now / 30000);
  for (const counter of [current - 1, current, current + 1]) {
    if (counter <= lastCounter) continue;
    const message = new Uint8Array(8); let n = counter;
    for (let i = 7; i >= 0; i -= 1) { message[i] = n & 255; n = Math.floor(n / 256); }
    const mac = new Uint8Array(await crypto.subtle.sign("HMAC", key, message));
    const offset = mac[mac.length - 1] & 15;
    const binary = ((mac[offset] & 127) << 24) | (mac[offset + 1] << 16) | (mac[offset + 2] << 8) | mac[offset + 3];
    if (String(binary % 1000000).padStart(6, "0") === code) return counter;
  }
  return null;
}
function makeRecoveryCode() { const value = randomHex(8).toUpperCase(); return `${value.slice(0, 4)}-${value.slice(4, 8)}-${value.slice(8, 12)}-${value.slice(12)}`; }
function normalizeRecoveryCode(value) { return String(value || "").replace(/[^A-Z0-9]/gi, "").toUpperCase(); }
async function createRecoveryCodes(env, ownerId, staffId) {
  const codes = Array.from({ length: 10 }, makeRecoveryCode); const now = new Date().toISOString();
  await env.DB.prepare("DELETE FROM mfa_recovery_codes WHERE owner_id IS ? AND staff_id IS ?").bind(ownerId, staffId).run();
  for (const code of codes) await env.DB.prepare("INSERT INTO mfa_recovery_codes (id, owner_id, staff_id, code_hash, created_at) VALUES (?, ?, ?, ?, ?)").bind(crypto.randomUUID(), ownerId, staffId, await digest(normalizeRecoveryCode(code)), now).run();
  return codes;
}
async function issueSession(env, role, staffId = null) {
  const token = randomHex(32); const id = crypto.randomUUID(); const now = new Date().toISOString();
  await env.DB.prepare("INSERT INTO staff_sessions (id, token_hash, staff_id, actor_role, created_at, expires_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?)").bind(id, await digest(token), staffId, role, now, Date.now() + 12 * 60 * 60 * 1000, now).run();
  return token;
}
async function hashPassword(password, saltHex = randomHex(16)) {
  const salt = Uint8Array.from(saltHex.match(/.{2}/g) || [], (b) => parseInt(b, 16));
  const material = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
  // Cloudflare Workers currently rejects PBKDF2 deriveBits requests above 100,000 iterations.
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", salt, iterations: 100000, hash: "SHA-256" }, material, 256);
  return { salt: saltHex, hash: [...new Uint8Array(bits)].map((b) => b.toString(16).padStart(2, "0")).join("") };
}
async function passwordMatches(password, salt, expectedHash) {
  if (!salt || !expectedHash) return false;
  const actual = await hashPassword(password, salt);
  return actual.hash === expectedHash;
}
async function consumeRecoveryCode(env, code, ownerId, staffId) {
  if (!code) return false;
  const row = await env.DB.prepare("SELECT id FROM mfa_recovery_codes WHERE code_hash = ? AND owner_id IS ? AND staff_id IS ? AND used_at IS NULL").bind(await digest(normalizeRecoveryCode(code)), ownerId, staffId).first();
  if (!row) return false;
  const result = await env.DB.prepare("UPDATE mfa_recovery_codes SET used_at = ? WHERE id = ? AND used_at IS NULL").bind(new Date().toISOString(), row.id).run();
  return result.meta?.changes === 1;
}
async function recordLoginFailure(env, key, limit = 5) {
  const now = Date.now(); const row = await env.DB.prepare("SELECT failures, window_started_at FROM auth_login_attempts WHERE login_key = ?").bind(key).first();
  const failures = !row || now - row.window_started_at > 15 * 60 * 1000 ? 1 : row.failures + 1;
  await env.DB.prepare("INSERT INTO auth_login_attempts (login_key, failures, window_started_at, locked_until) VALUES (?, ?, ?, ?) ON CONFLICT(login_key) DO UPDATE SET failures = excluded.failures, window_started_at = excluded.window_started_at, locked_until = excluded.locked_until").bind(key, failures, !row || now - row.window_started_at > 15 * 60 * 1000 ? now : row.window_started_at, failures >= limit ? now + 15 * 60 * 1000 : null).run();
}

// Failed sign-ins are counted per account *and* IP address, so nobody can lock another person out from elsewhere.
// A separate, higher limit per IP address slows down guessing across many accounts.
async function staffLoginGuard(env, request, loginKey, now = Date.now()) {
  const ipHash = (await digest(request.headers.get("CF-Connecting-IP") || "unknown")).slice(0, 32);
  const accountKey = loginKey + "@" + ipHash, ipKey = "ip:" + ipHash;
  const { results } = await env.DB.prepare("SELECT locked_until FROM auth_login_attempts WHERE login_key IN (?, ?)").bind(accountKey, ipKey).all();
  return {
    locked: results.some((row) => Number(row.locked_until) > now),
    fail: () => Promise.all([recordLoginFailure(env, accountKey), recordLoginFailure(env, ipKey, 20)]),
    clear: () => env.DB.prepare("DELETE FROM auth_login_attempts WHERE login_key IN (?, ?)").bind(accountKey, loginKey).run()
  };
}

function staffPasswordProblem(password) {
  if (!password) return "Vul een nieuw wachtwoord in.";
  if (password.length < 12) return "Kies een wachtwoord van minimaal 12 tekens.";
  if (password.length > 512) return "Een wachtwoord mag maximaal 512 tekens hebben.";
  const normalized = password.toLocaleLowerCase("nl-NL");
  if (/^(password|wachtwoord|welkom|qwerty|admin|cohentra|eventhub)[\W_]*\d*$/i.test(password) || /^(123456|123456789|1234567890|qwerty|qwertyuiop|asdfghjkl|letmein|iloveyou)/i.test(password) || /(.)\1{5,}/.test(password) || /cohentra|eventhub/.test(normalized) && /\d{2,}$/.test(normalized)) return "Dit wachtwoord is te voorspelbaar. Kies een langere, unieke wachtzin.";
  return "";
}

async function recoveryCodesLeft(env, ownerId, staffId) {
  const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM mfa_recovery_codes WHERE used_at IS NULL AND owner_id IS ? AND staff_id IS ?").bind(ownerId, staffId).first();
  return Number(row?.n || 0);
}

async function finishStaffChallenge(env, challenge, challengeToken, now, extra = {}) {
  const mustChangePassword = !!challenge.staff_id && Number(challenge.staff_must_change_password) === 1;
  const timestamp = new Date(now).toISOString(), sessionExpiry = now + (mustChangePassword ? 10 * 60 * 1000 : 12 * 60 * 60 * 1000);
  const upgraded = await env.DB.prepare("UPDATE staff_sessions SET mfa_verified = 1, mfa_enrollment = 0, password_change_only = ?, expires_at = ?, last_seen_at = ? WHERE id = ? AND mfa_verified = 0 AND revoked_at IS NULL AND expires_at > ?").bind(mustChangePassword ? 1 : 0, sessionExpiry, timestamp, challenge.id, now).run();
  if (upgraded.meta?.changes !== 1) return json({ error: "Deze aanmeldstap is verlopen. Vul je accountgegevens opnieuw in." }, 401);
  await env.DB.prepare("UPDATE staff_sessions SET revoked_at = ? WHERE staff_id IS ? AND mfa_verified = 0 AND id <> ? AND revoked_at IS NULL").bind(timestamp, challenge.staff_id || null, challenge.id).run();
  const left = await recoveryCodesLeft(env, challenge.staff_id ? null : 1, challenge.staff_id || null);
  return json(mustChangePassword
    ? { ...extra, recovery_codes_left: left, password_change_required: true, password_change_token: challengeToken, expires_in: 600 }
    : { ...extra, recovery_codes_left: left, session_token: challengeToken });
}

async function sendStaffPasswordResetEmail(env, { staffId, isOwner, email, host }) {
  if (!env.EMAIL) throw new Error("De e-mailservice is niet beschikbaar.");
  const rawToken = randomHex(32), now = Date.now();
  await env.DB.batch([
    env.DB.prepare("UPDATE staff_password_resets SET consumed_at = ? WHERE staff_id IS ? AND is_owner = ? AND consumed_at IS NULL").bind(now, staffId, isOwner ? 1 : 0),
    env.DB.prepare("INSERT INTO staff_password_resets (token_hash, staff_id, is_owner, expires_at, created_at) VALUES (?, ?, ?, ?, ?)").bind(await digest(rawToken), staffId, isOwner ? 1 : 0, now + 30 * 60 * 1000, now)
  ]);
  const portal = host === "admin.cohentra.digital" ? "admin.cohentra.digital" : "staff.cohentra.digital";
  const link = "https://" + portal + "/?reset=" + rawToken;
  const brand = await loadEmailTemplateSettings(env, "branding");
  const subject = "Nieuw wachtwoord voor het Cohentra medewerkersportaal";
  const intro = "Je hebt gevraagd om een nieuw wachtwoord. Kies via de knop hieronder een nieuw wachtwoord. Daarna meld je aan zoals altijd, met je authenticatorcode.";
  const expiryNote = "Deze link is 30 minuten geldig en werkt één keer. Heb je dit niet aangevraagd? Dan kun je deze e-mail negeren; je wachtwoord blijft hetzelfde.";
  const html = renderAuthEmailHtml({ subject, intro, link, button: "Nieuw wachtwoord kiezen", expiryNote, brand });
  const text = subject + "\n\n" + intro + "\n\nOpen deze link (30 minuten geldig, eenmalig): " + link + "\n\nHeb je dit niet aangevraagd? Negeer deze e-mail.\n\nCohentra Digital · info@cohentra.digital";
  await env.EMAIL.send({ to: email, from: { email: "noreply@noreply.cohentra.digital", name: "Cohentra Digital" }, replyTo: "info@cohentra.digital", subject, text, html });
}

async function sendStaffInviteEmail(env, { staffId, email }) {
  if (!env.EMAIL) throw new Error("De e-mailservice is niet beschikbaar.");
  const rawToken = randomHex(32), now = Date.now(), expiresAt = now + 24 * 60 * 60 * 1000;
  await env.DB.batch([
    env.DB.prepare("UPDATE staff_password_resets SET consumed_at = ? WHERE staff_id = ? AND is_owner = 0 AND consumed_at IS NULL").bind(now, staffId),
    env.DB.prepare("INSERT INTO staff_password_resets (token_hash, staff_id, is_owner, expires_at, created_at) VALUES (?, ?, 0, ?, ?)").bind(await digest(rawToken), staffId, expiresAt, now),
    env.DB.prepare("UPDATE staff_access_tokens SET invitation_sent_at = ? WHERE id = ? AND revoked_at IS NULL").bind(new Date(now).toISOString(), staffId)
  ]);
  const link = "https://staff.cohentra.digital/?setup=" + rawToken;
  const brand = await loadEmailTemplateSettings(env, "branding");
  const subject = "Uitnodiging voor het Cohentra medewerkersportaal";
  const intro = "Je hebt toegang gekregen tot het Cohentra medewerkersportaal. Stel via de beveiligde link hieronder je persoonlijke wachtwoord in. Bij je eerste aanmelding koppel je ook je authenticator-app.";
  const expiryNote = "Deze eenmalige link is 24 uur geldig. Heb je deze uitnodiging niet verwacht? Negeer de e-mail of neem contact op via info@cohentra.digital.";
  const html = renderAuthEmailHtml({ subject, intro, link, button: "Wachtwoord instellen", expiryNote, brand });
  const text = subject + "\n\n" + intro + "\n\nKies via de beveiligde link je wachtwoord (eenmalig, 24 uur geldig): " + link + "\n\nHeb je deze uitnodiging niet verwacht? Negeer de e-mail.\n\nCohentra Digital · info@cohentra.digital";
  await env.EMAIL.send({ to: email, from: { email: "noreply@noreply.cohentra.digital", name: "Cohentra Digital" }, replyTo: "info@cohentra.digital", subject, text, html });
}

async function readJson(request, maxLength = 8192) {
  const length = Number(request.headers.get("Content-Length") || 0);
  if (length > maxLength) throw new Error("Aanvraag is te groot.");
  return await request.json();
}

function contactCorsHeaders() {
  return {
    "Access-Control-Allow-Origin": "https://cohentra.digital",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "600",
    "Vary": "Origin"
  };
}

function contactJson(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { ...JSON_HEADERS, ...contactCorsHeaders() } });
}

function contactFormPage(message, status = 200) {
  const safeMessage = String(message).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
  const isError = status >= 400;
  const label = isError ? "Niet verstuurd" : "Aanvraag ontvangen";
  const labelStyle = isError ? "color:#be4054;background:#fdecee" : "color:#138a66;background:#e5f5ee";
  const html = `<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#f6f8fc"><link rel="icon" type="image/png" href="https://customer.cohentra.digital/brand/cohentra-beeldmerk.png"><title>Contact · Cohentra Digital</title><body style="margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;box-sizing:border-box;background:radial-gradient(ellipse at 50% 0%,rgba(45,100,212,.1),transparent 55%),#f6f8fc;color:#121e36;font:16px/1.65 system-ui,-apple-system,'Segoe UI',sans-serif"><main style="width:100%;max-width:520px;text-align:center"><img src="${EMAIL_LOGO_URL}" width="140" height="44" alt="Cohentra Digital" style="display:block;height:44px;width:auto;margin:0 auto 26px"><div style="padding:34px 30px 32px;border:1px solid #dbe3ee;border-radius:16px;background:#fff;box-shadow:0 22px 60px rgba(18,30,54,.08)"><p style="display:inline-block;margin:0 0 16px;padding:4px 12px;border-radius:99px;font-size:12px;font-weight:700;letter-spacing:.04em;${labelStyle}">${label}</p><h1 style="margin:0;font-size:clamp(22px,5vw,28px);line-height:1.3;font-weight:700;letter-spacing:-.01em">${safeMessage}</h1><a style="display:inline-block;margin-top:24px;padding:12px 20px;border-radius:99px;background:#2d64d4;color:#fff;text-decoration:none;font-weight:700;font-size:14px" href="https://cohentra.digital/#contact">Terug naar Cohentra</a></div><p style="margin:18px 0 0;color:#66727e;font-size:13px">Vragen? Mail <a style="color:#2d64d4" href="mailto:info@cohentra.digital">info@cohentra.digital</a></p></main></body></html>`;
  return new Response(html, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer" } });
}

async function readContactBody(request) {
  const declaredLength = Number(request.headers.get("Content-Length") || 0);
  if (declaredLength > 8192) throw new Error("Aanvraag is te groot.");
  const reader = request.body?.getReader();
  if (!reader) return {};
  const chunks = [];
  let totalLength = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      totalLength += value.byteLength;
      if (totalLength > 8192) {
        try { await reader.cancel(); } catch {}
        throw new Error("Aanvraag is te groot.");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  const raw = new TextDecoder().decode(bytes);
  const contentType = (request.headers.get("Content-Type") || "").split(";", 1)[0].trim().toLowerCase();
  if (contentType === "application/json") return JSON.parse(raw);
  if (contentType === "application/x-www-form-urlencoded") return Object.fromEntries(new URLSearchParams(raw));
  throw new Error("Ongeldig aanvraagformaat.");
}

async function handlePublicContact(request, env) {
  const origin = request.headers.get("Origin") || "";
  const contentType = (request.headers.get("Content-Type") || "").split(";", 1)[0].trim().toLowerCase();
  const isJson = contentType === "application/json";
  const respond = (data, status = 200) => isJson
    ? contactJson(data, status)
    : contactFormPage(data.error || `Bedankt. Je aanvraag ${data.reference} is ontvangen. Cohentra Support neemt per e-mail contact met je op.`, status);

  if (request.method === "OPTIONS") {
    const requestedHeaders = (request.headers.get("Access-Control-Request-Headers") || "").split(",").map((value) => value.trim().toLowerCase()).filter(Boolean);
    if (origin !== "https://cohentra.digital" || request.headers.get("Access-Control-Request-Method") !== "POST" || requestedHeaders.some((header) => header !== "content-type")) {
      return new Response(null, { status: 403 });
    }
    return new Response(null, { status: 204, headers: contactCorsHeaders() });
  }
  if (request.method !== "POST") return json({ error: "Niet gevonden." }, 404);
  if (origin !== "https://cohentra.digital") return isJson ? json({ error: "Aanvraag niet toegestaan." }, 403) : contactFormPage("Deze aanvraag is niet toegestaan.", 403);

  const nowMs = Date.now();
  const windowStartedAt = Math.floor(nowMs / (60 * 60 * 1000));
  const ipHash = await digest(request.headers.get("CF-Connecting-IP") || "unknown");
  await env.DB.batch([
    env.DB.prepare("DELETE FROM website_contact_rate_limits WHERE window_started_at < ?").bind(windowStartedAt - 24),
    env.DB.prepare("INSERT INTO website_contact_rate_limits (ip_hash, window_started_at, request_count) VALUES (?, ?, 1) ON CONFLICT(ip_hash, window_started_at) DO UPDATE SET request_count = request_count + 1").bind(ipHash, windowStartedAt)
  ]);
  const rateLimit = await env.DB.prepare("SELECT request_count FROM website_contact_rate_limits WHERE ip_hash = ? AND window_started_at = ?").bind(ipHash, windowStartedAt).first();
  if (Number(rateLimit?.request_count || 0) > 5) return respond({ error: "Je hebt veel aanvragen kort na elkaar verstuurd. Probeer het later opnieuw." }, 429);

  let body;
  try { body = await readContactBody(request); } catch (error) {
    const status = String(error?.message || "").includes("te groot") ? 413 : 400;
    return respond({ error: status === 413 ? "Je bericht is te groot." : "Vul het formulier opnieuw in en probeer het nog eens." }, status);
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) return respond({ error: "Vul het formulier opnieuw in en probeer het nog eens." }, 400);
  if (String(body.company_site || "").trim()) {
    const reference = `CH-${new Date().getUTCFullYear()}-${randomHex(5).toUpperCase()}`;
    return respond({ ok: true, reference }, 201);
  }

  const name = String(body.name || "").trim();
  const email = String(body.email || "").trim();
  const organization = String(body.organization || "").trim();
  const requestType = String(body.request_type || "").trim();
  const subject = String(body.subject || "").trim();
  const message = String(body.message || "").trim();
  if (!name || name.length > 120 || !/^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(email) || email.length > 254 || organization.length > 160 || !WEBSITE_REQUEST_TYPES[requestType] || !subject || subject.length > 120 || !message || message.length > 5000) {
    return respond({ error: "Controleer je naam, e-mailadres, onderwerp en bericht." }, 400);
  }

  const now = new Date().toISOString();
  const id = crypto.randomUUID();
  const reference = `CH-${new Date(now).getUTCFullYear()}-${randomHex(5).toUpperCase()}`;
  const ticketMessage = [
    `Bron: Websiteformulier`,
    `Type aanvraag: ${WEBSITE_REQUEST_TYPES[requestType]}`,
    `Bedrijf of organisatie: ${organization || "Niet opgegeven"}`,
    "",
    message
  ].join("\n");

  await env.DB.batch([
    env.DB.prepare("INSERT OR IGNORE INTO customers (id, name, contact_name, contact_email, notes, status, created_at, updated_at) VALUES (?, 'Websiteformulieraanvragen', '', '', 'Interne inbox voor websitecontacten.', 'paused', ?, ?)").bind(WEBSITE_CONTACT_CUSTOMER_ID, now, now),
    env.DB.prepare("INSERT INTO support_tickets (id, reference, customer_id, created_by_account_id, category, subject, message, status, assigned_to, created_at, updated_at, source, contact_name, contact_email, organization, request_type) VALUES (?, ?, ?, NULL, 'other', ?, ?, 'new', NULL, ?, ?, 'website', ?, ?, ?, ?)").bind(id, reference, WEBSITE_CONTACT_CUSTOMER_ID, subject, ticketMessage, now, now, name, email, organization, requestType)
  ]);

  const emailSent = await sendSupportTicketEmail(env, {
    reference,
    source: "website",
    customerName: name,
    contactEmail: email,
    category: `Websiteformulier · ${WEBSITE_REQUEST_TYPES[requestType]}`,
    subject,
    message: ticketMessage
  });
  return respond({ ok: true, reference, source: "website", email_sent: emailSent }, 201);
}

async function handle(request, env) {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/health") {
    await env.DB.prepare("SELECT 1 AS ok").first();
    return json({ status: "ok" });
  }
  if (url.pathname === "/api/public/contact" && url.hostname === "support.cohentra.digital") return await handlePublicContact(request, env);
  if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/admin")) {
    const host = url.hostname.toLowerCase();
    if ((host === "customer.cohentra.digital" || host === "support.cohentra.digital" || host === "staff.cohentra.digital") && url.pathname !== "/") return json({ error: "Niet gevonden." }, 404);
    if (host === "support.cohentra.digital") return Response.redirect("https://staff.cohentra.digital/", 302);
    const html = host === "customer.cohentra.digital" ? CUSTOMER_PORTAL_HTML : ADMIN_PAGE_HTML;
    return new Response(html, { headers: {
      "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store",
      "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' blob:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
      "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"
    }});
  }
  if (request.method === "POST" && url.pathname === "/api/customer/auth/forgot-password") {
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const email = String(body.email || "").trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) return json({ error: "Vul een geldig e-mailadres in." }, 400);
    const now = Date.now(), emailKey = await digest(email), ipKey = await digest(request.headers.get("CF-Connecting-IP") || "unknown");
    const [emailAttempts, ipAttempts] = await Promise.all([
      recordCustomerAuthRequest(env, "email:" + emailKey, now),
      recordCustomerAuthRequest(env, "ip:" + ipKey, now)
    ]);
    if (emailAttempts > 5 || ipAttempts > 20) return json({ error: "Te veel verzoeken. Probeer het later opnieuw." }, 429);
    const account = await env.DB.prepare("SELECT a.id, a.active, a.email, a.username FROM customer_portal_accounts a JOIN customers c ON c.id = a.customer_id WHERE (a.username = ? COLLATE NOCASE OR a.email = ? COLLATE NOCASE) AND a.disabled_at IS NULL AND c.status = 'active' ORDER BY a.active DESC LIMIT 1").bind(email, email).first();
    if (account) {
      const recipient = String(account.email || account.username || email).trim().toLowerCase();
      try { await sendCustomerAuthEmail(env, account.id, recipient, account.active === 1 ? "password_reset" : "invite"); }
      catch (error) { console.error("Customer account email could not be sent", error); }
    }
    return json({ message: "Als er een actief klantenportaalaccount bij dit e-mailadres hoort, ontvang je zo een e-mail met een beveiligde link." });
  }
  if (request.method === "POST" && url.pathname === "/api/customer/auth/complete-email-auth") {
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const rawToken = String(body.token || ""), flow = String(body.flow || ""), password = String(body.password || "");
    if (!/^[a-f0-9]{64}$/i.test(rawToken) || !["invite", "reset"].includes(flow) || password.length < 10 || password.length > 512) return json({ error: "Gebruik een wachtwoord van minimaal 10 tekens en maximaal 512 tekens." }, 400);
    const purpose = flow === "invite" ? "invite" : "password_reset", now = Date.now();
    const tokenRow = await env.DB.prepare("SELECT t.customer_account_id, a.active, c.status AS customer_status FROM customer_auth_tokens t JOIN customer_portal_accounts a ON a.id = t.customer_account_id JOIN customers c ON c.id = a.customer_id WHERE t.token_hash = ? AND t.purpose = ? AND t.consumed_at IS NULL AND t.expires_at > ? AND a.disabled_at IS NULL LIMIT 1").bind(await digest(rawToken), purpose, now).first();
    if (!tokenRow || tokenRow.customer_status !== "active") return json({ error: "Deze link is verlopen of al gebruikt. Vraag een nieuwe link aan." }, 400);
    const credentials = await hashPassword(password), changedAt = Date.now();
    const results = await env.DB.batch([
      env.DB.prepare("UPDATE customer_auth_tokens SET consumed_at = ? WHERE token_hash = ? AND purpose = ? AND consumed_at IS NULL AND expires_at > ?").bind(changedAt, await digest(rawToken), purpose, now),
      env.DB.prepare("UPDATE customer_portal_accounts SET password_salt = ?, password_hash = ?, active = 1, updated_at = ? WHERE id = ? AND EXISTS (SELECT 1 FROM customer_auth_tokens WHERE token_hash = ? AND consumed_at = ?)").bind(credentials.salt, credentials.hash, new Date(changedAt).toISOString(), tokenRow.customer_account_id, await digest(rawToken), changedAt),
      env.DB.prepare("UPDATE customer_sessions SET revoked_at = ? WHERE customer_account_id = ? AND revoked_at IS NULL").bind(new Date(changedAt).toISOString(), tokenRow.customer_account_id)
    ]);
    if (results[0]?.meta?.changes !== 1) return json({ error: "Deze link is verlopen of al gebruikt. Vraag een nieuwe link aan." }, 400);
    return json({ ok: true });
  }
  if (url.pathname === "/api/customer/auth/register" || url.pathname === "/api/customer/auth/verify-email") {
    const registration = await handleCustomerAuthExtra(request, env, url, accountHelpers());
    if (registration) return registration;
  }
  if (request.method === "POST" && url.pathname === "/api/customer/auth/login") {
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const username = String(body.username || "").trim().toLowerCase(), password = String(body.password || "");
    if (!username || username.length > 254 || !password || password.length > 512) return json({ error: "Vul je gebruikersnaam en wachtwoord in." }, 400);
    const account = await env.DB.prepare("SELECT a.id, a.password_salt, a.password_hash, a.active, a.disabled_at, c.status AS customer_status FROM customer_portal_accounts a JOIN customers c ON c.id = a.customer_id WHERE a.username = ? COLLATE NOCASE LIMIT 1").bind(username).first();
    const loginKey = account ? `customer:${account.id}` : `customer-unknown:${await digest(username)}`, now = Date.now();
    const attempt = await env.DB.prepare("SELECT locked_until FROM auth_login_attempts WHERE login_key = ?").bind(loginKey).first();
    if (attempt?.locked_until > now) return json({ error: "Te veel mislukte pogingen. Probeer het over 15 minuten opnieuw." }, 429);
    const valid = !!account && account.active === 1 && !account.disabled_at && account.customer_status === "active" && await passwordMatches(password, account.password_salt, account.password_hash);
    if (!valid) { await recordLoginFailure(env, loginKey); return json({ error: "Gebruikersnaam of wachtwoord onjuist, of klanttoegang is gepauzeerd." }, 401); }
    await env.DB.prepare("DELETE FROM auth_login_attempts WHERE login_key = ?").bind(loginKey).run();
    return json({ session_token: await issueCustomerSession(env, account.id), expires_in: 43200 });
  }
  if (request.method === "POST" && url.pathname === "/api/customer/auth/logout") {
    const match = /^Bearer\s+(.+)$/i.exec(request.headers.get("Authorization") || "");
    if (match) await env.DB.prepare("UPDATE customer_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL").bind(new Date().toISOString(), await digest(match[1])).run();
    return json({ ok: true });
  }
  if (url.pathname.startsWith("/api/customer/")) {
    const customer = await customerAuthorized(request, env);
    if (!customer) return json({ error: "Sessie verlopen of klanttoegang niet actief. Meld opnieuw aan of neem contact op met Cohentra." }, 401);
    if (request.method === "GET" && url.pathname === "/api/customer/tickets") {
      const { results } = await env.DB.prepare("SELECT reference, subject, category, status, created_at, updated_at FROM support_tickets WHERE customer_id = ? ORDER BY created_at DESC LIMIT 100").bind(customer.customer_id).all();
      return json({ tickets: results });
    }
    if (request.method === "POST" && url.pathname === "/api/customer/tickets") {
      let body; try { body = await readJson(request, 16384); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const category = ["eventhub", "license", "account", "other"].includes(body.category) ? body.category : "";
      const subject = String(body.subject || "").trim(), message = String(body.message || "").trim();
      if (!category || !subject || subject.length > 120 || !message || message.length > 6000) return json({ error: "Vul een categorie, korte omschrijving en bericht in (maximaal 6.000 tekens)." }, 400);
      const now = new Date().toISOString(), since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
      const recent = await env.DB.prepare("SELECT COUNT(*) AS count FROM support_tickets WHERE customer_id = ? AND created_at >= ?").bind(customer.customer_id, since).first();
      if (Number(recent?.count || 0) >= 10) return json({ error: "Je kunt maximaal 10 supportaanvragen per 24 uur indienen. Mail bij spoed naar support@cohentra.digital." }, 429);
      const id = crypto.randomUUID(), reference = `CH-${new Date(now).getUTCFullYear()}-${randomHex(5).toUpperCase()}`;
      await env.DB.prepare("INSERT INTO support_tickets (id, reference, customer_id, created_by_account_id, category, subject, message, status, created_at, updated_at, contact_name, contact_email) VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?)").bind(id, reference, customer.customer_id, customer.account_id, category, subject, message, now, now, customer.account_name || "", customer.account_email || customer.username).run();
      const emailSent = await sendSupportTicketEmail(env, { reference, customerName: customer.customer_name, contactEmail: customer.username, category, subject, message });
      return json({ ok: true, reference, status: "new", created_at: now, email_sent: emailSent }, 201);
    }
    const accountShop = await handleCustomerAccountShop(request, env, url, customer, accountHelpers());
    if (accountShop) return accountShop;
    if (SHOP_CUSTOMER_ROUTES.some((pattern) => pattern.test(url.pathname))) {
      if (!env.SHOP) return json({ error: "De shop is nog niet gekoppeld. Neem contact op met Cohentra." }, 503);
      return await env.SHOP.customer(request, shopIdentity(customer));
    }
    if (request.method === "GET" && url.pathname === "/api/customer/me") {
      if (!customer.legacy_licensing) return json({ customer: { name: customer.customer_name, username: customer.username, role: customer.account_role, customer_type: customer.customer_type, legacy_licensing: false } });
      const used = await env.DB.prepare("SELECT COUNT(*) AS count FROM licenses WHERE customer_id = ? AND product_id = 'eventhub' AND revoked_at IS NULL AND valid_until >= ?").bind(customer.customer_id, new Date().toISOString().slice(0, 10)).first();
      return json({ customer: { name: customer.customer_name, username: customer.username, role: customer.account_role, customer_type: customer.customer_type, legacy_licensing: true, max_licenses: customer.max_licenses, licenses_in_use: Number(used?.count || 0), allowed_license_types: customer.allowed_license_types } });
    }
    if (request.method === "GET" && url.pathname === "/api/customer/licenses") {
      const { results } = await env.DB.prepare("SELECT id, label, valid_from, valid_until, created_at, revoked_at, license_type FROM licenses WHERE customer_id = ? AND product_id = 'eventhub' AND entitlement_id IS NULL ORDER BY created_at DESC LIMIT 500").bind(customer.customer_id).all();
      const today = new Date().toISOString().slice(0, 10);
      return json({ licenses: results.map((row) => ({ ...row, valid_until: row.valid_until === UNLIMITED_UNTIL ? "Onbeperkt" : row.valid_until, license_type: row.license_type || (row.valid_until === UNLIMITED_UNTIL ? "Beheerder" : "Gesloten beta"), status: row.revoked_at ? "Ingetrokken" : today < row.valid_from ? "Gepland" : today > row.valid_until ? "Verlopen" : "Actief" })) });
    }
    if (request.method === "POST" && url.pathname === "/api/customer/licenses") {
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      if (!customer.legacy_licensing || customer.account_role !== "admin") return json({ error: "Je account kan geen licenties uit het EventHub-quotum aanmaken." }, 403);
      const type = body.license_type === "admin" ? "admin" : body.license_type === "beta" ? "beta" : "";
      const validFrom = String(body.valid_from || ""), unlimited = type === "admin", validUntil = unlimited ? UNLIMITED_UNTIL : String(body.valid_until || "");
      const count = Number(body.count || 1), label = String(body.label || "").trim().slice(0, 80);
      if (!type || !customer.allowed_license_types.includes(type)) return json({ error: "Dit licentietype is niet toegestaan voor jouw account." }, 403);
      if (!Number.isInteger(count) || count !== 1) return json({ error: "Je kunt via het portaal één licentie tegelijk aanmaken." }, 400);
      if (!isIsoDate(validFrom) || (!unlimited && (!isIsoDate(validUntil) || validUntil < validFrom))) return json({ error: "Controleer de begindatum en einddatum." }, 400);
      const used = await env.DB.prepare("SELECT COUNT(*) AS count FROM licenses WHERE customer_id = ? AND product_id = 'eventhub' AND revoked_at IS NULL AND valid_until >= ?").bind(customer.customer_id, new Date().toISOString().slice(0, 10)).first();
      if (Number(used?.count || 0) >= Number(customer.max_licenses)) return json({ error: `De klantlimiet is bereikt (${used?.count || 0} van ${customer.max_licenses} in gebruik).` }, 409);
      const licenseKey = createLicenseKey(), id = crypto.randomUUID(), createdAt = new Date().toISOString();
      const inserted = await env.DB.prepare("INSERT INTO licenses (id, key_hash, label, created_at, valid_from, valid_until, license_type, customer_id, product_id) SELECT ?, ?, ?, ?, ?, ?, ?, ?, 'eventhub' WHERE (SELECT COUNT(*) FROM licenses WHERE customer_id = ? AND product_id = 'eventhub' AND revoked_at IS NULL AND valid_until >= ?) < ?").bind(id, await digest(normalizedKey(licenseKey)), label, createdAt, validFrom, validUntil, type === "admin" ? "Beheerder" : "Gesloten beta", customer.customer_id, customer.customer_id, new Date().toISOString().slice(0, 10), customer.max_licenses).run();
      if (inserted.meta?.changes !== 1) return json({ error: "De klantlimiet is net bereikt. Vernieuw het overzicht en probeer het opnieuw." }, 409);
      return json({ license: { id, license_key: licenseKey } }, 201);
    }
    const customerRevoke = /^\/api\/customer\/licenses\/([0-9a-f-]{36})\/revoke$/i.exec(url.pathname);
    if (customerRevoke && request.method === "POST") {
      if (customer.account_role !== "admin") return json({ error: "Alleen een beheerder van jullie account kan licenties intrekken." }, 403);
      const result = await env.DB.prepare("UPDATE licenses SET revoked_at = ? WHERE id = ? AND customer_id = ? AND product_id = 'eventhub' AND entitlement_id IS NULL AND revoked_at IS NULL").bind(new Date().toISOString(), customerRevoke[1], customer.customer_id).run();
      if (!result.meta?.changes) return json({ error: "Actieve licentie niet gevonden voor jouw account." }, 404);
      return json({ ok: true });
    }
    if (request.method === "POST" && url.pathname === "/api/customer/account/password") {
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const oldPassword = String(body.old_password || ""), newPassword = String(body.new_password || "");
      if (!newPassword || newPassword.length > 512) return json({ error: "Vul een geldig nieuw wachtwoord in." }, 400);
      const account = await env.DB.prepare("SELECT password_salt, password_hash FROM customer_portal_accounts WHERE id = ? AND active = 1").bind(customer.account_id).first();
      if (!account || !await passwordMatches(oldPassword, account.password_salt, account.password_hash)) return json({ error: "Het huidige wachtwoord is onjuist." }, 401);
      const credentials = await hashPassword(newPassword), timestamp = new Date().toISOString();
      await env.DB.batch([
        env.DB.prepare("UPDATE customer_portal_accounts SET password_salt = ?, password_hash = ?, updated_at = ? WHERE id = ? AND active = 1").bind(credentials.salt, credentials.hash, timestamp, customer.account_id),
        env.DB.prepare("UPDATE customer_sessions SET revoked_at = ? WHERE customer_account_id = ? AND revoked_at IS NULL").bind(timestamp, customer.account_id)
      ]);
      return json({ session_token: await issueCustomerSession(env, customer.account_id) });
    }
    return json({ error: "Niet gevonden." }, 404);
  }
  if (request.method === "POST" && url.pathname === "/api/auth/challenge") {
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const username = String(body.username || "").trim().toLowerCase(), password = String(body.password || "");
    if (!username || username.length > 254 || !password || password.length > 512) return json({ error: "Vul je gebruikersnaam en wachtwoord in." }, 400);
    const owner = await env.DB.prepare("SELECT username, password_salt, password_hash, mfa_enabled FROM owner_mfa WHERE username = ? COLLATE NOCASE").bind(username).first();
    const staff = owner ? null : await env.DB.prepare("SELECT id, name, username, password_salt, password_hash, mfa_enabled, totp_secret_enc FROM staff_access_tokens WHERE username = ? COLLATE NOCASE AND revoked_at IS NULL").bind(username).first();
    const account = owner || staff, loginKey = account ? (owner ? "owner" : `staff:${staff.id}`) : `unknown:${await digest(username)}`, now = Date.now();
    const guard = await staffLoginGuard(env, request, loginKey, now);
    if (guard.locked) return json({ error: "Te veel mislukte pogingen. Probeer het over 15 minuten opnieuw." }, 429);
    const validPassword = owner ? await passwordMatches(password, owner.password_salt, owner.password_hash) : staff ? await passwordMatches(password, staff.password_salt, staff.password_hash) : false;
    if (!validPassword) { await guard.fail(); return json({ error: "Gebruikersnaam of wachtwoord onjuist." }, 401); }
    if (owner && !owner.mfa_enabled) return json({ enrollment_required: true });
    const challenge = randomHex(32), id = crypto.randomUUID(), createdAt = new Date(now).toISOString();
    if (staff && !(staff.mfa_enabled && staff.totp_secret_enc)) {
      // First sign-in, or the owner reset 2FA: the staff member links their own authenticator now.
      await env.DB.prepare("INSERT INTO staff_sessions (id, token_hash, staff_id, actor_role, created_at, expires_at, last_seen_at, mfa_verified, mfa_enrollment) VALUES (?, ?, ?, 'support', ?, ?, ?, 0, 1)").bind(id, await digest(challenge), staff.id, createdAt, now + 10 * 60 * 1000, createdAt).run();
      return json({ challenge_token: challenge, mfa_enrollment_required: true, expires_in: 600 });
    }
    await env.DB.prepare("INSERT INTO staff_sessions (id, token_hash, staff_id, actor_role, created_at, expires_at, last_seen_at, mfa_verified) VALUES (?, ?, ?, ?, ?, ?, ?, 0)").bind(id, await digest(challenge), staff ? staff.id : null, staff ? "support" : "owner", createdAt, now + 5 * 60 * 1000, createdAt).run();
    return json({ challenge_token: challenge, expires_in: 300 });
  }
  if (request.method === "POST" && url.pathname === "/api/auth/login") {
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const challengeToken = String(body.challenge_token || ""), code = String(body.mfa_code || "").replace(/[\s-]/g, ""), recoveryCode = String(body.recovery_code || "");
    if (!/^[0-9a-f]{64}$/i.test(challengeToken)) return json({ error: "Deze aanmeldstap is verlopen. Vul je accountgegevens opnieuw in." }, 401);
    const now = Date.now(), challengeHash = await digest(challengeToken);
    const challenge = await env.DB.prepare("SELECT ss.id, ss.staff_id, ss.actor_role, ss.expires_at, ss.mfa_verified, ss.mfa_enrollment, st.mfa_enabled AS staff_mfa_enabled, st.totp_secret_enc AS staff_secret, st.last_totp_counter AS staff_counter, st.revoked_at AS staff_revoked, st.must_change_password AS staff_must_change_password, om.mfa_enabled AS owner_mfa_enabled, om.totp_secret_enc AS owner_secret, om.last_totp_counter AS owner_counter FROM staff_sessions ss LEFT JOIN staff_access_tokens st ON st.id = ss.staff_id LEFT JOIN owner_mfa om ON ss.staff_id IS NULL AND om.id = 1 WHERE ss.token_hash = ? AND ss.revoked_at IS NULL").bind(challengeHash).first();
    if (!challenge || challenge.mfa_verified || challenge.mfa_enrollment || challenge.expires_at <= now || challenge.staff_revoked) return json({ error: "Deze aanmeldstap is verlopen. Vul je accountgegevens opnieuw in." }, 401);
    const guard = await staffLoginGuard(env, request, challenge.staff_id ? `staff:${challenge.staff_id}` : "owner", now);
    if (guard.locked) return json({ error: "Te veel mislukte pogingen. Probeer het over 15 minuten opnieuw." }, 429);
    let accepted = false;
    if (recoveryCode) accepted = await consumeRecoveryCode(env, recoveryCode, challenge.staff_id ? null : 1, challenge.staff_id || null);
    else if (/^\d{6}$/.test(code) && challenge.staff_id && challenge.staff_mfa_enabled && challenge.staff_secret) {
      const secret = await decryptMfaSecret(challenge.staff_secret, env), counter = await totpCounter(secret, code, now, challenge.staff_counter);
      if (counter !== null) accepted = (await env.DB.prepare("UPDATE staff_access_tokens SET last_totp_counter = ? WHERE id = ? AND last_totp_counter < ? AND revoked_at IS NULL").bind(counter, challenge.staff_id, counter).run()).meta?.changes === 1;
    } else if (/^\d{6}$/.test(code) && !challenge.staff_id && challenge.owner_mfa_enabled && challenge.owner_secret) {
      const secret = await decryptMfaSecret(challenge.owner_secret, env), counter = await totpCounter(secret, code, now, challenge.owner_counter);
      if (counter !== null) accepted = (await env.DB.prepare("UPDATE owner_mfa SET last_totp_counter = ? WHERE id = 1 AND last_totp_counter < ?").bind(counter, counter).run()).meta?.changes === 1;
    }
    if (!accepted) { await guard.fail(); return json({ error: recoveryCode ? "Deze herstelcode klopt niet of is al gebruikt." : "Die code klopt niet. Probeer de nieuwste code uit je authenticator-app." }, 401); }
    await guard.clear();
    return await finishStaffChallenge(env, challenge, challengeToken, now);
  }
  if (request.method === "POST" && (url.pathname === "/api/auth/mfa/enroll" || url.pathname === "/api/auth/mfa/enroll/confirm")) {
    const match = /^Bearer\s+([0-9a-f]{64})$/i.exec(request.headers.get("Authorization") || "");
    const expired = () => json({ error: "Deze aanmeldstap is verlopen. Vul je accountgegevens opnieuw in." }, 401);
    if (!match) return expired();
    const now = Date.now(), challengeToken = match[1];
    const challenge = await env.DB.prepare("SELECT ss.id, ss.staff_id, ss.expires_at, ss.mfa_verified, ss.mfa_enrollment, st.username, st.mfa_enabled AS staff_mfa_enabled, st.totp_secret_enc AS staff_secret, st.revoked_at AS staff_revoked, st.must_change_password AS staff_must_change_password FROM staff_sessions ss JOIN staff_access_tokens st ON st.id = ss.staff_id WHERE ss.token_hash = ? AND ss.revoked_at IS NULL").bind(await digest(challengeToken)).first();
    if (!challenge || challenge.mfa_verified || !challenge.mfa_enrollment || challenge.expires_at <= now || challenge.staff_revoked || challenge.staff_mfa_enabled) return expired();
    if (url.pathname === "/api/auth/mfa/enroll") {
      let secret = challenge.staff_secret ? await decryptMfaSecret(challenge.staff_secret, env).catch(() => null) : null;
      if (!secret) {
        secret = encodeBase32(crypto.getRandomValues(new Uint8Array(20)));
        await env.DB.prepare("UPDATE staff_access_tokens SET totp_secret_enc = ?, last_totp_counter = -1 WHERE id = ? AND mfa_enabled = 0").bind(await encryptMfaSecret(secret, env), challenge.staff_id).run();
      }
      return json({ secret, account: challenge.username, issuer: "Cohentra" });
    }
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const guard = await staffLoginGuard(env, request, `staff:${challenge.staff_id}`, now);
    if (guard.locked) return json({ error: "Te veel mislukte pogingen. Probeer het over 15 minuten opnieuw." }, 429);
    if (!challenge.staff_secret) return json({ error: "Start de koppeling opnieuw door opnieuw aan te melden." }, 409);
    const counter = await totpCounter(await decryptMfaSecret(challenge.staff_secret, env), String(body.code || "").replace(/[\s-]/g, ""), now);
    if (counter === null) { await guard.fail(); return json({ error: "Die code klopt niet. Controleer of de tijd op je telefoon klopt en probeer de nieuwste code." }, 400); }
    const enabled = await env.DB.prepare("UPDATE staff_access_tokens SET mfa_enabled = 1, last_totp_counter = ? WHERE id = ? AND mfa_enabled = 0 AND revoked_at IS NULL").bind(counter, challenge.staff_id).run();
    if (enabled.meta?.changes !== 1) return json({ error: "Deze koppeling is al afgerond. Meld opnieuw aan." }, 409);
    const recovery_codes = await createRecoveryCodes(env, null, challenge.staff_id);
    await guard.clear();
    return await finishStaffChallenge(env, challenge, challengeToken, now, { recovery_codes });
  }
  if (request.method === "POST" && url.pathname === "/api/auth/password/first-change") {
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const newPassword = String(body.new_password || ""), confirmPassword = String(body.confirm_password || "");
    const problem = staffPasswordProblem(newPassword);
    if (problem) return json({ error: problem }, 400);
    if (newPassword !== confirmPassword) return json({ error: "De nieuwe wachtwoorden komen niet overeen." }, 400);
    const match = /^Bearer\s+(.+)$/i.exec(request.headers.get("Authorization") || "");
    if (!match) return json({ error: "De wachtwoordstap is verlopen. Meld opnieuw aan." }, 401);
    const now = Date.now(), tokenHash = await digest(match[1]);
    const session = await env.DB.prepare("SELECT ss.id, ss.staff_id, st.password_salt, st.password_hash FROM staff_sessions ss JOIN staff_access_tokens st ON st.id = ss.staff_id WHERE ss.token_hash = ? AND ss.password_change_only = 1 AND ss.mfa_verified = 1 AND ss.revoked_at IS NULL AND ss.expires_at > ? AND st.must_change_password = 1 AND st.revoked_at IS NULL").bind(tokenHash, now).first();
    if (!session) return json({ error: "De tijdelijke wachtwoordstap is verlopen. Meld opnieuw aan." }, 401);
    if (await passwordMatches(newPassword, session.password_salt, session.password_hash)) return json({ error: "Kies een ander wachtwoord dan het tijdelijke wachtwoord." }, 400);
    const credentials = await hashPassword(newPassword), timestamp = new Date(now).toISOString();
    const updates = await env.DB.batch([
      env.DB.prepare("UPDATE staff_access_tokens SET password_salt = ?, password_hash = ?, must_change_password = 0 WHERE id = ? AND must_change_password = 1 AND revoked_at IS NULL").bind(credentials.salt, credentials.hash, session.staff_id),
      env.DB.prepare("UPDATE staff_sessions SET password_change_only = 0, expires_at = ?, last_seen_at = ? WHERE id = ? AND token_hash = ? AND password_change_only = 1 AND mfa_verified = 1 AND revoked_at IS NULL AND expires_at > ?").bind(now + 12 * 60 * 60 * 1000, timestamp, session.id, tokenHash, now),
      env.DB.prepare("UPDATE staff_sessions SET revoked_at = ? WHERE staff_id = ? AND id <> ? AND revoked_at IS NULL").bind(timestamp, session.staff_id, session.id)
    ]);
    if (Number(updates[0]?.meta?.changes) !== 1 || Number(updates[1]?.meta?.changes) !== 1) return json({ error: "Het wachtwoord kon niet worden bijgewerkt. Meld opnieuw aan." }, 409);
    return json({ ok: true, session_token: match[1] });
  }
  if (request.method === "POST" && url.pathname === "/api/auth/mfa/setup") {
    const match = /^Bearer\s+(.+)$/i.exec(request.headers.get("Authorization") || "");
    if (!match || !env.ADMIN_TOKEN || !constantTimeEqual(match[1], env.ADMIN_TOKEN)) return json({ error: "Alleen de Cohentra-beheerderssleutel kan de eerste 2FA instellen." }, 401);
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const username = String(body.username || "").trim().toLowerCase();
    const password = String(body.password || "");
    if (!username || username.length > 254 || !password || password.length > 512) return json({ error: "Vul een gebruikersnaam en wachtwoord in." }, 400);
    const existingUsername = await env.DB.prepare("SELECT 1 AS found FROM staff_access_tokens WHERE username = ? COLLATE NOCASE UNION ALL SELECT 1 AS found FROM owner_mfa WHERE username = ? COLLATE NOCASE LIMIT 1").bind(username, username).first();
    if (existingUsername && !(await env.DB.prepare("SELECT 1 AS pending FROM owner_mfa WHERE id = 1 AND mfa_enabled = 0 AND username = ? COLLATE NOCASE").bind(username).first())) return json({ error: "Deze gebruikersnaam is al in gebruik." }, 409);
    const current = await env.DB.prepare("SELECT mfa_enabled, totp_secret_enc FROM owner_mfa WHERE id = 1").first();
    if (current?.mfa_enabled) return json({ error: "2FA is al ingesteld. Meld aan met je authenticatorcode." }, 409);
    const secret = current?.totp_secret_enc ? await decryptMfaSecret(current.totp_secret_enc, env).catch(() => null) : null;
    const generated = secret || encodeBase32(crypto.getRandomValues(new Uint8Array(20)));
    const encrypted = await encryptMfaSecret(generated, env);
    const credentials = await hashPassword(password);
    await env.DB.prepare("INSERT INTO owner_mfa (id, totp_secret_enc, mfa_enabled, last_totp_counter, username, password_salt, password_hash) VALUES (1, ?, 0, -1, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET totp_secret_enc = excluded.totp_secret_enc, username = excluded.username, password_salt = excluded.password_salt, password_hash = excluded.password_hash").bind(encrypted, username, credentials.salt, credentials.hash).run();
    return json({ secret: generated, account: "Cohentra Admin", issuer: "Cohentra" });
  }
  if (request.method === "POST" && url.pathname === "/api/auth/mfa/confirm") {
    const match = /^Bearer\s+(.+)$/i.exec(request.headers.get("Authorization") || "");
    if (!match || !env.ADMIN_TOKEN || !constantTimeEqual(match[1], env.ADMIN_TOKEN)) return json({ error: "Aanmelden met de Cohentra-beheerderssleutel is vereist." }, 401);
    const current = await env.DB.prepare("SELECT totp_secret_enc, mfa_enabled, username FROM owner_mfa WHERE id = 1").first();
    if (!current || current.mfa_enabled) return json({ error: "Start eerst de 2FA-instelling." }, 409);
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const secret = await decryptMfaSecret(current.totp_secret_enc, env);
    const counter = await totpCounter(secret, String(body.code || "").replace(/[\s-]/g, ""));
    if (counter === null) return json({ error: "De code klopt niet. Controleer de tijd op je telefoon en probeer de actuele code." }, 400);
    await env.DB.prepare("UPDATE owner_mfa SET mfa_enabled = 1, last_totp_counter = ?, enrolled_at = ? WHERE id = 1 AND mfa_enabled = 0").bind(counter, new Date().toISOString()).run();
    const recovery_codes = await createRecoveryCodes(env, 1, null);
    return json({ ok: true, recovery_codes });
  }
  if (request.method === "POST" && url.pathname === "/api/auth/password/forgot") {
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const identifier = String(body.identifier || "").trim().toLowerCase().slice(0, 254), now = Date.now();
    if (!identifier) return json({ error: "Vul je gebruikersnaam of e-mailadres in." }, 400);
    const [idAttempts, ipAttempts] = await Promise.all([
      recordCustomerAuthRequest(env, "staff-reset:" + await digest(identifier), now),
      recordCustomerAuthRequest(env, "staff-reset-ip:" + await digest(request.headers.get("CF-Connecting-IP") || "unknown"), now)
    ]);
    if (idAttempts > 3 || ipAttempts > 10) return json({ error: "Te veel verzoeken. Probeer het later opnieuw." }, 429);
    const owner = await env.DB.prepare("SELECT email FROM owner_mfa WHERE id = 1 AND (username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE)").bind(identifier, identifier).first();
    const staff = owner ? null : await env.DB.prepare("SELECT id, email FROM staff_access_tokens WHERE revoked_at IS NULL AND (username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE) LIMIT 1").bind(identifier, identifier).first();
    const email = String((owner || staff)?.email || "").trim().toLowerCase();
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      try { await sendStaffPasswordResetEmail(env, { staffId: staff ? staff.id : null, isOwner: !!owner, email, host: url.hostname.toLowerCase() }); }
      catch (error) { console.error("staff_password_reset_email_failed", String(error?.message || error).slice(0, 160)); }
    }
    return json({ message: "Als er een account bij hoort, ontvang je zo een e-mail met een link om een nieuw wachtwoord te kiezen." });
  }
  if (request.method === "POST" && url.pathname === "/api/auth/password/reset") {
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const rawToken = String(body.token || ""), newPassword = String(body.new_password || ""), confirmPassword = String(body.confirm_password || "");
    const invalid = () => json({ error: "Deze link is ongeldig of verlopen. Vraag een nieuwe link aan." }, 400);
    if (!/^[0-9a-f]{64}$/i.test(rawToken)) return invalid();
    const problem = staffPasswordProblem(newPassword);
    if (problem) return json({ error: problem }, 400);
    if (newPassword !== confirmPassword) return json({ error: "De wachtwoorden komen niet overeen." }, 400);
    const now = Date.now(), tokenHash = await digest(rawToken);
    const reset = await env.DB.prepare("SELECT r.staff_id, r.is_owner FROM staff_password_resets r LEFT JOIN staff_access_tokens st ON st.id = r.staff_id WHERE r.token_hash = ? AND r.consumed_at IS NULL AND r.expires_at > ? AND (r.is_owner = 1 OR st.revoked_at IS NULL)").bind(tokenHash, now).first();
    if (!reset) return invalid();
    const consumed = await env.DB.prepare("UPDATE staff_password_resets SET consumed_at = ? WHERE token_hash = ? AND consumed_at IS NULL").bind(now, tokenHash).run();
    if (consumed.meta?.changes !== 1) return invalid();
    const credentials = await hashPassword(newPassword), timestamp = new Date(now).toISOString();
    if (reset.is_owner) await env.DB.batch([
      env.DB.prepare("UPDATE owner_mfa SET password_salt = ?, password_hash = ? WHERE id = 1").bind(credentials.salt, credentials.hash),
      env.DB.prepare("UPDATE staff_sessions SET revoked_at = ? WHERE staff_id IS NULL AND revoked_at IS NULL").bind(timestamp),
      env.DB.prepare("DELETE FROM auth_login_attempts WHERE login_key = 'owner' OR login_key LIKE 'owner@%'")
    ]);
    else await env.DB.batch([
      env.DB.prepare("UPDATE staff_access_tokens SET password_salt = ?, password_hash = ?, must_change_password = 0, invitation_sent_at = NULL WHERE id = ? AND revoked_at IS NULL").bind(credentials.salt, credentials.hash, reset.staff_id),
      env.DB.prepare("UPDATE staff_sessions SET revoked_at = ? WHERE staff_id = ? AND revoked_at IS NULL").bind(timestamp, reset.staff_id),
      env.DB.prepare("DELETE FROM auth_login_attempts WHERE login_key = ? OR login_key LIKE ?").bind("staff:" + reset.staff_id, "staff:" + reset.staff_id + "@%")
    ]);
    return json({ ok: true });
  }
  if (request.method === "POST" && url.pathname === "/api/auth/owner/recover") {
    // Emergency route for the owner who lost both the authenticator and the recovery codes.
    // It needs the Worker secret ADMIN_TOKEN (only in Cloudflare) plus the owner's password, and only switches 2FA off so it can be set up again.
    const now = Date.now(), guard = await staffLoginGuard(env, request, "owner-recover", now);
    if (guard.locked) return json({ error: "Te veel mislukte pogingen. Probeer het over 15 minuten opnieuw." }, 429);
    let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
    const match = /^Bearer\s+(.+)$/i.exec(request.headers.get("Authorization") || "");
    const owner = await env.DB.prepare("SELECT username, password_salt, password_hash FROM owner_mfa WHERE id = 1").first();
    const username = String(body.username || "").trim().toLowerCase(), password = String(body.password || "");
    const keyOk = !!match && !!env.ADMIN_TOKEN && constantTimeEqual(match[1], env.ADMIN_TOKEN);
    const valid = keyOk && !!owner && String(owner.username || "").toLowerCase() === username && await passwordMatches(password, owner.password_salt, owner.password_hash);
    if (!valid) { await guard.fail(); return json({ error: "De Worker-sleutel, gebruikersnaam of het wachtwoord klopt niet." }, 401); }
    await env.DB.batch([
      env.DB.prepare("UPDATE owner_mfa SET mfa_enabled = 0, totp_secret_enc = '', last_totp_counter = -1 WHERE id = 1"),
      env.DB.prepare("DELETE FROM mfa_recovery_codes WHERE owner_id = 1"),
      env.DB.prepare("UPDATE staff_sessions SET revoked_at = ? WHERE staff_id IS NULL AND revoked_at IS NULL").bind(new Date(now).toISOString())
    ]);
    await guard.clear();
    return json({ ok: true });
  }
  if (request.method === "POST" && url.pathname === "/api/auth/logout") {
    const match = /^Bearer\s+(.+)$/i.exec(request.headers.get("Authorization") || "");
    if (match) await env.DB.prepare("UPDATE staff_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL").bind(new Date().toISOString(), await digest(match[1])).run();
    return json({ ok: true });
  }
  if (request.method === "POST" && url.pathname === "/api/validate") {
    let body;
    try { body = await readJson(request); } catch { return json({ valid: false, message: "Ongeldige aanvraag." }, 400); }
    const key = normalizedKey(body.license_key);
    if (!/^EH[0-9A-F]{32}$/.test(key)) return json({ valid: false, message: "Licentiesleutel ongeldig." }, 200);
    const keyHash = await digest(key);
    const row = await env.DB.prepare("SELECT l.id, l.valid_from, l.valid_until, l.revoked_at, l.license_type, l.activated_device_hash, l.activated_at, l.customer_id, l.product_id, l.entitlement_id, c.status AS customer_status, cp.enabled AS product_enabled, p.active AS product_active FROM licenses l LEFT JOIN customers c ON c.id = l.customer_id LEFT JOIN customer_products cp ON cp.customer_id = l.customer_id AND cp.product_id = l.product_id LEFT JOIN products p ON p.id = l.product_id WHERE l.key_hash = ? LIMIT 1").bind(keyHash).first();
    if (!row) return json({ valid: false, message: "Licentiesleutel niet herkend." });
    if (row.revoked_at) return json({ valid: false, message: "Deze licentie is ingetrokken." });
    const requestedProduct = String(body.product_id || "").trim().toLowerCase();
    if (requestedProduct && requestedProduct !== row.product_id) return json({ valid: false, message: "Deze licentiesleutel hoort bij een ander product." });
    let entitlement = null;
    if (row.entitlement_id) {
      if (row.customer_status !== "active") return json({ valid: false, message: "De toegang voor deze klant is gepauzeerd. Neem contact op met Cohentra." });
      entitlement = await loadEffectiveEntitlement(env, row.entitlement_id);
      if (!entitlement || !entitlement.use_allowed) return json({ valid: false, message: entitlementRefusal(entitlement), entitlement_status: entitlement?.status || "revoked" });
    } else if (row.customer_id && (row.customer_status !== "active" || row.product_enabled !== 1 || row.product_active !== 1)) return json({ valid: false, message: "De toegang voor deze klant of dit product is gepauzeerd. Neem contact op met Cohentra." });
    const today = new Date().toISOString().slice(0, 10);
    if (today < row.valid_from) return json({ valid: false, message: `Deze licentie is geldig vanaf ${row.valid_from}.`, valid_from: row.valid_from, valid_until: row.valid_until });
    if (today > row.valid_until) return json({ valid: false, message: `Deze licentie is verlopen op ${row.valid_until}.`, valid_until: row.valid_until });
    const deviceId = String(body.device_id || "").toLowerCase();
    if (!deviceId) {
      if (row.activated_device_hash) return json({ valid: false, message: "Deze licentie is aan een andere client gekoppeld. Werk EventHub bij naar 0.3.1." });
      const lastSeenAt = new Date().toISOString();
      await env.DB.prepare("UPDATE licenses SET last_seen_at = ? WHERE id = ?").bind(lastSeenAt, row.id).run();
      return json({ valid: true, message: "Licentie geldig.", server_time: lastSeenAt, license_type: row.license_type || (row.valid_until === UNLIMITED_UNTIL ? "Beheerder" : "Gesloten beta"), valid_from: row.valid_from, valid_until: row.valid_until === UNLIMITED_UNTIL ? null : row.valid_until, activation_bound: false, ...licenseRights(row, entitlement) });
    }
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(deviceId)) return json({ valid: false, message: "Client-ID ongeldig." });
    const deviceHash = await digest(deviceId);
    if (!row.activated_device_hash) await env.DB.prepare("UPDATE licenses SET activated_device_hash = ?, activated_at = ? WHERE id = ? AND activated_device_hash IS NULL").bind(deviceHash, new Date().toISOString(), row.id).run();
    const activation = await env.DB.prepare("SELECT activated_device_hash, activated_at FROM licenses WHERE id = ?").bind(row.id).first();
    if (!activation || activation.activated_device_hash !== deviceHash) return json({ valid: false, message: "Deze licentie is al aan een andere client gekoppeld. Neem contact op met de beheerder." });
    const lastSeenAt = new Date().toISOString();
    await env.DB.prepare("UPDATE licenses SET last_seen_at = ? WHERE id = ?").bind(lastSeenAt, row.id).run();
    return json({ valid: true, message: "Licentie geldig.", server_time: lastSeenAt, license_type: row.license_type || (row.valid_until === UNLIMITED_UNTIL ? "Beheerder" : "Gesloten beta"), valid_from: row.valid_from, valid_until: row.valid_until === UNLIMITED_UNTIL ? null : row.valid_until, activation_bound: true, ...licenseRights(row, entitlement) });
  }
  if (url.pathname.startsWith("/api/support/")) {
    const actor = await adminAuthorized(request, env);
    if (!actor) return json({ error: "Supporttoegang ongeldig of verlopen." }, 401);
    if (request.method === "POST" && url.pathname === "/api/support/inbox/sync") {
      if (!hasPermission(actor, "support.view")) return permissionDenied("support.view");
      try { return json(await syncSupportMailbox(env)); }
      catch (error) {
        console.error("support_mailbox_sync_failed", { message: String(error?.message || error).slice(0, 180) });
        return json({ error: "De STRATO-inbox kon niet worden opgehaald. Controleer de mailboxinstellingen of probeer het later opnieuw." }, 502);
      }
    }
    const mailIssueRoute = /^\/api\/support\/inbox\/issues\/([0-9a-f-]{36})\/resolve$/i.exec(url.pathname);
    if (request.method === "POST" && mailIssueRoute) {
      if (!hasPermission(actor, "support.reply")) return permissionDenied("support.reply");
      await env.DB.prepare("UPDATE support_mail_sync_issues SET resolved_at = ? WHERE id = ? AND resolved_at IS NULL").bind(new Date().toISOString(), mailIssueRoute[1]).run();
      return json({ ok: true });
    }
    if (request.method === "POST" && url.pathname === "/api/support/account/password") {
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const currentPassword = String(body.current_password || ""), newPassword = String(body.new_password || ""), confirmPassword = String(body.confirm_password || "");
      const passwordProblem = staffPasswordProblem(newPassword);
      if (passwordProblem) return json({ error: passwordProblem }, 400);
      if (newPassword !== confirmPassword) return json({ error: "De nieuwe wachtwoorden komen niet overeen." }, 400);
      const account = actor.role === "support"
        ? await env.DB.prepare("SELECT password_salt, password_hash FROM staff_access_tokens WHERE id = ? AND revoked_at IS NULL").bind(actor.id).first()
        : await env.DB.prepare("SELECT password_salt, password_hash FROM owner_mfa WHERE id = 1").first();
      if (!account || !await passwordMatches(currentPassword, account.password_salt, account.password_hash)) return json({ error: "Het huidige wachtwoord is onjuist." }, 401);
      const credentials = await hashPassword(newPassword), timestamp = new Date().toISOString();
      if (actor.role === "support") {
        await env.DB.batch([
          env.DB.prepare("UPDATE staff_access_tokens SET password_salt = ?, password_hash = ?, must_change_password = 0 WHERE id = ? AND revoked_at IS NULL").bind(credentials.salt, credentials.hash, actor.id),
          env.DB.prepare("UPDATE staff_sessions SET revoked_at = ? WHERE staff_id = ? AND id <> ? AND revoked_at IS NULL").bind(timestamp, actor.id, actor.session_id)
        ]);
      } else {
        await env.DB.batch([
          env.DB.prepare("UPDATE owner_mfa SET password_salt = ?, password_hash = ? WHERE id = 1").bind(credentials.salt, credentials.hash),
          env.DB.prepare("UPDATE staff_sessions SET revoked_at = ? WHERE staff_id IS NULL AND id <> ? AND revoked_at IS NULL").bind(timestamp, actor.session_id)
        ]);
      }
      return json({ ok: true });
    }
    if (request.method === "GET" && url.pathname === "/api/support/tickets") {
      if (!hasPermission(actor, "support.view")) return permissionDenied("support.view");
      const cursor = url.searchParams.get("cursor") || "";
      if (cursor && !/^[0-9a-f-]{36}$/i.test(cursor)) return json({ error: "Ongeldige ticketcursor." }, 400);
      const { results } = await env.DB.prepare("SELECT t.id, t.reference, t.category, t.subject, t.message, t.status, t.created_at, t.updated_at, t.assigned_to, t.source, t.organization, t.request_type, t.customer_id, t.created_by_staff_name, COALESCE(NULLIF(t.contact_name, ''), NULLIF(c.contact_name, ''), c.name) AS customer_name, COALESCE(NULLIF(t.contact_email, ''), c.contact_email) AS contact_email, c.name AS customer_org, st.name AS assigned_name, (SELECT CASE WHEN m.external_message_id IS NOT NULL THEN 1 ELSE 0 END FROM support_ticket_messages m WHERE m.ticket_id = t.id AND m.is_internal = 0 AND (m.external_message_id IS NOT NULL OR m.delivery_status = 'sent') ORDER BY m.created_at DESC LIMIT 1) AS customer_spoke_last FROM support_tickets t JOIN customers c ON c.id = t.customer_id LEFT JOIN staff_access_tokens st ON st.id = t.assigned_to WHERE t.id > ? ORDER BY t.id ASC LIMIT 501").bind(cursor).all();
      const tickets = results.slice(0, 500);
      return json({ tickets, next_cursor: results.length > 500 ? tickets.at(-1).id : null });
    }
    if (request.method === "POST" && url.pathname === "/api/support/tickets") {
      if (!hasPermission(actor, "support.reply")) return permissionDenied("support.reply");
      let body; try { body = await readJson(request, 16384); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const subject = String(body.subject || "").trim(), message = String(body.message || "").trim();
      if (!subject || subject.length > 120 || !message || message.length > 6000) return json({ error: "Vul een onderwerp (maximaal 120 tekens) en een omschrijving in." }, 400);
      const customer = await env.DB.prepare("SELECT id, contact_name, contact_email FROM customers WHERE id = ? AND id <> ?").bind(String(body.customer_id || ""), WEBSITE_CONTACT_CUSTOMER_ID).first();
      if (!customer) return json({ error: "Klant niet gevonden." }, 404);
      const id = crypto.randomUUID(), now = new Date().toISOString(), reference = `CH-${new Date(now).getUTCFullYear()}-${randomHex(5).toUpperCase()}`;
      await env.DB.prepare("INSERT INTO support_tickets (id, reference, customer_id, category, subject, message, status, assigned_to, created_at, updated_at, contact_name, contact_email, created_by_staff_name) VALUES (?, ?, ?, 'other', ?, ?, 'in_progress', ?, ?, ?, ?, ?, ?)").bind(id, reference, customer.id, subject, message, actor.id || null, now, now, customer.contact_name || "", customer.contact_email || "", actor.name).run();
      return json({ ok: true, id, reference }, 201);
    }
    const ticketRoute = /^\/api\/support\/tickets\/([0-9a-f-]{36})(?:\/(replies))?$/i.exec(url.pathname);
    if (ticketRoute && !ticketRoute[2] && request.method === "GET") {
      if (!hasPermission(actor, "support.view")) return permissionDenied("support.view");
      const ticket = await env.DB.prepare("SELECT t.id, t.reference, t.category, t.subject, t.message, t.status, t.created_at, t.updated_at, t.assigned_to, t.source, t.organization, t.request_type, t.customer_id, t.created_by_staff_name, COALESCE(NULLIF(t.contact_name, ''), NULLIF(c.contact_name, ''), c.name) AS customer_name, COALESCE(NULLIF(t.contact_email, ''), c.contact_email) AS contact_email, c.name AS customer_org, st.name AS assigned_name, (SELECT COUNT(*) FROM licenses l WHERE l.customer_id = t.customer_id AND l.revoked_at IS NULL AND l.valid_until >= ?) AS active_licenses FROM support_tickets t JOIN customers c ON c.id = t.customer_id LEFT JOIN staff_access_tokens st ON st.id = t.assigned_to WHERE t.id = ?").bind(new Date().toISOString().slice(0, 10), ticketRoute[1]).first();
      if (!ticket) return json({ error: "Ticket niet gevonden." }, 404);
      const { results: replies } = await env.DB.prepare("SELECT id, author_name, author_email, author_staff_id, message, CASE WHEN external_message_id IS NOT NULL THEN 'received' ELSE delivery_status END AS delivery_status, is_internal, created_at, sent_at FROM support_ticket_messages WHERE ticket_id = ? ORDER BY created_at ASC").bind(ticketRoute[1]).all();
      return json({ ticket, replies });
    }
    if (ticketRoute && ticketRoute[2] === "replies" && request.method === "POST") {
      if (!hasPermission(actor, "support.reply")) return permissionDenied("support.reply");
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const message = String(body.message || "").trim();
      if (!message || message.length > 6000) return json({ error: "Vul een antwoord in van maximaal 6.000 tekens." }, 400);
      const nextStatus = body.status === undefined || body.status === null || body.status === "" ? null : String(body.status);
      if (nextStatus && !["new", "in_progress", "waiting_customer", "closed"].includes(nextStatus)) return json({ error: "Kies een geldige ticketstatus." }, 400);
      if (nextStatus && !hasPermission(actor, "support.status")) return permissionDenied("support.status");
      if (body.internal === true) {
        const exists = await env.DB.prepare("SELECT id FROM support_tickets WHERE id = ?").bind(ticketRoute[1]).first();
        if (!exists) return json({ error: "Ticket niet gevonden." }, 404);
        const id = crypto.randomUUID(), createdAt = new Date().toISOString();
        await env.DB.batch([
          env.DB.prepare("INSERT INTO support_ticket_messages (id, ticket_id, author_name, author_email, author_staff_id, message, delivery_status, created_at, is_internal) VALUES (?, ?, ?, '', ?, ?, 'sent', ?, 1)").bind(id, exists.id, actor.name, actor.id || "owner", message, createdAt),
          env.DB.prepare("UPDATE support_tickets SET updated_at = ? WHERE id = ?").bind(createdAt, exists.id)
        ]);
        return json({ ok: true, reply: { id, message, delivery_status: "sent", is_internal: 1, created_at: createdAt } }, 201);
      }
      const ticket = await env.DB.prepare("SELECT t.id, t.reference, t.subject, t.status, t.created_at, COALESCE(NULLIF(t.contact_name, ''), NULLIF(c.contact_name, ''), c.name) AS customer_name, COALESCE(NULLIF(t.contact_email, ''), c.contact_email) AS contact_email FROM support_tickets t JOIN customers c ON c.id = t.customer_id WHERE t.id = ?").bind(ticketRoute[1]).first();
      if (!ticket) return json({ error: "Ticket niet gevonden." }, 404);
      if (!/^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(String(ticket.contact_email || ""))) return json({ error: "Dit ticket heeft geen geldig klant e-mailadres." }, 400);
      const id = crypto.randomUUID(), createdAt = new Date().toISOString();
      await env.DB.prepare("INSERT INTO support_ticket_messages (id, ticket_id, author_name, author_email, author_staff_id, message, delivery_status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)").bind(id, ticket.id, actor.name, "support@cohentra.digital", actor.id || "owner", message, createdAt).run();
      const supportSmtpUser = String(env.STRATO_SUPPORT_SMTP_USER || "").trim().toLowerCase();
      const supportSmtpConfigured = supportSmtpUser === "support@cohentra.digital" && Boolean(env.STRATO_SUPPORT_SMTP_PASSWORD);
      const delivery = supportSmtpConfigured ? await sendSupportTicketEmail(env, ticket, { message, staffName: actor.name, staffFirstName: actor.first_name }) : false;
      const sent = delivery === true;
      const deliveryStatus = sent ? "sent" : "failed", sentAt = sent ? new Date().toISOString() : null;
      await env.DB.batch([
        env.DB.prepare("UPDATE support_ticket_messages SET delivery_status = ?, sent_at = ? WHERE id = ?").bind(deliveryStatus, sentAt, id),
        env.DB.prepare("UPDATE support_tickets SET updated_at = ?, status = CASE WHEN ? IS NOT NULL AND ? = 1 THEN ? ELSE status END, assigned_to = CASE WHEN ? = 'owner' THEN assigned_to ELSE ? END WHERE id = ?").bind(sentAt || createdAt, nextStatus, sent ? 1 : 0, nextStatus, actor.role, actor.id, ticket.id)
      ]);
      if (!sent) {
        const smtpReason = delivery && typeof delivery === "object" ? ` STRATO-fase: ${delivery.reason}` : "";
        const error = supportSmtpConfigured ? `E-mail niet bevestigd door STRATO.${smtpReason} Er is niets als verzonden gemarkeerd.` : "De aparte STRATO-inlog voor support ontbreekt. Voeg in Cloudflare Worker Secrets STRATO_SUPPORT_SMTP_USER (support@cohentra.digital) en STRATO_SUPPORT_SMTP_PASSWORD toe.";
        return json({ error, reply: { id, message, delivery_status: deliveryStatus, created_at: createdAt } }, 502);
      }
      return json({ ok: true, status: nextStatus || ticket.status, reply: { id, message, delivery_status: deliveryStatus, created_at: createdAt, sent_at: sentAt } }, 201);
    }
    if (ticketRoute && !ticketRoute[2] && request.method === "PATCH") {
      if (!hasPermission(actor, "support.status")) return permissionDenied("support.status");
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const statuses = ["new", "in_progress", "waiting_customer", "closed"];
      if (!statuses.includes(body.status)) return json({ error: "Kies een geldige ticketstatus." }, 400);
      const ticket = await env.DB.prepare("SELECT t.id, t.reference, t.status, COALESCE(NULLIF(t.contact_name, ''), NULLIF(c.contact_name, ''), c.name) AS customer_name, COALESCE(NULLIF(t.contact_email, ''), c.contact_email) AS contact_email FROM support_tickets t JOIN customers c ON c.id = t.customer_id WHERE t.id = ?").bind(ticketRoute[1]).first();
      if (!ticket) return json({ error: "Ticket niet gevonden." }, 404);
      const statusChanged = ticket.status !== body.status;
      const updatedAt = new Date().toISOString();
      await env.DB.prepare("UPDATE support_tickets SET status = ?, assigned_to = CASE WHEN ? = 'owner' THEN assigned_to ELSE ? END, updated_at = ? WHERE id = ?").bind(body.status, actor.role, actor.id, updatedAt, ticketRoute[1]).run();
      let statusNotice = null;
      if (statusChanged && body.status === "in_progress") {
        const id = crypto.randomUUID();
         await env.DB.prepare("INSERT INTO support_ticket_messages (id, ticket_id, author_name, author_email, author_staff_id, message, delivery_status, created_at) VALUES (?, ?, 'Cohentra Support', 'support@cohentra.digital', ?, ?, 'pending', ?)").bind(id, ticket.id, actor.id || "owner", `We hebben je supportaanvraag ${ticket.reference} in behandeling genomen.`, updatedAt).run();
        const supportSmtpUser = String(env.STRATO_SUPPORT_SMTP_USER || "").trim().toLowerCase();
        const supportSmtpConfigured = supportSmtpUser === "support@cohentra.digital" && Boolean(env.STRATO_SUPPORT_SMTP_PASSWORD);
        const delivery = supportSmtpConfigured ? await sendSupportTicketEmail(env, ticket, { kind: "status", staffFirstName: actor.first_name }) : false;
        const sent = delivery === true, sentAt = sent ? new Date().toISOString() : null;
        await env.DB.prepare("UPDATE support_ticket_messages SET delivery_status = ?, sent_at = ? WHERE id = ?").bind(sent ? "sent" : "failed", sentAt, id).run();
        statusNotice = sent ? "sent" : "failed";
      }
      return json({ ok: true, status: body.status, status_notice: statusNotice });
    }
    return json({ error: "Niet gevonden." }, 404);
  }
  if (url.pathname.startsWith("/api/admin/")) {
    const actor = await adminAuthorized(request, env);
    if (!actor) return json({ error: "Toegangscode ongeldig of ingetrokken." }, 401);
    const ownerOnly = () => actor.role === "owner";
    if (SHOP_ADMIN_ROUTES.some((pattern) => pattern.test(url.pathname))) {
      if (!env.SHOP) return json({ error: "De shop-worker is nog niet gekoppeld (service binding SHOP)." }, 503);
      return await env.SHOP.admin(request, { id: actor.id, name: actor.name, role: actor.role, permissions: actor.permissions });
    }
    const customerTypeRoute = /^\/api\/admin\/customers\/([0-9a-f-]{36})\/type$/i.exec(url.pathname);
    if (customerTypeRoute && request.method === "PUT") {
      if (!hasPermission(actor, "customers.manage")) return permissionDenied("customers.manage");
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const type = body.customer_type === "individual" ? "individual" : body.customer_type === "business" ? "business" : "";
      if (!type) return json({ error: "Kies een klanttype." }, 400);
      const before = await env.DB.prepare("SELECT customer_type FROM customers WHERE id = ? AND id <> ?").bind(customerTypeRoute[1], WEBSITE_CONTACT_CUSTOMER_ID).first();
      if (!before) return json({ error: "Klant niet gevonden." }, 404);
      await env.DB.prepare("UPDATE customers SET customer_type = ?, updated_at = ? WHERE id = ?").bind(type, new Date().toISOString(), customerTypeRoute[1]).run();
      await audit(env, { customer_id: customerTypeRoute[1], entity_type: "customer", entity_id: customerTypeRoute[1], action: "customer.type_changed", actor_type: "staff", actor_name: actor.name, details: { from: before.customer_type, to: type } });
      return json({ ok: true });
    }
    const portalRoleRoute = /^\/api\/admin\/portal-users\/([0-9a-f-]{36})\/role$/i.exec(url.pathname);
    if (portalRoleRoute && request.method === "PUT") {
      if (!hasPermission(actor, "customers.manage")) return permissionDenied("customers.manage");
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const role = body.role === "member" ? "member" : body.role === "admin" ? "admin" : "";
      const account = await env.DB.prepare("SELECT id, customer_id, role FROM customer_portal_accounts WHERE id = ?").bind(portalRoleRoute[1]).first();
      if (!account || !role) return json({ error: "Portaalgebruiker of rol ongeldig." }, 404);
      if (role === "member") {
        const admins = await env.DB.prepare("SELECT COUNT(*) AS n FROM customer_portal_accounts WHERE customer_id = ? AND role = 'admin' AND disabled_at IS NULL AND id <> ?").bind(account.customer_id, account.id).first();
        if (!Number(admins.n)) return json({ error: "Een klant houdt minimaal één beheerder." }, 409);
      }
      await env.DB.prepare("UPDATE customer_portal_accounts SET role = ?, updated_at = ? WHERE id = ?").bind(role, new Date().toISOString(), account.id).run();
      await audit(env, { customer_id: account.customer_id, entity_type: "account", entity_id: account.id, action: "account.role_changed", actor_type: "staff", actor_name: actor.name, details: { from: account.role, to: role } });
      return json({ ok: true });
    }
    const avatarRoute = /^\/api\/admin\/avatar\/(owner|[0-9a-f-]{36})$/i.exec(url.pathname);
    if (avatarRoute && request.method === "GET") {
      const avatarId = avatarRoute[1].toLowerCase(), ownId = actor.id || "owner";
      if (avatarId !== ownId && !hasPermission(actor, "support.view")) return permissionDenied("support.view");
      if (!env.STAFF_AVATARS) return json({ error: "Profielfoto-opslag is nog niet geconfigureerd." }, 503);
      const account = avatarId === "owner"
        ? await env.DB.prepare("SELECT avatar_key FROM owner_mfa WHERE id = 1").first()
        : await env.DB.prepare("SELECT avatar_key FROM staff_access_tokens WHERE id = ?").bind(avatarId).first();
      if (!account?.avatar_key) return json({ error: "Geen profielfoto gevonden." }, 404);
      const object = await env.STAFF_AVATARS.get(account.avatar_key);
      if (!object) return json({ error: "Geen profielfoto gevonden." }, 404);
      return new Response(object.body, { headers: { "Content-Type": "image/jpeg", "Content-Length": String(object.size), "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Cross-Origin-Resource-Policy": "same-origin", "Vary": "Authorization" } });
    }
    if (url.pathname === "/api/admin/me/avatar" && (request.method === "PUT" || request.method === "DELETE")) {
      if (!env.STAFF_AVATARS) return json({ error: "Profielfoto-opslag is nog niet geconfigureerd." }, 503);
      const table = actor.id ? "staff_access_tokens" : "owner_mfa", accountId = actor.id || 1;
      const current = actor.id
        ? await env.DB.prepare("SELECT avatar_key FROM staff_access_tokens WHERE id = ? AND revoked_at IS NULL").bind(accountId).first()
        : await env.DB.prepare("SELECT avatar_key FROM owner_mfa WHERE id = 1").first();
      if (!current) return json({ error: "Account niet gevonden." }, 404);
      const avatarKey = `staff/${actor.id || "owner"}.jpg`;
      if (request.method === "DELETE") {
        if (current.avatar_key) await env.STAFF_AVATARS.delete(current.avatar_key);
        if (actor.id) await env.DB.prepare("UPDATE staff_access_tokens SET avatar_key = NULL WHERE id = ?").bind(accountId).run();
        else await env.DB.prepare("UPDATE owner_mfa SET avatar_key = NULL WHERE id = 1").run();
        return json({ ok: true, has_avatar: false });
      }
      const contentType = String(request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
      if (contentType !== "image/jpeg") return json({ error: "De foto moet als JPEG-afbeelding worden aangeleverd." }, 415);
      const announcedLength = Number(request.headers.get("Content-Length") || 0);
      if (announcedLength > 262144) return json({ error: "De bewerkte foto is te groot; kies een kleinere afbeelding." }, 413);
      const bytes = await readBoundedRequestBytes(request, 262144);
      if (!bytes?.length) return json({ error: "De foto is leeg of te groot." }, 413);
      const dimensions = jpegDimensions(bytes);
      if (!dimensions || dimensions.width < 32 || dimensions.height < 32 || dimensions.width > 1024 || dimensions.height > 1024) return json({ error: "Deze JPEG-foto is ongeldig of heeft ongeschikte afmetingen." }, 400);
      await env.STAFF_AVATARS.put(avatarKey, bytes, { httpMetadata: { contentType: "image/jpeg", cacheControl: "private, no-store" } });
      if (actor.id) await env.DB.prepare("UPDATE staff_access_tokens SET avatar_key = ? WHERE id = ? AND revoked_at IS NULL").bind(avatarKey, accountId).run();
      else await env.DB.prepare("UPDATE owner_mfa SET avatar_key = ? WHERE id = 1").bind(avatarKey).run();
      return json({ ok: true, has_avatar: true });
    }
    if (request.method === "GET" && url.pathname === "/api/admin/me") {
      const account = actor.id ? await env.DB.prepare("SELECT username, email, avatar_key FROM staff_access_tokens WHERE id = ?").bind(actor.id).first() : await env.DB.prepare("SELECT username, email, avatar_key FROM owner_mfa WHERE id = 1").first();
      return json({ id: actor.id || null, role: actor.role, name: actor.name, first_name: actor.first_name, username: account?.username || "", email: account?.email || "", has_avatar: Boolean(account?.avatar_key), recovery_codes_left: await recoveryCodesLeft(env, actor.id ? null : 1, actor.id || null), permissions: actor.permissions, functions: actor.functions });
    }
    if (request.method === "POST" && url.pathname === "/api/admin/me/recovery-codes") {
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const row = actor.id ? await env.DB.prepare("SELECT totp_secret_enc AS secret, last_totp_counter AS counter FROM staff_access_tokens WHERE id = ?").bind(actor.id).first() : await env.DB.prepare("SELECT totp_secret_enc AS secret, last_totp_counter AS counter FROM owner_mfa WHERE id = 1").first();
      if (!row?.secret) return json({ error: "Voor dit account is geen authenticator gekoppeld." }, 400);
      const now = Date.now(), guard = await staffLoginGuard(env, request, actor.id ? `staff:${actor.id}` : "owner", now);
      if (guard.locked) return json({ error: "Te veel mislukte pogingen. Probeer het over 15 minuten opnieuw." }, 429);
      const counter = await totpCounter(await decryptMfaSecret(row.secret, env), String(body.code || "").replace(/[\s-]/g, ""), now, row.counter);
      if (counter === null) { await guard.fail(); return json({ error: "Die code klopt niet. Probeer de nieuwste code uit je authenticator-app." }, 400); }
      if (actor.id) await env.DB.prepare("UPDATE staff_access_tokens SET last_totp_counter = ? WHERE id = ? AND last_totp_counter < ?").bind(counter, actor.id, counter).run();
      else await env.DB.prepare("UPDATE owner_mfa SET last_totp_counter = ? WHERE id = 1 AND last_totp_counter < ?").bind(counter, counter).run();
      const recovery_codes = await createRecoveryCodes(env, actor.id ? null : 1, actor.id || null);
      return json({ recovery_codes });
    }
    if (request.method === "PATCH" && url.pathname === "/api/admin/me") {
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const firstName = String(body.first_name || "").trim().replace(/\s+/g, " ").slice(0, 40);
      const displayName = String(body.name || "").trim().replace(/\s+/g, " ").slice(0, 80);
      if (!firstName || !displayName) return json({ error: "Vul zowel je volledige naam als je voornaam in." }, 400);
      const email = body.email === undefined ? null : String(body.email || "").trim().toLowerCase().slice(0, 254);
      if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json({ error: "Vul een geldig e-mailadres in." }, 400);
      if (actor.id) await env.DB.prepare("UPDATE staff_access_tokens SET name = ?, first_name = ?, email = CASE WHEN ? IS NULL THEN email ELSE NULLIF(?, '') END WHERE id = ? AND revoked_at IS NULL").bind(displayName, firstName, email, email, actor.id).run();
      else await env.DB.prepare("UPDATE owner_mfa SET name = ?, first_name = ?, email = CASE WHEN ? IS NULL THEN email ELSE NULLIF(?, '') END WHERE id = 1").bind(displayName, firstName, email, email).run();
      return json({ name: displayName, first_name: firstName, email: email ?? undefined });
    }
    if (url.pathname.startsWith("/api/admin/email-templates")) {
      if (!hasPermission(actor, "email.templates.manage")) return permissionDenied("email.templates.manage");
      if (request.method === "GET" && url.pathname === "/api/admin/email-templates") {
        const { results } = await env.DB.prepare("SELECT template_key, settings_json, updated_at, updated_by FROM email_template_settings").all();
        const templates = Object.fromEntries(Object.keys(EMAIL_TEMPLATE_DEFAULTS).map((key) => [key, { ...EMAIL_TEMPLATE_DEFAULTS[key] }]));
        const metadata = {};
        for (const row of results) {
          try { templates[row.template_key] = normalizeEmailTemplateSettings(row.template_key, { ...templates[row.template_key], ...JSON.parse(row.settings_json) }); metadata[row.template_key] = { updated_at: row.updated_at, updated_by: row.updated_by }; }
          catch (error) { console.error("email_template_settings_invalid", { key: row.template_key, message: String(error?.message || error).slice(0, 120) }); }
        }
        return json({ templates, metadata });
      }
      const saveRoute = /^\/api\/admin\/email-templates\/(support|auth|branding)$/.exec(url.pathname);
      if (saveRoute && request.method === "PUT") {
        let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
        let settings; try { settings = normalizeEmailTemplateSettings(saveRoute[1], body.settings); } catch (error) { return json({ error: String(error?.message || "Controleer de ingevulde waarden.") }, 400); }
        const updatedAt = new Date().toISOString();
        await env.DB.prepare("INSERT INTO email_template_settings (template_key, settings_json, updated_at, updated_by) VALUES (?, ?, ?, ?) ON CONFLICT(template_key) DO UPDATE SET settings_json = excluded.settings_json, updated_at = excluded.updated_at, updated_by = excluded.updated_by").bind(saveRoute[1], JSON.stringify(settings), updatedAt, actor.name || "Cohentra beheerder").run();
        return json({ ok: true, key: saveRoute[1], settings, updated_at: updatedAt, updated_by: actor.name || "Cohentra beheerder" });
      }
      if (request.method === "POST" && url.pathname === "/api/admin/email-templates/preview") {
        let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
        if (!["support", "auth", "branding"].includes(body.key)) return json({ error: "Onbekend e-mailsjabloon." }, 400);
        const key = body.key;
        let settings, brand;
        try {
          if (key === "branding") { brand = normalizeEmailTemplateSettings("branding", body.settings); settings = await loadEmailTemplateSettings(env, "auth"); }
          else { settings = normalizeEmailTemplateSettings(key, body.settings); brand = normalizeEmailTemplateSettings("branding", body.brand || await loadEmailTemplateSettings(env, "branding")); }
        } catch (error) { return json({ error: String(error?.message || "Controleer de ingevulde waarden.") }, 400); }
        let html;
        if (key === "support") {
          const ticket = { reference: "CH-2026-VOORBEELD", subject: "Voorbeeldonderwerp", customerName: "Noor Bakker", contactEmail: "noor@example.com", category: "Account / toegang", message: "Dit is een fictief voorbeeld van een klantbericht." };
          if (body.variant === "new") html = renderSupportEmailHtml({ ticket, agentReply: null, bodyText: "", firstName: "Jamie", settings, brand });
          else if (body.variant === "status") html = renderSupportEmailHtml({ ticket, agentReply: { kind: "status" }, bodyText: templateText(settings.status_body, { reference: ticket.reference }), firstName: "Jamie", settings, brand });
          else html = renderSupportEmailHtml({ ticket, agentReply: { message: "Bedankt voor je bericht. Ik kijk dit graag voor je na." }, bodyText: "Bedankt voor je bericht. Ik kijk dit graag voor je na.", firstName: "Jamie", settings, brand });
        } else {
          const invite = key === "branding" || body.variant !== "reset";
          html = renderAuthEmailHtml({ subject: invite ? settings.invite_subject : settings.reset_subject, intro: invite ? settings.invite_intro : settings.reset_intro, link: "https://portal.cohentra.digital/voorbeeldlink", button: invite ? settings.invite_button : settings.reset_button, expiryNote: settings.expiry_note, brand });
        }
        return json({ html });
      }
      return json({ error: "Niet gevonden." }, 404);
    }
    if (request.method === "GET" && url.pathname === "/api/admin/staff") {
      if (!ownerOnly()) return json({ error: "Alleen de Cohentra-eigenaar kan medewerkers en functies beheren." }, 403);
      const { results } = await env.DB.prepare("SELECT s.id, s.name, s.first_name, s.username, s.email, s.role, s.created_at, s.revoked_at, s.last_seen_at, s.invitation_sent_at, s.must_change_password, s.mfa_enabled, (SELECT COUNT(*) FROM mfa_recovery_codes r WHERE r.staff_id = s.id AND r.used_at IS NULL) AS recovery_codes_left, COALESCE(group_concat(a.function_key), '') AS function_keys FROM staff_access_tokens s LEFT JOIN staff_function_assignments a ON a.staff_id = s.id GROUP BY s.id ORDER BY s.revoked_at IS NOT NULL, s.name COLLATE NOCASE").all();
      return json({ staff: results.map((row) => ({ ...row, function_keys: row.function_keys ? row.function_keys.split(",") : [] })) });
    }
    if (request.method === "GET" && url.pathname === "/api/admin/functions") {
      if (!ownerOnly()) return json({ error: "Alleen de Cohentra-eigenaar kan functies en rechten beheren." }, 403);
      const { results } = await env.DB.prepare("SELECT function_key, name, permissions_json FROM staff_functions ORDER BY name COLLATE NOCASE").all();
      return json({ functions: results.map((row) => ({ function_key: row.function_key, name: row.name, permissions: JSON.parse(row.permissions_json) })) });
    }
    const functionRoute = /^\/api\/admin\/functions\/([a-z0-9_-]{2,40})$/i.exec(url.pathname);
    if (functionRoute && request.method === "PATCH") {
      if (!ownerOnly()) return json({ error: "Alleen de Cohentra-eigenaar kan functies en rechten beheren." }, 403);
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const known = new Set(["support.view", "support.reply", "support.status", "customers.view", "customers.manage", "licenses.view", "licenses.issue", "licenses.manage", "sales.view", "sales.manage", "email.templates.manage", "shop.view", "shop.manage", "billing.view", "billing.manage"]);
      const permissions = Array.isArray(body.permissions) ? [...new Set(body.permissions.filter((item) => known.has(item)))] : null;
      const name = String(body.name || "").trim().replace(/\s+/g, " ").slice(0, 60);
      if (!permissions || !name) return json({ error: "Vul een functienaam in en kies geldige rechten." }, 400);
      const result = await env.DB.prepare("UPDATE staff_functions SET name = ?, permissions_json = ?, updated_at = ? WHERE function_key = ?").bind(name, JSON.stringify(permissions), new Date().toISOString(), functionRoute[1]).run();
      if (!result.meta?.changes) return json({ error: "Functie niet gevonden." }, 404);
      return json({ ok: true, function_key: functionRoute[1], name, permissions });
    }
    const staffFunctionsRoute = /^\/api\/admin\/staff\/([0-9a-f-]{36})\/functions$/i.exec(url.pathname);
    if (staffFunctionsRoute && request.method === "PATCH") {
      if (!ownerOnly()) return json({ error: "Alleen de Cohentra-eigenaar kan medewerkers en functies beheren." }, 403);
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const keys = Array.isArray(body.function_keys) ? [...new Set(body.function_keys.map(String))] : null;
      if (!keys || keys.length > 12 || keys.some((key) => !/^[a-z0-9_-]{2,40}$/i.test(key))) return json({ error: "Kies één of meer geldige functies." }, 400);
      const staff = await env.DB.prepare("SELECT id FROM staff_access_tokens WHERE id = ? AND revoked_at IS NULL").bind(staffFunctionsRoute[1]).first();
      if (!staff) return json({ error: "Actieve medewerker niet gevonden." }, 404);
      if (keys.length) {
        const marks = keys.map(() => "?").join(",");
        const { results } = await env.DB.prepare(`SELECT function_key FROM staff_functions WHERE function_key IN (${marks})`).bind(...keys).all();
        if (results.length !== keys.length) return json({ error: "Een gekozen functie bestaat niet." }, 400);
      }
      const now = new Date().toISOString();
      await env.DB.batch([env.DB.prepare("DELETE FROM staff_function_assignments WHERE staff_id = ?").bind(staff.id), ...keys.map((key) => env.DB.prepare("INSERT INTO staff_function_assignments (staff_id, function_key, assigned_at) VALUES (?, ?, ?)").bind(staff.id, key, now))]);
      return json({ ok: true, function_keys: keys });
    }
    if (request.method === "POST" && url.pathname === "/api/admin/staff") {
      if (!ownerOnly()) return json({ error: "Alleen de Cohentra-beheerder kan supporttoegang beheren." }, 403);
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const name = String(body.name || "").trim().slice(0, 80);
      const firstName = String(body.first_name || "").trim().replace(/\s+/g, " ").slice(0, 40);
      const username = String(body.username || "").trim();
      if (!name || !firstName || !username || username.length > 254) return json({ error: "Vul een naam, voornaam en gebruikersnaam in." }, 400);
      const duplicate = await env.DB.prepare("SELECT 1 AS found FROM staff_access_tokens WHERE username = ? COLLATE NOCASE UNION ALL SELECT 1 AS found FROM owner_mfa WHERE username = ? COLLATE NOCASE LIMIT 1").bind(username, username).first();
      if (duplicate) return json({ error: "Deze gebruikersnaam is al in gebruik." }, 409);
      const email = String(body.email || "").trim().toLowerCase().slice(0, 254);
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json({ error: "Vul een geldig e-mailadres in; daar sturen we de instellink naartoe." }, 400);
      if (!env.EMAIL) return json({ error: "De e-mailservice is niet beschikbaar. Het account is niet aangemaakt." }, 503);
      const functionKeys = Array.isArray(body.function_keys) ? [...new Set(body.function_keys.map(String))] : ["support"];
      const { results: knownFunctions } = await env.DB.prepare("SELECT function_key FROM staff_functions").all();
      const validKeys = functionKeys.filter((key) => knownFunctions.some((row) => row.function_key === key));
      if (!validKeys.length) return json({ error: "Kies minimaal één geldige functie." }, 400);
      const id = crypto.randomUUID();
      const credentials = await hashPassword(randomHex(32));
      const createdAt = new Date().toISOString();
      // The invited employee sets a personal password via a one-time link, then enrolls MFA on first sign-in.
      await env.DB.batch([
        env.DB.prepare("INSERT INTO staff_access_tokens (id, name, first_name, username, email, password_salt, password_hash, token_hash, role, created_at, totp_secret_enc, mfa_enabled, must_change_password, invitation_sent_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'support', ?, NULL, 0, 0, NULL)").bind(id, name, firstName, username, email, credentials.salt, credentials.hash, await digest(randomHex(32)), createdAt),
        ...validKeys.map((key) => env.DB.prepare("INSERT INTO staff_function_assignments (staff_id, function_key, assigned_at) VALUES (?, ?, ?)").bind(id, key, createdAt))
      ]);
      try { await sendStaffInviteEmail(env, { staffId: id, email }); }
      catch (error) {
        console.error("staff_invitation_email_failed", { staff_id: id, message: String(error?.message || error).slice(0, 160) });
        await env.DB.prepare("DELETE FROM staff_access_tokens WHERE id = ?").bind(id).run();
        return json({ error: "De uitnodigingsmail kon niet worden verstuurd. Het account is niet aangemaakt; controleer de e-mailservice en probeer opnieuw." }, 502);
      }
      return json({ id, name, first_name: firstName, username, email, invitation_sent: true, role: "support" }, 201);
    }
    const staffInviteRoute = /^\/api\/admin\/staff\/([0-9a-f-]{36})\/invite$/i.exec(url.pathname);
    if (staffInviteRoute && request.method === "POST") {
      if (!ownerOnly()) return json({ error: "Alleen de Cohentra-eigenaar kan medewerkers uitnodigen." }, 403);
      const staff = await env.DB.prepare("SELECT id, email, invitation_sent_at, mfa_enabled, revoked_at FROM staff_access_tokens WHERE id = ?").bind(staffInviteRoute[1]).first();
      if (!staff || staff.revoked_at) return json({ error: "Actieve medewerker niet gevonden." }, 404);
      if (!staff.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(staff.email)) return json({ error: "Stel eerst een geldig e-mailadres in bij dit account." }, 400);
      if (!staff.invitation_sent_at || Number(staff.mfa_enabled)) return json({ error: "Dit account wacht niet meer op de eerste instellink." }, 409);
      try { await sendStaffInviteEmail(env, { staffId: staff.id, email: staff.email }); }
      catch (error) { console.error("staff_invitation_resend_failed", { staff_id: staff.id, message: String(error?.message || error).slice(0, 160) }); return json({ error: "De uitnodiging kon niet worden verstuurd. Controleer de e-mailservice." }, 502); }
      return json({ ok: true, invitation_sent: true });
    }
    const staffDetailRoute = /^\/api\/admin\/staff\/([0-9a-f-]{36})$/i.exec(url.pathname);
    if (staffDetailRoute && request.method === "PATCH") {
      if (!ownerOnly()) return json({ error: "Alleen de Cohentra-eigenaar kan medewerkers beheren." }, 403);
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const name = String(body.name || "").trim().slice(0, 80), firstName = String(body.first_name || "").trim().replace(/\s+/g, " ").slice(0, 40), email = String(body.email || "").trim().toLowerCase().slice(0, 254);
      if (!name || !firstName) return json({ error: "Vul een naam en voornaam in." }, 400);
      if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json({ error: "Vul een geldig e-mailadres in." }, 400);
      const result = await env.DB.prepare("UPDATE staff_access_tokens SET name = ?, first_name = ?, email = ? WHERE id = ?").bind(name, firstName, email || null, staffDetailRoute[1]).run();
      if (!result.meta?.changes) return json({ error: "Medewerker niet gevonden." }, 404);
      return json({ ok: true });
    }
    if (staffDetailRoute && request.method === "DELETE") {
      if (!ownerOnly()) return json({ error: "Alleen de Cohentra-eigenaar kan medewerkers verwijderen." }, 403);
      let body; try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const staff = await env.DB.prepare("SELECT id, username FROM staff_access_tokens WHERE id = ?").bind(staffDetailRoute[1]).first();
      if (!staff) return json({ error: "Medewerker niet gevonden." }, 404);
      if (String(body.confirm_username || "").trim() !== staff.username) return json({ error: "Typ de gebruikersnaam precies over om te bevestigen." }, 400);
      // Sessions, recovery codes, function assignments and reset links cascade; assigned tickets become unassigned.
      await env.DB.prepare("DELETE FROM staff_access_tokens WHERE id = ?").bind(staff.id).run();
      return json({ ok: true });
    }
    const staffActionRoute = /^\/api\/admin\/staff\/([0-9a-f-]{36})\/(reset-mfa|reset-password|restore)$/i.exec(url.pathname);
    if (staffActionRoute && request.method === "POST") {
      if (!ownerOnly()) return json({ error: "Alleen de Cohentra-eigenaar kan medewerkers beheren." }, 403);
      const staffId = staffActionRoute[1], action = staffActionRoute[2].toLowerCase(), timestamp = new Date().toISOString();
      const staff = await env.DB.prepare("SELECT id, revoked_at FROM staff_access_tokens WHERE id = ?").bind(staffId).first();
      if (!staff) return json({ error: "Medewerker niet gevonden." }, 404);
      const revokeSessions = env.DB.prepare("UPDATE staff_sessions SET revoked_at = ? WHERE staff_id = ? AND revoked_at IS NULL").bind(timestamp, staffId);
      if (action === "restore") {
        await env.DB.prepare("UPDATE staff_access_tokens SET revoked_at = NULL WHERE id = ?").bind(staffId).run();
        return json({ ok: true });
      }
      if (staff.revoked_at) return json({ error: "Activeer dit account eerst weer." }, 400);
      if (action === "reset-mfa") {
        await env.DB.batch([
          env.DB.prepare("UPDATE staff_access_tokens SET totp_secret_enc = NULL, mfa_enabled = 0, last_totp_counter = -1 WHERE id = ?").bind(staffId),
          env.DB.prepare("DELETE FROM mfa_recovery_codes WHERE staff_id = ?").bind(staffId),
          revokeSessions
        ]);
        return json({ ok: true });
      }
      const password = randomHex(8).toUpperCase().replace(/(.{4})(?=.)/g, "$1-"), credentials = await hashPassword(password);
      await env.DB.batch([
        env.DB.prepare("UPDATE staff_access_tokens SET password_salt = ?, password_hash = ?, must_change_password = 1 WHERE id = ?").bind(credentials.salt, credentials.hash, staffId),
        revokeSessions
      ]);
      return json({ ok: true, password });
    }
    const staffRoute = /^\/api\/admin\/staff\/([0-9a-f-]{36})\/revoke$/i.exec(url.pathname);
    if (staffRoute && request.method === "POST") {
      if (!ownerOnly()) return json({ error: "Alleen de Cohentra-beheerder kan supporttoegang beheren." }, 403);
      const result = await env.DB.prepare("UPDATE staff_access_tokens SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL").bind(new Date().toISOString(), staffRoute[1]).run();
      if (!result.meta?.changes) return json({ error: "Actieve supporttoegang niet gevonden." }, 404);
      return json({ ok: true });
    }
    if (request.method === "GET" && url.pathname === "/api/admin/customers") {
      if (!hasPermission(actor, "customers.view")) return permissionDenied("customers.view");
      const { results } = await env.DB.prepare("SELECT c.id, c.customer_number, c.name, c.contact_name, c.contact_email, c.contact_role, c.phone, c.city, c.notes, c.status, c.created_at, c.customer_type, c.source, cp.product_id, cp.max_licenses, cp.allowed_license_types, cp.enabled AS product_enabled, (SELECT COUNT(*) FROM licenses l WHERE l.customer_id = c.id AND l.product_id = cp.product_id AND l.revoked_at IS NULL AND l.valid_until >= ?) AS licenses_in_use, (SELECT COUNT(*) FROM customer_portal_accounts a WHERE a.customer_id = c.id AND a.disabled_at IS NULL) AS portal_users, (SELECT COUNT(*) FROM support_tickets t WHERE t.customer_id = c.id AND t.status <> 'closed') AS open_tickets FROM customers c LEFT JOIN customer_products cp ON cp.customer_id = c.id AND cp.product_id = 'eventhub' WHERE c.id <> ? ORDER BY c.name COLLATE NOCASE, c.customer_number").bind(new Date().toISOString().slice(0, 10), WEBSITE_CONTACT_CUSTOMER_ID).all();
      return json({ customers: results.map((row) => ({ ...row, allowed_license_types: allowedLicenseTypes(row.allowed_license_types) })) });
    }
    if (request.method === "POST" && url.pathname === "/api/admin/customers") {
      if (!hasPermission(actor, "customers.manage")) return permissionDenied("customers.manage");
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const parsed = customerDetailsFromBody(body);
      if (parsed.error) return json({ error: parsed.error }, 400);
      const maxLicenses = body.max_licenses === undefined ? 5 : Number(body.max_licenses);
      const licenseTypes = Array.isArray(body.allowed_license_types) ? [...new Set(body.allowed_license_types.filter((type) => type === "beta" || type === "admin"))] : ["beta"];
      if (!Number.isInteger(maxLicenses) || maxLicenses < 0 || maxLicenses > 10000 || licenseTypes.length === 0) return json({ error: "Vul een geldige licentielimiet en minimaal één toegestaan licentietype in." }, 400);
      const id = crypto.randomUUID(), now = new Date().toISOString(), details = parsed.details;
      const last = await env.DB.prepare("SELECT MAX(CAST(substr(customer_number, 5) AS INTEGER)) AS n FROM customers WHERE customer_number LIKE 'CUS-%'").first();
      const customerNumber = "CUS-" + String(Number(last?.n || 0) + 1).padStart(4, "0");
      await env.DB.batch([
        env.DB.prepare("INSERT INTO customers (id, customer_number, " + CUSTOMER_DETAIL_COLUMNS.join(", ") + ", notes, status, created_at, updated_at) VALUES (?, ?, " + CUSTOMER_DETAIL_COLUMNS.map(() => "?").join(", ") + ", ?, 'active', ?, ?)").bind(id, customerNumber, ...CUSTOMER_DETAIL_COLUMNS.map((key) => details[key]), String(body.notes || "").trim().slice(0, 2000), now, now),
        env.DB.prepare("INSERT INTO customer_products (customer_id, product_id, max_licenses, allowed_license_types, enabled) VALUES (?, 'eventhub', ?, ?, 1)").bind(id, maxLicenses, JSON.stringify(licenseTypes))
      ]);
      return json({ customer: { id, customer_number: customerNumber, ...details, status: "active" } }, 201);
    }
    const portalAccountRoute = /^\/api\/admin\/customers\/([0-9a-f-]{36})\/portal-account$/i.exec(url.pathname);
    if (portalAccountRoute && request.method === "POST") {
      if (!hasPermission(actor, "customers.manage")) return permissionDenied("customers.manage");
      const customerRow = await env.DB.prepare("SELECT id, contact_email FROM customers WHERE id = ? AND status = 'active'").bind(portalAccountRoute[1]).first();
      if (!customerRow) return json({ error: "Klant niet gevonden." }, 404);
      const email = String(customerRow.contact_email || "").trim().toLowerCase();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json({ error: "Vul eerst een geldig e-mailadres in bij de klantgegevens." }, 400);
      const existing = await env.DB.prepare("SELECT id, username, active FROM customer_portal_accounts WHERE customer_id = ?").bind(customerRow.id).first();
      const accountId = existing?.id || crypto.randomUUID();
      if (!existing) {
        const placeholder = await hashPassword(randomHex(32));
        const accountUsername = email;
        try {
          await env.DB.prepare("INSERT INTO customer_portal_accounts (id, customer_id, username, password_salt, password_hash, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 0, ?, ?)")
            .bind(accountId, customerRow.id, accountUsername, placeholder.salt, placeholder.hash, new Date().toISOString(), new Date().toISOString()).run();
        } catch (error) {
          if (String(error?.message || error).toLowerCase().includes("unique")) return json({ error: "Dit e-mailadres is al als portaalgebruikersnaam in gebruik." }, 409);
          throw error;
        }
      }
      try {
        await sendCustomerAuthEmail(env, accountId, email, "invite");
      } catch (error) {
        console.error("Customer portal invitation could not be sent", error);
        return json({ error: "De uitnodigingsmail kon niet worden verstuurd. Controleer de e-mailinstelling en probeer opnieuw." }, 502);
      }
      return json({ email, account_id: accountId, existing_account: !!existing, message: existing?.active ? "Instellink verstuurd; bestaande toegang en wachtwoord blijven actief." : "Uitnodiging verstuurd; het account wordt actief zodra de klant een wachtwoord kiest." }, existing ? 200 : 201);
    }
    const customerRoute = /^\/api\/admin\/customers\/([0-9a-f-]{36})$/i.exec(url.pathname);
    if (customerRoute && request.method === "GET") {
      if (!hasPermission(actor, "customers.view")) return permissionDenied("customers.view");
      const customerId = customerRoute[1], today = new Date().toISOString().slice(0, 10);
      const customer = await env.DB.prepare("SELECT id, customer_number, " + CUSTOMER_DETAIL_COLUMNS.join(", ") + ", notes, status, created_at, updated_at, customer_type, source, billing_company FROM customers WHERE id = ? AND id <> ?").bind(customerId, WEBSITE_CONTACT_CUSTOMER_ID).first();
      if (!customer) return json({ error: "Klant niet gevonden." }, 404);
      const [products, catalog, licenses, users, tickets] = await Promise.all([
        env.DB.prepare("SELECT cp.product_id, p.name, p.active AS product_active, cp.max_licenses, cp.allowed_license_types, cp.enabled, (SELECT COUNT(*) FROM licenses l WHERE l.customer_id = cp.customer_id AND l.product_id = cp.product_id AND l.revoked_at IS NULL AND l.valid_until >= ?) AS in_use FROM customer_products cp JOIN products p ON p.id = cp.product_id WHERE cp.customer_id = ? ORDER BY p.name COLLATE NOCASE").bind(today, customerId).all(),
        env.DB.prepare("SELECT id, name FROM products WHERE active = 1 ORDER BY name COLLATE NOCASE").all(),
        env.DB.prepare("SELECT id, label, license_type, product_id, valid_from, valid_until, activated_at, last_seen_at FROM licenses WHERE customer_id = ? AND revoked_at IS NULL ORDER BY created_at DESC").bind(customerId).all(),
        env.DB.prepare("SELECT id, name, email, username, active, disabled_at, created_at, last_seen_at, role, email_verified_at FROM customer_portal_accounts WHERE customer_id = ? ORDER BY disabled_at IS NOT NULL, name COLLATE NOCASE, username").bind(customerId).all(),
        hasPermission(actor, "support.view") ? env.DB.prepare("SELECT id, reference, subject, status, updated_at FROM support_tickets WHERE customer_id = ? ORDER BY CASE WHEN status = 'closed' THEN 1 ELSE 0 END, updated_at DESC LIMIT 20").bind(customerId).all() : Promise.resolve({ results: null })
      ]);
      return json({
        customer,
        products: products.results.map((row) => ({ ...row, allowed_license_types: allowedLicenseTypes(row.allowed_license_types) })),
        catalog: catalog.results,
        licenses: licenses.results.map((row) => ({ ...row, valid_until: row.valid_until === UNLIMITED_UNTIL ? null : row.valid_until, expired: row.valid_until < today })),
        users: users.results,
        tickets: tickets.results
      });
    }
    if (customerRoute && request.method === "PATCH") {
      if (!hasPermission(actor, "customers.manage")) return permissionDenied("customers.manage");
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const parsed = customerDetailsFromBody(body);
      if (parsed.error) return json({ error: parsed.error }, 400);
      const details = parsed.details;
      const result = await env.DB.prepare("UPDATE customers SET " + CUSTOMER_DETAIL_COLUMNS.map((key) => key + " = ?").join(", ") + ", updated_at = ? WHERE id = ? AND id <> ?").bind(...CUSTOMER_DETAIL_COLUMNS.map((key) => details[key]), new Date().toISOString(), customerRoute[1], WEBSITE_CONTACT_CUSTOMER_ID).run();
      if (!result.meta?.changes) return json({ error: "Klant niet gevonden." }, 404);
      return json({ ok: true });
    }
    if (customerRoute && request.method === "DELETE") {
      if (!ownerOnly()) return json({ error: "Alleen de eigenaar kan klanten verwijderen." }, 403);
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const customer = await env.DB.prepare("SELECT id, name FROM customers WHERE id = ? AND id <> ?").bind(customerRoute[1], WEBSITE_CONTACT_CUSTOMER_ID).first();
      if (!customer) return json({ error: "Klant niet gevonden." }, 404);
      if (String(body.confirm_name || "").trim() !== customer.name) return json({ error: "Typ de klantnaam precies over om te bevestigen." }, 400);
      // Betaalhistorie moet bewaard blijven: zo'n klant kan alleen worden gepauzeerd.
      const commerce = await env.DB.prepare("SELECT (SELECT COUNT(*) FROM shop_orders WHERE customer_id = ?) + (SELECT COUNT(*) FROM entitlements WHERE customer_id = ?) + (SELECT COUNT(*) FROM billing_invoices WHERE customer_id = ?) AS n").bind(customer.id, customer.id, customer.id).first();
      if (Number(commerce?.n || 0)) return json({ error: "Deze klant heeft bestellingen, facturen of rechten. Die moeten bewaard blijven; pauzeer de klant in plaats van te verwijderen." }, 409);
      // Licenses keep their history: they are revoked and detached so validation stops immediately.
      await env.DB.batch([
        env.DB.prepare("UPDATE licenses SET revoked_at = COALESCE(revoked_at, ?), customer_id = NULL, group_id = NULL WHERE customer_id = ?").bind(new Date().toISOString(), customer.id),
        env.DB.prepare("DELETE FROM customers WHERE id = ?").bind(customer.id)
      ]);
      return json({ ok: true });
    }
    const customerNotesRoute = /^\/api\/admin\/customers\/([0-9a-f-]{36})\/notes$/i.exec(url.pathname);
    if (customerNotesRoute && request.method === "PUT") {
      if (!hasPermission(actor, "customers.manage")) return permissionDenied("customers.manage");
      let body;
      try { body = await readJson(request, 16384); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const notes = String(body.notes || "").slice(0, 2000);
      const result = await env.DB.prepare("UPDATE customers SET notes = ?, updated_at = ? WHERE id = ? AND id <> ?").bind(notes, new Date().toISOString(), customerNotesRoute[1], WEBSITE_CONTACT_CUSTOMER_ID).run();
      if (!result.meta?.changes) return json({ error: "Klant niet gevonden." }, 404);
      return json({ ok: true });
    }
    const customerProductRoute = /^\/api\/admin\/customers\/([0-9a-f-]{36})\/products\/([a-z0-9_-]{1,40})$/i.exec(url.pathname);
    if (customerProductRoute && request.method === "PUT") {
      if (!hasPermission(actor, "customers.manage")) return permissionDenied("customers.manage");
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const maxLicenses = Number(body.max_licenses);
      const licenseTypes = Array.isArray(body.allowed_license_types) ? [...new Set(body.allowed_license_types.filter((type) => type === "beta" || type === "admin"))] : [];
      if (!Number.isInteger(maxLicenses) || maxLicenses < 0 || maxLicenses > 10000 || licenseTypes.length === 0) return json({ error: "Vul een geldige licentielimiet en minimaal één toegestaan licentietype in." }, 400);
      const [customer, product] = await Promise.all([
        env.DB.prepare("SELECT id FROM customers WHERE id = ? AND id <> ?").bind(customerProductRoute[1], WEBSITE_CONTACT_CUSTOMER_ID).first(),
        env.DB.prepare("SELECT id FROM products WHERE id = ? AND active = 1").bind(customerProductRoute[2]).first()
      ]);
      if (!customer) return json({ error: "Klant niet gevonden." }, 404);
      if (!product) return json({ error: "Product niet gevonden." }, 404);
      await env.DB.prepare("INSERT INTO customer_products (customer_id, product_id, max_licenses, allowed_license_types, enabled) VALUES (?, ?, ?, ?, ?) ON CONFLICT(customer_id, product_id) DO UPDATE SET max_licenses = excluded.max_licenses, allowed_license_types = excluded.allowed_license_types, enabled = excluded.enabled").bind(customer.id, product.id, maxLicenses, JSON.stringify(licenseTypes), body.enabled === false ? 0 : 1).run();
      return json({ ok: true });
    }
    const customerPortalUsersRoute = /^\/api\/admin\/customers\/([0-9a-f-]{36})\/portal-users$/i.exec(url.pathname);
    if (customerPortalUsersRoute && request.method === "POST") {
      if (!hasPermission(actor, "customers.manage")) return permissionDenied("customers.manage");
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const name = String(body.name || "").trim().slice(0, 120), email = String(body.email || "").trim().toLowerCase().slice(0, 254);
      if (!name) return json({ error: "Vul een naam in." }, 400);
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json({ error: "Vul een geldig e-mailadres in." }, 400);
      const customer = await env.DB.prepare("SELECT id FROM customers WHERE id = ? AND status = 'active' AND id <> ?").bind(customerPortalUsersRoute[1], WEBSITE_CONTACT_CUSTOMER_ID).first();
      if (!customer) return json({ error: "Klant niet gevonden of gepauzeerd." }, 404);
      const accountId = crypto.randomUUID(), now = new Date().toISOString(), placeholder = await hashPassword(randomHex(32));
      try {
        await env.DB.prepare("INSERT INTO customer_portal_accounts (id, customer_id, username, name, email, password_salt, password_hash, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)").bind(accountId, customer.id, email, name, email, placeholder.salt, placeholder.hash, now, now).run();
      } catch (error) {
        if (String(error?.message || error).toLowerCase().includes("unique")) return json({ error: "Dit e-mailadres heeft al een portaalaccount." }, 409);
        throw error;
      }
      try { await sendCustomerAuthEmail(env, accountId, email, "invite"); }
      catch (error) {
        console.error("Customer portal invitation could not be sent", error);
        return json({ error: "Het account is aangemaakt, maar de uitnodiging kon niet worden verstuurd. Stuur hem opnieuw via het menu.", id: accountId }, 502);
      }
      return json({ ok: true, id: accountId, email }, 201);
    }
    const portalUserRoute = /^\/api\/admin\/portal-users\/([0-9a-f-]{36})\/(resend|disable|enable)$/i.exec(url.pathname);
    if (portalUserRoute && request.method === "POST") {
      if (!hasPermission(actor, "customers.manage")) return permissionDenied("customers.manage");
      const account = await env.DB.prepare("SELECT a.id, a.email, a.username, a.active, a.disabled_at, c.status AS customer_status FROM customer_portal_accounts a JOIN customers c ON c.id = a.customer_id WHERE a.id = ?").bind(portalUserRoute[1]).first();
      if (!account) return json({ error: "Portaalgebruiker niet gevonden." }, 404);
      const action = portalUserRoute[2].toLowerCase(), now = new Date().toISOString();
      if (action === "disable") {
        await env.DB.batch([
          env.DB.prepare("UPDATE customer_portal_accounts SET disabled_at = COALESCE(disabled_at, ?), updated_at = ? WHERE id = ?").bind(now, now, account.id),
          env.DB.prepare("UPDATE customer_sessions SET revoked_at = ? WHERE customer_account_id = ? AND revoked_at IS NULL").bind(now, account.id),
          env.DB.prepare("UPDATE customer_auth_tokens SET consumed_at = ? WHERE customer_account_id = ? AND consumed_at IS NULL").bind(Date.now(), account.id)
        ]);
        return json({ ok: true });
      }
      if (action === "enable") {
        await env.DB.prepare("UPDATE customer_portal_accounts SET disabled_at = NULL, updated_at = ? WHERE id = ?").bind(now, account.id).run();
        return json({ ok: true });
      }
      if (account.disabled_at) return json({ error: "Schakel dit account eerst weer in." }, 400);
      if (account.customer_status !== "active") return json({ error: "Deze klant is gepauzeerd." }, 400);
      const recipient = String(account.email || account.username).trim().toLowerCase(), purpose = account.active === 1 ? "password_reset" : "invite";
      try { await sendCustomerAuthEmail(env, account.id, recipient, purpose); }
      catch (error) {
        console.error("Customer portal e-mail could not be sent", error);
        return json({ error: "De e-mail kon niet worden verstuurd. Probeer het later opnieuw." }, 502);
      }
      return json({ ok: true, email: recipient, purpose });
    }
    const customerStatusRoute = /^\/api\/admin\/customers\/([0-9a-f-]{36})\/(pause|resume)$/i.exec(url.pathname);
    if (customerStatusRoute && request.method === "POST") {
      if (!hasPermission(actor, "customers.manage")) return permissionDenied("customers.manage");
      const status = customerStatusRoute[2] === "pause" ? "paused" : "active";
      const result = await env.DB.prepare("UPDATE customers SET status = ?, updated_at = ? WHERE id = ?").bind(status, new Date().toISOString(), customerStatusRoute[1]).run();
      if (!result.meta?.changes) return json({ error: "Klant niet gevonden." }, 404);
      return json({ ok: true, status });
    }
    const licenseScopeRoute = /^\/api\/admin\/license-scope\/(intern|[0-9a-f-]{36})$/i.exec(url.pathname);
    if (licenseScopeRoute && request.method === "GET") {
      if (!hasPermission(actor, "licenses.view")) return permissionDenied("licenses.view");
      const owner = licenseScopeRoute[1].toLowerCase() === "intern" ? null : licenseScopeRoute[1];
      if (!owner && actor.role === "support") return json({ error: "Alleen de eigenaar ziet interne licenties." }, 403);
      const today = new Date().toISOString().slice(0, 10);
      const [licenses, groups] = await Promise.all([
        env.DB.prepare("SELECT l.id, l.label, l.license_type, l.product_id, l.valid_from, l.valid_until, l.created_at, l.revoked_at, l.activated_at, l.last_seen_at, l.group_id FROM licenses l WHERE l.customer_id IS ? ORDER BY l.revoked_at IS NOT NULL, l.label COLLATE NOCASE, l.created_at").bind(owner).all(),
        env.DB.prepare("SELECT g.id, g.name, (SELECT COUNT(*) FROM licenses l WHERE l.group_id = g.id AND l.revoked_at IS NULL) AS license_count FROM license_groups g WHERE g.customer_id IS ? ORDER BY g.name COLLATE NOCASE").bind(owner).all()
      ]);
      return json({
        groups: groups.results,
        licenses: licenses.results.map((row) => ({ ...row, unlimited: row.valid_until === UNLIMITED_UNTIL, valid_until: row.valid_until === UNLIMITED_UNTIL ? null : row.valid_until, expired: !row.revoked_at && row.valid_until < today }))
      });
    }
    if (request.method === "GET" && url.pathname === "/api/admin/licenses/expiring") {
      if (!hasPermission(actor, "licenses.view")) return permissionDenied("licenses.view");
      const today = new Date().toISOString().slice(0, 10), limit = new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10);
      const [active, expiring] = await Promise.all([
        env.DB.prepare("SELECT COUNT(*) AS n FROM licenses WHERE revoked_at IS NULL AND valid_until >= ?" + (actor.role === "support" ? " AND customer_id IS NOT NULL" : "")).bind(today).first(),
        env.DB.prepare("SELECT l.id, l.label, l.license_type, l.valid_until, l.customer_id, c.name AS customer_name, g.name AS group_name, l.expiry_notice_sent_at FROM licenses l LEFT JOIN customers c ON c.id = l.customer_id LEFT JOIN license_groups g ON g.id = l.group_id WHERE l.revoked_at IS NULL AND l.valid_until >= ? AND l.valid_until <= ?" + (actor.role === "support" ? " AND l.customer_id IS NOT NULL" : "") + " ORDER BY l.valid_until, c.name COLLATE NOCASE LIMIT 50").bind(today, limit).all()
      ]);
      return json({ active: Number(active?.n || 0), expiring: expiring.results });
    }
    if (request.method === "POST" && url.pathname === "/api/admin/licenses/extend") {
      if (!hasPermission(actor, "licenses.manage")) return permissionDenied("licenses.manage");
      let body; try { body = await readJson(request, 32768); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const ids = Array.isArray(body.license_ids) ? [...new Set(body.license_ids.map(String))] : [];
      const validUntil = String(body.valid_until || ""), today = new Date().toISOString().slice(0, 10);
      if (!ids.length || ids.length > 500 || ids.some((id) => !/^[0-9a-f-]{36}$/i.test(id))) return json({ error: "Selecteer één of meer geldige licenties." }, 400);
      if (!isIsoDate(validUntil) || validUntil < today) return json({ error: "Kies een einddatum vanaf vandaag." }, 400);
      const { results: rows } = await env.DB.prepare("SELECT id, customer_id, product_id, valid_until FROM licenses WHERE revoked_at IS NULL AND valid_until <> ? AND id IN (" + ids.map(() => "?").join(", ") + ")").bind(UNLIMITED_UNTIL, ...ids).all();
      if (!rows.length) return json({ error: "Geen actieve licenties met een einddatum geselecteerd." }, 400);
      // Extending an expired license makes it count again, so check each customer's limit first.
      const revived = rows.filter((row) => row.valid_until < today && row.customer_id);
      for (const customerId of [...new Set(revived.map((row) => row.customer_id))]) {
        const extra = revived.filter((row) => row.customer_id === customerId).length;
        const limit = await env.DB.prepare("SELECT cp.max_licenses, (SELECT COUNT(*) FROM licenses l WHERE l.customer_id = cp.customer_id AND l.product_id = cp.product_id AND l.revoked_at IS NULL AND l.valid_until >= ?) AS in_use FROM customer_products cp WHERE cp.customer_id = ? AND cp.product_id = 'eventhub'").bind(today, customerId).first();
        if (limit && Number(limit.in_use) + extra > Number(limit.max_licenses)) return json({ error: `Met deze verlenging komt een klant boven de limiet (${limit.in_use} + ${extra} van ${limit.max_licenses}).` }, 409);
      }
      const results = await env.DB.batch(rows.map((row) => env.DB.prepare("UPDATE licenses SET valid_until = ?, expiry_notice_sent_at = NULL WHERE id = ? AND revoked_at IS NULL").bind(validUntil, row.id)));
      return json({ ok: true, extended: results.reduce((n, r) => n + (r.meta?.changes || 0), 0), skipped: ids.length - rows.length });
    }
    const replaceRoute = /^\/api\/admin\/licenses\/([0-9a-f-]{36})\/replace$/i.exec(url.pathname);
    if (replaceRoute && request.method === "POST") {
      if (!hasPermission(actor, "licenses.issue") || !hasPermission(actor, "licenses.manage")) return permissionDenied("licenses.manage");
      const old = await env.DB.prepare("SELECT l.*, c.status AS customer_status FROM licenses l LEFT JOIN customers c ON c.id = l.customer_id WHERE l.id = ? AND l.revoked_at IS NULL").bind(replaceRoute[1]).first();
      if (!old) return json({ error: "Actieve licentie niet gevonden." }, 404);
      if (!old.customer_id && actor.role === "support") return json({ error: "Alleen de eigenaar beheert interne licenties." }, 403);
      if (old.customer_id && old.customer_status !== "active") return json({ error: "Deze klant is gepauzeerd." }, 400);
      const licenseKey = createLicenseKey(), id = crypto.randomUUID(), now = new Date().toISOString();
      await env.DB.batch([
        env.DB.prepare("UPDATE licenses SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL").bind(now, old.id),
        env.DB.prepare("INSERT INTO licenses (id, key_hash, label, created_at, valid_from, valid_until, license_type, group_id, customer_id, product_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)").bind(id, await digest(normalizedKey(licenseKey)), old.label, now, old.valid_from, old.valid_until, old.license_type, old.group_id, old.customer_id, old.product_id || "eventhub")
      ]);
      return json({ ok: true, id, license_key: licenseKey, label: old.label }, 201);
    }
    if (request.method === "GET" && url.pathname === "/api/admin/licenses") {
      if (!hasPermission(actor, "licenses.view")) return permissionDenied("licenses.view");
      const { results } = await env.DB.prepare("SELECT l.id, l.label, l.valid_from, l.valid_until, l.created_at, l.revoked_at, l.license_type, l.activated_at, l.last_seen_at, l.group_id, g.name AS group_name, l.customer_id, c.name AS customer_name FROM licenses l LEFT JOIN license_groups g ON g.id = l.group_id LEFT JOIN customers c ON c.id = l.customer_id WHERE l.revoked_at IS NULL ORDER BY l.created_at DESC LIMIT 1000").all();
      const { results: groups } = await env.DB.prepare("SELECT g.id, g.name, COUNT(l.id) AS license_count FROM license_groups g LEFT JOIN licenses l ON l.group_id = g.id AND l.revoked_at IS NULL GROUP BY g.id, g.name ORDER BY g.name COLLATE NOCASE").all();
      const today = new Date().toISOString().slice(0, 10);
      return json({ groups, licenses: results.map((row) => ({
        ...row,
        valid_until: row.valid_until === UNLIMITED_UNTIL ? "Onbeperkt" : row.valid_until,
        license_type: row.license_type || (row.valid_until === UNLIMITED_UNTIL ? "Beheerder" : "Gesloten beta"),
        status: row.revoked_at ? "Ingetrokken" : today < row.valid_from ? "Gepland" : today > row.valid_until ? "Verlopen" : "Actief"
      })) });
    }
    if (request.method === "POST" && url.pathname === "/api/admin/licenses") {
      if (!hasPermission(actor, "licenses.issue")) return permissionDenied("licenses.issue");
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const validFrom = String(body.valid_from || "");
      const unlimited = body.unlimited === true;
      const licenseType = body.license_type === "admin" ? "Beheerder" : "Gesloten beta";
      const effectiveUnlimited = licenseType === "Beheerder" || unlimited;
      const validUntil = effectiveUnlimited ? UNLIMITED_UNTIL : String(body.valid_until || "");
      const count = Number(body.count || 1);
      if (!Number.isInteger(count) || count < 1 || count > 100) return json({ error: "Aantal licenties moet tussen 1 en 100 liggen." }, 400);
      if (!isIsoDate(validFrom) || (!effectiveUnlimited && (!isIsoDate(validUntil) || validUntil < validFrom))) {
        return json({ error: "Controleer de begindatum en einddatum." }, 400);
      }
      const label = String(body.label || "").trim().slice(0, 80);
      const groupId = body.group_id ? String(body.group_id) : null;
      const customerId = body.customer_id ? String(body.customer_id) : null;
      const productId = customerId ? String(body.product_id || "eventhub") : "eventhub";
      if (actor.role === "support" && !customerId) return json({ error: "Support kan alleen licenties namens een klant aanmaken." }, 403);
      if (customerId) {
        const entitlement = await env.DB.prepare("SELECT c.status, cp.max_licenses, cp.allowed_license_types, cp.enabled, p.active AS product_active FROM customers c JOIN customer_products cp ON cp.customer_id = c.id JOIN products p ON p.id = cp.product_id WHERE c.id = ? AND cp.product_id = ?").bind(customerId, productId).first();
        if (!entitlement || entitlement.status !== "active" || entitlement.enabled !== 1 || entitlement.product_active !== 1) return json({ error: "Deze klant heeft geen actieve toegang tot dit product." }, 400);
        if (!allowedLicenseTypes(entitlement.allowed_license_types).includes(licenseType === "admin" ? "admin" : "beta")) return json({ error: "Dit licentietype is niet toegestaan voor deze klant." }, 403);
        const used = await env.DB.prepare("SELECT COUNT(*) AS count FROM licenses WHERE customer_id = ? AND product_id = ? AND revoked_at IS NULL AND valid_until >= ?").bind(customerId, productId, new Date().toISOString().slice(0, 10)).first();
        if (Number(used?.count || 0) + count > Number(entitlement.max_licenses)) return json({ error: `De klantlimiet is bereikt (${used?.count || 0} van ${entitlement.max_licenses} in gebruik).` }, 409);
      }
      if (groupId && !await env.DB.prepare("SELECT 1 FROM license_groups WHERE id = ? AND customer_id IS ?").bind(groupId, customerId).first()) return json({ error: "De gekozen groep bestaat niet bij deze klant." }, 400);
      const createdAt = new Date().toISOString();
      const licenses = await Promise.all(Array.from({length: count}, async (_, i) => {
        const licenseKey = createLicenseKey();
        const id = crypto.randomUUID();
        const itemLabel = count > 1 ? `${label || "Licentie"} ${String(i + 1).padStart(3, "0")}`.slice(0, 80) : label;
        return { id, license_key: licenseKey, label: itemLabel, statement: env.DB.prepare("INSERT INTO licenses (id, key_hash, label, created_at, valid_from, valid_until, license_type, group_id, customer_id, product_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)").bind(id, await digest(normalizedKey(licenseKey)), itemLabel, createdAt, validFrom, validUntil, licenseType, groupId, customerId, productId) };
      }));
      await env.DB.batch(licenses.map((x) => x.statement));
      return json({ licenses: licenses.map(({statement, ...x}) => ({...x, customer_id: customerId, product_id: productId, valid_from: validFrom, valid_until: effectiveUnlimited ? null : validUntil})) }, 201);
    }
    if (request.method === "POST" && url.pathname === "/api/admin/licenses/group") {
      if (!hasPermission(actor, "licenses.manage")) return permissionDenied("licenses.manage");
      let body;
      try { body = await readJson(request, 32768); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const ids = Array.isArray(body.license_ids) ? [...new Set(body.license_ids.map(String))] : [];
      if (!ids.length || ids.length > 500 || ids.some((id) => !/^[0-9a-f-]{36}$/i.test(id))) return json({ error: "Selecteer één of meer geldige licenties." }, 400);
      const groupId = body.group_id ? String(body.group_id) : null;
      if (groupId && !await env.DB.prepare("SELECT 1 FROM license_groups WHERE id = ?").bind(groupId).first()) return json({ error: "De gekozen groep bestaat niet." }, 400);
      // A license can only join a group of its own customer (or an internal group for internal licenses).
      const updates = ids.map((id) => groupId
        ? env.DB.prepare("UPDATE licenses SET group_id = ? WHERE id = ? AND revoked_at IS NULL AND customer_id IS (SELECT customer_id FROM license_groups WHERE id = ?)").bind(groupId, id, groupId)
        : env.DB.prepare("UPDATE licenses SET group_id = NULL WHERE id = ? AND revoked_at IS NULL").bind(id));
      const results = await env.DB.batch(updates);
      const moved = results.reduce((count, result) => count + (result.meta?.changes || 0), 0);
      return json({ ok: true, moved });
    }
    if (request.method === "POST" && url.pathname === "/api/admin/groups") {
      if (!hasPermission(actor, "licenses.manage")) return permissionDenied("licenses.manage");
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const name = String(body.name || "").trim().slice(0, 60);
      if (!name) return json({ error: "Vul een groepsnaam in." }, 400);
      const customerId = body.customer_id ? String(body.customer_id) : null;
      if (!customerId && actor.role === "support") return json({ error: "Alleen de eigenaar beheert interne groepen." }, 403);
      if (customerId && !await env.DB.prepare("SELECT 1 FROM customers WHERE id = ? AND id <> ?").bind(customerId, WEBSITE_CONTACT_CUSTOMER_ID).first()) return json({ error: "Klant niet gevonden." }, 404);
      const id = crypto.randomUUID();
      try { await env.DB.prepare("INSERT INTO license_groups (id, customer_id, name, created_at) VALUES (?, ?, ?, ?)").bind(id, customerId, name, new Date().toISOString()).run(); }
      catch { return json({ error: "Deze klant heeft al een groep met deze naam." }, 409); }
      return json({ id, name, customer_id: customerId }, 201);
    }
    const groupRoute = /^\/api\/admin\/groups\/([0-9a-f-]{36})$/i.exec(url.pathname);
    if (groupRoute && request.method === "PATCH") {
      if (!hasPermission(actor, "licenses.manage")) return permissionDenied("licenses.manage");
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const name = String(body.name || "").trim().slice(0, 60);
      if (!name) return json({ error: "Vul een groepsnaam in." }, 400);
      try { const result = await env.DB.prepare("UPDATE license_groups SET name = ? WHERE id = ?").bind(name, groupRoute[1]).run(); if (!result.meta?.changes) return json({ error: "Groep niet gevonden." }, 404); }
      catch { return json({ error: "Deze klant heeft al een groep met deze naam." }, 409); }
      return json({ ok: true, name });
    }
    if (groupRoute && request.method === "DELETE") {
      if (!hasPermission(actor, "licenses.manage")) return permissionDenied("licenses.manage");
      await env.DB.prepare("UPDATE licenses SET group_id = NULL WHERE group_id = ?").bind(groupRoute[1]).run();
      const result = await env.DB.prepare("DELETE FROM license_groups WHERE id = ?").bind(groupRoute[1]).run();
      if (!result.meta?.changes) return json({ error: "Groep niet gevonden." }, 404);
      return json({ ok: true });
    }
    const assignGroup = /^\/api\/admin\/licenses\/([0-9a-f-]{36})\/group$/i.exec(url.pathname);
    if (request.method === "POST" && assignGroup) {
      if (!hasPermission(actor, "licenses.manage")) return permissionDenied("licenses.manage");
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      const groupId = body.group_id ? String(body.group_id) : null;
      if (groupId && !await env.DB.prepare("SELECT 1 FROM license_groups WHERE id = ?").bind(groupId).first()) return json({ error: "De gekozen groep bestaat niet." }, 400);
      const result = groupId
        ? await env.DB.prepare("UPDATE licenses SET group_id = ? WHERE id = ? AND revoked_at IS NULL AND customer_id IS (SELECT customer_id FROM license_groups WHERE id = ?)").bind(groupId, assignGroup[1], groupId).run()
        : await env.DB.prepare("UPDATE licenses SET group_id = NULL WHERE id = ? AND revoked_at IS NULL").bind(assignGroup[1]).run();
      if (!result.meta?.changes) return json({ error: "Actieve licentie niet gevonden." }, 404);
      return json({ ok: true });
    }
    const revoke = /^\/api\/admin\/licenses\/([0-9a-f-]{36})\/revoke$/i.exec(url.pathname);
    if (request.method === "POST" && revoke) {
      if (!hasPermission(actor, "licenses.manage")) return permissionDenied("licenses.manage");
      const result = await env.DB.prepare("UPDATE licenses SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL").bind(new Date().toISOString(), revoke[1]).run();
      if (!result.meta?.changes) return json({ error: "Licentie niet gevonden of al ingetrokken." }, 404);
      return json({ ok: true });
    }
    const rename = /^\/api\/admin\/licenses\/([0-9a-f-]{36})\/label$/i.exec(url.pathname);
    if (request.method === "POST" && rename) {
      if (!hasPermission(actor, "licenses.manage")) return permissionDenied("licenses.manage");
      let body;
      try { body = await readJson(request); } catch { return json({ error: "Ongeldige aanvraag." }, 400); }
      if (typeof body.label !== "string") return json({ error: "Voer een geldige naam in." }, 400);
      const label = body.label.trim().slice(0, 80);
      const result = await env.DB.prepare("UPDATE licenses SET label = ? WHERE id = ? AND revoked_at IS NULL").bind(label, rename[1]).run();
      if (!result.meta?.changes) return json({ error: "Actieve licentie niet gevonden." }, 404);
      return json({ ok: true, label });
    }
    const reset = /^\/api\/admin\/licenses\/([0-9a-f-]{36})\/reset-activation$/i.exec(url.pathname);
    if (request.method === "POST" && reset) {
      if (!hasPermission(actor, "licenses.manage")) return permissionDenied("licenses.manage");
      const result = await env.DB.prepare("UPDATE licenses SET activated_device_hash = NULL, activated_at = NULL WHERE id = ? AND activated_device_hash IS NOT NULL").bind(reset[1]).run();
      if (!result.meta?.changes) return json({ error: "Licentie niet gevonden of niet geactiveerd." }, 404);
      return json({ ok: true });
    }
    return json({ error: "Niet gevonden." }, 404);
  }
  return json({ error: "Niet gevonden." }, 404);
}

// Runs once a day (Cron Trigger): customers hear 14 days in advance which licenses expire.
async function sendExpiryNotices(env) {
  if (!env.EMAIL) return { sent: 0 };
  const today = new Date().toISOString().slice(0, 10), limit = new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 10);
  const { results } = await env.DB.prepare("SELECT l.id, l.label, l.valid_until, c.id AS customer_id, c.name AS customer_name, c.contact_email FROM licenses l JOIN customers c ON c.id = l.customer_id WHERE l.revoked_at IS NULL AND l.expiry_notice_sent_at IS NULL AND l.valid_until >= ? AND l.valid_until <= ? AND c.status = 'active' ORDER BY l.valid_until").bind(today, limit).all();
  const byCustomer = new Map();
  for (const row of results) { if (!byCustomer.has(row.customer_id)) byCustomer.set(row.customer_id, []); byCustomer.get(row.customer_id).push(row); }
  const brand = await loadEmailTemplateSettings(env, "branding");
  const formatDate = (iso) => new Date(iso + "T12:00:00Z").toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Amsterdam" });
  let sent = 0;
  for (const [customerId, rows] of byCustomer) {
    const { results: users } = await env.DB.prepare("SELECT email FROM customer_portal_accounts WHERE customer_id = ? AND active = 1 AND disabled_at IS NULL AND email <> ''").bind(customerId).all();
    const recipients = [...new Set([rows[0].contact_email, ...users.map((u) => u.email)].map((v) => String(v || "").trim().toLowerCase()).filter((v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)))];
    if (!recipients.length) continue;
    const list = rows.map((row) => (row.label || "Licentie zonder naam") + " (tot en met " + formatDate(row.valid_until) + ")");
    const subject = rows.length === 1 ? "Je EventHub-licentie verloopt binnenkort" : "Je EventHub-licenties verlopen binnenkort";
    const intro = "Binnenkort verloopt " + (rows.length === 1 ? "deze licentie" : "het volgende") + " voor " + rows[0].customer_name + ": " + list.join("; ") + ". Wil je blijven werken met EventHub? Neem dan contact met ons op, dan verlengen we de licentie.";
    const html = renderAuthEmailHtml({ subject, intro, link: "https://customer.cohentra.digital/", button: "Naar het klantenportaal", expiryNote: "Je ontvangt deze melding 14 dagen voordat een licentie verloopt. Vragen? Mail naar support@cohentra.digital.", brand });
    const text = subject + "\n\n" + intro + "\n\nKlantenportaal: https://customer.cohentra.digital/\n\nCohentra Digital · support@cohentra.digital";
    try {
      for (const to of recipients) await env.EMAIL.send({ to, from: { email: "noreply@noreply.cohentra.digital", name: "Cohentra Digital" }, replyTo: "support@cohentra.digital", subject, text, html });
      const now = new Date().toISOString();
      await env.DB.batch(rows.map((row) => env.DB.prepare("UPDATE licenses SET expiry_notice_sent_at = ? WHERE id = ?").bind(now, row.id)));
      sent += 1;
    } catch (error) { console.error("license_expiry_notice_failed", { customer: customerId, message: String(error?.message || error).slice(0, 160) }); }
  }
  return { sent };
}

export default {
  async fetch(request, env) {
    try {
      if (request.method === "GET" || request.method === "HEAD") {
        const asset = brandAssetResponse(new URL(request.url).pathname);
        if (asset) return asset;
      }
      return await handle(request, env);
    } catch (error) {
      console.error(JSON.stringify({ event: "request_failed", message: String(error?.message || error) }));
      return json({ error: "Er is iets misgegaan. Probeer het later opnieuw." }, 500);
    }
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(sendExpiryNotices(env).catch((error) => console.error("license_expiry_run_failed", String(error?.message || error).slice(0, 160))));
  }
};
