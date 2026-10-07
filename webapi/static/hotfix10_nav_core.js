'use strict';
/* QA77: install authoritative navigation once and preserve user-open state. */
(()=>{
  if(window.__naHotfix10Installed)return;
  window.__naHotfix10Installed=true;
  const desired=[
    ['TỔNG QUAN',['dashboard','daily57','soc51','taskcenter47']],
    ['🛡 HACKER MŨ TRẮNG · PHÒNG THỦ',['bluehub61','wintools79','scan','ipmac','vuln51','bluetls62','blueids62','blueweb61','blueapi62','bluesecrets62','bluelog61','bluemalware62','bluepass61','bluefirewall62','blueiam62','blueir62','bluecontainer62','bluefim62','blueedr62','bluephish62','siem51','threat54','endpoint58','secpost51']],
    ['🥷 HACKER MŨ ĐỎ · RED TEAM LAB',['redlocal79','redhub61','redinject61','redxss61','redidor61','redupload62','redredirect62','redssrf62','redxxe62','redauth61','redpacket61','redload61','redhash62','redsupply62','redsession62','redmitm62','redtunnel62','redprivesc62','redpersist62','redevasion62']],
    ['THIẾT BỊ & HẠ TẦNG',['devices','managed','profiles','organization','topology','lan','netspeed59','pingmonitor','history','monitoringx','health','server','snmp','extensions','remote']],
    ['VẬN HÀNH & PHẢN ỨNG',['autoip','audit','terminal','backup','compare','dailyaudit','scheduler','restore','readiness','jobs','compliance53','notify56','reports','cases55','security','alerts','rules','incidents','services','sla','inbox47']],
    ['QUẢN TRỊ',['accounts','credentials','vault51','crypto51','production','runtime47','system46','platform50','auditall','notify','logs','diag','settingsx','password']]
  ];
  const apply=()=>{try{groups.splice(0,groups.length,...desired);state.groupOpen={0:true,1:true,2:true,3:false,4:false,5:false,...(state.groupOpen||{})};if(typeof navigation==='function')navigation();const sub=document.querySelector('.brand small');if(sub)sub.textContent='NetworkAutomation Desktop / UI '+NA_UI_VERSION;document.documentElement.dataset.naUiBuild=NA_UI_VERSION;}catch(e){console.error('QA77_NAV_CORE',e)}};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',apply,{once:true});else apply();
  window.naHotfix10={version:NA_UI_VERSION,navigation:'core-authoritative-once'};
})();
