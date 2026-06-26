// Request types a project can be locked to. Mirrors the backend routing:
// MarComms service_type values (app/services/hive_service.py SERVICE_LABELS)
// plus the VDR research-impact flow. `serviceType` is sent as locked_service_type;
// `intent` is sent as locked_intent so the chat can seed the right flow.

export interface RequestType {
  /** Stored in project.locked_service_type (undefined for the VDR flow). */
  serviceType?: string;
  /** Stored in project.locked_intent. */
  intent: string;
  label: string;
}

// `intent` values must match the backend intent keys
// (research | event | social_media | media | other); see intent_classifier.py.
export const REQUEST_TYPES: RequestType[] = [
  { serviceType: 'web_services', intent: 'other', label: 'Web Services / Digital Marketing' },
  { serviceType: 'media_outreach', intent: 'media', label: 'Media Outreach' },
  { serviceType: 'photo', intent: 'other', label: 'Photo Request' },
  { serviceType: 'digital_screens', intent: 'other', label: 'Digital Screens' },
  { serviceType: 'web_article', intent: 'other', label: 'Web Article' },
  { serviceType: 'event_coverage', intent: 'event', label: 'Event Coverage' },
  { serviceType: 'youtube', intent: 'other', label: 'YouTube / Video' },
  { serviceType: 'social_media', intent: 'social_media', label: 'Social Media' },
  { serviceType: 'event_promotion', intent: 'event', label: 'Event Promotion' },
  { serviceType: 'consultation', intent: 'other', label: 'MarComms Consultation' },
  { intent: 'research', label: 'VDR Research & Impact Submission' },
];

/** Resolve a stored project lock back to its RequestType (for display/seeding). */
export function findRequestType(
  intent?: string | null,
  serviceType?: string | null,
): RequestType | undefined {
  if (serviceType) {
    return REQUEST_TYPES.find(t => t.serviceType === serviceType);
  }
  return REQUEST_TYPES.find(t => !t.serviceType && t.intent === intent);
}

export function requestTypeLabel(
  intent?: string | null,
  serviceType?: string | null,
): string {
  return findRequestType(intent, serviceType)?.label ?? 'Any request type';
}
