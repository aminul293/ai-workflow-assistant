export type InquiryInput = {sender:string;subject:string;body:string;synthetic_ack:boolean};
export function validateInquiry(input:InquiryInput):string;
export function validateDraft(value:string):string;
export function apiErrorMessage(data:unknown):string;
