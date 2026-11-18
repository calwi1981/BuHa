// BUHA_ADMIN_NAV_342

function updateRecurringVisibility(){
 const tenant=(state.tenants||[]).find(t=>
  Number(t.id)===Number(state.tenantId)
 );
 const isLandlord=tenant?.tenant_type==="vermieter";
 document.querySelectorAll('[data-page="recurringInvoices"]')
  .forEach(button=>{
   button.hidden=isLandlord;
   button.style.display=isLandlord?"none":"";
  });
}

"use strict";
const $=id=>document.getElementById(id);
const state={page:"dashboard",user:null,editing:null,rows:[],tenants:[],tenantId:null,tenantRole:null};
const titles={dashboard:"Übersicht",partners:"Kunden & Lieferanten",accounts:"Kontenplan",
 products:"Produkte & Leistungen",invoices:"Rechnungen",bookings:"Buchungen",journal:"Monatsjournal",eur:"EÜR",administration:"Administration"};
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const euro=v=>new Intl.NumberFormat("de-DE",{style:"currency",currency:"EUR"}).format(Number(v||0));
const today=()=>new Date().toLocaleDateString("sv-SE");
function notify(message,bad=false){const n=$("notice");n.textContent=message;n.className="notice"+(bad?" bad":"");}
async function api(path,options={}){
 const tenantHeader=state.tenantId&&!path.startsWith("/api/auth/")&&
  !path.startsWith("/api/tenants/my")&&
  !path.startsWith("/api/system/")
  ?{"X-Tenant-ID":String(state.tenantId)}:{};
 const response=await fetch(path,{credentials:"same-origin",
  ...options,
  headers:{"Content-Type":"application/json",...tenantHeader,...(options.headers||{})}
 });
 if(response.status===401){showLogin();throw Error("Sitzung abgelaufen. Bitte anmelden.");}
 let data;try{data=await response.json();}catch{data={};}
 if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:JSON.stringify(data.detail||data));
 return data;
}
let companyLogoUrl = null;

async function loadCompanyLogo(){
 try{
  if(!state.tenantId)throw Error("Kein aktiver Mandant");
  const response = await fetch(
   "/api/administration/logo",
   {credentials:"same-origin",cache:"no-store",
    headers:{"X-Tenant-ID":String(state.tenantId)}}
  );

  if(!response.ok)throw Error("Kein Logo");

  const blob = await response.blob();

  if(!blob.type.startsWith("image/"))
   throw Error("Keine Bilddatei");

  const url = URL.createObjectURL(blob);

  if(companyLogoUrl)
   URL.revokeObjectURL(companyLogoUrl);

  companyLogoUrl = url;

  document.querySelectorAll(".company-logo").forEach(img=>{
   img.src=url;
   img.classList.remove("hidden");
  });

 }catch{
  document.querySelectorAll(".company-logo").forEach(img=>{
   img.removeAttribute("src");
   img.classList.add("hidden");
  });
 }
}

function showLogin(){$("login").classList.remove("hidden");$("application").classList.add("hidden");}

async function loadTenants(){
 const result=await api("/api/tenants/my");
 const tenants=Array.isArray(result)?result:
  Array.isArray(result.tenants)?result.tenants:null;
 if(!tenants)throw Error("Mandantenliste ungueltig.");

 state.tenants=tenants;
 const tenantStorageKey="buha.selectedTenant."+
  String(state.user?.id??state.user?.username??"unknown");
 let savedTenantId=null;
 try{
  savedTenantId=Number(localStorage.getItem(tenantStorageKey));
 }catch{}
 const available=id=>tenants.some(t=>Number(t.id)===Number(id));
 if(!state.tenantId||!available(state.tenantId)){
  state.tenantId=available(savedTenantId)
   ?savedTenantId
   :(tenants.length?Number(tenants[0].id):null);
 }
 if(state.tenantId){
  try{localStorage.setItem(tenantStorageKey,String(state.tenantId));}catch{}
 }
 const active=tenants.find(t=>Number(t.id)===Number(state.tenantId));
 state.tenantRole=active?.role||null;
  updateRecurringVisibility();

 const selector=$("tenant-selector");
 if(selector){
  selector.innerHTML=tenants.map(t=>
   '<option value="'+Number(t.id)+'"'+
   (Number(t.id)===state.tenantId?' selected':'')+'>'+
   esc(t.name||t.code||("Mandant "+t.id))+'</option>'
  ).join("");
  selector.disabled=tenants.length<2;
 }
}

function showApp(){
 // BUHA_NAV_FIX_351
 const activeTenant=(state.tenants||[]).find(t=>
  Number(t.id)===Number(state.tenantId)
 );
 loadCompanyLogo();
 $("login").classList.add("hidden");
 $("application").classList.remove("hidden");
 $("current-user").textContent=state.user?.username||"";
 const isSystemAdmin=state.user?.role==="system_admin";
 document.querySelectorAll("#navigation [data-page]").forEach(button=>{
  if(button.dataset.page!=="systemAdministration")
   button.classList.toggle("hidden",isSystemAdmin);
 });
 $("system-admin-nav").classList.toggle("hidden",!isSystemAdmin);
 const isTenantAdmin=!isSystemAdmin&&state.tenantRole==="admin";
 $("admin-nav").classList.add("hidden");
 $("payment-accounts-nav").classList.add("hidden");
 setupAdminSubmenu();
 const invoiceNav=document.querySelector(
  '.sidebar button[data-page="invoices"]'
 );
 if(invoiceNav){
  invoiceNav.textContent=
   activeTenant?.tenant_type==="vermieter"
    ? "NK-Abrechnungen" : "Rechnungen";
 }
 const selector=$("tenant-selector");
 if(selector)selector.closest(".tenant-selector-wrap")?.classList.toggle(
  "hidden",state.tenants.length===0
 );
}
$("login-form").onsubmit=async e=>{
 e.preventDefault();$("login-error").textContent="";
 try{
  const data=await api("/api/auth/login",{method:"POST",body:JSON.stringify({username:$("username").value,password:$("password").value})});
  state.user=data.user;$("password").value="";
  state.tenantId=null;
  await loadTenants();
  showApp();
  if(state.user?.role==="system_admin")await navigate("systemAdministration");
  else if(state.tenantId)await navigate("dashboard");
  else $("content").innerHTML='<div class="panel">Keine Mandantenzuordnung vorhanden.</div>';
 }catch(err){$("login-error").textContent=err.message;}
};
$("logout").onclick=async()=>{
 try{await api("/api/auth/logout",{method:"POST"});}catch{}
 state.user=null;state.tenantId=null;state.tenantRole=null;state.tenants=[];
 showLogin();
};
$("tenant-selector").onchange=async e=>{
 const id=Number(e.target.value);
 const tenant=state.tenants.find(t=>Number(t.id)===id);
 if(!tenant)return;
 state.tenantId=id;
 state.tenantRole=tenant.role;
 try{
  localStorage.setItem(
   "buha.selectedTenant."+
   String(state.user?.id??state.user?.username??"unknown"),
   String(id)
  );
 }catch{}
  updateRecurringVisibility();
 state.editing=null;
 showApp();
 await navigate("dashboard");
};
$("navigation").onclick=e=>{
 const b=e.target.closest("[data-page]");
 if(!b)return;
 if(b.dataset.adminSection){
  activeAdminSection=b.dataset.adminSection;
 }
 navigate(b.dataset.page);
};
async function navigate(page){
 if(state.user?.role==="system_admin"&&page!=="systemAdministration")
  page="systemAdministration";
 if(state.user?.role!=="system_admin"&&page==="systemAdministration")
  page="dashboard";

 const activeTenant=(state.tenants||[]).find(t=>
  Number(t.id)===Number(state.tenantId)
 );
 if(page==="recurringInvoices"&&
    activeTenant?.tenant_type==="vermieter"){
  page="invoices";
 }
 // BUHA_FINAL_NAV_354
 state.page=page;
 if(["administration","paymentAccounts","accounts"].includes(page)){
  const submenu=$("admin-submenu");
  const toggle=$("admin-menu-toggle");
  if(submenu)submenu.classList.remove("hidden");
  if(toggle)toggle.setAttribute("aria-expanded","true");
 }
 state.editing=null;$("page-title").textContent=(page==="invoices" && activeTenant?.tenant_type==="vermieter" ? "NK-Abrechnungen" : page==="recurringInvoices"?"Wiederkehrende Rechnungen":page==="paymentAccounts"?"Zahlungskonten":page==="systemAdministration"?"Systemadministration":titles[page]);
 document.querySelectorAll("[data-page]").forEach(b=>b.classList.toggle("active",b.dataset.page===page));
 $("notice").classList.add("hidden");$("content").innerHTML='<div class="panel">Lade Daten …</div>';
 try{await ({dashboard,partners:()=>master("partners"),accounts:()=>master("accounts"),
 products:()=>master("products"),invoices,bookings,recurringInvoices,journal,eur,administration,paymentAccounts,systemAdministration})[page]();}
 catch(e){$("content").innerHTML='<div class="panel"></div>';notify(e.message,true);}
}
function table(headers,rows){
 return '<div class="table-wrap"><table><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join("")+
 '</tr></thead><tbody>'+rows.join("")+'</tbody></table></div>';
}
function field(name,label,type="text",value="",options=null){
 const control=options?'<select name="'+name+'">'+options.map(o=>'<option value="'+esc(o[0])+'"'+(String(o[0])===String(value)?" selected":"")+'>'+esc(o[1])+'</option>').join("")+'</select>':
 type==="textarea"?'<textarea name="'+name+'">'+esc(value)+'</textarea>':
 '<input name="'+name+'" type="'+type+'" value="'+esc(value)+'"'+(type==="number"?' step="any"':"")+'>';
 return '<label>'+esc(label)+control+'</label>';
}
const schemas={
 partners:[["partner_number","Nummer"],["name","Name"],["is_customer","Kunde","select",null,[["true","Ja"],["false","Nein"]]],
 ["is_supplier","Lieferant","select",null,[["false","Nein"],["true","Ja"]]],["street","Straße"],["postal_code","PLZ"],
 ["city","Ort"],["country","Land (ISO)"],["email","E-Mail"],["phone","Telefon"],["vat_id","USt-ID"],
  ["xrechnung_endpoint","XRechnung: Elektronische Adresse"],
  ["xrechnung_endpoint_scheme","XRechnung: Adressschema (z. B. EM)"],
  ["xrechnung_buyer_reference","XRechnung: Käuferreferenz / Leitweg-ID"],
  ["notes","Notizen","textarea"]],
 accounts:[["number","Kontonummer"],["name","Bezeichnung"],["account_type","Kontoart","select",null,
 [["income","Einnahme"],["expense","Ausgabe"],["asset","Aktiva"],["liability","Passiva"],["equity","Eigenkapital"]]],

  ["default_vat_rate","Standardsteuersatz (%)","number"],
  ["tax_treatment","Steuerbehandlung","select",null,
   [["none","Keine Steuer"],
    ["output_vat","Umsatzsteuer"],
    ["input_vat","Vorsteuer"]]],
  ["input_vat_deductible_percent","Vorsteuerabzug (%)","number"],
  ["description","Beschreibung","textarea"]],
 products:[["sku","Artikelnummer"],["name","Bezeichnung"],["description","Beschreibung","textarea"],
 ["product_type","Typ","select",null,[["service","Dienstleistung"],["product","Produkt"]]],
 ["unit","Einheit"],["net_price","Nettopreis","number"],
 ["revenue_account_id","Buchungskonto","select",null,[]]]
};
async function master(kind){
 if(kind==="products"){
  state.productAccounts=await api("/api/accounts");
 }

 const rows=await api("/api/"+kind);
 state.rows=rows;
 const columns={
  partners:["partner_number","name","city","email"],
  accounts:["number","name","account_type"],
  products:["sku","name","net_price","revenue_account_id"]
 }[kind];
 const labels={
  partners:["Nummer","Name","Ort","E-Mail"],
  accounts:["Nummer","Bezeichnung","Art"],
  products:["Artikel","Bezeichnung","Netto","Buchungskonto"]
 }[kind];
 const body=rows.map(r=>'<tr>'+
  columns.map(k=>'<td>'+esc(r[k])+'</td>').join("")+
  '<td class="actions"><button class="small secondary" data-edit="'+r.id+'">Bearbeiten</button></td></tr>');
 $("content").innerHTML=
  '<div class="toolbar"><button id="new-entry">+ Neu anlegen</button>'+
  '<span class="muted">'+rows.length+' Einträge</span></div>'+
  '<div id="editor"></div>'+
  '<div class="panel">'+table([...labels,"Aktion"],body)+'</div>';
 $("new-entry").onclick=()=>{
  editMaster(kind,null);
  $("editor").scrollIntoView({behavior:"smooth",block:"start"});
 };
 document.querySelectorAll("[data-edit]").forEach(b=>{
  b.onclick=()=>{
   editMaster(kind,rows.find(r=>r.id===Number(b.dataset.edit)));
   $("editor").scrollIntoView({behavior:"smooth",block:"start"});
  };
 });
}

function editMaster(kind,item){
 const fields=schemas[kind].map(([name,label,type,_,options])=>{
  if(kind==="products"&&name==="revenue_account_id"){
   options=[
    ["","Kein Buchungskonto"],
    ...(state.productAccounts||[])
     .filter(a=>["income","expense"].includes(a.account_type)&&a.is_active!==false)
     .map(a=>[a.id,a.number+" – "+a.name])
   ];
  }

  const defaults={country:"DE",unit:"Stueck",vat_rate:"19",net_price:"0",is_customer:"true",is_supplier:"false",
    default_vat_rate:"0",
    tax_treatment:"none",
    input_vat_deductible_percent:"100"};
  return field(name,label,type||"text",item?.[name]??defaults[name]??"",options);
 }).join("");
 $("editor").innerHTML='<div class="panel"><h2>'+(item?"Eintrag bearbeiten":"Neuer Eintrag")+
 '</h2><form id="master-form"><div class="grid-form">'+fields+'</div><div class="form-actions"><button>Speichern</button>'+
 '<button type="button" class="secondary" id="cancel-edit">Abbrechen</button></div></form></div>';
 $("cancel-edit").onclick=()=>$("editor").innerHTML="";
 $("master-form").onsubmit=async e=>{
  e.preventDefault();
  const data=Object.fromEntries(new FormData(e.target));
  for(const key of ["is_customer","is_supplier"])if(key in data)data[key]=data[key]==="true";
  if(kind==="products"){
   delete data.vat_rate;
   if(!data.revenue_account_id)data.revenue_account_id=null;
   else data.revenue_account_id=Number(data.revenue_account_id);
  }
  try{await api("/api/"+kind+(item?"/"+item.id:""),{method:item?"PUT":"POST",body:JSON.stringify(data)});
   await master(kind);notify("Eintrag gespeichert.");
  }catch(err){notify(err.message,true);}
 };
}
async function bookings(){
 const [bookingsData,paymentAccountsData,accountsData]=
  await Promise.all([
   api("/api/manual-bookings"),
   api("/api/payment-accounts"),
   api("/api/accounts")
  ]);

 if(!Array.isArray(bookingsData)||
    !Array.isArray(paymentAccountsData)||
    !Array.isArray(accountsData)){
  throw new Error("Ungueltige Antwort der Buchungs-API.");
 }

 const paymentAccounts=paymentAccountsData.filter(a=>
  a.is_active===true
 );

 const accounts=accountsData.filter(a=>
  a.is_active===true&&
  ["income","expense"].includes(a.account_type)
 );

 const canCreate=state.tenantRole==="admin";

 const paymentNames=new Map(
  paymentAccountsData.map(a=>[Number(a.id),a.name])
 );

 const accountNames=new Map(
  accountsData.map(a=>[
   Number(a.id),
   String(a.number)+" - "+String(a.name)
  ])
 );

 const rows=bookingsData.map(b=>{
  const type=b.booking_type==="income"?"Einnahme":"Ausgabe";
  return '<tr>'+
   '<td>'+esc(b.booking_number)+'</td>'+
   '<td>'+esc(b.booking_date)+'</td>'+
   '<td>'+esc(type)+'</td>'+
   '<td>'+esc(euro(b.amount))+'</td>'+
   '<td>'+esc(paymentNames.get(Number(b.payment_account_id))||
    ("Konto "+b.payment_account_id))+'</td>'+
   '<td>'+esc(accountNames.get(Number(b.account_id))||
    ("Konto "+b.account_id))+'</td>'+
   '</tr>';
 });

 const paymentOptions=paymentAccounts.map(a=>[
  String(a.id),a.name
 ]);

 const defaultPayment=paymentAccounts.find(a=>
  a.is_default===true
 )||paymentAccounts[0];

 const canSubmit=paymentAccounts.length>0&&accounts.length>0;

 $("content").innerHTML=
  (canCreate?
   '<div class="panel"><h2>Neue Buchung</h2>'+
   '<form id="manual-booking-form">'+
   '<div class="grid-form">'+
   field("booking_type","Buchungsart","select","income",[
    ["income","Einnahme"],
    ["expense","Ausgabe"]
   ])+
   field("booking_date","Buchungsdatum","date",today())+
   field("amount","Betrag (EUR)","number","")+
   field("payment_account_id","Zahlungskonto","select",
    defaultPayment?String(defaultPayment.id):"",paymentOptions)+
   '<label>Buchungskonto<select name="account_id" '+
   'id="manual-booking-account"></select></label>'+
   '</div>'+
   (!canSubmit?
    '<p class="muted">Für neue Buchungen werden ein aktives '+
    'Zahlungskonto und ein aktives Einnahmen- oder '+
    'Ausgabenkonto benötigt.</p>':'')+
   '<div class="form-actions"><button type="submit"'+
   (!canSubmit?' disabled':'')+
   '>Buchung speichern</button></div>'+
   '</form></div>':'')+
  '<div class="panel"><h2>Gespeicherte Buchungen</h2>'+
  '<p class="muted">'+bookingsData.length+' Buchungen</p>'+
  table(
   ["Nummer","Datum","Art","Betrag","Zahlungskonto",
    "Buchungskonto"],
   rows
  )+
  '</div>';

 if(!canCreate)return;

 const form=$("manual-booking-form");
 const typeField=form.elements.namedItem("booking_type");
 const accountField=$("manual-booking-account");

 function updateBookingAccounts(){
  const expected=typeField.value;
  const available=accounts.filter(a=>
   a.account_type===expected
  );

  accountField.innerHTML=available.map(a=>
   '<option value="'+Number(a.id)+'">'+
   esc(a.number+" - "+a.name)+'</option>'
  ).join("");

  accountField.disabled=available.length===0;
  form.querySelector('button[type="submit"]').disabled=
   !canSubmit||available.length===0;
 }

 typeField.onchange=updateBookingAccounts;
 updateBookingAccounts();

 form.onsubmit=async event=>{
  event.preventDefault();

  const button=form.querySelector('button[type="submit"]');

  try{
   const data=Object.fromEntries(new FormData(form));
   const amount=Number(data.amount);
   const paymentId=Number(data.payment_account_id);
   const accountId=Number(data.account_id);

   if(!Number.isFinite(amount)||amount<=0){
    throw new Error("Bitte einen positiven Betrag eingeben.");
   }

   if(!/^\d{4}-\d{2}-\d{2}$/.test(data.booking_date)){
    throw new Error("Bitte ein gueltiges Buchungsdatum eingeben.");
   }

   if(!paymentAccounts.some(a=>Number(a.id)===paymentId)){
    throw new Error("Bitte ein gueltiges Zahlungskonto auswaehlen.");
   }

   if(!accounts.some(a=>
    Number(a.id)===accountId&&
    a.account_type===data.booking_type
   )){
    throw new Error("Bitte ein passendes Buchungskonto auswaehlen.");
   }

   data.payment_account_id=paymentId;
   data.account_id=accountId;
   data.amount=amount;

   button.disabled=true;

   const saved=await api("/api/manual-bookings",{
    method:"POST",
    body:JSON.stringify(data)
   });

   await bookings();
   notify("Buchung "+saved.booking_number+" gespeichert.");

  }catch(err){
   notify(err.message,true);
   button.disabled=false;
  }
 };
}

async function dashboard(){
 const isLandlord=state.tenants.find(t=>Number(t.id)===Number(state.tenantId))?.tenant_type==="vermieter";
 const now=new Date();
 const year=now.getFullYear();
 const month=now.getMonth()+1;

 const [partners,products,invoices,journalData]=await Promise.all([
  api("/api/partners"),
  api("/api/products"),
  api("/api/invoices"),
  api("/api/accounting/journal?year="+year+"&month="+month)
 ]);

 const outstanding=invoices.filter(i=>
  ["open","partial"].includes(i.status)&&
  Number(i.open_total)>0
 );

 const openAmount=outstanding.reduce(
  (sum,i)=>sum+Number(i.open_total||0),0
 );

 const customers=partners.filter(p=>p.is_customer===true).length;
 const suppliers=partners.filter(p=>p.is_supplier===true).length;

 const bankBalance=journalData.bank_closing_balance;
 const bankAvailable=bankBalance!==null&&bankBalance!==undefined;

 const partnerMap=new Map(partners.map(p=>[Number(p.id),p]));

 const invoiceRows=invoices.filter(i=>
  i.status==="draft"||
  (["open","partial"].includes(i.status)&&
   (Number(i.open_total)!==0||i.utility_period_from!=null))
 );

 const statusNames={
  draft:"Entwurf",
  open:"Offen",
  partial:"Teilbezahlt"
 };

 const typeNames={
  outgoing:"Ausgang",
  incoming:"Eingang"
 };

 const topCustomerMap=new Map();

 for(const invoice of invoices){
  if(invoice.invoice_type!=="outgoing")continue;
  if(["draft","cancelled"].includes(invoice.status))continue;

  const partner=partnerMap.get(Number(invoice.partner_id));
  if(!partner)continue;

  const key=Number(invoice.partner_id);
  const previous=topCustomerMap.get(key)||{
   name:partner.name,
   amount:0
  };

  previous.amount+=Number(invoice.gross_total||0);
  topCustomerMap.set(key,previous);
 }

 const topCustomers=Array.from(topCustomerMap.values())
  .sort((a,b)=>b.amount-a.amount)
  .slice(0,5);

 const maxRevenue=Math.max(
  0,...topCustomers.map(customer=>customer.amount)
 );

 const metric=(label,value,note="")=>
  '<div class="card">'+
   '<div class="muted">'+esc(label)+'</div>'+
   '<div class="metric">'+esc(value)+'</div>'+
   (note?'<div class="muted dashboard-metric-note">'+
    esc(note)+'</div>':"")+
  '</div>';

 const invoiceTable=table(
  ["Nummer","Datum","Art","Kunde / Lieferant",
   "Status","Brutto","Offen"],
  invoiceRows.map(i=>{
   const partner=partnerMap.get(Number(i.partner_id));

   return '<tr>'+
    '<td><button type="button" '+
     'class="dashboard-invoice-link" '+
     'data-dashboard-invoice="'+Number(i.id)+'">'+
     esc(i.invoice_number)+'</button></td>'+
    '<td>'+esc(i.invoice_date)+'</td>'+
    '<td>'+esc(typeNames[i.invoice_type]||i.invoice_type)+'</td>'+
    '<td>'+esc(partner?.name||"Nicht zugeordnet")+'</td>'+
    '<td><span class="pill">'+
     esc(statusNames[i.status]||i.status)+'</span></td>'+
    '<td>'+euro(i.gross_total)+'</td>'+
    '<td>'+euro(i.open_total)+'</td>'+
   '</tr>';
  })
 );

 const topChart=topCustomers.length
  ?'<div class="dashboard-top5-v440">'+
   topCustomers.map((customer,index)=>{
    const width=maxRevenue>0
     ?Math.max(0,customer.amount/maxRevenue*100)
     :0;

    return '<div class="dashboard-top5-item">'+
     '<div class="dashboard-top5-header">'+
      '<div class="dashboard-top5-customer">'+
       '<span class="dashboard-top5-position">'+(index+1)+'.</span>'+
       '<span>'+esc(customer.name)+'</span>'+
      '</div>'+
      '<div class="dashboard-top5-amount">'+
       euro(customer.amount)+
      '</div>'+
     '</div>'+
     '<div class="dashboard-top5-track">'+
      '<div class="dashboard-top5-fill" style="width:'+
       width.toFixed(2)+'%"></div>'+
     '</div>'+
    '</div>';
   }).join("")+
   '</div>'
  :'<p class="muted">Noch keine freigegebenen Ausgangsrechnungen vorhanden.</p>';

 $("content").innerHTML=
  '<div class="cards dashboard-three-cards">'+
   metric(isLandlord?"Offene NK-Rechnungen (unbezahlt)":"Offene Rechnungen (unbezahlt)",outstanding.length)+
   metric(isLandlord?"Offener NK-Rechnungsbetrag":"Offener Rechnungsbetrag",euro(openAmount))+
   metric(
    "Gesamtbestand aller Zahlungskonten",
    bankAvailable?euro(bankBalance):"–",
    "Summe aller Zahlungskonten"
   )+
  '</div>'+
  // BUHA_ACCOUNT_BALANCE_DISPLAY_349
  '<div class="panel"><h2>Einzelne Zahlungskonten</h2>'+
  paymentAccountBalanceCards(journalData.payment_accounts)+
  '</div>'+

  '<div class="panel">'+
   '<h2>'+(isLandlord?"Offene NK-Rechnungen und Entwürfe":"Offene Rechnungen und Entwürfe")+"</h2>"+
   (invoiceRows.length
    ?invoiceTable
    :'<p class="muted">Keine offenen Rechnungen oder Entwürfe.</p>')+
  '</div>'+

  (isLandlord?'':
  '<div class="panel dashboard-top5">'+
   '<h2>TOP 5 Kunden – Umsatz</h2>'+
   '<p class="muted">Bruttoumsatz aus freigegebenen Ausgangsrechnungen, gesamt</p>'+
   topChart+
  '</div>')+

  '<div class="cards dashboard-three-cards">'+
   metric(isLandlord?"Mieter gesamt":"Kunden gesamt",customers)+
   (isLandlord?'':
    metric("Lieferanten gesamt",suppliers)+
    metric("Produkte & Leistungen",products.length))+
  '</div>';

 document.querySelectorAll("[data-dashboard-invoice]")
  .forEach(button=>{
   button.onclick=async()=>{
    const invoiceId=Number(button.dataset.dashboardInvoice);

    try{
     await navigate("invoices");

     const detailButton=document.querySelector(
      '[data-invoice="'+invoiceId+'"]'
     );

     if(!detailButton){
      throw Error("Rechnung in der Rechnungsübersicht nicht gefunden.");
     }

     detailButton.click();

    }catch(error){
     notify(error.message,true);
    }
   };
  });
}

// BUHA_LANDLORD_LABELS_341
async function invoices(){
 // BUHA_INVOICE_TENANT_FIX_360
 const activeTenant=(state.tenants||[]).find(t=>
  Number(t.id)===Number(state.tenantId)
 );
 const [rows,partners]=await Promise.all([
  api("/api/invoices"),api("/api/partners")
 ]);
 state.rows=rows;
 const partnerMap=new Map(partners.map(p=>[p.id,p]));
 const typeLabel=t=>t==="outgoing"?"Ausgang":"Eingang";
 const statusLabel=s=>({
  draft:"Entwurf",open:"Offen",partial:"Teilbezahlt",
  paid:"Bezahlt",cancelled:"Storniert"
 })[s]||s;

 const body=rows.map(i=>{
  const p=partnerMap.get(i.partner_id);
  const payments=i.payments||[];
  const paymentDates=payments
   .map(x=>x.payment_date).filter(Boolean).sort();
  const paidAt=paymentDates.length
   ?paymentDates[paymentDates.length-1]:"–";
  return '<tr>'+
   '<td>'+esc(i.invoice_number)+'</td>'+
   '<td>'+esc(i.invoice_date)+'</td>'+
   '<td>'+esc(typeLabel(i.invoice_type))+'</td>'+
   '<td>'+esc(p?.name||"Nicht zugeordnet")+'</td>'+
   '<td><span class="pill">'+esc(statusLabel(i.status))+'</span></td>'+
   '<td>'+euro(i.gross_total)+'</td>'+
   '<td>'+euro(i.paid_total)+'</td>'+
   '<td>'+euro(i.open_total)+'</td>'+
   '<td>'+esc(paidAt)+'</td>'+
   '<td><button class="small secondary" data-invoice="'+i.id+'">Öffnen</button>'+
    (i.status==="draft"?' <button class="small secondary" data-edit-invoice="'+i.id+'">Entwurf bearbeiten</button>':'')+
    '</td>'+
   '</tr>';
 });

 const isUtilityTenant=activeTenant?.tenant_type==="vermieter";

 $("content").innerHTML=
  '<div class="toolbar"><button id="new-invoice">'+
  (isUtilityTenant?'+ NK-Abrechnung erstellen':'+ Rechnung erfassen')+
  '</button>'+
  (isUtilityTenant?'':'<button type="button" class="secondary" id="import-xrechnung">XRechnung importieren</button>')+
  '<span class="muted">'+rows.length+
  (isUtilityTenant?' NK-Abrechnungen':' Rechnungen')+
  '</span></div>'+
  '<div id="invoice-editor"></div>'+
  '<div class="panel">'+
  table(isUtilityTenant
   ?["NK-Nummer","Datum","Art","Mieter","Status",
     "Mieteranteil","Bezahlt","Offen","Letzte Zahlung","Aktion"]
   :["Nummer","Datum","Art","Kunde / Lieferant","Status",
     "Brutto","Bezahlt","Offen","Letzte Zahlung","Aktion"],body)+
  '</div>';

 $("new-invoice").onclick=()=>{
  newInvoice(partners);
  $("invoice-editor").scrollIntoView({behavior:"smooth",block:"start"});
 };


  if($("import-xrechnung"))$("import-xrechnung").onclick=async()=>{
    try {
      await showXRechnungImport(partners);
      $("invoice-editor").scrollIntoView({
        behavior:"smooth",
        block:"start"
      });
    } catch(err) {
      notify(err.message,true);
    }
  };

  document.querySelectorAll("[data-edit-invoice]").forEach(b=>{
  b.onclick=async()=>{
   const item=rows.find(i=>i.id===Number(b.dataset.editInvoice));
   if(!item||item.status!=="draft")return;
   await newInvoice(partners,item);
   $("invoice-editor").scrollIntoView({behavior:"smooth",block:"start"});
  };
 });
 document.querySelectorAll("[data-invoice]").forEach(b=>{
  b.onclick=()=>{
   const item=rows.find(i=>i.id===Number(b.dataset.invoice));
   invoiceDetail(item,partnerMap.get(item.partner_id));
   $("invoice-editor").scrollIntoView({behavior:"smooth",block:"start"});
  };
 });
}

async function newInvoice(partners,existing=null){
  const activeTenant=state.tenants.find(t=>
   Number(t.id)===Number(state.tenantId)
  );
  const isUtilityTenant=activeTenant?.tenant_type==="vermieter";
 const editor=$("invoice-editor");
  const invoiceList=editor.nextElementSibling;
  if(invoiceList && invoiceList.classList.contains("panel")){
    invoiceList.hidden=true;
  }
 editor.innerHTML='<div class="panel">Rechnungsformular wird geladen …</div>';

 let products,accounts;
 try{
  [products,accounts]=await Promise.all([
   api("/api/products"),
   api("/api/accounts")
  ]);
 }catch(err){
  editor.innerHTML='<div class="panel">'+esc(err.message)+'</div>';
  return;
 }

 const partnerOptions=partners.filter(p=>p.is_active!==false);
 const existingProductIds=new Set(
  (existing?.lines||[]).map(line=>Number(line.product_id))
 );
 const productOptions=products.filter(p=>
  p.is_active!==false||existingProductIds.has(p.id)
 );
 const existingAccountIds=new Set(
  (existing?.lines||[]).map(line=>Number(line.account_id))
 );
 const accountOptions=accounts.filter(a=>
  a.is_active!==false||existingAccountIds.has(a.id)
 );

 editor.innerHTML=`
 <div class="panel">
  <h2>${isUtilityTenant?(existing?'NK-Abrechnung bearbeiten':'Neue NK-Abrechnung'):(existing?'Rechnungsentwurf bearbeiten':'Neue Rechnung')}</h2>
  <form id="invoice-form">
   <div class="grid-form">
    <div class="readonly-number">
  <span>Rechnungsnummer</span>
  <strong>Automatisch bei Freigabe</strong>
</div>
    ${field("invoice_type","Rechnungsart","select","outgoing",
      [["outgoing","Ausgangsrechnung"],["incoming","Eingangsrechnung"]])}
    ${field("partner_id","Kunde / Lieferant","select","",
      partnerOptions.map(p=>[p.id,p.name]))}
    ${field("invoice_date","Rechnungsdatum","date",today())}
    ${field("due_date","Fälligkeit","date","")}
    ${field("notes","Notizen","textarea")}
     <div id="utility-options" style="grid-column:1/-1" hidden>
      <h3>Nebenkostenabrechnung</h3>
      <div class="grid-form">
       ${field("utility_period_from","Abrechnungszeitraum von","date","")}
       ${field("utility_period_to","Abrechnungszeitraum bis","date","")}
       ${field("utility_prepayments","Vorauszahlungen (€)","number","0")}
        ${field("utility_account_id","NK-Buchungskonto","select","",
          accounts.filter(a=>
           a.account_type==="income" &&
           a.is_active===true
          ).map(a=>[
           String(a.id),
           String(a.number)+" - "+String(a.name)
          ]))}
      </div>
      <div id="utility-result">
       <p>Mieteranteil: <strong id="utility-tenant-total">0,00 €</strong></p>
       <p>Vorauszahlungen: <strong id="utility-advance-total">0,00 €</strong></p>
       <p>Nachzahlung / Guthaben:
        <strong id="utility-balance">0,00 €</strong>
       </p>
      </div>
     </div>
    <div id="xrechnung-options" style="grid-column:1/-1">
     <label style="display:inline-flex;align-items:center;justify-content:flex-start;gap:8px;width:auto">
       <input type="checkbox" name="xrechnung_enabled"
        style="width:16px;height:16px;margin:0;flex:none">
       <span>XRechnung zusätzlich als XML-Anhang versenden</span>
      </label>
     ${field("xrechnung_buyer_reference","Käuferreferenz / Leitweg-ID")}
   </div>
    </div>

    <h2 class="invoice-section-title">Rechnungspositionen</h2>
   <div class="table-wrap">
    <table class="invoice-lines">
     <thead>
      <tr>
       <th>Artikel / Leistung</th>
       <th>Beschreibung</th>
       <th>Menge</th>
       <th>Einheit</th>
       <th>Einzelpreis netto</th>
       <th>Rabattart</th><th>Rabatt</th><th>USt %</th>
       <th>Buchungskonto</th>
        ${isUtilityTenant
         ?'<th>Umlage: Kosten / Schlüssel</th>'
         :''}
       <th>Netto</th>
       <th>Brutto</th>
       <th></th>
      </tr>
     </thead>
     <tbody id="invoice-line-body"></tbody>
    </table>
   </div>

   <div class="toolbar invoice-line-toolbar">
    <button type="button" id="add-invoice-line" class="secondary">
     + Position hinzufügen
    </button>
   </div>

   <div class="invoice-totals">
    <div><span>Netto</span><strong id="invoice-net">0,00 €</strong></div>
    <div><span>Umsatzsteuer</span><strong id="invoice-vat">0,00 €</strong></div>
    <div class="invoice-total">
     <span>Gesamtbetrag brutto</span>
     <strong id="invoice-gross">0,00 €</strong>
    </div>
   </div>

   <div id="invoice-form-attachments">
    <h2 class="invoice-section-title">Rechnungsanhänge</h2>
    <p class="muted">Zusätzliche PDF-Dokumente zur Ausgangsrechnung.
    Maximal 20 Dateien, 10 MB je Datei und 20 MB insgesamt.</p>
    <input type="file" id="invoice-form-attachment-files"
     accept=".pdf,application/pdf" multiple>
    <div id="invoice-form-attachment-selected"></div>
    <div id="invoice-form-existing-attachments"></div>
   </div>


   <div class="form-actions">
    <button type="submit">Entwurf speichern</button>
     <button type="button" id="save-finalize-invoice">Rechnung freigeben</button>
    <button type="button" class="secondary" id="cancel-invoice">
     Abbrechen
    </button>
   </div>
  </form>
 </div>`;

 const form=$("invoice-form");
  if(isUtilityTenant){
   $("utility-options").hidden=false;
   editor.querySelector("h2").textContent=existing
    ?"Nebenkostenabrechnung bearbeiten"
    :"Neue Nebenkostenabrechnung";
   form.elements.invoice_type.value="outgoing";
   form.elements.invoice_type.disabled=true;
  }

 if(isUtilityTenant){
   const renameField=(name,label)=>{
    const element=form.elements[name];
    const wrapper=element?.closest("label");
    if(wrapper){
     const textNode=Array.from(wrapper.childNodes)
      .find(node=>node.nodeType===Node.TEXT_NODE);
     if(textNode)textNode.textContent=label;
    }
   };

   const hideField=name=>{
    const element=form.elements[name];
    const wrapper=element?.closest("label");
    if(wrapper)wrapper.hidden=true;
   };

   hideField("invoice_type");
   $("xrechnung-options").hidden=true;

   renameField("partner_id","Mieter");
   renameField("invoice_date","Abrechnungsdatum");

   const numberLabel=editor.querySelector(".readonly-number span");
   if(numberLabel)numberLabel.textContent="NK-Abrechnungsnummer";

   editor.querySelectorAll(".invoice-section-title").forEach(heading=>{
    if(heading.textContent==="Rechnungspositionen")
     heading.textContent="Umlagefähige Nebenkosten";
    if(heading.textContent==="Rechnungsanhänge")
     heading.textContent="Belege zur Nebenkostenabrechnung";
   });

   const attachmentInfo=$("invoice-form-attachments")
    ?.querySelector("p.muted");
   if(attachmentInfo)
    attachmentInfo.textContent=
     "Zusätzliche PDF-Belege zur Nebenkostenabrechnung. "+
     "Maximal 20 Dateien, 10 MB je Datei und 20 MB insgesamt.";

   $("save-finalize-invoice").textContent="NK-Abrechnung freigeben";
   $("add-invoice-line").textContent="+ Nebenkostenposition hinzufügen";
  }

  if(isUtilityTenant){
   const standardTotals=editor.querySelector(".invoice-totals");
   if(standardTotals)standardTotals.hidden=true;
  }

  const attachmentInput=$("invoice-form-attachment-files");
 const attachmentSelected=$("invoice-form-attachment-selected");
 const existingAttachments=$("invoice-form-existing-attachments");

 attachmentInput.onchange=()=>{
  const files=Array.from(attachmentInput.files||[]);
  attachmentSelected.textContent=files.length
   ?files.map(file=>file.name).join(", ")
   :"";
 };

 if(existing){
  form.elements.invoice_type.value=existing.invoice_type;
  form.elements.invoice_type.disabled=true;
  form.elements.partner_id.value=String(existing.partner_id);
  form.elements.invoice_date.value=existing.invoice_date||"";
  form.elements.due_date.value=existing.due_date||"";
  form.elements.notes.value=existing.notes||"";
   form.elements.xrechnung_enabled.checked=
    existing.xrechnung_enabled===true;
   form.elements.xrechnung_buyer_reference.value=
    existing.xrechnung_buyer_reference||"";
 }

 if(existing && isUtilityTenant){
   form.elements.utility_period_from.value=
    existing.utility_period_from||"";
   form.elements.utility_period_to.value=
    existing.utility_period_to||"";
   form.elements.utility_prepayments.value=
    existing.utility_prepayments??"0";
   form.elements.utility_account_id.value=
    existing.utility_account_id==null
     ?""
     :String(existing.utility_account_id);
  }

  const body=$("invoice-line-body");

 const optionHtml=(items,selected="",emptyLabel="Bitte wählen")=>
  '<option value="">'+esc(emptyLabel)+'</option>'+
  items.map(([value,label])=>
   '<option value="'+esc(value)+'"'+
   (String(value)===String(selected)?' selected':'')+'>'+
   esc(label)+'</option>'
  ).join("");

 const numberValue=value=>{
  const parsed=Number(String(value||"0").replace(",","."));
  return Number.isFinite(parsed)?parsed:0;
 };

 const cents=value=>Math.round((value+Number.EPSILON)*100)/100;

 function applyAccountTax(row){
  const accountId=Number(
   row.querySelector(".line-account").value
  );
  const account=accountOptions.find(a=>a.id===accountId);
  if(!account)return;

  const rate=Number(account.default_vat_rate);
  if(!Number.isFinite(rate)||rate<0||rate>100)return;

  row.querySelector(".line-vat").value=String(rate);
  calculate();
 }

 if(isUtilityTenant){
   const headers=Array.from(
    editor.querySelectorAll(".invoice-lines thead th")
   );

   if(headers.length!==13){
    throw new Error("NK-Tabellenstruktur unerwartet: "+headers.length);
   }

   headers[0].textContent="Nebenkostenposition";
   headers[2].textContent="Menge";
   headers[9].textContent="Gesamtkosten / Umlageschlüssel";
   headers[10].textContent="Mieteranteil";

   [2,3,4,5,6,7,8,11].forEach(index=>{
    headers[index].style.display="none";
   });
  }

  function addLine(initial={}){
  const row=document.createElement("tr");
  row.innerHTML=`
   <td>
    <select class="line-product">
     ${optionHtml(productOptions.map(p=>[
       p.id,(p.sku?p.sku+" – ":"")+p.name
     ]),initial.product_id??"","Freie Position")}
    </select>
   </td>
   <td>
    <input class="line-description" required
     value="${esc(initial.description||"")}">
   </td>
   <td>
    <input class="line-quantity" type="number" min="0.001"
     step="0.001" value="${esc(initial.quantity||"1")}" required>
   </td>
   <td>
    <input class="line-unit"
     value="${esc(initial.unit||"Stueck")}">
   </td>
   <td>
    <input class="line-price" type="number" min="0"
     step="0.0001" value="${esc(initial.unit_net_price||"0")}"
     required>
   </td>
   <td>
    <select class="line-discount-type">
     <option value="none">Kein Rabatt</option>
     <option value="percent">Prozent (%)</option>
     <option value="fixed">Festbetrag (€)</option>
    </select>
   </td>
   <td>
    <input class="line-discount-value" type="number"
     min="0" step="0.01"
     value="${esc(initial.discount_value??"0")}">
   </td>
   <td>
    <input class="line-vat" type="number" min="0" max="100"
     step="0.01" value="${esc(initial.vat_rate??"0")}" required>
   </td>
   <td>
    <select class="line-account"></select>
   </td>

    <td class="utility-line-fields" hidden>
     <label>Gesamtkosten (€)
      <input class="utility-total-cost" type="number"
       min="0" step="0.01"
       value="${esc(initial.utility_total_cost??"0")}">
     </label>
     <label>Gesamtschlüssel
      <input class="utility-total-key" type="number"
       min="0" step="any"
       value="${esc(initial.utility_total_key??"1")}">
     </label>
     <label>Mieterschlüssel
      <input class="utility-tenant-key" type="number"
       min="0" step="any"
       value="${esc(initial.utility_tenant_key??"1")}">
     </label>
    </td>
   <td class="line-net-result">0,00 €</td>
   <td class="line-gross-result">0,00 €</td>
   <td>
    <button type="button" class="small secondary line-remove">
     Entfernen
    </button>
   </td>`;

  body.appendChild(row);
   if(isUtilityTenant){
    const cells=Array.from(row.children);

    if(cells.length!==13){
     throw new Error("NK-Zellenstruktur unerwartet: "+cells.length);
    }

    [2,3,4,5,6,7,8,11].forEach(index=>{
     cells[index].style.display="none";
    });

    const utilityCell=cells[9];
    utilityCell.hidden=false;
    utilityCell.style.display="";
   }


   row.querySelectorAll(".utility-line-fields").forEach(cell=>{
    cell.hidden=!isUtilityTenant;
   });

   row.querySelector(".line-discount-type").value=
    initial.discount_type||"none";
   row.querySelector(".line-discount-type").addEventListener(
    "change",calculate
   );


  function updateAccounts(){
   const expected=form.elements.invoice_type.value==="outgoing"
    ?"income":"expense";

   const current=row.querySelector(".line-account").value||String(initial.account_id??"");

   row.querySelector(".line-account").innerHTML=optionHtml(
    accountOptions
     .filter(a=>a.account_type===expected)
     .map(a=>[a.id,a.number+" – "+a.name]),
    current,
    "Kein Konto"
   );
  }

  row.updateAccounts=updateAccounts;
  row.querySelector(".line-account").addEventListener("change",()=>applyAccountTax(row));
  updateAccounts();

  row.querySelector(".line-product").onchange=e=>{
   const product=productOptions.find(p=>p.id===Number(e.target.value));
   if(!product)return;

   row.querySelector(".line-description").value=product.name;
   row.querySelector(".line-unit").value=product.unit||"Stueck";
   row.querySelector(".line-price").value=product.net_price||"0";


   if(product.revenue_account_id){
    const productAccount=accountOptions.find(a=>
     a.id===Number(product.revenue_account_id));
    const expectedType=form.elements.invoice_type.value==="outgoing"
     ?"income":"expense";
    if(productAccount?.account_type===expectedType){
     row.querySelector(".line-account").value=
      String(product.revenue_account_id);
    }
   }

   if(row.querySelector(".line-account").value){
     applyAccountTax(row);
    }else{
     calculate();
    }
  };

  row.querySelector(".line-remove").onclick=()=>{
   if(body.children.length===1){
    notify("Mindestens eine Rechnungsposition ist erforderlich.",true);
    return;
   }
   row.remove();
   calculate();
  };

  row.querySelectorAll("input").forEach(input=>{
   input.addEventListener("input",calculate);
  });

  calculate();
 }

 function readLines(){
  return [...body.querySelectorAll("tr")].map(row=>{
   const get=selector=>row.querySelector(selector).value;
   const account=get(".line-account");
   const product=get(".line-product");

   return {
    description:get(".line-description").trim(),
    quantity:get(".line-quantity"),
    unit:get(".line-unit").trim()||"Stueck",
    unit_net_price:get(".line-price"),
    vat_rate:get(".line-vat"),
     discount_type:get(".line-discount-type"),
     discount_value:get(".line-discount-value"),
    account_id:account?Number(account):null,
    product_id:product?Number(product):null,
     ...(isUtilityTenant?{
      utility_total_cost:get(".utility-total-cost"),
      utility_total_key:get(".utility-total-key"),
      utility_tenant_key:get(".utility-tenant-key")
     }:{})
   };
  });
 }


  function calculateUtility(){
   if(!isUtilityTenant)return;

   let tenantTotal=0;

   body.querySelectorAll("tr").forEach(row=>{
    const totalCost=numberValue(
     row.querySelector(".utility-total-cost").value
    );
    const totalKey=numberValue(
     row.querySelector(".utility-total-key").value
    );
    const tenantKey=numberValue(
     row.querySelector(".utility-tenant-key").value
    );

    const valid=totalCost>=0&&totalKey>0&&
     tenantKey>=0&&tenantKey<=totalKey;

    const share=valid
     ?cents(totalCost*tenantKey/totalKey)
     :0;

    tenantTotal+=share;

    row.querySelector(".line-quantity").value="1";
    row.querySelector(".line-price").value=share.toFixed(2);
    row.querySelector(".line-discount-type").value="none";
    row.querySelector(".line-discount-value").value="0";
    row.querySelector(".line-vat").value="0";
   });

   tenantTotal=cents(tenantTotal);

   const advance=numberValue(
    form.elements.utility_prepayments.value
   );
   const difference=cents(tenantTotal-advance);

   $("utility-tenant-total").textContent=euro(tenantTotal);
   $("utility-advance-total").textContent=euro(advance);
   $("utility-balance").textContent=euro(Math.abs(difference));

   const label=$("utility-balance").parentElement;
   label.firstChild.textContent=difference>=0
    ?"Nachzahlung: "
    :"Guthaben: ";
  }

 function calculate(){
  calculateUtility();
  let totalNet=0;
  let totalVat=0;

  [...body.querySelectorAll("tr")].forEach(row=>{
   const quantity=numberValue(
    row.querySelector(".line-quantity").value
   );
   const price=numberValue(
    row.querySelector(".line-price").value
   );
   const rate=numberValue(
    row.querySelector(".line-vat").value
   );

   const baseNet=cents(quantity*price);
   const discountType=row.querySelector(
    ".line-discount-type"
   ).value;
   const discountValue=numberValue(
    row.querySelector(".line-discount-value").value
   );

   let discount=0;

   if(discountType==="percent"){
    discount=cents(baseNet*discountValue/100);
   }else if(discountType==="fixed"){
    discount=cents(discountValue);
   }

   const net=cents(baseNet-discount);
   const vat=cents(net*rate/100);

   totalNet+=net;
   totalVat+=vat;

   row.querySelector(".line-net-result").textContent=euro(net);
   row.querySelector(".line-gross-result").textContent=euro(net+vat);
  });

  $("invoice-net").textContent=euro(totalNet);
  $("invoice-vat").textContent=euro(totalVat);
  $("invoice-gross").textContent=euro(totalNet+totalVat);
 }

 form.elements.invoice_type.onchange=()=>{
  const type=form.elements.invoice_type.value;
   $("invoice-form-attachments").hidden=type!=="outgoing";
   $("xrechnung-options").hidden=isUtilityTenant||type!=="outgoing";
   form.elements.xrechnung_enabled.disabled=type!=="outgoing";
   form.elements.xrechnung_buyer_reference.disabled=
    type!=="outgoing";

  const allowed=partnerOptions.filter(p=>
   type==="outgoing"?p.is_customer:p.is_supplier
  );

  form.elements.partner_id.innerHTML=optionHtml(
   allowed.map(p=>[p.id,p.name]),"","Bitte wählen"
  );

  [...body.children].forEach(row=>{
    row.updateAccounts();
    if(row.querySelector(".line-account").value){
     applyAccountTax(row);
    }
   });
 };

 $("add-invoice-line").onclick=()=>addLine();

 $("cancel-invoice").onclick=()=>{
  editor.innerHTML="";
    if(invoiceList)invoiceList.hidden=false;
 };
 if(existing && existing.invoice_type==="outgoing"){
  const target=existingAttachments;

  async function refreshDraftAttachments(){
   const data=await api(
    "/api/invoices/"+existing.id+"/attachments"
   );

   if(!target.isConnected)return;

   const files=data.attachments||[];
   const locked=Boolean(data.locked);

   target.innerHTML=
    (files.length
     ?'<p class="muted">Gespeicherte Dokumente:</p>'+
      files.map(item=>
       '<div class="toolbar">'+
        '<span>'+esc(item.filename)+'</span>'+
        '<button type="button" class="small secondary" '+
         'data-attachment-open="'+item.id+'">Öffnen</button>'+
        (locked?"":'<button type="button" class="small secondary" '+
         'data-attachment-delete="'+item.id+'">Löschen</button>')+
       '</div>'
      ).join("")
     :'<p class="muted">Noch keine Anhänge gespeichert.</p>');

   attachmentInput.disabled=locked;

   target.querySelectorAll("[data-attachment-open]")
    .forEach(button=>{
     button.onclick=async()=>{
      try{
       await openInvoiceAttachment(
        existing.id,Number(button.dataset.attachmentOpen)
       );
      }catch(error){
       notify(error.message,true);
      }
     };
    });

   target.querySelectorAll("[data-attachment-delete]")
    .forEach(button=>{
     button.onclick=async()=>{
      if(!confirm("Dokument wirklich löschen?"))return;
      button.disabled=true;
      try{
       await invoiceAttachmentRequest(
        "/api/invoices/"+existing.id+"/attachments/"+
         Number(button.dataset.attachmentDelete),
        {method:"DELETE"}
       );
       await refreshDraftAttachments();
       notify("Dokument gelöscht.");
      }catch(error){
       notify(error.message,true);
       button.disabled=false;
      }
     };
    });
  }

  refreshDraftAttachments().catch(error=>{
   if(target.isConnected)target.textContent=error.message;
  });
 }

 async function uploadSelectedInvoiceAttachments(invoiceId){
  if(form.elements.invoice_type.value!=="outgoing")return;

  const files=Array.from(attachmentInput.files||[]);
  if(!files.length)return;

  const existingData=await api(
   "/api/invoices/"+invoiceId+"/attachments"
  );

  if(existingData.locked){
   throw Error("Rechnungsanhänge sind gesperrt.");
  }

  const already=existingData.attachments||[];

  if(already.length+files.length>20){
   throw Error("Maximal 20 PDF-Anhänge pro Rechnung.");
  }

  const total=files.reduce((sum,file)=>sum+file.size,0)+
   already.reduce((sum,item)=>sum+item.file_size,0);

  if(total>20*1024*1024){
   throw Error("Maximal 20 MB PDF-Anhänge insgesamt.");
  }

  for(const file of files){
   if(file.size>10*1024*1024){
    throw Error(file.name+": maximal 10 MB erlaubt.");
   }
   if(!file.name.toLowerCase().endsWith(".pdf")){
    throw Error(file.name+": nur PDF-Dateien erlaubt.");
   }
  }

  for(let index=0;index<files.length;index++){
   const file=files[index];
   const body=new FormData();
   body.append("file",file);

   await invoiceAttachmentRequest(
    "/api/invoices/"+invoiceId+"/attachments",
    {method:"POST",body}
   );

   // Nur noch nicht hochgeladene Dateien in der Auswahl halten.
   const remainingFiles=files.slice(index+1);
   const transfer=new DataTransfer();
   for(const remaining of remainingFiles){
    transfer.items.add(remaining);
   }
   attachmentInput.files=transfer.files;
   attachmentSelected.textContent=
    remainingFiles.map(item=>item.name).join(", ");
  }
 }

 let finalizeAfterSave=false;
 let invoiceSaving=false;
 let currentInvoiceId=existing?.id||null;

  $("save-finalize-invoice").onclick=()=>{
   if(invoiceSaving)return;
   finalizeAfterSave=true;
   form.requestSubmit();
  };

  form.onsubmit=async event=>{
   event.preventDefault();
   if(invoiceSaving)return;
   invoiceSaving=true;
   const shouldFinalize=finalizeAfterSave;
   finalizeAfterSave=false;

  event.preventDefault();

  const data=Object.fromEntries(new FormData(form));
  data.invoice_type=form.elements.invoice_type.value;
  data.partner_id=Number(data.partner_id);
  data.due_date=data.due_date||null;
   data.xrechnung_enabled=
    data.invoice_type==="outgoing"&&
    form.elements.xrechnung_enabled.checked;
   data.xrechnung_buyer_reference=
    data.invoice_type==="outgoing"
     ?(form.elements.xrechnung_buyer_reference.value.trim()||null)
     :null;
  data.lines=readLines();
   if(isUtilityTenant){
    data.utility_period_from=
     form.elements.utility_period_from.value||null;
    data.utility_period_to=
     form.elements.utility_period_to.value||null;
    data.utility_prepayments=
     form.elements.utility_prepayments.value;
     data.utility_account_id=Number(form.elements.utility_account_id.value);
   }else{
    delete data.utility_period_from;
    delete data.utility_period_to;
    delete data.utility_prepayments;
     delete data.utility_account_id;
   }

  delete data.invoice_number;

  if(!data.partner_id){
   invoiceSaving=false;
   notify("Bitte einen Kunden oder Lieferanten auswählen.",true);
   return;
  }

  if(data.lines.some(line=>
   !line.description||
   !(numberValue(line.quantity)>0)||
   numberValue(line.unit_net_price)<0||
   numberValue(line.vat_rate)<0||
   numberValue(line.vat_rate)>100
  )){
   invoiceSaving=false;
   notify("Bitte die Rechnungspositionen prüfen.",true);
   return;
  }

  let savedInvoiceId=existing?.id||null;

  try{
   const saved=await api(
     "/api/invoices"+(currentInvoiceId?"/"+currentInvoiceId:""),
     {
      method:currentInvoiceId?"PUT":"POST",
      body:JSON.stringify(data)
     }
    );
    const invoiceId=currentInvoiceId||saved?.id;
    if(!invoiceId){
     throw Error("Rechnung gespeichert, aber Rechnungs-ID fehlt.");
    }

    savedInvoiceId=invoiceId;
    currentInvoiceId=invoiceId;
    await uploadSelectedInvoiceAttachments(invoiceId);

    if(shouldFinalize){
     if(!invoiceId){
      throw Error("Entwurf gespeichert, aber Rechnungs-ID fehlt. Bitte Rechnungsübersicht prüfen.");
     }
     const finalizeResult=await api(
      "/api/invoices/"+invoiceId+"/finalize",
      {method:"POST"}
     );
     await invoices();
     const delivery=finalizeResult?.email_delivery;

     if(delivery?.status==="failed" || (
       delivery && delivery.status!=="disabled" &&
       delivery.ok===false
     )){
      notify(
       "Rechnung freigegeben, aber automatischer E-Mail-Versand "+
       "fehlgeschlagen: "+
       (delivery.error||"Bitte Versandstatus prüfen."),
       true
      );
     }else if(delivery?.ok===true){
      notify("Rechnung freigegeben und per E-Mail versendet.");
     }else{
      notify("Rechnung freigegeben.");
     }
    }else{
     await invoices();
     notify("Rechnungsentwurf gespeichert.");
    }
  }catch(err){
   notify(
    (savedInvoiceId
     ?"Rechnungsentwurf ID "+savedInvoiceId+
      ": Vorgang nicht vollständig abgeschlossen. "
     :"Rechnung konnte nicht gespeichert werden. ")+
    err.message,
    true
   );
  } finally {
    invoiceSaving=false;
   }
 };

 form.elements.invoice_type.dispatchEvent(new Event("change"));
    if (existing && existing.partner_id != null) {
      form.elements.partner_id.value = String(existing.partner_id);
    }

 if(existing&&Array.isArray(existing.lines)&&existing.lines.length){
  existing.lines.forEach(line=>addLine(line));
 }else{
  addLine();
 }
}

async function downloadInvoicePdf(invoiceId, invoiceNumber){
 try{
  const response=await fetch(
   `/api/invoices/${invoiceId}/pdf`,
   {credentials:"same-origin",cache:"no-store",headers:{"X-Tenant-ID":String(state.tenantId)}}
  );

  if(!response.ok){
   let message="PDF konnte nicht erstellt werden.";
   try{
    const error=await response.json();
    message=error.detail||message;
   }catch{}
   throw Error(message);
  }

  const blob=await response.blob();
  if(blob.type!=="application/pdf")
   throw Error("Ungueltiges PDF-Format.");

  const url=URL.createObjectURL(blob);
  const link=document.createElement("a");
  link.href=url;
  link.download=invoiceNumber+".pdf";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);

 }catch(err){
  notify(err.message,true);
 }
}

function invoiceDiscountLabel(line){
 const type=line.discount_type||"none";
 const value=Number(line.discount_value||0);

 if(type==="none"||value<=0)return "";

 const formatted=value.toLocaleString("de-DE",{
  maximumFractionDigits:2
 });

 if(type==="percent"){
  return " (Rabatt: "+formatted+" %)";
 }

 if(type==="fixed"){
  return " (Rabatt: "+euro(value)+")";
 }

 return "";
}


async function invoiceAttachmentRequest(path,options={}){
 const response=await fetch(path,{
  credentials:"same-origin",
  ...options,
  headers:{
   ...(options.headers||{}),
   "X-Tenant-ID":String(state.tenantId)
  }
 });

 if(response.status===401){
  showLogin();
  throw Error("Sitzung abgelaufen. Bitte anmelden.");
 }

 let data;
 try{
  data=await response.json();
 }catch{
  data={};
 }

 if(!response.ok){
  throw Error(
   typeof data.detail==="string"
    ?data.detail
    :JSON.stringify(data.detail||data)
  );
 }

 return data;
}

async function openInvoiceAttachment(invoiceId,attachmentId){
 const response=await fetch(
  "/api/invoices/"+invoiceId+"/attachments/"+attachmentId,
  {
   credentials:"same-origin",
   cache:"no-store",
   headers:{"X-Tenant-ID":String(state.tenantId)}
  }
 );

 if(response.status===401){
  showLogin();
  throw Error("Sitzung abgelaufen. Bitte anmelden.");
 }

 if(!response.ok){
  throw Error("PDF-Dokument konnte nicht geöffnet werden.");
 }

 const blob=await response.blob();
 const url=URL.createObjectURL(blob);

 const link=document.createElement("a");
 link.href=url;
 link.target="_blank";
 link.rel="noopener";

 document.body.appendChild(link);
 link.click();
 link.remove();

 setTimeout(()=>URL.revokeObjectURL(url),60000);
}

async function loadInvoiceAttachments(invoiceId){
 const target=$("invoice-attachments");
 if(!target)return;

 try{
  const data=await api(
   "/api/invoices/"+invoiceId+"/attachments"
  );

  const current=$("invoice-attachments");
  if(!current)return;

  const locked=Boolean(data.locked);
  const attachments=data.attachments||[];

  const rows=attachments.map(item=>
   '<tr>'+
    '<td>'+esc(item.filename)+'</td>'+
    '<td>'+esc((item.file_size/1024).toFixed(1))+' KB</td>'+
    '<td>'+
     '<button type="button" class="small secondary" '+
      'data-open-attachment="'+item.id+'">Öffnen</button>'+
     (locked
      ?""
      :' <button type="button" class="small secondary" '+
       'data-delete-attachment="'+item.id+'">Löschen</button>')+
    '</td>'+
   '</tr>'
  );

  const list=attachments.length
   ?table(["Dateiname","Größe","Aktion"],rows)
   :'<p class="muted">Keine Dokumente hinterlegt.</p>';

  const upload=locked
   ?'<p class="muted">Anhänge sind wegen eines laufenden oder '+
    'bereits erfolgreichen Rechnungsversands gesperrt.</p>'
   :'<form id="invoice-attachment-form">'+
     '<input type="file" id="invoice-attachment-files" '+
      'accept=".pdf,application/pdf" multiple required>'+
     '<button type="submit">PDF hochladen</button>'+
    '</form>';

  current.innerHTML=list+upload;

  current.querySelectorAll("[data-open-attachment]").forEach(button=>{
   button.onclick=async()=>{
    try{
     await openInvoiceAttachment(
      invoiceId,
      Number(button.dataset.openAttachment)
     );
    }catch(error){
     notify(error.message,true);
    }
   };
  });

  current.querySelectorAll("[data-delete-attachment]").forEach(button=>{
   button.onclick=async()=>{
    if(!confirm("Dokument wirklich löschen?"))return;

    button.disabled=true;

    try{
     await invoiceAttachmentRequest(
      "/api/invoices/"+invoiceId+
      "/attachments/"+Number(button.dataset.deleteAttachment),
      {method:"DELETE"}
     );

     await loadInvoiceAttachments(invoiceId);
     notify("Dokument gelöscht.");
    }catch(error){
     notify(error.message,true);
     await loadInvoiceAttachments(invoiceId);
    }
   };
  });

  const form=$("invoice-attachment-form");

  if(form){
   form.onsubmit=async event=>{
    event.preventDefault();

    const files=Array.from(
     $("invoice-attachment-files").files||[]
    );

    if(!files.length)return;

    const button=form.querySelector("button");
    button.disabled=true;

    try{
     for(const file of files){
      if(file.size>10*1024*1024){
       throw Error(
        file.name+": maximal 10 MB pro PDF erlaubt."
       );
      }

      const body=new FormData();
      body.append("file",file);

      await invoiceAttachmentRequest(
       "/api/invoices/"+invoiceId+"/attachments",
       {
        method:"POST",
        body
       }
      );
     }

     await loadInvoiceAttachments(invoiceId);
     notify("PDF-Dokumente gespeichert.");

    }catch(error){
     await loadInvoiceAttachments(invoiceId);
     notify(error.message,true);
    }
   };
  }

 }catch(error){
  const current=$("invoice-attachments");

  if(current){
   current.textContent=error.message;
  }

  notify(error.message,true);
 }
}

async function invoiceDetail(i,partner=null){
 const activeTenant=(state.tenants||[]).find(t=>
  Number(t.id)===Number(state.tenantId)
 );
 const isUtilityTenant=
  activeTenant?.tenant_type==="vermieter" &&
  i.utility_period_from!=null;
 const utilityAdvance=Number(i.utility_prepayments||0);
 const utilityDifference=Number(i.utility_difference||0);
 const utilityShare=Number(i.gross_total||0);

 const utilityCards=
  '<div class="cards">'+
  '<div class="card"><div class="muted">Mieteranteil</div><div class="metric">'+euro(utilityShare)+'</div></div>'+
  '<div class="card"><div class="muted">Vorauszahlungen</div><div class="metric">'+euro(utilityAdvance)+'</div></div>'+
  '<div class="card"><div class="muted">'+
   (utilityDifference<0?"Guthaben":"Nachzahlung")+
   '</div><div class="metric">'+euro(Math.abs(utilityDifference))+'</div></div>'+
  '<div class="card"><div class="muted">Bereits bezahlt</div><div class="metric">'+euro(i.paid_total)+'</div></div>'+
  '<div class="card"><div class="muted">Offener Saldo</div><div class="metric">'+euro(i.open_total)+'</div></div>'+
  '</div>';

 const statusLabel={
  draft:"Entwurf",open:"Offen",partial:"Teilbezahlt",
  paid:"Bezahlt",cancelled:"Storniert"
 };
 const typeLabel=i.invoice_type==="outgoing"
  ?"Ausgangsrechnung":"Eingangsrechnung";
 const address=partner?[
  partner.name,partner.street,
  [partner.postal_code,partner.city].filter(Boolean).join(" "),
  partner.country
 ].filter(Boolean).map(esc).join("<br>"):"Nicht zugeordnet";
 const info=[
  ["Rechnungsnummer",i.invoice_number],
  ["Rechnungsart",typeLabel],
  ["Rechnungsdatum",i.invoice_date],
  ["Fälligkeit",i.due_date||"–"],
  ["Lieferanten-Rechnungsnummer",i.supplier_reference||"–"],
  ["Status",statusLabel[i.status]||i.status],
  ["Kunde / Lieferant",partner?.name||"Nicht zugeordnet"],
  ["E-Mail",partner?.email||"–"],
  ["Telefon",partner?.phone||"–"],
  ["USt-IdNr.",partner?.vat_id||"–"]
 ];
 if(isUtilityTenant){
  info.length=0;
  info.push(
   ["NK-Abrechnungsnummer",i.invoice_number],
   ["Abrechnungsdatum",i.invoice_date],
   ["Abrechnungszeitraum von",i.utility_period_from||"–"],
   ["Abrechnungszeitraum bis",i.utility_period_to||"–"],
   ["Fälligkeit",i.due_date||"–"],
   ["Status",statusLabel[i.status]||i.status],
   ["Mieter",partner?.name||"Nicht zugeordnet"]
  );
 }

 const infoTable='<div class="panel"><h3>'+(isUtilityTenant?"NK-Abrechnungsinformationen":"Rechnungsinformationen")+'</h3>'+
  table(["Angabe","Wert"],info.map(([k,v])=>
   '<tr><td>'+esc(k)+'</td><td>'+esc(v)+'</td></tr>'))+
  '</div>';

 const lines=isUtilityTenant
  ?table(
   ["Position","Beschreibung","Gesamtkosten",
    "Gesamtschlüssel","Mieterschlüssel","Mieteranteil"],
   (i.lines||[]).map(l=>
    '<tr><td>'+esc(l.position)+'</td>'+
    '<td>'+esc(l.description)+'</td>'+
    '<td>'+euro(l.utility_total_cost)+'</td>'+
    '<td>'+esc(l.utility_total_key)+'</td>'+
    '<td>'+esc(l.utility_tenant_key)+'</td>'+
    '<td>'+euro(l.gross_total)+'</td></tr>')
  )
  :table(
  ["Position","Beschreibung","Menge","Einheit","Einzelpreis netto",
   "Rabatt","USt %","Netto","USt","Brutto"],
  (i.lines||[]).map(l=>
   '<tr><td>'+esc(l.position)+'</td>'+
   '<td>'+esc(l.description)+'</td>'+
   '<td>'+esc(l.quantity)+'</td>'+
   '<td>'+esc(l.unit||"")+'</td>'+
   '<td>'+euro(l.unit_net_price)+'</td>'+
   '<td>'+esc(invoiceDiscountLabel(l)||"–")+'</td>'+
   '<td>'+esc(l.vat_rate)+'</td>'+
   '<td>'+euro(l.net_total)+'</td>'+
   '<td>'+euro(l.vat_total)+'</td>'+
   '<td>'+euro(l.gross_total)+'</td></tr>')
 );

 const payments=i.payments||[];
 const paymentTable=payments.length
  ?table(["Datum","Betrag","Zahlungsart","Referenz","Bemerkung"],
   payments.map(p=>
    '<tr><td>'+esc(p.payment_date)+'</td>'+
    '<td>'+euro(p.amount)+'</td>'+
    '<td>'+esc(p.payment_method||"–")+'</td>'+
    '<td>'+esc(p.reference||"–")+'</td>'+
    '<td>'+esc(p.notes||"–")+'</td></tr>'))
  :'<p class="muted">Noch keine Zahlung erfasst.</p>';

 const pdfButton=i.invoice_type==="outgoing"&&i.status!=="draft"
  ?'<button type="button" id="download-invoice-pdf">PDF herunterladen</button>'
  :"";

 $("invoice-editor").innerHTML=
  '<div class="panel">'+
   '<div class="toolbar"><div><h2>'+esc(isUtilityTenant?'Nebenkostenabrechnung':typeLabel)+' '+esc(i.invoice_number)+'</h2>'+
   '<div class="muted">'+esc(partner?.name||"Nicht zugeordnet")+
   ' · '+esc(statusLabel[i.status]||i.status)+'</div></div>'+
   pdfButton+
   (!isUtilityTenant&&i.invoice_type==="outgoing"&&i.status!=="draft"
    ? '<button type="button" id="send-xrechnung">X-Rechnung</button>'
    : "")+
   '<button type="button" class="secondary" id="close-invoice-detail">Schließen</button>'+
   '</div>'+
   (isUtilityTenant?utilityCards:
   '<div class="cards">'+
    '<div class="card"><div class="muted">Netto</div><div class="metric">'+euro(i.net_total)+'</div></div>'+
    '<div class="card"><div class="muted">USt</div><div class="metric">'+euro(i.vat_total)+'</div></div>'+
    '<div class="card"><div class="muted">Brutto</div><div class="metric">'+euro(i.gross_total)+'</div></div>'+
    '<div class="card"><div class="muted">Bezahlt</div><div class="metric">'+euro(i.paid_total)+'</div></div>'+
    '<div class="card"><div class="muted">Offen</div><div class="metric">'+euro(i.open_total)+'</div></div>'+
   '</div>')+
   '<h3>'+(isUtilityTenant?'Nebenkostenpositionen':'Rechnungspositionen')+'</h3>'+lines+
   (i.invoice_type==="outgoing"
    ?'<h3>'+(isUtilityTenant?'NK-Belege':'Rechnungsanhänge')+'</h3>'+
     '<div id="invoice-attachments">'+
     '<p class="muted">Dokumente werden geladen …</p>'+
     '</div>'
    :"")+
   '<h3>Zahlungen</h3>'+paymentTable+
   '<h3>Notizen</h3><p>'+esc(i.notes||"Keine Notizen")+'</p>'+
   '<div id="invoice-actions"></div>'+
  '</div>'+infoTable+
  '<div class="panel"><h3>'+(isUtilityTenant?'Mieteranschrift':'Partneranschrift')+'</h3><p>'+address+'</p></div>';

 if(i.invoice_type==="outgoing"){
  loadInvoiceAttachments(i.id);
 }

 $("close-invoice-detail").onclick=()=>{
  $("invoice-editor").innerHTML="";
 };

 if(pdfButton){
  $("download-invoice-pdf").onclick=()=>
   downloadInvoicePdf(i.id,i.invoice_number);
 }


  const xrechnungButton=$("send-xrechnung");

  if(xrechnungButton){
   xrechnungButton.onclick=async()=>{
    if(!confirm("XRechnung mit PDF und XML per E-Mail versenden?"))return;

    xrechnungButton.disabled=true;

    try{
     const result=await api(
      "/api/invoices/"+i.id+"/send-xrechnung",
      {method:"POST"}
     );

     notify(
      "XRechnung per E-Mail versendet an "+
      (result.recipient||"Empfänger")
     );
    }catch(err){
     notify(err.message,true);
    }finally{
     xrechnungButton.disabled=false;
    }
   };
  }

 const actions=$("invoice-actions");
 const utilityOpen=Number(i.open_total||0);
 const paymentHeading=isUtilityTenant
  ?(utilityOpen<0?"Auszahlung an Mieter erfassen":
    utilityOpen>0?"Zahlungseingang erfassen":"Abrechnung ohne Zahlung ausgleichen")
  :"Zahlung erfassen";
 const paymentButtonLabel=isUtilityTenant
  ?(utilityOpen<0?"Auszahlung speichern":
    utilityOpen>0?"Zahlungseingang speichern":"Ausgleich speichern")
  :"Zahlung speichern";
 if(i.status==="draft"){
  actions.innerHTML=
   '<button type="button" id="finalize">'+(isUtilityTenant?'NK-Abrechnung freigeben':'Rechnung freigeben')+'</button>';
  $("finalize").onclick=async()=>{
   if(!confirm(isUtilityTenant?"NK-Abrechnung wirklich freigeben?":"Rechnung wirklich freigeben?"))return;
   try{
    await api("/api/invoices/"+i.id+"/finalize",{method:"POST"});
    await invoices();
    notify(isUtilityTenant?"NK-Abrechnung freigegeben.":"Rechnung freigegeben.");
   }catch(err){notify(err.message,true);}
  };
 }else if(["open","partial"].includes(i.status)){
  let paymentAccounts=[];
  try{
   const accounts=await api("/api/payment-accounts");
   if(!Array.isArray(accounts)){
    throw new Error("Ungueltige Antwort der Zahlungskonten-API.");
   }
   paymentAccounts=accounts.filter(a=>a.is_active===true);
  }catch(err){
   actions.innerHTML='<h3>'+paymentHeading+'</h3>'+
    '<p class="muted">Zahlungskonten konnten nicht geladen werden.</p>';
   notify(err.message,true);
   return;
  }

  const accountOptions=paymentAccounts.map(a=>[
   String(a.id),a.name
  ]);

  const defaultPaymentAccount=
   paymentAccounts.find(a=>a.is_default===true)||
   paymentAccounts[0];

  actions.innerHTML=
   '<h3>'+paymentHeading+'</h3>'+
   (paymentAccounts.length===0
    ?'<p class="muted">Kein aktives Zahlungskonto vorhanden.</p>'
    :'')+
   '<form id="payment-form"><div class="grid-form">'+
   field("payment_account_id",
     isUtilityTenant&&utilityOpen<0?"Auszahlungskonto":"Zahlungskonto",
     "select",
    defaultPaymentAccount?String(defaultPaymentAccount.id):"",
    accountOptions)+
   field("payment_date",
     isUtilityTenant&&utilityOpen<0?"Auszahlungsdatum":"Zahlungsdatum",
     "date",today())+
   field("amount",
     isUtilityTenant
      ?(utilityOpen<0?"Auszahlungsbetrag":
        utilityOpen>0?"Zahlungseingang":"Ausgleichsbetrag")
      :"Betrag",
     "number",i.open_total)+
   field("payment_method","Zahlungsart","select","bank",
    [["bank","Bank"],["cash","Bar"],["other","Sonstige"]])+
   field("reference","Referenz")+
   '</div><button'+(paymentAccounts.length===0?' disabled':'')+
   '>'+paymentButtonLabel+'</button></form>';

  $("payment-form").onsubmit=async e=>{
   e.preventDefault();
   try{
    const data=Object.fromEntries(new FormData(e.target));
    const accountId=Number(data.payment_account_id);

    if(!Number.isSafeInteger(accountId)||accountId<=0||
       !paymentAccounts.some(a=>a.id===accountId)){
     throw new Error("Bitte ein gueltiges Zahlungskonto auswaehlen.");
    }

    data.payment_account_id=accountId;

    await api("/api/invoices/"+i.id+"/payments",{
     method:"POST",
     body:JSON.stringify(data)
    });

    await invoices();
    notify(isUtilityTenant
     ?(utilityOpen<0?"Auszahlung gespeichert.":
       utilityOpen>0?"Zahlungseingang gespeichert.":
       "Nullsaldo ausgeglichen.")
     :"Zahlung gespeichert.");
   }catch(err){notify(err.message,true);}
  };
 }
}

// BUHA_ACCOUNT_BALANCE_CARDS_348
function paymentAccountBalanceCards(accounts){
 if(!Array.isArray(accounts)||!accounts.length){
  return '<p class="muted">Keine Zahlungskonten vorhanden.</p>';
 }

 return '<div class="cards">'+accounts.map(account=>{
  const name=account.name||account.account_name||
   "Zahlungskonto "+(account.id||account.account_id||"");
  const balance=account.balance??account.closing_balance??
   account.current_balance??null;

  // BUHA_ACCOUNT_DISPLAY_FIX_361
  return '<div class="card" style="display:flex;flex-direction:column;gap:12px">'+
   '<span class="muted">'+esc(name)+'</span>'+
   '<strong style="display:block;font-size:24px">'+
   (balance===null?"–":euro(balance))+
   '</strong></div>';
 }).join("")+'</div>';
}

async function journal(){
 const d=new Date();const year=d.getFullYear(),month=d.getMonth()+1;
 $("content").innerHTML='<div class="toolbar"><input id="j-year" type="number" value="'+year+'"><select id="j-month">'+
 Array.from({length:12},(_,i)=>'<option value="'+(i+1)+'"'+(i+1===month?" selected":"")+'>'+(i+1)+'. Monat</option>').join("")+
 '</select><button id="j-load">Anzeigen</button></div><div id="j-result"></div>';
 $("j-load").onclick=loadJournal;await loadJournal();
}
async function loadJournal(){
 try{const data=await api("/api/accounting/journal?year="+Number($("j-year").value)+"&month="+Number($("j-month").value));
 const bankAvailable=
  data.bank_closing_balance!==null &&
  data.bank_closing_balance!==undefined;

 const bankCards=bankAvailable
  ? '<div class="panel"><h2>Gesamtübersicht Zahlungskonten</h2><div class="cards">'+
    [
     ["Gesamtbestand Monatsanfang",
      data.bank_opening_balance],
     ["Zahlungseingänge",data.bank_incoming],
     ["Zahlungsausgänge",data.bank_outgoing],
     ["Gesamtbestand Monatsende",
      data.bank_closing_balance]
    ].map(([label,value])=>
     '<div class="card"><div class="muted">'+esc(label)+
     '</div><div class="metric">'+
     (value===null||value===undefined?"–":euro(value))+
     '</div></div>'
    ).join("")+'</div></div>'
  : '<div class="panel"><p class="muted">'+
    'Bankanfangsbestand und Stichtag bitte in der '+
    'Administration hinterlegen.</p></div>';

 $("j-result").innerHTML=
  '<div class="panel"><h2>Einzelne Zahlungskonten</h2>'+
  paymentAccountBalanceCards(data.payment_accounts)+
  '</div>'+
  bankCards+'<div class="cards">'+[["Netto",data.net_total],["USt",data.vat_total],["Brutto",data.gross_total]]
 .map(([n,v])=>'<div class="card"><div class="muted">'+n+'</div><div class="metric">'+euro(v)+'</div></div>').join("")+
 '</div><div class="panel">'+table(["Datum","Rechnung","Art","Konto","Beschreibung","Zahlungskonto","Netto","USt","Brutto"],
 data.rows.map(r=>'<tr><td>'+esc(r.payment_date)+'</td><td>'+esc(r.invoice_number)+'</td><td>'+esc(
  r.source_type==="manual_booking"
   ?(r.invoice_type==="outgoing"?"Einnahme":"Ausgabe")
   :(r.invoice_type==="outgoing"?"Ausgangsrechnung":
     r.invoice_type==="incoming"?"Eingangsrechnung":
     r.invoice_type)
 )+'</td><td>'+esc(
  [r.account_number,r.account_name].filter(Boolean).join(" - ")
 )+'</td><td>'+esc(r.description)+'</td><td>'+esc(r.payment_account_name||'')+'</td><td>'+euro(r.net)+
 '</td><td>'+euro(r.vat)+'</td><td>'+euro(r.gross)+'</td></tr>'))+'</div>';
 }catch(e){notify(e.message,true);}
}
async function eur(){
 const year=new Date().getFullYear();

 $("content").innerHTML=
  '<div class="toolbar">'+
  '<label>Jahr <input id="e-year" type="number" min="2000" max="2099" value="'+year+'"></label>'+
  '<label>Von <input id="e-from" type="date" value="'+year+'-01-01"></label>'+
  '<label>Bis <input id="e-to" type="date" value="'+year+'-12-31"></label>'+
  '<label>Darstellung <select id="e-view">'+
  '<option value="details">Alle Einzelbuchungen</option>'+
  '<option value="summary">Nur Kontensummen</option>'+
  '</select></label>'+
  '<label>Sortierung <select id="e-sort">'+
  '<option value="date">Datum</option>'+
  '<option value="account">Buchhaltungskonto</option>'+
  '<option value="type">Einnahmen / Ausgaben</option>'+
  '</select></label>'+
  '<label>Gruppierung <select id="e-group">'+
  '<option value="account">Buchhaltungskonto</option>'+
  '<option value="type">Einnahmen / Ausgaben</option>'+
  '<option value="date">Datum</option>'+
  '</select></label>'+
  '<button id="e-load">Auswerten</button>'+
  '<button id="e-pdf" type="button">PDF exportieren</button>'+
  '</div><div id="e-result"></div>';

 $("e-year").onchange=()=>{
  const y=Number($("e-year").value);
  if(Number.isInteger(y)&&y>=2000&&y<=2099){
   $("e-from").value=y+"-01-01";
   $("e-to").value=y+"-12-31";
  }
 };

 $("e-load").onclick=loadEur;
 $("e-pdf").onclick=downloadEurPdf;

 $("e-view").onchange=()=>{
  const summary=$("e-summary");
  const details=$("e-details");
  const showDetails=$("e-view").value==="details";
  if(summary)summary.style.display=showDetails?"none":"";
  if(details)details.style.display=showDetails?"":"none";
 };

 await loadEur();
}

async function loadEur(){
 try{
  const year=Number($("e-year").value);
  const from=$("e-from").value;
  const to=$("e-to").value;

  if(!Number.isInteger(year)||year<2000||year>2099){
   throw new Error("Bitte ein gültiges Jahr zwischen 2000 und 2099 wählen.");
  }

  if(!from||!to||from>to){
   throw new Error("Bitte einen gültigen Zeitraum Von/Bis auswählen.");
  }

  const params=new URLSearchParams({
   year:String(year),
   date_from:from,
   date_to:to,
   sort_by:$("e-sort").value,
   group_by:$("e-group").value
  });

  const d=await api("/api/accounting/eur?"+params.toString());

  if(!Array.isArray(d.accounts)||!Array.isArray(d.detail_groups)){
   throw new Error("Die EÜR-API liefert keine vollständigen Auswertungsdaten.");
  }

  const taxCards=
   '<div class="panel"><h2>Umsatzsteuerübersicht (zahlungsbasiert)</h2>'+
   '<div class="cards">'+
   [
    ["Vereinnahmte Umsatzsteuer",d.output_vat_total],
    ["Berücksichtigte Vorsteuer",d.input_vat_total],
    ["Umsatzsteuerdifferenz",d.vat_difference]
   ].map(([label,value])=>
    '<div class="card"><div class="muted">'+esc(label)+'</div>'+
    '<div class="metric">'+euro(value??0)+'</div></div>'
   ).join("")+
   '</div><p class="muted">Diese Übersicht ist keine '+
   'Umsatzsteuer-Voranmeldung. Steuerliche Fälligkeiten '+
   'und Vorsteuerabzugszeitpunkte sind gesondert zu prüfen.</p>'+
   '</div>';

  const totals=
   '<div class="cards">'+
   [
    ["Einnahmen netto",d.income_net],
    ["Ausgaben netto",d.expenses_net],
    ["Ergebnis",d.result_net]
   ].map(([name,value])=>
    '<div class="card"><div class="muted">'+esc(name)+'</div>'+
    '<div class="metric">'+euro(value)+'</div></div>'
   ).join("")+
   '</div>';

  const summary=
   '<div id="e-summary" class="panel">'+
   '<h2>Auswertung nach Buchhaltungskonten</h2>'+
   table(
    ["Art","Konto","Bezeichnung","Netto","USt","Brutto"],
    d.accounts.map(r=>
     '<tr><td>'+esc(r.invoice_type==="outgoing"?"Einnahme":"Ausgabe")+'</td>'+
     '<td>'+esc(r.account_number??"")+'</td>'+
     '<td>'+esc(r.account_name??"")+'</td>'+
     '<td>'+euro(r.net)+'</td>'+
     '<td>'+euro(r.vat)+'</td>'+
     '<td>'+euro(r.gross)+'</td></tr>'
    )
   )+
   '</div>';

  const details=
   '<div id="e-details" class="panel">'+
   '<h2>Alle Einzelbuchungen</h2>'+
   '<p class="muted">Zeitraum: '+esc(d.date_from)+' bis '+esc(d.date_to)+'</p>'+
   d.detail_groups.map(g=>
    '<h3>'+esc(g.group)+'</h3>'+
    table(
     ["Datum","Rechnung","Art","Konto","Beschreibung","Netto","USt","Brutto"],
     (g.rows||[]).map(r=>
      '<tr><td>'+esc(r.payment_date)+'</td>'+
      '<td>'+esc(r.invoice_number??"")+'</td>'+
      '<td>'+esc(r.invoice_type==="outgoing"?"Einnahme":"Ausgabe")+'</td>'+
      '<td>'+esc(r.account_number??"")+'</td>'+
      '<td>'+esc(r.description??"")+'</td>'+
      '<td>'+euro(r.net)+'</td>'+
      '<td>'+euro(r.vat)+'</td>'+
      '<td>'+euro(r.gross)+'</td></tr>'
     )
    )+
    '<p><strong>Gruppensumme: Netto '+euro(g.net)+
    ' | USt '+euro(g.vat)+
    ' | Brutto '+euro(g.gross)+'</strong></p>'
   ).join("")+
   '</div>';

  $("e-result").innerHTML=taxCards+totals+summary+details;

  const showDetails=$("e-view").value==="details";
  $("e-summary").style.display=showDetails?"none":"";
  $("e-details").style.display=showDetails?"":"none";

 }catch(e){
  notify(e.message,true);
 }
}

async function downloadEurPdf(){
 try{
  const year=Number($("e-year").value);
  const from=$("e-from").value;
  const to=$("e-to").value;

  if(!Number.isInteger(year)||year<2000||year>2099){
   throw new Error("Bitte ein gültiges Jahr auswählen.");
  }

  if(!from||!to||from>to){
   throw new Error("Bitte einen gültigen Zeitraum auswählen.");
  }

  const params=new URLSearchParams({
   year:String(year),
   date_from:from,
   date_to:to,
   sort_by:$("e-sort").value,
   group_by:$("e-group").value,
   view:$("e-view").value
  });

  const headers={};

  if(state.tenantId){
   headers["X-Tenant-ID"]=String(state.tenantId);
  }

  const response=await fetch(
   "/api/accounting/eur/pdf?"+params.toString(),
   {
    method:"GET",
    credentials:"same-origin",
    headers
   }
  );

  if(!response.ok){
   let message="PDF-Export fehlgeschlagen.";

   try{
    const error=await response.json();
    message=error.detail||message;
   }catch{}

   throw new Error(message);
  }

  const blob=await response.blob();

  if(blob.type!=="application/pdf"){
   throw new Error("Der Server hat keine PDF-Datei geliefert.");
  }

  const url=URL.createObjectURL(blob);
  const link=document.createElement("a");

  link.href=url;
  link.download=
   "EUR_"+from+"_"+to+"_"+$("e-view").value+".pdf";

  document.body.appendChild(link);
  link.click();
  link.remove();

  setTimeout(()=>URL.revokeObjectURL(url),1000);

 }catch(e){
  notify(e.message,true);
 }
}

(async()=>{
 try{
  state.user=await api("/api/auth/me");
  await loadTenants();
  showApp();
  if(state.user?.role==="system_admin")await navigate("systemAdministration");
  else if(state.tenantId)await navigate("dashboard");
  else $("content").innerHTML='<div class="panel">Keine Mandantenzuordnung vorhanden.</div>';
 }catch{showLogin();}
})();



async function paymentAccounts(){
 if(state.tenantRole!=="admin"){
  $("content").innerHTML="<p>Keine Berechtigung.</p>";
  return;
 }
 const accounts=await api("/api/payment-accounts");
 const todayDate=new Date().toISOString().slice(0,10);
 const balances=await api("/api/payment-accounts/balances?target_date="+todayDate);
 const transfers=await api("/api/payment-account-transfers");

 if(!Array.isArray(accounts)||!Array.isArray(balances)||!Array.isArray(transfers)){
  throw new Error("Ungueltige Antwort der Zahlungskonten-API.");
 }

 const balanceById=new Map(balances.map(b=>[Number(b.id||b.account_id),b]));

 $("content").innerHTML=
  '<div class="panel"><h2>Zahlungskonten</h2>'+
  '<p class="muted">Zahlungskonten des aktuellen Mandanten</p>'+
  '<div id="payment-account-list"></div>'+
  '<h3>Neues Zahlungskonto</h3>'+
  '<form id="new-payment-account"><div class="grid-form">'+
  field("name","Kontoname")+
  field("opening_balance","Anfangsbestand","number","0")+
  field("opening_date","Anfangsdatum","date",todayDate)+
  '</div><label><input type="checkbox" name="is_default"> Als Standardkonto festlegen</label>'+
  '<div><button>Konto anlegen</button></div></form></div>';

 $("content").insertAdjacentHTML("beforeend",
  '<div class="panel"><h2>Umbuchungen</h2>'+
  '<form id="payment-transfer-form"><div class="grid-form">'+
  field("source_account_id","Quellkonto","select","",[])+
  field("target_account_id","Zielkonto","select","",[])+
  field("transfer_date","Buchungsdatum","date",todayDate)+
  field("amount","Betrag (EUR)","number","")+
  field("reference","Referenz")+
  '</div><button type="submit">Umbuchung speichern</button></form>'+
  '<h3>Umbuchungshistorie</h3>'+
  '<div id="payment-transfer-list"></div></div>'
 );


 const rows=accounts.map(account=>{
  const balance=balanceById.get(Number(account.id));
  const balanceValue=balance?.balance??balance?.current_balance;
  return '<tr>'+
   '<td>'+esc(account.name)+'</td>'+
   '<td>'+esc(account.is_active?"Aktiv":"Inaktiv")+'</td>'+
   '<td>'+esc(account.is_default?"Standard":"–")+'</td>'+
   '<td>'+euro(account.opening_balance)+'</td>'+
   '<td>'+esc(account.opening_date)+'</td>'+
   '<td>'+(balanceValue==null?"–":euro(balanceValue))+'</td>'+
   '<td>'+
   (!account.is_default&&account.is_active
    ?'<button type="button" data-default-account="'+Number(account.id)+'">Als Standard</button>'
    :'')+
   '<button type="button" data-edit-account="'+Number(account.id)+'">Bearbeiten</button>'+
   '</td></tr>';
 });

 $("payment-account-list").innerHTML=table(
  ["Konto","Status","Standard","Anfangsbestand","Anfangsdatum","Kontostand","Aktionen"],
  rows
 );


 const activeAccounts=accounts.filter(a=>a.is_active===true);
 const sourceSelect=$("payment-transfer-form").elements.source_account_id;
 const targetSelect=$("payment-transfer-form").elements.target_account_id;

 for(const account of activeAccounts){
  sourceSelect.add(new Option(account.name,String(account.id)));
  targetSelect.add(new Option(account.name,String(account.id)));
 }

 if(activeAccounts.length>1){
  targetSelect.value=String(activeAccounts[1].id);
 }else{
  $("payment-transfer-form").querySelector('button[type="submit"]').disabled=true;
 }

 const accountNames=new Map(
  accounts.map(a=>[Number(a.id),a.name])
 );

 $("payment-transfer-list").innerHTML=table(
  ["Datum","Quellkonto","Zielkonto","Betrag","Referenz"],
  transfers.map(t=>'<tr>'+
   '<td>'+esc(t.transfer_date)+'</td>'+
   '<td>'+esc(accountNames.get(Number(t.source_account_id))||t.source_account_id)+'</td>'+
   '<td>'+esc(accountNames.get(Number(t.target_account_id))||t.target_account_id)+'</td>'+
   '<td>'+euro(t.amount)+'</td>'+
   '<td>'+esc(t.reference||"")+'</td></tr>')
 );

 $("payment-transfer-form").onsubmit=async e=>{
  e.preventDefault();
  try{
   const data=Object.fromEntries(new FormData(e.target));
   data.source_account_id=Number(data.source_account_id);
   data.target_account_id=Number(data.target_account_id);

   if(!Number.isSafeInteger(data.source_account_id)||
      !Number.isSafeInteger(data.target_account_id)||
      data.source_account_id===data.target_account_id||
      !activeAccounts.some(a=>Number(a.id)===data.source_account_id)||
      !activeAccounts.some(a=>Number(a.id)===data.target_account_id)){
    throw new Error("Bitte zwei unterschiedliche aktive Konten auswaehlen.");
   }

   const amount=Number(data.amount);
   if(!Number.isFinite(amount)||amount<=0||
      !/^\\d+(?:\\.\\d{1,2})?$/.test(data.amount)){
    throw new Error("Betrag muss positiv sein und maximal zwei Nachkommastellen haben.");
   }

   if(!/^\\d{4}-\\d{2}-\\d{2}$/.test(data.transfer_date)){
    throw new Error("Bitte ein Buchungsdatum eingeben.");
   }

   if((data.reference||"").length>255){
    throw new Error("Referenz darf maximal 255 Zeichen enthalten.");
   }

   await api("/api/payment-account-transfers",{
    method:"POST",
    body:JSON.stringify(data)
   });

   await paymentAccounts();
   notify("Umbuchung gespeichert.");
  }catch(err){
   notify(err.message,true);
  }
 };

$("new-payment-account").onsubmit=async e=>{
  e.preventDefault();
  const data=Object.fromEntries(new FormData(e.target));
  data.is_default=e.target.elements.is_default.checked;
  try{
   await api("/api/payment-accounts",{
    method:"POST",body:JSON.stringify(data)
   });
   notify("Zahlungskonto angelegt.");
   await paymentAccounts();
  }catch(err){notify(err.message,true);}
 };

 $("payment-account-list").onclick=async e=>{
  const defaultButton=e.target.closest("[data-default-account]");
  const editButton=e.target.closest("[data-edit-account]");

  if(defaultButton){
   const id=Number(defaultButton.dataset.defaultAccount);
   try{
    await api("/api/payment-accounts/"+id,{
     method:"PATCH",
     body:JSON.stringify({is_default:true})
    });
    await paymentAccounts();
    notify("Standardkonto geaendert.");
   }catch(err){notify(err.message,true);}
   return;
  }

  if(editButton){
   const id=Number(editButton.dataset.editAccount);
   const account=accounts.find(a=>Number(a.id)===id);
   if(!account)return;

   const editor=document.createElement("div");
   editor.className="panel";
   editor.innerHTML=
    '<h3>Zahlungskonto bearbeiten</h3>'+
    '<form id="edit-payment-account"><div class="grid-form">'+
    field("name","Kontoname","text",account.name)+
    field("opening_balance","Anfangssaldo (EUR)","number",account.opening_balance)+
    field("opening_date","Anfangsdatum","date",account.opening_date)+
    '</div><button type="submit">Änderungen speichern</button> '+
    '<button type="button" id="cancel-payment-account-edit">Abbrechen</button>'+
    '</form>';

   const existing=$("edit-payment-account");
   if(existing)existing.closest(".panel").remove();

   $("payment-account-list").after(editor);

   $("cancel-payment-account-edit").onclick=()=>editor.remove();

   $("edit-payment-account").onsubmit=async event=>{
    event.preventDefault();
    const form=event.target;
    const data=Object.fromEntries(new FormData(form));

    data.name=data.name.trim();

    if(!data.name){
     notify("Kontoname darf nicht leer sein.",true);
     return;
    }

    data.opening_balance=data.opening_balance.trim().replace(",", ".");

    if(!/^-?\d+(?:\.\d{1,2})?$/.test(data.opening_balance)){
     notify("Bitte einen gültigen Anfangssaldo mit maximal zwei Nachkommastellen eingeben.",true);
     return;
    }

    if(!/^\d{4}-\d{2}-\d{2}$/.test(data.opening_date)){
     notify("Bitte ein gültiges Anfangsdatum eingeben.",true);
     return;
    }

    try{
     await api("/api/payment-accounts/"+id,{
      method:"PATCH",
      body:JSON.stringify(data)
     });
     await paymentAccounts();
     notify("Zahlungskonto aktualisiert.");
    }catch(err){
     notify(err.message,true);
    }
   };

  }
 };
}


// BUHA_ADMIN_SUBMENU_NAV_338
let activeAdminSection="company";

// BUHA_ADMIN_SUBMENU_WIRING_339
function refreshAdminSubmenu(){
 setupAdminSubmenu();

 const menu=$("admin-menu");
 const submenu=$("admin-submenu");
 const toggle=$("admin-menu-toggle");

 if(!menu||!submenu||!toggle)return;

 const adminPages=[
  "administration","paymentAccounts","accounts"
 ];

 const expanded=adminPages.includes(state.page);

 submenu.classList.toggle("hidden",!expanded);
 toggle.setAttribute("aria-expanded",String(expanded));
}

function setupAdminSubmenu(){
 const menu=$("admin-menu");
 const toggle=$("admin-menu-toggle");
 const submenu=$("admin-submenu");

 if(!menu||!toggle||!submenu)return;

 // BUHA_ADMIN_NAV_FINAL_355
 const allowed=state.user?.role!=="system_admin"&&
               state.tenantRole==="admin";

 menu.classList.toggle("hidden",!allowed);

 if(!allowed){
  submenu.classList.add("hidden");
  toggle.setAttribute("aria-expanded","false");
  return;
 }

 toggle.onclick=()=>{
  const expanded=toggle.getAttribute("aria-expanded")==="true";
  toggle.setAttribute("aria-expanded",String(!expanded));
  submenu.classList.toggle("hidden",expanded);
 };

 submenu.querySelectorAll("[data-admin-section]").forEach(button=>{
  button.addEventListener("click",()=>{
   activeAdminSection=button.dataset.adminSection;
  });
 });
}

// BUHA_ADMIN_SECTIONS_343
// BUHA_ADMIN_VISIBILITY_352
function showAdminSection(){
 const section=["company","mail","invoices"].includes(activeAdminSection)
  ?activeAdminSection:"company";
 const form=$("admin-form");
 if(!form)return;

 const groups={
  company:[
   "company_name","street","postal_code","city",
   "email","phone","tax_number","vat_id",
   "bank_name","website","bank_holder","iban","bic"
  ],
  invoices:[
   "invoice_prefix","invoice_digits","invoice_next",
   "incoming_prefix","incoming_digits","incoming_next",
   "utility_invoice_prefix","utility_invoice_digits",
   "utility_invoice_next",
   "booking_income_prefix","booking_income_digits",
   "booking_income_next",
   "booking_expense_prefix","booking_expense_digits",
   "booking_expense_next"
  ],
  mail:[
   "smtp_host","smtp_port","smtp_security",
   "smtp_username","smtp_from_name","smtp_from_email",
   "smtp_reply_to","invoice_mail_subject",
   "invoice_mail_body","invoice_auto_send_enabled",
   "invoice_bcc_enabled","invoice_bcc_email"
  ]
 };

 // BUHA_INVOICE_SETTINGS_TENANT_362
 const tenant=(state.tenants||[]).find(t=>
  Number(t.id)===Number(state.tenantId)
 );
 const isLandlord=tenant?.tenant_type==="vermieter";

 if(section==="invoices"){
  const outgoing=[
   "invoice_prefix","invoice_digits","invoice_next"
  ];
  const utility=[
   "utility_invoice_prefix","utility_invoice_digits",
   "utility_invoice_next"
  ];
  groups.invoices=groups.invoices.filter(name=>
   isLandlord?!outgoing.includes(name):!utility.includes(name)
  );
 }

 const headings={
  company:"Firmendaten",
  mail:"E-Mail-Einstellungen",
  invoices:isLandlord
   ?"NK-Abrechnungseinstellungen"
   :"Rechnungseinstellungen"
 };

 const heading=form.closest(".panel")?.querySelector("h2");
 if(heading)heading.textContent=headings[section];

 form.querySelectorAll("[name]").forEach(el=>{
  const label=el.closest("label");
  if(label)label.classList.toggle(
   "hidden",!groups[section].includes(el.name)
  );
 });

 // BUHA_ADMIN_FORM_FIX_353
 form.querySelectorAll(".grid-form").forEach(grid=>{
  const fields=[...grid.querySelectorAll("[name]")];
  if(fields.length){
   grid.classList.toggle(
    "hidden",
    !fields.some(el=>groups[section].includes(el.name))
   );
  }
 });

 form.querySelectorAll("h3").forEach(h=>{
  h.classList.toggle("hidden",section!=="mail");
 });

 const password=$("smtp-password");
 if(password){
  password.closest("label")?.classList.toggle(
   "hidden",section!=="mail"
  );
 }

 const logo=$("admin-logo");
 if(logo){
  logo.closest(".panel")?.classList.toggle(
   "hidden",section!=="company"
  );
 }

 const accounts=$("admin-accounts");
 if(accounts)accounts.closest(".panel")?.classList.add("hidden");

 const smtpTest=$("buha-smtp-test-send");
 if(smtpTest){
  smtpTest.closest(".panel")?.classList.toggle(
   "hidden",section!=="mail"
  );
 }

 // BUHA_ADMIN_HINTS_356
 form.querySelectorAll(".hint").forEach(h=>{
  h.classList.toggle("hidden",section!=="mail");
 });

 form.querySelectorAll(".bcc-toggle").forEach(label=>{
  label.classList.toggle("hidden",section!=="mail");
 });
}

async function administration(){
 if(state.tenantRole!=="admin"){
  $("content").innerHTML="<p>Keine Berechtigung.</p>";
  return;
 }

 const response=await api("/api/administration");
 const values=response.values;

 const fields=[
  ["company_name","Firmenname"],
  ["street","Straße"],
  ["postal_code","PLZ"],
  ["city","Ort"],
  ["email","E-Mail"],
  ["phone","Telefon"],
  ["tax_number","Steuernummer"],
  ["vat_id","USt-IdNr."],
  ["bank_name","Bank"],
  ["website","Internetadresse"],
  ["bank_holder","Kontoinhaber"],
  ["iban","IBAN"],

  ["bic","BIC"],
  ["invoice_prefix","Präfix Ausgangsrechnung"],
  ["invoice_digits","Stellen RE"],
  ["invoice_next","Startnummer RE"],
  ["incoming_prefix","Präfix Eingangsrechnung"],
  ["incoming_digits","Stellen LR"],
  ["incoming_next","Startnummer LR"],
   ["utility_invoice_prefix","Nebenkosten: Präfix"],
   ["utility_invoice_digits","Nebenkosten: Stellenzahl"],
   ["utility_invoice_next","Nebenkosten: Startnummer"],
   ["booking_income_prefix","Einnahmen: Präfix"],
   ["booking_income_digits","Einnahmen: Stellenzahl"],
   ["booking_income_next","Einnahmen: Startnummer"],
   ["booking_expense_prefix","Ausgaben: Präfix"],
   ["booking_expense_digits","Ausgaben: Stellenzahl"],
   ["booking_expense_next","Ausgaben: Startnummer"]
 ];

 $("content").innerHTML=`
  <div class="panel">
   <h2>Administration</h2>
   <form id="admin-form">
    <div class="grid-form">
     ${fields.map(([name,label])=>
       field(name,label,"text",values[name]??"")
     ).join("")}
    </div>

     <h3>E-Mail-Konto / SMTP</h3>
     <div class="grid-form">
      ${field("smtp_host","SMTP-Server","text",values.smtp_host??"")}
      ${field("smtp_port","SMTP-Port","number",values.smtp_port??"587")}
      ${field("smtp_security","Verschlüsselung","select",
        values.smtp_security??"starttls",[
         ["starttls","STARTTLS"],
         ["ssl","SSL/TLS"],
         ["none","Keine Verschlüsselung"]
        ])}
      ${field("smtp_username","SMTP-Benutzername","text",
        values.smtp_username??"")}
      ${field("smtp_from_name","Absendername","text",
        values.smtp_from_name??"")}
      ${field("smtp_from_email","Absenderadresse","email",
        values.smtp_from_email??"")}
      ${field("smtp_reply_to","Antwortadresse (Reply-To)","email",
        values.smtp_reply_to??"")}
     </div>
     <label>SMTP-Passwort
      <input type="password" id="smtp-password"
       autocomplete="new-password"
       placeholder="Neues Passwort eingeben">
     </label>
     <p class="hint">Das Passwort wird erst mit Aktivierung
     der sicheren SMTP-Speicherung übernommen.</p>

     <h3>Rechnungsversand – Mailvorlage</h3>
     <div class="grid-form">
      ${field("invoice_mail_subject","E-Mail-Betreff","text",
        values.invoice_mail_subject??
        "Ihre Rechnung {rechnungsnummer}")}
      ${field("invoice_mail_body","E-Mail-Text","textarea",
        values.invoice_mail_body??
        "Guten Tag,\\n\\nanbei erhalten Sie unsere Rechnung "+
        "{rechnungsnummer} vom {rechnungsdatum} über "+
        "{bruttobetrag} als PDF-Anhang.\\n\\n"+
        "Mit freundlichen Grüßen\\n{firmenname}")}
     </div>
     <p class="hint">
      Platzhalter: {rechnungsnummer}, {rechnungsdatum},
      {faelligkeit}, {kundenname}, {bruttobetrag}, {firmenname}
     </p>

    <h3>Automatischer Rechnungsversand</h3>
    <label class="bcc-toggle">
     <input type="checkbox"
      id="invoice-auto-send-enabled"
      name="invoice_auto_send_enabled"
      ${values.invoice_auto_send_enabled===true?"checked":""}>
     Ausgangsrechnungen bei Freigabe automatisch
     per E-Mail mit PDF-Anhang versenden
    </label>
    <p class="hint">
     Die E-Mail wird an die Adresse aus dem Kundenstamm gesendet.
     Bei einem Versandfehler bleibt die Rechnung freigegeben.
    </p>

    <h3>Rechnungsversand – BCC-Kopie</h3>
    <label class="bcc-toggle">
     <input type="checkbox"
            id="invoice-bcc-enabled"
            name="invoice_bcc_enabled"
            ${values.invoice_bcc_enabled ? "checked" : ""}>
     Automatische BCC-Kopie aktiv
    </label>
    <div class="grid-form">
     ${field(
       "invoice_bcc_email",
       "BCC-E-Mail-Adresse",
       "email",
       values.invoice_bcc_email ?? ""
     )}
    </div>
    <p class="hint">
     Bei aktivierter Funktion erhält diese Adresse eine
     versteckte Kopie jeder per BUHA versendeten Rechnung.
    </p>
    <button type="submit">Einstellungen speichern</button>
   </form>
  </div>
  <div class="panel">
   <h2>Kontenplan</h2>
   <button id="admin-accounts">Kontenplan öffnen</button>
  </div>
  <div class="panel">
   <h2>Firmenlogo</h2>
   <div class="logo-preview">
    <img class="company-logo admin-logo hidden"
         alt="Aktuell gespeichertes Firmenlogo">
   </div>
   <input id="admin-logo" type="file" accept="image/png,image/jpeg">
   <button id="admin-logo-save">Logo hochladen</button>
  </div>`;

 // BUHA_ADMIN_MAIL_162B
 const smtpTestPanel=document.createElement("div");
 smtpTestPanel.className="panel";
 smtpTestPanel.innerHTML=`
  <h2>SMTP-Verbindung testen</h2>
  <p id="buha-smtp-status" class="muted">
   Passwortstatus wird geladen.
  </p>
  <div class="grid-form">
   <label>Testmail-Empfänger
    <input type="email" id="buha-smtp-test-recipient"
     placeholder="test@example.de">
   </label>
  </div>
  <button type="button" id="buha-smtp-test-send">
   Test-E-Mail senden
  </button>`;
 $("admin-form").closest(".panel").after(smtpTestPanel);

 api("/api/administration/smtp/status")
  .then(result=>{
   $("buha-smtp-status").textContent=result.password_configured
    ? "SMTP-Passwort gespeichert."
    : "Noch kein SMTP-Passwort gespeichert.";
  })
  .catch(err=>{
   $("buha-smtp-status").textContent=err.message;
  });

 $("buha-smtp-test-send").onclick=async()=>{
  const recipient=$("buha-smtp-test-recipient").value.trim();
  if(!recipient)return notify("Empfängeradresse fehlt.",true);
  if(!confirm("Testmail an "+recipient+" senden?"))return;
  try{
   await api("/api/administration/smtp/test",{
    method:"POST",
    body:JSON.stringify({recipient})
   });
   notify("Testmail an SMTP-Server übergeben.");
  }catch(err){notify(err.message,true);}
 };

 if(companyLogoUrl){
  const preview=document.querySelector(".admin-logo");
  if(preview){
   preview.src=companyLogoUrl;
   preview.classList.remove("hidden");
  }
 }

 showAdminSection();

 $("admin-accounts").onclick=()=>navigate("accounts");

 $("admin-form").onsubmit=async e=>{
  e.preventDefault();
  // BUHA_ADMIN_SAVE_344
  const allowed={
   company:[
    "company_name","street","postal_code","city",
    "email","phone","tax_number","vat_id",
    "bank_name","website","bank_holder","iban","bic"
   ],
   invoices:[
    "invoice_prefix","invoice_digits","invoice_next",
    "incoming_prefix","incoming_digits","incoming_next",
    "utility_invoice_prefix","utility_invoice_digits",
    "utility_invoice_next",
    "booking_income_prefix","booking_income_digits",
    "booking_income_next",
    "booking_expense_prefix","booking_expense_digits",
    "booking_expense_next"
   ],
   mail:[
    "smtp_host","smtp_port","smtp_security",
    "smtp_username","smtp_from_name","smtp_from_email",
    "smtp_reply_to","invoice_mail_subject",
    "invoice_mail_body","invoice_auto_send_enabled",
    "invoice_bcc_enabled","invoice_bcc_email"
   ]
  };
  // BUHA_INVOICE_SAVE_TENANT_363
  const section=activeAdminSection||"company";
  let names=allowed[section];
  if(!names)return notify("Ungültiger Administrationsbereich.",true);

  if(section==="invoices"){
   const tenant=(state.tenants||[]).find(t=>
    Number(t.id)===Number(state.tenantId)
   );
   const isLandlord=tenant?.tenant_type==="vermieter";
   const outgoing=[
    "invoice_prefix","invoice_digits","invoice_next"
   ];
   const utility=[
    "utility_invoice_prefix","utility_invoice_digits",
    "utility_invoice_next"
   ];
   names=names.filter(name=>
    isLandlord?!outgoing.includes(name):!utility.includes(name)
   );
  }

  const formData=new FormData(e.target);
  const data={};

  for(const name of names){
   if(name==="invoice_bcc_enabled"||
      name==="invoice_auto_send_enabled"){
    data[name]=formData.has(name);
   }else if(formData.has(name)){
    data[name]=formData.get(name);
   }
  }

  for(const key of [
   "invoice_digits","incoming_digits",
   "invoice_next","incoming_next",
   "utility_invoice_digits","utility_invoice_next",
   "booking_income_digits","booking_income_next",
   "booking_expense_digits","booking_expense_next"
  ]){
   if(key in data)data[key]=Number(data[key]);
  }

  try{
   await api("/api/administration",{
    method:"PUT",
    body:JSON.stringify({values:data})
   });
   const smtpPassword=$("smtp-password").value;
   if(section==="mail"&&smtpPassword){
    await api("/api/administration/smtp/password",{
     method:"PUT",
     body:JSON.stringify({password:smtpPassword})
    });
    $("smtp-password").value="";
   }
   notify("Einstellungen gespeichert.");
  }catch(err){notify(err.message,true);}
 };

 $("admin-logo-save").onclick=async()=>{
  const file=$("admin-logo").files[0];
  if(!file)return notify("Bitte Logo auswählen.",true);
  if(file.size>2000000)return notify("Logo zu groß.",true);

  const reader=new FileReader();
  reader.onload=async()=>{
   try{
    await api("/api/administration/logo",{
     method:"PUT",
     body:JSON.stringify({
      content_base64:String(reader.result).split(",")[1],
      mime:file.type
     })
    });
    await loadCompanyLogo();
    notify("Logo gespeichert.");
   }catch(err){notify(err.message,true);}
  };
  reader.readAsDataURL(file);
 };
}


// BUHA_RECURRING_UI_382
async function recurringInvoices(){
 const root=$("content");
 const [templates,partners,products]=await Promise.all([
  api("/api/recurring-invoices"),
  api("/api/partners"),
  api("/api/products")
 ]);

 const customers=partners.filter(p=>p.is_customer && p.is_active);
 const articles=products.filter(p=>p.is_active);
 const pmap=new Map(partners.map(p=>[Number(p.id),p]));
 const amap=new Map(products.map(p=>[Number(p.id),p]));

 const fmtDate=value=>value?String(value).slice(0,10):"–";
 const fmtMoney=value=>euro(value||0);

 const productOptions=selected=>{
  return '<option value="">Artikel auswählen</option>'+
   articles.map(p=>
    '<option value="'+p.id+'"'+
    (Number(selected)===Number(p.id)?' selected':'')+'>'+
    esc((p.sku||"")+" – "+p.name+" ("+fmtMoney(p.net_price)+")")+
    '</option>'
   ).join("");
 };

 const customerOptions=selected=>{
  return '<option value="">Kunde auswählen</option>'+
   customers.map(p=>
    '<option value="'+p.id+'"'+
    (Number(selected)===Number(p.id)?' selected':'')+'>'+
    esc((p.partner_number||p.id)+" – "+p.name)+
    '</option>'
   ).join("");
 };

 root.innerHTML=
  '<div class="panel">'+
   '<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">'+
    '<div><h2>Wiederkehrende Rechnungen</h2>'+
    '<p>Rechnungen werden zum jeweiligen Termin mit den aktuellen Artikelpreisen erstellt.</p></div>'+
    '<button type="button" id="rec-new">Neue Vorlage</button>'+
   '</div>'+
   '<div id="rec-editor" class="hidden"></div>'+
  '</div>'+
  '<div class="panel">'+
   '<h2>Gespeicherte Vorlagen</h2>'+
   table(
    ["Bezeichnung","Kunde","Intervall","Nächster Termin","Letzte Rechnung","Status","Aktionen"],
    templates.map(t=>{
     const customer=pmap.get(Number(t.partner_id));
     const interval=Number(t.interval_months)===12?"Jährlich":
      Number(t.interval_months)===1?"Monatlich":
      "Alle "+t.interval_months+" Monate";
     return '<tr>'+
      '<td>'+esc(t.name)+'</td>'+
      '<td>'+esc(customer?.name||"Kunde #"+t.partner_id)+'</td>'+
      '<td>'+esc(interval)+'</td>'+
      '<td>'+fmtDate(t.next_date)+'</td>'+
      '<td>'+fmtDate(t.last_generated_date)+'</td>'+
      '<td>'+esc(t.is_active?"Aktiv":"Pausiert")+'</td>'+
      '<td>'+
       '<button type="button" class="secondary rec-edit" data-id="'+t.id+'">Bearbeiten</button> '+
       '<button type="button" class="secondary rec-toggle" data-id="'+t.id+'">'+
        (t.is_active?"Pausieren":"Aktivieren")+'</button> '+
       '<button type="button" class="secondary rec-delete" data-id="'+t.id+'">Löschen</button>'+
      '</td>'+
     '</tr>';
    })
   )+
  '</div>';

 function addLine(productId="",quantity="1"){
  const container=$("rec-lines");
  const row=document.createElement("div");
  row.className="rec-line";
  row.style.cssText="display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin-bottom:12px";
  row.innerHTML=
   '<label style="flex:3;min-width:220px">Artikel'+
    '<select class="rec-product" required>'+productOptions(productId)+'</select>'+
   '</label>'+
   '<label style="flex:1;min-width:110px">Menge'+
    '<input class="rec-quantity" type="number" min="0.001" step="any" required value="'+
    esc(quantity)+'">'+
   '</label>'+
   '<button type="button" class="secondary rec-remove">Entfernen</button>';
  container.appendChild(row);
  row.querySelector(".rec-remove").onclick=()=>{
   if(container.children.length===1){
    notify("Mindestens eine Rechnungsposition erforderlich.",true);
    return;
   }
   row.remove();
  };
 }

 function openEditor(template=null){
  const editor=$("rec-editor");
  editor.classList.remove("hidden");

  const t=template||{};
  const interval=Number(t.interval_months||1);
  const preset=[1,2,3,6,12].includes(interval)?String(interval):"custom";

  editor.innerHTML=
   '<h3>'+(template?"Vorlage bearbeiten":"Neue Vorlage")+'</h3>'+
   '<form id="rec-form">'+
    '<div class="form-grid">'+
     field("name","Bezeichnung","text",t.name||"")+
     '<label>Kunde<select name="partner_id" required>'+
      customerOptions(t.partner_id)+'</select></label>'+
     '<label>Wiederholung<select name="interval_preset">'+
      [
       ["1","Monatlich"],
       ["2","Alle 2 Monate"],
       ["3","Vierteljährlich"],
       ["6","Halbjährlich"],
       ["12","Jährlich"],
       ["custom","Individuell"]
      ].map(([v,label])=>
       '<option value="'+v+'"'+(v===preset?' selected':'')+'>'+label+'</option>'
      ).join("")+
     '</select></label>'+
     field("interval_months","Intervall in Monaten","number",interval)+
     field("start_date","Startdatum","date",fmtDate(t.start_date)==="–"?
      new Date().toLocaleDateString("en-CA"):fmtDate(t.start_date))+
     field("end_date","Enddatum (optional)","date",fmtDate(t.end_date)==="–"?
      "":fmtDate(t.end_date))+
     field("due_days","Zahlungsziel in Tagen","number",t.due_days??14)+
     field("xrechnung_buyer_reference","Leitweg-ID / Käuferreferenz (optional)",
      "text",t.xrechnung_buyer_reference||"")+
    '</div>'+
    '<label>Bemerkung<textarea name="notes">'+esc(t.notes||"")+'</textarea></label>'+
    '<label><input type="checkbox" name="xrechnung_enabled"'+
     (t.xrechnung_enabled?' checked':'')+'> XRechnung zusätzlich versenden</label>'+
    '<label><input type="checkbox" name="is_active"'+
     (t.is_active!==false?' checked':'')+'> Vorlage aktiv</label>'+
    '<h3>Rechnungspositionen</h3>'+
    '<p>Gespeichert werden ausschließlich Artikelreferenz und Menge. Preis, Steuer und Beschreibung stammen bei jeder Rechnung aus dem aktuellen Artikelstamm.</p>'+
    '<div id="rec-lines"></div>'+
    '<button type="button" class="secondary" id="rec-add-line">Position hinzufügen</button>'+
    '<div style="display:flex;gap:12px;margin-top:20px">'+
     '<button type="submit">Vorlage speichern</button>'+
     '<button type="button" class="secondary" id="rec-cancel">Abbrechen</button>'+
    '</div>'+
   '</form>';

  const lines=t.lines?.length?t.lines:[{product_id:"",quantity:1}];
  lines.forEach(l=>addLine(l.product_id,l.quantity));

  $("rec-add-line").onclick=()=>addLine();
  $("rec-cancel").onclick=()=>editor.classList.add("hidden");

  const form=$("rec-form");
  const presetInput=form.elements.namedItem("interval_preset");
  const intervalInput=form.elements.namedItem("interval_months");

  presetInput.onchange=()=>{
   if(presetInput.value!=="custom"){
    intervalInput.value=presetInput.value;
   }
  };

  form.onsubmit=async event=>{
   event.preventDefault();

   const get=name=>form.elements.namedItem(name);
   const lines=[...editor.querySelectorAll(".rec-line")].map(row=>({
    product_id:Number(row.querySelector(".rec-product").value),
    quantity:Number(row.querySelector(".rec-quantity").value)
   }));

   const intervalMonths=Number(intervalInput.value);
   const dueDays=Number(get("due_days").value);

   if(!get("name").value.trim() || !Number(get("partner_id").value)){
    notify("Bezeichnung und Kunde sind erforderlich.",true);
    return;
   }
   if(!Number.isInteger(intervalMonths)||intervalMonths<1){
    notify("Das Intervall muss mindestens einen Monat betragen.",true);
    return;
   }
   if(!Number.isInteger(dueDays)||dueDays<0){
    notify("Das Zahlungsziel muss eine nichtnegative ganze Zahl sein.",true);
    return;
   }
   if(lines.some(l=>!l.product_id||!Number.isFinite(l.quantity)||l.quantity<=0)){
    notify("Bitte alle Artikel und Mengen prüfen.",true);
    return;
   }

   const payload={
    name:get("name").value.trim(),
    partner_id:Number(get("partner_id").value),
    notes:get("notes").value,
    interval_months:intervalMonths,
    start_date:get("start_date").value,
    end_date:get("end_date").value||null,
    due_days:dueDays,
    is_active:get("is_active").checked,
    xrechnung_enabled:get("xrechnung_enabled").checked,
    xrechnung_buyer_reference:get("xrechnung_buyer_reference").value.trim()||null,
    lines
   };

   if(payload.end_date && payload.end_date<payload.start_date){
    notify("Enddatum darf nicht vor dem Startdatum liegen.",true);
    return;
   }

   try{
    await api(
     template?"/api/recurring-invoices/"+template.id:"/api/recurring-invoices",
     {
      method:template?"PUT":"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload)
     }
    );
    notify("Wiederkehrende Rechnung gespeichert.");
    await recurringInvoices();
   }catch(error){
    notify(error.message,true);
   }
  };

  editor.scrollIntoView({behavior:"smooth",block:"start"});
 }

 $("rec-new").onclick=()=>openEditor();

 root.querySelectorAll(".rec-edit").forEach(button=>{
  button.onclick=()=>{
   const template=templates.find(t=>Number(t.id)===Number(button.dataset.id));
   if(template)openEditor(template);
  };
 });

 root.querySelectorAll(".rec-toggle").forEach(button=>{
  button.onclick=async()=>{
   const template=templates.find(t=>Number(t.id)===Number(button.dataset.id));
   if(!template)return;
   try{
    await api("/api/recurring-invoices/"+template.id+"/active",{
     method:"PATCH",
     headers:{"Content-Type":"application/json"},
     body:JSON.stringify({is_active:!template.is_active})
    });
    await recurringInvoices();
   }catch(error){
    notify(error.message,true);
   }
  };
 });

 root.querySelectorAll(".rec-delete").forEach(button=>{
  button.onclick=async()=>{
   const template=templates.find(t=>Number(t.id)===Number(button.dataset.id));
   if(!template)return;
   if(!confirm(
    'Vorlage "'+template.name+'" wirklich löschen? Bereits erzeugte Rechnungen bleiben erhalten.'
   ))return;
   try{
    await api("/api/recurring-invoices/"+template.id,{
     method:"DELETE"
    });
    await recurringInvoices();
   }catch(error){
    notify(error.message,true);
   }
  };
 });
}
