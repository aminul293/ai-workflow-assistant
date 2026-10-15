/** Preview-only form validation. The API independently validates every request. */
export function validateInquiry(input) {
  if (!input.sender.trim() || !input.subject.trim() || !input.body.trim()) return 'Complete sender, subject and inquiry text.';
  if (input.sender.length > 255 || input.subject.length > 255 || input.body.length > 10000) return 'Keep sender and subject within 255 characters and inquiry text within 10,000.';
  if (!/^[A-Z0-9._%+-]+@(?:[A-Z0-9](?:[A-Z0-9-]*[A-Z0-9])?\.)+test$/i.test(input.sender.trim())) return 'Use a fictional sender address ending in .test.';
  if (input.synthetic_ack !== true) return 'Confirm that this is fictional data.';
  return '';
}
export function validateDraft(value) {
  return !value.trim() || value.length > 2000 ? 'Draft must contain 1 to 2,000 characters.' : '';
}
export function apiErrorMessage(data) {
  if (data && typeof data.detail === 'string') return data.detail;
  if (data && Array.isArray(data.detail)) {
    const messages = data.detail.filter(x=>x && typeof x.msg === 'string').map(x=>x.msg).slice(0,3);
    if (messages.length) return messages.join(' ');
  }
  return 'Request failed. Please retry.';
}
