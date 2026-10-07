'use strict';
/* QA79: Windows-native White/Red Hat diagnostic profiles. No Kali, SSH worker or arbitrary shell input. */
(()=>{
  if(window.__naWindowsTools79Installed)return;window.__naWindowsTools79Installed=true;
  tr.wintools79='Windows Local Tools · Mũ trắng';navIcon.wintools79='▣';
  tr.redlocal79='Windows Local Lab · Mũ đỏ';navIcon.redlocal79='▤';

  const canRun=()=>['Admin','Analyst','Operator'].includes(state.user?.role);
  const profileLabels={
    system_overview:'Tổng quan Windows',ping:'Ping',dns_lookup:'Tra cứu DNS',tcp_port:'Kiểm tra cổng TCP',route_table:'Bảng định tuyến',arp_table:'ARP / Neighbor',tcp_connections:'Kết nối TCP',http_head:'HTTP/HTTPS headers',tls_certificate:'TLS / Certificate',file_hash:'SHA-256 file',processes:'Tiến trình',services:'Dịch vụ Windows',firewall:'Windows Firewall',windows_events:'Windows Event Log',adapters:'Card mạng / IP',traceroute:'Traceroute',server_status:'Trạng thái máy chủ',network_state:'Trạng thái mạng cục bộ',
    red_recon:'Recon an toàn một host private',red_config_audit:'Kiểm tra cấu hình Windows',red_connectivity:'Connectivity private host/port',red_http_headers:'HTTP headers private URL',red_tls_audit:'TLS/certificate private host',red_cookie_audit:'Session/Cookie audit',red_network_state:'Packet/Network state cục bộ',red_light_load:'Tải nhẹ private URL (1–5 HEAD)'
  };
  const result=(title,r)=>panel(title,`<div class="cards">${metric('Trạng thái',r.ok?'Đạt':'Lỗi',r.ok?'green':'red')}${metric('Mã thoát',r.exit_code??'—')}${metric('Engine',r.engine||r.backend||'Windows')}${metric('Thời gian',`${r.elapsed_ms??0} ms`)}</div><pre style="max-height:460px;overflow:auto;white-space:pre-wrap">${esc((r.stdout||'')+(r.stderr?'\n[stderr]\n'+r.stderr:''))}</pre>`);
  const fields=(mode)=>`<div class="form-grid">${select('Tác vụ','profile',(mode==='white'?[
    'system_overview','ping','dns_lookup','tcp_port','route_table','arp_table','tcp_connections','http_head','tls_certificate','file_hash','processes','services','firewall','windows_events','adapters','traceroute','server_status','network_state'
  ]:[
    'red_recon','red_config_audit','red_connectivity','red_http_headers','red_tls_audit','red_cookie_audit','red_network_state','red_light_load'
  ]),mode==='white'?'system_overview':'red_recon')}${input('Mục tiêu / URL / đường dẫn file','target','text',mode==='white'?'192.168.1.1':'192.168.1.1')}${input('Cổng','port','number',443)}${input('Số request tải nhẹ (1–5)','count','number',3)}</div><label>Cookie/header text (chỉ dùng cho Session/Cookie audit)<textarea name="text" rows="5" placeholder="session=redacted; Secure; HttpOnly; SameSite=Lax"></textarea></label>`;
  const noteWhite=`<p class="caption">Backend chỉ cho chạy profile whitelist. Không có ô nhập lệnh PowerShell/CMD tùy ý. Tác vụ mạng chủ động bị giới hạn vào host/URL private; PowerShell/CMD chạy ẩn, có timeout và giới hạn output.</p>`;
  const noteRed=`<p class="caption">Mũ đỏ chỉ dùng cho kiểm thử được ủy quyền: private-host reconnaissance, connectivity, headers, TLS, cookie audit, trạng thái mạng cục bộ và tối đa 5 HEAD request tuần tự. Không có exploit, brute-force, persistence, shell tùy ý hoặc flood.</p>`;

  pages.wintools79=async()=>`<div class="mode-hero61 white"><div><div class="eyebrow">HACKER MŨ TRẮNG · WINDOWS LOCAL</div><h2>Windows Local Tools / PowerShell Engine</h2><p>Kiểm tra mạng, hệ điều hành và dịch vụ trực tiếp trên máy Windows chạy NetworkAutomation — không cần Kali Linux, SSH hay VM.</p></div><span class="mode-shield61">▣</span></div>${panel('Chạy tác vụ Windows whitelist',canRun()?`<form id="wintools79-form">${fields('white')}<div class="toolbar"><button class="primary" type="submit">Chạy tác vụ</button></div></form><div id="wintools79-result"></div>${noteWhite}`:'<p class="caption">Viewer chỉ được xem trạng thái; Admin/Analyst/Operator mới được chạy tác vụ.</p>')}`;

  pages.redlocal79=async()=>`<div class="mode-hero61 red"><div><div class="eyebrow">HACKER MŨ ĐỎ · WINDOWS LOCAL LAB</div><h2>Windows Red-Team Diagnostic Lab</h2><p>Reconnaissance và kiểm thử cấu hình an toàn bằng profile Windows đã giới hạn, trên hệ thống bạn được phép kiểm tra.</p></div><span class="mode-shield61">▤</span></div>${panel('Tác vụ Mũ đỏ an toàn',canRun()?`<form id="redlocal79-form">${fields('red')}<div class="toolbar"><button class="primary" type="submit">Chạy kiểm thử an toàn</button></div></form><div id="redlocal79-result"></div>${noteRed}`:'<p class="caption">Viewer không có quyền chạy tác vụ chủ động.</p>')}`;

  async function submitTool(form,mode,outId){const v=vals(form),out=$(outId);out.innerHTML='<div class="loading">Windows đang thực thi tác vụ…</div>';try{const r=await api('/v1/windows-tools/run',{method:'POST',body:JSON.stringify({mode,profile:v.profile,target:v.target||null,port:Number(v.port||443),text:v.text||null,count:Number(v.count||3)})});out.innerHTML=result('Kết quả Windows Local Tools',r)}catch(e){out.innerHTML=panel('Không chạy được',`<pre>${esc(e.message||String(e))}</pre>`)}}
  forms['wintools79-form']=async f=>submitTool(f,'white','#wintools79-result');
  forms['redlocal79-form']=async f=>submitTool(f,'red','#redlocal79-result');

  const appendTool=(page,mode,profile,label,fieldsHtml)=>{const old=pages[page];if(typeof old!=='function')return;pages[page]=async()=>{const html=await old();if(!canRun())return html;return html+panel(mode==='white'?'▣ Windows Local Tools · Mũ trắng':'▤ Windows Local Lab · Mũ đỏ',`<form id="win79-${page}">${fieldsHtml}<input type="hidden" name="profile" value="${profile}"><div class="toolbar"><button class="primary" type="submit">${label}</button><button type="button" data-action="page" data-page="${mode==='white'?'wintools79':'redlocal79'}">Mở trung tâm Windows</button></div></form><div id="win79-${page}-result"></div>${mode==='white'?noteWhite:noteRed}`)};forms[`win79-${page}`]=async f=>{const v=vals(f),out=$(`#win79-${page}-result`);out.innerHTML='<div class="loading">Đang chạy tác vụ Windows…</div>';try{const r=await api('/v1/windows-tools/run',{method:'POST',body:JSON.stringify({mode,profile,target:v.target||v.url||'',port:Number(v.port||443),text:v.text||v.cookie||'',count:Number(v.count||3)})});out.innerHTML=result('Kết quả',r)}catch(e){out.innerHTML=panel('Không chạy được',`<pre>${esc(e.message||String(e))}</pre>`)}}};

  // White Hat integrations.
  appendTool('bluetls62','white','tls_certificate','Kiểm tra TLS bằng Windows',`${input('Private IP/hostname','target','text','192.168.1.1')}${input('Cổng','port','number',443)}`);
  appendTool('blueweb61','white','http_head','Đọc HTTP headers bằng Windows',input('Private URL','target','text','https://192.168.1.1/'));
  appendTool('bluefirewall62','white','firewall','Đọc Windows Firewall','');
  appendTool('bluelog61','white','windows_events','Đọc System Event Log 24 giờ','');
  appendTool('bluefim62','white','file_hash','Tính SHA-256 file',input('Đường dẫn file Windows','target','text','C:\\path\\file.exe'));

  // Red Hat safe diagnostic integrations.
  appendTool('redpacket61','red','red_network_state','Đọc trạng thái mạng cục bộ','');
  appendTool('redsession62','red','red_cookie_audit','Kiểm tra thuộc tính cookie',`<label>Set-Cookie mẫu<textarea name="text" rows="5" placeholder="session=redacted; Secure; HttpOnly; SameSite=Lax"></textarea></label>`);
  appendTool('redmitm62','red','red_tls_audit','Kiểm tra TLS private host',`${input('Private IP/hostname','target','text','192.168.1.1')}${input('Cổng','port','number',443)}`);
  appendTool('redload61','red','red_light_load','Chạy tải nhẹ (tối đa 5 HEAD)',`${input('Private URL','target','text','https://192.168.1.1/')}${input('Số request','count','number',3)}`);

  document.addEventListener('na:page-rendered',e=>{const p=e.detail?.page,b=$('#breadcrumb');if(p==='wintools79'&&b)b.textContent='🛡 HACKER MŨ TRẮNG · WINDOWS LOCAL';if(p==='redlocal79'&&b)b.textContent='🥷 HACKER MŨ ĐỎ · WINDOWS LOCAL LAB';});
  window.naWindowsTools79={version:NA_UI_VERSION,backend:'windows-local',arbitrary_shell:false,whiteProfiles:18,redProfiles:8};
})();
