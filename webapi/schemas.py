from pydantic import BaseModel, Field
from webapi.model37 import StrictBaseModel
class LoginIn(StrictBaseModel): username: str; password: str
class MfaVerifyIn(StrictBaseModel): challenge: str=''; code: str
class MfaCodeIn(StrictBaseModel): code: str
class EventIn(StrictBaseModel): asset_ip: str=''; source: str; event_type: str; severity: str; title: str; detail: str=''
class IncidentIn(StrictBaseModel): title: str; severity: str='MEDIUM'; summary: str=''; owner: str=''
class PlaybookIn(StrictBaseModel): incident_id: int; name: str; action_type: str; target: str=''; notes: str=''
class VulnerabilityIn(StrictBaseModel):
    asset_ip: str; cve_id: str; product: str=''; installed_version: str=''; fixed_version: str=''; cvss: float=Field(0,ge=0,le=10); kev: bool=False; severity: str='MEDIUM'; source: str='MANUAL'; notes: str=''
class IdentityIn(StrictBaseModel): observed_mac: str=''; observed_hostname: str=''
class TcpProbeIn(StrictBaseModel): ports: list[int]=[22,80,443,445,3389]
class PatchIn(StrictBaseModel):
    asset_ip: str; patch_name: str; cve_id: str=''; status: str='PENDING'; due_date: str=''; owner: str=''; notes: str=''
class PatchStatusIn(StrictBaseModel): status: str; notes: str=''
class ComplianceUpdateIn(StrictBaseModel): status: str; evidence: str=''; owner: str=''
