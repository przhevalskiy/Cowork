"""
Lightweight intent classifier for Cowork marketing communications intake.
Uses regex pattern matching — zero latency, no LLM call.
"""
import re
from dataclasses import dataclass


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: str        # Machine key: "research", "event", "social_media", "media", "other"
    label: str         # Display label: "Research", "Event", "Social Media", etc.
    prompt_suffix: str # Appended to system prompt to guide intake conversation


INTENT_DEFINITIONS = [
    {
        "intent": "research",
        "label": "Research",
        "patterns": [
            r"\bresearch\b",
            r"\bpr request\b",
            r"\bpress release\b",
            r"\bpitch\b",
            r"\bstory (idea|pitch|angle)\b",
            r"\bjournalist\b",
            r"\bmedia (outreach|pitch|coverage|placement)\b",
            r"\bpublication\b",
            r"\bnewswire\b",
            r"\bbyline\b",
            r"\bop.?ed\b",
            r"\bthought leadership\b",
            r"\bsecure (coverage|placement|a story)\b",
            r"\bget (coverage|a story|press)\b",
            r"\bwant (coverage|a story|press|to pitch)\b",
        ],
        "prompt_suffix": (
            "\n\nThis request is likely for media outreach, a press release, or PR coverage. "
            "Use service_type: media_outreach or web_article as appropriate. "
            "Make sure to capture the story angle, target outlets, and spokesperson in the 'details' field."
        ),
    },
    {
        # Checked before "event" so that "social media posts for an event" routes here, not event_promotion.
        "intent": "social_media",
        "label": "Social Media",
        "patterns": [
            r"\bsocial media\b",
            r"\binstagram\b",
            r"\blinkedin\b",
            r"\btwitter\b",
            r"\bx\.com\b",
            r"\bfacebook\b",
            r"\bsocial (post|content|copy|campaign|strategy)\b",
            r"\bpost(s)? (for|on) (instagram|linkedin|twitter|facebook|social)\b",
            r"\bcaption(s)?\b",
            r"\bhashtag(s)?\b",
            r"\breels?\b",
            r"\bstories (for|on)\b",
        ],
        "prompt_suffix": (
            "\n\nThis request is for social media content. "
            "Use service_type: social_media. "
            "Capture the target platforms, event or topic being promoted, tone, any tagging requirements, "
            "and brand guidelines in the 'details' field."
        ),
    },
    {
        "intent": "event",
        "label": "Event",
        "patterns": [
            r"\bevent\b",
            r"\blaunch (event|party|reception)\b",
            r"\bproduct launch\b",
            r"\bconference\b",
            r"\bwebinar\b",
            r"\bpanel\b",
            r"\bspeaking (engagement|slot|opportunity)\b",
            r"\btradeshow\b",
            r"\btrade show\b",
            r"\bexpo\b",
            r"\bsummit\b",
            r"\bforum\b",
            r"\bannouncement\b",
            r"\bpress (event|conference|briefing)\b",
            r"\bmedia (day|event|briefing)\b",
        ],
        "prompt_suffix": (
            "\n\nThis request involves an event. "
            "Determine the right service_type based on what the user actually needs: "
            "event_promotion for pre-event marketing, event_coverage for photography or recap content, "
            "social_media if the primary deliverable is social media posts about the event. "
            "Make sure to capture the event name, date, and deliverables needed in the 'details' field."
        ),
    },
    {
        "intent": "media",
        "label": "Media",
        "patterns": [
            r"\bmedia kit\b",
            r"\bpress kit\b",
            r"\bmedia contact\b",
            r"\bspokesperson\b",
            r"\bboilerplate\b",
            r"\bbrand (asset|guideline|guide|kit)\b",
            r"\blogo\b",
            r"\bheadshot\b",
            r"\bcompany (bio|fact sheet|overview|profile)\b",
            r"\bfact sheet\b",
            r"\bbackgrounder\b",
            r"\bpress (room|page|asset)\b",
            r"\bmedia (asset|resource|materials?)\b",
        ],
        "prompt_suffix": (
            "\n\nThis request involves media assets or a press kit. "
            "Use service_type: media_outreach or photo as appropriate. "
            "Capture the specific assets needed and usage context in the 'details' field."
        ),
    },
]


INTENT_LOOKUP: dict = {d["intent"]: d for d in INTENT_DEFINITIONS}


def get_intent_for_key(intent_key: str) -> IntentResult:
    """Return a pre-built IntentResult for a known intent key (e.g. from stored discussion.intent)."""
    defn = INTENT_LOOKUP.get(intent_key)
    if defn:
        return IntentResult(
            intent=defn["intent"],
            label=defn["label"],
            prompt_suffix=defn["prompt_suffix"],
        )
    return classify_intent("")


def classify_intent(message: str) -> IntentResult:
    """
    Classify the user's message into a Hive intake intent category.
    Returns the first matching intent, or the 'other' fallback.
    Uses case-insensitive regex matching — zero latency.
    """
    message_lower = message.lower().strip()

    for definition in INTENT_DEFINITIONS:
        if any(re.search(p, message_lower) for p in definition["patterns"]):
            return IntentResult(
                intent=definition["intent"],
                label=definition["label"],
                prompt_suffix=definition["prompt_suffix"],
            )

    return IntentResult(
        intent="other",
        label="General",
        prompt_suffix="",
    )
