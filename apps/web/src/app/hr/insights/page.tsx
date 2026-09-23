import { redirect } from 'next/navigation';

export default function InsightsPage() { redirect('/hr#' + encodeURIComponent('Данные')); }
