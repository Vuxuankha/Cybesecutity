'use strict';
/* QA77 compatibility shim. Red/Black Hat is configuration-only. */
(()=>{
  if(window.__naHotfix9Installed)return;
  window.__naHotfix9Installed=true;
  window.naHotfix9={version:NA_UI_VERSION,navigation:'no-op',mode:'red-config-only',kaliRedProfiles:[]};
})();
