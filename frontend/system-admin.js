"use strict";

async function systemAdministration(){
  if(state.user?.role!=="system_admin"){
    $("content").innerHTML="<p>Keine Berechtigung.</p>";
    return;
  }

  const [tenants,users]=await Promise.all([
    api("/api/system/tenants"),
    api("/api/system/users")
  ]);

  const tenantOptions=tenants.filter(t=>t.is_active).map(t=>
    '<option value="'+Number(t.id)+'">'+esc(t.name)+' ('+esc(t.code)+')</option>'
  ).join("");

  const tenantRows=tenants.map(t=>
    '<tr><td>'+esc(t.code)+'</td><td>'+esc(t.name)+'</td>'+
    '<td>'+esc(t.tenant_type==="vermieter"?"Vermieter":"Unternehmen")+'</td>'+
    '<td>'+esc(t.is_active?"Aktiv":"Inaktiv")+'</td>'+
    '<td><button type="button" data-tenant-edit="'+Number(t.id)+'">Bearbeiten</button></td></tr>'
  );

  const userRows=users.map(u=>
    '<tr><td>'+esc(u.username)+'</td><td>'+esc(u.email)+'</td>'+
    '<td>'+esc(u.is_active?"Aktiv":"Inaktiv")+'</td>'+
    '<td>'+esc((u.tenants||[]).map(t=>t.tenant_name+" ("+t.role+")").join(", "))+'</td>'+
    '<td><button type="button" data-user-edit="'+Number(u.id)+'">Bearbeiten</button> '+
    '<button type="button" data-user-password="'+Number(u.id)+'">Passwort</button></td></tr>'
  );

  $("content").innerHTML=
    '<div class="panel"><h2>Mandantenverwaltung</h2>'+
    table(["Code","Name","Typ","Status","Aktionen"],tenantRows)+
    '<h3>Mandant anlegen</h3>'+
    '<form id="system-tenant-form"><div class="grid-form">'+
    field("code","Mandantencode")+
    field("name","Mandantenname")+
    field("tenant_type","Mandantentyp","select","unternehmen",[
      ["unternehmen","Unternehmen"],["vermieter","Vermieter"]
    ])+
    '</div><button>Mandant anlegen</button></form></div>'+
    '<div class="panel"><h2>Benutzerverwaltung</h2>'+
    '<div id="system-users">'+
    table(["Benutzer","E-Mail","Status","Mandanten","Aktionen"],userRows)+
    '</div>'+
    '<h3>Benutzer anlegen</h3>'+
    '<form id="system-user-form"><div class="grid-form">'+
    field("username","Benutzername")+
    field("email","E-Mail")+
    field("password","Passwort","password")+
    '<label>Mandant<select name="tenant_id">'+tenantOptions+'</select></label>'+
    field("role","Mandantenrolle","select","user",[
      ["admin","Administrator"],["user","Benutzer"]
    ])+
    '</div><button>Benutzer anlegen</button></form></div>';

  function assignmentFields(user){
    const assigned=new Map((user.tenants||[]).map(t=>
      [Number(t.tenant_id),t.role]
    ));
    return tenants.map(t=>{
      const role=assigned.get(Number(t.id));
      return '<div class="system-assignment" style="display:flex;gap:12px;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid #ddd">'+
        '<label style="flex:1"><input type="checkbox" data-assignment-id="'+Number(t.id)+'" '+
        (role?'checked ':'')+
        (!t.is_active&&!role?'disabled ':'')+
        '> '+esc(t.name)+' ('+esc(t.code)+')'+
        (!t.is_active?' – Inaktiv':'')+'</label>'+
        '<select data-assignment-role="'+Number(t.id)+'">'+
        '<option value="user"'+(role!=="admin"?' selected':'')+'>Benutzer</option>'+
        '<option value="admin"'+(role==="admin"?' selected':'')+'>Administrator</option>'+
        '</select></div>';
    }).join("");
  }

  function readAssignments(form){
    return [...form.querySelectorAll("[data-assignment-id]:checked")].map(cb=>{
      const id=Number(cb.dataset.assignmentId);
      return {
        tenant_id:id,
        role:form.querySelector('[data-assignment-role="'+id+'"]').value
      };
    });
  }

  function showEditor(title,html,onSave){
    const panel=document.createElement("div");
    panel.className="panel";
    panel.style.marginTop="16px";
    panel.innerHTML='<h3>'+esc(title)+'</h3>'+
      '<form id="system-editor-form">'+html+
      '<div style="display:flex;gap:10px;margin-top:16px">'+
      '<button type="submit">Änderungen speichern</button>'+
      '<button type="button" id="system-editor-cancel">Abbrechen</button>'+
      '</div></form>';
    $("content").prepend(panel);
    panel.querySelector("#system-editor-cancel").onclick=()=>panel.remove();
    panel.querySelector("form").onsubmit=async e=>{
      e.preventDefault();
      try{
        await onSave(e.target);
        await systemAdministration();
        notify("Änderungen gespeichert.");
      }catch(err){notify(err.message,true);}
    };
    panel.scrollIntoView({behavior:"smooth",block:"start"});
  }

  $("system-tenant-form").onsubmit=async e=>{
    e.preventDefault();
    const data=Object.fromEntries(new FormData(e.target));
    try{
      await api("/api/system/tenants",{
        method:"POST",body:JSON.stringify(data)
      });
      await systemAdministration();
      notify("Mandant angelegt.");
    }catch(err){notify(err.message,true);}
  };

  $("system-user-form").onsubmit=async e=>{
    e.preventDefault();
    const data=Object.fromEntries(new FormData(e.target));
    try{
      await api("/api/system/users",{
        method:"POST",
        body:JSON.stringify({
          username:data.username,
          email:data.email,
          password:data.password,
          tenants:[{
            tenant_id:Number(data.tenant_id),
            role:data.role
          }]
        })
      });
      await systemAdministration();
      notify("Benutzer angelegt.");
    }catch(err){notify(err.message,true);}
  };

  $("content").querySelectorAll("[data-tenant-edit]").forEach(button=>{
    button.onclick=()=>{
      const tenant=tenants.find(t=>Number(t.id)===Number(button.dataset.tenantEdit));
      if(!tenant)return;
      showEditor("Mandant bearbeiten: "+tenant.name,
        '<div class="grid-form">'+
        '<label>Mandantencode<input name="code" required value="'+esc(tenant.code)+'"></label>'+
        '<label>Mandantenname<input name="name" required value="'+esc(tenant.name)+'"></label>'+
        '<label>Mandantentyp<input disabled value="'+esc(tenant.tenant_type)+'"></label>'+
        '<label>Status<select name="is_active">'+
        '<option value="true"'+(tenant.is_active?' selected':'')+'>Aktiv</option>'+
        '<option value="false"'+(!tenant.is_active?' selected':'')+'>Inaktiv</option>'+
        '</select></label></div>',
        async form=>{
          const data=Object.fromEntries(new FormData(form));
          await api("/api/system/tenants/"+tenant.id,{
            method:"PATCH",
            body:JSON.stringify({
              code:data.code,
              name:data.name,
              is_active:data.is_active==="true"
            })
          });
        }
      );
    };
  });

  $("system-users").onclick=async e=>{
    const edit=e.target.closest("[data-user-edit]");
    const password=e.target.closest("[data-user-password]");

    if(password){
      const id=Number(password.dataset.userPassword);
      const value=prompt("Neues Passwort (mindestens 12 Zeichen)");
      if(value===null)return;
      if(value.length<12){
        notify("Passwort muss mindestens 12 Zeichen haben.",true);
        return;
      }
      try{
        await api("/api/system/users/"+id+"/password",{
          method:"PATCH",
          body:JSON.stringify({password:value})
        });
        notify("Passwort aktualisiert. Bestehende Sitzungen widerrufen.");
      }catch(err){notify(err.message,true);}
      return;
    }

    if(edit){
      const id=Number(edit.dataset.userEdit);
      const user=users.find(u=>Number(u.id)===id);
      if(!user)return;

      showEditor("Benutzer bearbeiten: "+user.username,
        '<div class="grid-form">'+
        '<label>Benutzername<input name="username" required value="'+esc(user.username)+'"></label>'+
        '<label>E-Mail<input name="email" type="email" required value="'+esc(user.email)+'"></label>'+
        '<label>Status<select name="is_active">'+
        '<option value="true"'+(user.is_active?' selected':'')+'>Aktiv</option>'+
        '<option value="false"'+(!user.is_active?' selected':'')+'>Inaktiv</option>'+
        '</select></label></div>'+
        '<h4>Mandantenzuordnungen</h4>'+
        '<p>Mandanten auswählen und je Mandant die Berechtigung festlegen.</p>'+
        assignmentFields(user),
        async form=>{
          const data=Object.fromEntries(new FormData(form));
          await api("/api/system/users/"+id,{
            method:"PATCH",
            body:JSON.stringify({
              username:data.username,
              email:data.email,
              is_active:data.is_active==="true",
              tenants:readAssignments(form)
            })
          });
        }
      );
    }
  };
}
