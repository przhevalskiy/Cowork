"""Hive API integration — routes requests to the correct Marcomms sub-project."""
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

HIVE_BASE_URL = "https://app.hive.com/api/v2"
WORKSPACE_ID = "MvJ2A7jmTiCJcheoM"

# Marcomms Service Requests sub-project IDs
SERVICE_PROJECT_MAP = {
    "web_services":     "46u9tbXY28SyHXxty",
    "media_outreach":   "Nq9yjjP6MTRh33Pbs",
    "photo":            "9Pkm2bSg7hMWNs4Jy",
    "digital_screens":  "n2pgMprEkoSTSXA6f",
    "web_article":      "WJJfzensshDySmwfs",
    "event_coverage":   "ouLeGxMQriFRFsYsW",
    "youtube":          "mfTJrGj6FrTaBnviz",
    "social_media":     "GNPJiJnFMuzD54CvH",
    "event_promotion":  "Xov2Fcmcdm5cktzje",
    "consultation":     "qT3WRqYtoyqLLAkJG",
}

SERVICE_LABELS = {
    "web_services":    "Web Services/Digital Marketing",
    "media_outreach":  "Media Outreach",
    "photo":           "Photo Request",
    "digital_screens": "Digital Screens",
    "web_article":     "Web Article",
    "event_coverage":  "Event Coverage",
    "youtube":         "YouTube/Video",
    "social_media":    "Social Media",
    "event_promotion": "Event Promotion",
    "consultation":    "MarComms Consultation",
}

# VDR Impact Submissions — sub-project IDs (parent: Ha2kdQfm8v5CSd3hp).
# impact_type drives routing; everything not explicitly mapped falls back to
# the "_default" entry ("VDR_Research and Impact Submissions").
VDR_AWARDS_PROJECT_ID       = "y3PEd49oAfrjG3MPL"   # VDR Awards Submissions
VDR_MEDIA_PROJECT_ID        = "ttf3zbwo2jKBoexHn"   # VDR Media Mention Submissions
VDR_RESEARCH_PROJECT_ID     = "W2ChxFDWE8WhFbuE5"   # VDR_Research and Impact Submissions

VDR_PROJECT_MAP = {
    "Award":         VDR_AWARDS_PROJECT_ID,
    "Media mention": VDR_MEDIA_PROJECT_ID,
    "_default":      VDR_RESEARCH_PROJECT_ID,
}

# ---------------------------------------------------------------------------
# UAT routing tables — twins of the production maps above.
# When HIVE_UAT_MODE is enabled, requests route through these instead, using
# the SAME service_type / impact_type keys, so per-service routing is exercised
# end-to-end against test folders.
#
# >>> FILL IN: paste the Hive project ID of each UAT folder you create. <<<
# Any key left blank fails closed (raises) rather than firing a real ticket.
# ---------------------------------------------------------------------------
UAT_SERVICE_PROJECT_MAP = {
    "web_services":     "",
    "media_outreach":   "",
    "photo":            "",
    "digital_screens":  "",
    "web_article":      "",
    "event_coverage":   "",
    "youtube":          "",
    "social_media":     "",
    "event_promotion":  "",
    "consultation":     "",
}

UAT_VDR_PROJECT_MAP = {
    "Award":         "",
    "Media mention": "",
    "_default":      "",
}

_hive_service: Optional["HiveService"] = None


def _build_description(fields: dict) -> str:
    """Format collected fields as structured HTML matching the Hive form layout."""
    contact   = fields.get("contact_name", "—")
    role      = fields.get("role", "—")
    uni       = fields.get("uni", "—")
    dept      = fields.get("department", "—")
    is_event  = fields.get("is_event", "—")
    service   = SERVICE_LABELS.get(fields.get("service_type", ""), fields.get("service_type", "—"))
    brief     = fields.get("brief", "—")
    details   = fields.get("details", "—")

    return (
        "<h3>Section I — Point of Contact</h3>"
        f"<p><strong>Name:</strong> {contact}</p>"
        f"<p><strong>Role:</strong> {role}</p>"
        f"<p><strong>UNI:</strong> {uni}</p>"
        f"<p><strong>Department:</strong> {dept}</p>"
        f"<p><strong>Is this for an event?</strong> {is_event}</p>"
        "<h3>Section II — Request Details</h3>"
        f"<p><strong>Service:</strong> {service}</p>"
        f"<p><strong>Project brief:</strong> {brief}</p>"
        f"<p><strong>Additional details:</strong> {details}</p>"
        "<p><em>Submitted via Cowork</em></p>"
    )


def _build_vdr_description(fields: dict) -> str:
    """Format collected VDR fields as structured HTML matching the research-impact form."""
    role       = fields.get("submitter_role", "—")
    faculty    = fields.get("faculty_name", "—")
    division   = fields.get("division", "—")
    impact     = fields.get("impact_type", "—")
    summary    = fields.get("summary", "—")
    expertise  = fields.get("area_of_expertise", "—")
    collab     = fields.get("collaborators", "—")
    channels   = fields.get("promo_channels", "—")
    details    = fields.get("details", "—")

    return (
        "<h3>Section I — General Information</h3>"
        f"<p><strong>Submitting as:</strong> {role}</p>"
        f"<p><strong>Faculty member:</strong> {faculty}</p>"
        f"<p><strong>Division:</strong> {division}</p>"
        "<h3>Section II — Research Impact</h3>"
        f"<p><strong>Impact type:</strong> {impact}</p>"
        f"<p><strong>Summary:</strong> {summary}</p>"
        f"<p><strong>Area of expertise:</strong> {expertise}</p>"
        f"<p><strong>CBS collaborator(s):</strong> {collab}</p>"
        "<h3>Section III — Sharing Your Success</h3>"
        f"<p><strong>Promote via:</strong> {channels}</p>"
        f"<p><strong>Additional details:</strong> {details}</p>"
        "<p><em>Submitted via Cowork</em></p>"
    )


class HiveService:
    def __init__(self, api_key: str, user_id: str, uat_mode: bool = False):
        self._headers = {"api_key": api_key, "user_id": user_id}
        self._uat_mode = uat_mode

    def _resolve_project(self, prod_map: dict, uat_map: dict, key: str, default_key: str) -> str:
        """Pick the destination project for `key`, honouring UAT mode.

        Uses the UAT twin map when UAT mode is on, otherwise production.
        Falls back to `default_key` within the chosen map. In UAT mode an
        unmapped/blank key fails closed, so testing never leaks a real ticket
        into a production project.
        """
        table = uat_map if self._uat_mode else prod_map
        project_id = table.get(key) or table.get(default_key)
        if self._uat_mode and not project_id:
            raise ValueError(
                f"UAT mode is on but no UAT project is mapped for '{key}' "
                f"(default '{default_key}' is also blank). Fill in the UAT map "
                f"in hive_service.py before testing this request type."
            )
        return project_id

    async def create_action(self, fields: dict) -> dict:
        service_type = fields.get("service_type", "consultation")
        project_id = self._resolve_project(
            SERVICE_PROJECT_MAP, UAT_SERVICE_PROJECT_MAP, service_type, "consultation"
        )

        contact = fields.get("contact_name", "Unknown")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %I:%M %p")
        brief = fields.get("brief", "Communications request")
        title = f"{brief[:60]} - MarComms Service Request - {contact} {ts}"

        payload = {
            "workspaceId": WORKSPACE_ID,
            "projectId": project_id,
            "title": title,
            "description": _build_description(fields),
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{HIVE_BASE_URL}/actions",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def create_vdr_action(self, fields: dict) -> dict:
        impact_type = fields.get("impact_type", "")
        project_id = self._resolve_project(
            VDR_PROJECT_MAP, UAT_VDR_PROJECT_MAP, impact_type, "_default"
        )

        faculty = fields.get("faculty_name") or fields.get("summary", "Faculty")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %I:%M %p")
        summary = fields.get("summary", "Research impact")
        title = f"{summary[:60]} - VDR {impact_type or 'Submission'} - {faculty} {ts}"

        payload = {
            "workspaceId": WORKSPACE_ID,
            "projectId": project_id,
            "title": title,
            "description": _build_vdr_description(fields),
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{HIVE_BASE_URL}/actions",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def get_action(self, action_id: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{HIVE_BASE_URL}/actions/{action_id}",
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()


def get_hive_service() -> HiveService:
    global _hive_service
    if _hive_service is None:
        settings = get_settings()
        _hive_service = HiveService(
            api_key=settings.hive_api_key,
            user_id=settings.hive_user_id,
            uat_mode=settings.hive_uat_mode,
        )
    return _hive_service
