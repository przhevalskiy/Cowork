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

COWORK_TOOLS = [SHOW_CHECKLIST_TOOL, SUBMIT_TO_HIVE_TOOL]
