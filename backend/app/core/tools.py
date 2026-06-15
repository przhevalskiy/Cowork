"""Claude tool definitions for Cowork intake flow."""

_INTAKE_FIELDS = {
    "type": "object",
    "properties": {
        "contact_name": {"type": "string", "description": "Full name of the person making the request"},
        "role":         {"type": "string", "description": "Their role: Staff, Faculty, Student, or External"},
        "uni":          {"type": "string", "description": "Columbia UNI (e.g. ap3456). If not applicable use N/A"},
        "department":   {"type": "string", "description": "Their department or school"},
        "is_event":     {"type": "string", "description": "Is this request related to an event? Yes or No"},
        "service_type": {
            "type": "string",
            "description": "The Marcomms service sub-project this request belongs to",
            "enum": [
                "web_services",
                "media_outreach",
                "photo",
                "digital_screens",
                "web_article",
                "event_coverage",
                "youtube",
                "social_media",
                "event_promotion",
                "consultation",
            ],
        },
        "brief":   {"type": "string", "description": "Short project brief (1-2 sentences)"},
        "details": {"type": "string", "description": "Any additional context, links, deadlines, or attachments noted"},
    },
    "required": ["contact_name", "role", "department", "service_type", "brief"],
}

SHOW_CHECKLIST_TOOL = {
    "name": "show_checklist",
    "description": (
        "Display a structured summary checklist to the user showing all collected intake information. "
        "Call this when you have gathered all required fields. "
        "The user will review and confirm before submission."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "fields": _INTAKE_FIELDS,
            "intent": {
                "type": "string",
                "description": "The conversation intent",
                "enum": ["research", "event", "social_media", "media", "other"],
            },
        },
        "required": ["fields", "intent"],
    },
}

SUBMIT_TO_HIVE_TOOL = {
    "name": "submit_to_hive",
    "description": (
        "Submit the completed and confirmed intake form to the correct Hive Marcomms sub-project. "
        "Only call this after the user has reviewed the checklist and confirmed they want to submit."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "fields": _INTAKE_FIELDS,
            "intent": {
                "type": "string",
                "description": "The conversation intent",
                "enum": ["research", "event", "social_media", "media", "other"],
            },
        },
        "required": ["fields", "intent"],
    },
}

# ---------------------------------------------------------------------------
# VDR (research impact / success) submission flow
# ---------------------------------------------------------------------------

_VDR_FIELDS = {
    "type": "object",
    "properties": {
        "submitter_role": {
            "type": "string",
            "description": "Who is submitting this report",
            "enum": [
                "Faculty member",
                "PhD student",
                "Staff member submitting on behalf of a faculty member",
            ],
        },
        "faculty_name": {"type": "string", "description": "Full name of the faculty member whose achievement this is (their own name if they are the submitter)"},
        "division": {
            "type": "string",
            "description": "The faculty member's CBS division",
            "enum": [
                "Accounting",
                "Decision, Risk and Operations",
                "Economics",
                "Finance",
                "Management",
                "Marketing",
                "Other",
            ],
        },
        "impact_type": {
            "type": "string",
            "description": "The type of research impact / success being reported",
            "enum": [
                "Award",
                "Book",
                "Case Study",
                "Grant",
                "Media mention",
                "Notable Service",
                "Research article",
                "Speaking Engagement/Major event appearance",
                "Other",
            ],
        },
        "summary":           {"type": "string", "description": "Short title or summary of the achievement (e.g. paper or book title, award name, outlet and topic of the media mention)"},
        "area_of_expertise": {"type": "string", "description": "Area of expertise associated with the impact event"},
        "collaborators":     {"type": "string", "description": "CBS collaborator name(s) — faculty and current or former PhD students. Use 'None' if there were no CBS collaborators."},
        "promo_channels":    {"type": "string", "description": "Comma-separated outreach channels the school may use to promote this (e.g. CBS Website, Social Media, Research in Brief), or 'None (website citation only)'"},
        "details":           {"type": "string", "description": "Any additional context to share about the achievement"},
    },
    "required": ["submitter_role", "faculty_name", "division", "impact_type", "summary", "collaborators"],
}

SHOW_VDR_CHECKLIST_TOOL = {
    "name": "show_vdr_checklist",
    "description": (
        "Display a structured summary checklist of a research impact / success (VDR) submission "
        "for the user to review. Call this once all required VDR fields are gathered. "
        "The user will review and confirm before submission."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"fields": _VDR_FIELDS},
        "required": ["fields"],
    },
}

SUBMIT_VDR_TOOL = {
    "name": "submit_vdr",
    "description": (
        "Submit the completed and confirmed research impact / success (VDR) report to the correct "
        "VDR sub-project in Hive. Only call this after the user has reviewed the checklist and "
        "confirmed they want to submit."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"fields": _VDR_FIELDS},
        "required": ["fields"],
    },
}

COWORK_TOOLS = [SHOW_CHECKLIST_TOOL, SUBMIT_TO_HIVE_TOOL, SHOW_VDR_CHECKLIST_TOOL, SUBMIT_VDR_TOOL]
