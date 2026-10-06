'use strict';
(function(){
  if(typeof pages==='undefined') return;
  window.__NA_DESKTOP70_LOADED__=true;
  tr.scan='Mạng Windows / ARP';

  function pingText70(r){
    if(!r)return 'Chưa đo';
    if(String(r.status||'').toLowerCase()==='online'){if(r.response==null)return 'Online';return r.response_is_upper_bound?`<${r.response} ms`:`${r.response} ms`;}
    return r.status||'Unknown';
  }
  function nativeCards70(n){
    const gp=n.gateway_ping||{};
    return `<div class="cards">${metric('Adapter',n.adapter||'—')}${metric('IP LAN',n.local_ip||'—',n.local_ip?'green':'')}${metric('Subnet',n.network||'—')}${metric('Gateway',n.gateway||'—')}${metric('Ping gateway',pingText70(gp),String(gp.status||'').toLowerCase()==='online'?'green':'amber')}${metric('ARP / Neighbor',n.arp_count??0,'green')}${metric('Ping Online',n.online_count==null?'—':n.online_count)}${metric('Internet',n.internet?'Online':'Chưa xác minh',n.internet?'green':'amber')}</div>`;
  }
  function arpTable70(rows){
    return table(rows||[],[
      ['IP','ip'],['MAC','mac'],['Vai trò','role',badge],['Ping','status',badge],
      ['Latency','latency_ms',(v,r)=>v==null?'—':(r.latency_is_upper_bound?'&lt;':'')+esc(v)+' ms'],['Loss','packet_loss',v=>v==null?'—':esc(v)+'%']
    ]);
  }
  async function native70(probe=true,force=false){
    return api(`/desktop/network-overview?probe=${probe?'true':'false'}&force=${force?'true':'false'}`,{retry:false});
  }

  const previousDashboard70=pages.dashboard;
  pages.dashboard=async()=>{
    const basePromise=previousDashboard70();
    let n=null,nativeError='';
    try{n=await native70(canWrite(),false)}catch(e){nativeError=e.message||String(e)}
    const base=await basePromise;
    if(!n)return `<div class="notice error"><b>Mạng Windows tạm chưa đọc được:</b> ${esc(nativeError)}. Dashboard chính vẫn hoạt động.</div>`+base;
    const rows=(n.devices||[]).slice(0,20);
    const bounded=n.probe_truncated?`<p class="caption">Ping được giới hạn ${esc(n.probe_limit)} thiết bị/lần để tránh quá tải. ARP vẫn hiển thị toàn bộ.</p>`:'';
    return `<div class="notice"><b>Desktop Native 7.0.3:</b> số liệu mạng bên dưới được đọc trực tiếp từ Windows trên máy đang chạy ứng dụng.${canWrite()?'':' Tài khoản chỉ đọc không tự phát ping.'}</div>`+
      nativeCards70(n)+bounded+
      panel('Thiết bị thấy trong ARP / Neighbor',arpTable70(rows),canWrite()?button('Làm mới mạng Windows','desktop70-refresh',{},'primary'):'')+
      (Number(n.arp_count||0)>rows.length?`<p class="caption">Đang hiển thị ${rows.length}/${esc(n.arp_count)} thiết bị. Mở “Mạng Windows / ARP” để xem toàn bộ.</p>`:'')+
      base;
  };

  pages.scan=async()=>{
    const n=await native70(canWrite(),true);
    return `<div class="noc-hero"><div class="hero-copy"><div class="kicker">WINDOWS NATIVE NETWORK</div><h2>Mạng hiện tại & ARP</h2><p>Đọc trực tiếp adapter, IPv4 LAN, subnet, default gateway, bảng ARP/neighbor và ping từ chính máy Windows đang chạy ứng dụng.</p></div><div class="hero-actions">${button('Làm mới','desktop70-refresh',{},'primary')}</div></div>`+
      nativeCards70(n)+
      panel('Tất cả thiết bị ARP / Neighbor',arpTable70(n.devices||[]))+
      panel('Ý nghĩa dữ liệu',`<p class="caption">ARP/Neighbor là các thiết bị mà Windows đã quan sát trong LAN. Ping “Online” nghĩa là thiết bị trả lời ICMP tại thời điểm kiểm tra; thiết bị có thể chặn ping nhưng vẫn xuất hiện trong ARP.</p>`);
  };

  actions['desktop70-refresh']=async()=>{await go(state.page==='scan'?'scan':'dashboard')};

  let timer70=null;
  window.addEventListener('na46:ready',()=>{
    if(timer70)clearInterval(timer70);
    timer70=setInterval(()=>{
      if(state.user&&state.live&&document.visibilityState==='visible'&&(state.page==='dashboard'||state.page==='scan')){if(typeof window.refreshPage46==='function')void window.refreshPage46(state.page);else void go(state.page);}
    },30000);
  });
  window.addEventListener('na46:logout',()=>{if(timer70){clearInterval(timer70);timer70=null;}});
})();
