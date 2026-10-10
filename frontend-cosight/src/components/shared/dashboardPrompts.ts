export interface DashboardPrompt {
  label: string;
  prompt: string;
}

export const OVERVIEW_PROMPTS: DashboardPrompt[] = [
  { label: 'Summarize last 30 days', prompt: 'Summarize marketing performance across all channels for the last 30 days' },
  { label: "What's trending?", prompt: 'What are the biggest trends and changes in our marketing data this month?' },
  { label: 'Compare channels', prompt: 'Compare performance across web, search, email, and social for the last 30 days' },
  { label: 'Build a report', prompt: 'Build a monthly marketing performance report for the last 30 days' },
];

export const SOCIAL_PROMPTS: DashboardPrompt[] = [
  { label: 'Explain the drop-off', prompt: 'Why did social impressions change in the last few days? Break it down by platform and account.' },
  { label: 'Top posts insight', prompt: 'What patterns do you see in our top-performing social posts this period?' },
  { label: 'Platform comparison', prompt: 'Compare LinkedIn, Instagram, and Facebook performance for Columbia Business School this period.' },
  { label: 'Build social report', prompt: 'Build a social media performance report for Columbia Business School for this date range.' },
];

export const WEB_PROMPTS: DashboardPrompt[] = [
  { label: 'Traffic drivers', prompt: 'What drove web sessions this period? Highlight top pages and any notable shifts.' },
  { label: 'Compare to prior', prompt: 'How does web traffic compare to the prior period? Call out the biggest changes.' },
  { label: 'Top pages', prompt: 'Analyze our top landing pages — what is working and what needs attention?' },
  { label: 'Build web report', prompt: 'Build a web analytics report for this date range.' },
];

export const SEO_PROMPTS: DashboardPrompt[] = [
  { label: 'Query winners', prompt: 'Which search queries gained or lost the most clicks this period?' },
  { label: 'CTR analysis', prompt: 'Analyze our search CTR and average position trends — what stands out?' },
  { label: 'Ranking shifts', prompt: 'Are there notable ranking changes for columbia business school keywords?' },
  { label: 'Build SEO report', prompt: 'Build a search performance report for this date range.' },
];

export const EMAIL_PROMPTS: DashboardPrompt[] = [
  { label: 'Campaign highlights', prompt: 'Summarize email campaign performance this period — opens, clicks, and standouts.' },
  { label: 'Compare to prior', prompt: 'How does email performance compare to the prior period?' },
  { label: 'Improve open rate', prompt: 'Based on recent email data, what might improve our open and click rates?' },
  { label: 'Build email report', prompt: 'Build an email marketing report for this date range.' },
];
