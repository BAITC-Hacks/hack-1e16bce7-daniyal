import { notFound } from 'next/navigation';
import { HrDashboard, type HrView } from '../../../components/hr-dashboard';
import { Workspace } from '../../../components/workspace';
export default async function HrSection({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (!['employees', 'skill-gaps', 'activities', 'import'].includes(section)) notFound();
  return <Workspace hr><HrDashboard key={section} view={section as HrView} /></Workspace>;
}
