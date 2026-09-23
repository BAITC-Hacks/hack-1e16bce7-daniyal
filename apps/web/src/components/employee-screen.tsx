'use client';
import { EmployeeProfile, type EmployeeView } from './employee-profile';
import { Workspace, useSession } from './workspace';
export function EmployeeScreen({ view = 'dashboard' }: { view?: EmployeeView }) {
  const { user } = useSession();
  return <Workspace>{user?.role === 'employee' && user.employee_id && <EmployeeProfile key={user.employee_id} employeeId={user.employee_id} view={view} />}</Workspace>;
}
