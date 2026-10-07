'use strict';
/* Kali Linux integration. Active execution is available only from White Hat
   defensive pages. Red/Black Hat receives configuration-only access. */
(()=>{
  if(window.__naKali63Installed)return;window.__naKali63Installed=true;
  tr.kali63='Kali Linux · Mũ trắng'; navIcon.kali63='🐉';
  tr.kaliconfig63='Cấu hình kết nối Kali Linux'; navIcon.kaliconfig63='⚙';

  const resultBox=(title,r)=>panel(title,`<div class="mode-result61"><div class="cards">${metric('Mã thoát',r.exit_code??'—',r.ok?'green':'red')}${metric('Máy thực thi',r.backend||'Kali SSH')}</div><pre style="max-height:420px;overflow:auto;white-space:pre-wrap">${esc((r.stdout||'')+(r.stderr?'\n[stderr]\n'+r.stderr:''))}</pre></div>`);
  const configFields=(c,prefix='kali63',allowImport=true)=>`<div class="form-grid">${input('IP/Hostname Kali','host','text',c.host||'')}${input('Cổng SSH','port','number',c.port||22)}${input('Tên đăng nhập','username','text',c.username||'kali')}${input('Mật khẩu (để trống nếu đã lưu)','password','password','')}${input('SSH host key SHA256','hostkey_sha256','text',c.hostkey_sha256||'')}</div><label class="check"><input name="enabled" type="checkbox" ${c.enabled?'checked':''}> Bật kết nối Kali</label>${allowImport?`<input id="${prefix}-import-file" type="file" accept=".json,application/json" class="hidden">`:''}`;
  const importHelp=`<p class="caption">Có thể nhập file JSON cấu hình gồm host, port, username, hostkey_sha256, enabled. Vì an toàn, mật khẩu không được lấy từ file import; nhập trực tiếp rồi lưu nếu cần.</p>`;
  async function loadConfig(){let c={enabled:false,host:'',port:22,username:'kali',hostkey_sha256:''};if(isAdmin()){try{c=await api('/v1/kali/config')}catch{}}return c;}
  function fillConfigForm(form,obj={}){if(!form)return;for(const key of ['host','port','username','hostkey_sha256'])if(form.elements[key]&&obj[key]!=null)form.elements[key].value=obj[key];if(form.elements.enabled&&obj.enabled!=null)form.elements.enabled.checked=!!obj.enabled;}
  async function importConfig(file,form,resultSelector){if(!file)return;let obj;try{obj=JSON.parse(await file.text())}catch{throw new Error('File cấu hình Kali không phải JSON hợp lệ.')}if(!obj||typeof obj!=='object'||Array.isArray(obj))throw new Error('Cấu hình Kali phải là một object JSON.');fillConfigForm(form,obj);const host=document.querySelector(resultSelector);if(host)host.innerHTML=panel('Đã nhập cấu hình',kv({host:obj.host||'',port:obj.port||22,username:obj.username||'',hostkey_sha256:obj.hostkey_sha256||'',enabled:!!obj.enabled,note:'Mật khẩu không được import từ file.'}));}
  async function saveConfig(form,resultSelector){const v=vals(form);const body={host:v.host,port:Number(v.port||22),username:v.username,password:v.password||null,hostkey_sha256:v.hostkey_sha256,enabled:!!form.elements.enabled.checked};const r=await api('/v1/kali/config',{method:'POST',body:JSON.stringify(body)});const host=$(resultSelector);if(host)host.innerHTML=panel('Đã lưu cấu hình Kali',kv(r));toast('Đã lưu cấu hình Kali');return r;}

  pages.kali63=async()=>{
    const admin=isAdmin(),runner=canWrite(),c=await loadConfig();
    const configBody=admin?`<form id="kali63-form">${configFields(c,'kali63')}<div class="toolbar"><button type="button" id="kali63-import">Nhập cấu hình JSON</button><button type="button" id="kali63-probe">Lấy fingerprint</button><button class="primary" type="submit">Lưu cấu hình</button><button type="button" id="kali63-test">Kiểm tra kết nối</button><button type="button" id="kali63-tools">Kiểm tra công cụ</button></div>${importHelp}</form><div id="kali63-config-result"></div>`:`<p class="caption">Chỉ Admin được thay đổi cấu hình Kali. Operator có thể chạy tác vụ phòng thủ đã giới hạn.</p><div class="toolbar">${runner?'<button type="button" id="kali63-test">Kiểm tra kết nối</button><button type="button" id="kali63-tools">Kiểm tra công cụ</button>':''}</div><div id="kali63-config-result"></div>`;
    const runBody=runner?`<form id="kali63-run"><div class="form-grid">${select('Hồ sơ','profile',['network_discovery','port_service_scan','tls_audit','web_headers','worker_network_state'],'network_discovery')}${input('IP/CIDR riêng hoặc URL riêng','target','text','192.168.1.0/24')}${input('Cổng (TLS)','port','number',443)}</div><div class="toolbar"><button class="primary" type="submit">Chạy phòng thủ trên Kali</button></div></form><div id="kali63-run-result"></div><p class="caption">Chỉ mục tiêu private được chấp nhận. Không có exploit, brute-force, pivot, persistence hay flood.</p>`:`<p class="caption">Tài khoản ${esc(state.user?.role||'hiện tại')} không có quyền chạy Kali.</p>`;
    return `<div class="mode-hero61 white"><div><div class="eyebrow">HACKER MŨ TRẮNG · KALI LINUX</div><h2>Tích hợp Kali Linux cho phòng thủ</h2><p>Nhập/cấu hình máy Kali rồi dùng làm execution worker cho các tác vụ kiểm tra phòng thủ được cấp phép.</p></div></div>`+panel('Kết nối / nhập cấu hình Kali',configBody)+panel('Chạy tác vụ phòng thủ bằng Kali',runBody);
  };

  // Red/Black Hat is configuration only. No Kali run/test/tools controls are exposed here.
  pages.kaliconfig63=async()=>{
    const c=await loadConfig();
    if(!isAdmin())return panel('Cấu hình Kali Linux','<p class="caption">Chỉ Admin được tạo hoặc sửa cấu hình kết nối Kali. Khu vực Mũ đỏ không chạy lệnh Kali.</p>');
    return `<div class="mode-hero61 red"><div><div class="eyebrow">HACKER MŨ ĐỎ/ĐEN · CẤU HÌNH</div><h2>Cấu hình kết nối Kali Linux</h2><p>Trang này chỉ tạo/lưu cấu hình SSH đến Kali Linux. Không có nút chạy lệnh, quét hay công cụ Kali trong khu vực này.</p></div></div>`+panel('Cấu hình kết nối',`<form id="kali63-red-form">${configFields(c,'kali63-red',false)}<div class="toolbar"><button class="primary" type="submit">Lưu cấu hình</button></div><p class="caption">Khu vực Mũ đỏ/Đen chỉ lưu cấu hình kết nối Kali; không nhập file cấu hình và không chạy công cụ Kali.</p></form><div id="kali63-red-result"></div>`);
  };

  forms['kali63-form']=async f=>saveConfig(f,'#kali63-config-result');
  forms['kali63-red-form']=async f=>saveConfig(f,'#kali63-red-result');
  forms['kali63-run']=async f=>{const v=vals(f),out=$('#kali63-run-result');out.innerHTML='<div class="loading">Kali đang thực thi tác vụ…</div>';try{const r=await api('/v1/kali/run',{method:'POST',body:JSON.stringify({profile:v.profile,target:v.target,port:Number(v.port||443)})});out.innerHTML=resultBox('Kết quả Kali',r)}catch(e){out.innerHTML=panel('Lỗi',`<pre>${esc(e.message||String(e))}</pre>`)}};

  document.addEventListener('click',async e=>{
    if(e.target?.id==='kali63-import'){$('#kali63-import-file')?.click();return;}
    if(e.target?.id==='kali63-probe'){const f=$('#kali63-form'),v=vals(f);try{const r=await api(`/v1/kali/probe-hostkey?host=${encodeURIComponent(v.host)}&port=${encodeURIComponent(v.port||22)}`,{retry:false});f.elements.hostkey_sha256.value=r.sha256;$('#kali63-config-result').innerHTML=panel('SSH fingerprint',kv(r))}catch(err){toast(err.message||String(err),true)}}
    if(e.target?.id==='kali63-test'){try{const r=await api('/v1/kali/test',{method:'POST'});$('#kali63-config-result').innerHTML=resultBox('Kiểm tra kết nối',r)}catch(err){toast(err.message||String(err),true)}}
    if(e.target?.id==='kali63-tools'){try{const r=await api('/v1/kali/tools',{method:'POST',body:'{}'});$('#kali63-config-result').innerHTML=resultBox('Công cụ Kali',r)}catch(err){toast(err.message||String(err),true)}}
  });
  document.addEventListener('change',async e=>{try{if(e.target?.id==='kali63-import-file')await importConfig(e.target.files?.[0],$('#kali63-form'),'#kali63-config-result')}catch(err){toast(err.message||String(err),true)}finally{if(e.target?.type==='file')e.target.value=''}});

  // White Hat only: attach bounded Kali execution to defensive pages.
  const appendKali=(page,profile,label,targetHtml)=>{const old=pages[page];if(typeof old!=='function')return;pages[page]=async()=>{const html=await old();if(!canWrite())return html;return html+panel('🐉 Kali Linux · Mũ trắng',`<form id="kali63-${page}">${targetHtml}<input type="hidden" name="profile" value="${profile}"><div class="toolbar"><button class="primary" type="submit">${label}</button><button type="button" data-action="page" data-page="kali63">Cấu hình Kali</button></div></form><div id="kali63-${page}-result"></div><p class="caption">Tác vụ chạy qua SSH đã pin host key và chỉ chấp nhận private target.</p>`)};forms[`kali63-${page}`]=async f=>{const v=vals(f),out=$(`#kali63-${page}-result`);out.innerHTML='<div class="loading">Kali đang thực thi…</div>';try{const r=await api('/v1/kali/run',{method:'POST',body:JSON.stringify({profile,target:v.target||v.network||v.asset_ip||v.url||'',port:Number(v.port||443)})});out.innerHTML=resultBox('Kết quả Kali',r)}catch(e){out.innerHTML=panel('Kali lỗi',`<pre>${esc(e.message||String(e))}</pre>`)}}};
  appendKali('scan','network_discovery','Quét discovery bằng Kali',input('Private IPv4 CIDR','target','text','192.168.1.0/24'));
  appendKali('vuln51','port_service_scan','Quét service bằng Kali',input('Private IP/hostname','target','text','192.168.1.1'));
  appendKali('bluetls62','tls_audit','Kiểm tra TLS bằng Kali',`${input('Private IP/hostname','target','text','192.168.1.1')}${input('Cổng','port','number',443)}`);
  appendKali('blueweb61','web_headers','Kiểm tra headers bằng Kali',input('Private URL','target','text','https://192.168.1.1/'));
  document.addEventListener('na:page-rendered',e=>{const page=e.detail?.page,b=$('#breadcrumb');if(page==='kali63'&&b)b.textContent='🛡 HACKER MŨ TRẮNG · KALI';if(page==='kaliconfig63'&&b)b.textContent='🥷 HACKER MŨ ĐỎ/ĐEN · CHỈ CẤU HÌNH KALI';});
  window.naKali63={version:NA_UI_VERSION,mode:'white-execution-red-config-only',profiles:['network_discovery','port_service_scan','tls_audit','web_headers','worker_network_state']};
})();
