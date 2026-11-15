
"use strict";

// BUHA_INVOICE_MAIL_UI_169E
(function(){
 let currentInvoiceId=null;
 let renderGeneration=0;

 function getInvoiceId(){
  const editor=document.getElementById("invoice-editor");
  if(!editor)return null;

  const pdfButton=editor.querySelector("#download-invoice-pdf");
  if(!pdfButton)return null;

  const detailHeading=editor.querySelector("h2");
  if(!detailHeading)return null;

  const rows=[...editor.querySelectorAll("table tr")];
  const invoiceRow=rows.find(row=>
   row.cells?.[0]?.textContent?.trim()==="Rechnungsnummer"
  );

  if(!invoiceRow)return null;

  const number=invoiceRow.cells?.[1]?.textContent?.trim();
  if(!number)return null;

  return {number,editor};
 }

 async function initialize(){
  const detail=getInvoiceId();

  if(!detail){
   currentInvoiceId=null;
   return;
  }

  const generation=++renderGeneration;

  if(detail.editor.querySelector("#send-invoice-email"))return;

  const close=detail.editor.querySelector("#close-invoice-detail");
  if(!close)return;

  let invoice;

  try{
   const list=await api("/api/invoices");
   invoice=list.find(item=>
    item.invoice_number===detail.number &&
    item.invoice_type==="outgoing" &&
    item.status!=="draft"
   );
  }catch(error){
   return;
  }

  if(generation!==renderGeneration)return;
  if(!invoice||!detail.editor.isConnected)return;
  if(detail.editor.querySelector("#send-invoice-email"))return;

  const button=document.createElement("button");
  button.type="button";
  button.id="send-invoice-email";
  button.textContent="Per E-Mail versenden";

  close.parentNode.insertBefore(button,close);

  const panel=document.createElement("div");
  panel.className="panel";
  panel.innerHTML=
   '<h3>E-Mail-Versandhistorie</h3>'+
   '<div id="invoice-email-history">Wird geladen ...</div>';

  detail.editor.appendChild(panel);

  async function refreshHistory(){
   const target=panel.querySelector("#invoice-email-history");
   try{
    const entries=await api(
     "/api/invoices/"+invoice.id+"/email-history"
    );

    if(!panel.isConnected)return;

    target.innerHTML=entries.length
     ?table(
      ["Zeitpunkt","Empfänger","Versandart","Status","Hinweis"],
      entries.map(entry=>
       '<tr><td>'+esc(entry.completed_at||entry.created_at||"–")+'</td>'+
       '<td>'+esc(entry.recipient||"–")+'</td>'+
       '<td>'+esc(entry.delivery_type==="automatic"?"Automatisch":"Manuell")+'</td>'+
       '<td>'+esc(entry.status==="sent"?"SMTP angenommen":
        entry.status==="failed"?"Fehlgeschlagen":"Ausstehend")+'</td>'+
       '<td>'+esc(entry.error_message||"–")+'</td></tr>'
      )
     )
     :'<p class="muted">Noch keine Versandversuche.</p>';
   }catch(error){
    if(panel.isConnected)target.textContent=error.message;
   }
  }

  button.onclick=async()=>{
   const recipient=invoice.partner_email||"";

   if(!confirm(
    "Rechnung "+invoice.invoice_number+
    " jetzt per E-Mail versenden?"
   ))return;

   button.disabled=true;

   try{
    const result=await api(
     "/api/invoices/"+invoice.id+"/send-email",
     {method:"POST"}
    );
    notify(
     "Rechnung an "+result.recipient+
     " an SMTP-Server übergeben."
    );
   }catch(error){
    notify(error.message,true);
   }finally{
    button.disabled=false;
    await refreshHistory();
   }
  };

  await refreshHistory();
 }

 let pending=false;

 const observer=new MutationObserver(()=>{
  if(pending)return;
  pending=true;

  queueMicrotask(()=>{
   pending=false;
   const editor=document.getElementById("invoice-editor");
   if(!editor)return;

   const detail=getInvoiceId();

   if(!detail){
    currentInvoiceId=null;
    renderGeneration++;
    return;
   }

   if(currentInvoiceId!==detail.number){
    currentInvoiceId=detail.number;
    void initialize();
   }
  });
 });

 observer.observe(document.body,{
  childList:true,
  subtree:true
 });

 if(document.readyState==="loading"){
  document.addEventListener("DOMContentLoaded",()=>{
   void initialize();
  },{once:true});
 }else{
  void initialize();
 }
})();
