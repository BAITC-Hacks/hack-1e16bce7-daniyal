import { notFound } from 'next/navigation';
import { EmployeeScreen } from '../../components/employee-screen';
import type { EmployeeView } from '../../components/employee-profile';
export default async function EmployeePage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (!['career', 'recommendations', 'activities', 'history'].includes(section)) notFound();
  return <EmployeeScreen key={section} view={section as EmployeeView} />;
}
